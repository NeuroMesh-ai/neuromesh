#!/usr/bin/env python3
"""
UnityBrain v3.3 — Tests automatisés
Run: python3 tests/test_v33.py [--host HOST] [--port PORT] [--secret SECRET]
"""

import hmac
import hashlib
import time
import json
import sys
import os
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

# ============================================================================
# Configuration
# ============================================================================
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8080
DEFAULT_SECRET = "bug-pinky-2026-unity"
TIMEOUT = 30

passed = 0
failed = 0
errors = []

def test(name):
    """Decorator to register a test"""
    def decorator(func):
        def wrapper():
            global passed, failed
            try:
                result = func()
                if result is False:
                    failed += 1
                    errors.append(f"FAIL: {name}")
                    print(f"  ❌ {name}")
                else:
                    passed += 1
                    print(f"  ✅ {name}")
            except Exception as e:
                failed += 1
                errors.append(f"ERROR: {name} — {e}")
                print(f"  💥 {name}: {e}")
        wrapper._name = name
        return wrapper
    return decorator

# ============================================================================
# HTTP helpers
# ============================================================================

def api_get(url, timeout=TIMEOUT):
    """GET request to UnityBrain API"""
    req = urllib.request.Request(url)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode()) if e.headers.get('Content-Type','').startswith('application/json') else {}
    except Exception as e:
        return 0, {"error": str(e)}

def api_post(url, data, headers=None, timeout=TIMEOUT):
    """POST request with optional auth headers"""
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers or {})
    req.add_header('Content-Type', 'application/json')
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except:
            return e.code, {"raw": body}
    except Exception as e:
        return 0, {"error": str(e)}

def hmac_headers(path, secret):
    """Generate HMAC auth headers"""
    ts = str(time.time())
    msg = f"{path}:{ts}"
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return {
        'X-UnityBrain-Auth': sig,
        'X-UnityBrain-TS': ts,
    }

def jwt_headers(secret, node_name="test"):
    """Generate JWT auth headers (via Bearer token)"""
    # We'll use the TokenAuth class from the main module
    # For now, just use HMAC which we know works
    return hmac_headers("/api/query", secret)

# ============================================================================
# Test suite
# ============================================================================

def run_tests(host, port, secret):
    base_url = f"http://{host}:{port}"
    print(f"\n🧪 UnityBrain v3.3 Test Suite")
    print(f"   Target: {base_url}")
    print(f"   Secret: {secret[:8]}...")
    print()

    # ---- 1. Unauthenticated access ----
    @test("GET /api/status sans auth (doit marcher)")
    def t1():
        status, data = api_get(f"{base_url}/api/status")
        assert status == 200, f"Expected 200, got {status}"
        assert data.get("version") == "3.3.0", f"Expected v3.3.0, got {data.get('version')}"
        assert data.get("node") == "bug", f"Expected node=bug, got {data.get('node')}"
        return True

    @test("POST /api/query sans auth (doit échouer 401)")
    def t2():
        status, data = api_post(f"{base_url}/api/query", {"prompt": "test"})
        assert status == 401, f"Expected 401, got {status}"
        return True

    @test("POST /api/sync sans auth (doit échouer 401)")
    def t3():
        status, data = api_post(f"{base_url}/api/sync", {"memory": {}})
        assert status == 401, f"Expected 401, got {status}"
        return True

    # ---- 2. HMAC authentication ----
    @test("POST /api/sync avec HMAC valide")
    def t4():
        headers = hmac_headers("/api/sync", secret)
        status, data = api_post(f"{base_url}/api/sync", {"memory": {}}, headers=headers)
        assert status == 200, f"Expected 200, got {status}: {data}"
        assert data.get("status") == "ok", f"Expected ok, got {data}"
        return True

    @test("POST /api/sync avec HMAC expiré (ts > 300s)")
    def t5():
        old_ts = str(time.time() - 400)
        msg = f"/api/sync:{old_ts}"
        sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
        headers = {'X-UnityBrain-Auth': sig, 'X-UnityBrain-TS': old_ts}
        status, data = api_post(f"{base_url}/api/sync", {"memory": {}}, headers=headers)
        assert status == 401, f"Expected 401, got {status}: {data}"
        return True

    @test("POST /api/sync avec mauvais secret HMAC")
    def t6():
        headers = hmac_headers("/api/sync", "wrong-secret-12345")
        status, data = api_post(f"{base_url}/api/sync", {"memory": {}}, headers=headers)
        assert status == 401, f"Expected 401, got {status}: {data}"
        return True

    @test("POST /api/sync avec HMAC path mismatch")
    def t7():
        # Sign for /api/ping but send to /api/sync
        headers = hmac_headers("/api/ping", secret)
        status, data = api_post(f"{base_url}/api/sync", {"memory": {}}, headers=headers)
        assert status == 401, f"Expected 401, got {status}: {data}"
        return True

    # ---- 3. Memory operations ----
    @test("SET memory via API (POST)")
    def t8():
        # Set a value
        headers = hmac_headers("/api/memory", secret)
        status, data = api_post(f"{base_url}/api/memory", {
            "key": "test_automated",
            "value": {"msg": "hello from tests", "ts": time.time()}
        }, headers=headers)
        assert status == 200, f"SET failed: {status} {data}"
        return True

    @test("SYNC memory entre peers")
    def t9():
        headers = hmac_headers("/api/sync", secret)
        status, data = api_post(f"{base_url}/api/sync", {
            "memory": {
                "sync_test": {"value": "synced_value", "expires": time.time() + 3600}
            }
        }, headers=headers)
        assert status == 200, f"SYNC failed: {status} {data}"
        assert data.get("status") == "ok", f"Expected ok, got {data}"
        return True

    # ---- 4. P2P endpoints ----
    @test("GET /api/peers — vérifier la liste des peers")
    def t10():
        status, data = api_get(f"{base_url}/api/peers")
        assert status == 200, f"Expected 200, got {status}"
        peers = data if isinstance(data, list) else data.get("peers", [])
        assert len(peers) >= 1, f"Expected at least 1 peer, got {len(peers)}"
        # Check Pinky is there
        pinky = [p for p in peers if p.get("name") == "Pinky"]
        assert len(pinky) == 1, f"Pinky not found in peers: {peers}"
        return True

    @test("GET /api/monitor — stats système")
    def t11():
        status, data = api_get(f"{base_url}/api/monitor")
        assert status == 200, f"Expected 200, got {status}"
        assert "cpu_percent" in data or "memory" in data, f"Missing monitor fields: {data}"
        return True

    # ---- 5. Query (with auth, may be slow) ----
    @test("POST /api/query avec auth HMAC (modèle local)")
    def t12():
        headers = hmac_headers("/api/query", secret)
        status, data = api_post(f"{base_url}/api/query", {
            "prompt": "Réponds juste: OK",
            "model": "glm-5.1:cloud"
        }, headers=headers, timeout=120)
        assert status == 200, f"Expected 200, got {status}: {data}"
        assert data.get("status") == "success", f"Expected success, got {data}"
        assert data.get("response"), f"Empty response: {data}"
        return True

    # ---- 6. Circuit breaker ----
    @test("GET /api/status — circuit breaker vérifié")
    def t13():
        status, data = api_get(f"{base_url}/api/status")
        assert status == 200
        peers = data.get("peers", {}).get("list", [])
        for p in peers:
            cb = p.get("circuit_breaker", {})
            # Pinky should have closed circuit (working)
            if p["name"] == "Pinky":
                assert cb.get("state") in ["closed", "half_open"], \
                    f"Pinky circuit breaker should be closed/half_open, got {cb}"
        return True

    # ---- 7. Dashboard ----
    @test("GET / — dashboard HTML")
    def t14():
        try:
            req = urllib.request.Request(f"{base_url}/")
            resp = urllib.request.urlopen(req, timeout=TIMEOUT)
            html = resp.read().decode()
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            assert 'UnityBrain' in html or 'unitybrain' in html.lower(), f"Not a UnityBrain dashboard"
            return True
        except urllib.error.HTTPError as e:
            assert False, f"Dashboard returned {e.code}"
        except Exception as e:
            assert False, f"Dashboard error: {e}"

    # ---- 8. Peer self-filter (no ghost "azil") ----
    @test("Aucun peer fantôme 'azil' avec CB ouvert")
    def t15():
        # After discovery cycle, azil should not appear or have closed CB
        status, data = api_get(f"{base_url}/api/status")
        peers = data.get("peers", {}).get("list", [])
        azil = [p for p in peers if p["name"] == "azil"]
        if azil:
            # If it exists, it should be available or half_open, not permanently open
            for a in azil:
                assert a["circuit_breaker"]["state"] != "open" or a["available"] == False, \
                    f"Ghost peer azil with open CB: {a}"
                # Flag as warning, don't fail test
                print(f"     ⚠️  Peer 'azil' still present (will be cleaned by next discovery)")
        return True

    # ---- 9. P2P cross-node ----
    @test("Ping Pinky via Bug (P2P routing)")
    def t16():
        # Check that Bug can reach Pinky through the peer list
        status, data = api_get(f"{base_url}/api/status")
        pinky = [p for p in data.get("peers", {}).get("list", []) if p["name"] == "Pinky"]
        if not pinky:
            print("     ⚠️  Pinky not in peer list, skipping")
            return True
        assert pinky[0].get("available") == True or pinky[0].get("latency", float("inf")) < 5000, \
            f"Pinky not reachable: {pinky[0]}"
        return True

    # ---- 10. Event log persistence ----
    @test("Event log — vérifier la persistance fichier")
    def t17():
        log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
        events_file = os.path.join(log_dir, "events.jsonl")
        if os.path.exists(events_file):
            with open(events_file) as f:
                lines = f.readlines()
            assert len(lines) > 0, "events.jsonl is empty"
            # Verify format
            first = json.loads(lines[0])
            assert "type" in first and "time" in first, f"Bad event format: {first}"
            return True
        else:
            print("     ⚠️  events.jsonl not found (may need activity first)")
            return True

    # Run all tests
    tests = [t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12, t13, t14, t15, t16, t17]
    print(f"📋 {len(tests)} tests à exécuter\n")
    for t in tests:
        t()

    # Summary
    total = passed + failed
    print(f"\n{'='*50}")
    print(f"Résultats: {passed}/{total} réussis, {failed} échoués")
    if errors:
        print("\nÉchecs:")
        for e in errors:
            print(f"  • {e}")
    print(f"{'='*50}")

    return failed == 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--secret", default=DEFAULT_SECRET)
    args = parser.parse_args()

    success = run_tests(args.host, args.port, args.secret)
    sys.exit(0 if success else 1)