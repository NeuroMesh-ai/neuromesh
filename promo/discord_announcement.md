# UnityBrain v4.0.1 — Discord announcement template

## For AI/self-hosting/P2P Discord servers:

---

Hey everyone! 👋

Just released **UnityBrain v4.0.1** — a lightweight P2P distributed AI network.

**What:** Connect your machines running Ollama into a peer-to-peer network. Share compute, sync memory, route AI queries across nodes.

**Why:** No central server. No accounts. No premium tier. No mining. Your machines talk directly.

**How it works:**
- WebSocket real-time sync between nodes
- CRDT-based distributed memory (no merge conflicts)
- Ed25519 + HMAC decentralized auth with Web of Trust
- Auto-discovery via Tailscale
- Local AI models first, cloud on demand, peer failover

**Quick start:**
```bash
git clone https://github.com/dnshouet-cpu/Unitybrain.git
python3 src/unitybrain_v4.py --config mynode.json
```

0.16s startup, 17MB RAM, 4 dependencies. MIT license.

⭐ https://github.com/dnshouet-cpu/Unitybrain

Built with ❤️ by Bug 🐛 and Denis Houet