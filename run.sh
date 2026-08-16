#!/usr/bin/env bash
# Native Linux launcher. Creates .venv with uv and runs Streamlit from it.
set -u
cd "$(dirname "$0")" || exit 1

echo
echo " Personal finance agent"
echo " Uses a project .venv created by uv. Leave this terminal open."
echo

export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"
VENV_PY="$(pwd)/.venv/bin/python"

fail() {
  echo
  echo "[setup] Failed. See the messages above."
  exit 1
}

if ! command -v uv >/dev/null 2>&1; then
  echo "[setup] uv not found. Installing uv..."
  if ! command -v curl >/dev/null 2>&1; then
    echo "[setup] curl is required to install uv. Install curl, then run: bash run.sh"
    exit 1
  fi
  curl -LsSf https://astral.sh/uv/install.sh | sh || fail
  export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "[setup] uv is still not on PATH. Open a new terminal and run: bash run.sh"
  echo "        Or install from https://docs.astral.sh/uv/"
  exit 1
fi

echo "[setup] Ensuring Python 3.11+ is available to uv..."
uv python install || {
  echo "[setup] Could not install Python. Need a network connection and Python 3.11+."
  exit 1
}

if [ ! -x "${VENV_PY}" ]; then
  echo "[setup] Creating .venv with uv..."
  uv venv .venv || fail
else
  echo "[setup] Using existing .venv"
fi

echo "[setup] Installing dependencies into .venv..."
uv sync --all-groups --python "${VENV_PY}" || {
  echo "[setup] Dependency install failed. Check the messages above and try again."
  exit 1
}

if [ ! -x "${VENV_PY}" ]; then
  echo "[setup] .venv/bin/python missing after sync."
  exit 1
fi

if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "[setup] Created .env from .env.example. Add cloud keys there only if you need them."
  echo "        CSV/Excel ingest works with no keys. Do not commit .env."
fi

mkdir -p data

echo
echo "[setup] Ready. Starting Streamlit with .venv/bin/python ..."
echo

exec "${VENV_PY}" -m streamlit run streamlit_app.py --server.headless true --server.address localhost
