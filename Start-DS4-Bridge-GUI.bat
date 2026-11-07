@echo off
title FC 27 DualShock 4 Bridge
set "PYW="
where pyw >nul 2>nul
if not errorlevel 1 set "PYW=pyw"
if not defined PYW (
    where pythonw >nul 2>nul
    if not errorlevel 1 set "PYW=pythonw"
)
if not defined PYW goto nopython

start "" %PYW% "%~dp0ds4_bridge_gui.py"
exit /b 0

:nopython
echo Python is not installed. Install Python 3.12 or 3.13 from python.org
echo and tick "Add python.exe to PATH" during setup, then run this again.
pause
exit /b 1
