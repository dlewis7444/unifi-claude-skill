"""Traffic statistics: WAN/gateway, DPI, time-series reports."""

from __future__ import annotations

import argparse
import time
from typing import Any

from ..client import UDMClient

INTERVAL_SECONDS = {"5minutes": 300, "hourly": 3600, "daily": 86400}
DEFAULT_ATTRS = ["bytes", "wan-tx_bytes", "wan-rx_bytes", "num_sta", "duration"]


def gateway(client: UDMClient) -> dict:
    # Network 10.x removed stat/gateway; the wan/www health subsystems carry the
    # same information (WAN IP, throughput, speedtest, latency, uptime).
    health = client.get(client.legacy("stat/health"))
    return {s["subsystem"]: s for s in health if s.get("subsystem") in ("wan", "www")}


def report(client: UDMClient, interval: str = "hourly", hours: float | None = None,
           attrs: list[str] | None = None, scope: str = "site") -> Any:
    body: dict[str, Any] = {"attrs": attrs or DEFAULT_ATTRS}
    if hours:
        end = int(time.time() * 1000)
        body.update(start=end - int(hours * 3600 * 1000), end=end)
    return client.post(client.legacy(f"stat/report/{interval}.{scope}"), body,
                       mutating=False)


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("stats", help="Traffic statistics")
    p.set_defaults(func=lambda c, a: gateway(c))
    acts = p.add_subparsers(dest="action", metavar="TYPE")

    acts.add_parser("gateway", help="WAN / internet health (default)").set_defaults(
        func=lambda c, a: gateway(c))
    acts.add_parser("dpi", help="Traffic by application category").set_defaults(
        func=lambda c, a: c.get(c.legacy("stat/dpi")))

    ap = acts.add_parser("report", help="Time-series report (stat/report)")
    ap.add_argument("--interval", choices=list(INTERVAL_SECONDS), default="hourly")
    ap.add_argument("--hours", type=float, help="Look back N hours")
    ap.add_argument("--scope", choices=["site", "user", "ap", "gw"], default="site",
                    help="Report scope (default: site)")
    ap.add_argument("--attrs", help="Comma-separated attributes")
    ap.set_defaults(func=lambda c, a: report(
        c, a.interval, a.hours, a.attrs.split(",") if a.attrs else None, a.scope))
