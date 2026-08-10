#!/usr/bin/env bash

set -euo pipefail

STARTER_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$STARTER_ROOT"
export PYTHONDONTWRITEBYTECODE=1

QUICK=false
if [[ $# -gt 1 ]]; then
  echo "ERROR: usage: ./init.sh [--quick]" >&2
  exit 2
fi
if [[ $# -eq 1 ]]; then
  if [[ "$1" != "--quick" ]]; then
    echo "ERROR: usage: ./init.sh [--quick]" >&2
    exit 2
  fi
  QUICK=true
fi

echo "==> Harness starter baseline"
echo "    root: $STARTER_ROOT"

python3 scripts/validate_harness.py
if [[ "$QUICK" == false ]]; then
  python3 -B -m unittest discover -s tests -v
fi

if [[ "$QUICK" == true ]]; then
  echo "==> Quick baseline healthy (full Fixture suite deferred)"
else
  echo "==> Baseline healthy"
fi
