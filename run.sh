#!/usr/bin/env bash
# lingua-bridge launcher for Linux and macOS.
#   ./run.sh            full install (translation + web UI), then start the app
#   ./run.sh --light    conversion + detection + web UI only (no PyTorch, installs in seconds)
#   ./run.sh --reinstall   force a fresh install of the packages
set -euo pipefail
cd "$(dirname "$0")"

LIGHT=0; REINSTALL=0
for arg in "$@"; do
  case "$arg" in --light) LIGHT=1 ;; --reinstall) REINSTALL=1 ;; esac
done

PY=""
for c in python3.13 python3.12 python3.11 python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.11 or newer is required. Install it from https://www.python.org/downloads/ and run this again." >&2
  exit 1
fi

[ -d .venv ] || { echo "Creating virtual environment with $($PY --version)..."; "$PY" -m venv .venv; }
# shellcheck disable=SC1091
. .venv/bin/activate

MODE=full; EXTRAS="api,translate"
if [ "$LIGHT" = 1 ]; then MODE=light; EXTRAS="api"; fi
STAMP=".venv/.lingua-installed-$MODE"
if [ ! -f "$STAMP" ] || [ "$REINSTALL" = 1 ] || [ pyproject.toml -nt "$STAMP" ]; then
  echo "Installing lingua-bridge[$EXTRAS] (the full install downloads PyTorch, a few GB, one time)..."
  python -m pip install --quiet --upgrade pip
  python -m pip install -e ".[$EXTRAS]"
  [ "$LIGHT" = 1 ] || python scripts/setup_torch_gpu.py || true
  touch "$STAMP"
fi

[ -f .env ] || cp .env.example .env
echo
lingua doctor || true
echo
lingua serve --open
