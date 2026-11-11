"""Test helpers: a fake controller transport that records requests."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from udmlib.client import UDMClient  # noqa: E402

Route = Callable[[str, str, Any], "tuple[int, Any]"]


class FakeController:
    """Maps (METHOD, path-suffix) to a response. Responses can be a value
    (wrapped in the legacy {meta, data} envelope when `envelope=True`), a
    (status, body) tuple, or a callable(body) -> value."""

    def __init__(self):
        self.routes: dict[tuple[str, str], Any] = {}
        self.calls: list[tuple[str, str, Any]] = []

    def on(self, method: str, suffix: str, response: Any, envelope: bool = True):
        self.routes[(method, suffix)] = (response, envelope)
        return self

    def __call__(self, method, url, headers, data, timeout):
        body = json.loads(data) if data else None
        self.calls.append((method, url, body))
        for (m, suffix), (resp, envelope) in self.routes.items():
            if m == method and url.endswith(suffix):
                if callable(resp):
                    resp = resp(body)
                if isinstance(resp, tuple):
                    status, payload = resp
                    return status, payload if isinstance(payload, str) else json.dumps(payload)
                payload = {"meta": {"rc": "ok"}, "data": resp} if envelope else resp
                return 200, json.dumps(payload)
        return 404, json.dumps({"meta": {"rc": "error", "msg": "api.err.NotFound"}})

    def mutations(self):
        return [c for c in self.calls if c[0] != "GET"]


def make_client(fake: FakeController, **kw) -> UDMClient:
    return UDMClient("udm.test", "key", transport=fake, **kw)
