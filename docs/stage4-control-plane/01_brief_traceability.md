# Brief Traceability

Every requirement from the official brief must have a planned source, behavior, verification, and submission artifact before implementation starts.

| Requirement | Future source or behavior | Verification | Submission proof |
|---|---|---|---|
| `manifest.yaml` is the single source of truth | Manifest fields drive templates and deployment mode | Delete generated configs, rerun `swiftdeploy init` | README walkthrough and generated config screenshot |
| Base manifest contains `services`, `nginx`, and `network` fields | Manifest schema keeps required base fields unchanged | `swiftdeploy validate` required-field check | README manifest section |
| API service runs Python or Go | Design packet chooses stack and records rationale | API endpoint tests and Docker run | README architecture section |
| `MODE` supports stable and canary | Compose injects `MODE`, promote mutates manifest | `promote canary`, `promote stable`, `/healthz` checks | Promote screenshot |
| `GET /` returns mode, version, timestamp | API root endpoint | Curl response | README endpoint walkthrough |
| `GET /healthz` returns status and uptime | API health endpoint | Curl response and deploy wait loop | Promote health screenshot |
| `POST /chaos` supports slow, error, recover | API chaos state and canary activation decision | Curl cases and recovery case | README chaos section |
| Canary adds `X-Mode: canary` to every response | API middleware or equivalent global response handling | Header check through Nginx | Promote screenshot |
| CLI has `init`, `validate`, `deploy`, `promote`, `teardown` | `swiftdeploy` executable | Subcommand checks | README subcommand walkthrough |
| `validate` has five pre-flight checks | CLI validation function | Passing and failing validation proof | Validate screenshot |
| Nginx listens on manifest port | Nginx template rendered from manifest | Generated `nginx.conf` and curl | Generated config screenshot |
| Nginx returns JSON 502/503/504 bodies | Nginx error handlers | Nginx syntax and induced upstream failure | README explanation |
| Nginx adds `X-Deployed-By: swiftdeploy` | Nginx template header | Curl header check | README evidence |
| Nginx forwards `X-Mode` | Nginx proxy header config | Canary header through proxy | Promote screenshot |
| Access logs use required format | Nginx log format | `docker compose logs nginx` | Access log screenshot |
| Containers run non-root with dropped capabilities | Dockerfile and Compose hardening | Compose inspection and README defense | README security section |
| Service port is never exposed directly | Compose has no app host port mapping | Compose file inspection | Generated config screenshot |
| Images are under 300 MB | Docker image selection and build verification | `docker images` size check | README proof |
| Teardown removes stack and `--clean` deletes generated configs | CLI teardown behavior | File and container checks | README teardown section |

## Stage 4B Traceability

| Requirement | Planned source or behavior | Verification | Submission proof |
|---|---|---|---|
| API exposes `/metrics` in Prometheus text format | FastAPI metrics middleware and `/metrics` route | `python scripts/smoke_app.py`, curl through nginx | Status/proof output and README |
| Track request throughput/errors | `http_requests_total{method,path,status_code}` counter | Smoke test checks labels and values | `/metrics` screenshot/text capture |
| Track latency histogram | `http_request_duration_seconds` with Prometheus default buckets | Smoke test and CLI parser checks | Status output showing p99 |
| Track uptime, mode, and chaos state | `app_uptime_seconds`, `app_mode`, `chaos_active` gauges | Stable/canary smoke checks | Status output and blog chaos section |
| OPA sidecar in generated Compose | `templates/docker-compose.tmpl` renders `opa` service | `docker compose config --quiet`, generated config proof | Generated config screenshot |
| OPA reachable by CLI but not public ingress | Host binding is `127.0.0.1:${opa.port}:8181`; nginx has no OPA route | Curl OPA directly succeeds; curl via nginx `/v1/data` does not expose OPA | No-leakage proof |
| CLI does not decide allow/deny | CLI sends facts to OPA and enforces returned decision objects | Policy denial and allow evidence | Deploy/promote proof |
| Policies load from `policies/` | OPA service mounts `./policies:/policies:ro` and runs server on that directory | Compose config and OPA policy query | Generated config proof |
| Thresholds not hardcoded in Rego | Rego reads `input.thresholds`; CLI derives thresholds from manifest | Rego tests with changed thresholds | Policy proof |
| Independent policy domains | `infrastructure.rego` and `canary.rego` expose separate decision questions | Query each package independently | Status compliance list |
| Pre-deploy and pre-promote inputs differ | Host stats go to infrastructure; metrics window goes to canary | CLI evidence shows distinct input summaries | Deploy/promote proof |
| OPA output is not bare boolean | Rego returns `{domain, question, allowed, reason, violations}` | Rego and CLI output checks | Operator screenshots |
| OPA failure modes are human-readable | Python OPA client maps unavailable, timeout, unhealthy, policy error, malformed response, and deny | Injected/observed failure captures | Defense bank and proof |
| `status` dashboard | CLI scrapes metrics, computes req/s and p99, queries compliance, appends JSONL | `./swiftdeploy status --once` and live run | Status proof and `history.jsonl` |
| `audit` report | CLI parses `history.jsonl` and writes GitHub Markdown `audit_report.md` | `./swiftdeploy audit`, markdown inspection | Audit proof |
| Blog covers design, guardrails, chaos, lessons | Stage 4B article draft updated after proof refresh | Manual preview | Published blog link |

Issues settled in `SD4-DESIGN-001` (see `04_decisions_log.md`):

- API stack: Python 3.11 + FastAPI + uvicorn (D-004).
- CLI stack: Bash with embedded Python heredocs (D-005).
- Python interpreter resolution: prefer `python3`, fall back to `python` (D-006).
- YAML parsing: pyyaml as a documented prerequisite (D-007).
- Template rendering: stdlib `string.Template` with `${VAR}` placeholders (D-008).
- Manifest extension policy: base fields untouched, optional extensions defaulted at parse (D-009).
- Container healthcheck: stdlib `urllib.request`, not `curl` (D-010).
- Stable mode `/chaos` returns 403, canary mutates state; `X-Mode: canary` from HTTP middleware (D-011).
- Port pre-flight: pure Python `socket.bind()` (D-012).
- Nginx syntax check: containerized `nginx -t` against the same image we deploy (D-013).
- Portability contract: Bash 4+, Docker 20+ with Compose v2, Python 3.8+ with pyyaml, LF line endings (D-014).
