@echo off
set PYTHON=%~dp0..\.venv\Scripts\python.exe
if not exist "%PYTHON%" (
  echo Python executable not found: %PYTHON%
  exit /b 1
)
"%PYTHON%" -m mcp_115_server --transport http --host 127.0.0.1 --port 8000 --path /mcp
