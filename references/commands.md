# Command reference

`udm` = `python ~/.claude/skills/unifi/scripts/udm.py`. Global flags work in any
position: `--json`, `--dry-run`, `--host HOST`, `--site SITE`, `--timeout SEC`,
`--show-secrets`.

Secrets (WiFi passphrases, passwords, private keys, tokens — `x_*` fields, `*password*`,
`*private_key*`, `utm_token`, PEM private keys) are printed as `"<redacted>"` unless
`--show-secrets` is given. A PUT whose body still contains `"<redacted>"` gets the
current values filled back in from the controller; a POST with placeholders is refused.

Exit codes: `0` ok, `1` API/network error, `2` usage or configuration error.
Errors go to stderr as one line: `error: HTTP 400 for PUT …: api.err.InvalidPayload`.

## Overview

```bash
udm summary            # internet, subsystems, devices not online / upgradable, client counts, unread alerts
udm status             # raw stat/health + stat/sysinfo
```

`summary` fields: `internet.{status,wan_ip,isp,latency_ms,down_mbps,up_mbps,speedtest_at}`,
`subsystems.{wan,www,lan,wlan,vpn}`, `devices.{total,not_online[],upgradable[]}`,
`clients.{online,wired,wireless,blocked}`, `unread_alerts`.

## Clients

```bash
udm clients [--all] [--brief]          # online clients; --all adds offline known clients
udm clients find <text> [--full]       # substring match on name, hostname, IP, MAC, vendor (oui), note
udm clients block|unblock|kick <mac>
udm clients forget <mac>               # remove from known clients
udm clients set <mac> [--name ALIAS] [--note TEXT] [--fixed-ip IP [--network-id ID]] [--clear-fixed-ip]
```

MACs are accepted as `aa:bb:…`, `AA-BB-…` or `aabbcc…`.
Brief columns: `name ip mac network link(ssid|wired) signal online uptime last_seen blocked fixed_ip`.
Full-object fields worth knowing: `hostname`, `name` (alias), `ip`, `mac`, `oui`, `essid`,
`ap_mac`, `sw_mac`/`sw_port`, `signal`, `tx_bytes`, `rx_bytes`, `uptime`, `blocked`,
`last_seen`, `use_fixedip`, `fixed_ip`, `network_id`.

## Devices

```bash
udm devices [--brief]
udm devices restart|upgrade|adopt|force-provision|spectrum-scan|locate|unlocate <mac>
udm devices ports <mac>                 # port table: link, speed, PoE mode and draw
udm devices power-cycle <switch-mac> <port>
```

Brief columns: `name model type mac ip state version upgrade clients uptime`.
`type`: `udm`/`ugw`/`uxg` gateway, `usw` switch, `uap` access point.
`state`: online, offline, pending-adoption, upgrading, provisioning, heartbeat-missed, adopting.

## Collections (shared verbs)

```bash
udm <collection> [list] [--brief]
udm <collection> get <id>
udm <collection> create --data '<json>' | @file.json | -
udm <collection> update <id> --patch '<partial json>'    # fetch + deep-merge + PUT
udm <collection> update <id> --data  '<full json>'       # replace
udm <collection> delete <id>
udm <collection> enable|disable <id>
```

| Collection | Endpoint | Verbs |
|---|---|---|
| `firewall` | legacy `rest/firewallrule` | all |
| `firewall-groups` | legacy `rest/firewallgroup` | list get create update delete |
| `trafficrules` | v2 `trafficrules` | all |
| `portforward` / `pf` | legacy `rest/portforward` | all |
| `policies` | v2 `firewall-policies` (delete via `batch-delete`) | all |
| `zones` | v2 `firewall/zone` | list get |
| `networks` | legacy `rest/networkconf` | list get update enable disable |
| `wlans` | legacy `rest/wlanconf` | list get update enable disable + `set-password <id> <pw>` |
| `routes` | legacy `rest/routing` | all |
| `ddns` | legacy `rest/dynamicdns` | list get update |

Also: `udm zone-matrix` (zone × zone default actions), `udm vlans` (Integration API view
of networks), `udm vpn` (site-to-site, client tunnels, VPN users).

## Statistics and logs

```bash
udm stats [gateway]                    # wan + www health: IP, throughput, latency, speedtest
udm stats dpi                          # traffic by application category
udm stats report [--interval 5minutes|hourly|daily] [--hours N] [--scope site|user|ap|gw] [--attrs a,b]
udm speedtest [status]                 # last result
udm speedtest run [--wait]             # start a test (takes ~30–60 s)
udm events [--hours 24] [--limit N]    # v2 system log, newest first
udm alarms [list] | archive-all | archive <id>
```

Event fields: `timestamp` (epoch ms), `category`, `subcategory`, `event`, `severity`,
`message_raw` (template) + `parameters`, `status`, `target`.

## Guests and backups

```bash
udm vouchers [list]
udm vouchers create [--count 1] [--minutes 1440] [--uses 1] [--note T] [--up KBPS] [--down KBPS] [--quota-mb MB]
udm vouchers delete <id>
udm backup [list]                      # experimental
udm backup create [--days 0]           # experimental
```

## Escape hatch

```bash
udm raw GET    /proxy/network/api/s/default/stat/health
udm raw POST   /proxy/network/api/s/default/cmd/stamgr --data '{"cmd":"kick-sta","mac":"…"}'
udm raw PUT    /proxy/network/v2/api/site/default/trafficrules/<id> --data @rule.json
udm raw GET    /proxy/network/api/s/default/stat/health --no-unwrap   # keep {meta,data}
```
