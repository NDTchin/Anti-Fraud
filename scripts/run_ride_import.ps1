param(
    [string]$Source = "data\handoff\ride\cleaned_orders\orders_ride_clean_2026-07-14_to_17.parquet",
    [int]$BatchSize = 2000,
    [int]$WaitSeconds = 180
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ComposeFile = Join-Path $ProjectRoot "infra\docker-compose.full.yml"
$ResolvedSource = Join-Path $ProjectRoot $Source
$env:NEO4J_DOMAIN = "ride"

Set-Location $ProjectRoot

docker compose -f $ComposeFile up -d neo4j
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$importArgs = @(
    "-m", "scripts.import_ride_daily_to_neo4j",
    "--source", $ResolvedSource,
    "--batch-size", $BatchSize,
    "--wait-seconds", $WaitSeconds
)

& $Python @importArgs
exit $LASTEXITCODE
