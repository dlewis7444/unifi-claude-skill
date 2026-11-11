"""Shared helpers: argument parsing helpers, compact ("brief") views, output."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable

from .secrets import redact

_MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")


class UsageError(Exception):
    """Bad command-line input detected after argparse (missing data, bad MAC...)."""


def mac(value: str) -> str:
    """Normalise a MAC address to lower-case colon form (argparse type)."""
    raw = value.strip().lower().replace("-", ":").replace(".", "")
    if ":" not in raw and len(raw) == 12:
        raw = ":".join(raw[i:i + 2] for i in range(0, 12, 2))
    if not _MAC_RE.match(raw):
        raise argparse.ArgumentTypeError(f"not a MAC address: {value!r}")
    return raw


def load_json_arg(value: str | None, flag: str = "--data") -> Any:
    """Parse a JSON argument. Accepts inline JSON, `@path/to/file.json` or `-` (stdin)."""
    if value is None:
        raise UsageError(f"{flag} is required")
    if value == "-":
        text = sys.stdin.read()
    elif value.startswith("@"):
        text = Path(value[1:]).expanduser().read_text()
    else:
        text = value
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise UsageError(f"{flag} is not valid JSON: {e}") from e


def find_item(items: Iterable[dict], item_id: str) -> dict | None:
    return next((i for i in items if item_id in (i.get("_id"), i.get("id"))), None)


def item_id(item: dict) -> str | None:
    return item.get("_id") or item.get("id")


# ── Brief views ────────────────────────────────────────────────────────────

DEVICE_STATES = {
    0: "offline", 1: "online", 2: "pending-adoption", 4: "upgrading",
    5: "provisioning", 6: "heartbeat-missed", 7: "adopting", 9: "adoption-failed",
    10: "isolated", 11: "rf-scanning",
}


def ago(epoch_s: Any) -> str | None:
    if not isinstance(epoch_s, (int, float)) or epoch_s <= 0:
        return None
    return duration(time.time() - epoch_s) + " ago"


def duration(seconds: Any) -> str | None:
    if not isinstance(seconds, (int, float)):
        return None
    s = int(seconds)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if d:
        return f"{d}d{h}h"
    if h:
        return f"{h}h{m}m"
    return f"{m}m{s}s"


def client_brief(c: dict) -> dict:
    wired = c.get("is_wired")
    return {
        "name": c.get("name") or c.get("hostname") or c.get("oui") or "?",
        "ip": c.get("ip") or c.get("fixed_ip") or c.get("last_ip"),
        "mac": c.get("mac"),
        "network": c.get("network") or c.get("last_connection_network_name"),
        "link": "wired" if wired else (c.get("essid") or ("wifi" if wired is False else None)),
        "signal": c.get("signal"),
        "online": c.get("_online", "uptime" in c),
        "uptime": duration(c.get("uptime")),
        "last_seen": ago(c.get("last_seen")),
        "blocked": c.get("blocked", False),
        "fixed_ip": c.get("fixed_ip") if c.get("use_fixedip") else None,
    }


def device_brief(d: dict) -> dict:
    return {
        "name": d.get("name") or d.get("model"),
        "model": d.get("model"),
        "type": d.get("type"),
        "mac": d.get("mac"),
        "ip": d.get("ip"),
        "state": DEVICE_STATES.get(d.get("state"), d.get("state")),
        "version": d.get("version"),
        "upgrade": d.get("upgrade_to_firmware") if d.get("upgradable") else None,
        "clients": d.get("num_sta"),
        "uptime": duration(d.get("uptime")),
    }


def rule_brief(r: dict) -> dict:
    out = {"id": item_id(r), "name": r.get("name") or r.get("description")}
    for key in ("enabled", "action", "ruleset", "rule_index", "index", "predefined",
                "fwd", "fwd_port", "dst_port", "proto", "protocol"):
        if key in r:
            out[key] = r[key]
    return out


# ── Output ─────────────────────────────────────────────────────────────────

def drop_empty(rows: list[dict]) -> list[dict]:
    """Remove columns that are empty in every row."""
    keys = [k for k in (rows[0] if rows else {})
            if any(r.get(k) not in (None, "", False) for r in rows)]
    return [{k: r.get(k) for k in keys} for r in rows]


def table(rows: list[dict]) -> str:
    if not rows:
        return "(no results)"
    rows = drop_empty(rows)
    keys = list(rows[0])
    cells = [[_cell(r.get(k)) for k in keys] for r in rows]
    widths = [max(len(k), *(len(row[i]) for row in cells)) for i, k in enumerate(keys)]
    lines = ["  ".join(k.ljust(w) for k, w in zip(keys, widths)).rstrip()]
    lines += ["  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip() for row in cells]
    return "\n".join(lines)


def _cell(v: Any) -> str:
    if v is None:
        return "-"
    if v is True:
        return "yes"
    if v is False:
        return "no"
    return str(v)


def emit(data: Any, as_json: bool, show_secrets: bool = False) -> None:
    if not show_secrets:
        data = Brief(redact(data.rows)) if isinstance(data, Brief) else redact(data)
    if isinstance(data, Brief):
        if as_json:
            print(json.dumps(data.rows))
        else:
            print(table(data.rows))
        return
    print(json.dumps(data) if as_json else json.dumps(data, indent=2))


class Brief:
    """Marker wrapper: a list of flat dicts that should print as a table."""

    def __init__(self, rows: list[dict]):
        self.rows = rows
