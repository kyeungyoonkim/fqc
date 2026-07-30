#!/usr/bin/env bash
# Runs the Daily FQC pipeline once: (optional) auto-export from CTV/DLT MES,
# build the Excel + 2 dashboard PNGs, and send them to Telegram.
#
# Intended to be triggered by cron every morning, e.g. at 10:00 Asia/Seoul:
#
#   crontab -e
#   0 10 * * * /path/to/repo/scripts/run_daily.sh >> /path/to/repo/output/logs/cron.log 2>&1
#
# Requirements:
#   - This machine must already be on the corporate network / VPN so the
#     MES URLs in config.yaml are reachable (see README "실환경 적용시 체크포인트").
#   - config.yaml must exist next to this repo (copy from config.example.yaml).
#   - The venv below must have `pip install -r requirements.txt` +
#     `playwright install` already run once.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

mkdir -p output/logs

python mes_automation.py --config config.yaml --auto-export
