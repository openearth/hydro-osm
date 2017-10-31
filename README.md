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
  -c CHECK, --check=CHECK
                        which check to perform, can be: data_model,
                        connectivity, crossings
  -d DEST_PATH, --destination=DEST_PATH
                        Destination folder for reporting
  -p PREFIX, --prefix=PREFIX
                        Prefix for reporting files

A typical short written usage of the quality checks is as follows:

python run_osm_dq.py -i <INIFILE> -c <CHECK> -d <DEST_PATH> -p <PREFIX>

## Structure of .ini file
The ini file contains all settings needed to perform the quality checks. For the different quality checks, different
ini files may be required. The typical sections found are:

[input_data]: here the user can insert the osm file that needs be checked (osm_file),
the extent (xmin, xmax, ymin, ymax) of the target area, the layer index (int) that should be used (layer_index) and the
layer type that we'd be looking at (layer_type).

[bounds]: if provided, it defines a filter for polygons, that define user-specified geographical regions for which the
check should be performed. A layer_index should be selected (when the file contains multiple layers). Care should be
taken that a Polygon layer is selected. For .osm files, the Polygon layer typically is layer number 3. Furthermore a key
and a comma-separated list of values, or single value should be provided that filter out specific Polygons.
In the examples, we use the key "name" and as value a list of neighbourhood names, stored under the osm tag "name".

[filter]: here it is defined which key/value pairs should be considered to filter out data that should be checked for
quality. The user provides one key (in field key) and a comma-separated list of values (in field value).

[key_types]: this section provides a set of keys for which the filtered elements should be checked for, along with the
expected data type for this key. The entries are typically as follows:

key1 = datatype1
key2 = datatype2
etc...

where key1, key2 should be replaced by the actual name of the tag, and datatype1 and datatype2 should be replaced by
the type of data, which can be str, int or float.

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

[connectivity_options]: filter out end segments of a connected network. The user selects these segments by using
comma-separated osm_id values of the OpenStreetMap data set in the field 'selected_id'. The field 'tolerance' can be
used to select a spatial tolerance to snap lines. In case you wish to make sure that all lines are properly connected,
you should always set this to zero. The unit of this option is the spatial unit belonging to the projection of the
used input file. In most cases this will be WGS84 lat-lon.


## Running data quality routines
Running the data quality routines should be done with the following command:

python run_osm_dq.py -i <INIFILE> -c <CHECK> -d <DEST_PATH> -p <PREFIX>
where an .ini file is selected with -i, a check is selected with -c, the destination path, where outputs are written is
provided with -d, and a prefix to output file names (for later reference and easy recognition of files) can be
provided with -p. The choices for data quality assurance checks are:

### Data model (data_model)
Checks the completeness of the data_model for given filtered features. Features are selected geographically,
using a user-specified set of polygons (geographically), as well as tag-specific, using a user-specified tag filter.
For instance, in our examples, we use the section [bounds] to provide a set of geographical areas on which to perform
the check, and we use the [filter] section to filter out features using tags. The check then uses the [key_types] and
[key_values] to understand the data model and to check if the filtered features follow the data model.

### Connectivity (connectivity)
Checks topological connectivity of a line network with respect to a (set of) user-selected end segments representing.
stream network outlets. The end segments are filtered by the user in the section [connectivity] by using a key and
value set. key represents the property name and value a comma separated list of values to identify unique features
that represent outlets. The check filters out line elements that should belong to a network, and checks to which end
segment the line is connected.

### Crossings (crossings)
Three additional tag filters need to be provided for this, [filter_highway] and [filter_bridge] and [filter_tunnel].
The check will use the filter [filter] to filter out water ways, [filter_highway] to filter out roads, [filter_bridge]
to filter out bridges and [filter_tunnel] to filter out tunnels such as culverts. The check then searches for crossing
water way and road elements and will check if these crossing are either a bridge or a tunnel using the [filter_bridge]
and [filter_tunnel] tags. It will then report the found crossings and what the type of crossing is (bridge, tunnel
or undefined). The check uses the [bounds] filter to perform the check per Polygon. If this is not provided, the
complete dataset will be checked and reported as one region.

## output of data quality routines
### Data model
The data model check provides 2 outputs:
- Excel file: it has different tabs for each region selected in the [bounds] section. Within each tab, per tag,
a summary is provided of the amount of features that has an appropriate value for the tag (0), the amount that has an
invalid value (1), the amount that has a value but of the wrong datatype (2) and the amount, not having a value at all.

-GeoJSON file: this file can be loaded in GIS software such as QGIS and shows all filtered features. Each feature
contains the tags that were relevant in the selected data model, as well as new tags, similarly names, but with a
suffix '_flag' that show the result of the check on that feature and tag. For instance if a check is performed on the
tag 'width', the check will return the original value of the tag 'width' for each feature, but also a tag 'width_flag'.
This tag can have the value 0 (valid value), 1 (invalid value), 2 (incorrect data type) or 3 (no value). It is then
straightforward to use these flag values to color code the GIS layout.

### Connectivity
This check only provides one output. A GeoJSON file with the filtered line elements. A tag 'connected' is added. This
tag gives the osm_id to which the line elements is topologically connected, or a zero when there is no connection to
any selected end segment.

### Crossings
The check gives two outputs:
- Excel file: the excel shows (per selected region, using the [bounds] section) the amount of crossings with a bridge,
tunnel or undefined crossing.
- GeoJSON files. 3 files are provided. 2 files contain the filtered waterways and roads respectively. The last file
is a Point file containing the crossings found. Each crossing has a set of tags, being the name of the filtered region
in which the crossing is located, the osm_id of the crossing waterway, the osm_id of the crossing highway, a flag value
(0 when a known crossing is found, 1 when no crossing structure is found).

## Examples
The 'examples' folder contains a set of .ini files as well as .bat files. The .bat files can be used to run the examples.
Sample data to run the examples with, is provided in the folder 'sample_data'. Please unzip the file
'sample_data\kigogo.zip' to the folder 'examples' before running the examples.
