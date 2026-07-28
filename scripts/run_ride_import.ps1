param(
    [string]$Source = "data\handoff\ride\cleaned_orders\orders_ride_clean_2026-07-14_to_17.parquet",
    [string]$ImportDir = "data\neo4j-import\neo4j-import-ride",
    [double]$MinimumFreeGB = 2,
    [switch]$OverwriteStaging
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ComposeFile = Join-Path $ProjectRoot "infra\docker-compose.full.yml"
$RideImportOverride = Join-Path $ProjectRoot "infra\docker-compose.ride-import.yml"
$ResolvedSource = Join-Path $ProjectRoot $Source
$ResolvedImportDir = Join-Path $ProjectRoot $ImportDir
$env:NEO4J_STORE_DIR = (Join-Path $ProjectRoot "data\neo4j-store\neo4j-store-ride")

Set-Location $ProjectRoot

$prepareArgs = @(
    "-m", "scripts.prepare_clean_orders_neo4j_import",
    "--source", $ResolvedSource,
    "--domain", "ride",
    "--output", $ResolvedImportDir,
    "--minimum-free-gb", $MinimumFreeGB
)
if ($OverwriteStaging) {
    $prepareArgs += "--overwrite"
}

& $Python @prepareArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose -f $ComposeFile -f $RideImportOverride stop neo4j
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose -f $ComposeFile -f $RideImportOverride --profile tools run --rm neo4j-import
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose -f $ComposeFile -f $RideImportOverride up -d neo4j
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python scripts/initialize_neo4j.py --import-dir $ResolvedImportDir
exit $LASTEXITCODE
