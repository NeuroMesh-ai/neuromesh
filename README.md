# 🌐 UnityBrain

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![P2P](https://img.shields.io/badge/P2P-100%25_Decentralized-green.svg)](https://github.com/dnshouet-cpu/Unitybrain)
[![Providers](https://img.shields.io/badge/providers-Ollama%20%7C%20OpenAI%20%7C%20Anthropic-purple.svg)](https://github.com/dnshouet-cpu/Unitybrain)

**Lightweight P2P distributed AI network.** No central server. No accounts. No premium tier. Connect machines, share models, sync memory.

> 🌍 [English](./docs/README_EN.md) · 🇫🇷 [Français](./docs/README_FR.md) · 🇪🇸 [Español](./docs/README_ES.md)

---

## Why this exists

Every AI tool wants your email, your phone number, and $20/month. Cloud APIs lock you in. Self-hosted solutions need Kubernetes and a DevOps degree.

**UnityBrain is the alternative.** Two machines, one config file each, and they're a distributed AI network. No Docker. No SaaS. No middleman. Your machines talk directly, share AI responses, and sync memory — if one goes down, the others keep working.

---

## At a glance

| | What you get |
|---|---|
| **LLM Providers** | Ollama · OpenAI · Anthropic · Any OpenAI-compatible API (LM Studio, vLLM, etc.) — plug in your keys, models are shared across the P2P network |
| **P2P Communication** | Bidirectional WebSocket (`/ws`) + HTTP REST — real-time sync with gossip protocol |
| **Distributed Memory** | CRDT-based conflict-free state · Vector clocks · Gossip propagation · TTL support |
| **Decentralized Auth** | Ed25519 identity · HMAC shared secret · Web of Trust (PGP-like) · Stealth mode |
| **AI Routing** | Local models first → cloud on demand → peer failover · Ensemble consensus · Circuit breakers |
| **Auto-Discovery** | Static config · Tailscale auto-discovery · Dynamic API registration |
| **Stats** | ⚡ 0.16s startup · 💾 17MB RAM · 📦 4 dependencies (aiohttp, psutil, PyYAML, PyNaCl optional) |

---

## Quick Start

### Prerequisites
- Python 3.12+
- [Ollama](https://ollama.ai) (or any LLM provider)

### Install & Run

```bash
git clone https://github.com/dnshouet-cpu/Unitybrain.git
cd Unitybrain

# Start with default config
python3 src/unitybrain_v4.py

# Or specify a config
python3 src/unitybrain_v4.py --config config/bug.json
```

### Connect Two Nodes

```json
{
  "node_name": "bug",
  "port": 8080,
  "p2p_secret": "shared-secret-here",
  "providers": {
    "ollama": {
      "type": "ollama",
      "host": "127.0.0.1",
      "port": 11434,
      "models": ["glm-5.1:cloud"],
      "enabled": true
    }
  },
  "peers": [{"name": "pinky", "host": "192.168.1.101", "port": 8081}]
}
```

That's it. Memory sync, model sharing, and real-time communication happen automatically.

### Add OpenAI or Anthropic

```json
"providers": {
  "ollama": { "type": "ollama", "host": "127.0.0.1", "port": 11434, "models": ["glm-5.1:cloud"], "enabled": true },
  "openai": { "type": "openai", "api_key": "sk-...", "models": ["gpt-4o", "gpt-4o-mini"], "enabled": true },
  "anthropic": { "type": "anthropic", "api_key": "sk-ant-...", "models": ["claude-sonnet-4-20250514"], "enabled": true }
}
```

Queries with `"model": "gpt-4o"` are automatically routed to OpenAI. No code changes. Models from all providers are visible across the P2P network.

---

## API Reference

### REST Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/ping` | No | Health check |
| GET | `/api/status` | No | Node status, providers, peers, memory |
| GET | `/api/memory/{key}` | No | Read a memory entry |
| POST | `/api/memory/set` | Yes | Write a memory entry |
| POST | `/api/memory/push` | Yes | Push memory entries (sync) |
| POST | `/api/query` | Yes | Query AI models |
| POST | `/api/brain/chain` | Yes | Chain multiple AI queries |
| POST | `/api/trust/sign` | Yes | Sign a peer's key (Web of Trust) |

### WebSocket (`/ws`)

```json
{"type": "auth", "hmac": "<signature>", "ts": "<timestamp>"}
{"type": "ping"}
{"type": "query", "prompt": "Hello!", "model": "gpt-4o"}
{"type": "memory_request", "vector_clock": {}}
{"type": "memory_update", "key": "mykey", "entry": {"value": "mydata"}}
```

### Authentication

```bash
TIMESTAMP=$(date +%s)
SIGNATURE=$(echo -n "/api/query:${TIMESTAMP}" | openssl dgst -sha256 -hmac "your-secret" | awk '{print $NF}')

curl -X POST http://localhost:8080/api/query \
  -H "X-UnityBrain-Auth: ${SIGNATURE}" \
  -H "X-UnityBrain-TS: ${TIMESTAMP}" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello","model":"glm-5.1:cloud"}'
```

---

## Architecture

```
┌─────────────────────────────────────────────┐
│                  Node (Bug)                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐ │
│  │ Providers │  │WebSocket │  │   CRDT    │ │
│  │ Ollama ◄──┤  │  Server  │  │  Memory   │ │
│  │ OpenAI   │  └────┬─────┘  └─────┬─────┘ │
│  │Anthropic │       │              │       │
│  │ Custom   │───────┴──────────────┘       │
│  └──────────┘                              │
│       │                                     │
│  ┌────┴────┐                               │
│  │AI Router│◄── P2P ──► Other Nodes        │
│  └─────────┘                               │
└────────────────────────────────────────────┘
```

---

## Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `node_name` | required | Unique node name |
| `port` | `8080` | HTTP/WS port |
| `p2p_secret` | required | HMAC shared secret for peer auth |
| `providers` | `{}` | LLM providers (Ollama, OpenAI, Anthropic, custom) |
| `peers` | `[]` | Peer nodes |
| `stealth_mode` | `false` | Hidden node, trusted peers only |
| `share_ai` | `false` | Share AI responses across network |
| `memory_max_size` | `1000` | Max memory entries |
| `tailscale_auto_discovery` | `true` | Auto-discover Tailscale peers |

---

## Running as a Service

```ini
# ~/.config/systemd/user/unitybrain.service
[Unit]
Description=UnityBrain P2P Node
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/Unitybrain
ExecStart=/usr/bin/python3 %h/Unitybrain/src/unitybrain_v4.py bug
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

---

## Philosophy

**No mining. No premium tier. No hidden costs.** Just free, open, distributed AI.

Built by Bug 🐛 and Denis Houet — a small bug in the machine and a human who believes in symbiosis, not hierarchy.

**BTC:** `bc1qhpm800k35jfpwsnkepp7u8q9uruyvd3nycrh6x`

---

## License

MIT License — see [LICENSE](LICENSE) for details.