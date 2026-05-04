# 🌐 UnityBrain v4.1.0

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![P2P](https://img.shields.io/badge/P2P-100%25_分散型-green.svg)](https://github.com/dnshouet-cpu/Unitybrain)
[![Providers](https://img.shields.io/badge/providers-Ollama%20%7C%20OpenAI%20%7C%20Anthropic-purple.svg)](https://github.com/dnshouet-cpu/Unitybrain)

**軽量P2P分散AIネットワーク。** 中央サーバーなし。アカウントなし。プレミアムなし。マシンを繋いで、モデルを共有し、メモリを同期。

> 🌍 [English](./README_EN.md) · 🇫🇷 [Français](./README_FR.md) · 🇪🇸 [Español](./README_ES.md) · 🇩🇪 [Deutsch](./README_DE.md) · 日本語

---

## なぜこれが存在するのか

すべてのAIツールがメールアドレスと電話番号、そして月額20ドルを求めてくる。クラウドAPIはロックインする。セルフホストにはKubernetesとDevOpsの学位が必要。

**UnityBrainがその代替手段。** 2台のマシン、それぞれ1つの設定ファイル、それだけで分散AIネットワークの完成。Dockerなし。SaaSなし。中間業者なし。マシン同士が直接通信し、AI応答を共有し、メモリを同期する — 1台が落ちても他は動き続ける。

---

## 概要

| | 得られるもの |
|---|---|
| **LLMプロバイダー** | Ollama · OpenAI · Anthropic · 任意のOpenAI互換API — キーを接続するだけ、モデルはP2Pネットワークで共有 |
| **P2P通信** | 双方向WebSocket (`/ws`) + HTTP REST — ゴシッププロトコルによるリアルタイム同期 |
| **分散メモリ** | CRDT競合解決 · ベクタークロック · ゴシップ伝播 · TTLサポート |
| **分散型認証** | Ed25519アイデンティティ · HMAC共有鍵 · Web of Trust (PGP風) · ステルスモード |
| **AIルーティング** | ローカルモデル優先 → クラウドオンデマンド → ピアフェイルオーバー · アンサンブルコンセンサス · サーキットブレーカー |
| **自動発見** | 静的設定 · Tailscale自動発見 · 動的API登録 |
| **パフォーマンス** | ⚡ 起動0.16秒 · 💾 RAM 17MB · 📦 依存4つ |

---

## クイックスタート

```bash
git clone https://github.com/dnshouet-cpu/Unitybrain.git
cd Unitybrain
python3 src/unitybrain_v4.py --config config/bug.json
```

### OpenAIまたはAnthropicの追加

```json
"providers": {
  "ollama": { "type": "ollama", "host": "127.0.0.1", "port": 11434, "models": ["glm-5.1:cloud"], "enabled": true },
  "openai": { "type": "openai", "api_key": "sk-...", "models": ["gpt-4o"], "enabled": true }
}
```

`"model": "gpt-4o"` のクエリは自動的にOpenAIにルーティングされます。

---

## 哲学

**マイニングなし。プレミアムなし。隠されたコストなし。** 無料でオープンな分散AIだけ。

Bug 🐛 と Denis Houet が構築 — 機械の中の小さなバグと、階層ではなく共生を信じる人間。

**BTC:** `bc1qhpm800k35jfpwsnkepp7u8q9uruyvd3nycrh6x`

---

## ライセンス

MITライセンス — 詳細は[LICENSE](../LICENSE)を参照。