#!/usr/bin/env python3
"""Persistent Shared Memory for UnityBrain P2P Network - JSON file-based, git-synced."""

import json, os, sys, time, threading, logging, subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class PersistentSharedMemory:
    CATEGORIES = ["core", "context", "queries", "system"]

    def __init__(self, base_path: str, node_name: str = "unknown"):
        self.base_path = Path(base_path)
        self.node_name = node_name
        self.meta_path = self.base_path / "_meta.json"
        self._lock = threading.Lock()
        for cat in self.CATEGORIES:
            (self.base_path / cat).mkdir(parents=True, exist_ok=True)
        self._meta = self._load_meta()

    def _load_meta(self) -> Dict:
        if self.meta_path.exists():
            try:
                with open(self.meta_path) as f: return json.load(f)
            except Exception: pass
        meta = {"created": datetime.now().isoformat(), "node": self.node_name, "version": "1.0",
                "last_sync": None, "total_entries": 0, "last_updated": datetime.now().isoformat()}
        self._save_meta(meta)
        return meta

    def _save_meta(self, meta: Dict = None):
        meta = meta or self._meta
        meta["last_updated"] = datetime.now().isoformat()
        meta["total_entries"] = self.count()
        with open(self.meta_path, 'w') as f: json.dump(meta, f, indent=2)

    def _entry_path(self, key: str, category: str = None) -> Path:
        safe = key.replace('/', '_').replace(' ', '_').replace(':', '_')
        return self.base_path / (category or "core") / f"{safe}.json"

    def _find_entry_path(self, key: str) -> Optional[Path]:
        for cat in self.CATEGORIES:
            p = self._entry_path(key, cat)
            if p.exists(): return p
        return None

    def set(self, key: str, value: Any, category: str = "core",
            tags: List[str] = None, source: str = None) -> Dict:
        with self._lock:
            path = self._entry_path(key, category)
            now = datetime.now().isoformat()
            if path.exists():
                with open(path) as f: entry = json.load(f)
                entry.update({"value": value, "tags": tags or entry.get("tags", []),
                              "updated": now, "version": entry.get("version", 0) + 1,
                              "last_accessed": now, "source": source or self.node_name})
            else:
                entry = {"key": key, "value": value, "category": category,
                         "tags": tags or [], "source": source or self.node_name,
                         "created": now, "updated": now, "version": 1, "last_accessed": now}
            with open(path, 'w') as f: json.dump(entry, f, indent=2)
            self._save_meta()
            return entry

    def get(self, key: str, category: str = None) -> Any:
        path = self._find_entry_path(key)
        if not path: return None
        with open(path) as f: entry = json.load(f)
        entry["last_accessed"] = datetime.now().isoformat()
        with open(path, 'w') as f: json.dump(entry, f, indent=2)
        return entry["value"]

    def get_entry(self, key: str) -> Optional[Dict]:
        path = self._find_entry_path(key)
        if not path: return None
        with open(path) as f: return json.load(f)

    def delete(self, key: str, category: str = None) -> bool:
        with self._lock:
            if category:
                path = self._entry_path(key, category)
                if path.exists(): path.unlink(); self._save_meta(); return True
            path = self._find_entry_path(key)
            if path and path.exists(): path.unlink(); self._save_meta(); return True
            return False

    def search(self, query: str = None, category: str = None, tags: List[str] = None) -> List[Dict]:
        results, categories = [], [category] if category else self.CATEGORIES
        for cat in categories:
            cat_dir = self.base_path / cat
            if not cat_dir.exists(): continue
            for f in cat_dir.glob("*.json"):
                try:
                    with open(f) as fh: entry = json.load(fh)
                    if query and query.lower() not in entry.get("key", "").lower():
                        val = entry.get("value", "")
                        if isinstance(val, str) and query.lower() not in val.lower(): continue
                        elif isinstance(val, dict) and query.lower() not in json.dumps(val).lower(): continue
                    if tags:
                        etags = [t.lower() for t in entry.get("tags", [])]
                        if not any(t.lower() in etags for t in tags): continue
                    results.append(entry)
                except Exception: continue
        return results

    def get_all_for_sync(self) -> Dict[str, Dict]:
        result = {}
        for cat in self.CATEGORIES:
            cat_dir = self.base_path / cat
            if not cat_dir.exists(): continue
            for f in cat_dir.glob("*.json"):
                try:
                    with open(f) as fh: entry = json.load(fh)
                    result[entry["key"]] = entry
                except Exception: continue
        return result

    def import_from_sync(self, data: Dict) -> int:
        count = 0
        for key, entry in data.items():
            self.set(key, entry.get("value"), category=entry.get("category", "core"),
                     tags=entry.get("tags", []), source=entry.get("source", "sync"))
            count += 1
        return count

    def import_from_distributed_memory(self, store: Dict) -> int:
        count = 0
        for key, entry in store.items():
            if isinstance(entry, dict) and 'value' in entry:
                self.set(key, entry['value'], category="core", tags=["imported", "distributed"])
                count += 1
        return count

    def count(self, category: str = None) -> int:
        return len(self.search(category=category))

    def stats(self) -> Dict:
        return {"node": self.node_name, "total_entries": self.count(),
                "categories": {cat: self.count(cat) for cat in self.CATEGORIES},
                "last_updated": self._meta.get("last_updated"), "version": self._meta.get("version", "1.0")}

    def git_sync(self, commit_msg: str = "auto-sync") -> bool:
        try:
            repo_dir = self.base_path.parent
            if not (repo_dir / ".git").exists(): return False
            for cmd in [["git","add","-A"], ["git","commit","-m",commit_msg],
                        ["git","pull","--rebase"], ["git","push"]]:
                subprocess.run(cmd, cwd=str(repo_dir), capture_output=True, timeout=30)
            return True
        except Exception as e:
            logger.warning(f"git_sync failed: {e}")
            return False