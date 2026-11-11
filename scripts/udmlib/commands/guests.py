"""Hotspot vouchers for guest WiFi."""

from __future__ import annotations

import argparse
from typing import Any

from ..client import UDMClient
from ..util import Brief, item_id


def vouchers(client: UDMClient) -> list[dict]:
    return client.get(client.legacy("stat/voucher"))


def voucher_brief(v: dict) -> dict:
    code = str(v.get("code", ""))
    return {
        "id": item_id(v),
        "code": f"{code[:5]}-{code[5:]}" if len(code) == 10 else code,
        "minutes": v.get("duration"),
        "uses": v.get("quota"),
        "used": v.get("used"),
        "note": v.get("note"),
        "status": v.get("status"),
    }


def create(client: UDMClient, count: int, minutes: int, uses: int, note: str | None,
           up_kbps: int | None, down_kbps: int | None, quota_mb: int | None) -> Any:
    body: dict[str, Any] = {"n": count, "expire": minutes, "expire_number": minutes,
                            "expire_unit": 1, "quota": uses}
    if note:
        body["note"] = note
    if up_kbps:
        body["up"] = up_kbps
    if down_kbps:
        body["down"] = down_kbps
    if quota_mb:
        body["bytes"] = quota_mb
    created = client.cmd("hotspot", "create-voucher", **body)
    if client.dry_run:
        return created
    # The command only returns create_time; look the new codes up.
    stamp = created[0].get("create_time") if isinstance(created, list) and created else None
    if stamp is None:
        return created
    return Brief([voucher_brief(v) for v in vouchers(client) if v.get("create_time") == stamp])


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("vouchers", help="Guest hotspot vouchers")
    p.set_defaults(func=lambda c, a: Brief([voucher_brief(v) for v in vouchers(c)]))
    acts = p.add_subparsers(dest="action", metavar="ACTION")

    acts.add_parser("list", help="List vouchers (default)").set_defaults(
        func=lambda c, a: Brief([voucher_brief(v) for v in vouchers(c)]))

    ap = acts.add_parser("create", help="Create vouchers")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--minutes", type=int, default=1440, help="Validity (default 1 day)")
    ap.add_argument("--uses", type=int, default=1, help="0 = unlimited, 1 = single use")
    ap.add_argument("--note")
    ap.add_argument("--up", type=int, help="Upload limit, kbps")
    ap.add_argument("--down", type=int, help="Download limit, kbps")
    ap.add_argument("--quota-mb", type=int, help="Data quota, MB")
    ap.set_defaults(func=lambda c, a: create(c, a.count, a.minutes, a.uses, a.note,
                                             a.up, a.down, a.quota_mb))

    ap = acts.add_parser("delete", help="Revoke a voucher")
    ap.add_argument("id")
    ap.set_defaults(func=lambda c, a: c.cmd("hotspot", "delete-voucher", _id=a.id))
