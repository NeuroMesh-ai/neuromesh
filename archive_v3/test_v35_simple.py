#!/usr/bin/env python3
"""
🧪 BUGBRAIN v3.5 - TEST RAPIDE
Test rapide des modules d'autonomie
"""

import asyncio
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_modules():
    """Test rapide des modules"""
    print("=" * 70)
    print("🧪 BUGBRAIN v3.5 - TEST RAPIDE")
    print("=" * 70)
    print()

    passed = 0
    failed = 0

    # Test 1: Auto-Support
    print("🤖 Test: Auto-Support...")
    try:
        # Importer depuis le fichier
        exec(open("src/auto_support.py").read(), globals())

        # Créer instance
        support = AutoSupport()
        initialized = await support.initialize()

        if initialized:
            print("  ✅ PASS")
            passed += 1
        else:
            print("  ❌ FAIL: Initialisation échouée")
            failed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1

    # Test 2: Auto-Monitoring
    print("🏥 Test: Auto-Monitoring...")
    try:
        exec(open("src/auto_monitoring.py").read(), globals())

        # Test des métriques
        cpu = SystemMetrics.get_cpu_usage()
        ram = SystemMetrics.get_ram_usage()

        print(f"  ✅ PASS (CPU: {cpu:.1f}%, RAM: {ram['percent']:.1f}%)")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1

    # Test 3: Auto-Healing
    print("🩹 Test: Auto-Healing...")
    try:
        exec(open("src/auto_healing.py").read(), globals())

        healer = AutoHealer()
        result = await healer.heal_all([])

        print("  ✅ PASS")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1

    # Test 4: Auto-Optimization
    print("📈 Test: Auto-Optimization...")
    try:
        exec(open("src/auto_optimization.py").read(), globals())

        optimizer = AutoOptimizer()
        result = await optimizer.optimize()

        print("  ✅ PASS")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1

    # Test 5: Auto-Upgrade
    print("🔄 Test: Auto-Upgrade...")
    try:
        exec(open("src/auto_upgrade.py").read(), globals())

        upgrader = AutoUpgrader()
        version = await upgrader.get_current_version()

        print(f"  ✅ PASS (Version: {version})")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1

    # Résumé
    print()
    print("=" * 70)
    print("📊 RÉSUMÉ")
    print("=" * 70)
    print(f"Total:  {passed + failed}")
    print(f"✅ Pass: {passed}")
    print(f"❌ Fail: {failed}")
    print(f"📊 Taux: {passed/(passed+failed):.2%}")
    print()

    if failed == 0:
        print("✅ TOUS LES TESTS ONT RÉUSSI")
        print("🚀 PRÊT POUR LA PUBLICATION !")
        return True
    else:
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        return False


if __name__ == '__main__':
    success = asyncio.run(test_modules())
    sys.exit(0 if success else 1)