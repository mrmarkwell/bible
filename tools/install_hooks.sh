#!/usr/bin/env bash
# tools/install_hooks.sh — Automated Git hook installer for Bible Engine
# Installs zero-dependency pre-commit (<0.15s) and pre-push (<2.5s) hooks.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

python3 "$REPO_DIR/tools/doctor.py" --install-hooks "$@"
