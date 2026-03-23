echo off
set LOCALHOST=%COMPUTERNAME%
set KILL_CMD="D:\WORKST~1\Ansys\ANSYSI~1\v252\fluent/ntbin/win64/winkill.exe"

start "tell.exe" /B "D:\WORKST~1\Ansys\ANSYSI~1\v252\fluent\ntbin\win64\tell.exe" LLG-WS 59246 CLEANUP_EXITING
timeout /t 1
"D:\WORKST~1\Ansys\ANSYSI~1\v252\fluent\ntbin\win64\kill.exe" tell.exe
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 39560) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 28764) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 32716) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 34832) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 52992) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 39820) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 72652) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 41052) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 75436) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 48604) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 31004) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 65340) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 39104) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 36228) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 65428) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 32472) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 32168) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 21804)
del "F:\pyFluent\workspace\cleanup-fluent-LLG-WS-32168.bat"
