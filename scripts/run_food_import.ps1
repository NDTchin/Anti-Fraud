param(
    [string]$Source = "data\handoff\food\cleaned_orders\orders_food_clean_dashboard.parquet",
    [string]$ImportDir = "data\neo4j-import\neo4j-import-food",
    [double]$MinimumFreeGB = 2,
    [switch]$OverwriteStaging
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ComposeFile = Join-Path $ProjectRoot "infra\docker-compose.full.yml"
$FoodImportOverride = Join-Path $ProjectRoot "infra\docker-compose.food-import.yml"
$ResolvedSource = Join-Path $ProjectRoot $Source
$ResolvedImportDir = Join-Path $ProjectRoot $ImportDir
$env:NEO4J_STORE_DIR = (Join-Path $ProjectRoot "data\neo4j-store\neo4j-store-food")

Set-Location $ProjectRoot

$prepareArgs = @(
    "-m", "scripts.prepare_clean_orders_neo4j_import",
    "--source", $ResolvedSource,
    "--domain", "food",
    "--output", $ResolvedImportDir,
    "--minimum-free-gb", $MinimumFreeGB
)
if ($OverwriteStaging) {
    $prepareArgs += "--overwrite"
}

& $Python @prepareArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose -f $ComposeFile -f $FoodImportOverride stop neo4j
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose -f $ComposeFile -f $FoodImportOverride --profile tools run --rm neo4j-import
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose -f $ComposeFile -f $FoodImportOverride up -d neo4j
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python scripts/initialize_neo4j.py --import-dir $ResolvedImportDir
exit $LASTEXITCODE
