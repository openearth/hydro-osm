# hydro-osm
Hydrological tools for OpenStreetMap data

Hydro-osm is intended to become a toolbox to convert OpenStreetMap data into data layers that can be readily used
for hydrological and hydraulic modelling. At the moment, the tools provide step number 1: data quality checking in
particular for hydraulic modelling and the generation of a topologically correct 1D network.

It provides three quality checks
- checking of the tagging data model
- checking of the connectivity of the network, identifying disconnected parts in the network
- checking crossings of waterways and roads

## General run time information
the data quality routines are run through the python code run_osm_dq.py. The following code brings up a help screen

python ron_osm_dq.py -h

Usage: run_osm_dq.py [options]

Options:
  -h, --help            show this help message and exit
  -q, --quiet           do not print status messages to stdout
  -o, --osm_download    retrieve osm data over bounding box and store in
                        osm_file in .ini file
  -i INIFILE, --ini=INIFILE
                        ini configuration file
  -g, --graph           make graphs of validation flags (default False)
  -P, --popup           add popups to the map (default False)
  -c CHECK, --check=CHECK
                        which check to perform, can be: data_model,
                        connectivity, crossings
  -d DEST_PATH, --destination=DEST_PATH
                        Destination folder for reporting
  -p PREFIX, --prefix=PREFIX
                        Prefix for reporting files

A typical short written usage of the quality checks is as follows:

python run_osm_dq.py -i <INIFILE> -c <CHECK> -d <DEST_PATH> -p <PREFIX>

Graphs (-g) and popups (-P) are at the moment still placeholders for possible future functionality.

## Structure of .ini file
The ini file contains all settings needed to perform the quality checks. For the different quality checks, different
ini files may be required. The typical sections found are:

[input_data]: here the user can insert the osm file that needs be checked (osm_file),
the extent (xmin, xmax, ymin, ymax) of the target area, the layer index (int) that should be used (layer_index) and the
layer type that we'd be looking at (layer_type).
[filter]: here it is defined which key/value pairs should be considered to filter out data that should be checked for
quality. The user provides one key (in field key) and a comma-separated list of values (in field value).
[key_types]: this section provides a set of keys for which the filtered elements should be checked for, along with the
expected data type for this key. The entries are typically such>
key1 = datatype1
key2 = datatype2
etc...

where key is the name of the tag, and datatype the type of data, which can be str, int or float.

[key_ranges]: the range of values for each key that is allowed. For floats this should be a comma-separated
list of 2 values (minimum and maximum) while for integers and strings, this can be a comma-separated list of any number
of allowed entries.

[connectivity_options]: only used when checking for connectivity. Here the osm_id values of the selected valid outflow
points is provided as comma-separated list of integers, and a tolerance, which is a float, identifying any allowed
snapping distance for non-connected elements. In case the user expects that all line segments filtered should be
completely connected, this value should be set to zero.

[filter_highway]: only used with crossings check. Similar to [filter], but used to filter out roads (where
[filter] is assumed to filter out waterways).

[filter_bridge]: only used with crossings check. Similar to [filter], but used to filter out bridges.

[filter_tunnel]: only used with crossings check. Similar to [filter], but used to filter out tunnels (or culverts).

## Running data quality