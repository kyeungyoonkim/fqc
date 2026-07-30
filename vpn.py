"""Optional VPN connect hook for MES systems (DLT / JC) that require it.

This intentionally does NOT hardcode any specific VPN client, because that
depends entirely on what your company issues (FortiClient, Cisco AnyConnect,
OpenConnect, a custom SSL-VPN client, etc). Instead it runs whatever command
you put in the `<SITE>_VPN_CONNECT_COMMAND` env var (or a generic
`VPN_CONNECT_COMMAND` fallback), so you can plug in your client's CLI
silent-connect invocation.

If your VPN client has no CLI / silent mode, you have two practical options:
  1. Run this whole automation on a machine that is *already* inside the
     VPN (e.g. a small on-prem/always-on PC, or a persistent site-to-site
     VPN box), so no interactive VPN login is ever needed. This is the
     recommended path for a fully unattended 10:00 schedule.
  2. Keep the VPN connected manually and simply schedule this script to run
     while you know the VPN session is alive (least robust option).
"""
from __future__ import annotations

import logging
import os
import shlex
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def connect_vpn_if_configured(site_name: str, site_cfg: dict[str, Any]) -> bool:
    """Run the VPN connect command for `site_name` if one is configured.

    Looks up, in order:
      - env var f"{site_name.upper()}_VPN_CONNECT_COMMAND"
      - env var "VPN_CONNECT_COMMAND"
      - site_cfg["vpn"]["connect_command"] (from config.yaml)

    Returns True if a command was actually run.
    """
    vpn_cfg = site_cfg.get("vpn", {}) if isinstance(site_cfg.get("vpn"), dict) else {}

    command = (
        os.environ.get(f"{site_name.upper()}_VPN_CONNECT_COMMAND", "").strip()
        or os.environ.get("VPN_CONNECT_COMMAND", "").strip()
        or str(vpn_cfg.get("connect_command", "")).strip()
    )
    if not command:
        logger.info(
            "[%s] No VPN connect command configured - assuming VPN is already connected "
            "(e.g. this machine stays on VPN/intranet).",
            site_name,
        )
        return False

    logger.info("[%s] Connecting to VPN (%s)...", site_name, vpn_cfg.get("type", "unknown client"))
    command = command.replace("%VPN_USER%", os.environ.get(f"{site_name.upper()}_VPN_USERNAME", ""))
    command = command.replace("%VPN_PASS%", os.environ.get(f"{site_name.upper()}_VPN_PASSWORD", ""))

    result = subprocess.run(
        command if os.name == "nt" else shlex.split(command),
        shell=os.name == "nt",
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        logger.error("[%s] VPN connect command failed (%s):\n%s", site_name, result.returncode, result.stderr)
        raise RuntimeError(f"Failed to connect to VPN for {site_name}, aborting.")

    if vpn_cfg.get("duo_required", False):
        print(f"\n[ACTION] {site_name}: approve the DUO push for the VPN connection on your phone.")
        input("         After approval, press Enter to continue...\n")

    logger.info("[%s] VPN connect command finished successfully.", site_name)
    return True
