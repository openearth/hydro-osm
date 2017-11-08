"""
Parsers for command line arguments and configuration files
- parse command line arguments
- parse ini file
- get arguments in ini file
- get list of arguments in ini file
- parse a filter from ini file

"""


import logging
import os
import sys
from optparse import OptionParser
from configobj import ConfigObj

# package components
import log
import io


def create_options():
    if len(sys.argv) == 1:
        print('No arguments given. Please run with option "-h" for help')
        sys.exit(0)
    parser = create_parser()
    (options, args) = parser.parse_args()
    if len(args) != 0:
        print('Incorrect number of arguments given. Please run with option "-h" for help')
        sys.exit(0)

    if not os.path.exists(options.inifile):
        print('path to ini file {:s} cannot be found'.format(os.path.abspath(options.inifile)))
        sys.exit(1)
    # required input
    if not options.dest_path:  # if destination is not given
        print('destination path not given')

    # file names and directory bookkeeping
    options.dest_path = os.path.abspath(options.dest_path)
    options.code_path = io.get_script_path()
    options.osm_config = os.path.join(options.code_path, 'osmconf_osm2dh.ini')
    logfilename = os.path.join(options.dest_path, 'osm_validation.log')
    # create dir if not exist
    if not os.path.isdir(options.dest_path):
        os.makedirs(options.dest_path)
    # delete old destination and log files
    else:
        if os.path.isfile(logfilename):
            os.unlink(logfilename)
    # set up the logger
    logger, ch = log.setlogger(logfilename, 'osm_validation', options.verbose)
    logger.info('$Id: check_data_model.py 13605 2017-08-23 13:28:23Z winsemi $')

    options = add_ini(options)
    if not (os.path.exists(options.osm_fn)) and not options.osm_download:
        print('path to osm datafile {:s} cannot be found'.format(options.osm_fn))
        sys.exit(1)

    if not (os.path.isdir(options.gis_path)):
        os.makedirs(options.gis_path)
    if not (os.path.isdir(options.report_path)):
        os.makedirs(options.report_path)

    # write info to logger
    logger.info('Destination path: {:s}'.format(options.dest_path))
    logger.info('OSM file: {:s}'.format(options.osm_fn))
    return options, logger, ch


def create_parser():
    usage = "usage: %prog [options]"
    parser = OptionParser(usage=usage)
    parser.add_option('-q', '--quiet',
                      dest='verbose', default=True, action='store_false',
                      help='do not print status messages to stdout')
    parser.add_option('-o', '--osm_download',
                      dest='osm_download', default=False, action='store_true',
                      help='retrieve osm data over bounding box and store in osm_file in .ini file')
    parser.add_option('-i', '--ini', dest='inifile',
                      default='osm2dhydro.ini', nargs=1,
                      help='ini configuration file')
    parser.add_option('-c', '--check', type='choice', action='store',
                      dest='check', choices=['data_model', 'connectivity', 'crossings'],
                      default=None,
                      help='which check to perform, can be: data_model, connectivity, crossings')
    parser.add_option('-d', '--destination',
                      dest='dest_path', default='',
                      help='Destination folder for reporting')
    parser.add_option('-p', '--prefix',
                      dest='prefix', default='',
                      help='Prefix for reporting files')
    return parser


def add_ini(options, logger=logging):
    """
    Read configuration file
    """
    # open config-file
    config = ConfigObj(options.inifile)
    # read settings
    options.osm_fn = configget(config, 'input_data', 'osm_file', None)
    if options.osm_fn is None:
        raise ValueError('OSM file name not found in ini file, check [input_data] -> osm_file')
    options.layer_index = configget(config, 'input_data', 'layer_index', 1, 'int')
    options.layer_type = configget(config, 'input_data', 'layer_type', 'LineString', 'str')
    options.xmin = configget(config, 'input_data', 'xmin', None, 'float')
    options.xmax = configget(config, 'input_data', 'xmax', None, 'float')
    options.ymin = configget(config, 'input_data', 'ymin', None, 'float')
    options.ymax = configget(config, 'input_data', 'ymax', None, 'float')

    if 'bounds' in config:
        options.bounds = options_add_filter(config, 'bounds')
    else:
        options.bounds = None

    if options.check == 'crossings':
        options.filter = options_add_filter(config, 'filter')
        options.filter_highway = options_add_filter(config, 'filter_highway')
        options.filter_bridge = options_add_filter(config, 'filter_bridge')
        options.filter_tunnel = options_add_filter(config, 'filter_tunnel')

    if options.check == 'connectivity':
        options.connectivity = options_add_filter(config, 'connectivity')
        # options.connectivity = {}
        # options.connectivity['idx'] = configget(config, 'connectivity', 'selected_id', 'list')
        options.connectivity['tolerance'] = configget(config, 'connectivity', 'tolerance', '', 'float')

    if (options.check == 'data_model' or options.check == 'connectivity'):
        options.filter = options_add_filter(config, 'filter')
        options.key_types = {}
        options.json_types = {}
        options.key_ranges = {}
        for key in config['key_types']:
            options.key_types[key] = eval(configget(config, 'key_types', key, '', 'str'))
            options.json_types[key] = configget(config, 'key_types', key, '', 'str')

        # now parse the allowed values, check if these need to be converted to a certain data type
        for key in config['key_ranges']:
            # check datatype
            if key in options.key_types:
                dtype_str = options.key_types[key].__name__
            else:
                # assume datatype can be string
                dtype_str = 'str'

            options.key_ranges[key] = configget_list(config, 'key_ranges', key, dtype=dtype_str)
            if (dtype_str == 'float') & (len(options.key_ranges[key]) != 2):
                logger.error('key "{:s}" of type "{:s}" should have 2 range values in key_ranges section (min and max)'.format(key, dtype_str))
                sys.exit(1)
    # make some more option entries based on path and model name
    options.gis_path = os.path.join(options.dest_path, 'gis_files')
    options.report_path = os.path.join(options.dest_path, 'report_files')
    options.report_xlsx = os.path.join(options.report_path, '{:s}_report.xlsx'.format(options.prefix))
    options.report_json = os.path.join(options.gis_path, '{:s}_geo.json'.format(options.prefix))
    options.report_json_water = os.path.join(options.gis_path, '{:s}_geo_water.json'.format(options.prefix))
    options.report_json_roads = os.path.join(options.gis_path, '{:s}_geo_roads.json'.format(options.prefix))
    return options


def configget(config, section, var, default, datatype='str'):
    """
    Gets a string from a config file (.ini) and returns a default value if
    the key is not found. If the key is not found it also sets the value
    with the default in the config-file

    Input:
        - config - python ConfigObj object
        - section - section in the file
        - var - variable (key) to get
        - default - default value
        - datatype='str' - can be set to 'boolean', 'int', 'float' or 'str'

    Returns:
        - value (str, boolean, float or int) - either the value from the config file or the default value
    """

    try:
        if datatype == 'int':
            ret = int(config[section][var])
        elif datatype == 'float':
            ret = float(config[section][var])
        elif datatype == 'boolean':
            ret = bool(config[section][var])
        else:
            ret = config[section][var]
    except:
        ret = default
    return ret


def configget_list(config, section, var, dtype='float'):
    str = configget(config, section, var, '')
    if type(str).__name__ != 'list' and len(str) > 0:
        # make it a list!
        str = [str]
    if len(str) > 0:
        # str = str.split(split_sign)
        if dtype == 'float':
            return [float(str_part) for str_part in str]
        elif dtype == 'int':
            return [int(str_part) for str_part in str]
        elif dtype == 'list':
            return [int(str_part) for str_part in str.split(',')]
        else:
            return [str_part for str_part in str]
    else:
        return []


def options_add_filter(config, section):
    filter = {}
    filter['key'] = configget(config, section, 'key', '', 'str')
    filter['value'] = configget_list(config, section, 'value', dtype='str')
    if 'layer_index' in config[section]:
        filter['layer_index'] = configget(config, 'bounds', 'layer_index', None, 'int')
    return filter
