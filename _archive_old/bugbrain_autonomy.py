#!/usr/bin/env python3
"""
🚀 BUGBRAIN v3.5 - SYSTÈME D'AUTONOMIE AVANCÉE
Orchestration complète de tous les modules d'autonomie

Niveaux d'autonomie:
- Niveau 1: Auto-Support (✅ v3.0)
- Niveau 2: Auto-Monitoring (✅ v3.5)
- Niveau 3: Auto-Healing (✅ v3.5)
- Niveau 4: Auto-Optimization (✅ v3.5)
- Niveau 5: Auto-Upgrade (✅ v3.5)
"""

import asyncio
import signal
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path
import json

from .auto_support import AutoSupport
from .auto_monitoring import AutoMonitor
from .auto_healing import AutoHealer, IssueDetector
from .auto_optimization import AutoOptimizer, continuous_optimization
from .auto_upgrade import AutoUpgrader


class BugBrainAutonomy:
    """
    Système d'autonomie complète BugBrain
    Orchestre tous les modules d'autonomie
    """

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.version = "3.5.0"
        self.is_running = False

        # Initialiser les modules
        self.auto_support = AutoSupport(config)
        self.auto_monitor = AutoMonitor(check_interval=60)
        self.auto_healer = AutoHealer()
        self.issue_detector = IssueDetector()
        self.auto_optimizer = AutoOptimizer()
        self.auto_upgrader = AutoUpgrader()

        # Logs
        self.main_log = Path("logs/autonomy.log")

        # Stats
        self.start_time = None
        self.cycles_completed = 0

    async def initialize(self):
        """Initialise tous les modules d'autonomie"""
        print("🚀 Initialisation du système d'autonomie...")

        # Initialiser Auto-Support
        await self.auto_support.initialize()

        # Créer les répertoires de logs
        Path("logs").mkdir(exist_ok=True)

        print("✅ Système d'autonomie initialisé")

    async def start(self):
        """Démarre tous les modules d'autonomie"""
        print()
        print("=" * 70)
        print("🚀 BUGBRAIN v3.5 - AUTONOMIE AVANCÉE")
        print("=" * 70)
        print()

        self.is_running = True
        self.start_time = datetime.now()

        # Démarrer chaque module
        await self.start_monitoring()
        await self.start_optimization()
        await self.start_upgrade_check()

        print()
        print("✅ Tous les modules d'autonomie sont actifs !")
        print()
        print("🔄 Démarrage du cycle principal...")

        # Cycle principal
        while self.is_running:
            await self.main_cycle()
            await asyncio.sleep(60)  # 1 minute entre les cycles

    async def stop(self):
        """Arrête tous les modules d'autonomie"""
        print()
        print("🛑 Arrêt du système d'autonomie...")

        self.is_running = False

        await self.auto_monitor.stop()

        print("✅ Système d'autonomie arrêté")

    async def start_monitoring(self):
        """Démarre le monitoring"""
        print("🏥 Démarrage Auto-Monitoring...")
        monitor_task = asyncio.create_task(self.auto_monitor.start())

    async def start_optimization(self):
        """Démarre l'optimisation"""
        print("📈 Démarrage Auto-Optimization...")
        optimizer_task = asyncio.create_task(continuous_optimization(30))

    async def start_upgrade_check(self):
        """Démarre la vérification des mises à jour"""
        print("🔄 Vérification des mises à jour...")
        update_info = await self.auto_upgrader.check_updates()

        if update_info and update_info.get("update_available"):
            print(f"✅ Mise à jour disponible: {update_info['latest_version']}")

    async def main_cycle(self):
        """
        Cycle principal d'autonomie
        Exécuté toutes les minutes
        """
        self.cycles_completed += 1

        print(f"🔄 Cycle #{self.cycles_completed} - {datetime.now().strftime('%H:%M:%S')}")

        # 1. Monitoring
        health = await self.auto_monitor.health_checker.check_health()

        # 2. Détection des problèmes
        issues = await self.issue_detector.detect_issues()

        # 3. Réparation automatique si nécessaire
        if issues:
            print(f"⚠️ {len(issues)} problème(s) détecté(s)")
            await self.auto_healer.heal_all(issues)

        # 4. Optimisation
        await self.auto_optimizer.optimize()

        # 5. Logger
        await self.log_cycle(health, issues)

    async def log_cycle(self, health: Dict, issues: list):
        """Log le cycle d'autonomie"""
        log_entry = {
            "cycle": self.cycles_completed,
            "timestamp": datetime.now().isoformat(),
            "health": health.get("healthy", False),
            "issues": issues,
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        }

        try:
            with open(self.main_log, 'a') as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            print(f"⚠️ Erreur log cycle: {e}")

    async def get_status(self) -> Dict:
        """Retourne le status complet"""
        uptime = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0

        return {
            "version": self.version,
            "is_running": self.is_running,
            "uptime_seconds": uptime,
            "cycles_completed": self.cycles_completed,
            "modules": {
                "auto_support": await self.auto_support.initialize(),
                "auto_monitor": True,
                "auto_healing": True,
                "auto_optimization": True,
                "auto_upgrade": True
            },
            "stats": {
                "monitoring": self.auto_monitor.get_status_report(),
                "healing": self.auto_healer.get_stats(),
                "optimization": self.auto_optimizer.get_stats()
            }
        }

    async def handle_support_question(self, question: str) -> Dict:
        """Gère une question de support"""
        return await self.auto_support.handle_question(question)


# ============================================================================
# ============== INTERFACE CLI ==============================================
# ============================================================================

async def interactive_autonomy():
    """Interface interactive d'autonomie"""
    autonomy = BugBrainAutonomy()

    print("=" * 70)
    print("🚀 BUGBRAIN v3.5 - AUTONOMIE AVANCÉE")
    print("=" * 70)
    print()

    # Initialiser
    await autonomy.initialize()

    print()
    print("Commandes disponibles:")
    print("  start   - Démarrer l'autonomie complète")
    print("  status  - Voir le status")
    print("  support - Poser une question (auto-support)")
    print("  heal    - Détecter et réparer les problèmes")
    print("  optimize - Optimiser les performances")
    print("  upgrade - Vérifier les mises à jour")
    print("  stop    - Arrêter")
    print()

    while True:
        cmd = input("> ").strip().lower()

        if cmd == "start":
            print()
            await autonomy.start()

        elif cmd == "status":
            status = await autonomy.get_status()
            print("\n📊 Status:")
            print(json.dumps(status, indent=2))

        elif cmd == "support":
            question = input("❓ Votre question: ")
            result = await autonomy.handle_support_question(question)

            if result["success"]:
                print(f"\n✅ {result['answer']}")
            else:
                print(f"\n❌ {result['message']}")

        elif cmd == "heal":
            from .auto_healing import check_and_heal
            await check_and_heal()

        elif cmd == "optimize":
            from .auto_optimization import optimize_once
            await optimize_once()

        elif cmd == "upgrade":
            from .auto_upgrade import check_upgrade
            await check_upgrade()

        elif cmd in ["stop", "quit", "exit"]:
            await autonomy.stop()
            break

        else:
            print("Commande inconnue")


async def start_autonomous():
    """Démarre BugBrain en mode autonome"""
    autonomy = BugBrainAutonomy()

    # Initialiser
    await autonomy.initialize()

    # Démarrer
    await autonomy.start()


if __name__ == '__main__':
    import sys

    # Gestion du signal SIGINT
    def signal_handler(sig, frame):
        print("\n\n🛑 Arrêt demandé...")
        asyncio.create_task(autonomy.stop())
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    if len(sys.argv) > 1 and sys.argv[1] == "autonomous":
        asyncio.run(start_autonomous())
    else:
        asyncio.run(interactive_autonomy())