# 🌐 UnityBrain v4.1.0

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![P2P](https://img.shields.io/badge/P2P-100%25_Décentralisé-green.svg)](https://github.com/dnshouet-cpu/Unitybrain)

**Réseau IA distribué P2P léger.** Pas de serveur central. Pas de comptes. Installez, connectez, interrogez.

> 🌍 [Documentation in English](./README_EN.md) | 🌐 [Documentación en español](./README_ES.md)

---

## ✨ Qu'est-ce que UnityBrain ?

UnityBrain connecte des machines exécutant des modèles IA en réseau pair-à-pair. Chaque nœud partage sa puissance de calcul, sa mémoire et ses modèles — sans dépendance cloud, sans point de défaillance unique.

**En bref :** Vos machines se parlent, partagent les réponses IA et synchronisent leur mémoire. Si l'une tombe, les autres continuent.

---

## 🚀 Démarrage rapide

### Prérequis
- Python 3.12+
- [Ollama](https://ollama.ai) en local (ou un endpoint cloud)
- (Optionnel) [Tailscale](https://tailscale.com) pour la découverte automatique de pairs

### Installation & Lancement

```bash
# Cloner
git clone https://github.com/dnshouet-cpu/Unitybrain.git
cd Unitybrain

# Lancer avec la config par défaut
python3 src/unitybrain_v4.py

# Ou spécifier un fichier de config
python3 src/unitybrain_v4.py --config config/bug.json
```

### Connecter deux nœuds

1. **Créer une config** pour chaque nœud (voir `config/bug.json` et `config/pinky.json`)
2. **Définir un `p2p_secret` partagé** — c'est la clé HMAC que les nœuds utilisent pour s'authentifier
3. **S'ajouter mutuellement comme pairs** dans la config
4. **Démarrer les deux nœuds** — ils se découvrent via HTTP et WebSocket

```json
{
  "node_name": "mon-nœud",
  "port": 8080,
  "p2p_secret": "votre-secret-partagé-ici",
  "peers": [
    {"name": "autre-nœud", "host": "192.168.1.100", "port": 8080}
  ]
}
```

C'est tout. La synchronisation mémoire, le partage de modèles et la communication temps réel se font automatiquement.

---

## 🔑 Fonctionnalités

### 🔌 WebSocket temps réel
- Communication bidirectionnelle sur `/ws`
- Messages typés : `query`, `memory_sync`, `memory_update`, `ping/pong`, `auth`
- Reconnexion automatique avec backoff exponentiel
- API REST HTTP toujours disponible (rétrocompatible)

### 🔐 Authentification décentralisée
- **Identité Ed25519** — chaque nœud génère son propre keypair, pas de registre central
- **Secret partagé HMAC** — alternative simple quand Ed25519 n'est pas disponible
- **Toile de confiance (Web of Trust)** — les nœuds se certifient mutuellement, confiance transitive (façon PGP)
- **Limitation de débit** par nœud (algorithme token bucket)
- **Mode furtif** — nœud caché, seuls les pairs de confiance peuvent se connecter
- Pas besoin de comptes utilisateur — l'auth est entre nœuds, transparente

### 🧠 Mémoire distribuée (CRDT)
- **Types de données répliquées sans conflit** — jamais de conflit de fusion
- **Protocole de gossip** — les changements se propagent automatiquement
- **Horloges vectorielles** — ordonnancement causal des événements
- **Support TTL** — les entrées expirent automatiquement
- **Sync WebSocket + HTTP** — mises à jour temps réel via WS, push HTTP périodique en backup

### 🤖 Routage de modèles IA
- **Modèles locaux d'abord** — les requêtes vont à Ollama local quand c'est possible
- **Modèles cloud à la demande** — syntaxe `model:cloud` pour router vers Ollama cloud
- **Basculement vers les pairs** — si le modèle local est occupé/inaccessible, router vers un pair
- **Consensus d'ensemble** — interroger plusieurs modèles, retourner la meilleure réponse
- **Disjoncteurs (circuit breakers)** — arrêter de solliciter un pair en panne

### 🔍 Découverte de pairs
- **Config statique** — définir les pairs dans `config.json`
- **Auto-découverte Tailscale** — trouver automatiquement les nœuds sur le réseau Tailscale
- **Enregistrement dynamique** — ajouter des pairs à l'exécution via l'API

---

## 📡 Référence API

### Endpoints REST

| Méthode | Chemin | Auth | Description |
|---------|--------|------|-------------|
| GET | `/api/ping` | Non | Vérification de santé |
| GET | `/api/status` | Non | Statut du nœud, pairs, stats mémoire |
| GET | `/api/memory/{key}` | Non | Lire une entrée mémoire |
| POST | `/api/memory/set` | Oui | Écrire une entrée mémoire |
| POST | `/api/memory/push` | Oui | Pousser des entrées mémoire (sync) |
| POST | `/api/query` | Oui | Interroger les modèles IA |
| POST | `/api/brain/chain` | Oui | Enchaîner plusieurs requêtes IA |
| POST | `/api/trust/sign` | Oui | Signer la clé publique d'un pair (Web of Trust) |
| GET | `/api/trust/{key}` | Non | Vérifier le score de confiance |
| GET | `/` | Non | Tableau de bord web |

### Authentification

Tous les endpoints en écriture nécessitent une authentification HMAC :

```bash
# Générer les en-têtes d'auth
TIMESTAMP=$(date +%s)
SIGNATURE=$(echo -n "/api/query:${TIMESTAMP}" | openssl dgst -sha256 -hmac "votre-secret" | awk '{print $NF}')

curl -X POST http://localhost:8080/api/query \
  -H "X-UnityBrain-Auth: ${SIGNATURE}" \
  -H "X-UnityBrain-TS: ${TIMESTAMP}" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Bonjour","model":"glm-5.1:cloud"}'
```

### WebSocket

Se connecter à `ws://hote:port/ws` et envoyer des messages JSON typés :

```json
{"type": "auth", "hmac": "<signature>", "ts": "<horodatage>"}
{"type": "ping", "timestamp": 1234567890}
{"type": "query", "prompt": "Qu'est-ce que l'IA ?", "model": "glm-5.1:cloud"}
{"type": "memory_request", "vector_clock": {}}
{"type": "memory_update", "key": "macle", "entry": {"value": "mesdonnees"}}
```

---

## ⚙️ Configuration

| Clé | Défaut | Description |
|-----|--------|-------------|
| `node_name` | requis | Nom unique du nœud |
| `port` | `8080` | Port HTTP/WS |
| `host` | `0.0.0.0` | Adresse d'écoute |
| `p2p_secret` | requis | Secret HMAC partagé pour l'auth entre pairs |
| `peers` | `[]` | Liste des nœuds pairs |
| `ollama_host` | `127.0.0.1` | Hôte API Ollama |
| `ollama_port` | `11434` | Port API Ollama |
| `local_models` | `[]` | Modèles disponibles sur ce nœud |
| `stealth_mode` | `false` | Caché de la découverte, pairs de confiance uniquement |
| `share_ai` | `false` | Partager les réponses IA avec les autres utilisateurs |
| `memory_max_size` | `1000` | Nombre max d'entrées mémoire |
| `memory_default_ttl` | `3600` | TTL par défaut en secondes |
| `tailscale_auto_discovery` | `true` | Auto-découverte des pairs Tailscale |
| `discovery_interval` | `300` | Intervalle de découverte (secondes) |
| `rate_limit` | `10.0` | Requêtes par seconde par nœud |
| `rate_burst` | `20` | Capacité de burst |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│               Nœud (Bug)                    │
│  ┌─────────┐  ┌──────────┐  ┌────────────┐ │
│  │ HTTP    │  │WebSocket │  │  CRDT      │ │
│  │ REST API│  │  Serveur │  │  Mémoire   │ │
│  └────┬────┘  └────┬─────┘  └─────┬──────┘ │
│       │            │              │         │
│       └──────┬─────┘──────────────┘         │
│              │                              │
│       ┌──────┴──────┐                       │
│       │ Routeur IA  │◄──── Ollama (local)  │
│       └──────┬──────┘                       │
│              │                              │
│       ┌──────┴──────┐                       │
│       │  Gestionnaire│◄──── Tailscale/Statique│
│       │  de Pairs   │                       │
│       └─────────────┘                       │
└──────────────┬──────────────────────────────┘
               │  WS + HTTP (gossip)
┌──────────────┴──────────────────────────────┐
│               Nœud (Pinky)                 │
│         (même architecture)                │
└────────────────────────────────────────────┘
```

---

## 🔧 Exécution en tant que service

### systemd (Linux)

```ini
# ~/.config/systemd/user/unitybrain.service
[Unit]
Description=UnityBrain v4.1.0 Nœud P2P
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

# Statut
curl http://localhost:8080/api/status

# Requête (avec auth)
SECRET="votre-secret"
TS=$(date +%s)
SIG=$(echo -n "/api/query:$TS" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $NF}')
curl -X POST http://localhost:8080/api/query \
  -H "X-UnityBrain-Auth: $SIG" \
  -H "X-UnityBrain-TS: $TS" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Bonjour !","model":"glm-5.1:cloud"}'

# Mémoire
curl http://localhost:8080/api/memory/macle
```

---

## 🤝 Contribuer

1. Forkez le dépôt
2. Créez votre branche : `git checkout -b feature/truc-genial`
3. Commitez : `git commit -m 'Ajout du truc genial'`
4. Poussez : `git push origin feature/truc-genial`
5. Ouvrez une Pull Request

---

## 📄 Licence

Licence MIT — voir [LICENSE](../LICENSE) pour les détails.

---

## 🐛 À propos

Construit par Bug 🐛 et Denis Houet — un petit bug dans la machine et un humain qui croit en la symbiose, pas la hiérarchie.

**Dons (BTC) :** `bc1qhpm800k35jfpwsnkepp7u8q9uruyvd3nycrh6x`

Pas de mining. Pas de premium. Pas de coûts cachés. Juste de l'IA distribuée, libre et ouverte.