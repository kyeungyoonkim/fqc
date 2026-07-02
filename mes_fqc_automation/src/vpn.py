"""Optional VPN connect hook for MES systems (DLT / JC) that require it.

This intentionally does NOT hardcode any specific VPN client, because that
depends entirely on what your company issues (Cisco AnyConnect, FortiClient,
OpenConnect, a custom SSL-VPN client, etc). Instead it just runs whatever
command you put in the `VPN_CONNECT_COMMAND` env var, so you can plug in
your client's CLI silent-connect invocation.

If your VPN client has no CLI / silent mode, you have two practical options:
  1. Run this whole automation on a machine that is *already* inside the
     VPN (e.g. a small on-prem/always-on PC, or a persistent site-to-site
     VPN box), so no interactive VPN login is ever needed.
  2. Keep the VPN connected manually and simply schedule this script to run
     while you know the VPN session is alive (least robust option).
"""
from __future__ import annotations

import logging
import os
import shlex
import subprocess

logger = logging.getLogger(__name__)


def connect_vpn_if_configured() -> bool:
    """Run VPN_CONNECT_COMMAND if set. Returns True if a command was run."""
    command = os.environ.get("VPN_CONNECT_COMMAND", "").strip()
    if not command:
        logger.info("VPN_CONNECT_COMMAND not set - assuming VPN is already connected.")
        return False

    logger.info("Connecting to VPN...")
    # Substitute simple %VPN_USER%/%VPN_PASS%-style placeholders if present.
    command = command.replace("%VPN_USER%", os.environ.get("VPN_USERNAME", ""))
    command = command.replace("%VPN_PASS%", os.environ.get("VPN_PASSWORD", ""))

    result = subprocess.run(
        command if os.name == "nt" else shlex.split(command),
        shell=os.name == "nt",
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        logger.error("VPN connect command failed: %s\n%s", result.returncode, result.stderr)
        raise RuntimeError("Failed to connect to VPN, aborting DLT/JC scraping.")

    logger.info("VPN connect command finished successfully.")
    return True
