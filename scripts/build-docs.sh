#!/usr/bin/env bash
# Build both English (default) and Chinese documentation variants
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_BIN="$ROOT_DIR/.venv/bin"
SITE_DIR="$ROOT_DIR/site"

if [ -f "$VENV_BIN/activate" ]; then
  # shellcheck disable=SC1090
  source "$VENV_BIN/activate"
fi

rm -rf "$SITE_DIR"

zensical build
zensical build --config-file zensical.zh.toml
