# API notes

## Layers

| Layer | Base path | Notes |
|---|---|---|
| Legacy Network API | `/proxy/network/api/s/<site>/` | Most config (`rest/*`), stats (`stat/*`), commands (`cmd/*`). Responses use `{"meta": {"rc": "ok"}, "data": [...]}`. |
| v2 Network API | `/proxy/network/v2/api/site/<site>/` | Traffic rules, zone firewall, system log, VPN. Plain JSON, no envelope. |
| Integration API | `/proxy/network/integration/v1/` | Official, versioned, but limited: sites, devices, clients, networks. Uses site UUIDs. |

Authentication: header `X-API-Key: <key>`; no cookie or CSRF token needed. TLS
verification is disabled because UniFi OS uses a self-signed certificate. Port 443.

The script raises an error (exit 1) on HTTP ≥ 400 and on legacy envelopes with
`meta.rc == "error"` — `meta.msg` (e.g. `api.err.InvalidPayload`) is shown.

## Network Application 10.x changes

Removed legacy endpoints (they now return 404 `api.err.NotFound` or 400
`api.err.InvalidObject`): `stat/event`, `stat/alarm`, `stat/admin`, `stat/gateway`,
`rest/vpnclient`, `rest/vpnserver`, `stat/vpn`.

Replacements used by the script:

- Events → `POST v2/system-log/all` with `{"pageNumber": n, "pageSize": 100}`; paginated,
  newest first, `timestamp` in epoch ms, `total_page_count` in the response.
- Alarms → `POST v2/system-log/critical` (unread critical alerts);
  `PUT v2/system-log/critical/mark-all-as-read`, `PUT v2/system-log/critical/<id>/mark-as-read`.
- VPN → `GET v2/vpn/connections`, `v2/vpn/client-connections`, `v2/vpn/users`.
- Gateway stats → `stat/health` subsystems `wan` and `www`.

## Zone-based firewall (Network 9.x+)

- Zones: `GET v2/firewall/zone`; overview: `GET v2/firewall/zone-matrix`.
- Policies: `GET/POST v2/firewall-policies`, `PUT v2/firewall-policies/<id>`,
  delete with `POST v2/firewall-policies/batch-delete` and a JSON array of ids.
- Policies with `predefined: true` are system policies and are read-only.

These endpoints are undocumented and moved between releases; if one returns 404 on the
user's controller, explore with `udm raw GET /proxy/network/v2/api/site/default/<path>`
and report back rather than guessing payloads.

## Quirks

- Legacy `rest/*` PUT/DELETE need the object `_id` from a GET.
- Partial updates often fail or silently reset fields — use `update --patch`, which fetches,
  merges and PUTs the whole object.
- v2 `trafficrules` PUT answers HTTP 201 instead of 200.
- `cmd/*` calls are always POST; read-only ones (`speedtest-status`, `list-backups`) are
  marked non-mutating, so they also run under `--dry-run`.
- `stat/report/<interval>.<scope>` expects `start`/`end` in epoch **milliseconds**.
- Legacy firewall rules (`rest/firewallrule`) and v2 traffic rules are independent systems;
  once a site is migrated to the zone-based firewall, legacy rules are read-only or empty.
- Voucher codes are 10 digits; the UI shows them as `12345-67890`.

## Experimental / unverified on 10.x

`backup list|create` (legacy `cmd/backup`) and `vouchers` (legacy `cmd/hotspot`,
`stat/voucher`) come from the classic controller API. Check them with `--dry-run` and a
read first; if they return `api.err.NotFound`, they are not available on that release.
