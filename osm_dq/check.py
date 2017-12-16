"""
Functions that define the checks, typically ingest a list of features, and objects to check against
"""
import copy
import rtree
import shapely
import logging
import numpy as np

# package components
import filter


def check_data_model(feats, check_keys={}, check_ranges={}, check_conditions=[], schema=None,
                     keep_original=False, flag_suffix='_flag', global_props={}, add_props={}, logger=logging):
    """
    checks all features in list "feats" for compliancy with a data model

    Args:
        feats: list of JSON-type features (with 'geometry' and 'properties')
        check_keys={}: dictionary of keys with datatypes
        check_ranges={}: dictionary of keys with values
        check_conditions={}: dictionary of conditions to be met before checking is required
        schema=None: fiona schema that should be followed. If None, then schema is copied from features and all keys are copied
        keep_original=False: if set to True, the values (read as string) will be converted to their mandated key type
        flag_suffix='_flag': suffix to use for keys showing the flag value
        logger=logging: reference to logger object for messaging

    Returns:
        feats_checked: list of JSON-type features with 'properties' containing the flag values after data model checking
    """

    def _value_in_range(value, range_list):
        if isinstance(value, float):
            # check if value is in between first and second validation nr (when type is float)
            return _check_range(value, range_list)
        else:
            return ((value in range_list) or (len(range_list) == 0))

    def _check_range(value, range_list):
        """
        Check if a value lies within a predefined range
        if the range does not consist of 2 numbers, a None is returned
        Inputs:
            value: float or integer to check if it lies within range
            range_list: list of 2 numbers used to check valid range. These do not have to be in ascending order
        """

        if len(range_list) != 2:
            return None

        if np.min(range_list) <= value <= np.max(range_list):
            return True
        return False

    def _flag_data_model(check_keys, check_ranges, key, v):
        """
        Checks if value in a given key is according to a given data model,
        consisting of a mandated data type and allowed values
        :param check_keys: dictionary, with key names and mandated data type
        :param check_ranges: dictionary with key names and mandated data values
        :param key: key to check with data model (if it exists in the data model, then check!)
        :param v: value of key to check with data model
        :return:
            v_checked: checked value (left empty if checks are not successful
            flag: flag value with check, can be:
                (None) key is not required in data model
                (0) value is valid
                (1) there is a value of correct type but not within range of valid values
                (2) there is a value but in wrong data type (e.g. string instead of float)
                (3) there is no value (i.e. v is None or empty string)
        """
        if not (key in check_keys) and not (key in check_ranges):
            # nothing to be checked, so return with a flag=None
            return v, None

        if (key in check_keys) and (v is not None):
            # field value should have a mandated data type, check validity
            ftype = check_keys[key]
            v_checked = filter.check_Ftype(ftype, v)
            if v_checked:  # if not an empty string or None is returned
                flag = 0  # there is data, we assume in the right data model if any
                if key in check_ranges:
                    # check if v_checked is in range
                    if not _value_in_range(v_checked, check_ranges[key]):
                        flag = 1
            else:
                v_checked = ''
                if v:
                    flag = 2  # there is data, but wrong data type
                else:
                    flag = 3  # there is no data (v = '')

        else:
            # only flags 0, 1 and 3 are possible
            # field value should only follow a valid value range
            flag = 0  # first assume value is within range, then check and update
            if isinstance(v, str):
                v_checked = v.lower()
            else:
                v_checked = v
            if key in check_ranges:
                # check if v_checked is in range
                if not _value_in_range(v_checked, check_ranges[key]):
                    flag = 1
            if v_checked is None:  # v should be checked, but is None, and
                flag = 3
        return v_checked, flag
    feats_checked = []
    for n, feat in enumerate(feats):
        if schema is not None:
            props_schema = schema['properties']
        else:
            props_schema = {}
            for key in feat['properties']:
                props_schema[key] = type(feat['properties'][key]).__name__

                # set field values based on field in scheme
        props = {}
        # add any properties in global_props (usually the name of bounding box area
        for key in global_props:
            props[key] = global_props[key]
        # add any additional properties that you want to see copied to the feature without any check
        for key in add_props:
            try:
                props[key] = feat['properties'][key]
            except:
                props[key] = None

        for key in props_schema:
            # name of the flag tag
            key_flag = key + flag_suffix
            # determine conditional statements
            if check_conditions.has_key(key):
                # check if conditions are met
                logical_and = check_conditions[key]['logical_and']
                conditions_list = []
                for cond_key, cond_value in check_conditions[key]['conditions']:
                    # check if condition is met
                    conditions_list.append(feat['properties'][cond_key] == cond_value)
                # now check if conditions are met
                if logical_and == True:
                    conditions_met = np.all(conditions_list)
                else:
                    conditions_met = np.any(conditions_list)
            else:
                conditions_met = True
            try:
                v = feat['properties'][key]
            except:
                v = None
                pass
            if conditions_met:
                v_check, v_flag = _flag_data_model(check_keys, check_ranges, key, v)
                props[key] = v
                if v_flag is not None:
                    # key is within data model (else, don't use key)
                    if not (keep_original):
                        props[key] = v_check
                    props[key_flag] = v_flag
            else:
                props[key] = v
                props[key_flag] = None  # None means N/A
        # make a new features

        feat_checked = filter.create_feature(feat['geometry'], missing_value=None, **props)
        feats_checked.append(feat_checked)
    return feats_checked


def check_connectivity(feats, key, values=[], tolerance=0.0001, check_keys={}, check_ranges={}, logger=logging,schema=None):
    """
    checks the connectivity of all features in list "feats". Connected features are given the same connected_id, based on the
    initialy selected feature.

    Args:
        feats: list of JSON-type features (with 'geometry' and 'properties')
        select_id={}: id of the selected elemenet for which the connected network will be checked. Is set in ini-file
        tolerance=: tolerance where within elements are assumend to be connected. Is set in ini-file
        check_keys={}: dictionary of keys with datatypes
        logger=logging: reference to logger object for messaging

    Returns:
        feats: list of JSON-type features with 'properties' containing the connected flag (id)
    """
    feats_ = copy.copy(feats)

    # Build a spatial index to make all faster
    tree_idx = rtree.index.Index()
    lines_bbox = [l['geometry'].buffer(tolerance).bounds for l in feats_]

    for i, bbox in enumerate(lines_bbox):
        tree_idx.insert(i, bbox)

    # Create two new properties, needed to check connectivity. Initial value == 0
    for i, feat in enumerate(feats_):
        feat['properties']['connected'] = 0
        feat['properties']['endpoints'] = 0

    # Make a list of the selected elements, for which we need to check the connectivity
    select_ids = [idx for idx in np.arange(0, len(feats_)) if str(feats_[idx]['properties'][key]) in values]
    # Now start the actual check, looping over the selected elements
    for select_id in select_ids:
        # First set the properties of the selected elements
        feats_[int(select_id)]['properties']['connected'] = feats_[select_id]['properties'][key]
        feats_[int(select_id)]['properties']['endpoints'] = 2
        to_check = 1
        endpoints_list = [select_id]
        while to_check > 0:
            for endpoint_id in endpoints_list:
                # Find all elements for which the bounding box connects to the selected element to narrow
                # the number of elements to loop over.
                hits = list(tree_idx.intersection(lines_bbox[int(endpoint_id)], objects=False))
                for i in hits:
                    # Ugly solution to solve the issue
                    if feats_[i]['properties']['endpoints'] > 0:
                        feats_[i]['properties']['endpoints'] = feats_[i]['properties']['endpoints'] - 1

                    # Check if element is not itself, to overcome the issue of endless loop.
                    if feats_[i]['properties']['connected'] != feats_[select_id]['properties'][key]:
                        ## Now check is elements are disjoint. If disjoint, continue to the next step.
                        if feats_[i]['geometry'].disjoint(feats_[int(endpoint_id)]['geometry'].buffer(tolerance)):
                            continue
                        else:
                            # If elements are not disjoint, change the properties and add element to the "connected" list.
                            feats_[i]['properties']['endpoints'] = 15
                            feats_[i]['properties']['connected'] = feats_[select_id]['properties'][key]

            endpoints_list = [j for j, feat in enumerate(feats_) if feat['properties']['endpoints'] > 0]
            to_check = len(endpoints_list)

    return feats_


def check_crossings(feats_1, feats_2, key_bridge, value_bridge, key_tunnel, value_tunnel, props={}, logger=logging):
    """
    locates crossings of all features in list "feats_1" with features in list "feats_2". Result: list of pairs of
    objects from feats_1 and feats_2
    For each crossing, establishes if a data model entry is available to understand the crossing behaviour
    Uses functionality from check_data_model

    initialy selected feature.

    Args:
        feats: list of JSON-type features (with 'geometry' and 'properties')
        select_id={}: id of the selected elemenet for which the connected network will be checked. Is set in ini-file
        tolerance=: tolerance where within elements are assumend to be connected. Is set in ini-file
        check_keys={}: dictionary of keys with datatypes
        logger=logging: reference to logger object for messaging

    Returns:
        feats: list of JSON-type features with 'properties' containing the connected flag (id)
    """
    def _pair_crossings(feats_1, feats_2, buffer=0.0001):
        """
        Determines where features of one set cross with another, using spatial indexing
        """
        crossings = []
        all_feats = feats_1 + feats_2
        end_idx_1 = len(feats_1)  # last index of first feature set
        # make a list of bounding boxes so that we can perform spatial indexing
        lines_bbox = [f['geometry'].buffer(buffer).bounds for f in all_feats]
        tree_idx = rtree.index.Index()
        for i, bbox in enumerate(lines_bbox):
            tree_idx.insert(i, bbox)
        # now go over each feature from feats_1 and check which features of feats_2 it intersects using spatial indexing
        for idx_1 in range(end_idx_1):
            feat_1 = all_feats[idx_1]
            hits = np.array(list(tree_idx.intersection(lines_bbox[idx_1])))
            hits_feats_2 = hits[hits >= end_idx_1]
            for idx_2 in hits_feats_2:
                intersections = [(feat_1, feat_2) for feat_2 in list(np.array(all_feats)[hits_feats_2]) if feat_2['geometry'].intersects(feat_1['geometry'])]
            crossings += intersections
        return crossings

    def _check_dict(props, key, value):
        """
        Checks if feature has a key value pair according to filter
        Returns: True or False
        """
        if key in props.keys():
            f = props[key]
        else:
            return False
        # filter on key/values

        if isinstance(value, str):
            # if value is empty strings, pass all objects of key (unless f return nothing)
            if value == '':
                if f in ['', None, '-1']:
                    return False  # next feat
            # only matching key-value pairs
            else:
                if f != value:
                    return False
        # check against multiple values
        elif isinstance(value, list):
            if f not in value:
                return False
        return True

    def _flag_crossing(pass_1, pass_2, struct_1='bridge', struct_2='tunnel'):
        if pass_1 & pass_2:
            struct = '{:s} and {:s}'.format(struct_1, struct_2)
            flag = 0
        elif pass_1:
            struct = struct_1
            flag = 0
        elif pass_2:
            struct = struct_2
            flag = 0
        else:
            struct = ''
            flag = 1
        return struct, flag

    def _crossings_collection(crossings, key_1, key_2, values_1, values_2, name_1='highway', name_2='waterway', props={}):
        collection = []
        for c in crossings:
            ps = c[0]['geometry'].intersection(c[1]['geometry'])
            if isinstance(ps, shapely.geometry.LineString):
                ps = shapely.geometry.MultiPoint(zip(*ps.xy))
            elif isinstance(ps, shapely.geometry.Point):
                ps = [ps]
            # get all properties together
            props_1 = c[0]['properties']
            props_2 = c[1]['properties']
            pass_2 = _check_dict(props_2, key_2, values_2)
            pass_1 = _check_dict(props_1, key_1, values_1)
            struct, flag = _flag_crossing(pass_1, pass_2)

            props_cross = {'osm_id_{:s}'.format(name_1) : props_1['osm_id'],
                           'osm_id_{:s}'.format(name_2) : props_2['osm_id'],
                           'flag' : flag,
                           'structure' : struct,
                          }
            for prop in props:
                props_cross[prop] = props[prop]
            for n, p in enumerate(ps):
                collection.append(filter.create_feature(p, **props_cross))
        return collection

    crossings = _pair_crossings(feats_1, feats_2)
    return _crossings_collection(crossings, key_bridge, key_tunnel, value_bridge, value_tunnel, props=props)
