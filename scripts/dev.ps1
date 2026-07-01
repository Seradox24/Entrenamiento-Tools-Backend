$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "No existe .venv. Crea el entorno con: python -m venv .venv"
}

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$ProjectRoot'; npm.cmd run css:watch"
& $Python (Join-Path $ProjectRoot "manage.py") runserver
