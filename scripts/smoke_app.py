"""Smoke test for app/main.py.

Drives every route, every chaos transition, and the X-Mode middleware in
both stable and canary mode. Prints a single-line PASS/FAIL summary per
expectation so output is easy to capture in evidence_log.

Run:
    python scripts/smoke_app.py
"""
from __future__ import annotations

import importlib
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))


def reload_app(mode: str):
    os.environ["MODE"] = mode
    os.environ["APP_VERSION"] = "1.0.0-smoke"
    if "main" in sys.modules:
        importlib.reload(sys.modules["main"])
    else:
        import main  # noqa: F401
    return sys.modules["main"]


def expect(label: str, condition: bool, detail: str = "") -> int:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f"  -> {detail}" if detail else ""))
    return 0 if condition else 1


def metric_value(text: str, metric_name: str) -> float | None:
    pattern = re.compile(rf"^{re.escape(metric_name)}\s+([-+0-9.eE]+)$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return None
    return float(match.group(1))


def run_stable() -> int:
    from fastapi.testclient import TestClient

    main = reload_app("stable")
    client = TestClient(main.app)
    failures = 0

    r = client.get("/")
    failures += expect("stable / returns 200", r.status_code == 200, str(r.status_code))
    body = r.json()
    failures += expect("stable / mode=stable", body.get("mode") == "stable", str(body))
    failures += expect("stable / has version", "version" in body)
    failures += expect("stable / has timestamp", "timestamp" in body)
    failures += expect("stable / has no X-Mode", "X-Mode" not in r.headers, str(dict(r.headers)))

    r = client.get("/healthz")
    failures += expect("stable /healthz 200", r.status_code == 200)
    body = r.json()
    failures += expect("stable /healthz status ok", body.get("status") == "ok")
    failures += expect("stable /healthz uptime numeric", isinstance(body.get("uptime"), (int, float)))

    r = client.post("/chaos", json={"mode": "slow", "duration": 1})
    failures += expect("stable /chaos returns 403", r.status_code == 403, str(r.status_code))
    failures += expect("stable /chaos detail mentions stable", "stable" in r.text.lower())
    failures += expect("stable /chaos has no X-Mode", "X-Mode" not in r.headers)

    r = client.get("/metrics")
    metrics = r.text
    failures += expect("stable /metrics returns 200", r.status_code == 200, str(r.status_code))
    failures += expect("stable /metrics content-type is prometheus text",
                       "text/plain" in r.headers.get("content-type", ""))
    failures += expect("stable metrics include http_requests_total",
                       'http_requests_total{method="GET",path="/",status_code="200"}' in metrics)
    failures += expect("stable metrics include /chaos 403 counter",
                       'http_requests_total{method="POST",path="/chaos",status_code="403"}' in metrics)
    failures += expect("stable metrics include duration histogram bucket",
                       'http_request_duration_seconds_bucket{method="GET",path="/",le="0.5"}' in metrics)
    failures += expect("stable metrics app_mode=0", metric_value(metrics, "app_mode") == 0.0)
    failures += expect("stable metrics chaos_active=0", metric_value(metrics, "chaos_active") == 0.0)

    return failures


def run_canary() -> int:
    from fastapi.testclient import TestClient

    main = reload_app("canary")
    client = TestClient(main.app)
    failures = 0

    r = client.get("/")
    failures += expect("canary / returns 200", r.status_code == 200)
    failures += expect("canary / has X-Mode: canary", r.headers.get("X-Mode") == "canary", str(dict(r.headers)))
    failures += expect("canary / mode=canary", r.json().get("mode") == "canary")

    r = client.get("/healthz")
    failures += expect("canary /healthz has X-Mode", r.headers.get("X-Mode") == "canary")

    # slow chaos: set duration ~0.4s, then time a request, then recover
    r = client.post("/chaos", json={"mode": "slow", "duration": 0.4})
    failures += expect("canary chaos slow accepted", r.status_code == 200, str(r.text))
    failures += expect("canary chaos slow body has state", r.json().get("chaos", {}).get("mode") == "slow")
    t0 = time.monotonic()
    r = client.get("/healthz")
    elapsed = time.monotonic() - t0
    failures += expect("canary slow delays /healthz >= 0.35s", elapsed >= 0.35, f"elapsed={elapsed:.3f}s")
    failures += expect("canary slow /healthz still 200", r.status_code == 200)

    r = client.post("/chaos", json={"mode": "recover"})
    failures += expect("canary chaos recover accepted", r.status_code == 200)
    t0 = time.monotonic()
    r = client.get("/healthz")
    elapsed = time.monotonic() - t0
    failures += expect("canary after recover /healthz fast", elapsed < 0.2, f"elapsed={elapsed:.3f}s")

    # error chaos at 1.0 should always 500 on non-/chaos paths
    r = client.post("/chaos", json={"mode": "error", "rate": 1.0})
    failures += expect("canary chaos error accepted", r.status_code == 200)
    r = client.get("/")
    failures += expect("canary / under error=1.0 returns 500", r.status_code == 500, str(r.status_code))
    failures += expect("canary / under error=1.0 has X-Mode", r.headers.get("X-Mode") == "canary",
                       "middleware order check: X-Mode must stamp chaos 500s")

    r = client.get("/metrics")
    metrics = r.text
    failures += expect("canary /metrics exempt from error chaos", r.status_code == 200, str(r.status_code))
    failures += expect("canary /metrics has X-Mode", r.headers.get("X-Mode") == "canary")
    failures += expect("canary metrics include app_mode=1", metric_value(metrics, "app_mode") == 1.0)
    failures += expect("canary metrics include chaos_active=2", metric_value(metrics, "chaos_active") == 2.0)
    failures += expect("canary metrics counted chaos 500",
                       'http_requests_total{method="GET",path="/",status_code="500"}' in metrics)

    # /chaos itself must remain reachable so we can recover even at rate=1.0
    r = client.post("/chaos", json={"mode": "recover"})
    failures += expect("canary /chaos exempt from chaos at rate=1.0", r.status_code == 200, str(r.status_code))

    # back to clean state
    r = client.get("/healthz")
    failures += expect("canary /healthz after final recover 200", r.status_code == 200)

    # invalid payload should be 400 in canary
    r = client.post("/chaos", json={"mode": "nope"})
    failures += expect("canary /chaos invalid mode rejected", r.status_code in (400, 422), str(r.status_code))

    r = client.get("/metrics")
    metrics = r.text
    failures += expect("canary metrics include uptime gauge", metric_value(metrics, "app_uptime_seconds") is not None)
    failures += expect("canary metrics chaos_active returns to 0", metric_value(metrics, "chaos_active") == 0.0)

    return failures


def main() -> int:
    print("=== STABLE MODE ===")
    f1 = run_stable()
    print("\n=== CANARY MODE ===")
    f2 = run_canary()
    total = f1 + f2
    print(f"\nTotal failures: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
