set INIFILE=check_connectivity.ini
python ..\run_osm_dq.py -i %INIFILE% -c data_model -d .\connectivity -p connectivity -o
pause
