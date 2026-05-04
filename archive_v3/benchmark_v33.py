#!/usr/bin/env python3
"""
UnityBrain v3.3 — Benchmark complet
Tests de charge, latence, P2P, mémoire, concurrence, failover
"""

import hmac
import hashlib
import time
import json
import sys
import urllib.request
import urllib.error
import threading
import concurrent.futures

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8080
DEFAULT_SECRET = "bug-pinky-2026-unity"

def hmac_headers(path, secret):
    ts = str(time.time())
    msg = f"{path}:{ts}"
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return {'X-UnityBrain-Auth': sig, 'X-UnityBrain-TS': ts, 'Content-Type': 'application/json'}

def api_get(url, timeout=10):
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}

def api_post(url, data, headers=None, timeout=60):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers or {})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}

def run_benchmark(host, port, secret):
    base = f"http://{host}:{port}"
    
    print("🏁 UnityBrain v3.3 — Benchmark")
    print(f"   Target: {base}")
    print("=" * 60)

    # ================================================================
    # 1. LATENCE API — temps de réponse par endpoint
    # ================================================================
    print("\n📊 1. LATENCE API (100 requêtes par endpoint)")
    
    endpoints = {
        "GET /api/status": lambda: api_get(f"{base}/api/status"),
        "GET /api/peers": lambda: api_get(f"{base}/api/peers"),
        "GET /api/monitor": lambda: api_get(f"{base}/api/monitor"),
    }
    
    for name, fn in endpoints.items():
        latencies = []
        errors = 0
        for i in range(100):
            t0 = time.time()
            status, _ = fn()
            dt = (time.time() - t0) * 1000
            if status == 200:
                latencies.append(dt)
            else:
                errors += 1
        if latencies:
            latencies.sort()
            avg = sum(latencies) / len(latencies)
            p50 = latencies[len(latencies)//2]
            p95 = latencies[int(len(latencies)*0.95)]
            p99 = latencies[int(len(latencies)*0.99)]
            print(f"  {name}")
            print(f"    Avg: {avg:.1f}ms | P50: {p50:.1f}ms | P95: {p95:.1f}ms | P99: {p99:.1f}ms | Errors: {errors}")
        else:
            print(f"  {name}: TOUT EN ERREUR ({errors})")

    # ================================================================
    # 2. THROUGHPUT HMAC AUTH — requêtes auth/sec
    # ================================================================
    print("\n📊 2. THROUGHPUT AUTH (200 POST /api/sync authentifiées)")
    
    t0 = time.time()
    ok = 0
    fail = 0
    for i in range(200):
        headers = hmac_headers("/api/sync", secret)
        status, data = api_post(f"{base}/api/sync", {"memory": {f"bench_{i}": {"value": f"v{i}", "expires": time.time()+3600}}}, headers=headers)
        if status == 200:
            ok += 1
        else:
            fail += 1
    dt = time.time() - t0
    print(f"  Requêtes: {ok} OK / {fail} FAIL")
    print(f"  Temps total: {dt:.2f}s")
    print(f"  Throughput: {ok/dt:.1f} req/sec")

    # ================================================================
    # 3. MÉMOIRE DISTRIBUÉE — 100 clés, vérifier persistance
    # ================================================================
    print("\n📊 3. MÉMOIRE DISTRIBUÉE (100 clés SET + SYNC)")
    
    # Set 100 keys via sync
    headers = hmac_headers("/api/sync", secret)
    mem = {}
    for i in range(100):
        mem[f"bench_key_{i:03d}"] = {"value": f"bench_value_{i}", "expires": time.time() + 3600}
    
    t0 = time.time()
    status, data = api_post(f"{base}/api/sync", {"memory": mem}, headers=headers, timeout=30)
    dt = time.time() - t0
    
    if status == 200:
        synced = data.get("keys_synced", "?")
        print(f"  Sync: {synced} clés syncées en {dt*1000:.1f}ms")
    else:
        print(f"  Sync FAILED: {status} {data}")
    
    # Vérifier via status
    status, data = api_get(f"{base}/api/status")
    mem_keys = data.get("memory", {}).get("keys", "?")
    print(f"  Clés en mémoire: {mem_keys}")

    # ================================================================
    # 4. P2P LATENCE — ping vers Pinky via Bug
    # ================================================================
    print("\n📊 4. P2P LATENCE (20 pings Bug→Pinky)")
    
    status, data = api_get(f"{base}/api/status")
    peers = data.get("peers", {}).get("list", [])
    pinky = [p for p in peers if p["name"] == "Pinky"]
    
    if pinky:
        # Direct ping to Pinky
        pinky_base = f"http://{pinky[0]['host']}:{pinky[0]['port']}"
        latencies = []
        for i in range(20):
            t0 = time.time()
            status, _ = api_get(f"{pinky_base}/api/status", timeout=5)
            dt = (time.time() - t0) * 1000
            if status == 200:
                latencies.append(dt)
        if latencies:
            avg = sum(latencies) / len(latencies)
            latencies.sort()
            p50 = latencies[len(latencies)//2]
            p95 = latencies[int(len(latencies)*0.95)]
            print(f"  Bug → Pinky: Avg {avg:.1f}ms | P50 {p50:.1f}ms | P95 {p95:.1f}ms")
        else:
            print(f"  Bug → Pinky: Aucune réponse")
    else:
        print(f"  Pinky non trouvée dans les peers")

    # ================================================================
    # 5. CONCURRENCE — requêtes simultanées
    # ================================================================
    print("\n📊 5. CONCURRENCE (50 requêtes GET simultanées)")
    
    results = {"ok": 0, "fail": 0, "latencies": []}
    lock = threading.Lock()
    
    def concurrent_get(i):
        t0 = time.time()
        status, _ = api_get(f"{base}/api/status", timeout=10)
        dt = (time.time() - t0) * 1000
        with lock:
            if status == 200:
                results["ok"] += 1
                results["latencies"].append(dt)
            else:
                results["fail"] += 1
    
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as pool:
        futures = [pool.submit(concurrent_get, i) for i in range(50)]
        concurrent.futures.wait(futures)
    dt = time.time() - t0
    
    if results["latencies"]:
        lats = sorted(results["latencies"])
        avg = sum(lats) / len(lats)
        p95 = lats[int(len(lats)*0.95)]
        print(f"  OK: {results['ok']} / FAIL: {results['fail']}")
        print(f"  Temps total: {dt*1000:.0f}ms | Avg: {avg:.1f}ms | P95: {p95:.1f}ms")
        print(f"  Throughput: {results['ok']/dt:.1f} req/sec")

    # ================================================================
    # 6. QUERY MODEL — 3 queries avec latence
    # ================================================================
    print("\n📊 6. QUERY MODÈLE (3 requêtes glm-5.1:cloud)")
    
    prompts = [
        "Réponds en un mot: bonjour",
        "Donne-moi un nombre aléatoire entre 1 et 100",
        "Cite-moi un proverbe en 5 mots"
    ]
    
    for i, prompt in enumerate(prompts):
        headers = hmac_headers("/api/query", secret)
        t0 = time.time()
        status, data = api_post(f"{base}/api/query", {
            "prompt": prompt,
            "model": "glm-5.1:cloud"
        }, headers=headers, timeout=120)
        dt = (time.time() - t0) * 1000
        if status == 200:
            resp = data.get("response", "")[:80]
            routed = "local" if data.get("routed_locally") else "peer"
            print(f"  Q{i+1}: {dt:.0f}ms | {routed} | \"{resp}\"")
        else:
            print(f"  Q{i+1}: FAIL {status} {data}")

    # ================================================================
    # 7. FAILFAST — requêtes sur port mort
    # ================================================================
    print("\n📊 7. FAILFAST (requête sur port 9999 — doit échouer vite)")
    
    t0 = time.time()
    try:
        urllib.request.urlopen("http://localhost:9999/api/status", timeout=5)
    except:
        pass
    dt = (time.time() - t0) * 1000
    print(f"  Temps échec: {dt:.0f}ms {'✅ rapide' if dt < 2000 else '⚠️ lent'}")

    # ================================================================
    # 8. CIRCUIT BREAKER — vérifier états
    # ================================================================
    print("\n📊 8. CIRCUIT BREAKER (état des peers)")
    
    status, data = api_get(f"{base}/api/status")
    for p in data.get("peers", {}).get("list", []):
        cb = p.get("circuit_breaker", {})
        avail = "✅" if p["available"] else "❌"
        print(f"  {p['name']} {avail} | CB: {cb.get('state')} | Failures: {cb.get('failures',0)} | Lat: {p['latency']:.0f}ms")

    # ================================================================
    # 9. UPTIME & STABILITÉ
    # ================================================================
    print("\n📊 9. STABILITÉ")
    status, data = api_get(f"{base}/api/status")
    uptime = data.get("uptime", 0)
    queries = data.get("queries", {})
    print(f"  Uptime: {uptime:.0f}s ({uptime/3600:.1f}h)")
    print(f"  Queries: {queries.get('total',0)} total | {queries.get('successful',0)} OK | {queries.get('rate',0)} req/s")
    
    events = data.get("event_log", [])
    auth_fails = [e for e in events if e["type"] == "auth_fail"]
    syncs = [e for e in events if e["type"] == "sync"]
    print(f"  Recent auth_fails: {len(auth_fails)} | syncs: {len(syncs)}")

    print("\n" + "=" * 60)
    print("🏁 Benchmark terminé !")

if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT
    secret = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_SECRET
    run_benchmark(host, port, secret)