from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from . import config, history, metrics, policy


def log(message: str = "") -> None:
    print(message)


def pass_(message: str) -> None:
    print(f"[PASS] {message}")


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)


def die(message: str, code: int = 1) -> None:
    print(f"swiftdeploy: {message}", file=sys.stderr)
    raise SystemExit(code)


def run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=config.ROOT,
        check=check,
        text=True,
        capture_output=capture,
    )


def cmd_init(_args: argparse.Namespace | None = None) -> int:
    log(f"swiftdeploy init: rendering generated files from {config.MANIFEST}")
    config.render_templates()
    log("OK: nginx.conf and docker-compose.yml regenerated.")
    return 0


def validate_manifest_yaml() -> tuple[bool, dict[str, Any] | None]:
    if not config.MANIFEST.is_file():
        fail(f"manifest.yaml does not exist at {config.MANIFEST}")
        return False, None
    try:
        data = yaml.safe_load(config.MANIFEST.read_text(encoding="utf-8")) or {}
    except Exception:
        fail("manifest.yaml exists but is not valid YAML")
        return False, None
    pass_("manifest.yaml exists and is valid YAML")
    return True, data if isinstance(data, dict) else {}


def cmd_validate(_args: argparse.Namespace | None = None) -> int:
    fail_count = 0
    ok, manifest = validate_manifest_yaml()
    if not ok:
        fail_count += 1
        manifest = {}

    required = [
        ("services", "image"),
        ("services", "port"),
        ("nginx", "image"),
        ("nginx", "port"),
        ("network", "name"),
        ("network", "driver_type"),
    ]
    missing: list[str] = []
    for parent, key in required:
        section = (manifest or {}).get(parent) or {}
        if section.get(key) in (None, ""):
            missing.append(f"{parent}.{key}")
    if missing:
        fail("required manifest fields missing or empty: " + ",".join(missing))
        fail_count += 1
    else:
        pass_("all required manifest fields are present and non-empty")

    image = ((manifest or {}).get("services") or {}).get("image") or ""
    if not image:
        fail("cannot determine services.image from manifest")
        fail_count += 1
    elif run(["docker", "image", "inspect", str(image)], check=False, capture=True).returncode == 0:
        pass_(f"docker image '{image}' is present locally")
    else:
        fail(f"docker image '{image}' is not present locally (run docker build)")
        fail_count += 1

    nginx_port = ((manifest or {}).get("nginx") or {}).get("port") or ""
    if not nginx_port:
        fail("cannot determine nginx.port from manifest")
        fail_count += 1
    elif port_is_free(int(nginx_port)):
        pass_(f"nginx port {nginx_port} is free on the host")
    else:
        fail(f"nginx port {nginx_port} is already in use on the host")
        fail_count += 1

    if not config.NGINX_OUT.is_file():
        fail("nginx.conf has not been rendered yet (run: swiftdeploy init)")
        fail_count += 1
    else:
        quiet = run(
            [
                "docker",
                "run",
                "--rm",
                "--entrypoint",
                "nginx",
                "--add-host",
                "app:127.0.0.1",
                "-v",
                f"{config.NGINX_OUT}:/etc/nginx/conf.d/default.conf:ro",
                "nginx:latest",
                "-t",
                "-q",
            ],
            check=False,
            capture=True,
        )
        if quiet.returncode == 0:
            pass_("rendered nginx.conf passes 'nginx -t' inside nginx:latest")
        else:
            noisy = run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--entrypoint",
                    "nginx",
                    "--add-host",
                    "app:127.0.0.1",
                    "-v",
                    f"{config.NGINX_OUT}:/etc/nginx/conf.d/default.conf:ro",
                    "nginx:latest",
                    "-t",
                ],
                check=False,
                capture=True,
            )
            if noisy.stdout:
                print(noisy.stdout, end="")
            if noisy.stderr:
                print(noisy.stderr, end="", file=sys.stderr)
            fail("nginx -t rejected the rendered nginx.conf (see above)")
            fail_count += 1

    log()
    if fail_count == 0:
        log("validate: all 5 checks passed")
        return 0
    log(f"validate: {fail_count} check(s) failed")
    return 1


def port_is_free(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    try:
        sock.bind(("0.0.0.0", port))
    except OSError:
        return False
    finally:
        sock.close()
    return True


def ensure_opa_started() -> bool:
    log("swiftdeploy policy: starting OPA sidecar")
    result = policy.run_compose("up", "-d", "opa", check=False)
    if result.returncode != 0:
        # A stale container from a previous run (possibly under a different
        # Compose project) may be holding the container name. Stop and remove
        # it, then retry once.
        log("  OPA start failed; removing stale service container and retrying")
        policy.run_compose("rm", "-f", "-s", "opa", check=False)
        try:
            policy.run_compose("up", "-d", "opa")
        except subprocess.CalledProcessError as exc:
            fail(f"opa_unavailable: docker compose could not start OPA (exit {exc.returncode})")
            fail("  if a stale container persists, run: docker rm -f swiftdeploy-opa")
            return False
    health = policy.wait_opa_health()
    if not health.ok:
        fail(f"{health.mode}: {health.message}")
        return False
    pass_(health.message)
    return True


def print_policy_result(result: policy.PolicyResult) -> None:
    prefix = "[PASS]" if result.ok else "[FAIL]"
    print(f"{prefix} policy/{result.domain}: {result.message}")
    if result.decision:
        for violation in result.decision.get("violations", []):
            print(f"  - {violation.get('id')}: {violation.get('message')}")
    elif not result.ok:
        print(f"  - failure_mode: {result.mode}")


def append_policy_event(action: str, results: list[policy.PolicyResult], metrics_summary: dict[str, Any] | None = None) -> None:
    obs = config.observability_config()
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "timestamp": time.time(),
        "time": now,
        "event": "policy_check",
        "action": action,
        "metrics": metrics_summary or {},
        "policies": [policy_result_record(result) for result in results],
    }
    history.append_jsonl(obs["history_file"], record)


def gate_infrastructure(question: str, action: str) -> bool:
    result = policy.query_opa("infrastructure", policy.infrastructure_input(question))
    print_policy_result(result)
    append_policy_event(action, [result])
    return result.ok


def policy_result_record(result: policy.PolicyResult) -> dict[str, Any]:
    return {
        "domain": result.domain,
        "ok": result.ok,
        "mode": result.mode,
        "message": result.message,
        "decision": result.decision,
    }


def collect_metrics_summary(target: str = "") -> dict[str, Any]:
    manifest = config.load_manifest()
    nginx_port = config.manifest_get("nginx.port", manifest)
    window_seconds = config.policy_config(manifest)["canary"]["window_seconds"]
    first = metrics.scrape_metrics(nginx_port)
    # Probe through nginx between scrapes so an idle canary still produces
    # measurable error/latency samples for the policy question.
    for _ in range(5):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{nginx_port}/healthz", timeout=3).read()
        except Exception:
            pass
        time.sleep(0.2)
    last = metrics.scrape_metrics(nginx_port)
    summary = metrics.summarize_snapshots(first, last)
    summary["target"] = target
    summary["policy_window_target_seconds"] = window_seconds
    if summary["window_seconds"] == 0:
        summary["window_seconds"] = window_seconds
    return summary


def gate_canary(question: str, target: str, action: str) -> bool:
    try:
        summary = collect_metrics_summary(target)
    except Exception as exc:
        fail(f"metrics_unavailable: could not scrape /metrics for policy input: {exc}")
        return False
    result = policy.query_opa("canary", policy.canary_input(question, summary))
    print_policy_result(result)
    append_policy_event(action, [result], summary)
    return result.ok


def poll_health(timeout: int) -> bool:
    nginx_port = config.manifest_get("nginx.port")
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{nginx_port}/healthz", timeout=2) as response:
                body = json.loads(response.read().decode("utf-8"))
            if body.get("status") == "ok":
                print(f"  health ok at t={attempt}s")
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def confirm_mode(expected: str) -> bool:
    nginx_port = config.manifest_get("nginx.port")
    request = urllib.request.Request(f"http://127.0.0.1:{nginx_port}/")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))
            x_mode = response.headers.get("X-Mode")
    except Exception as exc:
        fail(f"{expected} not confirmed: {exc}")
        return False
    body_mode = body.get("mode")
    if expected == "canary" and body_mode == "canary" and x_mode == "canary":
        pass_("canary confirmed: body.mode=canary AND X-Mode: canary header present")
        return True
    if expected == "stable" and body_mode == "stable" and not x_mode:
        pass_("stable confirmed: body.mode=stable AND no X-Mode header")
        return True
    fail(f"{expected} not confirmed (body.mode={body_mode!r}, X-Mode={x_mode!r})")
    return False


def cmd_deploy(_args: argparse.Namespace | None = None) -> int:
    log("swiftdeploy deploy: rendering and starting policy sidecar")
    cmd_init()
    if not ensure_opa_started():
        return 1
    log("swiftdeploy deploy: querying pre-deploy policy")
    if not gate_infrastructure("pre_deploy", "deploy"):
        fail("deploy blocked by policy; app and nginx were not started")
        return 1
    log("swiftdeploy deploy: docker compose up -d app nginx")
    policy.run_compose("up", "-d", "app", "nginx")
    log("swiftdeploy deploy: waiting up to 60s for /healthz via nginx...")
    if poll_health(60):
        log("deploy: stack healthy")
        return 0
    fail("deploy: /healthz did not return status=ok within 60s")
    policy.run_compose("ps", check=False)
    policy.run_compose("logs", "--tail=30", "app", check=False)
    return 1


def cmd_promote(args: argparse.Namespace) -> int:
    target = args.target
    if target not in ("canary", "stable"):
        die(f"promote requires 'canary' or 'stable' (got {target!r})")
    log(f"swiftdeploy promote: target mode={target}")
    cmd_init()
    if not ensure_opa_started():
        return 1
    log("  policy: querying canary safety before manifest mutation")
    if not gate_canary("pre_promote", target, f"promote {target}"):
        fail("promote blocked by policy; manifest.yaml was not changed")
        return 1
    log("  step 1/4: mutating services.mode in manifest.yaml in-place")
    config.set_manifest_mode(target)
    log("  step 2/4: regenerating docker-compose.yml with the new MODE env")
    cmd_init()
    log("  step 3/4: recreating the app service only (--no-deps preserves nginx)")
    policy.run_compose("up", "-d", "--no-deps", "--force-recreate", "app")
    log("  step 4/4: waiting for /healthz and confirming mode")
    if not poll_health(60):
        fail("promote: /healthz did not return status=ok within 60s after recreate")
        return 1
    if not confirm_mode(target):
        return 1
    log(f"promote: completed; manifest.yaml now records mode={target}")
    return 0


def cmd_teardown(args: argparse.Namespace) -> int:
    if config.COMPOSE_OUT.is_file():
        log("swiftdeploy teardown: docker compose down -v --remove-orphans")
        policy.run_compose("down", "-v", "--remove-orphans", check=False)
    else:
        log("swiftdeploy teardown: no docker-compose.yml found; skipping compose down")
    if args.clean:
        log("swiftdeploy teardown --clean: removing generated configs")
        for path in (config.NGINX_OUT, config.COMPOSE_OUT):
            try:
                path.unlink()
                print(f"  removed: {path.name}")
            except FileNotFoundError:
                pass
    log("teardown: complete")
    return 0


def status_once(previous: metrics.MetricSnapshot | None = None) -> metrics.MetricSnapshot | None:
    manifest = config.load_manifest()
    obs = config.observability_config(manifest)
    nginx_port = config.manifest_get("nginx.port", manifest)
    now = datetime.now(timezone.utc).isoformat()
    try:
        snapshot = metrics.scrape_metrics(nginx_port)
        summary = metrics.summarize_snapshots(previous, snapshot)
    except Exception as exc:
        fail(f"metrics_unavailable: {exc}")
        return None

    policy_results = [
        policy.query_opa("infrastructure", policy.infrastructure_input("status")),
        policy.query_opa("canary", policy.canary_input("status", summary)),
    ]
    record = {
        "timestamp": snapshot.timestamp,
        "time": now,
        "event": "status_scrape",
        "action": "status",
        "metrics": summary,
        "policies": [policy_result_record(result) for result in policy_results],
    }
    history.append_jsonl(obs["history_file"], record)

    print(f"SwiftDeploy status @ {now}")
    print(f"mode={summary['mode']} chaos={summary['chaos']} uptime={summary['app_uptime_seconds']:.1f}s")
    print(
        "req/s={req_per_second:.3f} error_rate={error_rate:.2%} p99={p99_latency_seconds:.3f}s window={window_seconds:.1f}s".format(
            **summary
        )
    )
    print("Policy Compliance:")
    for result in policy_results:
        print_policy_result(result)
    print(f"history appended: {obs['history_file'].relative_to(config.ROOT)}")
    return snapshot


def cmd_status(args: argparse.Namespace) -> int:
    previous: metrics.MetricSnapshot | None = None
    interval = args.interval
    if interval is None:
        interval = config.observability_config()["status_interval"]
    while True:
        snapshot = status_once(previous)
        if snapshot is not None:
            previous = snapshot
        if args.once:
            return 0 if snapshot is not None else 1
        time.sleep(interval)


def cmd_audit(_args: argparse.Namespace | None = None) -> int:
    manifest = config.load_manifest()
    obs = config.observability_config(manifest)
    records = history.read_jsonl(obs["history_file"])
    report = render_audit_report(records)
    obs["audit_report"].write_text(report, encoding="utf-8", newline="\n")
    print(f"audit: wrote {obs['audit_report'].relative_to(config.ROOT)} from {len(records)} history record(s)")
    return 0


def render_audit_report(records: list[dict[str, Any]]) -> str:
    generated = datetime.now(timezone.utc).isoformat()
    lines = [
        "# SwiftDeploy Audit Report",
        "",
        f"- Generated: `{generated}`",
        f"- History records: `{len(records)}`",
        "",
        "## Timeline",
        "",
        "| Time | Mode | Chaos | Req/s | Error Rate | P99 Latency |",
        "|---|---|---|---:|---:|---:|",
    ]
    for record in records:
        m = record.get("metrics", {})
        lines.append(
            "| {time} | {mode} | {chaos} | {rps:.3f} | {err:.2%} | {p99:.3f}s |".format(
                time=record.get("time", ""),
                mode=m.get("mode", ""),
                chaos=m.get("chaos", ""),
                rps=float(m.get("req_per_second", 0.0)),
                err=float(m.get("error_rate", 0.0)),
                p99=float(m.get("p99_latency_seconds", 0.0)),
            )
        )

    lines.extend(["", "## Mode And Chaos Changes", ""])
    previous_mode = previous_chaos = None
    changes = 0
    for record in records:
        m = record.get("metrics", {})
        mode = m.get("mode")
        chaos = m.get("chaos")
        if mode != previous_mode or chaos != previous_chaos:
            lines.append(f"- `{record.get('time', '')}` mode=`{mode}` chaos=`{chaos}`")
            previous_mode, previous_chaos = mode, chaos
            changes += 1
    if changes == 0:
        lines.append("- No mode or chaos changes recorded.")

    lines.extend(["", "## Violations", ""])
    violation_count = 0
    for record in records:
        for result in record.get("policies", []):
            if result.get("ok"):
                continue
            violation_count += 1
            lines.append(
                f"- `{record.get('time', '')}` `{result.get('domain')}` `{result.get('mode')}`: {result.get('message')}"
            )
            decision = result.get("decision") or {}
            for violation in decision.get("violations", []) or []:
                lines.append(f"  - `{violation.get('id')}`: {violation.get('message')}")
    if violation_count == 0:
        lines.append("- No policy violations recorded.")
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="swiftdeploy")
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    sub.add_parser("init", help="Render generated configs from manifest.yaml").set_defaults(func=cmd_init)
    sub.add_parser("validate", help="Run 5 pre-flight checks").set_defaults(func=cmd_validate)
    sub.add_parser("deploy", help="Policy-gated init + compose up + health wait").set_defaults(func=cmd_deploy)

    promote = sub.add_parser("promote", help="Policy-gated mode switch")
    promote.add_argument("target", choices=["canary", "stable"])
    promote.set_defaults(func=cmd_promote)

    teardown = sub.add_parser("teardown", help="Remove containers/networks/volumes")
    teardown.add_argument("--clean", action="store_true", help="Delete generated configs")
    teardown.set_defaults(func=cmd_teardown)

    status = sub.add_parser("status", help="Live metrics and policy dashboard")
    status.add_argument("--interval", type=float, default=None)
    status.add_argument("--once", action="store_true")
    status.set_defaults(func=cmd_status)

    sub.add_parser("audit", help="Generate audit_report.md from history.jsonl").set_defaults(func=cmd_audit)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("swiftdeploy: interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
