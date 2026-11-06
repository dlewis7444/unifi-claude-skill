"""Command-line entry point: global flags, parser assembly, error handling."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .client import APIError, UDMClient
from .commands import MODULES
from .config import ConfigError, Settings, get_api_key, load_dotenv
from .util import UsageError, emit

# Global flags are accepted anywhere on the command line (before or after the command).
FLAGS = {"--json", "--dry-run"}
OPTIONS = {"--host", "--site", "--timeout"}

EPILOG = """\
global flags (accepted anywhere):
  --json            compact JSON output (tables become JSON lists)
  --dry-run         print mutating requests instead of sending them
  --host HOST       controller host       (env UDM_HOST, default unifi.local)
  --site SITE       site name             (env UDM_SITE, default 'default')
  --timeout SEC     HTTP timeout seconds  (env UDM_TIMEOUT, default 30)
"""


def split_globals(argv: list[str]) -> tuple[dict, list[str]]:
    found: dict = {}
    rest: list[str] = []
    it = iter(argv)
    for arg in it:
        name, eq, val = arg.partition("=")
        if arg in FLAGS:
            found[arg[2:].replace("-", "_")] = True
        elif name in OPTIONS:
            if not eq:
                val = next(it, None)
                if val is None:
                    raise UsageError(f"{name} needs a value")
            found[name[2:]] = val
        else:
            rest.append(arg)
    return found, rest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="udm.py", description="UniFi OS (UDM / UCG / UDR) command-line helper",
        epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True, metavar="COMMAND")
    for module in MODULES:
        module.register(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    load_dotenv()
    try:
        flags, rest = split_globals(argv)
        args = build_parser().parse_args(rest)
        settings = Settings.from_env()
        client = UDMClient(
            host=flags.get("host", settings.host),
            api_key=get_api_key(),
            site=flags.get("site", settings.site),
            timeout=float(flags.get("timeout", settings.timeout)),
            dry_run=flags.get("dry_run", False),
        )
        emit(args.func(client, args), flags.get("json", False))
        return 0
    except (ConfigError, UsageError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except APIError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
