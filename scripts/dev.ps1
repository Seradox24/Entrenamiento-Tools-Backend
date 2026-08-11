$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot

Push-Location $ProjectRoot
try {
    npm.cmd run css:build
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    docker compose -f compose.prod.yaml up --build
} finally {
    Pop-Location
}
