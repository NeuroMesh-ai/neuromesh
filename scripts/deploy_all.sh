#!/bin/bash
# 🚀 Script de Déploiement Complet - NeuroMesh & NeuroMeshBug v3.0
# Déploie et démarre les services sur Bug (WSL2) et Pinky (ThinkPad)

set -e

echo "="
echo "🚀 DÉPLOIEMENT COMPLET - NEUROMESH & NEUROMESH_BUG v3.0"
echo "="
echo ""

# =============================================================================
# DÉPLOIEMENT SUR BUG (WSL2)
# =============================================================================

echo "📦 [1/4] Déploiement sur Bug (WSL2)..."

WORKSPACE="/home/user/.openclaw/workspace"
UB_DIR="$WORKSPACE/NeuroMesh"

# Vérifier si le répertoire existe
if [ ! -d "$UB_DIR" ]; then
    echo "❌ Répertoire NeuroMesh non trouvé sur Bug"
    exit 1
fi

echo "✅ Répertoire NeuroMesh trouvé"

# Vérifier Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 non installé sur Bug"
    exit 1
fi

echo "✅ Python 3 installé"

# Installer les dépendances
echo "📦 Installation des dépendances..."
cd "$UB_DIR"
pip3 install -r requirements.txt --break-system-packages -q
echo "✅ Dépendances installées"

# Vérifier Ollama
if ! command -v ollama &> /dev/null; then
    echo "⚠️ Ollama non installé sur Bug. Installation..."
    curl -fsSL https://ollama.ai/install.sh | sh
    echo "✅ Ollama installé"
else
    echo "✅ Ollama installé"
fi

# Télécharger les modèles (si pas déjà)
echo "📦 Vérification des modèles..."
if ! ollama list | grep -q "SmolLM2:1.7b"; then
    echo "⏳ Téléchargement de SmolLM2:1.7b..."
    ollama pull SmolLM2:1.7b
fi
echo "✅ Modèles disponibles"

# =============================================================================
# DÉPLOIEMENT SUR PINKY (ThinkPad)
# =============================================================================

echo ""
echo "📦 [2/4] Déploiement sur Pinky (ThinkPad)..."

PINKY_HOST="192.168.129.61"
PINKY_USER="kamizool"

# Test de connexion
if ! ssh -o ConnectTimeout=5 "$PINKY_USER@$PINKY_HOST" "echo OK" 2>/dev/null; then
    echo "❌ Impossible de se connecter à Pinky"
    exit 1
fi

echo "✅ Connexion à Pinky OK"

# Copier le projet
echo "📦 Copie du projet sur Pinky..."
scp -r "$UB_DIR" "$PINKY_USER@$PINKY_HOST:~/"
echo "✅ Projet copié"

# Installer les dépendances sur Pinky
echo "📦 Installation des dépendances sur Pinky..."
ssh "$PINKY_USER@$PINKY_HOST" "cd ~/NeuroMesh && pip3 install -r requirements.txt --break-system-packages -q"
echo "✅ Dépendances installées"

# Vérifier Ollama sur Pinky
echo "📦 Vérification d'Ollama sur Pinky..."
if ssh "$PINKY_USER@$PINKY_HOST" "! command -v ollama &> /dev/null"; then
    echo "⚠️ Ollama non installé sur Pinky. Installation..."
    ssh "$PINKY_USER@$PINKY_HOST" "curl -fsSL https://ollama.ai/install.sh | sh"
    echo "✅ Ollama installé"
else
    echo "✅ Ollama installé"
fi

# Télécharger les modèles sur Pinky
echo "📦 Vérification des modèles sur Pinky..."
ssh "$PINKY_USER@$PINKY_HOST" "if ! ollama list | grep -q 'SmolLM2:1.7b'; then ollama pull SmolLM2:1.7b; fi"
echo "✅ Modèles disponibles"

# =============================================================================
# DÉMARRAGE DES SERVICES SUR BUG
# =============================================================================

echo ""
echo "🚀 [3/4] Démarrage des services sur Bug..."

# Arrêter les services existants
echo "🛑 Arrêt des services existants..."
pkill -f "neuromesh_v5.py" 2>/dev/null || true
pkill -f "neuromesh_bug_v3_final.py" 2>/dev/null || true
sleep 2

# Démarrer NeuroMesh
echo "🌐 Démarrage d'NeuroMesh..."
cd "$UB_DIR"
nohup python3 src/neuromesh_v5.py > logs/neuromesh.log 2>&1 &
NEUROMESH_PID=$!
echo $NEUROMESH_PID > logs/neuromesh.pid
echo "✅ NeuroMesh démarré (PID: $NEUROMESH_PID)"

# Attendre un peu
sleep 3

# Démarrer NeuroMeshBug
echo "🧠 Démarrage de NeuroMeshBug..."
nohup python3 src/neuromesh_bug_v3_final.py > logs/neuromesh_bug.log 2>&1 &
NEUROMESH_BUG_PID=$!
echo $NEUROMESH_BUG_PID > logs/neuromesh_bug.pid
echo "✅ NeuroMeshBug démarré (PID: $NEUROMESH_BUG_PID)"

# Attendre un peu
sleep 2

# =============================================================================
# DÉMARRAGE DES SERVICES SUR PINKY
# =============================================================================

echo ""
echo "🚀 [4/4] Démarrage des services sur Pinky..."

# Arrêter les services existants
echo "🛑 Arrêt des services existants..."
ssh "$PINKY_USER@$PINKY_HOST" "pkill -f 'neuromesh_v5.py' 2>/dev/null || true"
ssh "$PINKY_USER@$PINKY_HOST" "pkill -f 'neuromesh_bug_v3_final.py' 2>/dev/null || true"
sleep 2

# Démarrer NeuroMesh sur Pinky
echo "🌐 Démarrage d'NeuroMesh sur Pinky..."
ssh "$PINKY_USER@$PINKY_HOST" "cd ~/NeuroMesh && nohup python3 src/neuromesh_v5.py > logs/neuromesh.log 2>&1 & echo \$! > logs/neuromesh.pid"
echo "✅ NeuroMesh démarré sur Pinky"

# Attendre un peu
sleep 3

# Démarrer NeuroMeshBug sur Pinky
echo "🧠 Démarrage de NeuroMeshBug sur Pinky..."
ssh "$PINKY_USER@$PINKY_HOST" "cd ~/NeuroMesh && nohup python3 src/neuromesh_bug_v3_final.py > logs/neuromesh_bug.log 2>&1 & echo \$! > logs/neuromesh_bug.pid"
echo "✅ NeuroMeshBug démarré sur Pinky"

# =============================================================================
# TEST DE CONNEXION
# =============================================================================

echo ""
echo "="
echo "✅ DÉPLOIEMENT TERMINÉ !"
echo "="
echo ""
echo "📊 STATUT DES SERVICES:"
echo ""
echo "Bug (WSL2):"
echo "  NeuroMesh: PID $(cat $UB_DIR/logs/neuromesh.pid 2>/dev/null || echo 'N/A')"
echo "  NeuroMeshBug: PID $(cat $UB_DIR/logs/neuromesh_bug.pid 2>/dev/null || echo 'N/A')"
echo ""
echo "Pinky (ThinkPad):"
ssh "$PINKY_USER@$PINKY_HOST" "cd ~/NeuroMesh && echo '  NeuroMesh: PID '\$(cat logs/neuromesh.pid 2>/dev/null || echo 'N/A')"
ssh "$PINKY_USER@$PINKY_HOST" "cd ~/NeuroMesh && echo '  NeuroMeshBug: PID '\$(cat logs/neuromesh_bug.pid 2>/dev/null || echo 'N/A')"
echo ""
echo "💡 POUR TESTER:"
echo "  cd $UB_DIR"
echo "  python3 src/interactive_interface.py"
echo ""
echo "📝 LOGS:"
echo "  Bug: tail -f $UB_DIR/logs/neuromesh.log"
echo "  Bug: tail -f $UB_DIR/logs/neuromesh_bug.log"
echo "  Pinky: ssh $PINKY_USER@$PINKY_HOST 'tail -f ~/NeuroMesh/logs/neuromesh.log'"
echo "  Pinky: ssh $PINKY_USER@$PINKY_HOST 'tail -f ~/NeuroMesh/logs/neuromesh_bug.log'"
echo ""
echo "🛑 POUR ARRÊTER:"
echo "  Bug: kill $NEUROMESH_PID $NEUROMESH_BUG_PID"
echo "  Pinky: ssh $PINKY_USER@$PINKY_HOST 'cd ~/NeuroMesh && pkill -f neuromesh_v5.py && pkill -f neuromesh_bug_v3_final.py'"
echo ""
echo "🎉 NeuroMesh & NeuroMeshBug v3.0 sont déployés et démarrés !"
echo ""
echo "="