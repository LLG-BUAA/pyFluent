echo off
set LOCALHOST=%COMPUTERNAME%
set KILL_CMD="D:\WORKST~1\Ansys\ANSYSI~1\v252\fluent/ntbin/win64/winkill.exe"

start "tell.exe" /B "D:\WORKST~1\Ansys\ANSYSI~1\v252\fluent\ntbin\win64\tell.exe" LLG-WS 60093 CLEANUP_EXITING
timeout /t 1
"D:\WORKST~1\Ansys\ANSYSI~1\v252\fluent\ntbin\win64\kill.exe" tell.exe
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 66108) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 51840) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 20532) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 76452) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 56044) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 41884) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 72812) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 71716) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 3936) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 38168) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 21548) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 39528) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 76480) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 7956) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 59080) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 49712) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 74748) 
if /i "%LOCALHOST%"=="LLG-WS" (%KILL_CMD% 71124)
del "F:\pyFluent\workspace\cleanup-fluent-LLG-WS-74748.bat"
