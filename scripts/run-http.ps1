param(
    [string]$Python = ".\.venv\Scripts\python.exe",
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8000,
    [string]$Path = "/mcp"
)

if (-not (Test-Path $Python)) {
    Write-Error "Python executable not found: $Python"
    exit 1
}

& $Python -m mcp_115_server --transport http --host $BindHost --port $Port --path $Path
