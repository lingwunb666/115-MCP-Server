@echo off
set PYTHON=%~dp0..\.venv\Scripts\python.exe
if not exist "%PYTHON%" (
  echo Python executable not found: %PYTHON%
  exit /b 1
)
"%PYTHON%" -m mcp_115_server
