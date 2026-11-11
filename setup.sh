#!/usr/bin/env bash
# Create .venv, install requirements, make sure API key files exist, then run the tests.
set -euo pipefail
cd "$(dirname "$0")"

PY=python3
command -v python3.12 >/dev/null && PY=python3.12   # matches .python-version

if [ -d .venv ]; then
  echo "==> Virtual environment .venv already exists, reusing it"
else
  echo "==> Creating virtual environment .venv with $($PY --version)"
  "$PY" -m venv .venv
fi

echo "==> Upgrading pip"
.venv/bin/python -m pip install -q --upgrade pip

echo "==> Installing requirements from requirements.txt"
.venv/bin/python -m pip install -q -r requirements.txt
echo "==> Done. Activate with: source .venv/bin/activate"

# Keys: if ~/.secrets/<provider>_api_key exists we assume it holds the key and
# don't look at it; otherwise prompt for a paste (empty = skip) and save it mode 600.
echo "==> Checking API keys in ~/.secrets"
for provider in openai anthropic; do
  f="$HOME/.secrets/${provider}_api_key"
  if [ -f "$f" ]; then
    echo "    $provider: key file found ($f), skipping"
  else
    echo "    $provider: no key file at $f, asking for a key"
    .venv/bin/python -c "import sys; sys.path.insert(0, 'rq1'); from llm import ensure_api_key; ensure_api_key('$provider', optional=True)"
    if [ -f "$f" ]; then echo "    $provider: saved to $f (mode 600)"; else echo "    $provider: skipped"; fi
  fi
done
echo "==> Running tests (pytest rq1, from the repo root)"
.venv/bin/python -m pytest rq1 -q
echo "==> Setup complete"
