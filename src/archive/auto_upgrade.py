#!/usr/bin/env python3
"""
🔄 AUTO-UPGRADE - Mises à jour automatiques
BugBrain se met à jour automatiquement depuis GitHub
"""

import asyncio
import subprocess
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path
import json
import aiofiles
import os
import hashlib


class AutoUpgrader:
    """Gestionnaire de mises à jour automatiques"""

    def __init__(self, repo_url: str = "https://github.com/dnshouet-cpu/Unitybrain.git"):
        self.repo_url = repo_url
        self.version_file = Path("VERSION")
        self.upgrade_log = Path("logs/upgrades.log")
        self.backup_dir = Path("backups")

    async def check_updates(self) -> Optional[Dict]:
        """
        Vérifie s'il y a des mises à jour disponibles
        """
        try:
            # Récupérer la version actuelle
            current_version = await self.get_current_version()

            # Récupérer la dernière version depuis GitHub
            latest_version = await self.get_latest_version()

            if latest_version and latest_version != current_version:
                return {
                    "current_version": current_version,
                    "latest_version": latest_version,
                    "update_available": True,
                    "update_type": self.get_update_type(current_version, latest_version)
                }

            return {
                "current_version": current_version,
                "latest_version": latest_version,
                "update_available": False
            }

        except Exception as e:
            print(f"⚠️ Erreur vérification mises à jour: {e}")
            return None

    async def get_current_version(self) -> str:
        """Retourne la version actuelle"""
        try:
            # Lire depuis le fichier VERSION
            if self.version_file.exists():
                with open(self.version_file) as f:
                    return f.read().strip()

            # Essayer avec git
            result = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                return result.stdout.strip()

            return "unknown"

        except Exception as e:
            print(f"⚠️ Erreur récupération version actuelle: {e}")
            return "unknown"

    async def get_latest_version(self) -> Optional[str]:
        """Retourne la dernière version depuis GitHub"""
        try:
            # Utiliser GitHub API
            result = subprocess.run(
                ["gh", "release", "view", "--json", "tagName"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Parser le JSON
                import json
                data = json.loads(result.stdout)
                return data.get("tagName")

            return None

        except Exception as e:
            print(f"⚠️ Erreur récupération dernière version: {e}")
            return None

    def get_update_type(self, current: str, latest: str) -> str:
        """
        Détermine le type de mise à jour
        """
        if not current or current == "unknown":
            return "initial"

        current_parts = current.split(".")
        latest_parts = latest.split(".")

        if len(current_parts) >= 2 and len(latest_parts) >= 2:
            if current_parts[0] != latest_parts[0]:
                return "major"
            elif current_parts[1] != latest_parts[1]:
                return "minor"
            else:
                return "patch"

        return "unknown"

    async def create_backup(self) -> bool:
        """Crée une sauvegarde avant mise à jour"""
        try:
            self.backup_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"backup_{timestamp}.tar.gz"

            print(f"💾 Création de la sauvegarde: {backup_path}")

            # Créer l'archive
            subprocess.run(
                ["tar", "-czf", str(backup_path), "."],
                capture_output=True,
                timeout=300
            )

            print("✅ Sauvegarde créée")
            return True

        except Exception as e:
            print(f"❌ Erreur création sauvegarde: {e}")
            return False

    async def upgrade(self, force: bool = False) -> Dict:
        """
        Effectue la mise à jour automatique
        """
        result = {
            "success": False,
            "from_version": None,
            "to_version": None,
            "backup_created": False,
            "timestamp": datetime.now().isoformat()
        }

        try:
            # Vérifier les mises à jour
            update_info = await self.check_updates()

            if not update_info:
                print("⚠️ Impossible de vérifier les mises à jour")
                result["error"] = "Cannot check updates"
                return result

            if not force and not update_info.get("update_available"):
                print("✅ Aucune mise à jour disponible")
                result["message"] = "No updates available"
                return result

            result["from_version"] = update_info["current_version"]
            result["to_version"] = update_info["latest_version"]

            print(f"🔄 Mise à jour: {result['from_version']} → {result['to_version']}")
            print(f"Type: {update_info.get('update_type', 'unknown')}")

            # Confirmer si ce n'est pas forcé
            if not force:
                choice = input("Confirmer la mise à jour ? (y/n): ").strip().lower()
                if choice != 'y':
                    print("❌ Mise à jour annulée")
                    return result

            # Créer une sauvegarde
            print()
            backup_created = await self.create_backup()
            result["backup_created"] = backup_created

            if not backup_created:
                print("⚠️ Sauvegarde échouée, annulation...")
                result["error"] = "Backup failed"
                return result

            # Effectuer la mise à jour
            print()
            print("🔄 Téléchargement de la mise à jour...")

            # Fetch depuis GitHub
            fetch_result = subprocess.run(
                ["git", "fetch", "origin"],
                capture_output=True,
                text=True,
                timeout=300
            )

            if fetch_result.returncode != 0:
                print("❌ Erreur fetch")
                result["error"] = "Git fetch failed"
                return result

            # Checkout de la nouvelle version
            print("🔄 Installation de la mise à jour...")

            checkout_result = subprocess.run(
                ["git", "checkout", f"tags/{result['to_version']}"],
                capture_output=True,
                text=True,
                timeout=60
            )

            if checkout_result.returncode != 0:
                print("❌ Erreur checkout")
                result["error"] = "Git checkout failed"
                return result

            # Mettre à jour les dépendances
            print("🔄 Mise à jour des dépendances...")

            subprocess.run(
                ["pip", "install", "-r", "requirements.txt", "--break-system-packages"],
                capture_output=True,
                timeout=300
            )

            print("✅ Mise à jour terminée avec succès !")

            # Logger
            await self.log_upgrade(result)

            result["success"] = True

            return result

        except Exception as e:
            print(f"❌ Erreur mise à jour: {e}")
            result["error"] = str(e)
            return result

    async def rollback(self, backup_file: str) -> bool:
        """
        Annule une mise à jour en restaurant une sauvegarde
        """
        try:
            backup_path = self.backup_dir / backup_file

            if not backup_path.exists():
                print(f"❌ Sauvegarde non trouvée: {backup_file}")
                return False

            print(f"🔄 Restauration de: {backup_file}")

            # Extraire l'archive
            subprocess.run(
                ["tar", "-xzf", str(backup_path)],
                capture_output=True,
                timeout=300
            )

            print("✅ Restauration terminée")
            return True

        except Exception as e:
            print(f"❌ Erreur restauration: {e}")
            return False

    async def log_upgrade(self, result: Dict):
        """Log la mise à jour"""
        try:
            self.upgrade_log.parent.mkdir(exist_ok=True)
            async with aiofiles.open(self.upgrade_log, 'a') as f:
                await f.write(json.dumps(result, indent=2) + "\n")
        except Exception as e:
            print(f"⚠️ Erreur log mise à jour: {e}")


# ============================================================================
# ============== INTERFACE CLI ==============================================
# ============================================================================

async def check_upgrade():
    """Vérifie les mises à jour disponibles"""
    upgrader = AutoUpgrader()

    print("=" * 70)
    print("🔄 VÉRIFICATION DES MISES À JOUR")
    print("=" * 70)
    print()

    update_info = await upgrader.check_updates()

    if not update_info:
        print("❌ Impossible de vérifier les mises à jour")
        return

    print(f"Version actuelle: {update_info['current_version']}")
    print(f"Dernière version: {update_info['latest_version']}")
    print()

    if update_info["update_available"]:
        print("✅ Mise à jour disponible !")
        print(f"Type: {update_info.get('update_type', 'unknown')}")
        print()
        print("Pour effectuer la mise à jour, exécutez:")
        print("  python3 -m src.auto_upgrade upgrade")
    else:
        print("✅ Vous êtes à jour !")


async def do_upgrade(force: bool = False):
    """Effectue la mise à jour"""
    upgrader = AutoUpgrader()

    print("=" * 70)
    print("🔄 MISE À JOUR AUTOMATIQUE")
    print("=" * 70)
    print()

    result = await upgrader.upgrade(force=force)

    print()
    print("📊 Résultat:")

    if result["success"]:
        print("✅ Mise à jour réussie !")
        print(f"   De: {result['from_version']}")
        print(f"   À: {result['to_version']}")
        print(f"   Sauvegarde: {'Oui' if result['backup_created'] else 'Non'}")
    else:
        print("❌ Mise à jour échouée")
        print(f"   Erreur: {result.get('error', 'Unknown')}")


async def list_backups():
    """Liste les sauvegardes disponibles"""
    backup_dir = Path("backups")

    if not backup_dir.exists():
        print("❌ Aucune sauvegarde disponible")
        return

    print("=" * 70)
    print("💾 SAUVEGARDES DISPONIBLES")
    print("=" * 70)
    print()

    backups = sorted(backup_dir.glob("backup_*.tar.gz"))

    if not backups:
        print("❌ Aucune sauvegarde disponible")
        return

    for i, backup in enumerate(backups, 1):
        size_mb = backup.stat().st_size / (1024**2)
        print(f"{i}. {backup.name} ({size_mb:.1f} MB)")


async def do_rollback():
    """Effectue un rollback"""
    await list_backups()

    print()
    backup_file = input("Nom de la sauvegarde à restaurer: ").strip()

    upgrader = AutoUpgrader()
    success = await upgrader.rollback(backup_file)

    if success:
        print("\n✅ Rollback réussi !")
    else:
        print("\n❌ Rollback échoué")


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "check":
            asyncio.run(check_upgrade())
        elif command == "upgrade":
            force = len(sys.argv) > 2 and sys.argv[2] == "--force"
            asyncio.run(do_upgrade(force))
        elif command == "backups":
            asyncio.run(list_backups())
        elif command == "rollback":
            asyncio.run(do_rollback())
        else:
            print("Usage: python3 -m src.auto_upgrade [check|upgrade|backups|rollback]")
    else:
        asyncio.run(check_upgrade())