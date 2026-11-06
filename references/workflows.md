# Workflows

Remember the safety rules in SKILL.md: look up first, confirm mutations with the user,
`--dry-run` non-trivial changes.

## "Is everything OK?" / "the internet is slow"

1. `udm summary` — check `internet.status`, `latency_ms`, `subsystems`, `devices.not_online`.
2. If WAN looks fine, `udm speedtest` (last result) or, with consent, `udm speedtest run --wait`.
3. `udm events --hours 6 --limit 50` and `udm alarms` for recent problems (WAN failover,
   AP disconnects, DHCP exhaustion…).
4. Busy clients: `udm stats report --scope user --hours 1 --attrs bytes,rx_bytes,tx_bytes`
   or `udm stats dpi` for per-application traffic.

## Block a device by name

1. `udm clients find "<name>"` — confirm with the user which row is meant (several
   devices can share a vendor or hostname prefix).
2. `udm clients block <mac>`; undo with `unblock`.

## Give a device a fixed IP (DHCP reservation) and a friendly name

1. `udm clients find printer` → MAC and current network.
2. `udm networks --brief` → check the IP is inside that network's subnet and ideally
   outside the DHCP range.
3. `udm --dry-run clients set <mac> --name "Office printer" --fixed-ip 192.168.1.20`
4. Run it without `--dry-run`. The device picks the IP up on its next DHCP renew
   (`udm clients kick <mac>` forces a reconnect for WiFi clients).

## Add a port forward

```bash
udm --dry-run portforward create --data '{
  "name": "HTTPS to NAS", "enabled": true,
  "pfwd_interface": "wan", "src": "any",
  "dst_port": "443", "fwd": "192.168.1.50", "fwd_port": "443",
  "proto": "tcp", "log": false
}'
```

If the controller rejects the body, copy the shape of an existing rule:
`udm portforward get <existing-id>` and reuse its keys (minus `_id`, `site_id`).

## Toggle a rule

```bash
udm trafficrules --brief            # or: policies / firewall / portforward
udm trafficrules disable <id>
```

## Change one field of a rule

```bash
udm --dry-run policies update <id> --patch '{"action": "BLOCK"}'
udm policies update <id> --patch '{"action": "BLOCK"}'
```

## Zone-based firewall: block IoT → LAN

1. `udm zones --brief` → ids of the source zone (e.g. a custom "IoT" zone) and the
   destination zone (`internal`).
2. `udm policies --brief` → check nothing equivalent exists; note `index` values.
3. Use an existing user policy as a template: `udm policies get <id>`; build a new object
   with `name`, `enabled`, `action` (`BLOCK`/`ALLOW`/`REJECT`), `source.zone_id`,
   `destination.zone_id`, `protocol`, `ip_version`, keeping the other keys as in the template.
4. `udm --dry-run policies create --data @policy.json`, confirm, create.

Predefined policies (`predefined: true`) cannot be changed — add a user policy instead.

## Guest WiFi

- New password: `udm wlans --brief` → id of the guest SSID →
  `udm wlans set-password <id> '<new password>'` (clients must reconnect).
- Turn guest WiFi off for the night: `udm wlans disable <id>` (or a traffic rule with a schedule).
- Vouchers for visitors: `udm vouchers create --count 5 --minutes 480 --note "workshop"`
  prints the new codes.

## Restart a misbehaving AP

1. `udm devices --brief` → MAC of the AP, check `clients` count.
2. Warn the user how many clients will drop; after confirmation `udm devices restart <mac>`.
3. For a PoE-powered device that is hung: `udm devices ports <switch-mac>` → find the port,
   then `udm devices power-cycle <switch-mac> <port>`.
