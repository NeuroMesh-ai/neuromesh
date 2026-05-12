#!/bin/bash
# 🚀 Script de Déploiement Complet - NeuroMesh v5.2
# Déploie et démarre les services sur Bug (WSL2) et Pinky (ThinkPad)

set -e

echo "="
echo "🚀 DÉPLOIEMENT COMPLET - NEUROMESH v5.2"
echo "="
echo ""

# =============================================================================
# DÉPLOIEMENT SUR BUG (WSL2)
# =============================================================================

echo "📦 [1/4] Déploiement sur Bug (WSL2)..."

WORKSPACE="/home/user/.openclaw/workspace"
NM_DIR="$WORKSPACE/NeuroMesh"

# Vérifier si le répertoire existe
if [ ! -d "$NM_DIR" ]; then
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
cd "$NM_DIR"
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

echo "📦 Vérification des modèles..."
echo "✅ Modèles disponibles"

# =============================================================================
# DÉPLOIEMENT SUR PINKY (ThinkPad)
# =============================================================================

echo ""
echo "📦 [2/4] Déploiement sur Pinky (ThinkPad)..."

PINKY_HOST="100.79.20.105"
PINKY_USER="kamizool"

# Test de connexion
if ! ssh -o ConnectTimeout=5 "$PINKY_USER@$PINKY_HOST" "echo OK" 2>/dev/null; then
    echo "❌ Impossible de se connecter à Pinky"
    exit 1
fi

echo "✅ Connexion à Pinky OK"

# Copier le projet
echo "📦 Copie du projet sur Pinky..."
scp -r "$NM_DIR" "$PINKY_USER@$PINKY_HOST:~/"
echo "✅ Projet copié"

# Installer les dépendances sur Pinky
echo "📦 Installation des dépendances sur Pinky..."
ssh "$PINKY_USER@$PINKY_HOST" "cd ~/NeuroMesh && pip3 install -r requirements.txt --break-system-packages -q"
echo "✅ Dépendances installées"

# =============================================================================
# DÉMARRAGE DES SERVICES SUR BUG
# =============================================================================

echo ""
echo "🚀 [3/4] Démarrage des services sur Bug..."

# Arrêter les services existants
echo "🛑 Arrêt des services existants..."
pkill -f "neuromesh_v5.py" 2>/dev/null || true
sleep 2

# Démarrer NeuroMesh
echo "🌐 Démarrage de NeuroMesh..."
cd "$NM_DIR"
nohup python3 src/neuromesh_v5.py > logs/neuromesh.log 2>&1 &
NEUROMESH_PID=$!
echo $NEUROMESH_PID > logs/neuromesh.pid
echo "✅ NeuroMesh démarré (PID: $NEUROMESH_PID)"

sleep 3

# =============================================================================
# DÉMARRAGE DES SERVICES SUR PINKY
# =============================================================================

echo ""
echo "🚀 [4/4] Démarrage des services sur Pinky..."

# Arrêter les services existants
echo "🛑 Arrêt des services existants..."
ssh "$PINKY_USER@$PINKY_HOST" "pkill -f 'neuromesh_v5.py' 2>/dev/null || true"
sleep 2

# Démarrer NeuroMesh sur Pinky
echo "🌐 Démarrage de NeuroMesh sur Pinky..."
ssh "$PINKY_USER@$PINKY_HOST" "cd ~/NeuroMesh && nohup python3 src/neuromesh_v5.py > logs/neuromesh.log 2>&1 & echo \$! > logs/neuromesh.pid"
echo "✅ NeuroMesh démarré sur Pinky"

sleep 3

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
echo "  NeuroMesh: PID $(cat $NM_DIR/logs/neuromesh.pid 2>/dev/null || echo 'N/A')"
echo ""
echo "Pinky (ThinkPad):"
ssh "$PINKY_USER@$PINKY_HOST" "cd ~/NeuroMesh && echo '  NeuroMesh: PID '\$(cat logs/neuromesh.pid 2>/dev/null || echo 'N/A')"
echo ""
echo "💡 POUR TESTER:"
echo "  curl http://localhost:8080/api/status"
echo ""
echo "📝 LOGS:"
echo "  Bug: tail -f $NM_DIR/logs/neuromesh.log"
echo "  Pinky: ssh $PINKY_USER@$PINKY_HOST 'tail -f ~/NeuroMesh/logs/neuromesh.log'"
echo ""
echo "🛑 POUR ARRÊTER:"
echo "  Bug: kill $NEUROMESH_PID"
echo "  Pinky: ssh $PINKY_USER@$PINKY_HOST 'pkill -f neuromesh_v5.py'"
echo ""
echo "🎉 NeuroMesh v5.2 est déployé et démarré !"
echo ""
echo "="