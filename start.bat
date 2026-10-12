@echo off
chcp 65001 >nul
setlocal

rem force Python's stdio to UTF-8 so Chinese text and output markers always encode
set "PYTHONIOENCODING=utf-8"

rem switch to this script's folder so sibling modules can be imported
cd /d "%~dp0"

rem workspace comes from config.WORKSPACE
py main.py

pause
