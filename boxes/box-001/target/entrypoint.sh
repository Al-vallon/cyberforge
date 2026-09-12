#!/bin/bash
set -euo pipefail
mkdir -p /run/sshd
chmod 755 /run/sshd
exec /usr/sbin/sshd -D -e
