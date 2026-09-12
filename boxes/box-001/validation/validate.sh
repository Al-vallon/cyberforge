#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
BOX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../../../scripts/common.sh
source "${ROOT}/scripts/common.sh"

APP_CONTAINER="cyberforge-box001-app"
TARGET_CONTAINER="cyberforge-box001-target"
NETWORK_NAME="cyberforge_box001"
BOX_YML="${BOX_DIR}/box.yml"
FAILED=0

pass() {
  echo "[PASS] $*"
}

fail() {
  echo "[FAIL] $*"
  FAILED=1
}

container_running() {
  local name="$1"
  podman inspect -f '{{.State.Running}}' "${name}" 2>/dev/null | grep -qx true
}

http_body() {
  local path="${1:-/}"
  python3 - <<PY
import urllib.request
req = urllib.request.Request("http://127.0.0.1:5000${path}")
try:
    with urllib.request.urlopen(req, timeout=5) as resp:
        print(resp.read().decode("utf-8", errors="replace"))
except urllib.error.HTTPError as exc:
    print(exc.read().decode("utf-8", errors="replace"))
PY
}

echo "CyberForge Box 001 — validation"
echo

if container_running "${APP_CONTAINER}"; then
  pass "Container app running"
else
  fail "Container app running"
fi

if container_running "${TARGET_CONTAINER}"; then
  pass "Container target running"
else
  fail "Container target running"
fi

if podman network exists "${NETWORK_NAME}" >/dev/null 2>&1; then
  pass "Network ${NETWORK_NAME} exists"
else
  fail "Network ${NETWORK_NAME} exists"
fi

if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/', timeout=5)" >/dev/null 2>&1; then
  HOME_BODY="$(http_body /)"
  if grep -q "CyberForge Box 001" <<<"${HOME_BODY}" && grep -q "Version 1.0" <<<"${HOME_BODY}"; then
    pass "Web application reachable"
  else
    fail "Web application reachable (page does not identify CyberForge Box 001)"
  fi
else
  fail "Web application reachable"
  HOME_BODY=""
fi

PORTS="$(podman port "${APP_CONTAINER}" 2>/dev/null || true)"
if grep -Eq '127\.0\.0\.1:5000' <<<"${PORTS}"; then
  pass "HTTP published on localhost only"
else
  fail "HTTP published on localhost only (got: ${PORTS:-none})"
fi

COMBINED="${HOME_BODY}$(http_body /search)$(http_body /admin)"
if grep -Eq 'CF\{|/home/cyber/user.txt|/root/root.txt' <<<"${COMBINED}"; then
  fail "Flags are not exposed over HTTP"
else
  pass "Flags are not exposed over HTTP"
fi

if podman exec "${APP_CONTAINER}" python3 -c "import socket; s=socket.create_connection(('target', 22), 5); s.close()"; then
  pass "Target reachable from app network"
else
  fail "Target reachable from app network"
fi

if podman exec "${APP_CONTAINER}" id -u | grep -qx 0; then
  fail "Web application is not running as root"
else
  pass "Web application is not running as root"
fi

if podman exec "${TARGET_CONTAINER}" test -f /home/cyber/user.txt; then
  pass "User flag present"
else
  fail "User flag present"
fi

if podman exec "${TARGET_CONTAINER}" test -f /root/root.txt; then
  pass "Root flag present"
else
  fail "Root flag present"
fi

USER_STAT="$(podman exec "${TARGET_CONTAINER}" stat -c '%U %a' /home/cyber/user.txt 2>/dev/null || true)"
if [[ "${USER_STAT}" == "cyber 600" ]]; then
  pass "User flag permissions"
else
  fail "User flag permissions (expected 'cyber 600', got '${USER_STAT:-missing}')"
fi

ROOT_STAT="$(podman exec "${TARGET_CONTAINER}" stat -c '%U %a' /root/root.txt 2>/dev/null || true)"
if [[ "${ROOT_STAT}" == "root 600" ]]; then
  pass "Root flag permissions"
else
  fail "Root flag permissions (expected 'root 600', got '${ROOT_STAT:-missing}')"
fi

# Operator check: the flag files must not be world-readable.
if podman exec "${TARGET_CONTAINER}" bash -c 'test "$(stat -c %a /home/cyber/user.txt)" = "600" && test "$(stat -c %a /root/root.txt)" = "600"'; then
  pass "Flag files are not world-readable"
else
  fail "Flag files are not world-readable"
fi

SUDOERS="$(podman exec "${TARGET_CONTAINER}" cat /etc/sudoers.d/cyber 2>/dev/null || true)"
SCRIPT_PERM="$(podman exec "${TARGET_CONTAINER}" stat -c '%a' /usr/local/bin/system-health.sh 2>/dev/null || true)"
if grep -q 'NOPASSWD: /usr/local/bin/system-health.sh' <<<"${SUDOERS}" && [[ "${SCRIPT_PERM}" == "777" ]]; then
  pass "Privilege escalation configured"
else
  fail "Privilege escalation configured"
fi

if [[ -f "${BOX_YML}" ]] \
  && grep -q 'slug: box-001' "${BOX_YML}" \
  && grep -q 'initial_access' "${BOX_YML}" \
  && grep -q 'user_flag' "${BOX_YML}" \
  && grep -q 'privilege_escalation' "${BOX_YML}" \
  && grep -q 'root_flag' "${BOX_YML}"; then
  pass "box.yml objectives declared"
else
  fail "box.yml objectives declared"
fi

echo
if [[ "${FAILED}" -eq 0 ]]; then
  echo "Box validation: PASS"
  exit 0
fi

echo "Box validation: FAIL"
exit 1
