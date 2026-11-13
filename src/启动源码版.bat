@echo off
rem Launch the .pyw in this folder with a Python that has Tkinter.
rem Prefer the prebuilt EXE from Releases if you just want to use the tool.
chcp 65001 >nul 2>nul
cd /d "%~dp0"

set "TARGET="
for %%F in (*.pyw) do set "TARGET=%%~fF"
if not defined TARGET (
  echo [ERROR] No .pyw file found in this folder.
  pause
  exit /b 1
)

set "PYW="
for %%P in ("%ProgramFiles%\Python313\pythonw.exe" "%ProgramFiles%\Python312\pythonw.exe" "%ProgramFiles%\Python311\pythonw.exe" "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe") do (
  if not defined PYW if exist %%P set "PYW=%%~P"
)
if not defined PYW (
  where pythonw.exe >nul 2>nul && set "PYW=pythonw.exe"
)
if not defined PYW (
  echo [ERROR] Python 3 with Tkinter was not found.
  echo Install Python from https://www.python.org/ or download the EXE from Releases.
  pause
  exit /b 1
)

start "" "%PYW%" "%TARGET%"
