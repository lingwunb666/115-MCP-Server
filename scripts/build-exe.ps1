param(
    [string]$Python = ".\.venv\Scripts\python.exe"
)

if (-not (Test-Path $Python)) {
    Write-Error "Python executable not found: $Python"
    exit 1
}

& $Python -m PyInstaller --noconfirm --clean "115-MCP-Server.spec"
