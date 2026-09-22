@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -m ss6runtime.gui
) else (
    python -m ss6runtime.gui
)
if errorlevel 1 pause
