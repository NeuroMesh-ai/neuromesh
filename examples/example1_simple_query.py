#!/usr/bin/env python3
"""
Exemple 1: UnityBrain Simple Query
"""

import asyncio
import sys
import os

# Ajouter le chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.unitybrain_v3_final import UnityBrain, Peer


async def main():
    """Exemple simple"""

    print("=" * 70)
    print("EXEMPLE 1: UnityBrain - Requête Simple")
    print("=" * 70)

    # Créer UnityBrain
    unitybrain = UnityBrain()

    # Ajouter un peer local
    peer = Peer(
        name="LocalPeer",
        host="127.0.0.1",
        port=11434,  # Ollama default
        models=["SmolLM2:1.7b", "phi3:mini"]
    )

    await unitybrain.add_peer(peer)

    # Initialiser
    print("\n⚙️ Initialisation...")
    await unitybrain.initialize()

    # Faire une requête
    print("\n📝 Requête: 'Qu'est-ce que UnityBrain ?'")
    result = await unitybrain.query("Qu'est-ce que UnityBrain ?")

    if result["status"] == "success":
        print(f"\n✅ Succès !")
        print(f"   Peer: {result['peer']}")
        print(f"   Model: {result['model']}")
        print(f"   Latence: {result['latency']:.0f}ms")
        print(f"\n💬 Réponse:\n{result['response']}")
    else:
        print(f"\n❌ Erreur: {result}")

    # Statistiques
    print(f"\n📊 Statistiques:")
    print(f"   Queries: {len(unitybrain.query_history.queries)}")
    print(f"   Peers: {len(unitybrain.peers)}")


if __name__ == '__main__':
    asyncio.run(main())