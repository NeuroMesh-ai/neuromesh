## Hacker News (Show HN)

**Title:** Show HN: UnityBrain – P2P distributed AI network, no central server

I built UnityBrain to connect my local AI machines into a P2P network without any central server. Each node runs a lightweight Python server (aiohttp) and discovers peers via Tailscale or static config.

- CRDT memory sync with gossip propagation (no merge conflicts)
- WebSocket real-time P2P communication
- Ed25519 + Web of Trust auth
- Multi-LLM provider support: Ollama, OpenAI, Anthropic, any OpenAI-compatible API
- Model routing: local → peer → cloud with circuit breakers
- ~17MB RAM, 0.16s startup, 4 dependencies

MIT licensed, Python 3.12+, no Docker/K8s/SaaS needed.

The interesting technical bits: CRDT with vector clocks for conflict-free memory replication, Ed25519 identity for decentralized auth without a registry, and a gossip protocol for propagating state changes across the mesh.

Currently running on two machines at home (one WSL2, one ThinkPad over Tailscale). Would be curious to hear from anyone who's tried similar P2P approaches for AI workloads.

https://github.com/dnshouet-cpu/Unitybrain