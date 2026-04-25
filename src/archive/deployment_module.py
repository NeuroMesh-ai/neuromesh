#!/usr/bin/env python3
"""
🚀 DEPLOYMENT MODULE
Module de déploiement pour UnityBrain & BugBrain v3.0
Auto-déploiement, scaling, monitoring, rolling updates
"""

import asyncio
import json
import os
import subprocess
import shutil
import time
import hashlib
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field
import tarfile
import requests

# ============================================================================
# ============== DEPLOYMENT CONFIG =========================================
# ============================================================================

@dataclass
class DeploymentConfig:
    """Configuration de déploiement"""
    deployment_name: str = "unitybrain-deployment"
    environment: str = "production"  # development, staging, production
    node_count: int = 1
    min_nodes: int = 1
    max_nodes: int = 5
    auto_scaling: bool = True
    auto_healing: bool = True

    # Resource limits
    cpu_limit: float = 1.0
    memory_limit: str = "2GB"
    disk_limit: str = "10GB"

    # Updates
    rolling_update: bool = True
    update_batch_size: int = 1
    health_check_interval: int = 30

    # Monitoring
    metrics_enabled: bool = True
    logs_enabled: bool = True
    alert_enabled: bool = True

    # Backup
    backup_enabled: bool = True
    backup_interval: int = 3600  # 1 hour
    backup_retention: int = 7  # 7 days

# ============================================================================
# ============== NODE DEPLOYMENT ==========================================
# ============================================================================

@dataclass
class NodeDeployment:
    """Déploiement d'un nœud"""
    node_id: str
    deployment_id: str
    host: str
    port: int
    status: str = "deploying"  # deploying, running, stopped, failed
    pid: Optional[int] = None
    start_time: float = 0.0
    health_status: str = "unknown"

# ============================================================================
# ============== DEPLOYMENT MANAGER =======================================
# ============================================================================

class DeploymentManager:
    """Manager de déploiement"""
    def __init__(self, config: DeploymentConfig = None):
        self.config = config or DeploymentConfig()
        self.deployments: Dict[str, NodeDeployment] = {}
        self.deployment_history: List[Dict] = []
        self.backups: Dict[str, str] = {}

    async def deploy_node(self, node_id: str, host: str, port: int,
                          script_path: str = None) -> NodeDeployment:
        """Déploie un nœud"""
        print(f"\n🚀 Deploying node {node_id} on {host}:{port}...")

        deployment = NodeDeployment(
            node_id=node_id,
            deployment_id=self._generate_deployment_id(),
            host=host,
            port=port
        )

        try:
            # Deploy script
            if script_path and os.path.exists(script_path):
                await self._deploy_script(script_path, host, port)

            # Start node
            pid = await self._start_node(host, port, script_path)
            deployment.pid = pid
            deployment.status = "running"
            deployment.start_time = time.time()

            # Health check
            health = await self._health_check(host, port)
            deployment.health_status = health

            print(f"   ✅ Node {node_id} deployed successfully")

        except Exception as e:
            deployment.status = "failed"
            print(f"   ❌ Failed to deploy node {node_id}: {e}")

        self.deployments[node_id] = deployment
        self._record_deployment(deployment)

        return deployment

    async def _deploy_script(self, script_path: str, host: str, port: int):
        """Déploie le script sur un nœud"""
        print(f"   📦 Deploying script: {script_path}")

        # Copy script to target (simplified - in reality would use SSH/SCP)
        target_dir = f"/tmp/unitybrain_deployment_{port}"
        os.makedirs(target_dir, exist_ok=True)

        # Copy files
        shutil.copy(script_path, f"{target_dir}/main.py")

        print(f"   ✅ Script deployed to {target_dir}")

    async def _start_node(self, host: str, port: int, script_path: str) -> int:
        """Démarre un nœud"""
        print(f"   ▶️ Starting node on {host}:{port}")

        # Start process (simplified - in reality would use systemd/Docker)
        if script_path:
            cmd = ["python3", script_path]
        else:
            cmd = ["python3", "/tmp/unitybrain_v3_final.py"]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )

        return process.pid

    async def _health_check(self, host: str, port: int) -> str:
        """Vérifie la santé d'un nœud"""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                return "healthy"
            else:
                return "unhealthy"
        except Exception:
            return "unhealthy"

    async def stop_node(self, node_id: str):
        """Arrête un nœud"""
        if node_id not in self.deployments:
            print(f"   ⚠️ Node {node_id} not found")
            return

        deployment = self.deployments[node_id]
        print(f"\n🛑 Stopping node {node_id}...")

        try:
            if deployment.pid:
                # Kill process
                os.kill(deployment.pid, 9)
                print(f"   ✅ Node {node_id} stopped")
        except Exception as e:
            print(f"   ⚠️ Failed to stop node {node_id}: {e}")

        deployment.status = "stopped"

    async def scale_deployment(self, target_count: int):
        """Scale le déploiement"""
        print(f"\n📈 Scaling deployment to {target_count} nodes...")

        current_count = len(self._get_running_nodes())

        if target_count > current_count:
            # Scale up
            nodes_to_add = target_count - current_count
            print(f"   ▲ Scaling up: adding {nodes_to_add} nodes")

            for i in range(nodes_to_add):
                node_id = f"node-{len(self.deployments) + 1}"
                host = "0.0.0.0"
                port = 9999 + len(self.deployments) + 1

                await self.deploy_node(node_id, host, port)

        elif target_count < current_count:
            # Scale down
            nodes_to_remove = current_count - target_count
            print(f"   ▼ Scaling down: removing {nodes_to_remove} nodes")

            running_nodes = self._get_running_nodes()
            for i in range(min(nodes_to_remove, len(running_nodes))):
                await self.stop_node(running_nodes[i].node_id)

    async def rolling_update(self, new_script_path: str):
        """Rolling update"""
        print(f"\n🔄 Rolling update with {new_script_path}...")

        running_nodes = self._get_running_nodes()
        batch_size = self.config.update_batch_size

        for i in range(0, len(running_nodes), batch_size):
            batch = running_nodes[i:i+batch_size]

            print(f"\n   📦 Updating batch {i // batch_size + 1}/{(len(running_nodes) + batch_size - 1) // batch_size}")

            # Stop batch
            for node in batch:
                await self.stop_node(node.node_id)

            # Wait for health check
            await asyncio.sleep(5)

            # Start batch with new script
            for node in batch:
                await self.deploy_node(node.node_id, node.host, node.port, new_script_path)

            # Wait for health check
            await asyncio.sleep(self.config.health_check_interval)

        print(f"\n   ✅ Rolling update completed")

    async def auto_scale(self):
        """Auto-scaling basé sur les metrics"""
        if not self.config.auto_scaling:
            return

        # Get metrics
        metrics = await self._get_metrics()

        # Check CPU usage
        if metrics.get("cpu_usage", 0) > 80:
            # Scale up
            new_count = min(len(self.deployments) + 1, self.config.max_nodes)
            await self.scale_deployment(new_count)
        elif metrics.get("cpu_usage", 0) < 20 and len(self.deployments) > self.config.min_nodes:
            # Scale down
            new_count = max(len(self.deployments) - 1, self.config.min_nodes)
            await self.scale_deployment(new_count)

    async def auto_heal(self):
        """Auto-healing"""
        if not self.config.auto_healing:
            return

        for node_id, deployment in self.deployments.items():
            if deployment.status == "running":
                health = await self._health_check(deployment.host, deployment.port)

                if health == "unhealthy":
                    print(f"\n   🔧 Auto-healing node {node_id}...")

                    # Stop unhealthy node
                    await self.stop_node(node_id)

                    # Redeploy
                    await self.deploy_node(node_id, deployment.host, deployment.port)

    async def create_backup(self):
        """Crée une sauvegarde"""
        if not self.config.backup_enabled:
            return

        backup_id = self._generate_backup_id()
        backup_path = f"/tmp/backup_{backup_id}.tar.gz"

        print(f"\n💾 Creating backup {backup_id}...")

        with tarfile.open(backup_path, "w:gz") as tar:
            tar.add("/tmp", arcname="tmp")

        self.backups[backup_id] = backup_path
        print(f"   ✅ Backup created: {backup_path}")

        # Cleanup old backups
        await self._cleanup_old_backups()

    async def restore_backup(self, backup_id: str):
        """Restore une sauvegarde"""
        if backup_id not in self.backups:
            print(f"   ⚠️ Backup {backup_id} not found")
            return

        backup_path = self.backups[backup_id]
        print(f"\n🔄 Restoring backup {backup_id} from {backup_path}...")

        with tarfile.open(backup_path, "r:gz") as tar:
            tar.extractall("/")

        print(f"   ✅ Backup restored")

    async def _cleanup_old_backups(self):
        """Nettoie les anciennes sauvegardes"""
        while len(self.backups) > self.config.backup_retention:
            oldest = min(self.backups.keys())
            os.remove(self.backups[oldest])
            del self.backups[oldest]

    async def _get_metrics(self) -> Dict:
        """Récupère les metrics"""
        # Simplifié - en réalité collecterait les metrics réels
        return {
            "cpu_usage": 50.0,
            "memory_usage": 60.0,
            "active_connections": 10
        }

    def _get_running_nodes(self) -> List[NodeDeployment]:
        """Retourne les nœuds en cours d'exécution"""
        return [
            deployment for deployment in self.deployments.values()
            if deployment.status == "running"
        ]

    def _generate_deployment_id(self) -> str:
        """Génère un ID de déploiement"""
        return f"deploy-{int(time.time())}"

    def _generate_backup_id(self) -> str:
        """Génère un ID de sauvegarde"""
        return f"backup-{int(time.time())}"

    def _record_deployment(self, deployment: NodeDeployment):
        """Enregistre un déploiement dans l'historique"""
        self.deployment_history.append({
            "timestamp": time.time(),
            "deployment_id": deployment.deployment_id,
            "node_id": deployment.node_id,
            "host": deployment.host,
            "port": deployment.port,
            "status": deployment.status
        })

    async def get_status(self) -> Dict:
        """Statut du déploiement"""
        running_nodes = self._get_running_nodes()

        return {
            "config": {
                "deployment_name": self.config.deployment_name,
                "environment": self.config.environment,
                "node_count": self.config.node_count,
                "min_nodes": self.config.min_nodes,
                "max_nodes": self.config.max_nodes,
                "auto_scaling": self.config.auto_scaling,
                "auto_healing": self.config.auto_healing
            },
            "deployments": {
                "total": len(self.deployments),
                "running": len(running_nodes),
                "failed": len([d for d in self.deployments.values() if d.status == "failed"]),
                "stopped": len([d for d in self.deployments.values() if d.status == "stopped"])
            },
            "nodes": [
                {
                    "node_id": d.node_id,
                    "host": d.host,
                    "port": d.port,
                    "status": d.status,
                    "health": d.health_status
                }
                for d in self.deployments.values()
            ],
            "backups": {
                "total": len(self.backups),
                "latest": list(self.backups.keys())[-1] if self.backups else None
            }
        }

# ============================================================================
# ============== MAIN ========================================================
# ============================================================================

async def main():
    """Main function"""
    print("=" * 70)
    print("🚀 DEPLOYMENT MODULE")
    print("=" * 70)
    print("\n✅ Auto-Deployment")
    print("✅ Scaling")
    print("✅ Rolling Updates")
    print("✅ Auto-Healing")
    print("✅ Backups")

    # Create deployment manager
    config = DeploymentConfig(
        deployment_name="unitybrain-deployment",
        node_count=2,
        auto_scaling=True,
        auto_healing=True
    )
    deployment = DeploymentManager(config)

    # Deploy nodes
    print(f"\n📦 Deploying {config.node_count} nodes...")
    await deployment.deploy_node("node-1", "0.0.0.0", 9999, "/tmp/unitybrain_v3_final.py")
    await deployment.deploy_node("node-2", "0.0.0.0", 10000, "/tmp/bugbrain_v3_final.py")

    # Status
    status = await deployment.get_status()
    print(f"\n📊 Status:")
    print(f"   Running nodes: {status['deployments']['running']}/{status['deployments']['total']}")

    # Create backup
    await deployment.create_backup()

    print(f"\n✅ Deployment completed!")

    # Keep running
    try:
        while True:
            await asyncio.sleep(60)

            # Auto-scale
            await deployment.auto_scale()

            # Auto-heal
            await deployment.auto_heal()

            # Status
            status = await deployment.get_status()
            print(f"\n📊 [Every 60s] Running nodes: {status['deployments']['running']}/{status['deployments']['total']}")

    except KeyboardInterrupt:
        print("\n\n🛑 Stopping deployment...")

        # Stop all nodes
        for node_id in list(deployment.deployments.keys()):
            await deployment.stop_node(node_id)

if __name__ == '__main__':
    asyncio.run(main())