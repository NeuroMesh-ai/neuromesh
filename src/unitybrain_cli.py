#!/usr/bin/env python3
"""
🖥️ UnityBrain CLI — Client interactif
Utilise UnityBrain comme application, avec ou sans réseau P2P.
Partage CPU/RAM avec le réseau quand share_ai=true.
"""

import sys
import os
import json
import time
import urllib.request
import urllib.parse
import hmac
import hashlib
import ssl

# ============================================================================
# CONFIG
# ============================================================================

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
HISTORY_FILE = os.path.expanduser("~/.unitybrain_history.json")

# SSL context (skip verification for local)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# ============================================================================
# API CLIENT
# ============================================================================

class UnityBrainClient:
    """Lightweight client for UnityBrain API."""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, secret=None):
        self.host = host
        self.port = port
        self.secret = secret
        self.base = f"http://{host}:{port}"

    def _auth_headers(self, path="/api/query"):
        headers = {}
        if self.secret:
            ts = str(int(time.time()))
            sig = hmac.new(
                self.secret.encode(),
                f"{path}:{ts}".encode(),
                hashlib.sha256
            ).hexdigest()
            headers["X-UnityBrain-Auth"] = sig
            headers["X-UnityBrain-TS"] = ts
        return headers

    def _request(self, path, data=None, method="GET"):
        url = f"{self.base}{path}"
        headers = self._auth_headers(path)
        body = None
        if data:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
            method = "POST"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            try:
                return json.load(e)
            except:
                return {"error": f"HTTP {e.code}"}
        except Exception as e:
            return {"error": str(e)}

    def status(self):
        return self._request("/api/status")

    def query(self, prompt, model=None, strategy="auto"):
        return self._request("/api/query", {
            "prompt": prompt,
            "model": model,
            "strategy": strategy
        })

    def memory_set(self, key, value, ttl=None):
        return self._request("/api/memory/set", {
            "key": key, "value": value, "ttl": ttl
        })

    def memory_get(self, key):
        return self._request(f"/api/memory/{key}")

    def peers(self):
        return self._request("/api/peers")

# ============================================================================
# INTERACTIVE SHELL
# ============================================================================

class UnityBrainShell:
    """Interactive shell for UnityBrain."""

    PROMPT = "UnityBrain> "
    COMMANDS = {
        "help": "Show this help",
        "status": "Show node status",
        "peers": "List connected peers",
        "models": "List available models",
        "memory": "Memory operations (set/get/search)",
        "history": "Show query history",
        "export": "Export history (json/txt)",
        "model": "Set default model",
        "ensemble": "Query with ensemble consensus",
        "config": "Show current configuration",
        "quit": "Exit UnityBrain CLI",
    }

    def __init__(self, client):
        self.client = client
        self.history = []
        self.default_model = None
        self._load_history()

    def _load_history(self):
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE) as f:
                    self.history = json.load(f)
        except:
            self.history = []

    def _save_history(self):
        try:
            with open(HISTORY_FILE, "w") as f:
                json.dump(self.history[-100:], f, indent=2)
        except:
            pass

    def run(self):
        """Main interactive loop."""
        print()
        print("🖥️  UnityBrain CLI v4.1.0")
        print("   P2P Distributed AI Network")
        print()

        # Check connection
        status = self.client.status()
        if "error" in status:
            print(f"❌ Cannot connect to UnityBrain at {self.client.base}")
            print(f"   Make sure UnityBrain is running: python3 unitybrain_v4.py <node>")
            print()
            return

        node = status.get("node", "?")
        version = status.get("version", "?")
        share_ai = status.get("share_ai", False)
        peers_count = status.get("peers", {}).get("available", 0)

        print(f"✅ Connected to {node} (v{version})")
        if share_ai:
            print(f"📤 Sharing CPU/RAM with network ({peers_count} peer(s))")
        else:
            print(f"🔇 AI sharing disabled — your models are private")
        print()
        print("Type 'help' for commands, or just type your prompt.")
        print()

        while True:
            try:
                line = input(self.PROMPT).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n👋 Bye!")
                break

            if not line:
                continue

            # Check if it's a command
            if line.startswith("/"):
                self._handle_command(line[1:])
            elif line.lower() in ("quit", "exit", "q"):
                print("👋 Bye!")
                break
            elif line.lower() == "help":
                self._show_help()
            else:
                # It's a prompt — send query
                self._do_query(line)

    def _show_help(self):
        print()
        print("📚 UnityBrain CLI Commands:")
        print("─" * 40)
        for cmd, desc in self.COMMANDS.items():
            print(f"  /{cmd:12s} {desc}")
        print()
        print("Just type your prompt to query the AI.")
        print("Use /model <name> to set a default model.")
        print()

    def _handle_command(self, cmd_line):
        parts = cmd_line.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "status":
            self._show_status()
        elif cmd == "peers":
            self._show_peers()
        elif cmd == "models":
            self._show_models()
        elif cmd == "model":
            if args:
                self.default_model = args.strip()
                print(f"✅ Default model set to: {self.default_model}")
            else:
                print(f"Current default model: {self.default_model or 'auto'}")
        elif cmd == "memory":
            self._handle_memory(args)
        elif cmd == "history":
            self._show_history(args)
        elif cmd == "export":
            self._export_history(args)
        elif cmd == "ensemble":
            if args:
                self._do_query(args, strategy="ensemble")
            else:
                print("Usage: /ensemble <prompt>")
        elif cmd == "config":
            self._show_config()
        elif cmd in ("quit", "exit", "q"):
            print("👋 Bye!")
            sys.exit(0)
        elif cmd == "help":
            self._show_help()
        else:
            print(f"Unknown command: /{cmd}. Type /help for commands.")

    def _do_query(self, prompt, strategy="auto"):
        model = self.default_model
        print(f"📝 Querying{' [' + model + ']' if model else ''}...")

        start = time.time()
        result = self.client.query(prompt, model=model, strategy=strategy)
        elapsed = time.time() - start

        if "error" in result:
            print(f"❌ Error: {result['error']}")
            return

        response = result.get("response", "")
        source = result.get("source", "?")
        used_model = result.get("model", "?")

        # Store in history
        entry = {
            "timestamp": time.time(),
            "prompt": prompt[:200],
            "response": response[:500],
            "model": used_model,
            "source": source,
            "strategy": strategy,
            "latency": round(elapsed, 2)
        }
        self.history.append(entry)
        self._save_history()

        # Display
        print()
        print(f"💬 Response ({used_model} via {source}, {elapsed:.1f}s):")
        print("─" * 60)
        print(response)
        print("─" * 60)
        print()

    def _show_status(self):
        status = self.client.status()
        if "error" in status:
            print(f"❌ {status['error']}")
            return

        print()
        print(f"📊 UnityBrain v{status.get('version', '?')} — {status.get('node', '?')}")
        print("─" * 40)
        print(f"  Uptime:   {status.get('uptime', 0)/3600:.1f}h")
        print(f"  Share AI:   {'Yes ✅' if status.get('share_ai') else 'No 🔇'}")
        print(f"  Stealth:    {'Yes 🔒' if status.get('stealth_mode') else 'No'}")

        peers = status.get("peers", {})
        print(f"  Peers:   {peers.get('available', 0)}/{peers.get('total', 0)} available")

        queries = status.get("queries", {})
        print(f"  Queries: {queries.get('total', 0)} ({queries.get('rate', 0):.1f}% success)")

        memory = status.get("memory", {})
        print(f"  Memory:  {memory.get('active_entries', 0)}/{memory.get('total_entries', 0)} entries")

        models = status.get("local_models", [])
        if models:
            print(f"  Models:  {', '.join(models[:5])}")
        print()

    def _show_peers(self):
        peers = self.client.peers()
        if isinstance(peers, dict) and "error" in peers:
            print(f"❌ {peers['error']}")
            return
        if not peers:
            print("No peers connected.")
            return

        print()
        print("🌐 Connected Peers:")
        print("─" * 40)
        for p in peers:
            name = p.get("name", "?")
            host = p.get("host", "?")
            port = p.get("port", "?")
            models = p.get("models", [])
            latency = p.get("latency_ms", "?")
            status_icon = "✅" if p.get("available") else "❌"
            print(f"  {status_icon} {name} ({host}:{port}) {latency}ms")
            if models:
                print(f"     Models: {', '.join(models[:4])}")
        print()

    def _show_models(self):
        status = self.client.status()
        models = status.get("local_models", [])
        providers = status.get("providers", {})

        print()
        print("🧠 Available Models:")
        print("─" * 40)
        if providers:
            for name, info in providers.items():
                ptype = info.get("type", "?")
                enabled = "✅" if info.get("enabled") else "❌"
                pmodels = info.get("models", [])
                print(f"  {enabled} {name} ({ptype})")
                for m in pmodels:
                    marker = " ← default" if m == self.default_model else ""
                    print(f"     • {m}{marker}")
        elif models:
            for m in models:
                marker = " ← default" if m == self.default_model else ""
                print(f"  • {m}{marker}")
        else:
            print("  No models available")
        print()

    def _handle_memory(self, args):
        if not args:
            print("Usage: /memory set <key> <value> | /memory get <key>")
            return
        parts = args.split(maxsplit=2)
        subcmd = parts[0].lower()

        if subcmd == "set" and len(parts) >= 3:
            key, value = parts[1], parts[2]
            result = self.client.memory_set(key, value)
            print(f"✅ Memory set: {key}")
        elif subcmd == "get" and len(parts) >= 2:
            key = parts[1]
            result = self.client.memory_get(key)
            if "error" in result:
                print(f"❌ {result['error']}")
            else:
                print(f"📦 {key}: {json.dumps(result.get('value'), indent=2)[:300]}")
        else:
            print("Usage: /memory set <key> <value> | /memory get <key>")

    def _show_history(self, args=""):
        limit = 10
        if args:
            try:
                limit = int(args)
            except:
                pass

        if not self.history:
            print("No history yet.")
            return

        print()
        print(f"📜 Recent Queries (last {limit}):")
        print("─" * 40)
        for entry in self.history[-limit:]:
            ts = time.strftime("%H:%M:%S", time.localtime(entry.get("timestamp", 0)))
            prompt = entry.get("prompt", "?")[:60]
            model = entry.get("model", "?")
            latency = entry.get("latency", "?")
            print(f"  [{ts}] {prompt}... ({model}, {latency}s)")
        print()

    def _export_history(self, fmt="json"):
        if not self.history:
            print("No history to export.")
            return
        if fmt == "json":
            print(json.dumps(self.history, indent=2, ensure_ascii=False)[:2000])
        else:
            for entry in self.history:
                print(f"[{entry.get('timestamp')}] {entry.get('prompt')}")
                print(f"  → {entry.get('response', '')[:200]}")
                print()

    def _show_config(self):
        status = self.client.status()
        print()
        print("⚙️  Configuration:")
        print("─" * 40)
        print(f"  Node:      {status.get('node', '?')}")
        print(f"  Version:  {status.get('version', '?')}")
        print(f"  Share AI:   {status.get('share_ai', False)}")
        print(f"  Stealth:    {status.get('stealth_mode', False)}")
        print(f"  Default model: {self.default_model or 'auto'}")
        print()


# ============================================================================
# MAIN
# ============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="UnityBrain CLI — Interactive client")
    parser.add_argument("node", nargs="?", default="bug", help="Node name (default: bug)")
    parser.add_argument("--host", default=DEFAULT_HOST, help="UnityBrain host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="UnityBrain port")
    parser.add_argument("--secret", help="P2P secret for auth")
    parser.add_argument("--query", "-q", help="Single query (non-interactive)")
    parser.add_argument("--model", "-m", help="Model to use")
    parser.add_argument("--ensemble", action="store_true", help="Use ensemble consensus")
    args = parser.parse_args()

    # Try to load config for port/secret
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_dir = os.path.join(os.path.dirname(script_dir), "config")
    config_path = os.path.join(config_dir, f"{args.node}.json")

    host = args.host
    port = args.port
    secret = args.secret

    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                config = json.load(f)
            port = config.get("port", port)
            secret = config.get("p2p_secret", secret)
        except:
            pass

    client = UnityBrainClient(host=host, port=port, secret=secret)

    # Single query mode
    if args.query:
        strategy = "ensemble" if args.ensemble else "auto"
        result = client.query(args.query, model=args.model, strategy=strategy)
        if "error" in result:
            print(f"❌ {result['error']}")
            sys.exit(1)
        print(result.get("response", ""))
        sys.exit(0)

    # Interactive mode
    shell = UnityBrainShell(client)
    if args.model:
        shell.default_model = args.model
    shell.run()


if __name__ == "__main__":
    main()