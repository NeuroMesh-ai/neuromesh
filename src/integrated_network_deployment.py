#!/usr/bin/env python3
"""
🌐🚀 NETWORK & DEPLOYMENT INTEGRATION
Intégration complète des modules réseau et déploiement pour UnityBrain & BugBrain v3.0
"""

import asyncio
import sys
from network_specialization import NetworkManager, NetworkConfig, NetworkNode, NodeStatus
from deployment_module import DeploymentManager, DeploymentConfig

# ============================================================================
# ============== INTEGRATED MANAGER ========================================
# ============================================================================

class IntegratedManager:
    """Manager intégré - Réseau + Déploiement"""
    def __init__(self):
        # Configuration
        self.network_config = NetworkConfig()
        self.deployment_config = DeploymentConfig()

        # Managers
        self.network = None
        self.deployment = None

        # Status
        self.running = False

    async def initialize(self):
        """Initialise le système intégré"""
        print("\n" + "=" * 70)
        print("🌐🚀 INTEGRATED NETWORK & DEPLOYMENT MANAGER")
        print("=" * 70)

        # Initialize Network
        print(f"\n🌐 Initializing Network Specialization...")
        self.network = NetworkManager(self.network_config)
        await self.network.initialize()

        # Initialize Deployment
        print(f"\n🚀 Initializing Deployment Module...")
        self.deployment = DeploymentManager(self.deployment_config)

        print(f"\n✅ Integrated System initialized!")

    async def start(self):
        """Démarre le système intégré"""
        print(f"\n🚀 Starting Integrated System...")

        # Start Network
        await self.network.start()

        # Deploy initial nodes
        print(f"\n📦 Deploying initial nodes...")
        await self.deployment.deploy_node("unitybrain-node", "0.0.0.0", 9999, "/tmp/unitybrain_v3_final.py")
        await self.deployment.deploy_node("bugbrain-node", "0.0.0.0", 10000, "/tmp/bugbrain_v3_final.py")

        # Start background tasks
        self.running = True

        # Create backup
        await self.deployment.create_backup()

        print(f"\n✅ Integrated System started!")

    async def stop(self):
        """Arrête le système intégré"""
        print(f"\n🛑 Stopping Integrated System...")

        self.running = False

        # Stop Deployment
        for node_id in list(self.deployment.deployments.keys()):
            await self.deployment.stop_node(node_id)

        # Stop Network
        await self.network.stop()

        print(f"\n✅ Integrated System stopped!")

    async def get_status(self) -> dict:
        """Statut du système intégré"""
        network_status = await self.network.get_status()
        deployment_status = await self.deployment.get_status()

        return {
            "network": network_status,
            "deployment": deployment_status,
            "running": self.running
        }

    async def monitor(self):
        """Monitoring continu"""
        print(f"\n📊 Starting continuous monitoring...")

        while self.running:
            # Auto-scale
            await self.deployment.auto_scale()

            # Auto-heal
            await self.deployment.auto_heal()

            # Status
            status = await self.get_status()

            print(f"\n" + "=" * 70)
            print(f"📊 SYSTEM STATUS")
            print(f"=" * 70)

            print(f"\n🌐 Network:")
            print(f"   Active Nodes: {status['network']['nodes']['active']}/{status['network']['nodes']['total']}")
            print(f"   Local Node: {status['network']['local_node']['name']}")

            print(f"\n🚀 Deployment:")
            print(f"   Running: {status['deployment']['deployments']['running']}/{status['deployment']['deployments']['total']}")
            print(f"   Failed: {status['deployment']['deployments']['failed']}")
            print(f"   Backups: {status['deployment']['backups']['total']}")

            # Wait
            await asyncio.sleep(60)

# ============================================================================
# ============== CLI INTEGRATED ============================================
# ============================================================================

class IntegratedCLI:
    """CLI intégrée pour le système"""
    def __init__(self):
        self.manager = IntegratedManager()

    async def initialize_and_start(self):
        """Initialise et démarre"""
        await self.manager.initialize()
        await self.manager.start()

    async def run(self):
        """Exécute la CLI"""
        await self.initialize_and_start()

        print("\n" + "=" * 70)
        print("🎮 INTEGRATED CLI - Network & Deployment")
        print("=" * 70)
        print("\nCommandes disponibles:")
        print("   status          - Affiche le statut")
        print("   scale <count>   - Scale le déploiement")
        print("   update <script> - Rolling update")
        print("   backup          - Crée une sauvegarde")
        print("   restore <id>    - Restore une sauvegarde")
        print("   monitor         - Monitoring continu")
        print("   help            - Affiche l'aide")
        print("   quit            - Quitte")
        print("=" * 70)

        # Start monitoring in background
        monitor_task = asyncio.create_task(self.manager.monitor())

        try:
            while True:
                user_input = input(f"\n[Integrated]> ").strip()

                if not user_input:
                    continue

                parts = user_input.split(maxsplit=1)
                command = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""

                if command == 'quit' or command == 'exit':
                    print("\n👋 Au revoir!")
                    break

                elif command == 'help':
                    await self.show_help()

                elif command == 'status':
                    await self.show_status()

                elif command == 'scale':
                    if args.isdigit():
                        await self.scale_deployment(int(args))
                    else:
                        print("❌ Usage: scale <count>")

                elif command == 'update':
                    if args:
                        await self.rolling_update(args)
                    else:
                        print("❌ Usage: update <script_path>")

                elif command == 'backup':
                    await self.create_backup()

                elif command == 'restore':
                    if args:
                        await self.restore_backup(args)
                    else:
                        print("❌ Usage: restore <backup_id>")

                elif command == 'monitor':
                    print("Monitoring already running in background...")

                else:
                    print(f"❌ Commande inconnue: {command}")
                    print("   Tapez 'help' pour la liste des commandes")

        except KeyboardInterrupt:
            print("\n\n👋 Interruption détectée. Au revoir!")
        finally:
            monitor_task.cancel()
            await self.manager.stop()

    async def show_help(self):
        """Affiche l'aide"""
        print("\n" + "=" * 70)
        print("📚 COMMANDES DISPONIBLES")
        print("=" * 70)
        print("\n📊 Status:")
        print("   status - Affiche le statut complet du système")
        print("\n🚀 Deployment:")
        print("   scale <count>   - Scale le déploiement à <count> nœuds")
        print("   update <script> - Rolling update avec un nouveau script")
        print("\n💾 Backup:")
        print("   backup          - Crée une sauvegarde")
        print("   restore <id>    - Restore une sauvegarde")
        print("\n🔍 Monitoring:")
        print("   monitor         - Monitoring continu (déjà en background)")
        print("\n❓ Autre:")
        print("   help            - Affiche cette aide")
        print("   quit            - Quitte")

    async def show_status(self):
        """Affiche le statut"""
        status = await self.manager.get_status()

        print("\n" + "=" * 70)
        print("📊 SYSTÈME STATUS")
        print("=" * 70)

        print("\n🌐 Network:")
        print(f"   Local Node: {status['network']['local_node']['name']}")
        print(f"   Host: {status['network']['local_node']['host']}:{status['network']['local_node']['port']}")
        print(f"   Active Nodes: {status['network']['nodes']['active']}/{status['network']['nodes']['total']}")
        for node in status['network']['nodes']['list']:
            print(f"      - {node['name']} ({node['host']}:{node['port']}) - {node['status']}")

        print("\n🚀 Deployment:")
        print(f"   Running: {status['deployment']['deployments']['running']}/{status['deployment']['deployments']['total']}")
        print(f"   Failed: {status['deployment']['deployments']['failed']}")
        print(f"   Stopped: {status['deployment']['deployments']['stopped']}")
        for node in status['deployment']['nodes']:
            print(f"      - {node['node_id']} - {node['status']} (health: {node['health']})")

        print(f"\n💾 Backups:")
        print(f"   Total: {status['deployment']['backups']['total']}")
        print(f"   Latest: {status['deployment']['backups']['latest']}")

    async def scale_deployment(self, target_count: int):
        """Scale le déploiement"""
        print(f"\n📈 Scaling deployment to {target_count} nodes...")
        await self.manager.deployment.scale_deployment(target_count)
        print("✅ Scaling completed")

    async def rolling_update(self, script_path: str):
        """Rolling update"""
        print(f"\n🔄 Rolling update with {script_path}...")
        await self.manager.deployment.rolling_update(script_path)
        print("✅ Update completed")

    async def create_backup(self):
        """Crée une sauvegarde"""
        await self.manager.deployment.create_backup()

    async def restore_backup(self, backup_id: str):
        """Restore une sauvegarde"""
        print(f"\n🔄 Restoring backup {backup_id}...")
        await self.manager.deployment.restore_backup(backup_id)
        print("✅ Restore completed")

# ============================================================================
# ============== MAIN ========================================================
# ============================================================================

async def main():
    """Main function"""
    cli = IntegratedCLI()
    await cli.run()

if __name__ == '__main__':
    asyncio.run(main())