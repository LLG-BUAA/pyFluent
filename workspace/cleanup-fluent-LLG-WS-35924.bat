echo off
set LOCALHOST=%COMPUTERNAME%
set KILL_CMD="D:\WORKST~1\Ansys\ANSYSI~1\v252\fluent/ntbin/win64/winkill.exe"

start "tell.exe" /B "D:\WORKST~1\Ansys\ANSYSI~1\v252\fluent\ntbin\win64\tell.exe" LLG-WS 53655 CLEANUP_EXITING
timeout /t 1
"D:\WORKST~1\Ansys\ANSYSI~1\v252\fluent\ntbin\win64\kill.exe" tell.exe
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 60488) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 39340) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 7776) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 43860) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 8568) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 39184) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 21876) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 45940) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 60656) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 9868) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 68604) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 54332) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 54268) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 46032) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 69996) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 74392) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 35924) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 66632)
del "F:\pyFluent\workspace\cleanup-fluent-LLG-WS-35924.bat"
