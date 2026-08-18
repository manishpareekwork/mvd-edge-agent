#Requires -Version 5.1
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$serviceName = "MVDInsightsEdgeAgent"
$programDir = Join-Path $env:ProgramFiles "MVD Insights\Edge Agent"
$programDataDir = Join-Path $env:ProgramData "MVD Insights\Edge Agent"
$agentExe = Join-Path $programDir "mvd-edge-agent.exe"
$configPath = Join-Path $programDataDir "edge.env"
$dataDir = Join-Path $programDataDir "data"
$logDir = Join-Path $programDataDir "logs"

foreach ($path in @($agentExe, $configPath, $dataDir, $logDir)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing expected install path: $path"
    }
}

$env:MVD_EDGE_CONFIG = $configPath
$env:EDGE_DATA_DIR = $dataDir
$env:EDGE_LOG_DIR = $logDir
& $agentExe --check-config
if ($LASTEXITCODE -ne 0) {
    throw "Configuration validation failed."
}

$service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if (-not $service) {
    throw "Service is not installed: $serviceName"
}

Write-Host "Install check passed for $serviceName."
