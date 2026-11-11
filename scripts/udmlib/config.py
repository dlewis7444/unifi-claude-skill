"""Configuration: .env loading, environment variables and API key lookup."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PASS_PATH = "internal/unifi/api-key"


class ConfigError(Exception):
    """Raised when the tool is not configured well enough to talk to the controller."""


def load_dotenv(path: Path | None = None) -> None:
    """Load KEY=VALUE pairs from .env (project root by default).

    Existing environment variables are never overwritten — real env wins over file.
    """
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def get_api_key() -> str:
    """Return the API key from UNIFI_API_KEY, falling back to `pass`."""
    key = os.environ.get("UNIFI_API_KEY", "").strip()
    if key:
        return key

    pass_path = os.environ.get("UNIFI_PASS_PATH", DEFAULT_PASS_PATH)
    if shutil.which("pass"):
        result = subprocess.run(["pass", pass_path], capture_output=True, text=True)
        secret = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        if result.returncode == 0 and secret:
            return secret

    raise ConfigError(
        "No UniFi API key found. Set UNIFI_API_KEY in "
        f"{PROJECT_ROOT / '.env'} (see .env.example) or store it in "
        f"`pass {pass_path}`. See README.md → 'Generate a UniFi API key'."
    )


@dataclass
class Settings:
    host: str
    site: str
    timeout: float

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            timeout = float(os.environ.get("UDM_TIMEOUT", "30"))
        except ValueError as exc:
            raise ConfigError("UDM_TIMEOUT must be a number of seconds") from exc
        return cls(
            host=os.environ.get("UDM_HOST", "unifi.local"),
            site=os.environ.get("UDM_SITE", "default"),
            timeout=timeout,
        )
