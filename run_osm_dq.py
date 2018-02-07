#!/usr/bin/python
"""
Runner for OSM data quality assessment procedures

MIT License

Copyright (c) 2017 OpenEarth

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""
import sys

# package components
from osm_dq import config
from osm_dq import log
from osm_dq import tasks


def main():
    options, logger, ch = config.create_options()
    # download openstreetmap data
    if options.osm_download:
        tasks.get_osm_data(options, logger=logger)

    # filter geographical bounds (if provided)
    if options.bounds:
        bbox = tasks.get_bounds(options, logger=logger)
    else:
        bbox = {'full_area': None}

    # checking data model
    if options.check == 'data_model':
        tasks.run_data_model_check(options, bbox, logger)

    # # check connectivity
    # if options.check == 'connectivity':
    #     tasks.run_connectivity_check(options, bbox, logger)

    # check crossings of waterways and roads
    if options.check == 'crossings':
        tasks.run_crossings_check(options, bbox, logger)

    # close logger object
    logger, ch = log.close_logger(logger, ch)
    del logger, ch
    sys.exit(0)


if __name__ == "__main__":
    main()
