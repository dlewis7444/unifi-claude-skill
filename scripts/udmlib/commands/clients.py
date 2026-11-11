"""Clients (stations): list, search, block/kick/forget, alias/note/fixed IP."""

from __future__ import annotations

import argparse
from typing import Any

from ..client import APIError, UDMClient
from ..util import Brief, UsageError, client_brief, mac

STAMGR_CMDS = {"block": "block-sta", "unblock": "unblock-sta", "kick": "kick-sta"}


def active(client: UDMClient) -> list[dict]:
    return client.get(client.legacy("stat/sta"))


def known(client: UDMClient) -> list[dict]:
    return client.get(client.legacy("stat/alluser"))


def merged(client: UDMClient) -> list[dict]:
    """All known clients, with live data overlaid for the ones online right now."""
    live = {c.get("mac"): c for c in active(client)}
    out = []
    for c in known(client):
        online = c.get("mac") in live
        row = {**c, **live.pop(c.get("mac"), {})}
        row["_online"] = online
        out.append(row)
    for c in live.values():  # online but not (yet) in alluser
        out.append({**c, "_online": True})
    return out


def find(client: UDMClient, query: str) -> list[dict]:
    q = query.lower().replace("-", ":")
    fields = ("name", "hostname", "ip", "last_ip", "fixed_ip", "mac", "oui", "note")
    return [c for c in merged(client)
            if any(q in str(c.get(f, "")).lower() for f in fields)]


def user_record(client: UDMClient, mac_addr: str) -> dict:
    for c in known(client):
        if c.get("mac") == mac_addr:
            return c
    raise APIError(f"No known client with MAC {mac_addr}")


def configure(client: UDMClient, mac_addr: str, *, name: str | None = None,
              note: str | None = None, fixed_ip: str | None = None,
              network_id: str | None = None, clear_fixed_ip: bool = False) -> Any:
    user = user_record(client, mac_addr)
    body: dict[str, Any] = {}
    if name is not None:
        body["name"] = name
    if note is not None:
        body["note"] = note
        body["noted"] = bool(note)
    if fixed_ip:
        nid = network_id or user.get("network_id") or user.get("last_connection_network_id")
        if not nid:
            raise UsageError("Cannot infer network for fixed IP; pass --network-id "
                             "(see `udm.py networks list --brief`)")
        body.update(use_fixedip=True, fixed_ip=fixed_ip, network_id=nid)
    if clear_fixed_ip:
        body["use_fixedip"] = False
    if not body:
        raise UsageError("Nothing to change: pass --name, --note, --fixed-ip or --clear-fixed-ip")
    return client.put(client.legacy(f"rest/user/{user['_id']}"), body)


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("clients", help="Connected and known clients")
    p.add_argument("--all", action="store_true", help="Include offline (known) clients")
    p.add_argument("--brief", action="store_true", help="Compact table")
    p.set_defaults(func=_list)
    acts = p.add_subparsers(dest="action", metavar="ACTION")

    ap = acts.add_parser("list", help="List clients (default)")
    ap.add_argument("--all", action="store_true", default=argparse.SUPPRESS)
    ap.add_argument("--brief", action="store_true", default=argparse.SUPPRESS)
    ap.set_defaults(func=_list)

    ap = acts.add_parser("find", help="Search by name, hostname, IP, MAC, vendor or note")
    ap.add_argument("query")
    ap.add_argument("--full", action="store_true", help="Full objects instead of a table")
    ap.set_defaults(func=lambda c, a: find(c, a.query) if a.full
                    else Brief([client_brief(x) for x in find(c, a.query)]))

    for action, help_ in (("block", "Block network access"), ("unblock", "Unblock"),
                          ("kick", "Force reconnect")):
        ap = acts.add_parser(action, help=help_)
        ap.add_argument("mac", type=mac)
        ap.set_defaults(func=lambda c, a, cmd=STAMGR_CMDS[action]:
                        c.cmd("stamgr", cmd, mac=a.mac))

    ap = acts.add_parser("forget", help="Remove a client from the known-clients list")
    ap.add_argument("mac", type=mac)
    ap.set_defaults(func=lambda c, a: c.cmd("stamgr", "forget-sta", macs=[a.mac]))

    ap = acts.add_parser("set", help="Set alias, note or fixed IP (DHCP reservation)")
    ap.add_argument("mac", type=mac)
    ap.add_argument("--name", help="Alias shown in the UI ('' clears)")
    ap.add_argument("--note", help="Free-text note ('' clears)")
    ap.add_argument("--fixed-ip", help="Reserve this IP for the client")
    ap.add_argument("--network-id", help="Network for the reservation (default: current)")
    ap.add_argument("--clear-fixed-ip", action="store_true", help="Remove the reservation")
    ap.set_defaults(func=lambda c, a: configure(
        c, a.mac, name=a.name, note=a.note, fixed_ip=a.fixed_ip,
        network_id=a.network_id, clear_fixed_ip=a.clear_fixed_ip))


def _list(client: UDMClient, args: argparse.Namespace) -> Any:
    rows = merged(client) if args.all else active(client)
    return Brief([client_brief(c) for c in rows]) if args.brief else rows
