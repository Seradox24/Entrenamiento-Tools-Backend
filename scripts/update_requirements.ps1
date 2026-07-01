$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Requirements = Join-Path $ProjectRoot "requirements.txt"

if (-not (Test-Path $Python)) {
    throw "No existe .venv. Crea el entorno con: python -m venv .venv"
}

& $Python -m pip freeze | Set-Content -Path $Requirements -Encoding ascii
Write-Host "requirements.txt actualizado desde .venv"
