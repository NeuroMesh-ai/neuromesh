# NeuroMesh v4.0.1 — Reddit / HackerNews post

## Title: NeuroMesh — A lightweight P2P distributed AI network (no server, no accounts, no premium)

I've been building NeuroMesh, a peer-to-peer network for distributed AI. No central server, no user accounts, no premium tier. Just machines talking to each other, sharing AI models and memory.

### What it does:

- Connects machines running Ollama into a P2P network
- Syncs memory across nodes using CRDTs (conflict-free)
- Routes AI queries to local models first, falls back to peers
- WebSocket real-time communication between nodes
- Ed25519 identity + Web of Trust for decentralized auth
- Tailscale auto-discovery for zero-config networking
- Stealth mode for hidden nodes

### How it works:

Each node runs a Python server (aiohttp) with HTTP REST + WebSocket endpoints. Nodes discover each other via static config or Tailscale, authenticate with HMAC/Ed25519, and start syncing. Memory uses CRDTs with vector clocks and gossip propagation — no merge conflicts, ever.

### Stats:

- Startup: ~0.16s
- RAM: ~17MB idle
- Dependencies: aiohttp, psutil, PyYAML (PyNaCl optional)
- Python 3.12+

### Two-node setup:

```json
{"node_name": "bug", "port": 8080, "p2p_secret": "shared-secret",
 "peers": [{"name": "pinky", "host": "192.168.1.101", "port": 8081}]}
```

That's it. No Docker, no Kubernetes, no SaaS. Just Python and a config file.

### Why?

I'm tired of AI tools that require cloud accounts, phone numbers, and subscription tiers. NeuroMesh is my answer: take your machines, connect them, share AI. No middleman. The code is MIT licensed.

The project started as a weekend experiment and grew into something I actually use daily — my two machines (Bug and Pinky) sync their AI memory and share model queries across the network.

Repository: https://github.com/NeuroMesh-ai/neuromesh

Feedback welcome! Particularly interested in:
- Use cases beyond "two machines on a home network"
- Security review of the auth model
- Ideas for the gossip protocol (currently basic, could be much smarter)

BTC: `bc1qhpm800k35jfpwsnkepp7u8q9uruyvd3nycrh6x`