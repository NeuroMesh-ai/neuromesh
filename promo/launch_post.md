# 🌐 UnityBrain v4.0.1 — P2P Distributed AI Network

**No central server. No accounts. No premium tier. Just free, open, distributed AI.**

## What is it?

UnityBrain connects machines running AI models into a peer-to-peer network. Each node shares compute, memory, and models — if one goes down, the others keep working.

## Key features

- 🔌 **WebSocket real-time sync** — bidirectional P2P communication
- 🔐 **Decentralized auth** — Ed25519 identity + HMAC + Web of Trust
- 🧠 **CRDT memory** — conflict-free distributed state with gossip protocol
- 🤖 **AI model routing** — local models first, cloud on demand, peer failover
- 🔍 **Auto-discovery** — Tailscale + static config + dynamic registration
- 🕵️ **Stealth mode** — hidden nodes, trusted peers only

## Quick start

```bash
git clone https://github.com/unitybrain-ai/unitybrain.git
cd Unitybrain
python3 src/unitybrain_v4.py --config config/bug.json
```

## Two nodes, one command each

```json
// bug.json
{"node_name": "bug", "port": 8080, "p2p_secret": "shared-secret", "peers": [{"name": "pinky", "host": "192.168.1.101", "port": 8081}]}
```

That's it. Memory sync, model sharing, and real-time communication happen automatically.

## Stats

- 🚀 Startup: ~0.16s
- 💾 RAM: ~17MB idle
- 📦 Dependencies: aiohttp, psutil, PyYAML (PyNaCl optional for Ed25519)
- 🐍 Python 3.12+

## Philosophy

No mining. No premium. No hidden costs. Built by Bug 🐛 and Denis Houet — a small bug in the machine and a human who believes in symbiosis, not hierarchy.

**BTC donations:** `bc1qhpm800k35jfpwsnkepp7u8q9uruyvd3nycrh6x`

⭐ Star the repo: https://github.com/unitybrain-ai/unitybrain