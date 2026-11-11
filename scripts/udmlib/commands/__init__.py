"""Command modules. Each exposes `register(subparsers)`; handlers are
`func(client, args) -> data` set via `set_defaults(func=...)`."""

from . import clients, devices, firewall, guests, logs, network, stats, system

MODULES = (system, clients, devices, network, firewall, logs, stats, guests)
