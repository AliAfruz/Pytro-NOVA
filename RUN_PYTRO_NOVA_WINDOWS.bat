@echo off
setlocal
cd /d "%~dp0"
set "PATH=C:\Qt\6.12.0\mingw_64\bin;C:\Qt\Tools\mingw1310_64\bin;%PATH%"
set "QT_QPA_PLATFORM_PLUGIN_PATH=C:\Qt\6.12.0\mingw_64\plugins\platforms"
if not exist "build-mingw\PytroNOVA.exe" (
    echo The program is not built yet.
    echo Please run BUILD_AND_RUN_WINDOWS.ps1 first.
    pause
    exit /b 1
)
"build-mingw\PytroNOVA.exe" %*
