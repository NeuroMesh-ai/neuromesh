#!/bin/bash
# 🚀 Script de Démarrage Rapide - Bug uniquement

echo "="
echo "🚀 DÉMARRAGE RAPIDE - NEUROMESH & NEUROMESH_BUG v3.0"
echo "="
echo ""

WORKSPACE="/home/user/.openclaw/workspace"
UB_DIR="$WORKSPACE/NeuroMesh"

# Arrêter les services existants
echo "🛑 Arrêt des services existants..."
pkill -f "neuromesh_v4.py" 2>/dev/null || true
pkill -f "neuromesh_bug_v3_final.py" 2>/dev/null || true
sleep 2

# Démarrer NeuroMesh
echo "🌐 Démarrage d'NeuroMesh..."
cd "$UB_DIR"
python3 src/neuromesh_v4.py &
NEUROMESH_PID=$!
echo $NEUROMESH_PID > logs/neuromesh.pid
echo "✅ NeuroMesh démarré (PID: $NEUROMESH_PID)"

# Attendre un peu
sleep 3

# Démarrer NeuroMeshBug
echo "🧠 Démarrage de NeuroMeshBug..."
python3 src/neuromesh_bug_v3_final.py &
NEUROMESH_BUG_PID=$!
echo $NEUROMESH_BUG_PID > logs/neuromesh_bug.pid
echo "✅ NeuroMeshBug démarré (PID: $NEUROMESH_BUG_PID)"

# Attendre un peu
sleep 2

echo ""
echo "="
echo "✅ SERVICES DÉMARRÉS !"
echo "="
echo ""
echo "📊 STATUT:"
echo "  NeuroMesh: PID $NEUROMESH_PID"
echo "  NeuroMeshBug: PID $NEUROMESH_BUG_PID"
echo ""
echo "💡 POUR TESTER:"
echo "  python3 src/interactive_interface.py"
echo ""
echo "📝 LOGS:"
echo "  tail -f logs/neuromesh.log"
echo "  tail -f logs/neuromesh_bug.log"
echo ""
echo "🛑 POUR ARRÊTER:"
echo "  kill $NEUROMESH_PID $NEUROMESH_BUG_PID"
echo ""
echo "🎉 Prêt à tester !"
echo ""
echo "="