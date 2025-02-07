@echo off
start python surfchan.py
start css_server/server/srcds.exe -console -game cstrike -insecure -tickrate 66 +maxplayers 4 +map de_dust
