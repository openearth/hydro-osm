set INIFILE=c:\test\check_connectivity.ini
cd d:\git\hydro-osm
d:
python run_osm_dq.py -i %INIFILE% -c connectivity -d c:\test -p connectivity -o
pause
