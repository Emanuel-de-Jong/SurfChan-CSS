@echo off
start css_server/server/cstrike/addons/sourcemod/scripting/spcomp.exe surfchan_plugin.sp
echo Press enter when surfchan_plugin.smx created
pause
move /y surfchan_plugin.smx css_server/server/cstrike/addons/sourcemod/plugins/surfchan_plugin.smx
