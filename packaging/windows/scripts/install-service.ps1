#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$SourceDir = (Split-Path -Parent $PSScriptRoot),
    [switch]$StartService,
    [switch]$SkipConfigCheck
)

$ErrorActionPreference = "Stop"

$serviceName = "MVDInsightsEdgeAgent"
$wrapperFileName = "MVDInsightsEdgeAgent.exe"
$serviceXmlName = "MVDInsightsEdgeAgent.xml"
$programDir = Join-Path $env:ProgramFiles "MVD Insights\Edge Agent"
$programDataDir = Join-Path $env:ProgramData "MVD Insights\Edge Agent"
$dataDir = Join-Path $programDataDir "data"
$logDir = Join-Path $programDataDir "logs"
$configPath = Join-Path $programDataDir "edge.env"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell session."
    }
}

function Copy-RequiredFile {
    param(
        [string]$Source,
        [string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        throw "Required file not found: $Source"
    }

    Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

Assert-Administrator

$agentExe = Join-Path $SourceDir "mvd-edge-agent.exe"
$wrapperExe = Join-Path $SourceDir $wrapperFileName
$serviceXml = Join-Path $SourceDir $serviceXmlName
$configTemplate = Join-Path (Split-Path -Parent $PSScriptRoot) "config\edge.env.example"

New-Item -ItemType Directory -Force -Path $programDir, $programDataDir, $dataDir, $logDir | Out-Null

Copy-RequiredFile -Source $agentExe -Destination (Join-Path $programDir "mvd-edge-agent.exe")
Copy-RequiredFile -Source $wrapperExe -Destination (Join-Path $programDir $wrapperFileName)
Copy-RequiredFile -Source $serviceXml -Destination (Join-Path $programDir $serviceXmlName)

if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    Copy-RequiredFile -Source $configTemplate -Destination $configPath
    Write-Host "Created config template: $configPath"
} else {
    Write-Host "Preserved existing config: $configPath"
}

if (-not $SkipConfigCheck) {
    $env:MVD_EDGE_CONFIG = $configPath
    $env:EDGE_DATA_DIR = $dataDir
    $env:EDGE_LOG_DIR = $logDir
    & (Join-Path $programDir "mvd-edge-agent.exe") --check-config
    if ($LASTEXITCODE -ne 0) {
        throw "Configuration validation failed. Service was not installed."
    }
}

Push-Location $programDir
try {
    & ".\$serviceName.exe" install
    if ($LASTEXITCODE -ne 0) {
        throw "Service installation failed."
    }

    Set-Service -Name $serviceName -StartupType Automatic

    if ($StartService) {
        Start-Service -Name $serviceName
    } else {
        Write-Host "Service installed. Start with: Start-Service -Name $serviceName"
    }
} finally {
    Pop-Location
}

Write-Host "MVD Insights Edge Agent Windows service installation complete."
