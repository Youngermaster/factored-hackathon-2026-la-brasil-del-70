#!/usr/bin/env bash
# Smoke test of a deployed stack: deploy/smoke_test.sh <base-url> [--ca-file <root.crt>]
#
# The TLS certificate, health, security headers, the demo sign-in and its cookies, one read-only conversation per
# workflow in Spanish and Portuguese, an out-of-scope abstention, and a cross-customer 404 (deploy/smoke_test.py has
# the list). Needs python3 (3.10 or later, standard library only), which Ubuntu and Debian VMs ship. Exits non-zero
# on the first failure and prints no secret.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  printf 'usage: %s <base-url> [--ca-file <root.crt>]\n' "$0" >&2
  exit 2
fi
PYTHON="${PYTHON:-python3}"
command -v "${PYTHON}" > /dev/null || { printf 'error: %s is not installed\n' "${PYTHON}" >&2; exit 2; }
exec "${PYTHON}" "$(dirname "${BASH_SOURCE[0]}")/smoke_test.py" "$@"
