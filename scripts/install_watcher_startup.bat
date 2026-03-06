@echo off
chcp 65001 >nul
setlocal
REM このバッチがあるフォルダ(scripts)の親 = プロジェクトルート（絶対パス）
set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "BAT=%STARTUP%\win_notify_watcher.bat"

(
  echo @echo off
  echo title Notify Watcher
  echo cd /d "%ROOT%"
  echo py -3 "%ROOT%\scripts\win_notify_watcher.py" notify_data
  echo pause
) > "%BAT%"

echo Registered to Startup: %BAT%
echo Watcher will start automatically on next Windows logon.
echo To run watcher now: double-click the .bat above. A console window will open.
echo If "py" is not found, add Python to PATH or use full path to python.exe.
pause
