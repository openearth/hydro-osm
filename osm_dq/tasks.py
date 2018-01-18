"""
program specific tasks
These include the runners for tasks (typically require options, bbox, and logger arg): def run_<>
as well as getting the tasks done: def get_<>
"""

import os
import sys
import logging
import shapely
import shapely.geometry
import pandas as pd
import fiona

# package components
import filter
import io
import check
import copy

def get_osm_data(options, logger=logging):
    # prepare domain
    domain = shapely.geometry.Polygon([(options.xmin, options.ymax),
                                       (options.xmin, options.ymin),
                                       (options.xmax, options.ymin),
                                       (options.xmax, options.ymax)])
    bbox_latlon = domain.bounds
    logger.info('Downloading OSM data to {:s}'.format(options.osm_fn))
    if os.path.isfile(options.osm_fn):
        logger.warning(
            'File {:s} already exists, assuming download of OSM data is not necessary...'.format(options.osm_fn))
    else:
        io.download_overpass('{:s}.tmp'.format(options.osm_fn), bbox_latlon,
                          url_template='http://www.overpass-api.de/api/xapi_meta?*[bbox={xmin},{ymin},{xmax},{ymax}]')
        os.rename('{:s}.tmp'.format(options.osm_fn),
                  options.osm_fn)
    return None


def get_bounds(options, logger=logging):
    # find the geographical boundaries
    logger.info('Filtering bounds from {:s}'.format(options.osm_fn))
    bound_features = filter.filter_features(options.osm_fn,
                                     osm_config=options.osm_config,
                                     key=options.bounds['key'],
                                     value=options.bounds['value'],
                                     layer_index=options.bounds['layer_index'],
                                     wgs2utm=False,
                                     logger=logger,
                                     )
    if len(bound_features) > 1:
        logger.warning('More than one feature found, preparing a list of results per feature...')
    elif len(bound_features) == 0:
        logger.error('No bounding features found with key {:s} and value {:s}'.format(options.bounds['key']))
        sys.exit(1)
    else:
        # filter the all_features to only provide within-bounds
        logger.info('Found a unique bounding area with key {:s} and value {:s}'.format(options.bounds['key'],
                                                                             str(options.bounds['value'])))
    bbox = {}
    for val in options.bounds['value']:
        bb = shapely.geometry.MultiPolygon([bound_feature['geometry']
                                            for bound_feature in bound_features
                                            if bound_feature['properties'][options.bounds['key']] == val])
        bbox[val] = bb
    # bbox = [bound_feature['geometry'] for bound_feature in bound_features]
    if len(bbox) == 0:
        bbox = {} # [None]
    return bbox


def run_data_model_check(options, bbox, logger=logging):
    """
    run the data model checker
    :param options: options object
    :param bbox: (list of) bounding boxes
    :param logger: logging object
    :return: -
    """
    def get_data_model_check(options, bbox, global_props={}, logger=logging):
        """

        :param options: options object
        :param bbox: bounding box (shapely Polygon)
        :param global_props: properties that need to be added to all features (for instance name of bbox considered)
        :param logger: logging object
        :return: list of features with properties checked as well as properties with '_flag' that contain the flag value

        """
        logger.info('Filtering features from {:s}'.format(options.osm_fn))
        logger.info('Using key: {:s} and value: {:s}'.format(options.filter['key'], str(options.filter['value'])))
        all_features = filter.filter_features(options.osm_fn,
                                       osm_config=options.osm_config,
                                       key=options.filter['key'],
                                       value=options.filter['value'],
                                       layer_index=options.layer_index,
                                       wgs2utm=False,
                                       logger=logger,
                                       bbox=bbox,
                                       )
        logger.info('{:d} features found'.format(len(all_features)))

        # prepare schema
        schema = {
                  'geometry': options.layer_type,
                  'properties': options.json_types
        }
        logger.info('Checking data model')
        feats_checked = check.check_data_model(all_features,
                                         check_keys=options.key_types,
                                         check_ranges=options.key_ranges,
                                         check_conditions=options.conditions,
                                         schema=schema,
                                         keep_original=True,
                                         global_props=global_props,
                                         add_props=options.add_props,
                                         logger=logger,
                                         )

        return feats_checked

    schema = {
              'geometry': options.layer_type,
              'properties': options.json_types
    }
    # TODO get validation report in separate function
    feats_checked = []
    validation_report = {}
    for bb in bbox:
        if bbox[bb] is None:
            bound_filter_key = 'name_bound'
            bound_filter_name = 'full_area'
        else:
            bound_filter_key = options.bounds['key'] + '_bound'
            bound_filter_name = bb
        validation_report[bound_filter_name] = {}
        logger.info('Checking data model for {:s}'.format(bound_filter_name))
        _feats_checked = get_data_model_check(options, bbox[bb], global_props={bound_filter_key: bound_filter_name}, logger=logger)
        feats_checked += _feats_checked
        logger.info('Preparing data model validation report')
        for key in schema['properties']:
            key_flag = key + '_flag'
            flag = [feat['properties'][key_flag] for feat in _feats_checked]
            validation_report[bound_filter_name][key] = [flag.count(0),
                                                         flag.count(1),
                                                         flag.count(2),
                                                         flag.count(3),
                                                         ]

    prop_with_flags = {}
    for key in options.json_types:
        prop_with_flags[key] = options.json_types[key]
        prop_with_flags[key + '_flag'] = 'int'
        # add bounding box naming
        prop_with_flags[bound_filter_key] = 'str'

    if 'connectivity' in dir(options):
        for c_k in options.connectivity:
            logger.info('Filtering connect features from {:s}'.format(options.connectivity[c_k]['fn']))
            logger.info('Using key: {:s} and value: {:s}'.format(options.connectivity[c_k]['key'],
                                                                 str(options.connectivity[c_k]['value'])
                                                                 )
                        )
            feats_end_point = filter.filter_features(options.connectivity[c_k]['fn'],
                                                   osm_config=options.osm_config,
                                                   key=options.connectivity[c_k]['key'],
                                                   value=options.connectivity[c_k]['value'],
                                                   layer_index=options.layer_index,
                                                   wgs2utm=False,
                                                   logger=logger,
                                                   bbox=None,
                                                   )
            if len(feats_end_point) == 0:
                logger.warning('No connect features are found in {:s}. Skipping connectivity check'.format(options.connectivity[c_k]['fn'])
                             )
            else:
                prop_with_flags[c_k] = 'int'
                prop_with_flags[c_k + '_points'] = 'int'
                # perform connectivity check
                feats_checked = check.check_connectivity(feats_checked,
                                                         feats_end_point,
                                                         c_k,
                                                         options.connectivity[c_k]['uniqueid'],
                                                         tolerance=float(options.connectivity[c_k]['tolerance']),
                                                         logger=logger,
                                                         )



    # write data to GeoJSON file for further GIS-use.
    logger.info('Writing filtered and checked data to GeoJSON in {:s}'.format(options.report_json))

    # add the additional properties
    prop_with_flags.update(options.add_props)

    schema_flag = {
                  'geometry': options.layer_type,
                  'properties': prop_with_flags,
                  }

    io.write_layer(options.report_json,
                None,
                feats_checked,
                format='GeoJSON',
                write_mode='w',
                crs=fiona.crs.from_epsg(4326),
                schema=schema_flag,
                logger=logger,
                )
    # write reports to excel
    logger.info('Writing report to {:s}'.format(options.report_xlsx))
    writer = pd.ExcelWriter(options.report_xlsx)
    for bound_name in validation_report:
        df = pd.DataFrame(validation_report[bound_name])
        df.index = ['correct', 'invalid value', 'invalid data type', 'missing value']
        df.index.name = 'validation'
        df.to_excel(writer, bound_name)
    writer.save()


# def run_connectivity_check(options, bbox, logger):
#     logger.info('Filtering features from {:s}'.format(options.osm_fn))
#     logger.info('Using key: {:s} and value: {:s}'.format(options.filter['key'], str(options.filter['value'])))
#     feats = filter.filter_features(options.osm_fn,
#                            osm_config=options.osm_config,
#                            key=options.filter['key'],
#                            value=options.filter['value'],
#                            layer_index=options.layer_index,
#                            wgs2utm=False,
#                            logger=logger,
#                            bbox=None,
#                            )
#     # add connectivity flag to the model
#     schema = {
#               'geometry': options.layer_type,
#               'properties': options.json_types
#     }
#     feats_checked = check.check_data_model(feats,
#                                            check_keys=options.key_types,
#                                            check_ranges=options.key_ranges,
#                                            check_conditions=options.conditions,
#                                            schema=schema,
#                                            keep_original=True,
#                                            add_props=options.add_props,
#                                            logger=logger,
#                                            )
#     logger.info('Filtering connect features from {:s}'.format(options.connectivity['fn']))
#     logger.info('Using key: {:s} and value: {:s}'.format(options.connectivity['key'], str(options.connectivity['value'])))
#     feats_end_point = filter.filter_features(options.connectivity['fn'],
#                                            osm_config=options.osm_fn,
#                                            key=options.connectivity['key'],
#                                            value=options.connectivity['value'],
#                                            layer_index=options.layer_index,
#                                            wgs2utm=False,
#                                            logger=logger,
#                                            bbox=None,
#                                            )
#     if len(feats_end_point) == 0:
#         logger.error('No connect features are found in {:s}. Is your filter correct? {:s}: {:s}'.format(options.connectivity['fn'],
#                                                                                                         options.connectivity['key'],
#                                                                                                         options.connectivity['value']
#                                                                                                         )
#                      )
#         sys.exit(1)
#     prop_with_flags = {}
#     for key in options.json_types:
#         prop_with_flags[key] = options.json_types[key]
#         prop_with_flags[key + '_flag'] = 'int'
#     schema = {
#               'geometry': options.layer_type,
#               'properties': prop_with_flags,
#               }
#     feats_connected = check.check_connectivity(feats_checked,
#                                                # key=options.connectivity['key'],
#                                                # values=options.connectivity['value'],
#                                                feats_end_point,
#                                                options.connectivity['uniqueid'],
#                                                tolerance=float(options.connectivity['tolerance']),
#                                                logger=logger
#                                                )
#     logger.info('Writing filtered and checked data to GeoJSON in {:s}'.format(options.report_json))
#     props_schema = schema['properties']
#     props_schema['connected'] = 'int'
#     props_schema['endpoints'] = 'int'
#
#     # add the additional properties
#     props_schema.update(options.add_props)
#
#     schema = {
#               'geometry': options.layer_type,
#               'properties': props_schema,
#               }
#     io.write_layer(options.report_json,
#                    None,
#                    feats_connected,
#                    format='GeoJSON',
#                    write_mode='w',
#                    crs=fiona.crs.from_epsg(4326),
#                    schema=schema,
#                    logger=logger,
#                    )

def run_crossings_check(options, bbox, logger=logging):
    def get_crossings_check(options, bbox, props={}, logger=logging):
        logger.info('Checking crossings of waterways and highways')
        # make a list of results per filtered bbox
        highways = filter.filter_features(options.osm_fn,
                                   osm_config=options.osm_config,
                                   key=options.filter_highway['key'],
                                   value=options.filter_highway['value'],
                                   layer_index=1,
                                   wgs2utm=False,
                                   logger=logger,
                                   bbox=bbox,
                                   )
        waterways = filter.filter_features(options.osm_fn,
                                    osm_config=options.osm_config,
                                    key=options.filter['key'],
                                    value=options.filter['value'],  # these should be the waterways
                                    layer_index=1,
                                    wgs2utm=False,
                                    logger=logger,
                                    bbox=bbox,
                                    )
        crossings = check.check_crossings(highways,
                                    waterways,
                                    options.filter_bridge['key'],
                                    options.filter_bridge['value'],
                                    options.filter_tunnel['key'],
                                    options.filter_tunnel['value'],
                                    props=props,
                                    logger=logger,
                                    )
        return highways, waterways, crossings

    validation_report = {}

    highways = []
    waterways = []
    crossings = []
    for bb in bbox:
        if bbox[bb] is None:
            bound_filter_key = 'name_bound'
            bound_filter_name = 'full_area'
        else:
            bound_filter_key = options.bounds['key'] + '_bound'
            bound_filter_name = bb
        # _highways, _waterways, _crossings = get_crossings_check(options, bbox[bb], props={options.bounds['key']: bb}, logger=logger)
        _highways, _waterways, _crossings = get_crossings_check(options, bbox[bb],
                                                                props={bound_filter_key: bound_filter_name},
                                                                logger=logger)
        highways += _highways
        waterways += _waterways
        crossings += _crossings
        flag = [feat['properties']['flag'] for feat in _crossings]  # list all the flag values and write to df
        type = [feat['properties']['structure'] for feat in _crossings]  # list all the flag values and write to df
        validation_report[bb] = [flag.count(0),
                                 flag.count(1),
                                 type.count(options.filter_bridge['key']),
                                 type.count(options.filter_tunnel['key'])]

    df = pd.DataFrame(validation_report)
    df.index = ['correct', 'no info', 'nr. bridges', 'nr. tunnels']
    df.index.name = 'validation'
    logger.info('Writing report to {:s}'.format(options.report_xlsx))
    df.to_excel(options.report_xlsx)

    io.write_layer(options.report_json,
                None,
                crossings,
                format='GeoJSON',
                write_mode='w',
                crs=fiona.crs.from_epsg(4326),
                schema=None,
                logger=logger,
                )
    # remove any keys other than osm_id and key for bridges
    for n in range(len(waterways)):
        waterways[n]['properties'] = {key: waterways[n]['properties'][key] for key in ['osm_id', options.filter_tunnel['key']]}
    io.write_layer(options.report_json_water,
                None,
                waterways,
                format='GeoJSON',
                write_mode='w',
                crs=fiona.crs.from_epsg(4326),
                schema={'geometry': 'LineString',
                        'properties': {'osm_id': 'str',
                                       options.filter_tunnel['key']: 'str'
                                       }
                        },
                logger=logger,
                )

    for n in range(len(highways)):
        highways[n]['properties'] = {key: highways[n]['properties'][key] for key in ['osm_id', options.filter_bridge['key']]}
    io.write_layer(options.report_json_roads,
                None,
                highways,
                format='GeoJSON',
                write_mode='w',
                crs=fiona.crs.from_epsg(4326),
                schema={'geometry': 'LineString',
                        'properties': {'osm_id': 'str',
                                       options.filter_bridge['key']: 'str'
                                       }
                        },
                logger=logger,
                )
