# Runs the Daily FQC pipeline once: (optional) auto-export from CTV/DLT MES,
# build the Excel + 2 dashboard PNGs, and send them to Telegram.
#
# Register with Windows Task Scheduler to run every morning at 10:00:
#
#   schtasks /Create /SC DAILY /ST 10:00 /TN "MES Daily FQC" `
#     /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\path\to\repo\scripts\run_daily.ps1"
#
# Or via the Task Scheduler GUI:
#   Program/script : powershell.exe
#   Arguments      : -NoProfile -ExecutionPolicy Bypass -File "C:\path\to\repo\scripts\run_daily.ps1"
#   Start in       : C:\path\to\repo
#   Trigger        : Daily, 10:00
#
# Requirements:
#   - This PC must stay connected to the corporate network / VPN (DLT/JC)
#     so the MES URLs in config.yaml are reachable.
#   - config.yaml must exist next to this repo (copy from config.example.yaml).
#   - `pip install -r requirements.txt` and `playwright install` must have
#     been run once in the venv referenced below.

$RepoDir = Split-Path -Parent $PSScriptRoot
Set-Location $RepoDir

$VenvActivate = Join-Path $RepoDir ".venv\Scripts\Activate.ps1"
if (Test-Path $VenvActivate) {
    & $VenvActivate
}

New-Item -ItemType Directory -Force -Path (Join-Path $RepoDir "output\logs") | Out-Null

python mes_automation.py --config config.yaml --auto-export
