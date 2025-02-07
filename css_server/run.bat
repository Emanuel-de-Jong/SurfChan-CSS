@echo off
cd server
start srcds.exe -console -game cstrike -insecure -tickrate 66 +maxplayers 4 +map de_dust
