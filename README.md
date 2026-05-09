# UniFi Claude Code Skill

A [Claude Code](https://claude.ai/claude-code) skill for managing a UniFi Dream Machine Pro (or any UniFi OS controller) via its local API. Once installed, Claude can query clients, manage firewall rules, toggle port forwards, inspect devices, and more — just by asking.

## Requirements

- Python 3.10+
- A UniFi OS controller with API key support (UDM Pro, UDM SE, CloudGateway, etc.)
- [Claude Code](https://claude.ai/claude-code) with superpowers skills support

## Installation

### 1. Copy the skill into place

```bash
cp -r . ~/.claude/skills/unifi
```

Claude Code picks up skills from `~/.claude/skills/` automatically.

### 2. Generate a UniFi API key

In the UniFi OS web UI:

1. Go to **Settings → Admins & Users → API Keys**
2. Click **Create API Key**
3. Give it a name (e.g. `claude`) and copy the key

### 3. Configure host and API key (`.env`)

Copy the example file and fill in your values:

```bash
cp .env.example .env
$EDITOR .env
```

`.env` is gitignored. The script auto-loads it at startup. Supported keys:

| Key             | Purpose                                                              |
| --------------- | -------------------------------------------------------------------- |
| `UDM_HOST`      | UniFi controller hostname or IP (default: `unifi.local`)             |
| `UNIFI_API_KEY` | API key. Optional — falls back to `pass network/unifi/api-key` if unset |

Real environment variables always take precedence over the `.env` file, and a
runtime `--host` flag wins over both:

```bash
python udm.py --host 192.168.1.1 status
```

**API key alternatives.** Instead of `UNIFI_API_KEY` in `.env`, you can store it in
[`pass`](https://www.passwordstore.org/) under `network/unifi/api-key` (the script
will fetch it automatically), or export `UNIFI_API_KEY` in your shell profile.

## Usage

Once installed, just talk to Claude:

- "Who's connected to the network?"
- "Block the device with MAC aa:bb:cc:dd:ee:ff"
- "Show me all firewall rules"
- "Add a port forward — external 8080 to 192.168.1.50:80"
- "What's my WAN traffic for the last 24 hours?"
- "Restart the AP in the garage"

Claude will invoke the skill automatically when your request involves the network.

You can also run the helper script directly:

```bash
python ~/.claude/skills/unifi/scripts/udm.py status
python ~/.claude/skills/unifi/scripts/udm.py clients
python ~/.claude/skills/unifi/scripts/udm.py --help
```

## Structure

```
SKILL.md          # Skill definition read by Claude Code
scripts/
  udm.py          # Python CLI helper for the UniFi API
.env.example      # Template — copy to `.env` and fill in
LICENSE
README.md
```

## License

MIT — see [LICENSE](LICENSE).
