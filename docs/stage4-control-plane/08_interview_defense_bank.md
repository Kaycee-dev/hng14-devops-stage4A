# Interview Defense Bank

This file tracks questions the operator must be able to answer without AI.

## Governance Questions

1. Why did you create a control plane before writing code?
   - Because the task is graded not only by working output but by whether the work can be explained, regenerated, and defended. The control plane keeps requirements, decisions, evidence, and tests aligned.

2. Why block implementation with `implementation_allowed: false`?
   - To prevent premature files from appearing before the design choices are settled. This is especially important because the grader will test idempotency and generated artifacts.

3. Why keep an evidence log?
   - Claims are weak without proof. Evidence ids make it clear which command, screenshot, or artifact supports each gate.

4. Why not copy Claude's implementation directly?
   - Its response contains useful ideas, but it makes assumptions that must be verified against the brief and the grader environment.

## Design Questions (settled in SD4-DESIGN-001)

5. **Why FastAPI over Flask or Go?**
   - The chaos `slow` mode says "sleep N seconds before responding." `asyncio.sleep` in FastAPI is non-blocking — one slow request does not occupy a thread. Flask's WSGI model would force me into thread workers; Go would mean switching languages mid-stage. FastAPI is the smallest defensible step.

6. **Why Bash for the CLI with Python heredocs, not pure Python?**
   - The CLI orchestrates external processes (`docker compose`, `nginx -t`, `curl`). Bash is the natural shell for that. Python is invoked only where Bash is weak: YAML parsing, YAML mutation, template rendering, socket probes. Splitting the work this way means each half is short and individually defensible.

7. **Why pyyaml as a host prerequisite instead of a hand-rolled parser?**
   - The Python stdlib has no YAML parser. A hand parser would silently mishandle whitespace and quoting that the grader could legitimately introduce. pyyaml is in most distro packages and pip-installable. The README declares it as a prerequisite, which is honest about the dependency.

8. **Why `string.Template` for rendering, not `sed` or Jinja2?**
   - Manifest values include `:` and `/` (every Docker image string), which are sed delimiter hazards. We have zero conditional rendering needs, so Jinja2 would be over-engineering. `string.Template.safe_substitute` is stdlib and exact.

9. **Why is `/chaos` 403 in stable mode rather than 404?**
   - 403 expresses the policy ("chaos is disabled here"). 404 would be ambiguous — caller cannot tell whether the path is wrong or the policy denies them. The route topology stays constant across modes; only behavior changes.

10. **Why does the X-Mode header live in middleware?**
    - The brief says canary adds X-Mode to *every* response, including error responses. Per-handler injection misses error paths and any future endpoint a developer adds. Middleware applies globally before the response leaves the app.

11. **Why use stdlib `urllib.request` for the healthcheck instead of `curl`?**
    - `python:3.11-slim` does not ship `curl`. Adding it via `apt-get` adds a layer and around 5 MB to the image for a single HTTP probe. The Python interpreter is already there; reusing it is free.

12. **Why probe ports with `socket.bind()` instead of `ss`/`lsof`?**
    - `ss` and `lsof` are not present on Git Bash for Windows nor on minimal Linux containers. `socket.bind()` is stdlib, cross-platform, and tests the kernel the same way nginx will. If `bind` fails for our probe, it will fail for nginx.

13. **Why run `nginx -t` inside a container instead of on the host?**
    - The host may not have nginx installed, or may have a different version. Running `nginx -t` inside the same image we ship validates against the exact binary that will serve traffic.

14. **What happens if the manifest only has the brief's required fields and nothing else?**
    - The CLI applies defaults at parse time for every optional extension (`mode=stable`, `version=1.0.0`, `restart_policy=unless-stopped`, `log_volume=swiftdeploy-logs`, `proxy_timeout=30`, `error_contact=ops@swiftdeploy.local`). Templates render correctly because every placeholder still resolves.

15. **Why `set -euo pipefail` at the top of the CLI?**
    - `-e` aborts on the first failing command instead of continuing in a half-broken state. `-u` catches typos in variable names instead of expanding them to empty strings. `-o pipefail` propagates a non-zero exit from any command in a pipeline so failures are not swallowed by a successful tail command.

## API Questions (settled in SD4-APP-001)

16. **Why `time.monotonic()` for uptime instead of `time.time()`?**
    - Monotonic time only moves forward. `time.time()` is wall clock; if NTP corrects the host clock backward (or if someone runs `date`), uptime visibly decreases or goes negative. That is a bug an SRE will catch instantly.

17. **Why is the X-Mode header added in middleware, not in each route?**
    - The brief says canary adds X-Mode to *every* response, including 4xx and 5xx. Per-route injection misses error responses and any future route a developer adds. Middleware applies globally.

18. **Why is the X-Mode middleware registered AFTER the chaos middleware?**
    - In FastAPI/Starlette, the last-registered middleware becomes the outermost wrapper — it runs last on the response side. The X-Mode middleware therefore sees the final response, including the chaos-injected 500 from the inner middleware. The smoke test asserts this directly: chaos rate 1.0 returns 500 *with* X-Mode: canary.

19. **Why does the chaos middleware return `JSONResponse(...)` directly instead of raising `HTTPException`?**
    - Direct return is one trip through the middleware stack. Raising would route through FastAPI's exception handlers, adding an extra hop and a less predictable response path. The middleware owns its own contract — direct response is the right shape.

20. **Why is `/chaos` exempt from chaos effects?**
    - Recovery escape hatch. With error rate=1.0, every other endpoint returns 500. If `/chaos` were also affected, the operator could never recover. The middleware bypasses chaos when `request.url.path == "/chaos"`. The smoke test proves: chaos rate 1.0 plus `POST /chaos {recover}` still returns 200.

21. **Why does the stable-mode `/chaos` handler check `MODE` *before* parsing the body?**
    - The policy is "chaos disabled in stable mode" — that should be the response on any request to `/chaos` in stable, malformed body or not. Body validation first would surface a 422 about missing fields, hiding the real policy. Mode check first surfaces the actual reason.

22. **What does `Literal["slow","error","recover"]` give you that a string check would not?**
    - It moves validation from runtime conditional code into the type system. Pydantic enforces the closed set at parse time and returns a clean 422 for unknown values, with no manual `if/elif/else` for unsupported modes.

23. **What state is the chaos machine in after a container restart?**
    - Reset. `chaos_state` is a module-level dict; the dict re-initializes on import, which happens on every fresh process. The brief says canary "activates" chaos but does not require persistence — process-local is the simplest defensible model.

24. **What does `response.headers["X-Mode"] = "canary"` do that nginx couldn't?**
    - Nginx can pass headers through but the X-Mode value is a property of *the upstream service* — only the app knows whether it is currently running as canary or stable. Setting the header at the app boundary is the right layer; nginx then forwards it untouched.

## Container Questions (settled in SD4-CONTAINER-001)

25. **Why `python:3.11-slim` and not `alpine`?**
    - Alpine uses musl libc. uvloop and httptools (pulled in by `uvicorn[standard]`) ship glibc-only manylinux wheels. On alpine pip would have to compile them from source, which can fail or balloon the image. Slim is Debian-glibc, so the wheels install in seconds and the final image is 236 MB — already under the cap.

26. **Why is the image 236 MB, not the ~150 MB of slim itself?**
    - 150 MB is the bare base. Layered on top: pip-installed FastAPI + Pydantic v2 + uvloop + httptools + watchfiles + websockets, plus app code. Pydantic v2's compiled `pydantic_core` binary alone is ~10 MB. Total addition is around 86 MB. Still 64 MB under the 300 MB ceiling.

27. **Why is `requirements.txt` copied and installed BEFORE the app source?**
    - Docker layer caching. Each `COPY` and `RUN` is a layer; if the inputs to that layer don't change, Docker reuses the cached output. Putting `pip install` before app code means editing `main.py` and rebuilding only re-runs the final two `COPY` layers, not the network-bound pip step.

28. **Why `--no-cache-dir` (and `PIP_NO_CACHE_DIR=1`)?**
    - pip's wheel cache only helps across separate pip runs on the same host. Each Docker `RUN` is its own layer; the cache it builds is never read again. Caching just bakes 30+ MB of unused tarballs into the image.

29. **Why `PYTHONDONTWRITEBYTECODE=1` and `PYTHONUNBUFFERED=1`?**
    - DONTWRITEBYTECODE prevents `.pyc` files from being written into the image's writable layer at runtime — they'd be a deduplication waste in immutable containers. UNBUFFERED makes stdout/stderr line-flush, so `docker logs` shows output immediately rather than buffering it for crash analysis.

30. **Why is `cap_drop: ALL` in the Compose template, not the Dockerfile?**
    - Linux capabilities are a *runtime* property of the container — they live in the runc/containerd config, not in the image. Dockerfiles describe what the image contains, not how the host runs it. The Compose file is the right place.

31. **Why explicit UID 10001 instead of `--system` (low UID)?**
    - High UIDs avoid collisions if a host bind-mount path is owned by some low-numbered system user. The intent is "this user is application-scoped, isolated from any UID the host might use." It also documents the choice; a default `useradd -r` would pick something between 100–999 silently.

32. **What does the in-container HEALTHCHECK actually run?**
    - `python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:$APP_PORT/healthz', timeout=2)"`. Exits 0 on HTTP 200, non-zero otherwise. Uses stdlib only — no `curl` install (D-010).

33. **What is the difference between `EXPOSE` in a Dockerfile and `ports:` in Compose?**
    - `EXPOSE` is metadata — it documents which ports the image listens on but does NOT publish them. `ports:` in Compose actually publishes a host:container mapping. The brief forbids exposing the app port directly, so I never set `ports:` for `app`; nginx is the only published service.

## Template Questions (settled in SD4-TEMPLATE-001)

34. **Why are `nginx.conf` and `docker-compose.yml` GENERATED files, not committed source?**
    - The brief makes the manifest the single source of truth and explicitly tests this by deleting the generated files and rerunning `init`. Committing the generated outputs would create two sources of truth that could drift.

35. **Why use `${VAR}` placeholders and not a templating engine like Jinja2?**
    - We have no conditionals or loops. Stdlib `string.Template.safe_substitute` is the smallest tool that does the job. Adding Jinja2 means another pip dependency and another thing to defend.

36. **How do you stop `${request_time}` (an nginx variable that needs to survive into the rendered file) from being treated as a Python placeholder?**
    - `string.Template` treats `$$` as a literal `$`. The template stores `$${request_time}s` and renders to `${request_time}s` — exactly the brief's required log format. Same trick for shell-style nginx variables: `$$host`, `$$remote_addr`, etc.

37. **Why is `add_header X-Deployed-By swiftdeploy always;` qualified with `always`?**
    - Without `always`, nginx only emits the header on 2xx/3xx responses. The brief implies it applies on every response, including the JSON 502/503/504 we render — `always` is what makes that work.

38. **Why use `proxy_pass_header X-Mode;` rather than relying on nginx to forward it automatically?**
    - Nginx hides certain upstream headers by default (`Date`, `Server`, `X-Accel-*`). Even though `X-Mode` is not on that hidden list, declaring `proxy_pass_header X-Mode;` is the defensible move: explicit beats implicit.

39. **Why does the rendered `nginx.conf` go to `/etc/nginx/conf.d/default.conf`, not `/etc/nginx/nginx.conf`?**
    - The official nginx image's master config (`nginx.conf`) ends with `include /etc/nginx/conf.d/*.conf;`. Replacing only the `conf.d/default.conf` slot reuses the upstream image's worker, MIME, log-rotation, and event tuning — much smaller surface area than rewriting the master config.

40. **What does `error_page 502 = @err502;` (with the `=`) do that plain `error_page 502 @err502;` would not?**
    - The `=` rewrites the response status to whatever the named location returns. Without it, the named location's `return 502` would be ignored and the original upstream code would be used. We want full control of the response code AND body, so we use `=`.

41. **Why does the app service have no `ports:` block?**
    - The brief mandates it: traffic must flow through nginx so the X-Deployed-By header, JSON error bodies, and access log format all apply. Publishing the app port would let callers bypass nginx and skip the entire proxy contract.

42. **Why is `cap_drop: ALL` in Compose, not in the Dockerfile?**
    - Linux capabilities are a runtime container property managed by runc/containerd, not an image property. Dockerfiles describe the image; Compose describes how the runtime starts it. So caps belong here.

43. **Why does nginx need `cap_add: [CHOWN, SETUID, SETGID, NET_BIND_SERVICE]` after `cap_drop: ALL`?**
    - The nginx master starts as root (or the image user), then forks workers and drops them to the `nginx` user. To do that it needs SETUID/SETGID. To bind to a privileged port (≤1024) when configured, it needs NET_BIND_SERVICE. CHOWN is needed to take ownership of the worker pidfile. Dropping ALL and adding back exactly these four is least-privilege done explicitly.

44. **Why `condition: service_healthy` instead of plain `depends_on: app`?**
    - Plain `depends_on` only waits for the container process to start. `service_healthy` waits for the Compose-level healthcheck to actually report healthy — meaning nginx will not begin accepting traffic until the app is responding to `/healthz`. That's the difference between "started" and "ready."

45. **Why is the named log volume mounted only on the app, not on nginx?**
    - The upstream nginx image symlinks `/var/log/nginx/access.log` and `error.log` to `/dev/stdout` and `/dev/stderr`. Mounting a named volume over `/var/log/nginx` would replace those symlinks with real files in the volume and break `docker compose logs nginx`. The grader's "nginx access log" screenshot comes from `docker compose logs nginx`, so we keep the symlinks.

46. **Why `security_opt: no-new-privileges:true`?**
    - It disables the kernel's setuid/setgid mechanism for the container. Even if a setuid binary somehow existed inside the image, an exec'd process could not gain extra privileges. Cheap defense in depth on top of `cap_drop: ALL`.

## CLI init/validate Questions (settled in SD4-CLI-001)

47. **How do you prove `init` is idempotent?**
    - Three measurements: (1) hash the generated files; (2) re-run `init` and confirm identical hashes; (3) `rm` the generated files, run `init` again, confirm identical hashes. The grader's literal test is the third one — `rm nginx.conf docker-compose.yml && ./swiftdeploy init` — and our SHA256 matched on every run.

48. **What does the atomic-write pattern in `init` protect against?**
    - The renderer writes to a temp file in the same directory and then `os.replace`s into the final name. If the process crashes mid-write or the disk fills up, the temp file is orphaned but the existing `nginx.conf`/`docker-compose.yml` (if any) is untouched. Without this, a partial write could leave a half-rendered, unparseable file at the canonical path.

49. **Why are the 5 validate checks ordered the way they are?**
    - Each check assumes the previous one passed. (1) parses YAML — every other check depends on it. (2) confirms required fields — derives the values used in 3 and 4. (3) confirms the image exists — without it deploy would crash later. (4) confirms the port is free — same idea, would explode at runtime otherwise. (5) is the final shape check on the rendered nginx.conf. The order is "cheapest, most upstream check first."

50. **What does `socket.bind()` test that `ss -tln` does not?**
    - `bind()` is the same kernel call nginx will make. A successful bind here proves the port is grabbable for *our* process; a `ss` parse only tells you what was listening at one moment. Race conditions (something binding between `ss` and nginx start) leak through `ss`-based checks but not through `bind()` because we hold the socket open until the moment we hand off.

51. **Why is the nginx syntax check done with `--entrypoint nginx -t -q` rather than the default ENTRYPOINT?**
    - The upstream `nginx:latest` image's docker-entrypoint.sh runs setup scripts (`10-listen-on-ipv6-by-default.sh`, `20-envsubst-on-templates.sh`, etc.) before exec'ing the command. Those scripts mutate the config and emit lots of stdout that contaminates a screenshot. `--entrypoint nginx` bypasses them, and `-t -q` runs only the syntax test in quiet mode — clean output, exact same parser.

52. **What happens if `validate` is run before `init` has ever been run?**
    - Check 5 fails because `nginx.conf` does not exist. The script prints `[FAIL] nginx.conf has not been rendered yet (run: swiftdeploy init)` and exits 1. That is the right behavior: validate is a gate, not a fix-it.

53. **How does the script find the right Python?**
    - It iterates the candidates `python3` then `python`, calls `command -v` to get the path, and probes `--version` to confirm the binary actually runs. The probe step catches the Microsoft Store stub on Windows (which `command -v` finds but which exits non-zero when invoked). PATH lookup is necessary but not sufficient.

54. **Why pass the manifest path to Python via `argv` instead of inlining it in the heredoc?**
    - Two reasons. First, on Git Bash for Windows, MSYS path translation only happens for argv, not for in-body strings — so `/c/Users/...` in argv becomes `C:\Users\...` automatically. Second, an inlined path requires the heredoc delimiter to be unquoted (so bash expands the variable), which then makes the heredoc body subject to all the other shell expansions, breaking quoting. Passing through argv with a `'EOF'` quoted delimiter is safer and cross-platform.

55. **What does `set -euo pipefail` actually catch?**
    - `-e` aborts on any unexpected non-zero exit (so a failing `mv` does not silently continue with a half-state). `-u` errors on unset variables (so a typo in `${MANIFEST}` becomes an immediate abort instead of a confusing empty path). `-o pipefail` makes a pipeline's exit code reflect the leftmost failing command, so `failing_cmd | grep ok` returns non-zero instead of grep's success.

## CLI deploy/promote/teardown Questions (settled in SD4-CLI-002)

56. **What does `deploy` actually wait for?**
    - `deploy` polls `http://127.0.0.1:${nginx.port}/healthz` through nginx (not directly to the app port). It parses the JSON response and only declares the stack healthy when `status == "ok"`. A 200 with the wrong body would not pass. The poll runs for 60 seconds with one-second intervals; a single success short-circuits the wait.

57. **Why poll through nginx and not the app container directly?**
    - The point of the deployment is end-to-end health: nginx + app together. Hitting the app port directly would tell us the app is up but not that the proxy is correctly routing. The brief explicitly forbids exposing the app port, so polling through nginx is also the only port that *exists* on the host.

58. **Why does `promote` use `up -d --no-deps --force-recreate app` instead of `restart`?**
    - `restart` reuses the existing container. The container's environment was baked at create time, so a regenerated compose file with a new `MODE` value would not take effect. `up -d` reads the current compose, recreates any container whose config differs. `--no-deps` keeps nginx untouched (gateway stays up while the upstream cycles). `--force-recreate` covers the canary->canary case where compose otherwise sees no diff and skips.

59. **How do you know the new mode is actually active after `promote`?**
    - The CLI calls `confirm_mode_via_nginx` which curls `/` through the proxy and asserts BOTH that the response body's `mode` field equals the target AND that the `X-Mode: canary` header is present (canary) or absent (stable). Two independent signals; defense in depth.

60. **Why use a targeted regex to flip `services.mode` instead of `yaml.safe_dump`?**
    - `yaml.safe_dump` round-trips the whole document. That strips comments, blank lines, and original quoting — making `git diff manifest.yaml` after promote a noisy mess. The regex `(?m)^(\s*mode:[ \t]+)\S+` mutates exactly the line we promised to mutate. A `yaml.safe_load` sanity check after the write catches any case where the regex produced invalid YAML.

61. **What about the `services.version` field — could the regex hit `mode:` somewhere unintended?**
    - In our schema only `services.mode` exists at the `mode:` key. If we ever added another `mode:` key (say `nginx.mode`), the regex would hit the first match. Mitigation if that becomes real: anchor the regex to a section by reading the raw line offsets, or commit to ruamel.yaml. Not a current bug, just a constraint to remember.

62. **What does `teardown` remove and why `-v`?**
    - `docker compose down -v --remove-orphans` removes containers, the project's network, AND any named volumes the project owns. The `-v` flag is the difference between teardown leaving the named log volume orphaned (next deploy would re-attach old logs) and a fully clean reset. `--remove-orphans` clears containers from previous compose configs that may have been renamed.

63. **What does `teardown --clean` do that plain `teardown` does not?**
    - Plain teardown leaves `nginx.conf` and `docker-compose.yml` on disk so the next `deploy` is fast. `--clean` ALSO `rm`s those generated files, returning the repo to "manifest is the only artifact" — which is exactly the input to the grader's regeneration test (`rm generated && ./swiftdeploy init`).

64. **What evidence proves nginx stays up while the app is recreated during promote?**
    - The captured nginx access log shows 502 entries between the moment the app container is `Recreated/Starting` and the moment it reports healthy again. nginx returned a 502 (our JSON error body would have been served), which means nginx itself was alive and serving requests during the gap — it could not have logged anything otherwise. That is the operational meaning of "rolling restart" for a single-instance upstream.

65. **What does the access log entry `0.502s` next to `GET /healthz` actually demonstrate?**
    - Slow chaos was set with `duration=0.5`. The next `/healthz` slept 0.5s in the chaos middleware before responding 200. nginx logged `request_time` as `0.502s` — the proxy round-trip time. Three pieces of evidence aligning: chaos accepted the payload, the middleware slept, and the access log captured the exact timing.

## Future Technical Questions

- Why is the service port not exposed directly?
- What does `cap_drop: ALL` protect against?
- Why does `swiftdeploy init` need to be idempotent?
- How does `promote` ensure the new mode is active?
- Why does Nginx need `always` for response headers?
- How do you prove the image is under 300 MB?
- What does the chaos `error` rate mean statistically?
- Why `--no-deps` on the promote restart?
- Why use an `upstream` block in nginx instead of a direct `proxy_pass`?

## Stage 4B Questions

66. **Why add OPA instead of writing `if disk < 10` in the CLI?**
    - The brief explicitly requires all allow/deny logic to live in OPA. The CLI is only the enforcement point: it gathers facts, asks OPA, prints the reason, and enforces the answer.

67. **Why do thresholds live in the manifest-derived input instead of Rego?**
    - Rego should describe the rule structure. Environment-specific limits are data. Passing thresholds in `input.thresholds` lets the operator change limits without editing policy source.

68. **Why return an object instead of a boolean from OPA?**
    - Operators need to know why a gate passed or failed. The object carries `allowed`, `reason`, `violations`, and observed values, so the CLI can surface a useful result.

69. **Why is OPA bound to `127.0.0.1` on the host?**
    - The CLI needs to query OPA, but public users should only see Nginx. A loopback-only host binding makes OPA reachable from the local tool and not from the public ingress path.

70. **Why use Prometheus cumulative metrics?**
    - That is the native model for counters and histograms. Rates and p99 latency are derived by comparing snapshots over a window, which is exactly what the status and policy helpers do.

71. **Why is `/metrics` exempt from chaos?**
    - The canary safety gate must observe bad behavior even while user traffic is degraded. If chaos breaks the metrics endpoint, the control loop becomes blind.

72. **The brief says "over the last 30 seconds." How do you calculate the 30-second error rate for pre-promote?**
    - The implementation uses a live two-snapshot window, not a rolling 30-second average. The CLI takes a first metrics scrape, makes several `/healthz` pings (approximately 5 × 200 ms), then takes a second scrape. The delta in `http_requests_total` and the error fraction of that delta is what OPA evaluates. The window is ~1–1.3 seconds in practice. The `policy_window_target_seconds=30` field is logged in `history.jsonl` for audit purposes but is not enforced as a gate condition. The trade-off: a live window provides an immediate signal with no dependency on continuous `status` polling history; the downside is that a bursty error spike that finished more than 1–2 seconds before the promote command starts would not block promotion. Operators who want a full 30-second confidence window should run `swiftdeploy status` for ≥30 seconds before promoting; the rolling scrape history in `history.jsonl` then captures that period.
