@echo off
chcp 65001 >nul
setlocal

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "BAT=%STARTUP%\win_notify_watcher.bat"

if exist "%BAT%" (
  del "%BAT%"
  echo Removed from Startup: %BAT%
  echo Watcher will no longer start automatically on logon.
) else (
  echo win_notify_watcher.bat is not in Startup.
)
pause
