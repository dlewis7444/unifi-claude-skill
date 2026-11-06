"""Networks/VLANs, WiFi (WLANs), static routes, dynamic DNS."""

from __future__ import annotations

import argparse
from typing import Any

from ..client import UDMClient
from ..resources import Resource, register as register_resource
from ..util import item_id

NETWORKS = Resource(
    command="networks", help="Networks / VLANs (subnets, DHCP, purpose)",
    layer="legacy", path="rest/networkconf",
    actions=("list", "get", "update", "enable", "disable"),
    brief=lambda n: {"id": item_id(n), "name": n.get("name"), "purpose": n.get("purpose"),
                     "vlan": n.get("vlan"), "subnet": n.get("ip_subnet"),
                     "dhcp": n.get("dhcpd_enabled"), "enabled": n.get("enabled")},
)

WLANS = Resource(
    command="wlans", help="WiFi networks (SSIDs)",
    layer="legacy", path="rest/wlanconf",
    actions=("list", "get", "update", "enable", "disable"),
    brief=lambda w: {"id": item_id(w), "name": w.get("name"), "enabled": w.get("enabled"),
                     "security": w.get("security"), "network": w.get("networkconf_id"),
                     "guest": w.get("is_guest"), "hidden": w.get("hide_ssid")},
)

ROUTES = Resource(
    command="routes", help="Static routes",
    layer="legacy", path="rest/routing",
    brief=lambda r: {"id": item_id(r), "name": r.get("name"), "enabled": r.get("enabled"),
                     "network": r.get("static-route_network"),
                     "nexthop": r.get("static-route_nexthop"),
                     "type": r.get("static-route_type")},
)

DDNS = Resource(
    command="ddns", help="Dynamic DNS configs",
    layer="legacy", path="rest/dynamicdns", actions=("list", "get", "update"),
)


def vlans(client: UDMClient) -> Any:
    """Networks as seen by the official Integration API."""
    sites = client.get(client.integration("sites"))
    site_id = client.site
    if isinstance(sites, list) and sites:
        match = next((s for s in sites if s.get("internalReference") == client.site), sites[0])
        site_id = match.get("id", client.site)
    return client.get(client.integration(f"sites/{site_id}/networks"))


def vpn(client: UDMClient) -> dict:
    # Network 10.x removed rest/vpnclient, rest/vpnserver and stat/vpn;
    # the v2 VPN API replaces them.
    def conns(path: str) -> Any:
        data = client.get(client.v2(path))
        return data.get("connections", data) if isinstance(data, dict) else data

    return {
        "connections": conns("vpn/connections"),
        "client_connections": conns("vpn/client-connections"),
        "users": client.get(client.v2("vpn/users")),
    }


def register(sub: argparse._SubParsersAction) -> None:
    for res in (NETWORKS, ROUTES, DDNS):
        register_resource(sub, res)

    acts = register_resource(sub, WLANS)
    ap = acts.add_parser("set-password", help="Change the WPA passphrase of an SSID")
    ap.add_argument("id")
    ap.add_argument("password")
    ap.set_defaults(func=lambda c, a: WLANS.patch(c, a.id, {"x_passphrase": a.password}))

    sub.add_parser("vpn", help="VPN: site-to-site, client tunnels, VPN users").set_defaults(
        func=lambda c, a: vpn(c))
    sub.add_parser("vlans", help="Networks via the Integration API").set_defaults(
        func=lambda c, a: vlans(c))
