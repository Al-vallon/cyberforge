#!/usr/bin/env bash
# Shared helpers for CyberForge operator scripts.

BOX_DIR="${ROOT}/boxes/box-001"
COMPOSE_FILE="${BOX_DIR}/docker-compose.yml"
APP_CONTAINER="cyberforge-box001-app"
TARGET_CONTAINER="cyberforge-box001-target"
NETWORK_NAME="cyberforge_box001"
HTTP_URL="http://127.0.0.1:5000/"

err() {
  echo "[ERROR] $*" >&2
  exit 1
}

info() {
  echo "[INFO]  $*"
}

need_podman() {
  command -v podman >/dev/null 2>&1 || err "Podman n'est pas installé ou n'est pas dans PATH."
}

ensure_podman_socket() {
  local sock="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/podman/podman.sock"
  # podman compose uses the Docker-compatible API socket.
  if [[ ! -S "${sock}" ]]; then
    info "Démarrage du socket API Podman…"
    systemctl --user start podman.socket \
      || err "Impossible de démarrer podman.socket. Essayez : systemctl --user start podman.socket"
  fi
  export DOCKER_HOST="unix://${sock}"
}

compose() {
  need_podman
  ensure_podman_socket
  [[ -f "${COMPOSE_FILE}" ]] || err "Fichier compose introuvable : ${COMPOSE_FILE}"
  if podman compose version >/dev/null 2>&1; then
    podman compose -f "${COMPOSE_FILE}" --project-directory "${BOX_DIR}" "$@"
  else
    err "podman compose est introuvable. Installez le plugin compose."
  fi
}

wait_for_http() {
  local i
  for i in $(seq 1 30); do
    if python3 -c "import urllib.request; urllib.request.urlopen('${HTTP_URL}', timeout=2)" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  err "L'application n'a pas répondu sur ${HTTP_URL} après 30s."
}

need_podman
