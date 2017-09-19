"""
Functions for spatial and tag filtering
"""

import logging
import copy
import sys
import os
import rtree
import gdal
import shapely
import shapely.geometry
import numpy as np

from shapely.geometry import (Point, LineString, Polygon, shape, LinearRing,
                              MultiLineString, MultiPoint, MultiPolygon, GeometryCollection)

# package component
import utm


def toUTM(shape):
    new_coords = [utm.from_latlon(c[1], c[0])[:2] for c in shape.coords]
    if shape.type == 'LineString':
        return LineString(new_coords)
    elif shape.type == 'Polygon':
        return Polygon(new_coords)
    else:
        raise NotImplementedError('only shapely LineStrings and Polygons have been implemented')


def check_Ftype(ftype, value):
    try:
        v_out = ftype(value)  # parse
        if isinstance(v_out, str):
            v_out = v_out.lower()
    except:
        v_out = None
    return v_out


def create_feature(geom, **kwargs):
    feature = {"geometry": geom,
               "properties": {}}
    return add_properties(feature, **kwargs)


def add_properties(feature, missing_value='', **kwargs):
    for key in kwargs:
        if (not isinstance(kwargs[key], bool)) and (kwargs[key] is not None):
            feature['properties'][key] = kwargs[key]
        elif isinstance(kwargs[key], bool):
            feature['properties'][key] = int(kwargs[key])
        else:
            feature['properties'][key] = missing_value
    return feature


def multi2single_geoms(feature):
    # make separate data object for each geometry in multi geometry
    features = []
    if isinstance(feature['geometry'], (MultiLineString, MultiPoint, MultiPolygon, GeometryCollection)):
        i = 0
        for geom in feature['geometry']:
            # ft['geometry'] = feature['geometry'][i]
            if isinstance(geom, (LineString, Point, Polygon)):
                if geom.length > 0:
                    ft = copy.deepcopy(feature)
                    ft['geometry'] = geom
                    # keep unique id, but add geom_postfix property
                    ft['properties']['geom_postfix'] = "_{:03d}".format(i)
                    features.append(ft)
                    i += 1
            else:
                raise NotImplementedError("unknown geometry type {}".format(type(ft['geometry'])))
    else:
        features = [feature]
    return features



def filter_features(fn, layer_index=1, bbox=None, key='waterway', value='',
                    split_multigeoms=True, flatten=True, wgs2utm=True, logger=logging):
    """
    Filters out objects from a geo database (E.g. SQLite or OSM file) and a specified layer using key value pairs
    The values are checked for their datatype using "check_fields". If a different datatype is found than requested,
    this key/value pair is not parsed to the list of features
    Inputs:
        fn: filename of geo database or file (string)
        layer_index=1: integer, defining the layer in geo database to be used (=1 typically is line layer in OSM SQLite)
        bbox=None: shapely Polygon object indicating the domain, if supplied, any feature outside will be removed
        key: string, attribute used for filtering objects
        value: string or list with strings, value of attribute, used for filtering objects. if empty string all objects
            with key are passed
        split_multigeoms: Multi geometries are splitted into single geometries, the id is edited with _xxx
        logger=logging: handle to logging object far passing messages
    """

    def _check_osm(fn):
        """
        check if the file is an openstreetmap file or not
        Args:
            fn: gdal vector file name

        Returns: True/False

        """
        a = gdal.OpenEx(fn)
        drv = a.GetDriver().LongName
        a = None
        return drv.__contains__('OpenStreetMap')


    def _check_filter(feat, key, value):
        """
        Checks if feature has a key value pair according to filter
        Returns: True or False
        """
        if key in feat.keys():
            f = feat.GetField(key)
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


    def _props2dict(feat):
        """
        Translates all properties of a OGR feature to a JSON dictionary structure
        """
        properties = {}
        for i in range(feat.GetFieldCount()):
            fieldDef = feat.GetFieldDefnRef(i)
            fieldName = fieldDef.GetName()
            v = feat.GetField(fieldName)
            properties[fieldName] = v
        return properties
    if not(isinstance(bbox, list)):
        bbox = [bbox]
    assert os.path.isfile(fn), "Input file 'fn' {:s} does not exists".format(fn)
    assert isinstance(key, str), "Input variable 'key' should be of type string"
    assert isinstance(value, (str, list)), "Input variable 'value' should be of type string or list{string}"
    if isinstance(value, list):
        assert all(isinstance(n, str) for n in value), "Input variable 'value' should be of type string or list{string}"
    # check if dataset is of OpenStreetMap format
    osm_driver = _check_osm(fn)
    # read data
    if osm_driver:
        src_ds = gdal.OpenEx(fn, open_options=['CONFIG_FILE=osmconf_osm2dh.ini'])
    else:
        # assume the file can be read by any other driver
        src_ds = gdal.OpenEx(fn)
    src_lyr = src_ds.GetLayerByIndex(layer_index)
    all_features = [[]]*len(bbox)
    # features = []  # output is list of features
    for n, feat in enumerate(src_lyr):
        geom = shapely.wkt.loads(feat.GetGeometryRef().ExportToWkt())
        if wgs2utm:
            geom = toUTM(geom)
        # check if feature is completely outside domain (if so, discard)
        if bbox[0] is not None:
            try:
                geom_disjoint = [bb.buffer(0).disjoint(geom) for bb in bbox if bb is not None]
                if all(geom_disjoint):
                    continue
            except:
                logging('Could not perform disjoint operation on geometry, skipping...')
                continue
        else:
            geom_disjoint = [False]*len(bbox)
        # check if feature obeys to key/value filter. If not continue to next feature
        if not(_check_filter(feat, key, value)):
            continue
        # copy properties to JSON dictionary structure
        properties = _props2dict(feat)
        # read geometry
        try:
            ft = create_feature(geom, missing_value=None, **properties)
        except Exception as e:
            logger.warning('Error({0}), skipping geometry.'.format(e))
            continue

        if split_multigeoms:
            # geoms splitted and added "geom_postfix" property
            append = [features.append(ft) for disjoint, features in zip(geom_disjoint, all_features) if not(disjoint) for ft in multi2single_geoms(ft)]
        else:
            append = [features.append(ft) for disjoint, features in zip(geom_disjoint, all_features) if not(disjoint)]
    src_ds = None
    # if len(all_features) == 1:
    #     return all_features[0]
    # else:
    if flatten:
        return [y for x in all_features for y in x]
    else:
        return all_features

