#!/usr/bin/env bash
# Wrapper for cron on Linux/macOS. Example crontab entry (runs at 08:30 every
# weekday):
#   30 8 * * 1-5 /path/to/mes_fqc_automation/scripts/run_daily.sh >> /path/to/mes_fqc_automation/output/cron.log 2>&1
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

python -m src.main --config config.yaml
