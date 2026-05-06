from __future__ import annotations

import json
import http.client
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from . import config


@dataclass
class PolicyResult:
    domain: str
    ok: bool
    mode: str
    message: str
    decision: dict[str, Any] | None = None


def host_stats() -> dict[str, Any]:
    usage = shutil.disk_usage(config.ROOT)
    disk_free_gb = usage.free / (1024 ** 3)
    cpu_source = "os.getloadavg"
    try:
        cpu_load = float(os.getloadavg()[0])
    except (AttributeError, OSError):
        cpu_source = "unavailable_default"
        cpu_load = 0.0
    return {
        "disk_free_gb": round(disk_free_gb, 3),
        "cpu_load": round(cpu_load, 3),
        "cpu_source": cpu_source,
    }


def opa_port(manifest: dict[str, Any] | None = None) -> str:
    return str(config.manifest_context(manifest).get("OPA_PORT", "18181"))


def opa_url(path: str, manifest: dict[str, Any] | None = None) -> str:
    return f"http://127.0.0.1:{opa_port(manifest)}{path}"


def wait_opa_health(manifest: dict[str, Any] | None = None, timeout: int = 20) -> PolicyResult:
    deadline = time.time() + timeout
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(opa_url("/health", manifest), timeout=2) as response:
                if 200 <= response.status < 300:
                    return PolicyResult("opa", True, "healthy", "OPA health check passed")
                last_error = f"health returned HTTP {response.status}"
        except socket.timeout:
            last_error = "timeout while checking OPA health"
        except http.client.RemoteDisconnected:
            last_error = "OPA closed the health connection while starting"
        except urllib.error.URLError as exc:
            last_error = str(exc.reason)
        time.sleep(1)
    return PolicyResult("opa", False, "opa_unhealthy", f"OPA did not become healthy: {last_error}")


def query_opa(domain: str, input_doc: dict[str, Any], manifest: dict[str, Any] | None = None) -> PolicyResult:
    path = f"/v1/data/swiftdeploy/{domain}/decision"
    payload = json.dumps({"input": input_doc}).encode("utf-8")
    request = urllib.request.Request(
        opa_url(path, manifest),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8")
    except socket.timeout:
        return PolicyResult(domain, False, "opa_timeout", f"{domain}: OPA request timed out")
    except http.client.RemoteDisconnected:
        return PolicyResult(domain, False, "opa_unavailable", f"{domain}: OPA closed the connection")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return PolicyResult(domain, False, "opa_policy_error", f"{domain}: OPA HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        return PolicyResult(domain, False, "opa_unavailable", f"{domain}: OPA unavailable: {exc.reason}")

    try:
        decoded = json.loads(body)
    except json.JSONDecodeError:
        return PolicyResult(domain, False, "opa_malformed_response", f"{domain}: OPA returned non-JSON")

    decision = decoded.get("result")
    if not isinstance(decision, dict):
        return PolicyResult(domain, False, "opa_malformed_response", f"{domain}: OPA response missing decision object")
    if not isinstance(decision.get("allowed"), bool) or not decision.get("reason"):
        return PolicyResult(domain, False, "opa_malformed_response", f"{domain}: OPA decision missing allowed/reason")

    if decision["allowed"]:
        return PolicyResult(domain, True, "allow", str(decision["reason"]), decision)
    return PolicyResult(domain, False, "deny", str(decision["reason"]), decision)


def infrastructure_input(question: str) -> dict[str, Any]:
    manifest = config.load_manifest()
    return {
        "question": question,
        "host": host_stats(),
        "thresholds": config.policy_config(manifest)["infrastructure"],
    }


def canary_input(question: str, metrics_summary: dict[str, Any]) -> dict[str, Any]:
    manifest = config.load_manifest()
    canary = config.policy_config(manifest)["canary"]
    return {
        "question": question,
        "target": metrics_summary.get("target", ""),
        "metrics": {
            "error_rate": float(metrics_summary.get("error_rate", 0.0)),
            "p99_latency_seconds": float(metrics_summary.get("p99_latency_seconds", 0.0)),
            "window_seconds": float(metrics_summary.get("window_seconds", 0.0)),
        },
        "thresholds": {
            "max_error_rate": canary["max_error_rate"],
            "max_p99_latency_seconds": canary["max_p99_latency_seconds"],
        },
    }


def run_compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["docker", "compose", "-f", str(config.COMPOSE_OUT), *args]
    return subprocess.run(cmd, cwd=config.ROOT, check=check, text=True)
