#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$Purge
)

$ErrorActionPreference = "Stop"

$serviceName = "MVDInsightsEdgeAgent"
$wrapperFileName = "MVDInsightsEdgeAgent.exe"
$serviceXmlName = "MVDInsightsEdgeAgent.xml"
$programDir = Join-Path $env:ProgramFiles "MVD Insights\Edge Agent"
$programDataDir = Join-Path $env:ProgramData "MVD Insights\Edge Agent"
$configPath = Join-Path $programDataDir "edge.env"
$dataDir = Join-Path $programDataDir "data"
$logDir = Join-Path $programDataDir "logs"
$wrapperExe = Join-Path $programDir $wrapperFileName

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell session."
    }
}

Assert-Administrator

if (Get-Service -Name $serviceName -ErrorAction SilentlyContinue) {
    Stop-Service -Name $serviceName -ErrorAction SilentlyContinue
}

if (Test-Path -LiteralPath $wrapperExe -PathType Leaf) {
    Push-Location $programDir
    try {
        & ".\$serviceName.exe" uninstall
    } finally {
        Pop-Location
    }
}

Remove-Item -LiteralPath (Join-Path $programDir "mvd-edge-agent.exe") -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $programDir $wrapperFileName) -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $programDir $serviceXmlName) -Force -ErrorAction SilentlyContinue

if ($Purge) {
    Remove-Item -LiteralPath $configPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $dataDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $logDir -Recurse -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "Preserved config/data/logs by default:"
    Write-Host "  $configPath"
    Write-Host "  $dataDir"
    Write-Host "  $logDir"
}

Write-Host "MVD Insights Edge Agent Windows service uninstall complete."
