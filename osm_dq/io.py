"""
I/O functions
"""
import os
import sys
import logging
import numpy as np
import fiona
import shapely

from fiona import crs
from urllib2 import urlopen
from xml.etree import ElementTree as ET


def get_script_path():
    return os.path.dirname(os.path.realpath(sys.argv[0]))

def read_odk_data_model(xml_fn):
    """

    :param xml_fn: ODK configuration file
    :return: list of data model entries in XML format
    """
    xml = ET.parse(xml_fn)
    root = xml.getroot()
    return root[0].getchildren()[1].getchildren()


def write_layer(db, layer_name, data, write_mode='w', format='ESRI Shapefile', schema=None, crs=crs.from_epsg(4326), logger=logging):
    """
    write fiona gis file

    Args:
        db: filename or database
        layer_name: layer name
        data: list of dictionaries with 'geometry' (containing shapely geom) and 'properties' (containing dictionary of attributes)
        write_mode='w': of type 'a' (append) or 'w' (write)
        format='ESRI Shapefile': fiona/gdal driver to use to write
        schema=None: fiona schema for writing, if none, a schema will be attempted to be generated from the first feature in the list
        crs: fiona.crs object (default epsg:4326)

    Returns:
        Nothing, only a written file

    """
    # Define a polygon feature geometry with one attribute
    # prepare properties
    template = data[0]

    # try remove existing file if exists, otherwise fiona dies without warning when writing
    try:
        if write_mode == 'w':
            if os.path.isfile(db):
                os.unlink(db)
                if db.endswith('.shp'):
                    [os.unlink('{}{}'.format(db[:-3], ext)) for ext in ['cpg', 'dbf', 'prj', 'shx']
                     if os.path.isfile('{}{}'.format(db[:-3], ext))]
    except WindowsError, e:
        logger.error(e)
    if schema is None:
        # try to make a schema based upon the first feature in the list of features (should not contain 'None'!)
        props = {}
        for key in template['properties'].keys():
            if isinstance(template['properties'][key], np.generic):
                prop_type = type(np.asscalar(template['properties'][key])).__name__
            else:
                prop_type = type(template['properties'][key]).__name__

            props[key] = prop_type
        schema = {
                  'geometry': type(template['geometry']).__name__,  # ['type']
                  'properties': props,
                  }
    # Write a new Shapefile
    with fiona.open(db, write_mode, format, schema, layer=layer_name, crs=crs) as c:
        for n, o in enumerate(data):
            p = o.copy()
            if p['geometry'] is not None:
                p['geometry'] = shapely.geometry.mapping(p['geometry'])
            c.write(p)
    logger.info('file successfully written to {}'.format(db))
    return

def download_overpass(fn,
                      bbox,
                      url_template='http://overpass.osm.rambler.ru/cgi/xapi_meta?*[bbox={xmin},{ymin},{xmax},{ymax}]'):
    xmin, ymin, xmax, ymax = bbox
    url = url_template.format(xmin=xmin,
                              ymin=ymin,
                              xmax=xmax,
                              ymax=ymax
                              )
    print url
    response = urlopen(url)
    with open(fn, 'w') as f:
        f.write(response.read())
    return

def get_datatypes(xml_data_model, tag_name='nodeset', data_type='type', max_str=None):
    """

    :param xml_data_model: data model list read from ODK config (read_odk_data_model)
    :param tag_name: column name containing the tag names of the data model
    :param data_type: column name containing the data type belonging to tag in data model
    :param max_str: maximum string length used in tags in GIS file to check (can be limited to 10 in case of shapefile)
    :return: check_keys: dictionary of key, value = tag name, datatype
        check_json: same as check_keys but using a string representation of datatype
    """
    check_keys = {}
    check_json = {}
    for data in xml_data_model:  # skip first header line
        if len(data.keys()) > 0:
            try:
                name = data.get(tag_name).split('/')[-1][0:max_str]
                datatype = data.get(data_type)
                if datatype in ['string', 'select1']:  # '', 'date', 'dateTime'
                    dtype = 'str'
                elif datatype in ['int']:
                    dtype = 'int'
                elif datatype in ['float']:
                    dtype = 'float'
                else:
                    dtype = None
                if dtype is not None:
                    check_keys[name] = eval(dtype)
                    check_json[name] = dtype
            except:
                pass
    return check_keys, check_json


def get_conditions(xml_data_model, tag_name='nodeset', conditions='relevant', max_str=10):
    """
    Get the conditional tag values that should be met before the tag under consideration should be checked
    :param xml_data_model: data model list read from ODK config (read_odk_data_model)
    :param tag_name: column name containing the tag names of the data model
    :param conditions: column name containing conditional tag values to be met before tag should be checked
    :param max_str: maximum string length used in tags in GIS file to check (can be limited to 10 in case of shapefile)
    :return:
    """
    def dict_condition(cond_str, max_str=10):
        """
        convert string with conditionals into a list of conditionals and whether 'and' or 'or' check is required
        :param cond_str: string from ODK file, defining conditionals
        :param max_str: maximum string length for tag name (used in shapefiles, maximum 10)
        :return: whether 'and' or 'or' should be applied
            list of dictionaries of conditionals (key/value pairs)
        """
        # first split
        conds = []
        if ' and ' in cond_str:
            cond_list = cond_str.split(' and ')
            logical_and = True
        elif ' or ' in cond_str:
            cond_list = cond_str.split(' or ')
            logical_and = False
        else:
            cond_list = [cond_str]
            logical_and = None
        for cond in cond_list:
            # remove redundant space
            cond = cond.replace(' ', '')
            cond = cond.replace("'", "")
            # split on  '='
            key, value = cond.split('=')
            conds.append((key.split('/')[-1][0:max_str], value))
        return logical_and, conds


    check_conditions = {}
    for data in xml_data_model:  # skip first header line
        if len(data.keys()) > 0:
            try:
                condition = data.get(conditions)
                if condition is not None:
                    name = data.get(tag_name).split('/')[-1][0:max_str]
                    # try to find a 'and' or 'or' string
                    check_conditions[name] = {}
                    logical_and, conds = dict_condition(condition, max_str=max_str)
                    if ' and ' in condition:
                        # multiple conditions, so split on the word 'and'
                        check_conditions[name]['logical_and'] = True
                        condition_list = conditions.split(' and ')
                    elif ' or ' in condition:
                        # multiple conditions, so split on the word 'and'
                        check_conditions[name]['logical_and'] = False
                        condition_list = conditions.split(' or ')
                    else:
                        check_conditions[name]['logical_and'] = None
                        condition_list = [conditions]
                    check_conditions[name]['logical_and'] = logical_and
                    check_conditions[name]['conditions'] = conds
            except:
                pass
    return check_conditions
