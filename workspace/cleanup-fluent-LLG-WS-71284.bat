echo off
set LOCALHOST=%COMPUTERNAME%
set KILL_CMD="D:\WORKST~1\Ansys\ANSYSI~1\v252\fluent/ntbin/win64/winkill.exe"

start "tell.exe" /B "D:\WORKST~1\Ansys\ANSYSI~1\v252\fluent\ntbin\win64\tell.exe" LLG-WS 61578 CLEANUP_EXITING
timeout /t 1
"D:\WORKST~1\Ansys\ANSYSI~1\v252\fluent\ntbin\win64\kill.exe" tell.exe
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 50784) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 40160) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 63128) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 40496) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 73960) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 73504) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 69412) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 69356) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 51080) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 35872) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 37528) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 47256) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 66528) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 40440) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 57720) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 32584) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 71284) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 75868)
del "F:\pyFluent\workspace\cleanup-fluent-LLG-WS-71284.bat"
