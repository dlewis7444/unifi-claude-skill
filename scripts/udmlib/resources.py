"""Generic CRUD commands for UniFi config collections.

Every collection (firewall rules, port forwards, traffic rules, zone policies...)
gets the same verbs:

    list [--brief]      get <id>
    create --data JSON  update <id> --data JSON | --patch JSON
    delete <id>         enable <id> / disable <id>

`--patch` fetches the current object, deep-merges the patch into it and PUTs the
full object back — the controller rejects or corrupts partial updates on most
endpoints, so this is the safe way to change a few fields.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Any, Callable

from .client import APIError, UDMClient
from .util import Brief, UsageError, find_item, load_json_arg, rule_brief

ALL_ACTIONS = ("list", "get", "create", "update", "delete", "enable", "disable")


@dataclass(frozen=True)
class Resource:
    command: str
    help: str
    layer: str                      # "legacy" | "v2"
    path: str
    actions: tuple[str, ...] = ALL_ACTIONS
    batch_delete: str | None = None  # v2 collections that delete via POST <path>/<batch_delete>
    brief: Callable[[dict], dict] = rule_brief
    notes: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)

    def url(self, client: UDMClient, item: str | None = None) -> str:
        path = f"{self.path}/{item}" if item else self.path
        return client.legacy(path) if self.layer == "legacy" else client.v2(path)

    # ── operations ──────────────────────────────────────────────────────────

    def list(self, client: UDMClient) -> list[dict]:
        data = client.get(self.url(client))
        if isinstance(data, dict):  # some v2 endpoints wrap lists
            for key in ("data", "items", self.path.split("/")[-1]):
                if isinstance(data.get(key), list):
                    return data[key]
        return data if isinstance(data, list) else [data]

    def fetch(self, client: UDMClient, item: str) -> dict:
        found = find_item(self.list(client), item)
        if found is None:
            raise APIError(f"{self.command}: no object with id {item}")
        return found

    def create(self, client: UDMClient, body: dict) -> Any:
        body = {k: v for k, v in body.items() if k not in ("_id", "id")}
        return client.post(self.url(client), body)

    def update(self, client: UDMClient, item: str, body: dict) -> Any:
        return client.put(self.url(client, item), body)

    def patch(self, client: UDMClient, item: str, changes: dict) -> Any:
        current = self.fetch(client, item)
        return self.update(client, item, deep_merge(current, changes))

    def delete(self, client: UDMClient, item: str) -> Any:
        if self.batch_delete:
            return client.post(self.url(client, self.batch_delete), [item])
        return client.delete(self.url(client, item))


def deep_merge(base: dict, changes: dict) -> dict:
    out = dict(base)
    for key, val in changes.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def register(sub: argparse._SubParsersAction, res: Resource) -> argparse._SubParsersAction:
    """Add the resource command; returns its action subparsers for extra verbs."""
    p = sub.add_parser(res.command, aliases=list(res.aliases), help=res.help,
                       description=f"{res.help}. {res.notes}".strip())
    p.add_argument("--brief", action="store_true", help="Compact table (list only)")
    p.set_defaults(func=lambda c, a: _list(c, a, res))
    actions = p.add_subparsers(dest="action", metavar="ACTION")

    def add(name: str, help_: str, needs_id: bool = False) -> argparse.ArgumentParser:
        ap = actions.add_parser(name, help=help_)
        if needs_id:
            ap.add_argument("id", help="Object id (_id / id from `list`)")
        return ap

    if "list" in res.actions:
        ap = add("list", "List all objects")
        ap.add_argument("--brief", action="store_true", default=argparse.SUPPRESS,
                        help="Compact table")
        ap.set_defaults(func=lambda c, a: _list(c, a, res))
    if "get" in res.actions:
        add("get", "Show one object", True).set_defaults(
            func=lambda c, a: res.fetch(c, a.id))
    if "create" in res.actions:
        ap = add("create", "Create from JSON (--data '{...}' | @file | -)")
        ap.add_argument("--data", required=True)
        ap.set_defaults(func=lambda c, a: res.create(c, load_json_arg(a.data)))
    if "update" in res.actions:
        ap = add("update", "Replace (--data, full object) or merge (--patch)", True)
        g = ap.add_mutually_exclusive_group(required=True)
        g.add_argument("--data", help="Full object JSON")
        g.add_argument("--patch", help="Partial JSON merged into the current object")
        ap.set_defaults(func=lambda c, a: _update(c, a, res))
    if "delete" in res.actions:
        add("delete", "Delete an object", True).set_defaults(
            func=lambda c, a: res.delete(c, a.id))
    if "enable" in res.actions:
        add("enable", "Set enabled=true", True).set_defaults(
            func=lambda c, a: res.patch(c, a.id, {"enabled": True}))
    if "disable" in res.actions:
        add("disable", "Set enabled=false", True).set_defaults(
            func=lambda c, a: res.patch(c, a.id, {"enabled": False}))
    return actions


def _list(client: UDMClient, args: argparse.Namespace, res: Resource) -> Any:
    items = res.list(client)
    return Brief([res.brief(i) for i in items]) if args.brief else items


def _update(client: UDMClient, args: argparse.Namespace, res: Resource) -> Any:
    if args.patch is not None:
        changes = load_json_arg(args.patch, "--patch")
        if not isinstance(changes, dict):
            raise UsageError("--patch must be a JSON object")
        return res.patch(client, args.id, changes)
    return res.update(client, args.id, load_json_arg(args.data))
