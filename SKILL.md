---
name: unifi
description: >
  Manage and query a UniFi OS controller (Dream Machine Pro/SE, Cloud Gateway, UDR...)
  via its local API. Use this skill whenever the user asks about their home/office
  network, connected devices or clients, WiFi SSIDs or passwords, firewall rules or
  zone policies, port forwarding, VLANs, VPN, internet speed or WAN status, traffic
  stats, events or alerts, guest vouchers, or switch PoE ports — even if they don't
  say "UniFi". Typical asks: "who's on the network", "block this device", "give the
  printer a fixed IP", "add a port forward", "what's my WAN traffic", "run a speed
  test", "restart the AP", "change the guest WiFi password", "is everything healthy".
---

# UniFi skill

Everything goes through one helper script (Python 3.10+, no dependencies):

```bash
python ~/.claude/skills/unifi/scripts/udm.py <command> [action] [args] [global flags]
```

Below, `udm` means that full command. Run `udm <command> --help` for exact arguments.

**Global flags** (allowed anywhere): `--json` (compact output), `--dry-run` (print
mutating requests instead of sending), `--host`, `--site`, `--timeout`.

Configuration (host, API key) comes from `.env` next to `SKILL.md`. If the script
says `No UniFi API key found`, point the user to README.md → "Generate a UniFi API key"
— do not ask them to paste the key into the chat.

## Safety rules — follow every time

1. **Read before you write.** Look up ids/MACs with a list or `find` command first.
2. **Confirm mutating actions with the user** before running them: blocking/kicking/
   forgetting clients, restarting/upgrading/adopting devices, PoE power-cycles, any
   create/update/delete/enable/disable, WiFi password changes, voucher creation,
   alarm archiving, backups. Say exactly what will change (object name + id).
3. For non-trivial changes (create/update/patch/delete), run the command with
   `--dry-run` first, show the request, then run it for real after confirmation.
4. Never restart or upgrade the **gateway** (type `udm`/`ugw`/`uxg`) or the switch/AP
   the user is connected through without warning that the network will drop.
5. Prefer `update <id> --patch '{...}'` over `--data`: it fetches the current object
   and merges, so unrelated fields are not lost.

## Picking the right command

| User wants… | Command |
|---|---|
| Overall health / "is everything ok" | `udm summary` |
| Who is online / find a device | `udm clients --brief`, `udm clients find <name\|ip\|mac>` |
| Block / unblock / kick / forget | `udm clients block <mac>` (etc.) |
| Alias, note, fixed IP (DHCP reservation) | `udm clients set <mac> --name … --fixed-ip …` |
| APs, switches, gateway | `udm devices --brief`, `udm devices restart <mac>` |
| Switch ports, PoE reset | `udm devices ports <mac>`, `udm devices power-cycle <mac> <port>` |
| Networks / VLANs | `udm networks --brief` |
| WiFi SSIDs, toggle, password | `udm wlans --brief`, `wlans enable <id>`, `wlans set-password <id> <pw>` |
| Firewall (Network 9+ zone-based) | `udm zones --brief`, `udm policies --brief` |
| Firewall (legacy rule sets) | `udm firewall --brief`, `udm firewall-groups --brief` |
| Traffic rules (block apps/domains/schedules) | `udm trafficrules --brief` |
| Port forwards | `udm portforward --brief` (alias `pf`) |
| Internet speed | `udm speedtest`, `udm speedtest run --wait` |
| Traffic stats | `udm stats`, `udm stats dpi`, `udm stats report --hours 24` |
| Events / alerts | `udm events --hours 24 --limit 50`, `udm alarms` |
| Guest vouchers | `udm vouchers`, `udm vouchers create --count 3 --minutes 480` |
| VPN, routes, DDNS | `udm vpn`, `udm routes --brief`, `udm ddns` |
| Anything else | `udm raw GET /proxy/network/...` |

Collections (`firewall`, `firewall-groups`, `trafficrules`, `portforward`, `policies`,
`zones`, `networks`, `wlans`, `routes`, `ddns`) all share the same verbs:
`list [--brief]`, `get <id>`, `create --data`, `update <id> --patch|--data`, `delete <id>`,
`enable <id>`, `disable <id>` (where the resource supports them). `--data` and `--patch`
accept inline JSON, `@file.json`, or `-` for stdin.

**Which firewall?** If `udm zones` returns zones, the site uses the zone-based firewall
— manage it with `policies`. Otherwise use `firewall` (legacy). `trafficrules` exist in
both setups and are independent of the firewall.

**Context economy:** default to `--brief` for lists. Fetch full objects (`get <id>`)
only for the items you are going to inspect or modify.

## References (read when needed)

- `references/commands.md` — every command, argument and output field
- `references/workflows.md` — step-by-step recipes (port forward, block by name,
  fixed IP, zone policy, guest WiFi, troubleshooting a slow network)
- `references/api-notes.md` — API layers, Network 10.x endpoint changes, quirks, raw calls
