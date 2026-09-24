@echo off
rem  Self test: checks the sample drawing and opens its dashboard.
cd /d "%~dp0"
"%~dp0ram_mesh_import.exe" "%~dp0examples\sample_level.dxf" --config "%~dp0config.json" --dry-run --open
pause
