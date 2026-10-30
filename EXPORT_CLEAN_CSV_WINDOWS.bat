@echo off
setlocal
if "%~1"=="" (
  echo Drag a Metrohm NOVA .nox file onto this .bat file to export plot CSVs.
  echo Or run: EXPORT_CLEAN_CSV_WINDOWS.bat "C:\path\measurement.nox"
  pause
  exit /b 1
)
set "INPUT=%~1"
set "PARENT=%~dp1"
py -3 "%~dp0backend\bridge.py" export-package "%INPUT%" --dir "%PARENT%"
if errorlevel 1 (
  echo.
  echo Export failed. Check the error above.
  pause
  exit /b 1
)
echo.
echo Done. Your CSV files are in a new _NOVA_PLOTS folder next to the .nox file.
pause
