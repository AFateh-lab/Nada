@echo off
rem ===============================================================
rem  One-time setup: installs the Python packages and runs the tests.
rem  Run this from the ram_mesh_import folder after installing Python.
rem ===============================================================
cd /d "%~dp0"
python --version >/dev/null 2>&1 || (echo Python not found. Install Python 3.10+ from python.org and tick "Add to PATH". & pause & exit /b 1)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pytest
if not exist config.json copy examples\config.example.json config.json
echo.
echo Running self test ...
python -m pytest tests -q
echo.
echo Setup finished. Edit config.json for your project, then drag a DXF onto dry_run.bat.
pause
