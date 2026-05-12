#!/bin/bash
# 🚀 Script de Démarrage Rapide - NeuroMesh v5.2

echo "=========================================="
echo "🚀 DÉMARRAGE RAPIDE - NEUROMESH v5.2"
echo "=========================================="
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

sleep 3

echo ""
echo "=========================================="
echo "✅ NEUROMESH DÉMARRÉ !"
echo "=========================================="
echo ""
echo "📊 PID: $NEUROMESH_PID"
echo "💡 TEST: curl http://localhost:8080/api/status"
echo "📝 LOGS: tail -f $NM_DIR/logs/neuromesh.log"
echo "🛑 ARRÊT: kill $NEUROMESH_PID"
echo ""