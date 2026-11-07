@echo off
title DS4 to Xbox bridge for FC 27
set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py"
if not defined PY (
    python --version >nul 2>nul
    if not errorlevel 1 set "PY=python"
)
if not defined PY goto nopython

%PY% -c "import pygame, vgamepad" >nul 2>nul
if errorlevel 1 goto install
goto run

:install
echo Installing required Python packages, please wait...
%PY% -m pip install --disable-pip-version-check --upgrade pygame-ce vgamepad
if errorlevel 1 goto pipfail
goto run

:run
%PY% "%~dp0ds4_xbox_bridge.py"
echo.
pause
exit /b 0

:nopython
echo Python is not installed. Install Python 3.12 or 3.13 from python.org
echo and tick "Add python.exe to PATH" during setup, then run this again.
pause
exit /b 1

:pipfail
echo Package install failed. Check your internet connection and try again.
pause
exit /b 1
