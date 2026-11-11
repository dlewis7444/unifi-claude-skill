"""Events and critical alerts (Network 10.x v2 system-log API)."""

from __future__ import annotations

import argparse
import time
from typing import Any

from ..client import UDMClient


def events(client: UDMClient, hours: int = 24, limit: int | None = None) -> list[dict]:
    cutoff = int(time.time() * 1000) - hours * 3600 * 1000
    results: list[dict] = []
    page = 0
    while True:
        resp = client.post(client.v2("system-log/all"),
                           {"pageNumber": page, "pageSize": 100},
                           unwrap=False, mutating=False)
        batch = resp.get("data", []) if isinstance(resp, dict) else []
        if not batch:
            break
        results.extend(e for e in batch if e.get("timestamp", 0) >= cutoff)
        if limit and len(results) >= limit:
            return results[:limit]
        if (batch[-1].get("timestamp", 0) < cutoff
                or page + 1 >= resp.get("total_page_count", 0)):
            break
        page += 1
    return results


def alerts(client: UDMClient) -> Any:
    """Unread critical alerts — the Network 10.x successor to `stat/alarm`."""
    return client.post(client.v2("system-log/critical"), {}, mutating=False)


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("events", help="System log events")
    p.add_argument("--hours", type=int, default=24, help="Look back N hours (default 24)")
    p.add_argument("--limit", type=int, help="Stop after N events")
    p.set_defaults(func=lambda c, a: events(c, a.hours, a.limit))

    p = sub.add_parser("alarms", help="Unread critical alerts")
    p.set_defaults(func=lambda c, a: alerts(c))
    acts = p.add_subparsers(dest="action", metavar="ACTION")
    acts.add_parser("list", help="List unread alerts (default)").set_defaults(
        func=lambda c, a: alerts(c))
    acts.add_parser("archive-all", help="Mark all alerts as read").set_defaults(
        func=lambda c, a: c.put(c.v2("system-log/critical/mark-all-as-read"), {}))
    ap = acts.add_parser("archive", help="Mark one alert as read")
    ap.add_argument("id")
    ap.set_defaults(func=lambda c, a: c.put(
        c.v2(f"system-log/critical/{a.id}/mark-as-read"), {}))
