@echo off
setlocal
REM Run the converter with the isolated Python distributed with Pytro-NOVA.
set "NOVA_ROOT=%~dp0"
"%NOVA_ROOT%python\python.exe" "%NOVA_ROOT%tools\nova_to_txt.py" %*
exit /b %ERRORLEVEL%
