#!/usr/bin/env python3
"""
🏥 AUTO-MONITORING - Surveillance continue 24/7
BugBrain surveille sa santé en permanence
"""

import asyncio
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import json
import aiofiles


class SystemMetrics:
    """Collecteur de métriques système"""

    @staticmethod
    def get_cpu_usage() -> float:
        """Utilisation CPU en %"""
        return psutil.cpu_percent(interval=1)

    @staticmethod
    def get_ram_usage() -> Dict:
        """Utilisation RAM"""
        ram = psutil.virtual_memory()
        return {
            "used_gb": ram.used / (1024**3),
            "total_gb": ram.total / (1024**3),
            "percent": ram.percent,
            "available_gb": ram.available / (1024**3)
        }

    @staticmethod
    def get_disk_usage(path: str = "/") -> Dict:
        """Utilisation disque"""
        disk = psutil.disk_usage(path)
        return {
            "used_gb": disk.used / (1024**3),
            "total_gb": disk.total / (1024**3),
            "percent": disk.percent,
            "free_gb": disk.free / (1024**3)
        }

    @staticmethod
    def get_network_stats() -> Dict:
        """Statistiques réseau"""
        net_io = psutil.net_io_counters()
        return {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv
        }

    @staticmethod
    def get_process_info(pid: int) -> Optional[Dict]:
        """Infos sur un processus"""
        try:
            proc = psutil.Process(pid)
            return {
                "pid": pid,
                "name": proc.name(),
                "cpu_percent": proc.cpu_percent(),
                "memory_mb": proc.memory_info().rss / (1024**2),
                "status": proc.status(),
                "create_time": datetime.fromtimestamp(proc.create_time()).isoformat()
            }
        except psutil.NoSuchProcess:
            return None


class HealthChecker:
    """Vérificateur de santé"""

    def __init__(self):
        self.thresholds = {
            "cpu_high": 90.0,        # % CPU
            "cpu_critical": 95.0,
            "ram_high": 85.0,        # % RAM
            "ram_critical": 95.0,
            "disk_high": 80.0,       # % Disque
            "disk_critical": 90.0
        }

    async def check_health(self) -> Dict:
        """
        Check complet de la santé
        """
        cpu = SystemMetrics.get_cpu_usage()
        ram = SystemMetrics.get_ram_usage()
        disk = SystemMetrics.get_disk_usage()

        issues = []

        # Vérification CPU
        if cpu > self.thresholds["cpu_critical"]:
            issues.append(f"CPU critique: {cpu:.1f}%")
        elif cpu > self.thresholds["cpu_high"]:
            issues.append(f"CPU élevé: {cpu:.1f}%")

        # Vérification RAM
        if ram["percent"] > self.thresholds["ram_critical"]:
            issues.append(f"RAM critique: {ram['percent']:.1f}%")
        elif ram["percent"] > self.thresholds["ram_high"]:
            issues.append(f"RAM élevée: {ram['percent']:.1f}%")

        # Vérification Disque
        if disk["percent"] > self.thresholds["disk_critical"]:
            issues.append(f"Disque critique: {disk['percent']:.1f}%")
        elif disk["percent"] > self.thresholds["disk_high"]:
            issues.append(f"Disque élevé: {disk['percent']:.1f}%")

        healthy = len(issues) == 0

        return {
            "healthy": healthy,
            "timestamp": datetime.now().isoformat(),
            "cpu": cpu,
            "ram": ram,
            "disk": disk,
            "issues": issues
        }


class MetricsCollector:
    """Collecteur de métriques historiques"""

    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics_history = []
        self.metrics_file = Path("logs/metrics.json")

    async def collect(self):
        """Collecte les métriques actuelles"""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "cpu": SystemMetrics.get_cpu_usage(),
            "ram": SystemMetrics.get_ram_usage(),
            "disk": SystemMetrics.get_disk_usage(),
            "network": SystemMetrics.get_network_stats()
        }

        self.metrics_history.append(metrics)

        # Garder uniquement les N dernières entrées
        if len(self.metrics_history) > self.max_history:
            self.metrics_history = self.metrics_history[-self.max_history:]

        # Sauvegarder dans le fichier
        await self.save()

        return metrics

    async def save(self):
        """Sauvegarde les métriques dans le fichier"""
        try:
            self.metrics_file.parent.mkdir(exist_ok=True)
            async with aiofiles.open(self.metrics_file, 'w') as f:
                await f.write(json.dumps(self.metrics_history, indent=2))
        except Exception as e:
            print(f"⚠️ Erreur sauvegarde métriques: {e}")

    def get_average_metrics(self, minutes: int = 60) -> Dict:
        """
        Retourne les métriques moyennes sur N minutes
        """
        cutoff = datetime.now() - timedelta(minutes=minutes)
        cutoff_str = cutoff.isoformat()

        recent_metrics = [
            m for m in self.metrics_history
            if m["timestamp"] >= cutoff_str
        ]

        if not recent_metrics:
            return {}

        # Calculer les moyennes
        cpu_avg = sum(m["cpu"] for m in recent_metrics) / len(recent_metrics)
        ram_avg = sum(m["ram"]["percent"] for m in recent_metrics) / len(recent_metrics)
        disk_avg = sum(m["disk"]["percent"] for m in recent_metrics) / len(recent_metrics)

        return {
            "period_minutes": minutes,
            "samples": len(recent_metrics),
            "cpu_avg": cpu_avg,
            "ram_avg": ram_avg,
            "disk_avg": disk_avg
        }


class AutoMonitor:
    """Moniteur automatique principal"""

    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval
        self.health_checker = HealthChecker()
        self.metrics_collector = MetricsCollector()
        self.is_running = False
        self.alerts_log = Path("logs/alerts.log")

    async def start(self):
        """Démarre la surveillance"""
        print("🏥 Démarrage de l'Auto-Monitoring...")
        self.is_running = True

        while self.is_running:
            await self.check_and_log()
            await asyncio.sleep(self.check_interval)

    async def stop(self):
        """Arrête la surveillance"""
        print("🏥 Arrêt de l'Auto-Monitoring...")
        self.is_running = False

    async def check_and_log(self):
        """Effectue un check et log"""
        # Collecter les métriques
        metrics = await self.metrics_collector.collect()

        # Vérifier la santé
        health = await self.health_checker.check_health()

        # Logger les alertes
        if not health["healthy"]:
            await self.log_alerts(health["issues"])

        # Afficher le status
        self.print_status(health, metrics)

    async def log_alerts(self, issues: List[str]):
        """Log les alertes"""
        alert = {
            "timestamp": datetime.now().isoformat(),
            "issues": issues
        }

        try:
            self.alerts_log.parent.mkdir(exist_ok=True)
            async with aiofiles.open(self.alerts_log, 'a') as f:
                await f.write(json.dumps(alert) + "\n")
        except Exception as e:
            print(f"⚠️ Erreur log alertes: {e}")

    def print_status(self, health: Dict, metrics: Dict):
        """Affiche le status"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        if health["healthy"]:
            print(f"✅ [{timestamp}] Système sain - CPU: {metrics['cpu']:.1f}% | RAM: {metrics['ram']['percent']:.1f}% | Disque: {metrics['disk']['percent']:.1f}%")
        else:
            print(f"⚠️ [{timestamp}] Problèmes détectés:")
            for issue in health["issues"]:
                print(f"   - {issue}")

    def get_status_report(self) -> Dict:
        """Retourne un rapport de status complet"""
        health = asyncio.run(self.health_checker.check_health())
        avg_metrics = self.metrics_collector.get_average_metrics(60)

        return {
            "health": health,
            "average_metrics_60min": avg_metrics,
            "total_metrics_samples": len(self.metrics_collector.metrics_history)
        }


# ============================================================================
# ============== INTERFACE CLI ==============================================
# ============================================================================

async def interactive_monitor():
    """Interface interactive de monitoring"""
    monitor = AutoMonitor(check_interval=30)

    print("=" * 70)
    print("🏥 AUTO-MONITORING - Surveillance en temps réel")
    print("=" * 70)
    print("Tapez 'stop' pour arrêter")
    print("Tapez 'report' pour le rapport complet")
    print()

    # Démarrer la surveillance en arrière-plan
    monitor_task = asyncio.create_task(monitor.start())

    try:
        while True:
            cmd = input("\n> ").strip().lower()

            if cmd in ['stop', 'quit', 'exit']:
                await monitor.stop()
                break

            elif cmd == 'report':
                report = monitor.get_status_report()
                print("\n📊 Rapport de Status:")
                print(json.dumps(report, indent=2))

            elif cmd == 'avg':
                avg = monitor.metrics_collector.get_average_metrics()
                print("\n📈 Métriques moyennes (60 min):")
                print(json.dumps(avg, indent=2))

    except KeyboardInterrupt:
        print("\n\n🛑 Interruption...")
        await monitor.stop()


async def check_once():
    """Effectue un seul check"""
    monitor = AutoMonitor()
    metrics = await monitor.metrics_collector.collect()
    health = await monitor.health_checker.check_health()

    print("=" * 70)
    print("🏥 CHECK DE SANTÉ")
    print("=" * 70)
    print()

    print(f"⏱️ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    print(f"CPU: {metrics['cpu']:.1f}%")
    print(f"RAM: {metrics['ram']['percent']:.1f}% ({metrics['ram']['used_gb']:.1f}GB / {metrics['ram']['total_gb']:.1f}GB)")
    print(f"Disque: {metrics['disk']['percent']:.1f}% ({metrics['disk']['used_gb']:.1f}GB / {metrics['disk']['total_gb']:.1f}GB)")
    print()

    if health["healthy"]:
        print("✅ Système sain")
    else:
        print("⚠️ Problèmes détectés:")
        for issue in health["issues"]:
            print(f"   - {issue}")

    print()


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "check":
        asyncio.run(check_once())
    else:
        asyncio.run(interactive_monitor())