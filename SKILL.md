---
name: unifi
description: >
  Manage and query a UniFi Dream Machine Pro or other UniFi OS controller via its
  local API. Use this skill whenever the user asks about their network, connected
  devices, clients, firewall rules, port forwarding, VLANs, WiFi SSIDs, VPN, traffic
  stats, events, or alarms — even if they don't say "UniFi" explicitly. Also use for
  any task involving blocking/unblocking devices, restarting APs or switches, toggling
  rules, or viewing network health. If the user says things like "check who's on the
  network", "block this device", "add a port forward", "what's my WAN traffic", "show
  firewall rules", or "restart the AP", this skill applies.
---

# UniFi Dream Machine Pro Skill

## Helper script

All API operations go through the helper script. Use it for everything — don't make raw
curl calls unless `udm.py raw` is insufficient.

**Script path:** `~/.claude/skills/unifi/scripts/udm.py`

The script fetches the API key from the `UNIFI_API_KEY` env var or `pass network/unifi/api-key`
automatically. No manual credential handling needed.

```bash
python ~/.claude/skills/unifi/scripts/udm.py <command> [subcommand] [args]
```

Add `--json` for compact output when piping or parsing. Default output is pretty-printed JSON.

---

## Command reference

### Status & health
```bash
python udm.py status                        # System health + controller info
python udm.py stats gateway                 # WAN/gateway traffic stats
python udm.py stats dpi                     # Application/category traffic breakdown
python udm.py stats report [--interval hourly|daily|5minutes]
```

### Clients (connected devices)
```bash
python udm.py clients                       # Active/connected clients
python udm.py clients --all                 # All known clients incl. offline
python udm.py clients block   <mac>         # Block a client
python udm.py clients unblock <mac>         # Unblock a client
python udm.py clients kick    <mac>         # Force reconnect (kick)
```
Key fields in client data: `hostname`, `ip`, `mac`, `essid` (WiFi SSID), `ap_mac`,
`signal`, `tx_bytes`, `rx_bytes`, `uptime`, `blocked`, `last_seen`.

### Network devices (APs, switches, gateway)
```bash
python udm.py devices                       # All managed devices
python udm.py devices restart         <mac> # Restart a device
python udm.py devices upgrade         <mac> # Upgrade firmware
python udm.py devices adopt           <mac> # Adopt pending device
python udm.py devices force-provision <mac> # Force re-provision
python udm.py devices spectrum-scan   <mac> # WiFi spectrum scan
```
Key fields: `name`, `mac`, `model`, `version`, `ip`, `state`, `uptime`,
`update_available`, `num_sta` (connected clients).

### Networks and VLANs
```bash
python udm.py networks                      # All network configs (VLANs, subnets, DHCP)
python udm.py networks update <id> --data '<json>'   # Update a network
python udm.py vlans                         # VLANs via Integration API
python udm.py wlans                         # WiFi SSIDs
python udm.py wlans update <id> --data '<json>'      # Update a WLAN
```

### Firewall rules (legacy iptables-style)
```bash
python udm.py firewall list
python udm.py firewall create --data '<rule_json>'
python udm.py firewall update <id> --data '<full_rule_json>'  # must send full object
python udm.py firewall delete <id>
python udm.py firewall groups                                 # IP/port groups
python udm.py firewall group-create --data '<group_json>'
python udm.py firewall group-update <id> --data '<group_json>'
python udm.py firewall group-delete <id>
```
**Important:** Updates require the full object, not just the changed fields. Fetch first,
modify what you need, send it back.

### Traffic rules (v2 zone-based rules — newer UI "Traffic & Security")
```bash
python udm.py trafficrules list
python udm.py trafficrules enable  <id>
python udm.py trafficrules disable <id>
python udm.py trafficrules create  --data '<rule_json>'
python udm.py trafficrules update  <id> --data '<full_rule_json>'
python udm.py trafficrules delete  <id>
```
Note: PUT returns HTTP 201, not 200 — that's normal.

### Port forwarding
```bash
python udm.py portforward list
python udm.py portforward enable  <id>
python udm.py portforward disable <id>
python udm.py portforward create  --data '<rule_json>'
python udm.py portforward update  <id> --data '<full_rule_json>'
python udm.py portforward delete  <id>
```

### VPN
```bash
python udm.py vpn                           # VPN clients, servers, active tunnels
```

### Events & alarms
```bash
python udm.py events                        # Last 24 hours
python udm.py events --hours 48             # Custom window
python udm.py alarms                        # Unresolved alarms
python udm.py alarms archive-all            # Clear all alarms
python udm.py alarms archive <id>           # Archive a specific alarm
```

### Routing & DNS
```bash
python udm.py routes                        # Static routes
python udm.py ddns                          # Dynamic DNS configs
```

### Escape hatch — raw API calls
```bash
python udm.py raw GET  /proxy/network/api/s/default/stat/health
python udm.py raw POST /proxy/network/api/s/default/cmd/stamgr --data '{"cmd":"kick-sta","mac":"aa:bb:cc:dd:ee:ff"}'
python udm.py raw PUT  /proxy/network/v2/api/site/default/trafficrules/<id> --data '<json>'
```

---

## API structure (for raw calls)

| Layer | Base path | Notes |
|---|---|---|
| Legacy Network API | `/proxy/network/api/s/default/` | Comprehensive; use for most things |
| v2 Network API | `/proxy/network/v2/api/site/default/` | Traffic rules, newer resources |
| Integration API | `/proxy/network/integration/v1/` | Official but limited: sites, devices, clients, VLANs |

All auth uses `X-API-Key` header. No CSRF token needed with API key auth.
TLS verification is disabled (self-signed cert). Port 443 only.

---

## Workflow patterns

**"Who's on the network?"**
```bash
python udm.py clients | python -c "import json,sys; [print(f\"{c.get('hostname','?'):25} {c.get('ip','?'):15} {c.get('mac','?')}\") for c in json.load(sys.stdin)]"
```
Or just run `python udm.py clients` and summarize the relevant fields.

**"Block a device by hostname"**
1. `python udm.py clients` — find the MAC for the hostname
2. `python udm.py clients block <mac>`

**"Toggle a firewall/traffic rule"**
1. `python udm.py trafficrules list` — find the rule ID and current state
2. `python udm.py trafficrules enable <id>` or `disable <id>`

**"Add a port forward"**
```bash
python udm.py portforward create --data '{
  "name": "HTTP to server",
  "enabled": true,
  "fwd": "192.168.1.100",
  "fwd_port": "80",
  "dst_port": "80",
  "proto": "tcp_udp",
  "src": "any"
}'
```

**"Create a firewall rule"**
Fetch an existing rule as a template first:
```bash
python udm.py firewall list | python -c "import json,sys; rules=json.load(sys.stdin); print(json.dumps(rules[0], indent=2))"
```
Then POST a new rule with the same structure, without `_id`.

**"Check system health at a glance"**
```bash
python udm.py status
```
Look for `health[].subsystem` + `health[].status` for WAN/LAN/WLAN/VPN.

---

## Tips

- `_id` fields from GET responses are required for PUT/DELETE on legacy REST endpoints.
- For firewall and traffic rule updates, always fetch the full object first, modify in memory,
  then PUT the whole thing back. Partial updates often fail or silently corrupt config.
- The two firewall systems (legacy `firewallrule` vs v2 `trafficrules`) are independent —
  both may be in use simultaneously.
- If a command returns an empty list `[]` when you expect data, try `python udm.py raw GET <path>`
  to see the raw response envelope and any error messages.
