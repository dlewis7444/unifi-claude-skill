"""Firewall: legacy rules & groups, v2 traffic rules, zone-based policies, port forwards."""

from __future__ import annotations

from ..resources import Resource, register as register_resource
from ..util import item_id

FIREWALL_RULES = Resource(
    command="firewall", help="Legacy firewall rules (iptables-style rule sets)",
    layer="legacy", path="rest/firewallrule",
    notes="On Network 9+ with zone-based firewall enabled use `policies` instead.",
)

FIREWALL_GROUPS = Resource(
    command="firewall-groups", help="Firewall IP/port groups",
    layer="legacy", path="rest/firewallgroup",
    actions=("list", "get", "create", "update", "delete"),
    brief=lambda g: {"id": item_id(g), "name": g.get("name"),
                     "type": g.get("group_type"),
                     "members": ", ".join(map(str, g.get("group_members", [])))},
)

TRAFFIC_RULES = Resource(
    command="trafficrules", help="v2 traffic rules (Traffic & Security / Traffic Management)",
    layer="v2", path="trafficrules",
    notes="PUT returns HTTP 201 — that is normal.",
)

PORT_FORWARDS = Resource(
    command="portforward", help="Port forwarding rules",
    layer="legacy", path="rest/portforward", aliases=("pf",),
)

POLICIES = Resource(
    command="policies", help="Zone-based firewall policies (Network 9.x+)",
    layer="v2", path="firewall-policies", batch_delete="batch-delete",
    notes="Predefined (system) policies cannot be modified or deleted.",
    brief=lambda p: {
        "id": item_id(p), "name": p.get("name"), "enabled": p.get("enabled"),
        "action": p.get("action"), "index": p.get("index"),
        "src_zone": (p.get("source") or {}).get("zone_id"),
        "dst_zone": (p.get("destination") or {}).get("zone_id"),
        "predefined": p.get("predefined"),
    },
)

ZONES = Resource(
    command="zones", help="Firewall zones (Network 9.x+ zone-based firewall)",
    layer="v2", path="firewall/zone", actions=("list", "get"),
    brief=lambda z: {"id": item_id(z), "name": z.get("name"), "key": z.get("zone_key"),
                     "networks": len(z.get("network_ids", []) or [])},
)

RESOURCES = (FIREWALL_RULES, FIREWALL_GROUPS, TRAFFIC_RULES, PORT_FORWARDS, POLICIES, ZONES)


def register(sub) -> None:
    for res in RESOURCES:
        register_resource(sub, res)

    p = sub.add_parser("zone-matrix", help="Zone × zone overview of default policy actions")
    p.set_defaults(func=lambda c, a: c.get(c.v2("firewall/zone-matrix")))

