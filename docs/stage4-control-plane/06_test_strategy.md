# Test Strategy

## Governance Checks

- `python scripts/control_plane_check.py` must pass.
- `CURRENT_TASK` must match `config/runtime_status.json.current_packet`.
- Closed gates must cite evidence ids present in `05_evidence_log.md`.
- No SwiftDeploy implementation files may exist while `implementation_allowed` is `false`.

## Future CLI Checks

- `swiftdeploy init` regenerates `nginx.conf` and `docker-compose.yml` after deletion.
- `swiftdeploy validate` prints clear pass/fail output for all five required checks and exits non-zero on failure.
- `swiftdeploy deploy` runs `init`, starts the stack, and waits for health or times out at 60 seconds.
- `swiftdeploy promote canary` and `swiftdeploy promote stable` update manifest mode, regenerate Compose, restart only the service container, and confirm active mode.
- `swiftdeploy teardown --clean` removes containers, networks, volumes, and generated configs.

## Future API Checks

- `/` returns mode, version, and server timestamp.
- `/healthz` returns `status` and process uptime.
- `/chaos` supports slow, error, and recover behavior.
- Canary mode adds `X-Mode: canary` to every response.

## Future Docker And Nginx Checks

- App container runs as non-root and drops Linux capabilities.
- Service port is not host-exposed.
- Nginx listens on the manifest port.
- Nginx adds `X-Deployed-By: swiftdeploy`.
- Nginx forwards `X-Mode`.
- Nginx emits JSON 502/503/504 bodies.
- Nginx access logs match the required format.
- Built image is under 300 MB.

## Submission Checks

- Required screenshots exist and are mapped to the brief.
- README contains setup, subcommand walkthrough, architecture, and design defense.
- Blog draft claims match evidence.

## Stage 4B Checks

- `python scripts/smoke_app.py` must verify `/metrics`, required metric names, labels, histogram buckets, and gauges.
- Rego policies must return reason-bearing decision objects, not booleans, for both allow and deny cases.
- `swiftdeploy init` must render an OPA service that mounts `policies/` read-only and binds only to `127.0.0.1`.
- `swiftdeploy deploy` must start OPA first, query pre-deploy policy, and stop before app/nginx when OPA denies.
- `swiftdeploy promote canary` and `promote stable` must query canary safety policy before mutating `manifest.yaml`.
- `swiftdeploy status --once` must scrape `/metrics`, calculate req/s and p99, query policy compliance, and append `history.jsonl`.
- `swiftdeploy audit` must create GitHub-flavored `audit_report.md` from `history.jsonl`.
- OPA must not be reachable via the Nginx port.
