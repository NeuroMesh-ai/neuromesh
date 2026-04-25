# Auto-imports for extracted module
from typing import Dict
from typing import List
import time


class QueryHistory:
    def __init__(self, max_entries: int = 1000):
        self.history: List[Dict] = []
        self.max_entries = max_entries

    async def add(self, query: Dict):
        self.history.append({"timestamp": time.time(), **query})
        if len(self.history) > self.max_entries:
            self.history.pop(0)

    async def get(self, limit: int = 10) -> List[Dict]:
        return self.history[-limit:]


# ============================================================================
# ============== DISTRIBUTED MEMORY ======================================
# ============================================================================
