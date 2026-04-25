#!/usr/bin/env python3
"""
🩹 AUTO-HEALING - Réparation automatique
BugBrain se répare lui-même quand des problèmes sont détectés
"""

import asyncio
import subprocess
import shutil
import os
import time
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import json
import aiofiles


class IssueDetector:
    """Détecteur de problèmes"""

    def __init__(self):
        self.issues = []

    async def detect_issues(self) -> List[str]:
        """
        Détecte les problèmes dans le système
        """
        issues = []

        # Vérifier la RAM
        self.check_ram(issues)

        # Vérifier l'espace disque
        self.check_disk(issues)

        # Vérifier les processus
        self.check_processes(issues)

        # Vérifier Ollama
        await self.check_ollama(issues)

        # Vérifier les logs
        self.check_logs(issues)

        return issues

    def check_ram(self, issues: List[str]):
        """Vérifie l'utilisation RAM"""
        try:
            import psutil
            ram = psutil.virtual_memory()
            if ram.percent > 90:
                issues.append(f"RAM critique: {ram.percent:.1f}%")
        except:
            pass

    def check_disk(self, issues: List[str]):
        """Vérifie l'espace disque"""
        try:
            import psutil
            disk = psutil.disk_usage("/")
            if disk.percent > 90:
                issues.append(f"Disque critique: {disk.percent:.1f}%")
        except:
            pass

    def check_processes(self, issues: List[str]):
        """Vérifie les processus critiques"""
        # Vérifier si ollama tourne
        try:
            result = subprocess.run(
                ["pgrep", "-x", "ollama"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                issues.append("Ollama ne tourne pas")
        except:
            pass

    async def check_ollama(self, issues: List[str]):
        """Vérifie Ollama"""
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                issues.append("Ollama ne répond pas")
        except:
            issues.append("Ollama inaccessible")

    def check_logs(self, issues: List[str]):
        """Vérifie les logs pour erreurs"""
        logs_dir = Path("logs")
        if logs_dir.exists():
            for log_file in logs_dir.glob("*.log"):
                # Vérifier la taille (max 100MB)
                if log_file.stat().st_size > 100 * 1024 * 1024:
                    issues.append(f"Log trop volumineux: {log_file.name}")


class AutoHealer:
    """Auto-réparateur"""

    def __init__(self):
        self.issues_resolved = 0
        self.issues_failed = 0
        self.heal_log = Path("logs/healing.log")

    async def heal_all(self, issues: List[str]) -> Dict:
        """
        Tente de réparer tous les problèmes détectés
        """
        results = {
            "issues": issues,
            "resolved": [],
            "failed": [],
            "timestamp": datetime.now().isoformat()
        }

        for issue in issues:
            resolved = await self.heal_issue(issue)

            if resolved:
                results["resolved"].append(issue)
                self.issues_resolved += 1
            else:
                results["failed"].append(issue)
                self.issues_failed += 1

        # Logger
        await self.log_healing(results)

        return results

    async def heal_issue(self, issue: str) -> bool:
        """
        Tente de réparer un problème spécifique
        """
        print(f"🔧 Réparation: {issue}")

        try:
            # RAM élevée
            if "RAM" in issue:
                return await self.heal_ram()

            # Disque élevé
            elif "Disque" in issue:
                return await self.heal_disk()

            # Ollama ne tourne pas
            elif "Ollama ne tourne pas" in issue:
                return await self.heal_ollama_not_running()

            # Ollama ne répond pas
            elif "Ollama ne répond pas" in issue:
                return await self.heal_ollama_not_responding()

            # Log trop volumineux
            elif "Log trop volumineux" in issue:
                return await self.heal_large_log(issue)

            else:
                print(f"⚠️ Pas de solution automatique pour: {issue}")
                return False

        except Exception as e:
            print(f"❌ Erreur réparation: {e}")
            return False

    async def heal_ram(self) -> bool:
        """
        Libère de la RAM
        """
        print("  → Libération RAM...")

        try:
            import psutil

            # Vider le cache système (Linux)
            subprocess.run(
                ["sudo", "sync"],
                capture_output=True
            )

            subprocess.run(
                ["sudo", "sh", "-c", "echo 3 > /proc/sys/vm/drop_caches"],
                capture_output=True
            )

            print("  ✅ RAM libérée")
            return True

        except Exception as e:
            print(f"  ❌ Erreur: {e}")
            return False

    async def heal_disk(self) -> bool:
        """
        Libère de l'espace disque
        """
        print("  → Nettoyage disque...")

        try:
            # Nettoyer les logs anciens
            logs_dir = Path("logs")
            if logs_dir.exists():
                # Supprimer les logs de plus de 7 jours
                now = time.time()
                seven_days = 7 * 24 * 60 * 60

                for log_file in logs_dir.glob("*.log"):
                    if now - log_file.stat().st_mtime > seven_days:
                        log_file.unlink()
                        print(f"    → Supprimé: {log_file.name}")

            # Nettoyer le cache
            cache_dir = Path("cache")
            if cache_dir.exists():
                for cache_file in cache_dir.iterdir():
                    if cache_file.is_file():
                        cache_file.unlink()
                        print(f"    → Supprimé: {cache_file.name}")

            # Nettoyer le cache pip
            subprocess.run(
                ["pip", "cache", "purge"],
                capture_output=True
            )

            print("  ✅ Disque nettoyé")
            return True

        except Exception as e:
            print(f"  ❌ Erreur: {e}")
            return False

    async def heal_ollama_not_running(self) -> bool:
        """
        Redémarre Ollama
        """
        print("  → Redémarrage Ollama...")

        try:
            # Démarrer Ollama
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # Attendre qu'il démarre
            await asyncio.sleep(5)

            # Vérifier qu'il répond
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                print("  ✅ Ollama redémarré")
                return True
            else:
                print("  ❌ Ollama ne répond toujours pas")
                return False

        except Exception as e:
            print(f"  ❌ Erreur: {e}")
            return False

    async def heal_ollama_not_responding(self) -> bool:
        """
        Redémarre Ollama (il tourne mais ne répond pas)
        """
        print("  → Redémarrage forcé Ollama...")

        try:
            # Tuer Ollama
            subprocess.run(
                ["pkill", "-9", "ollama"],
                capture_output=True
            )

            await asyncio.sleep(2)

            # Redémarrer
            return await self.heal_ollama_not_running()

        except Exception as e:
            print(f"  ❌ Erreur: {e}")
            return False

    async def heal_large_log(self, issue: str) -> bool:
        """
        Tronque un log trop volumineux
        """
        print("  → Troncation du log...")

        try:
            # Extraire le nom du fichier
            log_name = issue.split(":")[-1].strip()

            log_file = Path("logs") / log_name
            if log_file.exists():
                # Garder seulement les 1000 dernières lignes
                with open(log_file, 'r') as f:
                    lines = f.readlines()

                with open(log_file, 'w') as f:
                    f.writelines(lines[-1000:])

                print(f"  ✅ Log tronqué: {log_name}")
                return True

            return False

        except Exception as e:
            print(f"  ❌ Erreur: {e}")
            return False

    async def log_healing(self, results: Dict):
        """
        Log les opérations de réparation
        """
        try:
            self.heal_log.parent.mkdir(exist_ok=True)
            async with aiofiles.open(self.heal_log, 'a') as f:
                await f.write(json.dumps(results, indent=2) + "\n")
        except Exception as e:
            print(f"⚠️ Erreur log healing: {e}")

    def get_stats(self) -> Dict:
        """
        Retourne les statistiques de réparation
        """
        return {
            "issues_resolved": self.issues_resolved,
            "issues_failed": self.issues_failed,
            "success_rate": self.issues_resolved / max(1, self.issues_resolved + self.issues_failed)
        }


# ============================================================================
# ============== INTERFACE CLI ==============================================
# ============================================================================

async def interactive_healing():
    """Interface interactive de réparation"""
    healer = AutoHealer()
    detector = IssueDetector()

    print("=" * 70)
    print("🩹 AUTO-HEALING - Réparation automatique")
    print("=" * 70)
    print()

    while True:
        print("🔍 Détection des problèmes...")
        issues = await detector.detect_issues()

        if not issues:
            print("✅ Aucun problème détecté")
        else:
            print(f"⚠️ {len(issues)} problème(s) détecté(s):")
            for issue in issues:
                print(f"   - {issue}")

            print()
            choice = input("Tenter la réparation automatique ? (y/n): ").strip().lower()

            if choice == 'y':
                print()
                results = await healer.heal_all(issues)

                print()
                print("📊 Résultats:")
                print(f"   ✅ Résolus: {len(results['resolved'])}")
                print(f"   ❌ Échoués: {len(results['failed'])}")

                if results['resolved']:
                    print("\n✅ Problèmes résolus:")
                    for issue in results['resolved']:
                        print(f"   - {issue}")

                if results['failed']:
                    print("\n❌ Problèmes non résolus:")
                    for issue in results['failed']:
                        print(f"   - {issue}")

        print()
        stats = healer.get_stats()
        print("📈 Statistiques globales:")
        print(f"   Résolus: {stats['issues_resolved']}")
        print(f"   Échoués: {stats['issues_failed']}")
        print(f"   Taux de succès: {stats['success_rate']:.2%}")

        print()
        choice = input("Continuer ? (y/n): ").strip().lower()
        if choice != 'y':
            break


async def check_and_heal():
    """Détecte et répare automatiquement"""
    healer = AutoHealer()
    detector = IssueDetector()

    print("=" * 70)
    print("🩹 DÉTECTION ET RÉPARATION AUTOMATIQUE")
    print("=" * 70)
    print()

    print("🔍 Détection des problèmes...")
    issues = await detector.detect_issues()

    if not issues:
        print("✅ Aucun problème détecté - Système sain !")
    else:
        print(f"⚠️ {len(issues)} problème(s) détecté(s):")
        for issue in issues:
            print(f"   - {issue}")

        print()
        print("🔧 Réparation automatique...")
        results = await healer.heal_all(issues)

        print()
        print("📊 Résultats:")
        print(f"   ✅ Résolus: {len(results['resolved'])}")
        print(f"   ❌ Échoués: {len(results['failed'])}")

    print()


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "auto":
        asyncio.run(check_and_heal())
    else:
        asyncio.run(interactive_healing())