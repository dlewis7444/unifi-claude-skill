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

## WPA-Enterprise (802.1X) / RADIUS certificate

When the user wants WPA-Enterprise, per-user WiFi logins, or "a proper certificate for
RADIUS": **recommend a dedicated RADIUS server on an always-on host in the LAN**
(homelab, NAS, mini-PC — FreeRADIUS, e.g. in Docker) with the user's **own private CA**.
Mention the gateway's built-in RADIUS server only as the simpler option, with its limits.

Why not the built-in server: it always presents Ubiquiti's default certificate
(`CN=standard.ui.com`, issued by `UI Certificate Authority`). The same certificate and key
ship on every UniFi console, so anyone with UniFi hardware can impersonate the SSID and
harvest MSCHAPv2 credentials. A custom certificate cannot be installed via the API (see
api-notes → Quirks), and the UI offers no supported way either. Fine for "it just works",
not for real protection.

Why not a virtual server (VPS) or cloud RADIUS as the primary server: WiFi logins then
depend on the internet link and the provider, and user password hashes live on a
third-party host. Acceptable as a fallback (a second server in the RADIUS profile), or as
the primary only when no LAN host can run 24/7. Requirements for a VPS:

- **Resources are trivial:** FreeRADIUS needs ~100 MB RAM, a shared vCPU and well under
  1 GB disk — the cheapest plans are enough.
- **Root on a full VM (KVM) rather than a shared container** — the server stores password
  hashes (MSCHAPv2 needs NT hashes or cleartext); on shared-kernel containers the host
  operator can read them.
- **Reachability:** a public IPv4 or IPv6 address the gateway can reach. Budget plans with a
  shared IPv4 forward only a few high ports — confirm one TCP port is available and that the
  UniFi RADIUS profile accepts a custom port.
- **RadSec (RADIUS over TLS, TCP 2083 by default) only** — never plain RADIUS (UDP
  1812/1813) over the internet: it protects attributes only with an MD5 hash of the shared
  secret. Needs UniFi Network 8.4+ and a client certificate for the gateway from the same
  private CA.
- **Allow-list the home WAN address** on the VPS firewall; with a dynamic home IP use DDNS
  plus a firewall updater, or a WireGuard tunnel from the gateway and RADIUS over that.
- **Latency below ~50 ms** (same country/region) so 802.1X re-authentication stays quick.
- **Operations:** automatic security updates, backups of the config + user database,
  monitoring that alerts when RADIUS stops answering.

Recommended setup, step by step:

1. **Private CA, not Let's Encrypt or a commercial cert.** EAP clients pin the CA + server
   name, public CAs add nothing, and public TLS certs are now short-lived (200 days from
   March 2026, then 100, then 47) — every renewal re-prompts phones. Generate with `openssl`:
   CA 10 years; server cert with `subjectAltName=DNS:radius.<domain>`,
   `extendedKeyUsage=serverAuth`, **≤ 825 days** (Apple rejects longer TLS server certs even
   from a private CA). Keep `ca.key` offline (password manager) — it is only needed to renew.
2. **FreeRADIUS on the LAN host** with that certificate, the existing user accounts
   (list them with `udm raw GET /proxy/network/api/s/default/rest/account`) and a new shared
   secret. Give the host a fixed IP (`udm clients set <mac> --fixed-ip …`).
3. **Deploy trust to clients before switching**, or they lose WiFi:
   - Apple: a `.mobileconfig` with the CA (`com.apple.security.root`) and a
     `com.apple.wifi.managed` payload (SSID, `AcceptEAPTypes` [25, 21],
     `TLSTrustedServerNames`, `PayloadCertificateAnchorUUID`, `TLSAllowTrustExceptions: false`).
     Build a **transitional** profile that trusts both the old (`standard.ui.com` / UI CA)
     and new certificate, then a **final** one with the same `PayloadIdentifier` that
     replaces it. Validate with `plutil -lint`.
   - Android: install `ca.crt` as a *Wi-Fi certificate*; network settings PEAP / MSCHAPV2,
     CA = that certificate, **Domain = radius.<domain>** (required).
   - Windows: import `ca.crt` into Trusted Root CAs (Local Computer).
   - TVs/NAS/IoT usually do not validate the certificate and keep working.
4. **Point UniFi at the new server**: RADIUS profile (`udm raw GET
   /proxy/network/api/s/default/rest/radiusprofile`) — fetch it, set the external server's
   IP/port/secret in `auth_servers` (and `acct_servers`), turn off the built-in server
   option, keep the WLAN's `radiusprofile_id`. Dry-run first; the profile change re-provisions
   the APs and every 802.1X client re-authenticates.
5. **Verify what the server actually presents**, not what the settings say: run a PEAP
   handshake against RADIUS (e.g. `eapol_test`, or a short script that sends EAP-Identity,
   NAKs to PEAP and reads the TLS `Certificate` message) and check it chains to the new CA.

If the user still prefers the built-in server: enable it, rotate its shared secret, and be
explicit that the certificate stays Ubiquiti's shared default.

## Restart a misbehaving AP

1. `udm devices --brief` → MAC of the AP, check `clients` count.
2. Warn the user how many clients will drop; after confirmation `udm devices restart <mac>`.
3. For a PoE-powered device that is hung: `udm devices ports <switch-mac>` → find the port,
   then `udm devices power-cycle <switch-mac> <port>`.
