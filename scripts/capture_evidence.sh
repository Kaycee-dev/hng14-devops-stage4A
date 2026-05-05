#!/usr/bin/env bash
# capture_evidence.sh - Run the full SwiftDeploy lifecycle and tee each
# stage's output to a file the operator can open in a terminal and screenshot
# for the Google Drive submission.
#
# Output goes to blog/assets/proof_outputs/.
#
# Pre-requisites:
#   - Docker 20+ with Compose v2 plugin
#   - bash 4+, curl, python3 (or python) with pyyaml
#   - The image declared in manifest.yaml must be built locally
#     (default: docker build -t swiftdeploy-stage4a-app:1.0.0 .)
#   - The host port declared in manifest.yaml (default 18080) must be free
#
# This script is idempotent: it tears down the running stack before and
# after the capture so reruns produce a clean evidence bundle.

set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." >/dev/null && pwd)"
OUT="${ROOT}/blog/assets/proof_outputs"
mkdir -p "${OUT}"

cd "${ROOT}"

# Read the host port from the manifest so the curls below use the right number.
HOST_PORT="$(./swiftdeploy 2>/dev/null >/dev/null; \
    python -c '
import yaml
m=yaml.safe_load(open("manifest.yaml","r",encoding="utf-8")) or {}
print((m.get("nginx") or {}).get("port",""))
')"
if [[ -z "${HOST_PORT}" ]]; then
    echo "capture_evidence: cannot read nginx.port from manifest.yaml" >&2
    exit 1
fi
echo "capture_evidence: using nginx.port=${HOST_PORT} from manifest"

# Make sure no leftover stack is around.
./swiftdeploy teardown --clean >/dev/null 2>&1 || true

#------------------------------------------------------------------------------
# 1. validate (expect 5/5 PASS).
#------------------------------------------------------------------------------
./swiftdeploy init >/dev/null
{
    echo "$ ./swiftdeploy validate"
    ./swiftdeploy validate
} > "${OUT}/01_validate.txt" 2>&1
echo "wrote ${OUT}/01_validate.txt"

#------------------------------------------------------------------------------
# 2. deploy (output, then curl evidence through nginx).
#------------------------------------------------------------------------------
{
    echo "$ ./swiftdeploy deploy"
    ./swiftdeploy deploy
    echo
    echo "$ curl -i http://127.0.0.1:${HOST_PORT}/"
    curl -i -s "http://127.0.0.1:${HOST_PORT}/"
    echo
    echo
    echo "$ curl -i http://127.0.0.1:${HOST_PORT}/healthz"
    curl -i -s "http://127.0.0.1:${HOST_PORT}/healthz"
    echo
} > "${OUT}/02_deploy.txt" 2>&1
echo "wrote ${OUT}/02_deploy.txt"

#------------------------------------------------------------------------------
# 3. promote canary + curl + slow-chaos timing.
#------------------------------------------------------------------------------
{
    echo "$ ./swiftdeploy promote canary"
    ./swiftdeploy promote canary
    echo
    echo "$ curl -i http://127.0.0.1:${HOST_PORT}/    # expect X-Mode: canary"
    curl -i -s "http://127.0.0.1:${HOST_PORT}/"
    echo
    echo
    echo "$ curl -i http://127.0.0.1:${HOST_PORT}/healthz    # expect X-Mode: canary"
    curl -i -s "http://127.0.0.1:${HOST_PORT}/healthz"
    echo
    echo
    echo "$ curl -i -X POST -H 'Content-Type: application/json' -d '{\"mode\":\"slow\",\"duration\":0.5}' http://127.0.0.1:${HOST_PORT}/chaos"
    curl -i -s -X POST -H "Content-Type: application/json" -d '{"mode":"slow","duration":0.5}' "http://127.0.0.1:${HOST_PORT}/chaos"
    echo
    echo
    echo "$ time curl -s http://127.0.0.1:${HOST_PORT}/healthz    # expect ~0.5s under slow chaos"
    (time curl -s "http://127.0.0.1:${HOST_PORT}/healthz") 2>&1
    echo
    echo "$ curl -i -X POST -d '{\"mode\":\"recover\"}' http://127.0.0.1:${HOST_PORT}/chaos"
    curl -i -s -X POST -H "Content-Type: application/json" -d '{"mode":"recover"}' "http://127.0.0.1:${HOST_PORT}/chaos"
    echo
} > "${OUT}/03_promote_canary.txt" 2>&1
echo "wrote ${OUT}/03_promote_canary.txt"

#------------------------------------------------------------------------------
# 4. promote stable + curl confirmation (no X-Mode).
#------------------------------------------------------------------------------
{
    echo "$ ./swiftdeploy promote stable"
    ./swiftdeploy promote stable
    echo
    echo "$ curl -i http://127.0.0.1:${HOST_PORT}/    # expect NO X-Mode header"
    curl -i -s "http://127.0.0.1:${HOST_PORT}/"
    echo
    echo
    echo "$ curl -i -X POST -d '{\"mode\":\"slow\",\"duration\":1}' http://127.0.0.1:${HOST_PORT}/chaos    # expect 403"
    curl -i -s -X POST -H "Content-Type: application/json" -d '{"mode":"slow","duration":1}' "http://127.0.0.1:${HOST_PORT}/chaos"
    echo
} > "${OUT}/04_promote_stable.txt" 2>&1
echo "wrote ${OUT}/04_promote_stable.txt"

#------------------------------------------------------------------------------
# 5. Generated configs (cat).
#------------------------------------------------------------------------------
{
    echo "$ cat manifest.yaml"
    cat manifest.yaml
    echo
    echo "$ sha256sum nginx.conf docker-compose.yml"
    sha256sum nginx.conf docker-compose.yml
    echo
    echo "$ cat nginx.conf"
    cat nginx.conf
    echo
    echo "$ cat docker-compose.yml"
    cat docker-compose.yml
} > "${OUT}/05_generated_configs.txt" 2>&1
echo "wrote ${OUT}/05_generated_configs.txt"

#------------------------------------------------------------------------------
# 6. nginx access log (the brief-mandated format).
#------------------------------------------------------------------------------
{
    echo "$ docker compose logs --no-color --tail=30 nginx"
    docker compose -f docker-compose.yml logs --no-color --tail=30 nginx
} > "${OUT}/06_nginx_access_log.txt" 2>&1
echo "wrote ${OUT}/06_nginx_access_log.txt"

#------------------------------------------------------------------------------
# 7. teardown --clean and idempotent re-init proof.
#------------------------------------------------------------------------------
{
    echo "$ ls nginx.conf docker-compose.yml    # before teardown"
    ls nginx.conf docker-compose.yml
    echo
    echo "$ ./swiftdeploy teardown --clean"
    ./swiftdeploy teardown --clean
    echo
    echo "$ ls nginx.conf docker-compose.yml 2>&1    # after teardown --clean"
    ls nginx.conf docker-compose.yml 2>&1 || true
    echo
    echo "$ ./swiftdeploy init    # regenerate from manifest"
    ./swiftdeploy init
    echo
    echo "$ sha256sum nginx.conf docker-compose.yml    # confirm regen is byte-identical"
    sha256sum nginx.conf docker-compose.yml
} > "${OUT}/07_teardown_and_regen.txt" 2>&1
echo "wrote ${OUT}/07_teardown_and_regen.txt"

echo
echo "Capture complete. Files in ${OUT}/:"
ls -1 "${OUT}/"
