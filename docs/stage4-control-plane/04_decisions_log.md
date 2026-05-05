# Decisions Log

## D-001 - Use a governed control plane before implementation

- Date: `2026-05-03`
- Decision: Create governance docs, task packets, evidence tracking, QA gates, and a checker before creating SwiftDeploy implementation files.
- Rationale: Stage 3 and Stage 4 feedback explicitly warn that work must be explainable without AI.
- Interview defense: "I separated planning/proof control from implementation so every later code slice has a documented reason, test, and defense path."

## D-002 - Keep implementation blocked until design closes

- Date: `2026-05-03`
- Decision: Set `implementation_allowed` to `false` until `SD4-DESIGN-001` settles stack choices and template strategy.
- Rationale: The official brief leaves several choices open, and premature coding would turn assumptions into hidden risk.
- Interview defense: "I treated design decisions as first-class DevOps work because deployment tools fail when hidden assumptions meet a grader environment."

## D-003 - Draft the dev.to article in-repo, publish manually

- Date: `2026-05-03`
- Decision: Maintain `blog/devto/swiftdeploy-stage4.md` and diagram assets in the repo; publish manually after final verification.
- Rationale: The blog should not make claims before the evidence exists, and manual publishing avoids adding API-key handling to the task.
- Interview defense: "The article is tied to the same evidence trail as the README, so it cannot drift into unsupported storytelling."

## D-004 - API stack is Python 3.11 + FastAPI + uvicorn

- Date: `2026-05-03`
- Decision: The HTTP service is built with FastAPI on uvicorn, packaged on `python:3.11-slim`.
- Alternatives considered:
  - Go (net/http or chi). Rejected: switching languages mid-stage adds defense surface; the brief allows either, so the deciding factor was operator confidence under interview pressure.
  - Flask. Rejected: synchronous WSGI; the chaos `slow` mode requires non-blocking sleep, which Flask only supports via thread workers or gevent.
- Rationale:
  - `asyncio.sleep(N)` inside an async FastAPI handler is the natural primitive for the chaos `slow` mode without stalling other workers.
  - Pydantic-driven request models give automatic JSON validation for `/chaos` body shapes.
  - `python:3.11-slim` is roughly 150 MB; FastAPI + uvicorn add roughly 30 MB on top, leaving headroom under the 300 MB image ceiling.
- Interview defense: "FastAPI maps the chaos `slow` mode onto `asyncio.sleep`, which keeps the event loop free for other requests. With a sync framework I would have needed thread workers, which is more code to defend for the same behavior."

## D-005 - CLI stack is Bash with embedded Python helpers

- Date: `2026-05-03`
- Decision: `swiftdeploy` is a Bash script. All non-trivial logic (YAML parse, YAML mutation, template render, port-bind probe) is delegated to short Python heredocs invoked from Bash.
- Alternatives considered:
  - Pure Python CLI (Click/Typer). Rejected: adds a packaged dependency; the script must be runnable from the project root without an install step.
  - Pure Bash with `yq`/`sed`. Rejected: `yq` is not universally installed; `sed` is fragile when manifest values contain `:` or `/` (every Docker image string does).
- Rationale:
  - The CLI orchestrates external tools (`docker compose`, `nginx -t`, `curl`). Bash maps cleanly onto that.
  - Python does the data work where Bash is weakest: YAML, JSON, sockets, string templating.
  - `set -euo pipefail` gives explicit, defensible failure semantics.
- Interview defense: "I split the CLI into orchestration (Bash) and computation (Python). Bash starts processes and propagates exit codes; Python handles structured data. Each half is easy to read and easy to defend in isolation."

## D-006 - Python interpreter resolution at CLI start

- Date: `2026-05-03`
- Decision: The CLI resolves the Python binary as `command -v python3 || command -v python` and aborts with a clear message if neither is present.
- Rationale: Linux graders typically expose `python3`; some Windows installs only expose `python`. Hardcoding either fails on the other environment.
- Interview defense: "I do not assume `python3` exists; I detect it. The CLI fails fast with a single actionable error if no interpreter is found, rather than producing confusing downstream errors."

## D-007 - YAML parsing uses pyyaml as a documented host prerequisite

- Date: `2026-05-03`
- Decision: The CLI uses `python3 -c 'import yaml; ...'` for all manifest reads and writes. README declares pyyaml as a prerequisite (`pip install pyyaml` or `apt install python3-yaml`).
- Alternatives considered:
  - Stdlib-only hand parser. Rejected: silently fails on whitespace and quoting edge cases. The grader could break our tool simply by adding indentation.
  - Vendored micro-YAML library. Rejected: extra surface area to defend with no functional gain.
- Rationale: The Python stdlib has no YAML parser. pyyaml is the de-facto standard, present in most distro python packages, and trivial to install.
- Interview defense: "I picked the smallest defensible dependency. pyyaml is the standard; a hand parser would silently mishandle valid YAML the grader writes."

## D-008 - Template rendering uses stdlib `string.Template`

- Date: `2026-05-03`
- Decision: Templates use `${VAR}` placeholders. Rendering goes through `string.Template(...).safe_substitute(context)` inside a Python helper.
- Alternatives considered:
  - `sed`. Rejected: must escape `:` and `/` from image strings on every replacement; one missed escape is a silent bug.
  - `envsubst`. Rejected: not universally installed; cannot do conditionals (we don't need them, but the absence is still a portability risk).
  - Jinja2. Rejected: third-party dependency for features we don't use.
- Rationale: We have zero conditional rendering needs. Every field has a default applied during parse, so placeholders always resolve. Stdlib only.
- Interview defense: "There is no logic in the templates. Stdlib `string.Template` is exactly the right shape; anything heavier would be over-engineering."

## D-009 - Manifest extension policy

- Date: `2026-05-03`
- Decision: The base required fields (`services.image`, `services.port`, `nginx.image`, `nginx.port`, `network.name`, `network.driver_type`) are unchanged. The CLI accepts these additional optional fields, each with a default applied during parse so a brief-only manifest still renders correctly:
  - `services.mode` (default `stable`)
  - `services.version` (default `1.0.0`)
  - `services.restart_policy` (default `unless-stopped`)
  - `services.log_volume` (default `swiftdeploy-logs`)
  - `nginx.proxy_timeout` (default `30`)
  - `nginx.error_contact` (default `ops@swiftdeploy.local`)
- Rationale: Every value referenced by a template must be derivable from the manifest, otherwise the manifest is not the single source of truth. Defaults guarantee a base-spec manifest still works without forcing operators to learn new fields.
- Interview defense: "I extended the manifest only with fields that templates actually consume. Each extension has a default, so a manifest with only the brief's required keys still renders without surprises."

## D-010 - Container healthcheck uses stdlib urllib, not curl

- Date: `2026-05-03`
- Decision: The Compose healthcheck runs `python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:${APP_PORT}/healthz').status==200 else 1)"`.
- Alternatives considered:
  - `curl --fail`. Rejected: requires `apt-get install curl` in the image (around 5 MB plus an extra layer) for one HTTP probe.
  - `wget`. Rejected: same install cost as curl.
- Rationale: The Python interpreter is already in the image. Reusing it removes a dependency and an image layer.
- Interview defense: "`curl` is not in the slim Python image. Installing it just to probe one endpoint trades image size for nothing the stdlib cannot already do."

## D-011 - Stable vs canary `/chaos` semantics

- Date: `2026-05-03`
- Decision: The `/chaos` route is always registered. In `MODE=stable` the handler returns HTTP 403 with `{"error": "chaos disabled in stable mode"}` and never mutates state. In `MODE=canary` the handler accepts `slow`, `error`, and `recover` payloads and mutates the in-memory chaos state. The `X-Mode: canary` header is added by an HTTP middleware that runs before any handler, so it appears on every response (including 4xx and 5xx) when MODE is canary.
- Alternatives considered:
  - Return 404 in stable mode. Rejected: ambiguous — a 404 cannot be distinguished from a typo'd path.
  - Conditionally register the route only in canary. Rejected: route topology should not change between modes; behavior should.
- Rationale: An explicit 403 documents the policy in the response itself. Middleware on the X-Mode header guarantees the header attaches to error responses too, which is what "every response" requires.
- Interview defense: "Stable mode returns 403, not 404, because the policy is `chaos is disabled`, not `the endpoint does not exist`. The middleware approach for X-Mode covers error paths too — handler-level injection would miss them."

## D-012 - Port pre-flight uses pure Python `socket.bind()`

- Date: `2026-05-03`
- Decision: Validate-step check 4 ("Nginx port is not already bound") opens a socket, sets `SO_REUSEADDR=0`, attempts `bind(('0.0.0.0', port))`, treats `OSError` as bound. Stdlib only.
- Alternatives considered:
  - `ss -tlnp`. Rejected: not present on Git Bash for Windows nor on minimal Linux containers without iproute2.
  - `lsof -i :PORT`. Rejected: same portability problem; not present on this dev shell.
  - `nc -z`. Rejected: not present in the dev shell, and only detects listening sockets — does not catch IPv4/IPv6 dual-bind cases cleanly.
- Rationale: The Python socket API is the same on every platform that runs Python. `bind()` failure is the single, authoritative signal that the port is unavailable for our use.
- Interview defense: "I check the port the same way the kernel will when nginx tries to start. If `bind` fails for me, it will fail for nginx — that is a stronger signal than parsing `ss` output."

## D-013 - Nginx syntax check via containerized `nginx -t`

- Date: `2026-05-03`
- Decision: Validate-step check 5 runs `docker run --rm -v "$PWD/nginx.conf:/etc/nginx/conf.d/default.conf:ro" nginx:latest nginx -t`.
- Alternatives considered:
  - Host-installed nginx. Rejected: not guaranteed on the grader.
  - String regex on the rendered file. Rejected: cannot catch directive ordering or context errors.
- Rationale: We test the same nginx image we ship. Same modules, same compile flags, same defaults.
- Interview defense: "The validator uses the same nginx binary that will serve traffic. A host nginx might be a different version or compiled differently, which would make the validator a liar."

## D-015 - Unique image tag and non-default nginx port (post-build clarification)

- Date: `2026-05-04`
- Trigger: Grading-team channel advice clarified that the brief's example
  `swift-deploy-1-node:latest` and `nginx.port: 8080` were illustrative; image
  names should be unique per submission, and the host port can be anything.
- Decision:
  - Service image: `swiftdeploy-stage4a-app:1.0.0`
  - Nginx host port: `18080`
- Alternatives considered:
  - Image: keep `swift-deploy-1-node:latest`. Rejected: matches everyone else's
    submission and fights the grader's stated request for uniqueness.
  - Image: include the operator's email handle (e.g. `odumosumatthew9-...`).
    Rejected: leaks personal-ish info into a registry tag for no compliance benefit.
  - Port: keep 8080. Rejected: 8080 is the most-collided port on shared CI hosts
    and on this dev box (Apache holds it). 18080 is much less likely to clash.
- Rationale:
  - `swiftdeploy-stage4a-app:1.0.0` is descriptive (project + stage + role) and
    uses semver instead of `:latest`, which makes future rebuilds tellable apart.
  - 18080 is high enough to avoid common dev-box collisions and matches the port
    we already used during the live capture in E-007, so the proof bundle and
    the manifest now agree byte-for-byte.
- Interview defense: "The grader explicitly asked for a unique image and any port.
  I picked a name that ties to project + stage and a port that is unlikely to
  clash on shared hosts. The same script works regardless — these values are
  pure manifest data, not code."

## D-014 - Documented portability constraints

- Date: `2026-05-03`
- Decision: Document the assumed grader environment in README and enforce it from the CLI:
  - Bash 4+
  - Docker 20+ with Compose v2 plugin (`docker compose`, never `docker-compose`)
  - Python 3.8+ with pyyaml installed
  - `swiftdeploy` script committed with LF line endings (enforced via `.gitattributes`)
- Rationale: A tool that "works on my machine" but breaks for the grader is a failed deployment tool by definition.
- Interview defense: "I declared the runtime contract up front and enforced it where I could. Anything outside that contract is the operator's responsibility, but anything inside it is ours."

