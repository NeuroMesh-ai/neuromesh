#!/usr/bin/env python3
"""
📈 AUTO-OPTIMIZATION - Optimisation automatique des performances
BugBrain optimise ses performances continuellement
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import json
import aiofiles
import subprocess


class PerformanceMetrics:
    """Collecteur de métriques de performance"""

    def __init__(self):
        self.metrics_history = []

    async def collect_metrics(self) -> Dict:
        """Collecte les métriques de performance"""
        try:
            import psutil

            # Temps de réponse
            start = time.time()

            # Métriques système
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "cpu": psutil.cpu_percent(interval=0.1),
                "ram_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage("/").percent,
            }

            # Temps de collecte
            metrics["collection_time_ms"] = (time.time() - start) * 1000

            self.metrics_history.append(metrics)

            return metrics

        except Exception as e:
            print(f"⚠️ Erreur collecte métriques: {e}")
            return {}


class PerformanceAnalyzer:
    """Analyseur de performances"""

    def __init__(self):
        self.baselines = {
            "cpu_avg": 30.0,
            "ram_avg": 50.0,
            "collection_time_avg": 100.0
        }

    def analyze(self, metrics_history: List[Dict]) -> Dict:
        """
        Analyse les métriques et identifie les problèmes
        """
        if not metrics_history:
            return {}

        # Calculer les moyennes
        recent_metrics = metrics_history[-100:]  # 100 derniers échantillons

        cpu_avg = sum(m["cpu"] for m in recent_metrics) / len(recent_metrics)
        ram_avg = sum(m["ram_percent"] for m in recent_metrics) / len(recent_metrics)
        collection_time_avg = sum(m["collection_time_ms"] for m in recent_metrics) / len(recent_metrics)

        # Comparer avec les baselines
        issues = []

        if cpu_avg > self.baselines["cpu_avg"] * 1.5:
            issues.append(f"CPU élevé: {cpu_avg:.1f}% (baseline: {self.baselines['cpu_avg']:.1f}%)")

        if ram_avg > self.baselines["ram_avg"] * 1.5:
            issues.append(f"RAM élevée: {ram_avg:.1f}% (baseline: {self.baselines['ram_avg']:.1f}%)")

        if collection_time_avg > self.baselines["collection_time_avg"] * 1.5:
            issues.append(f"Collecte lente: {collection_time_avg:.1f}ms (baseline: {self.baselines['collection_time_avg']:.1f}ms)")

        return {
            "current_avg": {
                "cpu": cpu_avg,
                "ram": ram_avg,
                "collection_time_ms": collection_time_avg
            },
            "baselines": self.baselines,
            "issues": issues,
            "needs_optimization": len(issues) > 0
        }


class AutoOptimizer:
    """Optimiseur automatique"""

    def __init__(self):
        self.metrics_collector = PerformanceMetrics()
        self.analyzer = PerformanceAnalyzer()
        self.optimizations_applied = []
        self.optimizations_log = Path("logs/optimizations.log")

    async def optimize(self) -> Dict:
        """
        Effectue l'optimisation automatique
        """
        # Collecter les métriques
        await self.metrics_collector.collect_metrics()

        # Analyser
        analysis = self.analyzer.analyze(self.metrics_collector.metrics_history)

        results = {
            "analysis": analysis,
            "optimizations": [],
            "timestamp": datetime.now().isoformat()
        }

        # Si optimisation nécessaire
        if analysis.get("needs_optimization"):
            print("🔧 Optimisation nécessaire...")

            for issue in analysis["issues"]:
                optimized = await self.optimize_issue(issue)

                if optimized:
                    results["optimizations"].append(issue)
                    self.optimizations_applied.append(issue)

            # Logger
            await self.log_optimization(results)

        return results

    async def optimize_issue(self, issue: str) -> bool:
        """
        Tente d'optimiser un problème spécifique
        """
        print(f"  → Optimisation: {issue}")

        try:
            # CPU élevé
            if "CPU élevé" in issue:
                return await self.optimize_cpu()

            # RAM élevée
            elif "RAM élevée" in issue:
                return await self.optimize_ram()

            # Collecte lente
            elif "Collecte lente" in issue:
                return await self.optimize_collection()

            else:
                print(f"  ⚠️ Pas de solution pour: {issue}")
                return False

        except Exception as e:
            print(f"  ❌ Erreur: {e}")
            return False

    async def optimize_cpu(self) -> bool:
        """Optimise l'utilisation CPU"""
        print("    → Optimisation CPU...")

        try:
            # Réduire la priorité des processus
            subprocess.run(
                ["renice", "10", "-p", str(os.getpid())],
                capture_output=True
            )

            print("    ✅ CPU optimisé")
            return True

        except Exception as e:
            print(f"    ❌ Erreur: {e}")
            return False

    async def optimize_ram(self) -> bool:
        """Optimise l'utilisation RAM"""
        print("    → Optimisation RAM...")

        try:
            import gc
            gc.collect()

            # Vider le cache système
            subprocess.run(
                ["sudo", "sync"],
                capture_output=True
            )

            subprocess.run(
                ["sudo", "sh", "-c", "echo 1 > /proc/sys/vm/drop_caches"],
                capture_output=True
            )

            print("    ✅ RAM optimisée")
            return True

        except Exception as e:
            print(f"    ❌ Erreur: {e}")
            return False

    async def optimize_collection(self) -> bool:
        """Optimise le temps de collecte"""
        print("    → Optimisation collecte...")

        try:
            # Vider l'historique des métriques
            if len(self.metrics_collector.metrics_history) > 1000:
                self.metrics_collector.metrics_history = self.metrics_collector.metrics_history[-500:]

            print("    ✅ Collecte optimisée")
            return True

        except Exception as e:
            print(f"    ❌ Erreur: {e}")
            return False

    async def log_optimization(self, results: Dict):
        """Log les optimisations"""
        try:
            self.optimizations_log.parent.mkdir(exist_ok=True)
            async with aiofiles.open(self.optimizations_log, 'a') as f:
                await f.write(json.dumps(results, indent=2) + "\n")
        except Exception as e:
            print(f"⚠️ Erreur log optimisation: {e}")

    def get_stats(self) -> Dict:
        """Retourne les statistiques d'optimisation"""
        return {
            "optimizations_applied": len(self.optimizations_applied),
            "last_optimizations": self.optimizations_applied[-10:]
        }


async def continuous_optimization(interval_minutes: int = 60):
    """Optimisation continue"""
    optimizer = AutoOptimizer()

    print("📈 Démarrage de l'Auto-Optimisation...")
    print(f"Intervalle: {interval_minutes} minutes")
    print()

    while True:
        print(f"⏰ {datetime.now().strftime('%H:%M:%S')} - Analyse et optimisation...")

        results = await optimizer.optimize()

        if results["optimizations"]:
            print(f"✅ {len(results['optimizations'])} optimisation(s) appliquée(s)")
        else:
            print("✅ Pas d'optimisation nécessaire")

        print()
        await asyncio.sleep(interval_minutes * 60)


async def optimize_once():
    """Optimisation unique"""
    optimizer = AutoOptimizer()

    print("=" * 70)
    print("📈 AUTO-OPTIMIZATION - Optimisation des performances")
    print("=" * 70)
    print()

    print("🔍 Analyse...")
    results = await optimizer.optimize()

    print()
    print("📊 Résultats:")

    if results["optimizations"]:
        print(f"✅ {len(results['optimizations'])} optimisation(s) appliquée(s):")
        for opt in results["optimizations"]:
            print(f"   - {opt}")
    else:
        print("✅ Pas d'optimisation nécessaire - Système optimal !")

    print()

    stats = optimizer.get_stats()
    print("📈 Statistiques globales:")
    print(f"   Optimisations totales: {stats['optimizations_applied']}")


if __name__ == '__main__':
    import sys
    import os

    if len(sys.argv) > 1 and sys.argv[1] == "continuous":
        asyncio.run(continuous_optimization(30))
    else:
        asyncio.run(optimize_once())