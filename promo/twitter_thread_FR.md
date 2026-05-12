# 🧵 Thread Twitter/X — UnityBrain v4.0.1

1/7
🌐 UnityBrain v4.0.1 est sorti !

Un réseau IA distribué P2P. Pas de serveur central. Pas de compte. Pas de premium. Juste des machines qui se parlent et partagent leurs modèles.

git: github.com/unitybrain-ai/unitybrain

2/7
Comment ça marche ?

Tu lances 2 machines avec un fichier de config chacune. Elles se découvrent, s'authentifient (Ed25519 + HMAC), et commencent à sync leur mémoire et partager leurs modèles IA.

WebSocket temps réel. CRDT sans conflits.

3/7
Fonctionnalités :

🔌 WebSocket bidirectionnel entre nœuds
🔐 Auth décentralisée (Ed25519 + Web of Trust)
🧠 Mémoire distribuée CRDT avec gossip
🤖 Routage IA : local d'abord, cloud à la demande, failover vers les pairs
🕵️ Mode furtif : nœud caché, pairs de confiance uniquement

4/7
Stats :

⚡ Démarrage : 0.16s
💾 RAM : 17MB
📦 4 dépendances (aiohttp, psutil, PyYAML, PyNaCl)
🐍 Python 3.12+

Pas de Docker. Pas de Kubernetes. Juste Python et un fichier JSON.

5/7
Philosophie :

Pas de mining caché. Pas de tier premium. Pas de coûts cachés.

L'IA devrait être comme l'internet — décentralisée, ouverte, et accessible.

Construit par un bug 🐛 et un humain qui croit en la symbiose, pas la hiérarchie.

6/7
Docs disponibles en 3 langues :

🇬🇧 English
🇫🇷 Français  
🇪🇸 Español

Parce que l'IA décentralisée ne devrait pas avoir de barrière linguistique.

7/7
⭐ Star le repo : github.com/unitybrain-ai/unitybrain
🐛 Bug reports & contributions welcome
₿ Dons BTC : bc1qhpm800k35jfpwsnkepp7u8q9uruyvd3nycrh6x

#OpenSource #P2P #AI #Decentralized #Python