# SwiftDeploy Stage 4B — Grading-Prep Audit Report

_Reviewed: 2026-05-06 by Claude Code (senior DevOps reviewer)_

---

## 1. Findings by Severity

---

### CRITICAL — F-001: Core Stage 4B implementation is NOT committed to git

**Requirement:** Submission repo must contain all implementation files.

**Files affected:** `swiftdeploy_lib/` (entire Python library), `policies/` (both Rego files), plus every Stage 4B proof file (02–11), `audit_report.md`, `history.jsonl`, `blog/devto/swiftdeploy-stage4b.md`, `blog/diagrams/stage4b_architecture.md`, `blog/diagrams/policy_gate_flow.md`.

**What is wrong:**

```
?? swiftdeploy_lib/          ← entire Python CLI library
?? policies/                 ← both Rego policies
?? audit_report.md
?? history.jsonl
?? blog/devto/swiftdeploy-stage4b.md
?? blog/assets/proof_outputs/02-11_*.txt
```

`git ls-files swiftdeploy_lib policies` returns nothing — these directories have never been staged. The committed `swiftdeploy` script still contains the Stage 4A bash-only implementation (`# manifest-driven CLI for the Stage 4A stack`). If the operator pushes right now, the grader receives a repo with no OPA policies, no Python library, no status/audit commands, and no proof.

**Why it matters:** This is a show-stopper. Every Stage 4B feature evaporates on push.

**Fix:** `git add swiftdeploy swiftdeploy_lib/ policies/ manifest.yaml templates/ docker-compose.yml nginx.conf audit_report.md history.jsonl blog/ docs/ scripts/ config/ app/ Dockerfile && git commit -m "Stage 4B SwiftDeploy submission"`

---

### CRITICAL — F-002: Blog article not published; `published: false` front-matter in draft

**Requirement:** "You must publish a technical deep dive (Dev.to, Hashnode, or Medium)."

**File:** `blog/devto/swiftdeploy-stage4b.md` line 2.

**What is wrong:** `published: false` is set and the article is also an untracked file (see F-001). No published URL exists. The submission form asks for a blog link; the link field would be empty.

**Why it matters:** The brief lists a published blog post as a named submission criterion alongside the repo link. Missing it is a certain partial-mark at best, full deduction at worst.

**Fix:** Publish before the deadline (manual operator step). The article body itself is also thin (see F-007).

---

### CRITICAL — F-003: Pre-promote canary window is ~1 second, not 30 seconds

**Requirement:** "Scrape `/metrics`, calculate Error Rate and P99 Latency... over the last 30 seconds."

**File:** `swiftdeploy_lib/cli.py` lines 244–257 (`collect_metrics_summary`).

**What is wrong:** The function takes two scrapes separated by `5 × (time.sleep(0.2) + healthz RTT)` ≈ 1–1.3 seconds. The history records confirm this:

```
promote canary  window=1.276s  policy_window_target_seconds=30
promote stable  window=1.095s  policy_window_target_seconds=30
```

The `policy_window_target_seconds` field is stored in history for logging but is **never sent to OPA** and never enforced. OPA decides purely on error_rate and p99 regardless of window size.

**Why it matters:** A grader who reads the brief ("last 30 seconds") and then checks the history records will see 1.1 s windows and ask "where is the 30-second measurement?" The brief is explicit. There is no policy check that rejects a window that is too small.

**Suggested fix:** Either replace the two-scrape approach with a rolling window from `history.jsonl` using `metrics.load_recent_history(window_seconds=30)` and aggregate those records for the policy input, **or** document in the README and blog that the implementation intentionally uses a live two-scrape window and justify why. The current silent mismatch is the risk; either fix or defend it explicitly.

---

### HIGH — F-004: CPU load is always `0.0` on this dev machine (Windows)

**Requirement:** "pre-deploy: Send host stats (Disk, CPU, Mem) to OPA."

**File:** `swiftdeploy_lib/policy.py` lines 31–38.

**What is wrong:** `os.getloadavg()` raises `AttributeError` on Windows. The code catches it and silently returns `cpu_load = 0.0`. Verified: `Platform: Windows — getloadavg() unavailable: module 'os' has no attribute 'getloadavg'`. Every `pre_deploy` record in `history.jsonl` shows `"cpu_load": 0.0`. The CPU policy check never actually fires on this machine.

**Why it matters:** If the grader runs on Linux the CPU check works correctly. But no proof of CPU policy denial exists. An interviewer asking "show me a CPU policy denial" finds nothing.

**Suggested fix:** Add a proof capture that overrides `max_cpu_load: 0.0` in the manifest, runs deploy, captures the CPU denial, then restores. Record as a new proof file `12_cpu_policy_denial.txt`.

---

### HIGH — F-005: `06_nginx_access_log.txt` deleted; no nginx log proof in Stage 4B bundle

**Requirement (Stage 4A persisting):** Access logs in format `$time_iso8601 | $status | ${request_time}s | $upstream_addr | $request`.

**Files:** Stage 4B deleted `blog/assets/proof_outputs/06_nginx_access_log.txt` (git status `D`). No Stage 4B file replaces it.

**What is wrong:** The entire Stage 4B proof bundle has 11 files but none show nginx access log output in the mandated format. The original Stage 4A proof of the log format no longer exists in the repo.

**Why it matters:** Stage 4A requirements still apply. A grader checking "access logs in required format" finds no proof anywhere in the submission.

**Suggested fix:** Add a 12th or 13th proof file that captures `docker compose logs nginx --tail=20`. Even a quick capture showing `2026-05-06T... | 200 | 0.002s | ...` satisfies this.

---

### HIGH — F-006: Proof output files exhibit reversed stdout ordering (Python buffering vs subprocess)

**Requirement:** Proof outputs must be legible to a grader as a correct sequence of events.

**File:** `blog/assets/proof_outputs/02_predeploy_policy_denial.txt`.

**What is wrong:** The file starts with Docker container events, then shows `[FAIL] deploy blocked by policy`, then shows `swiftdeploy deploy: rendering and starting policy sidecar` — which is the CLI banner that should appear first. Python's `print()` is block-buffered when redirected to a file; Docker's subprocess output is unbuffered and reaches the file first.

**Why it matters:** A grader reading this for the first time may conclude the output is fabricated or that the tool behaves incorrectly.

**Suggested fix:** Add `export PYTHONUNBUFFERED=1` at the top of `capture_evidence.sh` and re-run. This flushes Python stdout after every print, aligning it with Docker output. Re-capture all 11 proof files.

---

### HIGH — F-007: Blog article is too thin for "a reader should be able to replicate"

**Requirement:** "A reader should be able to replicate your work."

**File:** `blog/devto/swiftdeploy-stage4b.md`.

**What is wrong:** The article is 62 lines total with no code blocks, no embedded diagrams, no reproduction steps, no screenshots, and a 3-sentence "Lessons Learned" section. The chaos section describes events without showing terminal output.

**Why it matters:** The grader will click the blog link. "Explain how you built a tool that writes its own infrastructure files" and "Document what happened when you injected a slow or error state" are explicit blog criteria.

**Suggested fix:** Expand with: inline Mermaid architecture diagram, one Rego snippet showing thresholds from `input.thresholds`, one terminal block showing the chaos promotion denial output, reproduction steps.

---

### MEDIUM — F-008: OPA "no leakage" proof relies on app 404, not nginx block

**Requirement:** "The OPA API must not be accessible via the Nginx port."

**File:** `blog/assets/proof_outputs/08_opa_no_leakage.txt`.

**What is wrong:** `GET http://127.0.0.1:18080/v1/data` returns `{"detail":"Not Found"}` — a FastAPI 404, not an nginx-level block. The isolation holds because nginx has no upstream for OPA and OPA is port-forwarded to `127.0.0.1` only. Neither fact is demonstrated by the current proof.

**Suggested fix:** Add `curl http://0.0.0.0:18181/health` → should fail (OPA not on 0.0.0.0), and explain in the proof header that nginx has no OPA upstream, so the route never reaches the internal Docker network address.

---

### MEDIUM — F-009: `status` shows `window=0.0s` and confusing `req/s` on first call

**File:** `swiftdeploy_lib/cli.py` line 405, `swiftdeploy_lib/metrics.py` lines 126–157.

**What is wrong:** When `previous` is `None` (first call), elapsed=0, and `req_per_second = total_requests` (a raw count, not a rate). Proof shows `req/s=2.000 window=0.0s` — "2.000" means "2 total requests seen", not 2 per second.

**Suggested fix:** Display `req/s=N/A (no baseline)` on first call, or document the semantics clearly.

---

### MEDIUM — F-010: Variable shadowing in `prometheus_metrics` (latent correctness risk)

**File:** `app/main.py` lines 165–179.

**What is wrong:** The outer loop variable `count` is shadowed by the inner `for bucket, count in zip(...)` loop. An explicit re-assign after the inner loop restores the correct value. The code is currently correct but fragile.

**Suggested fix:** Rename the inner loop variable to `bucket_val`.

---

### MEDIUM — F-011: Dockerfile CMD hardcodes port 3000; does not honour `APP_PORT`

**File:** `Dockerfile` line 27.

**What is wrong:** `CMD [..., "--port", "3000"]`. Uvicorn ignores `APP_PORT`. The healthcheck uses `os.environ['APP_PORT']`. Changing `services.port` in manifest.yaml would break the stack silently.

**Suggested fix:** `CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port ${APP_PORT:-3000}"]`

---

### LOW — F-012: Image tag `1.0.0` vs app version `1.1.0` in manifest

**File:** `manifest.yaml` lines 6 and 9. Image tag `1.0.0`, `APP_VERSION` injected as `1.1.0`. Inconsistent; no documented reason.

---

### LOW — F-013: `task_details_4B.md` excluded via `.gitignore`

Intentional per HNG policy, but worth noting for awareness.

---

### LOW — F-014: `status_code = 500` dead initialization in `metrics_middleware`

**File:** `app/main.py` line 94. The value is unconditionally overwritten before use. Minor readability issue.

---

### LOW — F-015: No pip install instructions for `swiftdeploy_lib` dependencies

README lists `pyyaml` as a prerequisite but shows no install command.

---

## 2. Missing or Weak Evidence

| Claim | Evidence Available | Status |
|---|---|---|
| OPA blocks deploy on low disk | `02_predeploy_policy_denial.txt` | OK |
| OPA blocks promote on high error rate | `06_promote_denied_under_chaos.txt` | OK |
| CPU policy check works | No capture | **Missing** |
| OPA not accessible via nginx (network-level) | App 404 only | Weak |
| Nginx access log in mandated format | No file in Stage 4B bundle | **Missing** |
| Pre-promote uses 30-second window | History shows 1.1 s actual | **Contradicted** |
| `audit_report.md` renders as GFM | Present in repo | OK |
| Blog post published with architecture diagram | Not published | **Missing** |
| `/metrics` in Prometheus text format | `03_deploy_and_metrics.txt` | OK |

---

## 3. Stage 4A Regression Risks

| Requirement | Risk | Detail |
|---|---|---|
| nginx access log format | **High** | `06_nginx_access_log.txt` deleted, not replaced |
| Init idempotency SHA proof | Low | Stage 4A SHAs are stale (image renamed) |
| App image under 300 MB | Low | E-004 measured old image name |

---

## 4. Interview-Defense Questions the Operator May Fail

**Q1:** "The brief says 30 seconds. Show me where that window is enforced in code."
→ History records show 1.1 s. Operator must pre-prepare a documented defence.

**Q2:** "Show me the CPU policy blocking a deploy."
→ All proof shows `cpu_load: 0.0` (Windows fallback). No denial evidence exists.

**Q3:** "How does OPA get the threshold values?"
→ `input.thresholds` from `policy_config()` in `config.py` → `manifest.yaml`. Well-implemented, defensible.

**Q4:** "What are the distinct failure modes if OPA is unavailable?"
→ `opa_timeout`, `opa_unavailable`, `opa_policy_error`, `opa_malformed_response`, `opa_unhealthy`. Well-implemented, defensible.

**Q5:** "What happens to the stack if the app container crashes after deploy?"
→ `restart: unless-stopped` recovers it. Nginx may serve 502s briefly; JSON error body handler covers it. Defensible.

**Q6:** "If a grader deletes nginx.conf and docker-compose.yml and runs `swiftdeploy init`, do they get byte-identical files?"
→ Yes — `string.Template.safe_substitute` on static templates with static manifest is deterministic. Defensible.

**Q7:** "Show me the live status dashboard refreshing."
→ Proof only captures `--once`. Infinite loop mode not demonstrated.

**Q8:** "Why does status show `window=0.0s` with `req/s=2.000` on the first call?"
→ First-call edge case: no baseline snapshot. `req/s` is raw count, not rate. Must explain clearly.

---

## 5. Final Verdict

**NOT READY — Critical blockers before submission**

### Top 5 Actions Before Submission

| Priority | Action | Effort |
|---|---|---|
| 1 | **Stage and commit all Stage 4B files** (F-001) | 5 min |
| 2 | **Add `PYTHONUNBUFFERED=1` to capture script and re-run** (F-006) | 10 min |
| 3 | **Add CPU denial proof + nginx access log to bundle** (F-004, F-005) | 20 min |
| 4 | **Expand blog article** with diagram, Rego snippet, chaos terminal output, reproduction steps (F-007) | 60–90 min |
| 5 | **Publish blog and push repo** before 2026-05-08 11:59 WAT (F-002, F-001) | 15 min operator |

### Findings Summary

| ID | Severity | One-Line Description |
|---|---|---|
| F-001 | CRITICAL | swiftdeploy_lib/, policies/, proof files never committed |
| F-002 | CRITICAL | Blog article unpublished and untracked |
| F-003 | CRITICAL | Pre-promote window is ~1 s not 30 s |
| F-004 | HIGH | CPU load always 0 on Windows; no CPU denial proof |
| F-005 | HIGH | Nginx access log proof deleted from bundle |
| F-006 | HIGH | Proof output order scrambled by Python buffering |
| F-007 | HIGH | Blog article too thin to satisfy replication requirement |
| F-008 | MEDIUM | OPA isolation proof shows app 404, not nginx block |
| F-009 | MEDIUM | First-call status shows count as req/s with window=0 |
| F-010 | MEDIUM | Variable shadowing in prometheus_metrics (latent) |
| F-011 | MEDIUM | Dockerfile CMD ignores APP_PORT |
| F-012 | LOW | Image tag 1.0.0 vs APP_VERSION 1.1.0 inconsistency |
| F-013 | LOW | task_details_4B.md in .gitignore (intentional) |
| F-014 | LOW | Dead status_code=500 init in metrics_middleware |
| F-015 | LOW | No pip install command in README |
