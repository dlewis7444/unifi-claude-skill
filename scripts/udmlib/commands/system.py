"""Controller-wide commands: status, summary, speedtest, backups, raw API access."""

from __future__ import annotations

import argparse
import time
from typing import Any

from ..client import APIError, UDMClient
from ..util import DEVICE_STATES, duration, load_json_arg
from . import clients as clients_mod
from . import devices as devices_mod
from . import logs


def status(client: UDMClient) -> dict:
    health = client.get(client.legacy("stat/health"))
    sysinfo = client.get(client.legacy("stat/sysinfo"))
    return {"health": health, "sysinfo": sysinfo[0] if sysinfo else sysinfo}


def summary(client: UDMClient) -> dict:
    """One compact snapshot: internet, subsystems, devices, clients, alerts."""
    health = {s.get("subsystem"): s for s in client.get(client.legacy("stat/health"))}
    sysinfo = client.get(client.legacy("stat/sysinfo"))
    sysinfo = sysinfo[0] if isinstance(sysinfo, list) and sysinfo else {}
    devs = devices_mod.list_devices(client)
    stations = clients_mod.active(client)
    wan, www = health.get("wan", {}), health.get("www", {})

    try:
        alert_data = logs.alerts(client)
        alert_count = (len(alert_data) if isinstance(alert_data, list)
                       else alert_data.get("total_element_count") if isinstance(alert_data, dict)
                       else None)
    except APIError:
        alert_count = None

    return {
        "controller": {"version": sysinfo.get("version"), "hostname": sysinfo.get("hostname"),
                       "uptime": duration(sysinfo.get("uptime"))},
        "internet": {
            "status": www.get("status"),
            "wan_ip": wan.get("wan_ip"),
            "isp": wan.get("isp_name"),
            "latency_ms": www.get("latency"),
            "down_mbps": www.get("xput_down"),
            "up_mbps": www.get("xput_up"),
            "speedtest_at": time.strftime(
                "%Y-%m-%d %H:%M", time.localtime(www["speedtest_lastrun"]))
            if www.get("speedtest_lastrun") else None,
        },
        "subsystems": {k: v.get("status") for k, v in health.items()},
        "devices": {
            "total": len(devs),
            "not_online": [f"{d.get('name') or d.get('mac')} "
                           f"({DEVICE_STATES.get(d.get('state'), d.get('state'))})"
                           for d in devs if d.get("state") != 1],
            "upgradable": [f"{d.get('name') or d.get('mac')} → {d.get('upgrade_to_firmware')}"
                           for d in devs if d.get("upgradable")],
        },
        "clients": {
            "online": len(stations),
            "wired": sum(1 for s in stations if s.get("is_wired")),
            "wireless": sum(1 for s in stations if not s.get("is_wired")),
            "blocked": sum(1 for s in stations if s.get("blocked")),
        },
        "unread_alerts": alert_count,
    }


def speedtest_status(client: UDMClient) -> Any:
    res = client.cmd("devmgr", "speedtest-status", mutating=False)
    return res[0] if isinstance(res, list) and res else res


def speedtest(client: UDMClient, wait: bool, timeout: float = 180) -> Any:
    before = speedtest_status(client) if wait else {}
    started = client.cmd("devmgr", "speedtest")
    if not wait or client.dry_run:
        return started
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(5)
        st = speedtest_status(client)
        if isinstance(st, dict) and st.get("rundate") != before.get("rundate") \
                and st.get("status_summary") not in (None, 1):
            return st
    raise APIError(f"Speedtest did not finish within {timeout:.0f}s; "
                   "check later with `speedtest status`")


def register(sub: argparse._SubParsersAction) -> None:
    sub.add_parser("status", help="Health subsystems and controller info").set_defaults(
        func=lambda c, a: status(c))
    sub.add_parser("summary", help="Compact network health snapshot").set_defaults(
        func=lambda c, a: summary(c))

    p = sub.add_parser("speedtest", help="Run or read the gateway speed test")
    p.set_defaults(func=lambda c, a: speedtest_status(c))
    acts = p.add_subparsers(dest="action", metavar="ACTION")
    acts.add_parser("status", help="Last result (default)").set_defaults(
        func=lambda c, a: speedtest_status(c))
    ap = acts.add_parser("run", help="Start a speed test")
    ap.add_argument("--wait", action="store_true", help="Wait for and print the result")
    ap.set_defaults(func=lambda c, a: speedtest(c, a.wait))

    p = sub.add_parser("backup", help="Controller backups (experimental)")
    p.set_defaults(func=lambda c, a: c.cmd("backup", "list-backups", mutating=False))
    acts = p.add_subparsers(dest="action", metavar="ACTION")
    acts.add_parser("list", help="List stored backups (default)").set_defaults(
        func=lambda c, a: c.cmd("backup", "list-backups", mutating=False))
    ap = acts.add_parser("create", help="Create a backup now")
    ap.add_argument("--days", type=int, default=0,
                    help="Statistics history to include (0 = settings only, -1 = all)")
    ap.set_defaults(func=lambda c, a: c.cmd("backup", "backup", days=a.days))

    p = sub.add_parser("raw", help="Raw API call (escape hatch)")
    p.add_argument("method", type=str.upper, choices=["GET", "POST", "PUT", "DELETE", "PATCH"])
    p.add_argument("path", help="Path such as /proxy/network/api/s/default/stat/health, or full URL")
    p.add_argument("--data", help="JSON body (inline, @file or -)")
    p.add_argument("--no-unwrap", action="store_true", help="Keep the {meta, data} envelope")
    p.set_defaults(func=lambda c, a: c.request(
        a.method, c.absolute(a.path),
        load_json_arg(a.data) if a.data is not None else None,
        unwrap=not a.no_unwrap))
