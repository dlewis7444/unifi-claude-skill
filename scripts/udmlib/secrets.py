"""Secret redaction for API output, and restoring redacted values on writes.

The controller API returns credentials in plain text: WiFi passphrases, SSH/RADIUS/
PPPoE passwords, VPN and TLS private keys, API tokens. Everything the CLI prints is
passed through `redact()` (unless --show-secrets), so those values never end up in
terminal scrollback, logs or an AI assistant's context.

Because the usual update workflow is "fetch object → change a field → PUT it back",
a body may come back containing REDACTED placeholders. `restore()` swaps them for the
values at the same path in the controller's current object, so writes keep working
and a placeholder can never be stored as a real password.
"""

from __future__ import annotations

import base64
from typing import Any

REDACTED = "<redacted>"

_SECRET_KEYS = {
    "utm_token", "password", "passphrase", "psk", "secret", "token",
    "private_key", "server_certificate_key", "pre_shared_key", "shared_secret",
}
_SECRET_SUBSTRINGS = ("password", "passphrase", "private_key", "secret", "psk", "token")
_PEM_B64_PREFIX = "LS0tLS1CRUdJTi"  # base64 of "-----BEGIN"


class RedactionError(Exception):
    """A write body holds REDACTED placeholders that cannot be restored."""


def is_secret_key(key: str) -> bool:
    k = key.lower()
    return k.startswith("x_") or k in _SECRET_KEYS or any(s in k for s in _SECRET_SUBSTRINGS)


def _contains_private_key(value: str) -> bool:
    if "PRIVATE KEY" in value:
        return True
    if value.startswith(_PEM_B64_PREFIX) and len(value) > 200:
        try:
            return b"PRIVATE KEY" in base64.b64decode(value, validate=False)
        except Exception:
            return True  # undecodable PEM-looking blob: err on the safe side
    return False


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def redact(data: Any) -> Any:
    """Return a copy of data with secret values replaced by REDACTED.

    Keys that look secret are masked unless their value is empty or a boolean
    (flags such as `x_ssh_auth_password_enabled` carry no secret). Any string
    holding a PEM private key — plain or base64-encoded — is masked wherever it is.
    """
    if isinstance(data, dict):
        return {k: (REDACTED if is_secret_key(str(k)) and not _is_empty(v)
                    and not isinstance(v, bool) else redact(v))
                for k, v in data.items()}
    if isinstance(data, list):
        return [redact(v) for v in data]
    if isinstance(data, str) and _contains_private_key(data):
        return REDACTED
    return data


def has_redacted(data: Any) -> bool:
    if data == REDACTED:
        return True
    if isinstance(data, dict):
        return any(has_redacted(v) for v in data.values())
    if isinstance(data, list):
        return any(has_redacted(v) for v in data)
    return False


_MISSING = object()


def restore(new: Any, old: Any = _MISSING, path: str = "") -> Any:
    """Replace REDACTED placeholders in `new` with the value at the same path in `old`."""
    if new == REDACTED:
        if old is _MISSING:
            raise RedactionError(f"no current value to restore redacted field {path or '/'}")
        return old
    if isinstance(new, dict):
        return {k: restore(v, old.get(k, _MISSING) if isinstance(old, dict) else _MISSING,
                           f"{path}/{k}")
                for k, v in new.items()}
    if isinstance(new, list):
        return [restore(v, old[i] if isinstance(old, list) and i < len(old) else _MISSING,
                        f"{path}[{i}]")
                for i, v in enumerate(new)]
    return new
