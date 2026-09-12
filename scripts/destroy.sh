#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=common.sh
source "${ROOT}/scripts/common.sh"

info "Arrêt de CyberForge Box 001…"
compose down --volumes --remove-orphans
info "Box 001 arrêtée."
