@echo off

:: Compile the SourceMod plugin
start /wait css_server/server/cstrike/addons/sourcemod/scripting/spcomp.exe src/surfchan_plugin.sp
move /y surfchan_plugin.smx css_server/server/cstrike/addons/sourcemod/plugins/surfchan_plugin.smx

:: Start
start python src/surfchan.py
