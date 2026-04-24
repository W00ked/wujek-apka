# Prepend system Node.js so npx works when Cursor's bundled npm is broken.
# Usage from repo root:
#   .\scripts\hyperframes-run.ps1 --yes hyperframes@0.4.17 lint
#   .\scripts\hyperframes-run.ps1 --yes hyperframes@0.4.17 doctor

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$NpxArgs
)

$ErrorActionPreference = "Stop"
$nodeDir = "${env:ProgramFiles}\nodejs"
if (-not (Test-Path "$nodeDir\node.exe")) {
    Write-Error "Node.js not found at $nodeDir. Install Node 22 LTS or adjust path."
}
$env:PATH = "$nodeDir;" + ($env:PATH -replace '(?i)[^;]*cursor[^;]*helpers;?', '')
$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location "$repoRoot\hyperframes-commercial-app-ad"
& npx @NpxArgs
