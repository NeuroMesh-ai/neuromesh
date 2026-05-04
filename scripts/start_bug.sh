#!/bin/bash
# 🚀 Script de Démarrage Rapide - Bug uniquement

echo "="
echo "🚀 DÉMARRAGE RAPIDE - UNITYBRAIN & BUGBRAIN v3.0"
echo "="
echo ""

WORKSPACE="/home/user/.openclaw/workspace"
UB_DIR="$WORKSPACE/Unitybrain"

# Arrêter les services existants
echo "🛑 Arrêt des services existants..."
pkill -f "unitybrain_v4.py" 2>/dev/null || true
pkill -f "bugbrain_v3_final.py" 2>/dev/null || true
sleep 2

# Démarrer UnityBrain
echo "🌐 Démarrage d'UnityBrain..."
cd "$UB_DIR"
python3 src/unitybrain_v4.py &
UNITYBRAIN_PID=$!
echo $UNITYBRAIN_PID > logs/unitybrain.pid
echo "✅ UnityBrain démarré (PID: $UNITYBRAIN_PID)"

# Attendre un peu
sleep 3

# Démarrer BugBrain
echo "🧠 Démarrage de BugBrain..."
python3 src/bugbrain_v3_final.py &
BUGBRAIN_PID=$!
echo $BUGBRAIN_PID > logs/bugbrain.pid
echo "✅ BugBrain démarré (PID: $BUGBRAIN_PID)"

# Attendre un peu
sleep 2

echo ""
echo "="
echo "✅ SERVICES DÉMARRÉS !"
echo "="
echo ""
echo "📊 STATUT:"
echo "  UnityBrain: PID $UNITYBRAIN_PID"
echo "  BugBrain: PID $BUGBRAIN_PID"
echo ""
echo "💡 POUR TESTER:"
echo "  python3 src/interactive_interface.py"
echo ""
echo "📝 LOGS:"
echo "  tail -f logs/unitybrain.log"
echo "  tail -f logs/bugbrain.log"
echo ""
echo "🛑 POUR ARRÊTER:"
echo "  kill $UNITYBRAIN_PID $BUGBRAIN_PID"
echo ""
echo "🎉 Prêt à tester !"
echo ""
echo "="