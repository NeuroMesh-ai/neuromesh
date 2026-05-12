#!/bin/bash
# 🚀 Script de Démarrage Rapide - Bug uniquement

echo "="
echo "🚀 DÉMARRAGE RAPIDE - NEUROMESH v5.2"
echo "="
echo ""

WORKSPACE="/home/user/.openclaw/workspace"
NM_DIR="$WORKSPACE/NeuroMesh"

# Arrêter les services existants
echo "🛑 Arrêt des services existants..."
pkill -f "neuromesh_v5.py" 2>/dev/null || true
sleep 2

# Démarrer NeuroMesh
echo "🌐 Démarrage de NeuroMesh..."
cd "$NM_DIR"
python3 src/neuromesh_v5.py &
NEUROMESH_PID=$!
echo $NEUROMESH_PID > logs/neuromesh.pid
echo "✅ NeuroMesh démarré (PID: $NEUROMESH_PID)"

# Attendre un peu
sleep 3

echo ""
echo "="
echo "✅ SERVICES DÉMARRÉS !"
echo "="
echo ""
echo "📊 STATUT:"
echo "  NeuroMesh: PID $NEUROMESH_PID"
echo ""
echo "💡 POUR TESTER:"
echo "  curl http://localhost:8080/api/status"
echo ""
echo "📝 LOGS:"
echo "  tail -f logs/neuromesh.log"
echo ""
echo "🛑 POUR ARRÊTER:"
echo "  kill $NEUROMESH_PID"
echo ""
echo "🎉 Prêt !"
echo ""
echo "="