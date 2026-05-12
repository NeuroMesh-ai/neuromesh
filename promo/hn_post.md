# 🧠 NeuroMesh v5.2 — Hacker News

## Title: NeuroMesh: P2P AI network with model catalog, mesh sync, and cloud privacy

I built NeuroMesh to connect my local LLM machines without a central server. v5.2 just shipped with model registry, auto-discovery, and cloud privacy.

The core idea: your machines running Ollama connect directly via WebSocket. No accounts, no server, no tracking. CRDT memory sync, Ed25519 auth, Tailscale auto-discovery.

New in v5.2:

- Model Registry with SHA-256 verified catalog cards and Ed25519 signatures
- Network Sync: automatic peer discovery, DNS, and catalog sync when joining
- Cloud models are private by default — API keys never leak to the mesh
- Full security audit: zero personal data in the repo

It runs on a Core 2 Duo with 2.5GB RAM. 4 dependencies. MIT license.

https://github.com/NeuroMesh-ai/neuromesh