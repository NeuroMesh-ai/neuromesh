#!/usr/bin/env python3
"""
🎮 INTERFACE INTERACTIVE POUR UNITYBRAIN & BUGBRAIN v3.0
CLI et Web pour faire des requêtes par prompt et recevoir les réponses
"""

import asyncio
import sys
from unitybrain_v3_final import UnityBrain, Peer
from bugbrain_v3_final import BugBrain

# ============================================================================
# ============== CLI INTERACTIVE ============================================
# ============================================================================

class InteractiveCLI:
    """Interface CLI interactive"""

    def __init__(self):
        self.unitybrain = None
        self.bugbrain = None
        self.current_mode = None  # 'unitybrain' or 'bugbrain'

    async def initialize(self):
        """Initialise les systèmes"""
        print("\n" + "=" * 70)
        print("🎮 INTERFACE INTERACTIVE - UnityBrain & BugBrain v3.0")
        print("=" * 70)

        # Initialiser UnityBrain
        print("\n🌐 Initializing UnityBrain...")
        self.unitybrain = UnityBrain()
        bug_peer = Peer("Bug", "172.17.222.200", 9999,
                       ["SmolLM2:1.7b", "phi3:mini", "glm-4.7:cloud", "glm-5:cloud"])
        pinky_peer = Peer("Pinky", "192.168.129.61", 9999,
                         ["SmolLM2:1.7b", "TinyLlama:latest", "Stable-code:3b", "glm-4.7:cloud"],
                         ollama_host="192.168.129.61")
        await self.unitybrain.add_peer(bug_peer)
        await self.unitybrain.add_peer(pinky_peer)
        await self.unitybrain.initialize()
        await self.unitybrain.start_web_server()

        # Initialiser BugBrain
        print("\n🧠 Initializing BugBrain...")
        self.bugbrain = BugBrain()
        await self.bugbrain.initialize()

        # Mode par défaut
        self.current_mode = 'unitybrain'
        print(f"\n✅ Ready! Mode actuel: {self.current_mode.upper()}")
        print("   Tapez 'help' pour la liste des commandes")

    async def show_help(self):
        """Affiche l'aide"""
        print("\n" + "=" * 70)
        print("📚 COMMANDES DISPONIBLES")
        print("=" * 70)
        print("\n🎯 Commandes Principales:")
        print("   mode [unitybrain|bugbrain]  Change de mode")
        print("   query <votre prompt>        Envoie une requête")
        print("   status                      Affiche le statut")
        print("   help                        Affiche cette aide")
        print("   quit                        Quitte")
        print("\n🔍 Commandes UnityBrain:")
        print("   ensemble <prompt>           Query avec ensemble (multi-modèles)")
        print("   peers                       Liste des peers")
        print("   history [limit]             Historique des requêtes")
        print("   export [json|txt|code]      Exporte l'historique")
        print("\n🧠 Commandes BugBrain:")
        print("   emancipate                  Lance un cycle d'auto-émancipation")
        print("   memory search <query>       Recherche dans la mémoire")
        print("   skills                      Affiche les compétences")
        print("   goals                       Affiche les buts")
        print("   lessons                     Affiche les leçons")

    async def handle_query(self, prompt: str, use_ensemble: bool = False):
        """Gère une requête"""
        if not prompt:
            print("❌ Erreur: Prompt vide")
            return

        print(f"\n📝 Envoi de la requête...")
        print(f"   Prompt: {prompt[:100]}...")

        if self.current_mode == 'unitybrain':
            result = await self.unitybrain.query(prompt, use_ensemble=use_ensemble)
        else:
            result = await self.bugbrain.query(prompt)

        if result["status"] == "success":
            print(f"\n✅ Réponse reçue!")
            print(f"   Mode: {self.current_mode.upper()}")
            if "peer" in result:
                print(f"   Peer: {result['peer']}")
            print(f"   Model: {result['model']}")
            print(f"   Latency: {result['latency']:.0f}ms")
            print(f"\n💬 Réponse:")
            print("   " + "-" * 66)
            print("   " + result['response'])
            print("   " + "-" * 66)
        else:
            print(f"\n❌ Erreur: {result.get('message', 'Erreur inconnue')}")

    async def handle_status(self):
        """Affiche le statut"""
        print("\n" + "=" * 70)
        print(f"📊 STATUT - {self.current_mode.upper()}")
        print("=" * 70)

        if self.current_mode == 'unitybrain':
            status = self.unitybrain.get_status()
            print(f"\n🌐 Peers:")
            print(f"   Available: {status['peers']['available']}/{status['peers']['total']}")
            for peer in status['peers']['list']:
                status_icon = "✅" if peer['available'] else "❌"
                print(f"   {status_icon} {peer['name']}: {peer['latency']:.0f}ms (rep: {peer['reputation']:.2f})")

            print(f"\n📊 Queries:")
            print(f"   Total: {status['queries']['total']}")
            print(f"   Successful: {status['queries']['successful']}")
            print(f"   Rate: {status['queries']['rate']:.1f}%")

            print(f"\n⏱️ Uptime: {status['uptime']:.1f}s")
        else:
            status = await self.bugbrain.get_status()
            print(f"\n🤖 Emancipation:")
            print(f"   Age: {status['emancipation']['age']/60:.1f}m")
            print(f"   Interactions: {status['emancipation']['interactions']}")
            print(f"   Success rate: {status['emancipation']['success_rate']:.1%}")
            print(f"   Lessons: {status['emancipation']['lessons']}")
            print(f"   Goals: {status['emancipation']['goals']}")
            print(f"   Assessment: {status['emancipation']['assessment']}")

            print(f"\n🧠 Skills:")
            for skill, data in status['emancipation']['skills'].items():
                print(f"   {skill}: Level {data['level']:.2f} ({data['rate']:.1%})")

            print(f"\n📊 Queries:")
            print(f"   Total: {status['queries']['total']}")
            print(f"   Successful: {status['queries']['successful']}")
            print(f"   Rate: {status['queries']['rate']:.1f}%")

            print(f"\n💾 Memory:")
            print(f"   Size: {status['memory']['size']} entries")
            print(f"   Hit rate: {status['memory']['hit_rate']:.1%}")

    async def handle_peers(self):
        """Affiche les peers (UnityBrain only)"""
        if self.current_mode != 'unitybrain':
            print("❌ Commande disponible uniquement en mode UnityBrain")
            return

        print("\n🌐 PEERS CONNECTÉS:")
        for peer in self.unitybrain.peers:
            status_icon = "✅" if peer.available else "❌"
            print(f"   {status_icon} {peer.name}")
            print(f"      Host: {peer.host}:{peer.port}")
            print(f"      Latency: {peer.latency:.0f}ms")
            print(f"      Reputation: {peer.reputation:.2f}")
            print(f"      Models: {', '.join(peer.models)}")

    async def handle_history(self, limit: int = 10):
        """Affiche l'historique (UnityBrain only)"""
        if self.current_mode != 'unitybrain':
            print("❌ Commande disponible uniquement en mode UnityBrain")
            return

        history = await self.unitybrain.query_history.get(limit)
        print(f"\n📜 HISTORIQUE (derniers {len(history)} requêtes):")
        for i, entry in enumerate(history, 1):
            timestamp = entry.get('timestamp', 0)
            prompt = entry.get('prompt', '')
            print(f"\n   #{i} [{timestamp:.0f}]")
            print(f"   Prompt: {prompt[:80]}...")

    async def handle_export(self, format_type: str = "json"):
        """Exporte l'historique (UnityBrain only)"""
        if self.current_mode != 'unitybrain':
            print("❌ Commande disponible uniquement en mode UnityBrain")
            return

        export_data = await self.unitybrain.query_history.export(format_type)
        print(f"\n📤 EXPORT ({format_type.upper()}):")
        print("-" * 70)
        print(export_data[:1000] + "..." if len(export_data) > 1000 else export_data)
        print("-" * 70)

    async def handle_emancipate(self):
        """Lance un cycle d'émancipation (BugBrain only)"""
        if self.current_mode != 'bugbrain':
            print("❌ Commande disponible uniquement en mode BugBrain")
            return

        print("\n🔄 Lancement du cycle d'auto-émancipation...")
        cycle = await self.bugbrain.emancipation.cycle()
        print(f"\n✅ Cycle {cycle['cycle_number']} terminé!")
        print(f"   Assessment: {cycle['reflection']['assessment']}")
        print(f"   Opportunities: {len(cycle['opportunities'])}")
        print(f"   Improvement: {cycle['improvement']['status']}")

    async def handle_memory_search(self, query: str):
        """Recherche dans la mémoire (BugBrain only)"""
        if self.current_mode != 'bugbrain':
            print("❌ Commande disponible uniquement en mode BugBrain")
            return

        results = await self.bugbrain.memory.search(query, top_k=5)
        print(f"\n🔍 RÉSULTATS DE RECHERCHE: '{query}'")
        if not results:
            print("   Aucun résultat")
        else:
            for i, result in enumerate(results, 1):
                print(f"\n   #{i} (Score: {result['score']:.2f})")
                print(f"   Key: {result['key']}")
                print(f"   Value: {str(result['value'])[:100]}...")

    async def handle_skills(self):
        """Affiche les compétences (BugBrain only)"""
        if self.current_mode != 'bugbrain':
            print("❌ Commande disponible uniquement en mode BugBrain")
            return

        print("\n🧠 COMPÉTENCES:")
        skills = self.bugbrain.emancipation.learning.skills
        if not skills:
            print("   Aucune compétence enregistrée")
        else:
            for skill, data in skills.items():
                print(f"   {skill}:")
                print(f"      Level: {data['level']:.2f}")
                print(f"      Experience: {data['experience']}")
                print(f"      Success rate: {data['rate']:.1%}")

    async def handle_goals(self):
        """Affiche les buts (BugBrain only)"""
        if self.current_mode != 'bugbrain':
            print("❌ Commande disponible uniquement en mode BugBrain")
            return

        print("\n🎯 BUTS:")
        goals = self.bugbrain.emancipation.awareness.goals
        if not goals:
            print("   Aucun but défini")
        else:
            for i, goal in enumerate(goals[-10:], 1):  # Derniers 10
                status_icon = "✅" if goal.get('completed', False) else "🔄"
                print(f"   {status_icon} {i}. {goal['goal']} (priority: {goal['priority']})")

    async def handle_lessons(self):
        """Affiche les leçons (BugBrain only)"""
        if self.current_mode != 'bugbrain':
            print("❌ Commande disponible uniquement en mode BugBrain")
            return

        print("\n📚 LEÇONS:")
        lessons = self.bugbrain.emancipation.awareness.lessons
        if not lessons:
            print("   Aucune leçon apprise")
        else:
            for i, lesson in enumerate(lessons[-10:], 1):  # Dernières 10
                print(f"   {i}. {lesson['lesson']}")

    async def run(self):
        """Exécute l'interface interactive"""
        await self.initialize()

        print("\n" + "=" * 70)
        print("🎮 MODE INTERACTIF")
        print("=" * 70)
        print("   Tapez votre prompt ou une commande")
        print("   Exemple: 'Qu'est-ce que UnityBrain ?'")
        print("   Exemple: 'mode bugbrain'")
        print("   Exemple: 'help'")
        print("   Tapez 'quit' pour quitter")
        print("=" * 70)

        while True:
            try:
                # Prompt utilisateur
                user_input = input(f"\n[{self.current_mode.upper()}]> ").strip()

                if not user_input:
                    continue

                # Parser la commande
                parts = user_input.split(maxsplit=1)
                command = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""

                # Commandes
                if command == 'quit' or command == 'exit':
                    print("\n👋 Au revoir!")
                    break

                elif command == 'help':
                    await self.show_help()

                elif command == 'mode':
                    if args.lower() in ['unitybrain', 'bug']:
                        self.current_mode = args.lower()
                        print(f"\n✅ Mode changé vers: {self.current_mode.upper()}")
                    else:
                        print("❌ Usage: mode [unitybrain|bug]")

                elif command == 'status':
                    await self.handle_status()

                elif command == 'query':
                    await self.handle_query(args)

                elif command == 'ensemble':
                    if self.current_mode == 'unitybrain':
                        await self.handle_query(args, use_ensemble=True)
                    else:
                        print("❌ Commande disponible uniquement en mode UnityBrain")

                elif command == 'peers':
                    await self.handle_peers()

                elif command == 'history':
                    limit = int(args) if args.isdigit() else 10
                    await self.handle_history(limit)

                elif command == 'export':
                    format_type = args.lower() if args else 'json'
                    await self.handle_export(format_type)

                elif command == 'emancipate':
                    await self.handle_emancipate()

                elif command == 'memory':
                    if args.startswith('search '):
                        query = args[7:]
                        await self.handle_memory_search(query)
                    else:
                        print("❌ Usage: memory search <query>")

                elif command == 'skills':
                    await self.handle_skills()

                elif command == 'goals':
                    await self.handle_goals()

                elif command == 'lessons':
                    await self.handle_lessons()

                # Si ce n'est pas une commande connue, c'est un prompt
                else:
                    await self.handle_query(user_input)

            except KeyboardInterrupt:
                print("\n\n👋 Interruption détectée. Au revoir!")
                break
            except Exception as e:
                print(f"\n❌ Erreur: {e}")

# ============================================================================
# ============== MAIN ========================================================
# ============================================================================

async def main():
    """Main function"""
    cli = InteractiveCLI()
    await cli.run()

if __name__ == '__main__':
    asyncio.run(main())