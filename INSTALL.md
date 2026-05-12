# Installing UnityBrain

## Quick Install

```bash
git clone https://github.com/unitybrain-ai/unitybrain.git
cd Unitybrain
python3 setup.py --auto
```

## Requirements

- **Python 3.8+**
- **Ollama** — [ollama.com](https://ollama.com) (for local AI models)
- **Tailscale** — [tailscale.com](https://tailscale.com) (optional, for P2P over internet)

## Install Options

### Interactive
```bash
python3 setup.py
```
Asks for node name, sharing preferences, P2P secret.

### Automatic
```bash
python3 setup.py --auto
```
Uses defaults: node name = hostname, share_ai = true, auto-generated secret.

### Check existing install
```bash
python3 setup.py --check
```

## After Install

```bash
# Start the server
unitybrain start

# Or as a systemd service
systemctl --user daemon-reload
systemctl --user enable --now unitybrain

# Use the interactive CLI
unitybrain
```

## Connect Multiple Machines

1. Install UnityBrain on each machine
2. Set the **same `p2p_secret`** in all configs
3. They discover each other automatically (via Tailscale or local network)

```json
// ~/.unitybrain/config/mynode.json
{
  "p2p_secret": "your-shared-secret-here",
  "share_ai": true
}
```

**More nodes = more power.** Each node shares its CPU, RAM, and models with the network.

## Configuration

Config files live in `~/.unitybrain/config/<node_name>.json`.

| Key | Default | Description |
|-----|---------|-------------|
| `share_ai` | `true` | Share your models/CPU/RAM with the network |
| `stealth_mode` | `false` | Hide from peer discovery |
| `port` | `8080` | HTTP API port |
| `p2p_secret` | auto | Shared secret for network auth |
| `local_models` | auto | Models served by this node |
| `tailscale_auto_discovery` | `true` | Find peers via Tailscale |

## Uninstall

```bash
rm -rf ~/.unitybrain
rm ~/.local/bin/unitybrain
rm ~/.config/systemd/user/unitybrain.service
systemctl --user daemon-reload
```