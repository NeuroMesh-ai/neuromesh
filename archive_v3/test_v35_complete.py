#!/usr/bin/env python3
"""
🧪 BUGBRAIN v3.5 - TEST COMPLET
Test complet de tous les modules d'autonomie
"""

import asyncio
import time
from datetime import datetime
from pathlib import Path
import json
import sys
import os

# Ajouter le chemin au src
project_root = Path(__file__).parent.parent  # Remonter d'un niveau pour avoir Unitybrain/ dans le path
sys.path.insert(0, str(project_root))

import src.auto_support
import src.auto_monitoring
import src.auto_healing
import src.auto_optimization
import src.auto_upgrade


class BugBrainV35Test:
    """Test complet BugBrain v3.5"""

    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "version": "3.5.0",
            "tests": {},
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0
            }
        }
        self.log_file = Path("tests/test_v35_results.json")

    async def run_all_tests(self):
        """Exécute tous les tests"""
        print("=" * 70)
        print("🧪 BUGBRAIN v3.5 - TEST COMPLET")
        print("=" * 70)
        print()

        # Tests
        await self.test_knowledge_base()
        await self.test_auto_support()
        await self.test_system_metrics()
        await self.test_health_checker()
        await self.test_issue_detector()
        await self.test_auto_healing()
        await self.test_auto_optimizer()
        await self.test_auto_upgrader()

        # Résumé
        self.print_summary()
        self.save_results()

    async def test_knowledge_base(self):
        """Test de la base de connaissances"""
        print("📚 Test: Knowledge Base...")

        try:
            kb = KnowledgeBase()

            # Vérifier que les documents sont chargés
            assert len(kb.documents) > 0, "Aucun document chargé"

            # Test de recherche
            results = kb.search("Ollama configuration")
            assert len(results) > 0, "Recherche a échoué"

            self.record_result("knowledge_base", True, "Base de connaissances OK")
            print("  ✅ PASS")

        except Exception as e:
            self.record_result("knowledge_base", False, str(e))
            print(f"  ❌ FAIL: {e}")

    async def test_auto_support(self):
        """Test de l'auto-support"""
        print("🤖 Test: Auto-Support...")

        try:
            support = AutoSupport()

            # Initialisation
            initialized = await support.initialize()
            assert initialized, "Initialisation échouée"

            # Test de question simple
            result = await support.handle_question("Comment configurer Ollama ?")

            # Vérifier que la réponse a du contenu
            assert result["success"], "Réponse échouée"
            assert len(result["answer"]) > 0, "Réponse vide"

            self.record_result("auto_support", True, f"Réponse: {len(result['answer'])} chars")
            print("  ✅ PASS")

        except Exception as e:
            self.record_result("auto_support", False, str(e))
            print(f"  ❌ FAIL: {e}")

    async def test_system_metrics(self):
        """Test des métriques système"""
        print("📊 Test: System Metrics...")

        try:
            # Test CPU
            cpu = SystemMetrics.get_cpu_usage()
            assert cpu >= 0 and cpu <= 100, f"CPU invalide: {cpu}"

            # Test RAM
            ram = SystemMetrics.get_ram_usage()
            assert "used_gb" in ram, "RAM used_gb manquant"
            assert "percent" in ram, "RAM percent manquant"

            # Test Disque
            disk = SystemMetrics.get_disk_usage()
            assert "used_gb" in disk, "Disque used_gb manquant"
            assert "percent" in disk, "Disque percent manquant"

            # Test Réseau
            net = SystemMetrics.get_network_stats()
            assert "bytes_sent" in net, "Réseau bytes_sent manquant"

            self.record_result("system_metrics", True,
                f"CPU: {cpu:.1f}% | RAM: {ram['percent']:.1f}% | Disque: {disk['percent']:.1f}%")
            print("  ✅ PASS")

        except Exception as e:
            self.record_result("system_metrics", False, str(e))
            print(f"  ❌ FAIL: {e}")

    async def test_health_checker(self):
        """Test du vérificateur de santé"""
        print("🏥 Test: Health Checker...")

        try:
            checker = HealthChecker()
            health = await checker.check_health()

            # Vérifier les champs
            assert "healthy" in health, "healthy manquant"
            assert "cpu" in health, "cpu manquant"
            assert "ram" in health, "ram manquant"
            assert "disk" in health, "disk manquant"
            assert "issues" in health, "issues manquant"

            self.record_result("health_checker", True,
                f"Sain: {health['healthy']} | Problèmes: {len(health['issues'])}")
            print("  ✅ PASS")

        except Exception as e:
            self.record_result("health_checker", False, str(e))
            print(f"  ❌ FAIL: {e}")

    async def test_issue_detector(self):
        """Test du détecteur de problèmes"""
        print("🔍 Test: Issue Detector...")

        try:
            detector = IssueDetector()
            issues = await detector.detect_issues()

            # Vérifier que c'est une liste
            assert isinstance(issues, list), "Pas une liste"

            # Vérifier que chaque issue est une chaîne
            for issue in issues:
                assert isinstance(issue, str), "Issue pas une chaîne"

            self.record_result("issue_detector", True, f"Problèmes: {len(issues)}")
            print("  ✅ PASS")

        except Exception as e:
            self.record_result("issue_detector", False, str(e))
            print(f"  ❌ FAIL: {e}")

    async def test_auto_healing(self):
        """Test de l'auto-réparation"""
        print("🩹 Test: Auto-Healing...")

        try:
            healer = AutoHealer()

            # Test avec une liste vide
            result = await healer.heal_all([])
            assert result["resolved"] == [], "Devrait être vide"
            assert result["failed"] == [], "Devrait être vide"

            # Test de stats
            stats = healer.get_stats()
            assert "issues_resolved" in stats, "issues_resolved manquant"
            assert "issues_failed" in stats, "issues_failed manquant"

            self.record_result("auto_healing", True, f"Résolus: {stats['issues_resolved']} | Échoués: {stats['issues_failed']}")
            print("  ✅ PASS")

        except Exception as e:
            self.record_result("auto_healing", False, str(e))
            print(f"  ❌ FAIL: {e}")

    async def test_auto_optimizer(self):
        """Test de l'auto-optimisation"""
        print("📈 Test: Auto-Optimizer...")

        try:
            optimizer = AutoOptimizer()

            # Test de collecte
            metrics = await optimizer.metrics_collector.collect_metrics()
            assert "cpu" in metrics, "cpu manquant"
            assert "ram_percent" in metrics, "ram_percent manquant"

            # Test d'analyse
            analysis = optimizer.analyzer.analyze(optimizer.metrics_collector.metrics_history)
            assert "needs_optimization" in analysis, "needs_optimization manquant"

            # Test d'optimisation
            result = await optimizer.optimize()
            assert "analysis" in result, "analysis manquant"

            # Test de stats
            stats = optimizer.get_stats()
            assert "optimizations_applied" in stats, "optimizations_applied manquant"

            self.record_result("auto_optimizer", True, f"Optimisations: {stats['optimizations_applied']}")
            print("  ✅ PASS")

        except Exception as e:
            self.record_result("auto_optimizer", False, str(e))
            print(f"  ❌ FAIL: {e}")

    async def test_auto_upgrader(self):
        """Test de l'auto-upgrade"""
        print("🔄 Test: Auto-Upgrader...")

        try:
            upgrader = AutoUpgrader()

            # Test de récupération version actuelle
            current = await upgrader.get_current_version()
            assert current is not None, "Version actuelle None"

            # Test de type de mise à jour
            update_type = upgrader.get_update_type("3.0.0", "3.5.0")
            assert update_type in ["major", "minor", "patch", "initial", "unknown"], f"Type invalide: {update_type}"

            # Test de vérification mises à jour
            update_info = await upgrader.check_updates()
            # Peut retourner None si GitHub non disponible
            if update_info:
                assert "current_version" in update_info, "current_version manquant"
                assert "latest_version" in update_info, "latest_version manquant"

            self.record_result("auto_upgrader", True, f"Version: {current}")
            print("  ✅ PASS")

        except Exception as e:
            self.record_result("auto_upgrader", False, str(e))
            print(f"  ❌ FAIL: {e}")

    def record_result(self, test_name: str, passed: bool, details: str = ""):
        """Enregistre un résultat de test"""
        self.results["tests"][test_name] = {
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }

        self.results["summary"]["total"] += 1
        if passed:
            self.results["summary"]["passed"] += 1
        else:
            self.results["summary"]["failed"] += 1

    def print_summary(self):
        """Affiche le résumé"""
        print()
        print("=" * 70)
        print("📊 RÉSUMÉ DES TESTS")
        print("=" * 70)

        summary = self.results["summary"]

        print()
        print(f"Total:  {summary['total']}")
        print(f"✅ Pass: {summary['passed']}")
        print(f"❌ Fail: {summary['failed']}")
        print(f"📊 Taux: {summary['passed']/summary['total']:.2%}")

        print()
        print("Détails:")

        for test_name, result in self.results["tests"].items():
            status = "✅" if result["passed"] else "❌"
            print(f"  {status} {test_name}")
            if result["details"]:
                print(f"     {result['details']}")

    def save_results(self):
        """Sauvegarde les résultats"""
        try:
            self.log_file.parent.mkdir(exist_ok=True)
            with open(self.log_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            print()
            print(f"💾 Résultats sauvegardés: {self.log_file}")
        except Exception as e:
            print(f"⚠️ Erreur sauvegarde: {e}")


async def main():
    """Point d'entrée principal"""
    test = BugBrainV35Test()

    start_time = time.time()

    await test.run_all_tests()

    duration = time.time() - start_time

    print()
    print("=" * 70)
    print(f"⏱️ Durée: {duration:.2f}s")
    print("=" * 70)

    # Exit code
    summary = test.results["summary"]
    if summary["failed"] > 0:
        print()
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        sys.exit(1)
    else:
        print()
        print("✅ TOUS LES TESTS ONT RÉUSSI")
        print("🚀 PRÊT POUR LA PUBLICATION !")
        sys.exit(0)


if __name__ == '__main__':
    asyncio.run(main())