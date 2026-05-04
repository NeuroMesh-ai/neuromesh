## r/selfhosted

**Title:** UnityBrain — self-hosted P2P AI network, no server needed

Hey folks,

I've been working on something that might interest this community. I run Ollama on two machines at home and wanted them to share AI responses and sync memory without relying on any cloud service. So I built UnityBrain.

It's a lightweight Python P2P network — each node runs an aiohttp server with HTTP REST + WebSocket endpoints. You configure a shared secret for auth, point nodes at each other, and they start syncing CRDT memory and sharing model queries over WebSocket.

What it looks like in practice:
- I set a memory key on my desktop, it appears on my laptop ~30 seconds later
- If my local Ollama is busy, the query falls back to the other node
- I can also route queries to OpenAI or Anthropic (BYOK) and those responses get shared too

Key technical details:
- Ed25519 identity + Web of Trust for auth (HMAC fallback if PyNaCl isn't available)
- CRDT memory with vector clocks and gossip propagation — no merge conflicts
- Circuit breakers for dead peers
- Tailscale auto-discovery (or static config)
- Stealth mode (hidden node, trusted peers only)
- ~17MB RAM, starts in 0.16s, 4 dependencies

It's MIT licensed, Python 3.12+, and works with Ollama, OpenAI, Anthropic, or any OpenAI-compatible API.

Two machines is the simplest setup, but it's not a limit — it's P2P, so more nodes make the network stronger.

Repo: https://github.com/dnshouet-cpu/Unitybrain

Happy to answer questions or take feedback on the auth model / gossip protocol.

---

## r/LocalLLaMA

**Title:** UnityBrain — P2P network for sharing local LLM queries (with BYOK for cloud models)

I've been building a way for my local LLM machines to share queries and sync memory without a central server. It's called UnityBrain and it's now at v4.1.

The idea: you have machines running Ollama (or any LLM provider), and instead of each one being isolated, they form a P2P network. Memory syncs via CRDT with gossip propagation, queries can fall back to peers if your local model is busy, and you can also route to OpenAI/Anthropic/custom APIs — the responses get shared across the network.

Technical details:
- WebSocket for real-time P2P sync
- CRDT memory (no merge conflicts, ever)
- Ed25519 + HMAC + Web of Trust auth
- Multi-provider: Ollama, OpenAI, Anthropic, any OpenAI-compatible API
- Model routing: local → peer → cloud, with circuit breakers
- ~17MB RAM, Python 3.12+

Config example:
```json
{
  "node_name": "mynode",
  "port": 8080,
  "providers": {
    "ollama": {"type": "ollama", "host": "127.0.0.1", "port": 11434, "models": ["llama3.1:8b"]},
    "openai": {"type": "openai", "api_key": "sk-...", "models": ["gpt-4o-mini"]}
  },
  "peers": [{"name": "other", "host": "192.168.1.100", "port": 8081}]
}
```

I'm particularly interested in feedback on:
- The ensemble consensus approach (querying multiple models and picking the best response)
- Whether anyone has use cases beyond home networks (e.g., community mesh, small orgs)
- The gossip protocol — currently basic, room for smarter propagation

MIT licensed, no mining, no premium, no hidden costs.

Repo: https://github.com/dnshouet-cpu/Unitybrain