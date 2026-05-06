# SwiftDeploy Stage 4B

SwiftDeploy is a manifest-driven deployment CLI. `manifest.yaml` remains the
single source of truth: `./swiftdeploy init` regenerates `nginx.conf` and
`docker-compose.yml`, and the grader can delete those generated files and
recreate them from the manifest.

Stage 4B extends the Stage 4A stack with Prometheus metrics, an OPA policy
sidecar, gated deploy/promote flows, a live status dashboard, and a generated
audit report.

## Architecture

```mermaid
flowchart LR
    operator[Operator CLI] -->|localhost:18181| opa[OPA sidecar]
    operator -->|localhost:18080| nginx[Nginx ingress]
    nginx --> app[FastAPI app]
    app --> metrics[/metrics]
    operator --> history[history.jsonl]
    history --> audit[audit_report.md]
```

Nginx is the only public ingress. OPA is bound to `127.0.0.1:${opa.port}` for
the local CLI and is not routed by Nginx.

## Prerequisites

- Bash 4+
- Docker 20+ with Compose v2 (`docker compose`)
- Python with `pyyaml`
- `curl`

Build the image named in the manifest:

```bash
docker build -t swiftdeploy-stage4b-app:1.0.0 .
```

## Quickstart

```bash
./swiftdeploy init
./swiftdeploy validate
./swiftdeploy deploy
./swiftdeploy status --once
./swiftdeploy promote canary
curl -X POST -H "Content-Type: application/json" \
  -d '{"mode":"error","rate":1.0}' http://127.0.0.1:18080/chaos
./swiftdeploy promote stable        # blocked by OPA while canary is unhealthy
curl -X POST -H "Content-Type: application/json" \
  -d '{"mode":"recover"}' http://127.0.0.1:18080/chaos
./swiftdeploy promote stable
./swiftdeploy audit
```

## Commands

- `init`: renders `nginx.conf` and `docker-compose.yml` from `manifest.yaml`.
- `validate`: runs the original five pre-flight checks and exits non-zero on failure.
- `deploy`: renders configs, starts OPA first, asks the infrastructure policy,
  then starts app/nginx only if OPA allows.
- `promote {canary|stable}`: scrapes `/metrics`, asks the canary policy, then
  mutates `services.mode` and recreates only the app if OPA allows.
- `status [--interval N] [--once]`: scrapes `/metrics`, calculates req/s,
  error rate, and p99 latency, displays policy compliance, and appends
  `history.jsonl`.
- `audit`: generates `audit_report.md` from `history.jsonl`.
- `teardown [--clean]`: removes containers, network, and volume; `--clean`
  also removes generated configs.

## Manifest Additions

```yaml
opa:
  image: openpolicyagent/opa:1.16.1
  port: 18181

policy:
  infrastructure:
    min_disk_free_gb: 10
    max_cpu_load: 2.0
  canary:
    max_error_rate: 0.01
    max_p99_latency_seconds: 0.5
    window_seconds: 30

observability:
  history_file: history.jsonl
  audit_report: audit_report.md
  status_interval: 5
```

Thresholds are manifest data. The Rego files in `policies/` read thresholds
from `input.thresholds`; they do not hardcode environment limits.

## Metrics

`GET /metrics` returns Prometheus text format:

- `http_requests_total{method,path,status_code}`
- `http_request_duration_seconds` histogram
- `app_uptime_seconds`
- `app_mode` (`0=stable`, `1=canary`)
- `chaos_active` (`0=none`, `1=slow`, `2=error`)

`/metrics` and `/chaos` are exempt from injected chaos so the operator can
observe and recover a degraded canary.

## Policy

OPA exposes two independent decision domains:

- `data.swiftdeploy.infrastructure.decision`: pre-deploy/status host safety.
- `data.swiftdeploy.canary.decision`: pre-promote/status canary safety.

Each returns an object with `allowed`, `reason`, and `violations`; the CLI
does not make local allow/deny decisions.

## Proof Bundle

Run:

```bash
bash scripts/capture_evidence.sh
```

The screenshot-ready outputs are listed in
`blog/assets/proof_outputs/README.md`, including policy denial, status/history,
audit report, and OPA no-leakage proof.

## Generated Artifacts

Do not hand-edit:

- `nginx.conf`
- `docker-compose.yml`
- `history.jsonl`
- `audit_report.md`

The source of truth is `manifest.yaml`, `templates/`, `policies/`, `app/`, and
the `swiftdeploy` CLI source.
