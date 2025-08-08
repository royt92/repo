#!/usr/bin/env bash
set -euo pipefail

# Install dependencies (handle PEP 668 managed envs)
if python3 -m pip --version >/dev/null 2>&1; then
  python3 -m pip install -r requirements.txt --no-input --break-system-packages || true
else
  echo "pip for python3 is not available. Please install python3-pip." >&2
  exit 1
fi

# Copy env template if .env missing
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from template. Edit it before running live."
fi

# Run bot
exec python3 main.py