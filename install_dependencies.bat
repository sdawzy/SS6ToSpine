@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -m pip install UnityPy pillow numpy opencv-python
) else (
    python -m pip install UnityPy pillow numpy opencv-python
)
pause
