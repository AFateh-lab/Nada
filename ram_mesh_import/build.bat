@echo off
rem ===============================================================
rem  BUILD: drag a DXF (or a folder of DXFs) onto this file.
rem  Validates, then creates the RAM Concept model(s) and the mesh.
rem  Needs RAM Concept installed; set CONCEPT_PY below once.
rem ===============================================================
cd /d "%~dp0"
if "%~1"=="" (echo Drag a DXF file or a folder onto this .bat file. & pause & exit /b 1)

rem --- Path to the Python API folder inside your RAM Concept install ---
set "CONCEPT_PY=C:\Program Files\Bentley\Engineering\RAM Concept CONNECT Edition\RAM Concept\python"
if not exist "%CONCEPT_PY%" (echo RAM Concept API folder not found: & echo   %CONCEPT_PY% & echo Edit CONCEPT_PY in build.bat to match your installation. & pause & exit /b 1)
set "PYTHONPATH=%CONCEPT_PY%;%PYTHONPATH%"

set CFG=
if exist config.json set CFG=--config config.json
python -m ram_mesh_import "%~1" %CFG% --open
echo.
if errorlevel 1 (echo *** Build failed - see the dashboard. ***) else (echo Done - open the .cpt in RAM Concept.)
pause
