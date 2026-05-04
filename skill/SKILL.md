---
name: unitybrain
description: "UnityBrain P2P distributed AI network — deploy, query, and manage peer-to-peer AI nodes with WebSocket sync, CRDT memory, and decentralized auth."
metadata:
  openclaw:
    requires:
      bins: [python3]
      env:
        - UNITYBRAIN_CONFIG
    install:
      - id: git-clone
        kind: shell
        cmd: "git clone https://github.com/dnshouet-cpu/Unitybrain.git ${UNITYBRAIN_PATH:-$HOME/Unitybrain}"
---

# UnityBrain Skill

Deploy and manage UnityBrain P2P AI nodes.

## What it does

- Start/stop UnityBrain nodes
- Query AI models through the P2P network
- Read/write distributed CRDT memory
- Check node status and peer connections
- Push memory sync between nodes

## Setup

1. Clone the repo: `git clone https://github.com/dnshouet-cpu/Unitybrain.git`
2. Configure your node: edit `config/your_node.json`
3. Set `UNITYBRAIN_CONFIG` env var to your config path (or use `--config` flag)

## Usage

Ask Bug to:
- "Start UnityBrain with my config"
- "Query the P2P network for [question]"
- "Check UnityBrain status"
- "Sync memory between Bug and Pinky"
- "Set memory key X to value Y"

## Config

Your `config.json` needs:
- `node_name`: unique node name
- `port`: HTTP/WS port (default 8080)
- `p2p_secret`: HMAC shared secret for peer auth
- `peers`: list of peer nodes (name, host, port)
- `local_models`: available AI models