"""HTTP client for the UniFi OS local API (legacy, v2 and Integration layers)."""

from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request
from typing import Any, Callable

# transport(method, url, headers, data, timeout) -> (status, body_text)
Transport = Callable[[str, str, dict, "bytes | None", float], "tuple[int, str]"]


class APIError(Exception):
    """Any failure talking to the controller (network, HTTP or API-level)."""

    def __init__(self, message: str, status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body


def _urllib_transport(method: str, url: str, headers: dict, data: bytes | None,
                      timeout: float) -> tuple[int, str]:
    # UniFi OS ships a self-signed certificate.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except urllib.error.URLError as e:
        raise APIError(f"Cannot reach {url}: {e.reason}") from e
    except TimeoutError as e:
        raise APIError(f"Timed out after {timeout:g}s waiting for {url}") from e


class UDMClient:
    def __init__(self, host: str, api_key: str, site: str = "default",
                 timeout: float = 30.0, dry_run: bool = False,
                 transport: Transport | None = None):
        self.host = host
        self.base = f"https://{host}"
        self.site = site
        self.timeout = timeout
        self.dry_run = dry_run
        self._transport = transport or _urllib_transport
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ── URL builders ────────────────────────────────────────────────────────

    def legacy(self, path: str) -> str:
        return f"{self.base}/proxy/network/api/s/{self.site}/{path}"

    def v2(self, path: str) -> str:
        return f"{self.base}/proxy/network/v2/api/site/{self.site}/{path}"

    def integration(self, path: str) -> str:
        return f"{self.base}/proxy/network/integration/v1/{path}"

    def absolute(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self.base}/{path.lstrip('/')}"

    # ── Core request ────────────────────────────────────────────────────────

    def request(self, method: str, url: str, body: Any = None, *,
                unwrap: bool = True, mutating: bool | None = None) -> Any:
        """Send a request and return the decoded JSON.

        `mutating` defaults to "anything but GET". Reads that use POST (stats
        reports, system-log queries, status commands) pass mutating=False so they
        still run under --dry-run.
        """
        method = method.upper()
        if mutating is None:
            mutating = method != "GET"
        if self.dry_run and mutating:
            return {"dry_run": True, "method": method, "url": url, "body": body}

        data = json.dumps(body).encode() if body is not None else None
        status, text = self._transport(method, url, self.headers, data, self.timeout)

        if status >= 400:
            raise APIError(f"HTTP {status} for {method} {url}: {_error_message(text)}",
                           status=status, body=text)
        if not text.strip():
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            raise APIError(f"Non-JSON response from {url}: {text[:200]}",
                           status=status, body=text) from e

        if isinstance(parsed, dict):
            meta = parsed.get("meta")
            if isinstance(meta, dict) and meta.get("rc") == "error":
                raise APIError(f"API error for {method} {url}: {meta.get('msg', meta)}",
                               status=status, body=text)
            if unwrap and "data" in parsed:
                return parsed["data"]
        return parsed

    def get(self, url: str, **kw: Any) -> Any:
        return self.request("GET", url, **kw)

    def post(self, url: str, body: Any = None, **kw: Any) -> Any:
        return self.request("POST", url, body, **kw)

    def put(self, url: str, body: Any = None, **kw: Any) -> Any:
        return self.request("PUT", url, body, **kw)

    def delete(self, url: str, **kw: Any) -> Any:
        return self.request("DELETE", url, **kw)

    # Commands on the legacy cmd/* managers
    def cmd(self, manager: str, cmd: str, *, mutating: bool = True, **params: Any) -> Any:
        return self.post(self.legacy(f"cmd/{manager}"), {"cmd": cmd, **params},
                         mutating=mutating)


def _error_message(text: str) -> str:
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        plain = " ".join(re.sub(r"<[^>]+>", " ", text).split())
        return plain[:300] or "(empty body)"
    if isinstance(parsed, dict):
        meta = parsed.get("meta")
        if isinstance(meta, dict) and meta.get("msg"):
            return str(meta["msg"])
        for key in ("message", "msg", "error", "code"):
            if parsed.get(key):
                return str(parsed[key])
    return text.strip()[:300]
