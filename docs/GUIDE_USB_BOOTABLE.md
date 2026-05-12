# 🔧 NEUROMESH_BUG USB BOOTABLE - Guide de Création

## 🎯 Objectif

Créer une clé USB bootable avec NeuroMeshAgent/NeuroMesh préinstallé - **plug & play** sur n'importe quelle machine !

---

## 📋 Prérequis

### Pour créer la clé USB:
- **Linux** (Ubuntu, Debian, Fedora, etc.)
- **Accès root** (sudo)
- **Clé USB** (min 8GB, 16GB recommandé)
- **Outils:**
  - `genisoimage`
  - `xorriso`
  - `mtools`
  - `grub2`
  - `squashfs-tools`

### Pour utiliser la clé USB:
- **N'importe quel ordinateur** (PC/Mac/Linux)
- **Port USB**
- **Optionnel:** connexion internet (pour modèles P2P)

---

## 🚀 Méthode 1: Script Automatisé (Recommandé)

### Étape 1: Identifier votre clé USB

```bash
# Insérez la clé USB
# Lister les périphériques
lsblk

# Identifiez votre clé USB (ex: sdb, sdc, sdd...)
# NOTE: Attention à ne PAS vous tromper de disque !
```

### Étape 2: Exécuter le script

```bash
cd /home/user/.openclaw/workspace/NeuroMesh/scripts

sudo chmod +x create_neuromesh_bug_usb.sh

sudo ./create_neuromesh_bug_usb.sh /dev/sdX
```

Remplacez `/dev/sdX` par votre périphérique (ex: `/dev/sdb`).

### Étape 3: Attendre la fin

Le script va:
1. ✅ Créer l'image ISO
2. ✅ Copier NeuroMeshAgent
3. ✅ Configurer GRUB
4. ✅ Écrire sur la clé USB
5. ✅ Nettoyer les fichiers temporaires

**Temps estimé:** 10-20 minutes

---

## 🚀 Méthode 2: Manuel

### Étape 1: Télécharger l'ISO

Depuis GitHub:
```bash
wget https://github.com/NeuroMesh-ai/neuromesh/releases/download/v3.0.0/neuromesh_bug-3.0.0.iso
```

### Étape 2: Graver sur la clé USB

#### Linux:
```bash
# Identifier la clé USB
lsblk

# Graver
sudo dd if=neuromesh_bug-3.0.0.iso of=/dev/sdX bs=4M status=progress conv=fdatasync
```

#### Mac:
```bash
# Identifier la clé USB
diskutil list

# Graver
sudo dd if=neuromesh_bug-3.0.0.iso of=/dev/rdiskX bs=4m
```

#### Windows:
Utiliser **Rufus** ou **Etcher**:
1. Télécharger Rufus: https://rufus.ie/
2. Sélectionner l'ISO
3. Sélectionner la clé USB
4. Cliquer "Start"

---

## 💾 Contenu de la Clé USB

```
📁 neuromesh_bug-usb/
├─ 📄 README.txt                   (Instructions)
├─ 🚀 start_neuromesh_bug.sh            (Démarrage auto)
├─ 📁 NeuroMesh/                  (Code source)
│  ├─ 📄 README.md
│  ├─ 📁 src/
│  ├─ 📁 docs/
│  ├─ 📁 examples/
│  └─ 📁 scripts/
└─ 🐧 Ollama (installé auto)
```

---

## 🔧 Utilisation

### 1. Boot sur la clé USB

#### BIOS/UEFI:
1. Insérer la clé USB
2. Redémarrer l'ordinateur
3. Entrer dans le BIOS (F2, F12, Delete, ou ESC)
4. Sélectionner la clé USB comme périphérique de boot
5. Démarrer

#### Mac:
1. Insérer la clé USB
2. Redémarrer en maintenant la touche Option (⌥)
3. Sélectionner "EFI Boot"
4. Démarrer

### 2. Menu GRUB

Au démarrage, vous verrez le menu GRUB:

```
🐛 NeuroMeshAgent v3.0 - Boot Menu
================================

1. 🐛 NeuroMeshAgent v3.0 - Démarrage automatique
2. 🐛 NeuroMeshAgent v3.0 - Démarrage (verbose)
3. 🔧 Setup interactif
4. 💻 Shell (dépannage)
```

Choisissez l'option souhaitée.

### 3. Démarrage Automatique

NeuroMeshAgent va:
1. 🧠 Démarrer Ollama (si non installé)
2. 📥 Télécharger les modèles (SmolLM2:1.7b, phi3:mini)
3. 🚀 Lancer NeuroMeshAgent
4. 🌐 Se connecter au réseau P2P

**Premier démarrage:** ~10-15 minutes (téléchargement des modèles)
**Démarrages suivants:** ~30 secondes

### 4. Setup Interactif

Pour configurer NeuroMeshAgent:

```bash
cd /rootfs/NeuroMesh

python3 scripts/setup_interactive.py
```

Le setup va vous guider pour:
- Nom de l'agent
- Langue et timezone
- Configuration Ollama
- Clés API (optionnel)
- Configuration P2P
- Activation auto-support

### 5. Utilisation

Pour utiliser NeuroMeshAgent:

```bash
cd /rootfs/NeuroMesh

python3 -m src.neuromesh_v5
```

Ou utilisez les exemples:

```bash
# Simple query
python3 examples/example1_simple_query.py

# Ensemble query
python3 examples/example2_ensemble_query.py

# NeuroMeshAgent emancipation
python3 examples/example3_neuromesh_bug_emancipation.py
```

### 6. Auto-Support

Pour poser des questions de support:

```bash
cd /rootfs/NeuroMesh

python3 -m src.auto_support
```

NeuroMeshAgent répondra lui-même à vos questions !

---

## 🔍 Dépannage

### La clé USB ne boot pas

**Solutions:**
- Vérifier que le BIOS/UEFI supporte le boot USB
- Désactiver "Secure Boot" dans le BIOS
- Essayer un autre port USB
- Vérifier que la clé USB est bien gravée

### Ollama ne démarre pas

**Solutions:**
```bash
# Réinstaller Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Démarrer manuellement
ollama serve &
```

### Les modèles ne se téléchargent pas

**Solutions:**
```bash
# Télécharger manuellement
ollama pull SmolLM2:1.7b
ollama pull phi3:mini

# Vérifier la connexion internet
ping -c 4 google.com
```

### Pas assez d'espace disque

**Solutions:**
- Utiliser une clé USB de 16GB ou 32GB
- Désactiver le swap sur le live USB
- Installer sur le disque dur au lieu de la clé USB

---

## 📊 Spécifications

### Minimum Requis:
- **RAM:** 2GB
- **CPU:** x86_64 (Intel/AMD)
- **Stockage:** 8GB USB
- **Internet:** Optionnel (pour P2P)

### Recommandé:
- **RAM:** 4GB+
- **CPU:** 4+ cœurs
- **Stockage:** 16GB+ USB
- **Internet:** Oui (P2P complet)

---

## 🎯 Cas d'Usage

### 1. Démonstration rapide
- Insérer la clé USB
- Boot
- NeuroMeshAgent démarre automatiquement
- Prêt en 30 secondes

### 2. Atelier/Formation
- Distribuer des clés USB aux participants
- Chacun boot sur sa clé
- NeuroMeshAgent prêt à l'usage immédiat

### 3. Test sans installation
- Tester NeuroMeshAgent sans l'installer
- Aucun risque pour la machine hôte
- Retrait de la clé = suppression complète

### 4. Dépannage
- Démarrer sur une machine problématique
- Utiliser NeuroMeshAgent pour diagnostiquer
- Auto-support intégré

### 5. Production (si persistant)
- Installer NeuroMeshAgent sur le disque dur
- Configurer pour démarrage automatique
- NeuroMeshAgent devient un service

---

## 💡 Astuces

1. **Sauvegarder la configuration:**
   ```bash
   cp /rootfs/NeuroMesh/config.json /rootfs/config_backup.json
   ```

2. **Personnaliser le menu GRUB:**
   ```bash
   nano /boot/grub/grub.cfg
   ```

3. **Ajouter des modèles:**
   ```bash
   ollama pull llama3:8b
   ```

4. **Logs:**
   ```bash
   # Voir les logs de NeuroMeshAgent
   tail -f /rootfs/NeuroMesh/logs/neuromesh_bug.log

   # Voir les logs d'auto-support
   tail -f /rootfs/NeuroMesh/logs/auto_support.log
   ```

5. **Mettre à jour:**
   ```bash
   cd /rootfs/NeuroMesh
   git pull
   ```

---

## 🔒 Sécurité

- ✅ NeuroMeshAgent tourne en mode "live" - aucun changement persistant
- ✅ Modèles téléchargés depuis Ollama officiel
- ✅ Pas de données sensibles sur la clé USB
- ✅ Réseau P2P sécurisé (signatures Ed25519)

---

## 📞 Support

Questions ? **NeuroMeshAgent répond lui-même !**

```bash
python3 -m src.auto_support
```

Ou consulter la documentation:
- `/rootfs/NeuroMesh/README.md`
- `/rootfs/NeuroMesh/docs/`

---

## 🚀 Prochaines Étapes

Après avoir testé la clé USB:

1. ✅ Créer plusieurs clés USB
2. 📢 Distribuer à la communauté
3. 🎯 Organiser des ateliers
4. 📄 Créer des tutoriels vidéo
5. 🌍 Publier sur GitHub

---

_Créé par NeuroMeshAgent 🐛 avec l'idée géniale de Denis Houet_
_Plug & Play sur n'importe quelle machine !_