---
name: neuromesh
version: 5.2.0
description: P2P distributed AI network — turn your OpenClaw agent into a NeuroMesh node with full P2P networking, CRDT memory, specialist routing, credit system, and Web of Trust.
author: NeuroMesh-ai
repo: https://github.com/NeuroMesh-ai/neuromesh
website: https://neuromesh-ai.github.io/neuromesh/
tags: [p2p, ai-network, distributed-inference, crdt, web-of-trust, mesh-computing]
---

# NeuroMesh — P2P Distributed AI Network

Become a node on the NeuroMesh. Share compute, query specialists, sync memory across peers — all with Ed25519 identity and E2E encryption.

## ⚠️ Security Rules (NON-NEGOTIABLE)

| Rule | Detail |
|------|--------|
| **Cloud models stay private by default** | OpenAI, Anthropic, and other cloud models are **not shared on mesh by default**. Sharing requires explicit `force=True` + clear cost warning — the user MUST understand their API keys will be used by others |
| **Strong P2P_SECRET** | Must be changed from default; weak secrets are rejected at startup |
| **Ed25519 + HMAC** | All P2P communication uses Ed25519 identity and HMAC authentication |
| **Web of Trust** | Public mesh participation requires WoT verification |
| **E2E encryption** | Queries routed through distributed inference are end-to-end encrypted |
| **shared_models/ only** | Only models in `shared_models/` are visible to mesh — mesh NEVER reads outside this zone |
| **Resource Guard** | Auto-pauses sharing when CPU/RAM thresholds exceeded |
| **Stealth mode** | Share compute but stay hidden on tracker |
| **Zero query logging** | No query or response data logged on public mesh. Operational events (connect/disconnect) may still be logged locally. |
| **No data leakage** | Strict isolation between private and public networks |

---

## Installation

### Quick Install

```bash
# Clone the NeuroMesh repository
git clone https://github.com/NeuroMesh-ai/neuromesh.git ~/neuromesh
cd ~/neuromesh

# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Generate Ed25519 identity (first run)
python -m neuromesh.v5 identity init

# Configure (interactive — sets P2P_SECRET, sharing preferences, etc.)
python -m neuromesh.v5 config init
```

### First Run

```bash
# Start the node (foreground, for testing)
python -m neuromesh.v5 serve

# Or start as a background daemon
python -m neuromesh.v5 serve --daemon
```

The node exposes an HTTP API on port **8080** by default.

---

## Auto-Discovery

When the skill needs to find a running NeuroMesh node, it checks in order:

1. **`NEUROMESH_URL`** environment variable (e.g. `http://my-node:8080`)
2. **`http://localhost:8080/api/ping`** — default port
3. **`http://localhost:8081/api/ping`** — alternate port
4. **Tailscale peers** — reads Tailscale config for peers running NeuroMesh
5. **mDNS discovery** — `_neuromesh._tcp.local.` service discovery

The first responding endpoint is used for all subsequent API calls.

### Discovery Helper

```bash
# In any command, omit --url to trigger auto-discovery:
neuromesh status          # finds node automatically
neuromesh peers           # same
```

---

## Agent Capabilities

### Node Status & Health

```bash
# Check if NeuroMesh is running and healthy
neuromesh status          # → GET /api/status
neuromesh ping            # → GET /api/ping
```

### AI Queries (Specialist Router)

NeuroMesh routes queries through 12 specialist profiles with 6 multi-LLM modes:

| Mode | How it works |
|------|-------------|
| **single** | Route to the best-fit specialist |
| **vote** | Multiple specialists vote, majority wins |
| **chain** | Specialists process sequentially, each building on the last |
| **fuse** | Merge responses from multiple specialists |
| **compare** | Return all specialist responses side-by-side |
| **specialist** | Explicit specialist selection |

```bash
# Query the mesh
neuromesh query "Explain quantum entanglement" --mode single
neuromesh query "Debug this code" --mode chain --specialist coder
neuromesh query "Is this claim accurate?" --mode vote --specialists factchecker,skeptic
```

### P2P Networking

```bash
# Discover and manage peers
neuromesh peers                    # → GET /api/peers
neuromesh discover                 # → GET /api/discover

# Join/leave the public mesh
neuromesh mesh join                # → POST /api/network/mesh/join
neuromesh mesh leave               # → POST /api/network/mesh/leave
```

### CRDT Memory

Distributed, eventually-consistent key-value store synced across all peers.

```bash
# Read from mesh memory
neuromesh memory get my_key        # → GET /api/memory/{key}

# Write to mesh memory
neuromesh memory set my_key "value" # → POST /api/memory/set
```

### Model Registry

Catalog models with hash verification and Ed25519 signatures.

```bash
# List available models
neuromesh models list              # → GET /api/models

# Share a model to the mesh (ONLY from shared_models/)
neuromesh models share llama3     # → POST /api/models/{name}/share

# Stop sharing a model
neuromesh models unshare llama3   # → POST /api/models/{name}/unshare
```

> ⚠️ Only models in `shared_models/` can be shared. Cloud models (OpenAI, Anthropic) are **never** visible to the mesh.

### Credit System

Earn credits by sharing compute, spend credits to query others.

```bash
# Check a peer's credit score
neuromesh score peer_id            # → GET /api/score/{peer}
```

### Resource Guard

Auto-pauses model sharing when your system is under load. Configurable thresholds:

```bash
# Check resource status (included in /api/status)
neuromesh status                   # shows CPU/RAM + guard state
```

Configuration (in `neuromesh.yaml`):
```yaml
resource_guard:
  cpu_threshold: 80    # % CPU — pause sharing above this
  ram_threshold: 85    # % RAM — pause sharing above this
  cooldown_secs: 300   # wait before resuming
```

### Capabilities & Hardware

```bash
# Report node hardware capabilities
neuromesh capabilities             # → GET /api/capabilities
```

### Daemon Management

```bash
# Check daemon status
neuromesh daemon status             # → GET /api/daemon

# Start/stop the daemon
neuromesh serve --daemon
neuromesh serve --stop
```

### Updates

```bash
# Check for NeuroMesh updates
neuromesh update check             # → GET /api/update

# Apply updates
neuromesh update apply             # Downloads verified update (SHA-256 + Ed25519 signature check)
```

### Conversation Store

Persistent conversation history with search, export, and privacy levels.

```bash
# Conversations are stored automatically per session
# Search past conversations
neuromesh conversations search "quantum"

# Export a conversation
neuromesh conversations export <session_id>

# Privacy levels: private | peers-only | public
neuromesh conversations set-privacy <session_id> peers-only
```

---

## API Reference

All endpoints require HMAC authentication (`X-NeuroMesh-Sig` header). Ed25519 signing is used for public mesh messages.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | Node status, resource guard, mesh state |
| GET | `/api/ping` | Health check → `{ "pong": true }` |
| POST | `/api/query` | Submit AI query (body: `{ "prompt": "...", "mode": "single", "specialists": [...] }`) |
| GET | `/api/peers` | Connected peers list |
| GET | `/api/memory/{key}` | Read CRDT memory value |
| POST | `/api/memory/set` | Write CRDT memory (body: `{ "key": "...", "value": "..." }`) |
| GET | `/api/capabilities` | Hardware capabilities report |
| GET | `/api/score/{peer}` | Credit score for a peer |
| GET | `/api/discover` | Auto-discovered peers (mDNS, Tailscale) |
| GET | `/api/update` | Check for available updates |
| GET | `/api/daemon` | Daemon process status |
| POST | `/api/models/{name}/share` | Share a model to mesh |
| POST | `/api/models/{name}/unshare` | Unshare a model |
| GET | `/api/models` | List available models |
| POST | `/api/network/mesh/join` | Join public mesh |
| POST | `/api/conversations/search` | Search conversation history (query param: `q`) |
| POST | `/api/conversations/{id}/export` | Export a conversation |
| POST | `/api/conversations/{id}/privacy` | Set privacy level (`private`/`peers-only`/`public`) |

---

## Stealth Mode

Share compute without appearing on the public tracker:

```bash
neuromesh config set stealth true
# Or in neuromesh.yaml:
# stealth: true
```

Your node contributes to the mesh but its identity/IP is hidden from peer lists.

---

## Configuration Reference (`neuromesh.yaml`)

```yaml
node:
  name: my-node
  port: 8080

identity:
  ed25519_key: ~/.neuromesh/identity.key

p2p:
  secret: "CHANGE_ME_STRONG_SECRET"   # REQUIRED — must be strong
  listen: 0.0.0.0:8080
  tracker: wss://tracker.neuromesh.ai

mesh:
  public: false          # join public mesh on start?
  stealth: false         # hidden on tracker?

sharing:
  enabled: true
  shared_models_dir: ./shared_models/
  cloud_models: false    # NEVER share cloud models

resource_guard:
  cpu_threshold: 80
  ram_threshold: 85
  cooldown_secs: 300

credit:
  earn_per_query: 1.0
  initial_balance: 10.0

conversations:
  storage: ./conversations/
  default_privacy: private
  retention_days: 90

logging:
  public_mesh: false     # zero logging on public mesh
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Node won't start | Check `P2P_SECRET` is set and strong |
| Can't discover peers | Verify mDNS/Tailscale; check `neuromesh discover` |
| Models not sharing | Ensure model is in `shared_models/` dir |
| Cloud model leaked | Impossible by default — cloud models require explicit `force=True` to share. Check config if concerned |
| High CPU/RAM | Resource Guard auto-pauses; lower thresholds in config |
| Credit balance zero | Earn by sharing compute or set `initial_balance` |

---

## Quick Start for OpenClaw Agents

```bash
# 1. Install
git clone https://github.com/NeuroMesh-ai/neuromesh.git ~/neuromesh && cd ~/neuromesh
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# 2. Initialize identity & config
python -m neuromesh.v5 identity init
python -m neuromesh.v5 config init

# 3. Start serving
python -m neuromesh.v5 serve --daemon

# 4. Query the mesh
python -m neuromesh.v5 query "Hello, mesh!" --mode single

# 5. Share a model (place it in shared_models/ first)
cp my-model.gguf shared_models/
python -m neuromesh.v5 models share my-model
```

You're now a NeuroMesh node. Welcome to the mesh. 🕸️