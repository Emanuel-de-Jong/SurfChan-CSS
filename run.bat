@echo off

:: Compile the SourceMod plugin
start /wait css_server/server/cstrike/addons/sourcemod/scripting/spcomp.exe src/sourcemod_plugin.sp
move /y sourcemod_plugin.smx css_server/server/cstrike/addons/sourcemod/plugins/surfchan.smx

:: Start
start python src/SurfChan.py
