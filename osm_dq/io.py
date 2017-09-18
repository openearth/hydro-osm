"""
I/O functions
"""
import os
import logging
import numpy as np
import fiona
import shapely

from fiona import crs
from urllib2 import urlopen


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
        for o in data:
            p = o.copy()
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
