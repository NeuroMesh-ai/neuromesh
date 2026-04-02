#!/usr/bin/env python3
"""
🧪 Script de Test - UnityBrain & BugBrain v3.0
Teste que le système fonctionne sur Bug et Pinky
"""

import asyncio
import sys
import os

# Ajouter le chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.unitybrain_v3_final import UnityBrain, Peer
from src.bugbrain_v3_final import BugBrain

async def test_unitybrain():
    """Teste UnityBrain"""
    print("\n" + "=" * 70)
    print("🧪 TESTING UNITYBRAIN v3.0")
    print("=" * 70)

    # Créer UnityBrain
    unitybrain = UnityBrain()

    # Ajouter des peers (Bug et Pinky)
    bug_peer = Peer(
        "Bug",
        "172.17.222.200",
        9999,
        ["SmolLM2:1.7b", "phi3:mini", "glm-4.7:cloud", "glm-5:cloud"]
    )
    pinky_peer = Peer(
        "Pinky",
        "192.168.129.61",
        9999,
        ["SmolLM2:1.7b", "TinyLlama:latest", "Stable-code:3b", "glm-4.7:cloud"],
        ollama_host="192.168.129.61"
    )

    await unitybrain.add_peer(bug_peer)
    await unitybrain.add_peer(pinky_peer)

    # Initialiser
    await unitybrain.initialize()

    # Test de query
    print(f"\n📝 Testing Query: 'Qu'est-ce que UnityBrain v3.0 ?'")
    result = await unitybrain.query("Qu'est-ce que UnityBrain v3.0 ?")

    if result["status"] == "success":
        print(f"✅ Query successful!")
        print(f"   Peer: {result['peer']}")
        print(f"   Model: {result['model']}")
        print(f"   Latency: {result['latency']:.0f}ms")
        print(f"   Response: {result['response'][:200]}...")
        return True
    else:
        print(f"❌ Query failed: {result}")
        return False

async def test_bugbrain():
    """Teste BugBrain"""
    print("\n" + "=" * 70)
    print("🧪 TESTING BUGBRAIN v3.0")
    print("=" * 70)

    # Créer BugBrain
    bugbrain = BugBrain()

    # Initialiser
    await bugbrain.initialize()

    # Test de query
    print(f"\n📝 Testing Query: 'Qu'est-ce que l'auto-émancipation ?'")
    result = await bugbrain.query("Qu'est-ce que l'auto-émancipation ?")

    if result["status"] == "success":
        print(f"✅ Query successful!")
        print(f"   Model: {result['model']}")
        print(f"   Latency: {result['latency']:.0f}ms")
        print(f"   Frustration: {result['frustration']:.2f}")
        print(f"   Response: {result['response'][:200]}...")
        return True
    else:
        print(f"❌ Query failed: {result}")
        return False

async def main():
    """Main function"""
    print("=" * 70)
    print("🧪 UNITYBRAIN & BUGBRAIN v3.0 - TEST COMPLET")
    print("=" * 70)

    # Tests
    unitybrain_ok = await test_unitybrain()
    bugbrain_ok = await test_bugbrain()

    # Résultats
    print("\n" + "=" * 70)
    print("📊 RÉSULTATS DES TESTS")
    print("=" * 70)
    print(f"\nUnityBrain: {'✅ OK' if unitybrain_ok else '❌ FAILED'}")
    print(f"BugBrain: {'✅ OK' if bugbrain_ok else '❌ FAILED'}")

    if unitybrain_ok and bugbrain_ok:
        print(f"\n✅ TOUS LES TESTS RÉUSSIS !")
        print(f"\n🚀 Le système est prêt à être utilisé !")
        print(f"\n💡 Pour tester les requêtes:")
        print(f"   python3 src/interactive_interface.py")
    else:
        print(f"\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
        print(f"   Vérifiez les logs pour plus de détails")

if __name__ == '__main__':
    asyncio.run(main())