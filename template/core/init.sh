#!/usr/bin/env bash

set -euo pipefail

HARNESS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HARNESS_ROOT"

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "ERROR: Harness Core requires Python 3.10 or newer." >&2
  exit 1
fi

exec python3 scripts/harness.py init "$@"
