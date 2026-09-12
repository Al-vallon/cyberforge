#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=common.sh
source "${ROOT}/scripts/common.sh"

info "Réinitialisation complète de CyberForge Box 001…"
compose down --volumes --remove-orphans --rmi local || true
compose up -d --build --force-recreate
info "Attente de l'application HTTP…"
wait_for_http
info "Box 001 réinitialisée."
info "URL : http://127.0.0.1:5000"
