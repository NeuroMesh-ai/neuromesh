# 🌐 UnityBrain v4.1.0

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![P2P](https://img.shields.io/badge/P2P-100%25_去中心化-green.svg)](https://github.com/dnshouet-cpu/Unitybrain)
[![Providers](https://img.shields.io/badge/providers-Ollama%20%7C%20OpenAI%20%7C%20Anthropic-purple.svg)](https://github.com/dnshouet-cpu/Unitybrain)

**轻量级P2P分布式AI网络。** 无中心服务器。无账号。无高级订阅。连接机器，共享模型，同步记忆。

> 🌍 [English](./README_EN.md) · 🇫🇷 [Français](./README_FR.md) · 🇪🇸 [Español](./README_ES.md) · 🇩🇪 [Deutsch](./README_DE.md) · 日本語 · 🇷🇺 [Русский](./README_RU.md) · 简体中文

---

## 为什么需要 UnityBrain

每个AI工具都想要你的邮箱、手机号和每月20美元。云API把你锁住。自建方案需要Kubernetes和DevOps学位。

**UnityBrain 是替代方案。** 两台机器，各一个配置文件，就是分布式AI网络。不用Docker。不用SaaS。没有中间商。

---

## 一览

| | 你得到的 |
|---|---|
| **LLM 提供商** | Ollama · OpenAI · Anthropic · 任何OpenAI兼容API — 接入密钥，模型在P2P网络中共享 |
| **P2P 通信** | 双向WebSocket + HTTP REST — gossip协议实时同步 |
| **分布式记忆** | CRDT无冲突 · 向量时钟 · Gossip传播 · TTL支持 |
| **去中心化认证** | Ed25519身份 · HMAC共享密钥 · Web of Trust (类PGP) · 隐身模式 |
| **AI 路由** | 本地模型优先 → 按需云 → 节点故障转移 · 集成共识 · 断路器 |
| **性能** | ⚡ 0.16秒启动 · 💾 17MB内存 · 📦 4个依赖 |

---

## 快速开始

```bash
git clone https://github.com/dnshouet-cpu/Unitybrain.git
cd Unitybrain
python3 src/unitybrain_v4.py --config config/bug.json
```

### 添加 OpenAI 或 Anthropic

```json
"providers": {
  "ollama": { "type": "ollama", "host": "127.0.0.1", "port": 11434, "models": ["glm-5.1:cloud"], "enabled": true },
  "openai": { "type": "openai", "api_key": "sk-...", "models": ["gpt-4o"], "enabled": true }
}
```

---

## 理念

**无挖矿。无高级订阅。无隐藏费用。** 只有免费、开放、分布式的AI。

由 Bug 🐛 和 Denis Houet 构建 — 机器中的一个小bug，和相信共生而非层级的人类。

**BTC:** `bc1qhpm800k35jfpwsnkepp7u8q9uruyvd3nycrh6x`

---

## 许可证

MIT 许可证 — 详见 [LICENSE](../LICENSE)。