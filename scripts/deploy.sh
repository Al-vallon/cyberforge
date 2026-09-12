#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=common.sh
source "${ROOT}/scripts/common.sh"

info "Construction et démarrage de CyberForge Box 001…"
compose up -d --build
info "Attente de l'application HTTP…"
wait_for_http

cat <<EOF

CyberForge Box 001 est déployée.

  URL          : http://127.0.0.1:5000
  Réseau       : ${NETWORK_NAME}
  Conteneurs   : ${APP_CONTAINER}, ${TARGET_CONTAINER}

  Validation   : ${ROOT}/boxes/box-001/validation/validate.sh
  Arrêt        : ${ROOT}/scripts/destroy.sh
  Réinitialisation : ${ROOT}/scripts/reset.sh

Le port HTTP est bindé sur 127.0.0.1 uniquement.
La cible Linux n'est pas exposée sur l'hôte.

EOF
