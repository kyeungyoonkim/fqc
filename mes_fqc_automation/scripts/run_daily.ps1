# Wrapper for Windows Task Scheduler.
# Create a Basic Task -> Trigger: Daily at e.g. 08:30 -> Action:
#   Program/script: powershell.exe
#   Add arguments:  -NoProfile -ExecutionPolicy Bypass -File "C:\path\to\mes_fqc_automation\scripts\run_daily.ps1"

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoDir = Split-Path -Parent $ScriptDir
Set-Location $RepoDir

if (Test-Path ".venv\Scripts\Activate.ps1") {
    . .venv\Scripts\Activate.ps1
}

python -m src.main --config config.yaml
