"""Managed UniFi devices: gateway, switches, APs."""

from __future__ import annotations

import argparse
from typing import Any

from ..client import UDMClient
from ..util import Brief, device_brief, mac

# action name -> devmgr command
DEVMGR_CMDS = {
    "restart": "restart",
    "upgrade": "upgrade",
    "adopt": "adopt",
    "force-provision": "force-provision",
    "spectrum-scan": "spectrum-scan",
    "locate": "set-locate",
    "unlocate": "unset-locate",
}


def list_devices(client: UDMClient) -> list[dict]:
    return client.get(client.legacy("stat/device"))


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("devices", help="Gateway, switches and access points")
    p.add_argument("--brief", action="store_true", help="Compact table")
    p.set_defaults(func=_list)
    acts = p.add_subparsers(dest="action", metavar="ACTION")

    ap = acts.add_parser("list", help="List devices (default)")
    ap.add_argument("--brief", action="store_true", default=argparse.SUPPRESS)
    ap.set_defaults(func=_list)

    helps = {
        "restart": "Reboot the device", "upgrade": "Upgrade firmware",
        "adopt": "Adopt a pending device", "force-provision": "Re-push configuration",
        "spectrum-scan": "Run an RF spectrum scan (APs)",
        "locate": "Blink the device LED", "unlocate": "Stop blinking the LED",
    }
    for action, cmd in DEVMGR_CMDS.items():
        ap = acts.add_parser(action, help=helps[action])
        ap.add_argument("mac", type=mac)
        ap.set_defaults(func=lambda c, a, cmd=cmd: c.cmd("devmgr", cmd, mac=a.mac))

    ap = acts.add_parser("power-cycle", help="Power-cycle a PoE port on a switch")
    ap.add_argument("mac", type=mac, help="Switch MAC")
    ap.add_argument("port", type=int, help="Port number (port_idx)")
    ap.set_defaults(func=lambda c, a: c.cmd("devmgr", "power-cycle",
                                            mac=a.mac, port_idx=a.port))

    ap = acts.add_parser("ports", help="Port table of a switch/gateway")
    ap.add_argument("mac", type=mac)
    ap.set_defaults(func=_ports)


def _list(client: UDMClient, args: argparse.Namespace) -> Any:
    devs = list_devices(client)
    return Brief([device_brief(d) for d in devs]) if args.brief else devs


def _ports(client: UDMClient, args: argparse.Namespace) -> Any:
    dev = next((d for d in list_devices(client) if d.get("mac") == args.mac), None)
    if dev is None:
        from ..client import APIError
        raise APIError(f"No device with MAC {args.mac}")
    return Brief([{
        "port": p.get("port_idx"),
        "name": p.get("name"),
        "up": p.get("up"),
        "speed": p.get("speed"),
        "poe": p.get("poe_mode") if p.get("port_poe") else None,
        "poe_w": p.get("poe_power"),
        "profile": p.get("portconf_id"),
    } for p in dev.get("port_table", [])])
