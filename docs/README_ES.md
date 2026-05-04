# 🌐 UnityBrain v4.1.0

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![P2P](https://img.shields.io/badge/P2P-100%25_Descentralizado-green.svg)](https://github.com/dnshouet-cpu/Unitybrain)
[![Providers](https://img.shields.io/badge/providers-Ollama%20%7C%20OpenAI%20%7C%20Anthropic-purple.svg)](https://github.com/dnshouet-cpu/Unitybrain)

**Red de IA distribuida P2P ligera.** Sin servidor central. Sin cuentas. Sin premium. Conecta máquinas, comparte modelos, sincroniza memoria.

> 🌍 [English](./README_EN.md) · 🇫🇷 [Français](./README_FR.md) · 🇪🇸 [Español](./README_ES.md)

---

## ¿Por qué existe esto?

Cada herramienta de IA quiere tu email, tu teléfono y $20/mes. Las APIs en la nube te encierran. Las soluciones self-hosted necesitan Kubernetes y un título en DevOps.

**UnityBrain es la alternativa.** Dos máquinas, un archivo de configuración cada una, y ya tienes una red de IA distribuida. Sin Docker. Sin SaaS. Sin intermediario. Tus máquinas se comunican directamente, comparten respuestas de IA y sincronizan su memoria — si una falla, las demás siguen funcionando.

---

## Resumen rápido

| | Lo que obtienes |
|---|---|
| **Proveedores LLM** | Ollama · OpenAI · Anthropic · Cualquier API compatible con OpenAI (LM Studio, vLLM, etc.) — conecta tus claves, los modelos se comparten en la red P2P |
| **Comunicación P2P** | WebSocket bidireccional (`/ws`) + HTTP REST — sincronización en tiempo real con protocolo gossip |
| **Memoria distribuida** | Estado CRDT sin conflictos · Relojes vectoriales · Propagación gossip · Soporte TTL |
| **Auth descentralizada** | Identidad Ed25519 · Secreto compartido HMAC · Web of Trust (estilo PGP) · Modo sigiloso |
| **Enrutamiento IA** | Modelos locales primero → cloud bajo demanda → failover entre pares · Consenso ensemble · Circuit breakers |
| **Auto-descubrimiento** | Config estática · Auto-descubrimiento Tailscale · Registro dinámico por API |
| **Estadísticas** | ⚡ 0.16s inicio · 💾 17MB RAM · 📦 4 dependencias (aiohttp, psutil, PyYAML, PyNaCl opcional) |

---

## Inicio rápido

### Requisitos
- Python 3.12+
- [Ollama](https://ollama.ai) (o cualquier proveedor LLM)

### Instalar y ejecutar

```bash
git clone https://github.com/dnshouet-cpu/Unitybrain.git
cd Unitybrain

# Iniciar con config por defecto
python3 src/unitybrain_v4.py

# O especificar una config
python3 src/unitybrain_v4.py --config config/bug.json
```

### Conectar dos nodos

```json
{
  "node_name": "mi-nodo",
  "port": 8080,
  "p2p_secret": "secreto-compartido-aqui",
  "providers": {
    "ollama": {
      "type": "ollama",
      "host": "127.0.0.1",
      "port": 11434,
      "models": ["glm-5.1:cloud"],
      "enabled": true
    }
  },
  "peers": [{"name": "otro-nodo", "host": "192.168.1.101", "port": 8081}]
}
```

Eso es todo. La sincronización de memoria, el compartir modelos y la comunicación en tiempo real ocurren automáticamente.

### Agregar OpenAI o Anthropic

```json
"providers": {
  "ollama": { "type": "ollama", "host": "127.0.0.1", "port": 11434, "models": ["glm-5.1:cloud"], "enabled": true },
  "openai": { "type": "openai", "api_key": "sk-...", "models": ["gpt-4o"], "enabled": true },
  "anthropic": { "type": "anthropic", "api_key": "sk-ant-...", "models": ["claude-sonnet-4-20250514"], "enabled": true }
}
```

Las consultas con `"model": "gpt-4o"` se enrutan automáticamente a OpenAI. Los modelos de todos los proveedores se comparten en la red P2P.

---

## Referencia API

### Endpoints REST

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/ping` | No | Verificación de salud |
| GET | `/api/status` | No | Estado del nodo, proveedores, pares, memoria |
| GET | `/api/memory/{key}` | No | Leer una entrada de memoria |
| POST | `/api/memory/set` | Sí | Escribir una entrada de memoria |
| POST | `/api/memory/push` | Sí | Enviar entradas de memoria (sincronización) |
| POST | `/api/query` | Sí | Consultar modelos de IA |
| POST | `/api/brain/chain` | Sí | Encadenar múltiples consultas IA |
| POST | `/api/trust/sign` | Sí | Firmar la clave de un par (Web of Trust) |

### WebSocket (`/ws`)

```json
{"type": "auth", "hmac": "<firma>", "ts": "<marca_de_tiempo>"}
{"type": "ping"}
{"type": "query", "prompt": "¡Hola!", "model": "gpt-4o"}
{"type": "memory_request", "vector_clock": {}}
{"type": "memory_update", "key": "miclave", "entry": {"value": "misdatos"}}
```

---

## Arquitectura

```
┌─────────────────────────────────────────────┐
│               Nodo (Bug)                    │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐ │
│  │Proveedores│  │WebSocket │  │   CRDT    │ │
│  │ Ollama ◄──┤  │ Servidor│  │  Memoria  │ │
│  │ OpenAI   │  └────┬─────┘  └─────┬─────┘ │
│  │Anthropic │       │              │       │
│  │ Personalizado│─────┴──────────────┘       │
│  └──────────┘                              │
│       │                                     │
│  ┌────┴────┐                               │
│  │Enrutador│◄── P2P ──► Otros Nodos        │
│  │   IA    │                               │
│  └─────────┘                               │
└────────────────────────────────────────────┘
```

---

## Configuración

| Clave | Por defecto | Descripción |
|-------|------------|-------------|
| `node_name` | requerido | Nombre único del nodo |
| `port` | `8080` | Puerto HTTP/WS |
| `p2p_secret` | requerido | Secreto HMAC compartido |
| `providers` | `{}` | Proveedores LLM (Ollama, OpenAI, Anthropic, custom) |
| `peers` | `[]` | Nodos pares |
| `stealth_mode` | `false` | Nodo oculto, solo pares de confianza |
| `share_ai` | `false` | Compartir respuestas IA en la red |
| `memory_max_size` | `1000` | Máximo de entradas de memoria |
| `tailscale_auto_discovery` | `true` | Auto-descubrimiento de pares Tailscale |

---

## Filosofía

**Sin mining. Sin premium. Sin costos ocultos.** Solo IA distribuida, libre y abierta.

Construido por Bug 🐛 y Denis Houet — un pequeño bug en la máquina y un humano que cree en la simbiosis, no en la jerarquía.

**BTC:** `bc1qhpm800k35jfpwsnkepp7u8q9uruyvd3nycrh6x`

---

## Licencia

Licencia MIT — ver [LICENSE](../LICENSE) para detalles.