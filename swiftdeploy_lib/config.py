from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from string import Template
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - exercised by CLI startup
    raise SystemExit("swiftdeploy: PyYAML is required (pip install pyyaml)") from exc


ROOT = Path(os.environ.get("SWIFTDEPLOY_ROOT", Path(__file__).resolve().parents[1]))
MANIFEST = ROOT / "manifest.yaml"
TEMPLATE_DIR = ROOT / "templates"
NGINX_TMPL = TEMPLATE_DIR / "nginx.conf.tmpl"
COMPOSE_TMPL = TEMPLATE_DIR / "docker-compose.tmpl"
NGINX_OUT = ROOT / "nginx.conf"
COMPOSE_OUT = ROOT / "docker-compose.yml"
POLICIES_DIR = ROOT / "policies"


def load_manifest() -> dict[str, Any]:
    if not MANIFEST.is_file():
        raise SystemExit(f"swiftdeploy: manifest.yaml not found at {MANIFEST}")
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit("swiftdeploy: manifest.yaml must contain a YAML object")
    return data


def need(section: dict[str, Any], key: str, where: str) -> Any:
    value = section.get(key)
    if value in (None, ""):
        raise SystemExit(f"swiftdeploy: manifest.{where}.{key} is missing or empty")
    return value


def manifest_context(manifest: dict[str, Any] | None = None) -> dict[str, str]:
    m = manifest or load_manifest()
    services = m.get("services") or {}
    nginx = m.get("nginx") or {}
    network = m.get("network") or {}
    opa = m.get("opa") or {}

    mode = str(services.get("mode", "stable"))
    if mode not in ("stable", "canary"):
        raise SystemExit(f"swiftdeploy: services.mode must be stable or canary (got {mode!r})")

    return {
        "SERVICE_IMAGE": str(need(services, "image", "services")),
        "SERVICE_PORT": str(need(services, "port", "services")),
        "NGINX_IMAGE": str(need(nginx, "image", "nginx")),
        "NGINX_PORT": str(need(nginx, "port", "nginx")),
        "NETWORK_NAME": str(need(network, "name", "network")),
        "NETWORK_DRIVER": str(need(network, "driver_type", "network")),
        "MODE": mode,
        "APP_VERSION": str(services.get("version", "1.0.0")),
        "RESTART_POLICY": str(services.get("restart_policy", "unless-stopped")),
        "LOG_VOLUME": str(services.get("log_volume", "swiftdeploy-logs")),
        "PROXY_TIMEOUT": str(nginx.get("proxy_timeout", "30")),
        "ERROR_CONTACT": str(nginx.get("error_contact", "ops@swiftdeploy.local")),
        "OPA_IMAGE": str(opa.get("image", "openpolicyagent/opa:1.16.1")),
        "OPA_PORT": str(opa.get("port", "18181")),
    }


def policy_config(manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    m = manifest or load_manifest()
    policy = m.get("policy") or {}
    infra = policy.get("infrastructure") or {}
    canary = policy.get("canary") or {}
    return {
        "infrastructure": {
            "min_disk_free_gb": float(infra.get("min_disk_free_gb", 10)),
            "max_cpu_load": float(infra.get("max_cpu_load", 2.0)),
        },
        "canary": {
            "max_error_rate": float(canary.get("max_error_rate", 0.01)),
            "max_p99_latency_seconds": float(canary.get("max_p99_latency_seconds", 0.5)),
            "window_seconds": int(canary.get("window_seconds", 30)),
        },
    }


def observability_config(manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    m = manifest or load_manifest()
    observability = m.get("observability") or {}
    return {
        "history_file": ROOT / str(observability.get("history_file", "history.jsonl")),
        "audit_report": ROOT / str(observability.get("audit_report", "audit_report.md")),
        "status_interval": float(observability.get("status_interval", 5)),
    }


def manifest_get(path: str, manifest: dict[str, Any] | None = None) -> Any:
    cur: Any = manifest or load_manifest()
    for part in path.split("."):
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(part)
        if cur is None:
            return ""
    return cur


def set_manifest_mode(target: str) -> None:
    if target not in ("stable", "canary"):
        raise SystemExit(f"swiftdeploy: invalid mode {target!r}")

    text = MANIFEST.read_text(encoding="utf-8")
    pattern = re.compile(r"(?m)^services:\n(?P<body>(?:[ \t]+.*(?:\n|$))*)")
    match = pattern.search(text)
    if not match:
        raise SystemExit("swiftdeploy: services section not found in manifest.yaml")

    body = match.group("body")
    new_body, count = re.subn(
        r"(?m)^([ \t]+mode:[ \t]+)\S+",
        lambda m: m.group(1) + target,
        body,
        count=1,
    )
    if count == 0:
        raise SystemExit("swiftdeploy: services.mode line not found in manifest.yaml")

    new_text = text[: match.start("body")] + new_body + text[match.end("body") :]
    MANIFEST.write_text(new_text, encoding="utf-8", newline="\n")
    parsed = load_manifest()
    if manifest_get("services.mode", parsed) != target:
        raise SystemExit("swiftdeploy: post-edit verification failed for services.mode")


def ensure_policy_source() -> None:
    if not POLICIES_DIR.is_dir():
        raise SystemExit("swiftdeploy: policies/ directory is missing")
    rego_files = sorted(POLICIES_DIR.glob("*.rego"))
    if not rego_files:
        raise SystemExit("swiftdeploy: policies/ must contain at least one .rego file")


def atomic_write(target: Path, text: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".swiftdeploy.", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
            out.write(text)
        os.replace(tmp, target)
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def render_templates() -> None:
    ensure_policy_source()
    ctx = manifest_context()
    for path in (NGINX_TMPL, COMPOSE_TMPL):
        if not path.is_file():
            raise SystemExit(f"swiftdeploy: template missing: {path}")

    for tmpl_path, out_path in ((NGINX_TMPL, NGINX_OUT), (COMPOSE_TMPL, COMPOSE_OUT)):
        rendered = Template(tmpl_path.read_text(encoding="utf-8")).safe_substitute(ctx)
        atomic_write(out_path, rendered)
        print(f"rendered {out_path.name} <- {tmpl_path.relative_to(ROOT)}")
