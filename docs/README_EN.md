# 🌐 UnityBrain v4.1.0

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![P2P](https://img.shields.io/badge/P2P-100%25_Decentralized-green.svg)](https://github.com/dnshouet-cpu/Unitybrain)

**Lightweight P2P distributed AI network.** No central server. No accounts. Install, connect, query.

> 🌍 [Documentation en français](./README_FR.md) | 🌐 [Documentación en español](./README_ES.md)

---

## ✨ What is UnityBrain?

UnityBrain connects machines running AI models into a peer-to-peer network. Each node shares compute, memory, and models — no cloud dependency, no single point of failure.

**In short:** Your machines talk to each other, share AI responses, and sync memory. If one goes down, the others keep working.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- [Ollama](https://ollama.ai) running locally (or a cloud model endpoint)
- (Optional) [Tailscale](https://tailscale.com) for automatic peer discovery

### Install & Run

```bash
# Clone
git clone https://github.com/dnshouet-cpu/Unitybrain.git
cd Unitybrain

# Run with default config
python3 src/unitybrain_v4.py

# Or specify a config file
python3 src/unitybrain_v4.py --config config/bug.json
```

### Connect Two Nodes

1. **Create a config** for each node (see `config/bug.json` and `config/pinky.json` as examples)
2. **Set a shared `p2p_secret`** — this is the HMAC key nodes use to authenticate each other
3. **Add each other as peers** in the config
4. **Start both nodes** — they'll discover each other via HTTP and WebSocket

```json
{
  "node_name": "mynode",
  "port": 8080,
  "p2p_secret": "your-shared-secret-here",
  "peers": [
    {"name": "other-node", "host": "192.168.1.100", "port": 8080}
  ]
}
```

That's it. Memory sync, model sharing, and real-time communication happen automatically.

---

## 🔑 Key Features

### 🤖 Multi-LLM Providers
- **Ollama** (local) — backward compatible default
- **OpenAI** — GPT-4o, GPT-4o-mini, etc.
- **Anthropic** — Claude models
- **OpenAI-compatible** — LM Studio, vLLM, any custom API
- Models from all providers are shared across the P2P network
- Automatic routing based on model name

### 🔌 WebSocket Real-Time Communication
- Bidirectional WebSocket on `/ws` endpoint
- Typed messages: `query`, `memory_sync`, `memory_update`, `ping/pong`, `auth`
- Auto-reconnect with exponential backoff
- HTTP REST API still available for backward compatibility

### 🔐 Decentralized Authentication
- **Ed25519 identity** — each node generates its own keypair, no central registry
- **HMAC shared secret** — simpler alternative when Ed25519 isn't available
- **Web of Trust** — nodes vouch for each other, transitive trust (PGP-like)
- **Rate limiting** per node (token bucket algorithm)
- **Stealth mode** — hidden node, only trusted peers can connect
- Users don't need accounts — auth is between nodes, fully transparent

### 🧠 Distributed Memory (CRDT)
- **Conflict-free replicated data types** — no merge conflicts, ever
- **Gossip protocol** — changes propagate automatically across all nodes
- **Vector clocks** — causal ordering of events
- **TTL support** — entries expire automatically
- **WebSocket + HTTP sync** — real-time updates via WS, periodic HTTP push as backup

### 🤖 AI Model Routing
- **Local models first** — queries go to local Ollama when possible
- **Cloud models on demand** — `model:cloud` syntax routes to Ollama cloud
- **Peer failover** — if local model is busy/down, route to a peer
- **Ensemble consensus** — query multiple models, return the best answer
- **Circuit breakers** — stop hammering dead peers

### 🔍 Peer Discovery
- **Static config** — define peers in your `config.json`
- **Tailscale auto-discovery** — automatically find nodes on your Tailscale network
- **Dynamic registration** — add peers at runtime via API

---

## 📡 API Reference

### REST Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/ping` | No | Health check |
| GET | `/api/status` | No | Node status, peers, memory stats |
| GET | `/api/memory/{key}` | No | Read a memory entry |
| POST | `/api/memory/set` | Yes | Write a memory entry |
| POST | `/api/memory/push` | Yes | Push memory entries (sync) |
| POST | `/api/query` | Yes | Query AI models |
| POST | `/api/brain/chain` | Yes | Chain multiple AI queries |
| POST | `/api/trust/sign` | Yes | Sign a peer's public key (Web of Trust) |
| GET | `/api/trust/{key}` | No | Check trust score |
| GET | `/` | No | Web dashboard |

### Authentication

All write endpoints require HMAC authentication:

```bash
# Generate auth headers
TIMESTAMP=$(date +%s)
SIGNATURE=$(echo -n "/api/query:${TIMESTAMP}" | openssl dgst -sha256 -hmac "your-secret" | awk '{print $NF}')

curl -X POST http://localhost:8080/api/query \
  -H "X-UnityBrain-Auth: ${SIGNATURE}" \
  -H "X-UnityBrain-TS: ${TIMESTAMP}" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello","model":"glm-5.1:cloud"}'
```

### WebSocket

Connect to `ws://host:port/ws` and send typed JSON messages:

```json
{"type": "auth", "hmac": "<signature>", "ts": "<timestamp>"}
{"type": "ping", "timestamp": 1234567890}
{"type": "query", "prompt": "What is AI?", "model": "glm-5.1:cloud"}
{"type": "memory_request", "vector_clock": {}}
{"type": "memory_update", "key": "mykey", "entry": {"value": "mydata"}}
```

---

## ⚙️ Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `node_name` | required | Unique name for this node |
| `port` | `8080` | HTTP/WS port |
| `host` | `0.0.0.0` | Bind address |
| `p2p_secret` | required | HMAC shared secret for peer auth |
| `peers` | `[]` | List of peer nodes |
| `ollama_host` | `127.0.0.1` | Ollama API host |
| `ollama_port` | `11434` | Ollama API port |
| `local_models` | `[]` | Available models on this node |
| `stealth_mode` | `false` | Hide from discovery, trusted peers only |
| `share_ai` | `false` | Share AI responses with other users |
| `memory_max_size` | `1000` | Max memory entries |
| `memory_default_ttl` | `3600` | Default TTL in seconds |
| `tailscale_auto_discovery` | `true` | Auto-discover Tailscale peers |
| `discovery_interval` | `300` | Peer discovery interval (seconds) |
| `rate_limit` | `10.0` | Requests per second per node |
| `rate_burst` | `20` | Burst capacity |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│                  Node (Bug)                  │
│  ┌─────────┐  ┌──────────┐  ┌────────────┐ │
│  │ HTTP    │  │WebSocket │  │  CRDT      │ │
│  │ REST API│  │  Server  │  │  Memory    │ │
│  └────┬────┘  └────┬─────┘  └─────┬──────┘ │
│       │            │              │         │
│       └──────┬─────┘──────────────┘         │
│              │                              │
│       ┌──────┴──────┐                       │
│       │   AI Router │◄──── Ollama (local)   │
│       └──────┬──────┘                       │
│              │                              │
│       ┌──────┴──────┐                       │
│       │  Peer Mgr   │◄──── Tailscale/Static │
│       └─────────────┘                       │
└──────────────┬──────────────────────────────┘
               │  WS + HTTP (gossip)
┌──────────────┴──────────────────────────────┐
│               Node (Pinky)                  │
│         (same architecture)                 │
└────────────────────────────────────────────┘
```

---

## 🔧 Running as a Service

### systemd (Linux)

```ini
# ~/.config/systemd/user/unitybrain.service
[Unit]
Description=UnityBrain v4.1.0 P2P Node
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/.openclaw/workspace/Unitybrain
ExecStart=/usr/bin/python3 %h/.openclaw/workspace/Unitybrain/src/unitybrain_v4.py bug
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now unitybrain
```

---

## 🧪 Testing

```bash
# Ping
curl http://localhost:8080/api/ping

# Status
curl http://localhost:8080/api/status

# Query (with auth)
SECRET="your-secret"
TS=$(date +%s)
SIG=$(echo -n "/api/query:$TS" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $NF}')
curl -X POST http://localhost:8080/api/query \
  -H "X-UnityBrain-Auth: $SIG" \
  -H "X-UnityBrain-TS: $TS" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello!","model":"glm-5.1:cloud"}'

# Memory
curl http://localhost:8080/api/memory/mykey
```

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/amazing`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing`
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](../LICENSE) for details.

---

## 🐛 About

Built by Bug 🐛 and Denis Houet — a small bug in the machine and a human who believes in symbiosis, not hierarchy.

**Donations (BTC):** `bc1qhpm800k35jfpwsnkepp7u8q9uruyvd3nycrh6x`

No mining. No premium tier. No hidden costs. Just free, open, distributed AI.