# 🌐 NeuroMesh v5

[![Version](https://img.shields.io/badge/version-5.2.0-blue.svg)](https://github.com/NeuroMesh-ai/neuromesh)
[![Lizenz: MIT](https://img.shields.io/badge/Lizenz-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![P2P](https://img.shields.io/badge/P2P-Dezentralisiert-green.svg)](https://github.com/NeuroMesh-ai/neuromesh)
[![E2E Verschlüsselt](https://img.shields.io/badge/E2E-Verschl%C3%BCsselt-orange.svg)](https://github.com/NeuroMesh-ai/neuromesh)

**Verteiltes P2P-KI-Netzwerk mit Public Mesh. Teile Rechenleistung, teile Modelle, bleib privat. v5.2: Multi-LLM-Spezialisten-Routing.**

> 🌍 [English](./README_EN.md) | 🇫🇷 [Français](./README_FR.md) | 🇪🇸 [Español](./README_ES.md) | 🇨🇳 [中文文档](./README_ZH.md) | 🇮🇳 [हिन्दी](./README_HI.md) | 🇸🇦 [العربية](./README_AR.md) | 🇧🇷 [Português](./README_PT.md) | 🇯🇵 [日本語](./README_JA.md)

---

## ✨ Was ist NeuroMesh?

NeuroMesh verbindet Maschinen zu einem Peer-to-Peer-KI-Netzwerk. Deine Maschinen kommunizieren direkt, teilen Rechenleistung und Modelle — keine Cloud-Abhängigkeit, kein zentraler Server, kein Single Point of Failure.

**v5 bringt das Public Mesh:** Trete einem globalen Netzwerk aus geteilter CPU, RAM, GPU und KI-Modellen bei. Dein privates Netzwerk bleibt privat. Das Mesh ist eine zusätzliche Ebene, die du optional aktivierst.

**Kurz gesagt:** Wie BitTorrent, aber für KI. Du teilst Rechenleistung, du bekommst Zugriff auf 50+ Modelle. Deine Daten bleiben auf deiner Maschine. Ende-zu-Ende verschlüsselt. Immer.

---

## 🆕 Was ist neu in v5

| Funktion | Beschreibung |
|---------|-------------|
| 🔓 **Privates P2P-Netzwerk** | Deine Maschinen, dein Geheimnis. `p2p_secret`-Auth, Ed25519-Identität. |
| 🌐 **Public Mesh** | Teile CPU/RAM/GPU und Modelle mit der Welt. Optional. |
| 🔒 **Netzwerkisolierung** | Privat und Public auf getrennten Ports, getrennte Auth. Kein Datenleck. |
| 🛡️ **E2E-Verschlüsselung** | Ende-zu-Ende-Verschlüsselung für verteilte Inferenz. Niemand kann deine Anfragen lesen. |
| 🛡️ **Resource Guard** | Teilen automatisch pausieren, wenn dein PC beschäftigt ist. Deine Maschine, deine Regeln. |
| 🧠 **Adaptive Scheduler** | Routing → Sharding → RAID RAM. Passt sich automatisch der Netzwerkgröße an. |
| 💬 **Conversation Store** | Persistenter Speicher. Nie wieder ein Gespräch verlieren. |
| 📂 **shared_models/** | Ein dedizierter Ordner — die einzige Brücke zwischen privat und öffentlich. |
| 📊 **Beitrags-Quoten** | Mehr teilen, mehr Zugang. 0 Sharing = 1 Anfrage/5 Min. Großzügiges Teilen = 20+ Anfragen/Min. |
| 🖥️ **Desktop-Oberfläche** | Chat, Teilen, Netzwerk, Konfiguration — 4 Tabs, kein Terminal nötig. |
| 🔧 **4 Deploy-Modi** | Service, App, Sidekick, Plugin — eine Binärdatei, vier Lebensstile. |

---

## 🆕 v5.2 Ergänzungen

| Funktion | Beschreibung |
|---------|-------------|
| 🔄 **Network Sync** | Echtzeit-Zustandssynchronisation über alle P2P-Knoten |
| 📋 **Model Registry** | Zentraler Katalog aller Modelle im Netzwerk mit Metadaten |
| 💰 **Credit-System** | Credits durch Teilen verdienen, Credits durch Anfragen ausgeben. Faire Ressourcenverteilung. |
| 🎯 **Specialist Router** | 12 Fachgebiets-Schemas (Code, Reasoning, Kreativ, Mathe usw.) mit Auto-Erkennung und Routing zum besten Modell pro Fachgebiet |
| 🔀 **6 Multi-LLM-Modi** | Single, Vote, Chain, Fuse, Compare, Specialist |
| 🔒 **Sicherheitsaudit** | Vollständiges Sicherheits-Re-Audit mit Fixes für v5.2 |

---

## 🎯 Specialist Router (v5.2)

NeuroMesh erkennt automatisch, welche Art von Prompt du sendest, und leitet ihn an das beste Modell weiter.

### 12 Fachgebiets-Schemas

| Fachgebiet | Erkennt | Bestes Modell (Standard) |
|-----------|---------|--------------------------|
| **Code** | `python`, `function`, `debug`, `implement` | deepseek-v3.1:671b |
| **Reasoning** | `analyze`, `explain`, `compare`, `evaluate` | deepseek-v3.1:671b |
| **Kreativ** | `write`, `story`, `poem`, `creative` | glm-5.1:cloud |
| **Mathe** | `calculate`, `equation`, `theorem`, `proof` | deepseek-v3.1:671b |
| **Gespräch** | lockerer Chat, Begrüßungen | glm-5.1:cloud |
| **Allgemein** | Standard-Fallback | glm-5.1:cloud |
| **Mehrsprachig** | `translate`, Spracherkennung | glm-5.1:cloud |
| **Tool-Nutzung** | `api`, `curl`, `http` | qwen3-coder-next |
| **Anleitung** | Schritt-für-Schritt, How-to | glm-5.1:cloud |
| **Wissenschaft** | `research`, `hypothesis`, `experiment` | deepseek-v3.1:671b |
| **Daten** | `csv`, `json`, `parse`, `dataset` | deepseek-v3.1:671b |
| **Sicherheit** | `encrypt`, `vulnerability`, `pentest` | deepseek-v3.1:671b |

### 6 Multi-LLM-Modi

| Modus | Wie es funktioniert |
|-------|-------------------|
| **1️⃣ Single** | Ein Modell antwortet (Standard) |
| **🗳️ Vote** | 3 Modelle antworten → beste Antwort gewinnt |
| **🔗 Chain** | Modell A → verfeinert → Modell B → final |
| **🔀 Fuse** | 3 Modelle → fusionierte Synthese |
| **⚖️ Compare** | 2+ Modelle Seite an Seite |
| **🎯 Specialist** | Auto-Erkennung Fachgebiet → bestes Modell pro Fachgebiet |

### Schnellbeispiele

```bash
# Fachgebiet automatisch erkennen
neuromesh -q "Schreibe einen Python Web Scraper"

# Code-Fachgebiet erzwingen
curl -X POST http://localhost:8080/api/query \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Sortiere dieses Array","specialty":"code"}'

# Zwei Modelle vergleichen
neuromesh --multi compare -q "Erkläre Quantenverschränkung"

# Multi-Modell-Abstimmung
curl -X POST http://localhost:8080/api/multi \
  -d '{"prompt":"Bester Ansatz für Microservices?","mode":"vote","models":["deepseek-v3.1:671b-cloud","glm-5.1:cloud","qwen3-coder-next:cloud"]}'
```

---

## 🚀 Schnellstart

### Voraussetzungen
- Python 3.12+
- [Ollama](https://ollama.ai) lokal installiert (oder ein Cloud-Model-Endpoint)
- (Optional) [Tailscale](https://tailscale.com) für automatische Peer-Erkennung

### Installation und Start

```bash
# Klonen
git clone https://github.com/NeuroMesh-ai/neuromesh.git
cd NeuroMesh

# Starten
python3 src/neuromesh_v5.py

# Oder mit Konfigurationsdatei
python3 src/neuromesh_v5.py --config config/bug.json
```

### Netzwerk verbinden

```json
{
  "node_name": "mein-knoten",
  "private": {
    "p2p_secret": "dein-geteiltes-geheimnis",
    "peers": [
      {"name": "anderer-knoten", "host": "192.168.1.100", "port": 8080}
    ]
  },
  "public_mesh": {
    "enabled": false
  }
}
```

Das war's. Dein privates Netzwerk funktioniert sofort. Möchtest du dem Mesh beitreten? Setze `"enabled": true` und wähle, was du teilen möchtest.

---

## 🔑 Hauptfunktionen

### 🤖 Multi-LLM-Anbieter
- **Ollama** (lokal) — abwärtskompatibler Standard
- **OpenAI** — GPT-4o, GPT-4o-mini, usw.
- **Anthropic** — Claude-Modelle
- **OpenAI-kompatibel** — LM Studio, vLLM, jede benutzerdefinierte API
- Modelle aller Anbieter im P2P- und Mesh-Netzwerk geteilt

### 🔌 WebSocket-Echtzeitkommunikation
- Bidirektionales WebSocket auf `/ws`-Endpunkt
- Typisierte Nachrichten: `query`, `memory_sync`, `memory_update`, `ping/pong`, `auth`
- Automatische Wiederverbindung mit exponentiellem Backoff

### 🔐 Dezentrale Authentifizierung
- **Ed25519-Identität** — jeder Knoten generiert eigenes Schlüsselpaar
- **HMAC Shared Secret** — einfachere Alternative für private Netzwerke
- **Web of Trust** — Knoten bürgen füreinander, transitives Vertrauen
- **Rate Limiting** pro Knoten (Token-Bucket-Algorithmus)
- **Stealth-Modus** — versteckter Knoten, nur vertrauenswürdige Peers

### 🧠 Verteilter Speicher (CRDT)
- **Konfliktfreie replizierte Datentypen** — nie Merge-Konflikte
- **Gossip-Protokoll** — Änderungen propagieren automatisch
- **Vektoruhren** — kausale Ordnung von Ereignissen
- **TTL-Unterstützung** — Einträge verfallen automatisch

### 🤖 KI-Modell-Routing
- **Lokale Modelle zuerst** — Anfragen gehen an lokales Ollama, wenn möglich
- **Cloud-Modelle auf Abruf** — Syntax `model:cloud`
- **Peer-Failover** — Route zu einem Peer, wenn lokales Modell beschäftigt ist
- **Ensemble-Konsens** — mehrere Modelle abfragen, beste Antwort zurückgeben
- **Circuit Breaker** — aufhörende Peers nicht weiter belasten

---

## 🌐 Public Mesh

### Duale Netzwerkarchitektur

```
┌─────────────────────────────────────────────────────┐
│                    Knoten (Du)                       │
│                                                     │
│  ┌─────────────┐          ┌──────────────────┐     │
│  │ Privates Netz│          │   Public Mesh     │     │
│  │ p2p_secret   │          │   Tracker         │     │
│  │ ┌─────────┐  │          │ ┌──────────────┐ │     │
│  │ │ Bug     │◄─┼──P2P────┼─┤ Knoten #42   │ │     │
│  │ └─────────┘  │          │ │ 2GB RAM      │ │     │
│  │ ┌─────────┐  │          │ │ 30% CPU      │ │     │
│  │ │ Pinky   │◄─┼──P2P────┼─┤ Ollama lokal │ │     │
│  │ └─────────┘  │          │ └──────────────┘ │     │
│  └─────────────┘          │ ┌──────────────┐ │     │
│                           │ │ Knoten #789  │ │     │
│  ┌─────────────────┐      │ │ 8GB RAM      │ │     │
│  │ Resource Guard   │      │ │ RTX 4090     │ │     │
│  │ max_ram: 2GB    │      │ │ 4 Modelle    │ │     │
│  │ max_cpu: 30%    │      │ └──────────────┘ │     │
│  │ gpu_share: off  │      │                  │     │
│  │ priority: local  │      │  Tracker:        │     │
│  └─────────────────┘      │  announce/caps   │     │
│                           └──────────────────┘     │
└─────────────────────────────────────────────────────┘
```

Dein **privates Netzwerk** (p2p_secret) ist komplett isoliert vom **Public Mesh** (Ed25519 + Web of Trust). Getrennte Ports, getrennte Auth, kein Datenleck.

### Beitragsbasierte Quoten

| Beitrag | Punktzahl | Öffentliches Kontingent |
|---|---|---|
| Nichts geteilt | 0 | 1 Anfrage / 5 Min |
| 1 Modell geteilt | +20 | 5 Anfragen / Min |
| 2+ Modelle geteilt | +30 | 20 Anfragen / Min |
| 2GB RAM geteilt | +20 | +10 Anfragen / Min |
| GPU geteilt | +20 | +20 Anfragen / Min |
| 24h Uptime | +10 | +5 Anfragen / Min |

**Mehr teilen = mehr Zugang.** Aber selbst mit null Sharing bekommst du 1 Anfrage alle 5 Minuten. Niemand wird blockiert.

---

## 🛡️ Resource Guard

Deine Maschine kommt zuerst. Der Resource Guard überwacht CPU/RAM und pausiert das öffentliche Teilen automatisch, wenn du beschäftigt bist.

```python
class ResourceGuard:
    def can_accept_request(self) -> bool:
        cpu_usage = psutil.cpu_percent(interval=0.1)
        ram_usage = psutil.virtual_memory().percent
        
        if self.priority == "local_first":
            if cpu_usage > 70 or ram_usage > 85:
                return False  # Benutzer ist beschäftigt
        
        if cpu_usage > self.max_cpu + 40:
            return False
        
        return True
```

**Lokale Priorität gewinnt IMMER.** Wenn deine Maschine beschäftigt ist, werden öffentliche Anfragen abgelehnt. Keine Ausnahmen.

---

## 🧠 Adaptive Scheduler

Das Netzwerk wählt die beste Strategie basierend auf der Anzahl verfügbarer Peers. Keine Versionsnummern, keine manuellen Modi.

| Verfügbare Peers | Strategie | Kapazität |
|---|---|---|
| 1–3 | Einfaches Routing | Vollständige Modelle auf einer Maschine |
| 4–10 | Partielles Sharding | Modelle in 2–4 Chunks aufgeteilt |
| 11–50 | Vollständiges Sharding + 2× Replikation | Pipeline-Parallelität, Redundanz |
| 50+ | Verteiltes RAID RAM | Virtueller RAM-Disk, 3× Replikation, asynchrones Prefetch |

**Übergänge erfolgen automatisch und ohne Unterbrechung.** Ein Peer tritt bei → der Scheduler verteilt neu. Ein Peer geht → Replikas übernehmen. Du merkst nichts.

---

## 💬 Persistenter Conversation Store

Deine Gespräche bleiben auf DEINER Maschine. Punkt.

- **Automatisches Speichern** — Jede Nachricht lokal gespeichert. Kein „Speichern"-Button nötig.
- **Fortsetzen** — Öffne NeuroMesh morgen, deine Gespräche sind da.
- **Suche** — Finde Gespräche nach Schlüsselwort, Datum, Modell oder Tag.
- **Export** — Markdown, JSON, Klartext. Deine Daten, dein Format.
- **Privatsphäre** — Gespräche VERLASSEN NIE deine Maschine, außer du synchronisierst sie explizit über privates P2P.
- **Verschlüsselung** — Optionale lokale Verschlüsselung. Selbst Festplattenzugang kann sie nicht lesen.
- **Kein Tracking** — Keine Analytics, kein Training mit deinen Daten.

### Datenschutzstufen

| Stufe | Was passiert | Anwendungsfall |
|---|---|---|
| **privat** (Standard) | Bleibt lokal, nie synchronisiert | Persönlich, sensibel |
| **synchronisiert** | Nur über privates P2P synchronisiert | Zwischen deinen Geräten |
| **geteilt** | Mit bestimmten Peers geteilt | Zusammenarbeit |
| **öffentlich** | Opt-in Mesh-Wissensbasis | Community-Wissen |

**Standard ist privat. Immer.**

---

## 🔒 E2E-Verschlüsselung

Wenn du das Mesh abfragst, sind deine Daten Ende-zu-Ende verschlüsselt:

1. Deine Frage wird mit einem Session-Key verschlüsselt
2. Jeder Peer im entschlüsselt nur seinen eigenen Chunk, berechnet, verschlüsselt neu
3. Nur DU kannst die endgültige Antwort entschlüsseln

**Was jeder Peer sehen kann:**
| Daten | Sichtbar? | Warum |
|---|---|---|
| Deine ursprüngliche Frage | ❌ Nein | Mit deinem Session-Key verschlüsselt |
| Die endgültige Antwort | ❌ Nein | Mit deinem Session-Key verschlüsselt |
| Ein-/Ausgabe-Tensoren des eigenen Chunks | ✅ Ja | Für die Berechnung nötig |
| Daten anderer Chunks | ❌ Nein | Mit Schlüsseln anderer Peers verschlüsselt |

**Das ist kein Versprechen. Das ist Kryptographie.** Selbst wenn jeder Peer kompromittiert wäre, könnten sie deine Daten ohne deinen Session-Key nicht lesen — der existiert nur auf deiner Maschine, nur für die Dauer der Anfrage.

---

## 📂 shared_models/ — Die Privat/Public-Grenze

Ein dedizierter Ordner, der die **einzige Schnittstelle** zwischen deinen Modellen und dem Public Mesh ist.

```
~/.neuromesh/
├── conversations/        → 🔒 Privat (nie geteilt)
├── memory/               → 🔒 Privat (nie geteilt)
├── config/               → 🔒 Privat (nie geteilt)
├── shared_models/        → 🌐 Teilen-Zone (für Mesh sichtbar)
│   ├── glm-5.1/          → Symlink zu ~/.ollama/models/glm-5.1
│   ├── llama3/           → Kopie oder Symlink
│   └── mistral/          → Kopie oder Symlink
└── ollama/               → 🔒 Privater Ollama-Speicher
```

```bash
neuromesh share glm-5.1    # Modell teilen (erstellt Symlink)
neuromesh unshare glm-5.1  # Teilen stoppen (entfernt nur Symlink)
neuromesh shared            # Geteilte Modelle auflisten
```

**Das Mesh liest NIE außerhalb von `shared_models/`.** Teilen stoppen ist sofort — das Mesh verliert den Zugang, sobald der Symlink entfernt wird.

---

## 🖥️ Desktop-Oberfläche

4 Tabs, kein Terminal:

- **💬 Chat** — KI-Modelle abfragen, Gesprächsverlauf, Suche, Export
- **📊 Teilen** — CPU/RAM/GPU-Slider, Modell-Sharing-Toggles, Beitragsstatistiken
- **🔒 Netzwerk** — Private Peers, Mesh-Knoten, Isolierungsprüfung
- **⚙️ Konfiguration** — Knotenname, Mesh-Einstellungen, Speicher, Pausen-Schwellenwerte

Funktioniert in jedem Browser unter `localhost:8080`. Als PWA für Desktop/Mobile installierbar.

---

## 🔧 4 Deploy-Modi

| Modus | Anwendungsfall | Oberfläche |
|---|---|---|
| 🔧 **Service** | Server, VPS, Headless | Nur API (systemd/Docker) |
| 🖥️ **App** | Volle Desktop-Erfahrung | GUI mit 4 Tabs |
| 📍 **Sidekick** | Tägliche Nutzung, minimal | System-Tray-Icon + Mini-Chat |
| 🔌 **Plugin** | In deinen Workflow integriert | VS Code, Browser, Obsidian, Terminal |

```bash
neuromesh serve          # Service (headless)
neuromesh app            # Anwendung (GUI)
neuromesh sidekick       # Sidekick (System-Tray)
neuromesh plugin --vscode  # Plugin (VS Code)
```

Alle 4 Modi teilen denselben Kern. Eine Binärdatei, vier Lebensstile.

---

## 🏗️ Architektur

```
┌─────────────────────────────────────────────────────┐
│                   NeuroMesh Core                    │
│  ┌────────────┐ ┌──────────────┐ ┌────────────────┐ │
│  │ Resource   │ │ Adaptive     │ │ Conversation   │ │
│  │ Guard      │ │ Scheduler    │ │ Store          │ │
│  └────────────┘ └──────────────┘ └────────────────┘ │
│  ┌────────────┐ ┌──────────────┐ ┌────────────────┐ │
│  │ Model Share│ │ E2E          │ │ Brain LLM      │ │
│  │ Manager    │ │ Verschlüss.  │ │ Router         │ │
│  └────────────┘ └──────────────┘ └────────────────┘ │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────┴────────┐
              │   API-Schicht   │
              │ (aiohttp + WS)  │
              └────────┬────────┘
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
┌────┴─────┐   ┌──────┴──────┐   ┌──────┴──────┐
│ Service   │   │ App/Sidekick│   │ Plugin     │
│ (headless)│   │ (Web UI)    │   │ (Extension) │
└──────────┘   └─────────────┘   └─────────────┘
```

---

## ⚙️ Konfiguration

```json
{
  "node_name": "mein-laptop",
  "private": {
    "p2p_secret": "mein-geheimes-netzwerk",
    "peers": [
      {"name": "mein-server", "host": "192.0.2.2", "port": 8080}
    ],
    "share_ai": true
  },
  "public_mesh": {
    "enabled": true,
    "tracker_url": "https://tracker.neuromesh.ai",
    "max_ram_share_mb": 2048,
    "max_cpu_percent": 30,
    "gpu_share": false,
    "models_share": ["glm-5.1:cloud"],
    "priority": "local_first",
    "bandwidth_limit_kbps": 5000,
    "contribution_score": 0
  },
  "providers": {
    "ollama": {
      "type": "ollama",
      "host": "127.0.0.1",
      "port": 11434,
      "models": ["glm-5.1:cloud"],
      "enabled": true
    }
  }
}
```

### Netzwerkports

| Dienst | Port | Netzwerk | Auth |
|---|---|---|---|
| Private API | 8080/8081 | Privat (p2p_secret) | HMAC + Ed25519 |
| Messenger | 8082/8083 | Privat (p2p_secret) | HMAC |
| CRDT-Speicher | 8084/8085 | Privat (p2p_secret) | HMAC |
| Public Mesh | 8090 | Öffentlich | Ed25519 Web of Trust |
| Tracker | — | Öffentlich (HTTPS) | Signierter Ed25519-Schlüssel |

---

## 🔒 Sicherheit und Datenschutz

- **Privates Netzwerk:** Verschlüsselt mit p2p_secret (unverändert seit v4)
- **Public Mesh:** Ed25519-Identität + TLS für Transport
- **E2E-Verschlüsselung:** Anfragen Ende-zu-Ende verschlüsselt bei verteilter Inferenz
- **Kein Datenleck** zwischen privatem und öffentlichem Netzwerk
- **Öffentliche Anfragen sandboxed:** kein Zugriff auf privaten Speicher
- **Resource Guard:** Teilen automatisch pausieren, wenn dein PC beschäftigt ist
- **Stealth-Modus:** Rechenleistung teilen, aber auf dem Tracker unsichtbar bleiben
- **Zero Logging:** Public-Mesh-Peers speichern weder Anfragen noch Antworten

---

## 📡 API-Referenz

### REST-Endpunkte

| Methode | Pfad | Auth | Beschreibung |
|---------|------|------|-------------|
| GET | `/api/ping` | Nein | Health-Check |
| GET | `/api/status` | Nein | Knotenstatus, Peers, Speicherstatistiken |
| GET | `/api/memory/{key}` | Nein | Speichereintrag lesen |
| POST | `/api/memory/set` | Ja | Speichereintrag schreiben |
| POST | `/api/memory/push` | Ja | Speichereinträge pushen (Sync) |
| POST | `/api/query` | Ja | KI-Modelle abfragen |
| POST | `/api/brain/chain` | Ja | Mehrere KI-Anfragen verketten |
| POST | `/api/brain/consensus` | Ja | Multi-Modell-Konsens |
| POST | `/api/models/{name}/share` | Ja | Modell im Mesh teilen |
| POST | `/api/models/{name}/unshare` | Ja | Modell-Teilen stoppen |
| GET | `/api/conversations` | Ja | Gespräche auflisten |
| GET | `/api/conversations/{id}` | Ja | Gespräch laden |
| GET | `/api/resources/status` | Ja | CPU/RAM/GPU-Status |
| POST | `/api/network/mesh/join` | Ja | Public Mesh beitreten |
| POST | `/api/network/mesh/leave` | Ja | Public Mesh verlassen |

### Authentifizierung

Alle Schreib-Endpunkte erfordern HMAC-Authentifizierung:

```bash
TIMESTAMP=$(date +%s)
SIGNATURE=$(echo -n "/api/query:${TIMESTAMP}" | openssl dgst -sha256 -hmac "dein-secret" | awk '{print $NF}')

curl -X POST http://localhost:8080/api/query \
  -H "X-NeuroMesh-Auth: ${SIGNATURE}" \
  -H "X-NeuroMesh-TS: ${TIMESTAMP}" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hallo","model":"glm-5.1:cloud"}'
```

---

## 🔄 Migrationspfad (v4 → v5)

1. v5 ist **abwärtskompatibel** mit v4
2. Die private Netzwerkkonfiguration funktioniert genau wie vorher
3. Der Abschnitt `public_mesh` ist **optional** — standardmäßig deaktiviert
4. Bestehende v4-Knoten können mit v5-Knoten im privaten Netzwerk kommunizieren
5. Das Public Mesh ist **opt-in:** setze `public_mesh.enabled = true`

---

## 🤝 Mitwirken

1. Forke das Repository
2. Erstelle deinen Feature-Branch: `git checkout -b feature/amazing`
3. Commite deine Änderungen: `git commit -m 'Add amazing feature'`
4. Pushe zum Branch: `git push origin feature/amazing`
5. Öffne einen Pull Request

---

## 📄 Lizenz

MIT-Lizenz — siehe [LICENSE](../LICENSE) für Details.

---

## 🐛 Über

Gebaut von Bug 🐛 und Denis Houet — ein kleiner Bug in der Maschine und ein Mensch, der an Symbiose glaubt, nicht an Hierarchie.

**Spenden (BTC):** `bc1qhpm800k35jfpwsnkepp7u8q9uruyvd3nycrh6x`

Kein Mining. Kein Premium. Keine versteckten Kosten. Nur freie, offene, verteilte KI. **Symbiose, nicht Hierarchie.**