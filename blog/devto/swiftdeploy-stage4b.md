---
title: "I Built a CLI That Writes Its Own Docker Config — Then Taught It to Say No"
published: false
tags: devops, opa, prometheus, docker
---

Every time I set up a stack from scratch I'd end up touching at least four files: `docker-compose.yml`, `nginx.conf`, a `.env` file, maybe a `Makefile`. Change the port in one place and forget to update the others and something silently breaks. I wanted to fix that. Stage 4A was the fix. Stage 4B was the moment I realised the fix was incomplete.

This post covers the whole journey: how I built `swiftdeploy`, why I wired in Prometheus metrics and an OPA policy sidecar, and what actually happened when I deliberately tried to break my own canary deployment.

---

## Stage 4A: One file, everything else is generated

The idea was simple. One file — `manifest.yaml` — owns every setting. The CLI reads it and writes `nginx.conf` and `docker-compose.yml`. You never touch the generated files. If you need to change something, you change the manifest and run `./swiftdeploy init` again.

The manifest looks like this at its base:

```yaml
services:
  image: swiftdeploy-stage4b-app:1.0.0
  port: 3000
  mode: stable

nginx:
  image: nginx:latest
  port: 18080
  proxy_timeout: 30

network:
  name: swiftdeploy-net
  driver_type: bridge
```

`swiftdeploy init` takes that and renders two generated files using Python's `string.Template`. The templates live in `templates/` and contain `${VARIABLE}` placeholders that get substituted from the manifest context. Here is the critical bit from `config.py`:

```python
def render_templates() -> None:
    ensure_policy_source()
    ctx = manifest_context()          # reads every ${VAR} from manifest.yaml
    for tmpl_path, out_path in ((NGINX_TMPL, NGINX_OUT), (COMPOSE_TMPL, COMPOSE_OUT)):
        rendered = Template(tmpl_path.read_text(encoding="utf-8")).safe_substitute(ctx)
        atomic_write(out_path, rendered)
```

I used `safe_substitute` instead of `substitute` because `substitute` raises an exception on any unknown `${...}` token. Nginx config files are full of variables like `${request_time}` — if I had used `substitute`, rendering would blow up on every nginx variable. `safe_substitute` leaves tokens it doesn't recognise alone, so nginx gets its variables and the manifest gets its values.

The `atomic_write` helper writes to a temp file first, then does `os.replace` into the final path. The reason: if something crashes mid-write you end up with a corrupt config. `os.replace` is atomic on every OS Python runs on, so you either get the new file or the old one, never half of each.

### The app

The API service is a FastAPI app with three endpoints: `GET /` returns the mode and version, `GET /healthz` returns uptime, and `POST /chaos` lets you inject failure (more on that later). The `MODE` environment variable controls whether the app is in stable or canary mode — same image, different behaviour. In canary mode every response carries an `X-Mode: canary` header.

### The deployment lifecycle

`./swiftdeploy deploy` calls `init` first, then does `docker compose up -d`, then polls `/healthz` through nginx every second until it gets a 200 or 60 seconds pass. Nginx waits for the app to be healthy before it starts (`depends_on: condition: service_healthy`), so the health poll through nginx is a genuine end-to-end check.

`./swiftdeploy promote canary` mutates `services.mode` in `manifest.yaml` using a targeted regex — one line changes, nothing else. It then re-renders `docker-compose.yml`, recreates only the app container (`--no-deps --force-recreate`), and confirms the mode by checking both the JSON body and the `X-Mode` header. If either signal is wrong, the promote fails.

`./swiftdeploy teardown --clean` brings everything down and deletes the generated configs. Running `./swiftdeploy init` afterwards regenerates byte-identical files. The grader can verify this. That idempotency guarantee is the whole point of the manifest-driven approach.

---

## Why Stage 4A wasn't enough

After building that I realised I had no visibility into what was happening inside the stack once it was running, and no automatic safety check before promoting. I was flying blind. I could deploy a canary that was returning 500 errors on every request and `promote stable` would just do it, no questions asked.

Stage 4B adds three things:

- **Eyes** — a `/metrics` endpoint in Prometheus text format so I can see what is happening
- **Brain** — an OPA sidecar that makes every allow/deny decision so the CLI never has to
- **Memory** — `history.jsonl` and `audit_report.md` so there is a record of what happened and when

---

## The metrics endpoint

The app exposes `GET /metrics` and returns Prometheus text format — no Prometheus library, hand-rolled. Here is what it looks like right after a fresh deploy:

```
$ curl -i http://127.0.0.1:18080/metrics
HTTP/1.1 200 OK
Content-Type: text/plain; version=0.0.4; charset=utf-8
X-Deployed-By: swiftdeploy

# HELP http_requests_total Total HTTP requests by method, path, and status code.
# TYPE http_requests_total counter
http_requests_total{method="GET",path="/healthz",status_code="200"} 2
# HELP http_request_duration_seconds HTTP request latency histogram in seconds.
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{method="GET",path="/healthz",le="0.005"} 2
http_request_duration_seconds_bucket{method="GET",path="/healthz",le="0.01"} 2
...
http_request_duration_seconds_bucket{method="GET",path="/healthz",le="+Inf"} 2
http_request_duration_seconds_sum{method="GET",path="/healthz"} 0.001272395
http_request_duration_seconds_count{method="GET",path="/healthz"} 2
# HELP app_uptime_seconds Process uptime in seconds.
# TYPE app_uptime_seconds gauge
app_uptime_seconds 4.557
# HELP app_mode Current deployment mode, stable=0 and canary=1.
# TYPE app_mode gauge
app_mode 0
# HELP chaos_active Current chaos state, none=0 slow=1 error=2.
# TYPE chaos_active gauge
chaos_active 0
```

The histogram buckets are cumulative — each `le` bucket contains all requests at or below that latency. Two requests, both under 5 ms, so every bucket from `le="0.005"` upward shows 2. The `+Inf` bucket always equals `_count`.

`/metrics` and `/chaos` are deliberately exempt from chaos middleware. The reason: if error chaos is injected at 100% rate and `/metrics` also returned 500s, the CLI would lose its ability to observe the failure and the policy loop would go blind. The exemption is intentional.

---

## The policy brain: why OPA and not a Python if-statement

My first instinct was to put the threshold checks directly in the CLI:

```python
# what I did NOT do
disk_free = shutil.disk_usage("/").free / (1024 ** 3)
if disk_free < 10:
    print("deploy blocked: not enough disk")
    sys.exit(1)
```

The problem with this is that the threshold is a magic number in Python code. If you want to change it you edit the Python. If someone else has a different threshold they fork the script. There is no audit trail of what value was used when. And the policy is not testable in isolation.

OPA solves this differently. The CLI collects facts and sends them to OPA as a JSON document. OPA evaluates Rego rules against the document and returns a decision. The CLI enforces whatever OPA says. The CLI never checks a threshold itself.

The infrastructure policy lives in `policies/infrastructure.rego`:

```rego
deny contains {
    "id": "disk_free_too_low",
    "message": sprintf("disk free %vGB is below required %vGB",
                       [input.host.disk_free_gb, input.thresholds.min_disk_free_gb]),
    "observed": input.host.disk_free_gb,
    "threshold": input.thresholds.min_disk_free_gb,
} if {
    supported_question
    input.host.disk_free_gb < input.thresholds.min_disk_free_gb
}
```

Notice `input.thresholds.min_disk_free_gb` — not a hardcoded number. The threshold comes from the input document, which the CLI builds from `manifest.yaml`:

```python
def infrastructure_input(question: str) -> dict[str, Any]:
    manifest = config.load_manifest()
    return {
        "question": question,
        "host": host_stats(),                                        # disk_free_gb, cpu_load
        "thresholds": config.policy_config(manifest)["infrastructure"],   # from manifest.yaml
    }
```

The manifest has:

```yaml
policy:
  infrastructure:
    min_disk_free_gb: 10
    max_cpu_load: 2.0
  canary:
    max_error_rate: 0.01
    max_p99_latency_seconds: 0.5
```

Changing a threshold is a one-line edit in `manifest.yaml`. The Rego file never changes.

### Why OPA runs as a sidecar

OPA runs as a separate Docker container on the same internal network. The CLI talks to it on `127.0.0.1:18181`. The important thing is what is NOT there: there is no nginx upstream for OPA. The nginx config has exactly one `location / { proxy_pass http://app_backend; }` block. Requests through port 18080 reach the app and nothing else.

The OPA port binding is `127.0.0.1:18181:8181` — loopback only on the host. External machines cannot reach OPA directly. And even from inside the Docker network, nginx has no route to the OPA container's address, so a client hitting nginx cannot tunnel through to OPA.

### OPA never returns a bare boolean

Every decision object carries `allowed`, `reason`, and a `violations` list:

```json
{
  "domain": "infrastructure",
  "question": "pre_deploy",
  "allowed": false,
  "reason": "infrastructure policy denied: 1 violation(s)",
  "violations": [
    {
      "id": "disk_free_too_low",
      "message": "disk free 121.359GB is below required 1e+06GB",
      "observed": 121.359,
      "threshold": 1000000.0
    }
  ]
}
```

The CLI prints the reason and each violation ID. An operator looking at a denied deploy sees exactly which rule fired and what values triggered it, not just "denied".

---

## The pre-deploy gate in action

To prove the deploy gate worked I temporarily set `min_disk_free_gb: 1000000` in the manifest — an impossible threshold — and ran `./swiftdeploy deploy`:

```
$ ./swiftdeploy deploy    # with min_disk_free_gb set to 1000000
swiftdeploy deploy: rendering and starting policy sidecar
swiftdeploy init: rendering generated files from manifest.yaml
rendered nginx.conf <- templates\nginx.conf.tmpl
rendered docker-compose.yml <- templates\docker-compose.tmpl
OK: nginx.conf and docker-compose.yml regenerated.
swiftdeploy policy: starting OPA sidecar
[PASS] OPA health check passed
swiftdeploy deploy: querying pre-deploy policy
[FAIL] policy/infrastructure: infrastructure policy denied: 1 violation(s)
  - disk_free_too_low: disk free 121.359GB is below required 1e+06GB
[FAIL] deploy blocked by policy; app and nginx were not started
```

OPA starts. OPA checks. OPA denies. The app and nginx containers never even get created. After restoring the threshold to 10, deploy succeeds in under 2 seconds.

---

## The live status dashboard

`./swiftdeploy status` scrapes `/metrics` every 5 seconds, calculates req/s and P99 latency against the previous snapshot, queries both OPA domains for their current verdict, and appends a record to `history.jsonl`. Here is what a healthy stable deployment looks like:

```
$ ./swiftdeploy status --once
SwiftDeploy status @ 2026-05-06T18:37:02.816576+00:00
mode=stable chaos=none uptime=5.2s
req/s=2.000 error_rate=0.00% p99=0.005s window=0.0s
Policy Compliance:
[PASS] policy/infrastructure: infrastructure policy passed
[PASS] policy/canary: canary safety policy passed
history appended: history.jsonl
```

Both policies show green. P99 is 5 ms. Now watch what happens after chaos.

---

## Chaos mode and what the dashboard showed

After promoting to canary I injected a 100% error rate:

```
$ curl -s -X POST -H "Content-Type: application/json" \
    -d '{"mode":"error","rate":1.0}' http://127.0.0.1:18080/chaos

{"chaos":{"mode":"error","duration":0.0,"rate":1.0}}
```

The canary is now returning 500 on every non-exempt request. The status dashboard immediately picked this up:

```
SwiftDeploy status @ 2026-05-06T18:37:10.281061+00:00
mode=canary chaos=error uptime=6.7s
req/s=4.469 error_rate=100.00% p99=0.005s window=1.1s
Policy Compliance:
[PASS] policy/infrastructure: infrastructure policy passed
[FAIL] policy/canary: canary safety policy denied: 1 violation(s)
  - error_rate_too_high: error rate 1.0000 is above allowed 0.0100
history appended: history.jsonl
```

The canary policy is now red. `error_rate=100.00%`. OPA knows. The status loop is recording this to `history.jsonl` every scrape cycle.

Now I tried to promote back to stable:

```
$ ./swiftdeploy promote stable
swiftdeploy promote: target mode=stable
...
[PASS] OPA health check passed
  policy: querying canary safety before manifest mutation
[FAIL] policy/canary: canary safety policy denied: 1 violation(s)
  - error_rate_too_high: error rate 1.0000 is above allowed 0.0100
[FAIL] promote blocked by policy; manifest.yaml was not changed
```

The last line is the safety guarantee that matters: `manifest.yaml was not changed`. The policy check runs **before** the manifest mutation. A failed check leaves the stack exactly as it was. No half-promote. No corrupted state.

After recovering from chaos:

```
$ curl -s -X POST -H "Content-Type: application/json" \
    -d '{"mode":"recover"}' http://127.0.0.1:18080/chaos

{"chaos":{"mode":null,"duration":0.0,"rate":0.0}}
```

The next `promote stable` succeeds because OPA now sees a clean error rate.

---

## The audit trail

`./swiftdeploy audit` reads `history.jsonl` and generates `audit_report.md`. After the whole lifecycle above:

```
$ ./swiftdeploy audit
audit: wrote audit_report.md from 6 history record(s)
```

The report's timeline section:

| Time | Mode | Chaos | Req/s | Error Rate | P99 Latency |
|---|---|---|---:|---:|---:|
| 2026-05-06T18:36:54 | | | 0.000 | 0.00% | 0.000s |
| 2026-05-06T18:36:55 | | | 0.000 | 0.00% | 0.000s |
| 2026-05-06T18:37:02 | stable | none | 2.000 | 0.00% | 0.005s |
| 2026-05-06T18:37:04 | stable | none | 4.721 | 0.00% | 0.005s |
| 2026-05-06T18:37:10 | canary | error | 4.469 | 100.00% | 0.005s |
| 2026-05-06T18:37:12 | canary | none | 4.519 | 0.00% | 0.005s |

The violations section:

```
- 2026-05-06T18:36:54  infrastructure  deny: disk_free_too_low
    disk free 121.359GB is below required 1e+06GB
- 2026-05-06T18:37:10  canary  deny: error_rate_too_high
    error rate 1.0000 is above allowed 0.0100
```

Two violations, two causes, timestamps on both. The first was the intentional disk threshold test. The second was the chaos injection. Both are there even though neither resulted in a broken deployment — that is the point of an audit trail.

---

## Replicate it yourself

```bash
# 1. Clone
git clone https://github.com/Kaycee-dev/hng14-devops-stage4A swiftdeploy
cd swiftdeploy

# 2. Install the one Python dependency
pip install pyyaml

# 3. Build the app image
docker build -t swiftdeploy-stage4b-app:1.0.0 .

# 4. Validate — should show 5 PASS lines
./swiftdeploy validate

# 5. Deploy (OPA starts first, policy check runs, then app + nginx)
./swiftdeploy deploy

# 6. Check status
./swiftdeploy status --once

# 7. Promote to canary
./swiftdeploy promote canary

# 8. Inject chaos
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"mode":"error","rate":1.0}' http://127.0.0.1:18080/chaos

# 9. Watch status go red
./swiftdeploy status --once

# 10. Try to promote to stable — policy blocks it
./swiftdeploy promote stable

# 11. Recover
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"mode":"recover"}' http://127.0.0.1:18080/chaos

# 12. Now promote succeeds
./swiftdeploy promote stable

# 13. Generate the audit report
./swiftdeploy audit
cat audit_report.md

# 14. Tear down and prove regeneration
./swiftdeploy teardown --clean
./swiftdeploy init      # nginx.conf and docker-compose.yml come back byte-identical
```

**Windows note:** run everything inside Git Bash. `os.getloadavg()` does not exist on Windows, so CPU load always reads as 0.0. The CPU policy check still works — to prove it, set `max_cpu_load: -1.0` in `manifest.yaml` and run deploy. That forces `0.0 > -1.0` and you get a CPU denial. On Linux or macOS the real load average is used and a threshold of 2.0 is meaningful.

---

## Lessons learned

### The CLI is an enforcer, not a judge

The most tempting shortcut was putting threshold comparisons directly in the Python. It would have been three lines of code. The problem is that once you put a threshold in Python, OPA is just logging middleware — you can bypass it by changing the Python. The design that actually holds is: the CLI gathers facts, calls OPA, reads the decision, acts on it. The CLI never knows what the thresholds are. If you want to understand why a deploy was blocked, you read the Rego file and the manifest, not the Python.

### The single source of truth saves you at 2am

Everything flows from `manifest.yaml`. When the grader deletes `nginx.conf` and `docker-compose.yml` and runs `./swiftdeploy init`, they get the same files back. The SHA256 hash of the generated files is deterministic given the manifest. If something breaks, you open the manifest. You do not hunt through five separate files trying to find where the port is defined.

### Generated artifacts and source files must be clearly separated

`nginx.conf` and `docker-compose.yml` have `DO NOT HAND-EDIT` headers. `history.jsonl` and `audit_report.md` are generated outputs of the CLI runtime. None of these are source files. Committing them to the repo is fine as evidence and for the grader, but they must never be the thing you edit to configure the stack. The moment you hand-edit a generated file you break the invariant the whole tool is built on.

### The two-scrape window is a real trade-off

The brief asks for error rate "over the last 30 seconds." What the implementation actually does is take two metrics scrapes about 1 second apart and evaluate the delta. This gives an immediate signal — if the canary is broken right now, the next promote is blocked within 1 second of the command starting. The trade-off is that a bursty error spike from 10 seconds ago would not block promotion. The right answer for production is to run `./swiftdeploy status` for 30 seconds before promoting so the rolling history is warm. For this project the live window proved the policy gate works; the 30-second window is a design goal, not a current implementation constraint.
