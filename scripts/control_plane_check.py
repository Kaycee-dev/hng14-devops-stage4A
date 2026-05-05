from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "AGENTS.md",
    "CURRENT_TASK",
    "README.md",
    "config/runtime_status.json",
    "docs/stage4-control-plane/README.md",
    "docs/stage4-control-plane/01_brief_traceability.md",
    "docs/stage4-control-plane/02_execution_roadmap.md",
    "docs/stage4-control-plane/03_code_with_me_protocol.md",
    "docs/stage4-control-plane/04_decisions_log.md",
    "docs/stage4-control-plane/05_evidence_log.md",
    "docs/stage4-control-plane/06_test_strategy.md",
    "docs/stage4-control-plane/07_qa_checklist.md",
    "docs/stage4-control-plane/08_interview_defense_bank.md",
    "docs/stage4-control-plane/09_blog_and_diagram_plan.md",
    "blog/devto/swiftdeploy-stage4.md",
    "blog/diagrams/README.md",
    "blog/assets/README.md",
    "journal/2026-05-03-stage4-governance.md",
]

TASK_PACKETS = [
    "SD4-GOV-001",
    "SD4-DESIGN-001",
    "SD4-APP-001",
    "SD4-CONTAINER-001",
    "SD4-TEMPLATE-001",
    "SD4-CLI-001",
    "SD4-CLI-002",
    "SD4-PROOF-001",
    "SD4-BLOG-001",
]

FORBIDDEN_IMPLEMENTATION_PATHS = [
    "manifest.yaml",
    "swiftdeploy",
    "app",
    "templates",
    "Dockerfile",
    "docker-compose.yml",
    "nginx.conf",
]


class CheckResult:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def pass_(self, message: str) -> None:
        print(f"[PASS] {message}")

    def fail(self, message: str) -> None:
        print(f"[FAIL] {message}")
        self.failures.append(message)

    def require(self, condition: bool, pass_message: str, fail_message: str) -> None:
        if condition:
            self.pass_(pass_message)
        else:
            self.fail(fail_message)


def rel(path: str) -> Path:
    return ROOT / path


def load_runtime(result: CheckResult) -> dict[str, Any]:
    runtime_path = rel("config/runtime_status.json")
    try:
        data = json.loads(runtime_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        result.fail("config/runtime_status.json is missing")
        return {}
    except json.JSONDecodeError as exc:
        result.fail(f"config/runtime_status.json is invalid JSON: {exc}")
        return {}

    result.pass_("config/runtime_status.json is valid JSON")
    return data if isinstance(data, dict) else {}


def check_required_files(result: CheckResult) -> None:
    for file_name in REQUIRED_FILES:
        result.require(
            rel(file_name).is_file(),
            f"required file exists: {file_name}",
            f"required file missing: {file_name}",
        )

    for packet_id in TASK_PACKETS:
        packet_path = rel(f"docs/stage4-control-plane/task-packets/{packet_id}.yaml")
        result.require(
            packet_path.is_file(),
            f"task packet exists: {packet_id}",
            f"task packet missing: {packet_id}",
        )


def check_current_task(result: CheckResult, runtime: dict[str, Any]) -> None:
    current_task_path = rel("CURRENT_TASK")
    if not current_task_path.exists():
        result.fail("CURRENT_TASK is missing")
        return

    current_task = current_task_path.read_text(encoding="utf-8").strip()
    runtime_packet = str(runtime.get("current_packet", "")).strip()
    result.require(
        current_task == runtime_packet,
        "CURRENT_TASK matches runtime_status.current_packet",
        f"CURRENT_TASK ({current_task!r}) does not match runtime_status.current_packet ({runtime_packet!r})",
    )

    if runtime_packet:
        packet_path = rel(f"docs/stage4-control-plane/task-packets/{runtime_packet}.yaml")
        result.require(
            packet_path.is_file(),
            f"current packet file exists: {runtime_packet}",
            f"current packet file missing: {runtime_packet}",
        )


def check_forbidden_implementation_files(result: CheckResult, runtime: dict[str, Any]) -> None:
    implementation_allowed = bool(runtime.get("implementation_allowed", False))
    if implementation_allowed:
        result.pass_("implementation files are allowed by runtime status")
        return

    found = [path for path in FORBIDDEN_IMPLEMENTATION_PATHS if rel(path).exists()]
    result.require(
        not found,
        "no forbidden SwiftDeploy implementation files exist while implementation_allowed is false",
        "forbidden SwiftDeploy implementation paths exist while implementation_allowed is false: "
        + ", ".join(found),
    )


def check_closed_gate_evidence(result: CheckResult, runtime: dict[str, Any]) -> None:
    evidence_path = rel("docs/stage4-control-plane/05_evidence_log.md")
    evidence_text = evidence_path.read_text(encoding="utf-8") if evidence_path.exists() else ""
    gates = runtime.get("gates", {})
    if not isinstance(gates, dict):
        result.fail("runtime_status.gates must be an object")
        return

    closed_gate_count = 0
    for gate_name, gate_value in gates.items():
        if not isinstance(gate_value, dict):
            result.fail(f"gate {gate_name} must be an object")
            continue

        if gate_value.get("status") != "closed":
            continue

        closed_gate_count += 1
        evidence_ids = gate_value.get("evidence", [])
        has_evidence = isinstance(evidence_ids, list) and bool(evidence_ids)
        result.require(
            has_evidence,
            f"closed gate {gate_name} has evidence ids",
            f"closed gate {gate_name} has no evidence ids",
        )
        if not has_evidence:
            continue

        for evidence_id in evidence_ids:
            evidence_id_text = str(evidence_id)
            result.require(
                evidence_id_text in evidence_text,
                f"evidence id {evidence_id_text} is present in evidence log",
                f"evidence id {evidence_id_text} is missing from evidence log",
            )

    if closed_gate_count == 0:
        result.pass_("no closed gates require evidence yet")


def check_blog_scaffold(result: CheckResult) -> None:
    result.require(
        rel("blog/devto/swiftdeploy-stage4.md").is_file(),
        "blog draft exists",
        "blog draft missing",
    )
    result.require(
        rel("blog/diagrams").is_dir(),
        "blog diagram directory exists",
        "blog diagram directory missing",
    )
    result.require(
        rel("blog/assets").is_dir(),
        "blog asset directory exists",
        "blog asset directory missing",
    )


def main() -> int:
    result = CheckResult()
    check_required_files(result)
    runtime = load_runtime(result)
    check_current_task(result, runtime)
    check_forbidden_implementation_files(result, runtime)
    check_closed_gate_evidence(result, runtime)
    check_blog_scaffold(result)

    if result.failures:
        print(f"\nControl-plane check failed: {len(result.failures)} issue(s).")
        return 1

    print("\nControl-plane check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
