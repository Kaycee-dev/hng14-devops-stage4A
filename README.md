# SwiftDeploy

A manifest-driven CLI for the HNG DevOps Stage 4A task. `manifest.yaml` is the
single source of truth; the `swiftdeploy` script renders Nginx and Docker
Compose configs from it, brings the stack up, switches between stable and
canary modes by mutating one line of the manifest in place, and tears
everything down again.

## Architecture

```
                +----------+
client  ----->  |  Nginx   |  ----->  app (FastAPI on uvicorn, internal only)
                | 0.0.0.0  |          MODE = stable | canary
                |  :8080   |          /, /healthz, /chaos
                +----------+
                     ^
                     |
                manifest.yaml --(swiftdeploy init)--> nginx.conf, docker-compose.yml
```

Nginx is the only public service. The app container has no `ports:` mapping;
all traffic flows through the proxy so the `X-Deployed-By` header, JSON 502/503/504
bodies, access log format, and `X-Mode` forwarding all apply.

## Prerequisites

- Bash 4+
- Docker 20+ with the Compose v2 plugin (`docker compose`, not `docker-compose`)
- Python 3.8+ on the host with `pyyaml` installed (`pip install pyyaml` or
  `apt install python3-yaml`)
- `curl`

The image (`python:3.11-slim` based) builds to 236 MB and runs as a non-root
user (UID 10001). The image tag is set in `manifest.yaml` and must match
what the manifest declares (default: `swiftdeploy-stage4a-app:1.0.0`).

## Quickstart

```bash
docker build -t swiftdeploy-stage4a-app:1.0.0 .
./swiftdeploy validate     # 5 pre-flight checks
./swiftdeploy deploy       # init + compose up + 60s health poll via /healthz
curl -i http://127.0.0.1:18080/
./swiftdeploy promote canary
curl -i http://127.0.0.1:18080/    # response now carries X-Mode: canary
./swiftdeploy promote stable
./swiftdeploy teardown --clean    # remove containers, network, volume, generated configs
```

## Subcommand reference

### `init`

Renders `nginx.conf` and `docker-compose.yml` at the repo root from
`manifest.yaml`. Idempotent: byte-identical on re-runs and on
delete-then-regenerate. Atomic write (temp file + `os.replace`) so a crash
mid-write cannot leave a half-rendered file.

### `validate`

Runs the five brief-mandated pre-flight checks. Exits non-zero on any failure.

1. `manifest.yaml` exists and parses as YAML.
2. All required base fields are present and non-empty
   (`services.image`, `services.port`, `nginx.image`, `nginx.port`,
   `network.name`, `network.driver_type`).
3. The `services.image` referenced in the manifest exists locally
   (`docker image inspect`).
4. The `nginx.port` is free on the host. The probe uses `socket.bind()` —
   the same kernel call nginx will make — so a successful bind proves the
   port is grabbable.
5. The rendered `nginx.conf` passes `nginx -t` inside the same `nginx:latest`
   image we deploy. The validator runs with `--entrypoint nginx -t -q` so the
   upstream image's setup scripts do not contaminate the output.

### `deploy`

`init` -> `docker compose up -d` -> poll `http://127.0.0.1:${nginx.port}/healthz`
(via the proxy) for up to 60 seconds, declaring the stack healthy when the JSON
response has `status == "ok"`. On failure, prints `docker compose ps` and the
last 30 lines of the app log for diagnosis.

### `promote {canary | stable}`

1. Mutate `services.mode` in `manifest.yaml` *in place* via a targeted regex.
   Comments, blank lines, and quoting in the manifest are preserved; a
   post-edit `yaml.safe_load` confirms the result is still valid YAML.
2. Rerun `init` to regenerate `docker-compose.yml` with the new `MODE` env.
3. `docker compose up -d --no-deps --force-recreate app` — recreates only the
   app container so nginx (and the gateway) stays up while the upstream cycles.
4. Poll `/healthz` until ready. Confirm the new mode by curling `/` through
   nginx and asserting BOTH that the response body's `mode` matches AND that
   the `X-Mode: canary` header is present (canary) or absent (stable).

### `teardown [--clean]`

`docker compose down -v --remove-orphans` removes containers, the named
network, and the named log volume. Without `--clean`, generated configs stay on
disk. With `--clean`, `nginx.conf` and `docker-compose.yml` are also deleted —
returning the repo to a manifest-only state, which is exactly the input to the
grader's regeneration test.

## Manifest fields

```yaml
services:
  image: swiftdeploy-stage4a-app:1.0.0 # required (must match the image you build)
  port: 3000                           # required (container port; not host-exposed)
  mode: stable                         # optional, default: stable
  version: "1.0.0"                     # optional, default: 1.0.0
  restart_policy: unless-stopped       # optional, default: unless-stopped
  log_volume: swiftdeploy-logs         # optional, default: swiftdeploy-logs

nginx:
  image: nginx:latest                  # required
  port: 18080                          # required (host-exposed)
  proxy_timeout: 30                    # optional, default: 30 (seconds)
  error_contact: ops@swiftdeploy.local # optional, default: ops@swiftdeploy.local

network:
  name: swiftdeploy-net                # required
  driver_type: bridge                  # required
```

Optional fields each have a default supplied by the renderer, so a manifest
containing only the brief's required fields still renders correctly. See
`docs/stage4-control-plane/04_decisions_log.md` decision D-009 for the
rationale.

## Endpoints

| Method | Path | Behavior |
|---|---|---|
| GET | `/` | Welcome JSON: `{message, mode, version, timestamp (RFC3339)}`. In canary mode the response also carries `X-Mode: canary`. |
| GET | `/healthz` | `{status: "ok", uptime: <seconds since process start, monotonic clock>}`. |
| POST | `/chaos` | In stable mode: returns `403 {"detail": "chaos disabled in stable mode"}`. In canary mode: accepts `{mode: "slow", duration: N}`, `{mode: "error", rate: 0..1}`, or `{mode: "recover"}` and mutates a process-local chaos state. The middleware applies the active chaos (sleep N seconds; return 500 with rate probability) to every other path; `/chaos` itself is exempt so an operator can always recover from a 100% error rate. |

## Security and image hardening

- `python:3.11-slim` base; final image is 236 MB (under the 300 MB ceiling).
- Container runs as non-root: explicit UID/GID 10001 (`useradd --no-create-home --shell /usr/sbin/nologin`).
- Compose drops all Linux capabilities (`cap_drop: [ALL]`). Nginx adds back
  exactly four (`CHOWN`, `SETUID`, `SETGID`, `NET_BIND_SERVICE`) — the minimum
  it needs to fork and drop workers and bind a privileged port if configured.
- `security_opt: [no-new-privileges:true]` on both services.
- App service has no `ports:` mapping; only nginx publishes a host port.
- In-container HEALTHCHECK uses stdlib `urllib.request` rather than `curl` —
  no apt-get layer for one HTTP probe.

## Submission proof

The full lifecycle is captured in plain-text form for the Google Drive
screenshot bundle. See `blog/assets/proof_outputs/README.md` for the file map
and how to reproduce.

| Brief screenshot | Source |
|---|---|
| validate output | `blog/assets/proof_outputs/01_validate.txt` (5/5 PASS) |
| deploy output | `blog/assets/proof_outputs/02_deploy.txt` |
| promote + /healthz | `blog/assets/proof_outputs/03_promote_canary.txt` and `04_promote_stable.txt` |
| Generated configs | `blog/assets/proof_outputs/05_generated_configs.txt` (full file contents + SHA256) |
| Nginx access logs | `blog/assets/proof_outputs/06_nginx_access_log.txt` |

To reproduce locally:

```bash
docker build -t swiftdeploy-stage4a-app:1.0.0 .
bash scripts/capture_evidence.sh
```

The capture script reads the manifest as-is (default port 18080). If you
need to change the image name or the host port, edit `manifest.yaml` first
and rebuild the image to match the new tag.

## Repo layout

```
manifest.yaml                       single source of truth (hand-edit)
swiftdeploy                         CLI (Bash + embedded Python)
Dockerfile                          builds swiftdeploy-stage4a-app:1.0.0
.dockerignore
.gitattributes                      enforces LF line endings on the script
app/
  main.py                           FastAPI app (root, healthz, chaos, X-Mode middleware)
  requirements.txt
templates/
  nginx.conf.tmpl                   string.Template, ${VAR} placeholders
  docker-compose.tmpl
  README.md                         placeholder contract
nginx.conf                          GENERATED (do not hand-edit)
docker-compose.yml                  GENERATED (do not hand-edit)
docs/stage4-control-plane/          decisions, evidence, defense bank, QA, packets
blog/                               draft article + diagrams + proof outputs
journal/                            same-day notes per packet
scripts/
  control_plane_check.py            governance guardrail
  smoke_app.py                      in-process FastAPI smoke
  capture_evidence.sh               end-to-end proof replay
```

## Design defense

Every non-trivial decision (API stack, CLI stack, YAML parsing strategy,
template rendering strategy, port-probe strategy, chaos semantics, healthcheck
strategy, hardening strategy) is recorded in
`docs/stage4-control-plane/04_decisions_log.md` (D-004 through D-014) with
alternatives considered, rationale, and an interview-ready defense statement.
The matching question/answer drills are in
`docs/stage4-control-plane/08_interview_defense_bank.md`.

## Limitations and known constraints

- Tested on Linux containers with Docker Desktop on Windows (Git Bash) and
  Docker Engine on Linux. Not tested on Podman.
- The script assumes a working Python interpreter (`python3` or `python`) on
  PATH with `pyyaml` available. The script probes `--version` to reject the
  Microsoft Store stub on Windows.
- `manifest_set_mode` uses a regex anchored to the `mode:` line. If the schema
  ever grows another `mode:` key (e.g. `nginx.mode`), the regex will need a
  section anchor. Not a current bug; documented for future maintenance.
- Slow chaos with very large durations can exceed the Compose healthcheck
  timeout, which is the expected behavior — chaos is supposed to break
  things to test resilience.
