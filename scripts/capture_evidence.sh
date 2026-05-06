#!/usr/bin/env bash
# capture_evidence.sh - Run the Stage 4B SwiftDeploy lifecycle and write
# screenshot-ready proof files under blog/assets/proof_outputs/.

set -euo pipefail
export PYTHONUNBUFFERED=1

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null && pwd)"
OUT="${ROOT}/blog/assets/proof_outputs"
mkdir -p "${OUT}"
rm -f "${OUT}"/*.txt

cd "${ROOT}"

manifest_value() {
    python - "$1" <<'PY'
import sys, yaml
m = yaml.safe_load(open("manifest.yaml", "r", encoding="utf-8")) or {}
cur = m
for part in sys.argv[1].split("."):
    cur = (cur or {}).get(part)
print(cur or "")
PY
}

set_disk_threshold() {
    python - "$1" <<'PY'
import re, sys
path = "manifest.yaml"
target = sys.argv[1]
text = open(path, "r", encoding="utf-8").read()
new, n = re.subn(r"(?m)^(\s*min_disk_free_gb:\s*)\S+", lambda m: m.group(1) + target, text, count=1)
if n != 1:
    raise SystemExit("could not update policy.infrastructure.min_disk_free_gb")
open(path, "w", encoding="utf-8", newline="\n").write(new)
PY
}

set_cpu_threshold() {
    python - "$1" <<'PY'
import re, sys
path = "manifest.yaml"
target = sys.argv[1]
text = open(path, "r", encoding="utf-8").read()
new, n = re.subn(r"(?m)^(\s*max_cpu_load:\s*)\S+", lambda m: m.group(1) + target, text, count=1)
if n != 1:
    raise SystemExit("could not update policy.infrastructure.max_cpu_load")
open(path, "w", encoding="utf-8", newline="\n").write(new)
PY
}

HOST_PORT="$(manifest_value nginx.port)"
IMAGE="$(manifest_value services.image)"
OPA_PORT="$(manifest_value opa.port)"

echo "capture_evidence: using nginx.port=${HOST_PORT}, opa.port=${OPA_PORT}, image=${IMAGE}"

./swiftdeploy teardown --clean >/dev/null 2>&1 || true
rm -f history.jsonl audit_report.md

{
    echo "$ docker build -t ${IMAGE} ."
    docker build -t "${IMAGE}" .
    echo
    echo "$ ./swiftdeploy init"
    ./swiftdeploy init
    echo
    echo "$ ./swiftdeploy validate"
    ./swiftdeploy validate
} > "${OUT}/01_validate.txt" 2>&1
echo "wrote ${OUT}/01_validate.txt"

{
    echo "$ set policy.infrastructure.min_disk_free_gb to 1000000"
    set_disk_threshold 1000000
    echo "$ ./swiftdeploy deploy    # expect policy denial before app/nginx start"
    ./swiftdeploy deploy || echo "expected deploy denial exit=$?"
    echo
    echo "$ restore policy.infrastructure.min_disk_free_gb to 10"
    set_disk_threshold 10
} > "${OUT}/02_predeploy_policy_denial.txt" 2>&1
echo "wrote ${OUT}/02_predeploy_policy_denial.txt"

{
    echo "$ ./swiftdeploy deploy"
    ./swiftdeploy deploy
    echo
    echo "$ curl -i http://127.0.0.1:${HOST_PORT}/metrics"
    curl -i -s "http://127.0.0.1:${HOST_PORT}/metrics" | sed -n '1,80p'
} > "${OUT}/03_deploy_and_metrics.txt" 2>&1
echo "wrote ${OUT}/03_deploy_and_metrics.txt"

{
    echo "$ ./swiftdeploy status --once"
    ./swiftdeploy status --once
    echo
    echo "$ tail -n 3 history.jsonl"
    tail -n 3 history.jsonl
} > "${OUT}/04_status_history.txt" 2>&1
echo "wrote ${OUT}/04_status_history.txt"

{
    echo "$ ./swiftdeploy promote canary"
    ./swiftdeploy promote canary
    echo
    echo "$ curl -i http://127.0.0.1:${HOST_PORT}/healthz"
    curl -i -s "http://127.0.0.1:${HOST_PORT}/healthz"
} > "${OUT}/05_promote_canary.txt" 2>&1
echo "wrote ${OUT}/05_promote_canary.txt"

{
    echo "$ curl -X POST /chaos error rate=1.0"
    curl -i -s -X POST -H "Content-Type: application/json" \
        -d '{"mode":"error","rate":1.0}' "http://127.0.0.1:${HOST_PORT}/chaos"
    echo
    echo "$ ./swiftdeploy promote stable    # expect canary safety denial"
    ./swiftdeploy promote stable || echo "expected promote denial exit=$?"
    echo
    echo "$ curl -X POST /chaos recover"
    curl -i -s -X POST -H "Content-Type: application/json" \
        -d '{"mode":"recover"}' "http://127.0.0.1:${HOST_PORT}/chaos"
} > "${OUT}/06_promote_denied_under_chaos.txt" 2>&1
echo "wrote ${OUT}/06_promote_denied_under_chaos.txt"

{
    echo "$ ./swiftdeploy promote stable"
    ./swiftdeploy promote stable
    echo
    echo "$ curl -i http://127.0.0.1:${HOST_PORT}/"
    curl -i -s "http://127.0.0.1:${HOST_PORT}/"
} > "${OUT}/07_promote_stable.txt" 2>&1
echo "wrote ${OUT}/07_promote_stable.txt"

{
    echo "$ docker compose -f docker-compose.yml logs nginx --tail=30"
    docker compose -f docker-compose.yml logs nginx --tail=30
} > "${OUT}/13_nginx_access_log.txt" 2>&1
echo "wrote ${OUT}/13_nginx_access_log.txt"

{
    echo "$ curl http://127.0.0.1:${OPA_PORT}/health    # local CLI path"
    curl -i -s "http://127.0.0.1:${OPA_PORT}/health"
    echo
    echo "$ curl http://127.0.0.1:${HOST_PORT}/v1/data    # public nginx path must not expose OPA"
    curl -i -s "http://127.0.0.1:${HOST_PORT}/v1/data"
} > "${OUT}/08_opa_no_leakage.txt" 2>&1
echo "wrote ${OUT}/08_opa_no_leakage.txt"

{
    echo "$ ./swiftdeploy audit"
    ./swiftdeploy audit
    echo
    echo "$ cat audit_report.md"
    cat audit_report.md
} > "${OUT}/09_audit_report.txt" 2>&1
echo "wrote ${OUT}/09_audit_report.txt"

{
    echo "$ cat manifest.yaml"
    cat manifest.yaml
    echo
    echo "$ sha256sum nginx.conf docker-compose.yml"
    sha256sum nginx.conf docker-compose.yml
    echo
    echo "$ cat docker-compose.yml"
    cat docker-compose.yml
    echo
    echo "$ cat nginx.conf"
    cat nginx.conf
} > "${OUT}/10_generated_configs.txt" 2>&1
echo "wrote ${OUT}/10_generated_configs.txt"

{
    echo "$ ./swiftdeploy teardown --clean"
    ./swiftdeploy teardown --clean
    echo
    echo "$ ./swiftdeploy init"
    ./swiftdeploy init
    echo
    echo "$ ls nginx.conf docker-compose.yml history.jsonl audit_report.md"
    ls nginx.conf docker-compose.yml history.jsonl audit_report.md
} > "${OUT}/11_teardown_and_regen.txt" 2>&1
echo "wrote ${OUT}/11_teardown_and_regen.txt"

{
    # On Windows, os.getloadavg() is unavailable so cpu_load is always 0.0.
    # Set max_cpu_load to -1.0 so that 0.0 > -1.0 fires the CPU denial rule.
    # On Linux a threshold of 0.0 is sufficient; -1.0 is the cross-platform proof value.
    echo "$ set policy.infrastructure.max_cpu_load to -1.0 (forces denial: cpu_load=0.0 > -1.0)"
    set_cpu_threshold -1.0
    echo "$ ./swiftdeploy deploy   # expect CPU policy denial"
    ./swiftdeploy deploy || echo "expected cpu denial exit=$?"
    echo
    echo "$ restore policy.infrastructure.max_cpu_load to 2.0"
    set_cpu_threshold 2.0
} > "${OUT}/12_cpu_policy_denial.txt" 2>&1
echo "wrote ${OUT}/12_cpu_policy_denial.txt"

echo
echo "Capture complete. Files in ${OUT}:"
ls -1 "${OUT}"
