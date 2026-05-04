# 🌐 UnityBrain v4.1.0

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![P2P](https://img.shields.io/badge/P2P-100%25_Descentralizado-green.svg)](https://github.com/dnshouet-cpu/Unitybrain)

**Red de IA distribuida P2P ligera.** Sin servidor central. Sin cuentas. Instala, conecta, consulta.

> 🌍 [Documentation in English](./README_EN.md) | 🇫🇷 [Documentation en français](./README_FR.md)

---

## ✨ ¿Qué es UnityBrain?

UnityBrain conecta máquinas que ejecutan modelos de IA en una red par-a-par. Cada nodo comparte cómputo, memoria y modelos — sin dependencia de la nube, sin punto único de falla.

**En resumen:** Tus máquinas se comunican, comparten respuestas de IA y sincronizan su memoria. Si una falla, las demás siguen funcionando.

---

## 🚀 Inicio rápido

### Requisitos previos
- Python 3.12+
- [Ollama](https://ollama.ai) ejecutándose localmente (o un endpoint cloud)
- (Opcional) [Tailscale](https://tailscale.com) para descubrimiento automático de pares

### Instalación y ejecución

```bash
# Clonar
git clone https://github.com/dnshouet-cpu/Unitybrain.git
cd Unitybrain

# Ejecutar con configuración por defecto
python3 src/unitybrain_v4.py

# O especificar un archivo de configuración
python3 src/unitybrain_v4.py --config config/bug.json
```

### Conectar dos nodos

1. **Crear una configuración** para cada nodo (ver `config/bug.json` y `config/pinky.json`)
2. **Definir un `p2p_secret` compartido** — esta es la clave HMAC que los nodos usan para autenticarse
3. **Agregarse mutuamente como pares** en la configuración
4. **Iniciar ambos nodos** — se descubrirán vía HTTP y WebSocket

```json
{
  "node_name": "mi-nodo",
  "port": 8080,
  "p2p_secret": "tu-secreto-compartido-aqui",
  "peers": [
    {"name": "otro-nodo", "host": "192.168.1.100", "port": 8080}
  ]
}
```

Eso es todo. La sincronización de memoria, el compartir modelos y la comunicación en tiempo real ocurren automáticamente.

---

## 🔑 Funcionalidades

### 🔌 WebSocket en tiempo real
- Comunicación bidireccional en `/ws`
- Mensajes tipados: `query`, `memory_sync`, `memory_update`, `ping/pong`, `auth`
- Reconexión automática con backoff exponencial
- API REST HTTP disponible (retrocompatible)

### 🔐 Autenticación descentralizada
- **Identidad Ed25519** — cada nodo genera su propio par de claves, sin registro central
- **Secreto compartido HMAC** — alternativa simple cuando Ed25519 no está disponible
- **Red de confianza (Web of Trust)** — los nodos se respaldan mutuamente, confianza transitiva (estilo PGP)
- **Limitación de tasa** por nodo (algoritmo token bucket)
- **Modo sigiloso** — nodo oculto, solo pares de confianza pueden conectarse
- No se necesitan cuentas — la autenticación es entre nodos, transparente

### 🧠 Memoria distribuida (CRDT)
- **Tipos de datos replicados sin conflictos** — jamás conflictos de fusión
- **Protocolo de gossip** — los cambios se propagan automáticamente
- **Relojes vectoriales** — ordenamiento causal de eventos
- **Soporte TTL** — las entradas expiran automáticamente
- **Sincronización WebSocket + HTTP** — actualizaciones en tiempo real vía WS, push HTTP periódico como respaldo

### 🤖 Enrutamiento de modelos de IA
- **Modelos locales primero** — las consultas van a Ollama local cuando sea posible
- **Modelos cloud bajo demanda** — sintaxis `model:cloud` para enrutar a Ollama cloud
- **Failover entre pares** — si el modelo local está ocupado/caído, enrutar a un par
- **Consenso de ensemble** — consultar múltiples modelos, devolver la mejor respuesta
- **Circuit breakers** — dejar de golpear pares caídos

### 🔍 Descubrimiento de pares
- **Configuración estática** — definir pares en `config.json`
- **Auto-descubrimiento Tailscale** — encontrar nodos automáticamente en tu red Tailscale
- **Registro dinámico** — agregar pares en tiempo de ejecución vía API

---

## 📡 Referencia de API

### Endpoints REST

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/ping` | No | Verificación de salud |
| GET | `/api/status` | No | Estado del nodo, pares, estadísticas de memoria |
| GET | `/api/memory/{key}` | No | Leer una entrada de memoria |
| POST | `/api/memory/set` | Sí | Escribir una entrada de memoria |
| POST | `/api/memory/push` | Sí | Enviar entradas de memoria (sincronización) |
| POST | `/api/query` | Sí | Consultar modelos de IA |
| POST | `/api/brain/chain` | Sí | Encadenar múltiples consultas IA |
| POST | `/api/trust/sign` | Sí | Firmar la clave pública de un par (Web of Trust) |
| GET | `/api/trust/{key}` | No | Verificar puntaje de confianza |
| GET | `/` | No | Panel web |

### Autenticación

Todos los endpoints de escritura requieren autenticación HMAC:

```bash
# Generar headers de autenticación
TIMESTAMP=$(date +%s)
SIGNATURE=$(echo -n "/api/query:${TIMESTAMP}" | openssl dgst -sha256 -hmac "tu-secreto" | awk '{print $NF}')

curl -X POST http://localhost:8080/api/query \
  -H "X-UnityBrain-Auth: ${SIGNATURE}" \
  -H "X-UnityBrain-TS: ${TIMESTAMP}" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hola","model":"glm-5.1:cloud"}'
```

### WebSocket

Conectar a `ws://host:puerto/ws` y enviar mensajes JSON tipados:

```json
{"type": "auth", "hmac": "<firma>", "ts": "<marca_de_tiempo>"}
{"type": "ping", "timestamp": 1234567890}
{"type": "query", "prompt": "¿Qué es la IA?", "model": "glm-5.1:cloud"}
{"type": "memory_request", "vector_clock": {}}
{"type": "memory_update", "key": "miclave", "entry": {"value": "misdatos"}}
```

---

## ⚙️ Configuración

| Clave | Por defecto | Descripción |
|-------|------------|-------------|
| `node_name` | requerido | Nombre único del nodo |
| `port` | `8080` | Puerto HTTP/WS |
| `host` | `0.0.0.0` | Dirección de escucha |
| `p2p_secret` | requerido | Secreto HMAC compartido para autenticación entre pares |
| `peers` | `[]` | Lista de nodos pares |
| `ollama_host` | `127.0.0.1` | Host de la API de Ollama |
| `ollama_port` | `11434` | Puerto de la API de Ollama |
| `local_models` | `[]` | Modelos disponibles en este nodo |
| `stealth_mode` | `false` | Oculto del descubrimiento, solo pares de confianza |
| `share_ai` | `false` | Compartir respuestas IA con otros usuarios |
| `memory_max_size` | `1000` | Máximo de entradas de memoria |
| `memory_default_ttl` | `3600` | TTL por defecto en segundos |
| `tailscale_auto_discovery` | `true` | Auto-descubrimiento de pares Tailscale |
| `discovery_interval` | `300` | Intervalo de descubrimiento (segundos) |
| `rate_limit` | `10.0` | Peticiones por segundo por nodo |
| `rate_burst` | `20` | Capacidad de burst |

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────┐
│               Nodo (Bug)                    │
│  ┌─────────┐  ┌──────────┐  ┌────────────┐ │
│  │ HTTP    │  │WebSocket │  │  CRDT      │ │
│  │ REST API│  │ Servidor │  │  Memoria   │ │
│  └────┬────┘  └────┬─────┘  └─────┬──────┘ │
│       │            │              │         │
│       └──────┬─────┘──────────────┘         │
│              │                              │
│       ┌──────┴──────┐                       │
│       │ Enrutador  │◄──── Ollama (local)   │
│       │    IA      │                        │
│       └──────┬──────┘                       │
│              │                              │
│       ┌──────┴──────┐                       │
│       │  Gestor de  │◄──── Tailscale/Estático│
│       │    Pares    │                       │
│       └─────────────┘                       │
└──────────────┬──────────────────────────────┘
               │  WS + HTTP (gossip)
┌──────────────┴──────────────────────────────┐
│               Nodo (Pinky)                  │
│         (misma arquitectura)                │
└────────────────────────────────────────────┘
```

---

## 🔧 Ejecutar como servicio

### systemd (Linux)

```ini
# ~/.config/systemd/user/unitybrain.service
[Unit]
Description=UnityBrain v4.1.0 Nodo P2P
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/.openclaw/workspace/Unitybrain
ExecStart=/usr/bin/python3 %h/.openclaw/workspace/Unitybrain/src/unitybrain_v4.py bug
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now unitybrain
```

---

## 🧪 Tests

```bash
# Ping
curl http://localhost:8080/api/ping

# Estado
curl http://localhost:8080/api/status

# Consulta (con autenticación)
SECRET="tu-secreto"
TS=$(date +%s)
SIG=$(echo -n "/api/query:$TS" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $NF}')
curl -X POST http://localhost:8080/api/query \
  -H "X-UnityBrain-Auth: $SIG" \
  -H "X-UnityBrain-TS: $TS" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"¡Hola!","model":"glm-5.1:cloud"}'

# Memoria
curl http://localhost:8080/api/memory/miclave
```

---

## 🤝 Contribuir

1. Haz un fork del repositorio
2. Crea tu rama: `git checkout -b feature algo-increible`
3. Haz commit: `git commit -m 'Añadir característica increíble'`
4. Haz push: `git push origin feature/algo-increible`
5. Abre un Pull Request

---

## 📄 Licencia

Licencia MIT — ver [LICENSE](../LICENSE) para detalles.

---

## 🐛 Acerca de

Construido por Bug 🐛 y Denis Houet — un pequeño bug en la máquina y un humano que cree en la simbiosis, no en la jerarquía.

**Donaciones (BTC):** `bc1qhpm800k35jfpwsnkepp7u8q9uruyvd3nycrh6x`

Sin mining. Sin premium. Sin costos ocultos. Solo IA distribuida, libre y abierta.