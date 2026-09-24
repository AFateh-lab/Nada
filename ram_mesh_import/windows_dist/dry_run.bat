@echo off
rem ===============================================================
rem  DRY RUN: drag a DXF (or a folder of DXFs) onto this file.
rem  Checks the drawing, writes the dashboard and opens it.
rem  RAM Concept is NOT started. No Python needed.
rem ===============================================================
cd /d "%~dp0"
if "%~1"=="" (echo Drag a DXF file or a folder onto this .bat file. & pause & exit /b 1)
"%~dp0ram_mesh_import.exe" "%~1" --config "%~dp0config.json" --dry-run --open
echo.
if errorlevel 1 (echo *** Problems found - see the dashboard. ***) else (echo OK - drawing is ready for RAM Concept.)
pause
