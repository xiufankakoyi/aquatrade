@echo off
setlocal

set "SPIDER_DIR=d:\aquatrade\spider"

start "Guba Spider [0/1]" cmd.exe /k cd /d %SPIDER_DIR% ^&^& i:/python/python.exe 1.py --group-index 0 --group-total 1 --throttle-pages 100 --throttle-sleep 300

endlocal
