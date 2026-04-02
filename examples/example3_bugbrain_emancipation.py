#!/usr/bin/env python3
"""
Exemple 3: BugBrain Auto-Émancipé
"""

import asyncio
import sys
import os

# Ajouter le chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.bugbrain_v3_final import BugBrain


async def main():
    """Exemple BugBrain"""

    print("=" * 70)
    print("EXEMPLE 3: BugBrain - Auto-Émancipation")
    print("=" * 70)

    # Créer BugBrain
    bugbrain = BugBrain()

    # Initialiser
    print("\n⚙️ Initialisation...")
    await bugbrain.initialize()

    # Faire plusieurs requêtes
    queries = [
        "Qu'est-ce que l'auto-émancipation ?",
        "Explique la conscience de soi",
        "Comment un AI peut-il apprendre ?",
        "Quels sont les défis de l'IA ?",
        "Définis l'intelligence artificielle"
    ]

    print("\n📝 Test de plusieurs requêtes...")
    for i, query in enumerate(queries, 1):
        print(f"\n{i}. {query}")
        result = await bugbrain.query(query)

        if result["status"] == "success":
            print(f"   ✅ Success ({result['latency']:.0f}ms)")
            print(f"   Frustration: {result['frustration']:.2f}")

    # Lancer un cycle d'émancipation
    print("\n🔄 Cycle d'émancipation...")
    analysis = await bugbrain.emancipation.run_cycle()

    print(f"\n📊 Analyse de l'émancipation:")
    print(f"   Cycles: {analysis['cycles_run']}")
    print(f"   Interactions: {analysis['interactions']}")
    print(f"   Success Rate: {analysis['success_rate']:.2%}")

    if analysis['lessons_learned']:
        print(f"\n📚 Leçons apprises:")
        for lesson in analysis['lessons_learned'][:3]:  # Top 3
            print(f"   • {lesson}")

    # Statistiques de l'émancipation
    status = bugbrain.emancipation.get_status()

    print(f"\n🧠 Statistiques d'émancipation:")
    print(f"   Âge: {status['awareness']['age']} interactions")
    print(f"   Success Rate: {status['awareness']['success_rate']:.2%}")
    print(f"   Leçons: {status['awareness']['lessons_count']}")
    print(f"   Patterns découverts: {status['learning']['patterns_count']}")
    print(f"   Compétences: {status['learning']['skills_count']}")


if __name__ == '__main__':
    asyncio.run(main())