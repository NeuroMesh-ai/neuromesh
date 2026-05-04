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

# Ajouter le chemin au src (Unitybrain/ doit être dans le path)
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import direct des modules sans "src."
from src.auto_support import AutoSupport, KnowledgeBase
from src.auto_monitoring import AutoMonitor, SystemMetrics, HealthChecker
from src.auto_healing import AutoHealer, IssueDetector
from src.auto_optimization import AutoOptimizer
from src.auto_upgrade import AutoUpgrader