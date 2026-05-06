"""Smoke-test Stage 4B Rego policies through the OPA Docker image."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ROOT / "policies"
MANIFEST = ROOT / "manifest.yaml"


def opa_image() -> str:
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}
    return str((manifest.get("opa") or {}).get("image", "openpolicyagent/opa:1.16.1"))


def eval_decision(query: str, input_doc: dict) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        input_path = Path(tmp) / "input.json"
        input_path.write_text(json.dumps(input_doc), encoding="utf-8")
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{POLICIES}:/policies:ro",
                "-v",
                f"{Path(tmp)}:/inputs:ro",
                opa_image(),
                "eval",
                "--format",
                "json",
                "-d",
                "/policies",
                "-i",
                "/inputs/input.json",
                query,
            ],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    payload = json.loads(result.stdout)
    return payload["result"][0]["expressions"][0]["value"]


def expect(label: str, condition: bool, detail: str = "") -> int:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f"  -> {detail}" if detail else ""))
    return 0 if condition else 1


def main() -> int:
    failures = 0
    infra_allow = eval_decision(
        "data.swiftdeploy.infrastructure.decision",
        {
            "question": "pre_deploy",
            "host": {"disk_free_gb": 20, "cpu_load": 0.5},
            "thresholds": {"min_disk_free_gb": 10, "max_cpu_load": 2.0},
        },
    )
    failures += expect("infrastructure allow returns object", isinstance(infra_allow, dict))
    failures += expect("infrastructure allow allowed=true", infra_allow.get("allowed") is True, str(infra_allow))

    infra_deny = eval_decision(
        "data.swiftdeploy.infrastructure.decision",
        {
            "question": "pre_deploy",
            "host": {"disk_free_gb": 2, "cpu_load": 3.0},
            "thresholds": {"min_disk_free_gb": 10, "max_cpu_load": 2.0},
        },
    )
    failures += expect("infrastructure deny allowed=false", infra_deny.get("allowed") is False, str(infra_deny))
    failures += expect("infrastructure deny has reasons", len(infra_deny.get("violations", [])) == 2)

    canary_allow = eval_decision(
        "data.swiftdeploy.canary.decision",
        {
            "question": "pre_promote",
            "metrics": {"error_rate": 0.0, "p99_latency_seconds": 0.1, "window_seconds": 30},
            "thresholds": {"max_error_rate": 0.01, "max_p99_latency_seconds": 0.5},
        },
    )
    failures += expect("canary allow allowed=true", canary_allow.get("allowed") is True, str(canary_allow))

    canary_deny = eval_decision(
        "data.swiftdeploy.canary.decision",
        {
            "question": "pre_promote",
            "metrics": {"error_rate": 0.2, "p99_latency_seconds": 0.9, "window_seconds": 30},
            "thresholds": {"max_error_rate": 0.01, "max_p99_latency_seconds": 0.5},
        },
    )
    failures += expect("canary deny allowed=false", canary_deny.get("allowed") is False, str(canary_deny))
    failures += expect("canary deny has reasons", len(canary_deny.get("violations", [])) == 2)
    print(f"\nTotal failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
