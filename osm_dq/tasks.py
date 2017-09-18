"""
program specific tasks
These include the runners for tasks (typically require options, bbox, and logger arg): def run_<>
as well as getting the tasks done: def get_<>
"""
import os
import logging
import shapely, shapely.geometry
import io

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

