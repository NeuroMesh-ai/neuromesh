# 🌐 UnityBrain v4.0

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![P2P](https://img.shields.io/badge/P2P-100%25_Decentralized-green.svg)](https://github.com/dnshouet-cpu/Unitybrain)

**Lightweight P2P distributed AI network.** No central server. No accounts. Install, connect, query.

---

## ✨ v4.0 Features

### 🔌 WebSocket Temps Réel
- Bidirectional WebSocket communication (`/ws`)
- Typed messages: `query`, `memory_sync`, `memory_update`, `notification`, `peer_discovery`, `status`
- Auto-reconnect, WS heartbeat (ping/pong)
- HTTP REST API still available (retrocompatible)

### 🔐 Auth Renforcée (Decentralized)
- **Ed25519 identity** — each node generates its own keypair, no registry
- **Challenge-response** between nodes (nonce + timestamp, anti-replay)
- **Web of Trust** — nodes vouch for each other, transitive trust (PGP-like)
- **Rate limiting** per node (token bucket)
- **Stealth mode** — hidden node, no discovery broadcast, only trusted peers connect
- Users don't need accounts — auth is between nodes, transparent

### 🧠 Mémoire Sync P2P
- **CRDT-based** conflict-free replicated memory
- **Gossip protocol** for propagation
- **Vector clocks** for event ordering
- **Last-write-wins** with metadata (author, timestamp, node_id)
- API: `/api/memory/sync`, `/api/memory/push`, `/api/memory/pull`
- Share AI models: `share_ai: true` in config

### 🧹 Clean Architecture
- Lightweight — minimal dependencies (aiohttp, psutil, PyNaCl optional)
- Fast startup, low memory
- brain_llm stays async, non-blocking, cloud models on demand
- No heavy frameworks, no bloat

---

## 📦 Installation

### Prérequis
- Python 3.12+
- Ollama (https://ollama.ai)

### Install

```bash
git clone https://github.com/dnshouet-cpu/Unitybrain.git
cd Unitybrain
pip install -r requirements.txt
```

### Quick Start

```bash
# Start a node
python -m src.unitybrain_v4 bug

# Or with custom config
python -m src.unitybrain_v4 mynode
```

### Config

Edit `config/<node_name>.json`:

```json
{
  "node_name": "bug",
  "host": "0.0.0.0",
  "port": 8080,
  "ollama_host": "127.0.0.1",
  "ollama_port": 11434,
  "local_models": ["glm-5.1:cloud"],
  "stealth_mode": false,
  "share_ai": false,
  "peers": [
    {"name": "Pinky", "host": "100.79.20.105", "port": 8081, "models": ["glm-5.1:cloud"]}
  ]
}
```

---

## 🔌 API Reference

### HTTP REST (retrocompatible)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ping` | Health check |
| GET | `/api/status` | Node status |
| POST | `/api/query` | Query an AI model |
| POST | `/api/memory/set` | Set a memory key |
| GET | `/api/memory/{key}` | Get a memory key |
| POST | `/api/memory/sync` | Full memory sync push |
| POST | `/api/memory/push` | Push entries (CRDT merge) |
| POST | `/api/memory/pull` | Pull delta since vector clock |
| GET | `/api/peers` | List known peers |
| GET | `/api/monitor` | System metrics |
| POST | `/api/trust/sign` | Vouch for a node's public key |
| GET | `/api/trust/score/{key}` | Get trust score |

### WebSocket (`/ws`)

```json
{"type": "auth", "response": "<signature>", "from_key": "<public_key>"}
{"type": "ping"}
{"type": "query", "prompt": "Hello", "model": "glm-5.1:cloud"}
{"type": "memory_sync", "entries": {...}}
{"type": "memory_request", "vector_clock": {...}}
{"type": "notification", "message": "New model available"}
{"type": "peer_discovery", "peer": {"name": "...", "host": "...", "port": 8081}}
{"type": "status"}
```

---

## 🔐 Security

See [docs/AUTH_DESIGN.md](docs/AUTH_DESIGN.md) for the full auth design.

**Key points:**
- Node identity = Ed25519 public key (self-generated)
- Challenge-response auth between nodes (anti-replay)
- Web of Trust for decentralized trust propagation
- Stealth mode for nodes exposed to the internet
- Users don't authenticate — auth is transparent between nodes

---

## 🧠 brain_llm

The brain_llm engine coordinates distributed LLM reasoning:
- Model routing (local → cloud → P2P fallback)
- Ensemble consensus (multi-model agreement)
- Chain of reasoning (task decomposition)
- Context from distributed memory

brain_llm is **async and non-blocking**. Cloud models are loaded on demand only. It never feels heavy.

---

## 💰 Support UnityBrain

See [DONATIONS.md](DONATIONS.md) — voluntary BTC donations, clean sponsorship. No premium tiers, no feature gates. The project stays 100% free and open.

---

## 📄 License

MIT License — see [LICENSE](LICENSE)