#!/usr/bin/env python3
"""
Exemple 1: NeuroMesh Simple Query
"""

import asyncio
import sys
import os

# Ajouter le chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.neuromesh_v3_final import NeuroMesh, Peer


async def main():
    """Exemple simple"""

    print("=" * 70)
    print("EXEMPLE 1: NeuroMesh - Requête Simple")
    print("=" * 70)

    # Créer NeuroMesh
    neuromesh = NeuroMesh()

    # Ajouter un peer local
    peer = Peer(
        name="LocalPeer",
        host="127.0.0.1",
        port=11434,  # Ollama default
        models=["SmolLM2:1.7b", "phi3:mini"]
    )

    await neuromesh.add_peer(peer)

    # Initialiser
    print("\n⚙️ Initialisation...")
    await neuromesh.initialize()

    # Faire une requête
    print("\n📝 Requête: 'Qu'est-ce que NeuroMesh ?'")
    result = await neuromesh.query("Qu'est-ce que NeuroMesh ?")

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
    print(f"   Queries: {len(neuromesh.query_history.queries)}")
    print(f"   Peers: {len(neuromesh.peers)}")


if __name__ == '__main__':
    asyncio.run(main())