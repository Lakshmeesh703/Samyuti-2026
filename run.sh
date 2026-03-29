#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
LOG_DIR="$ROOT_DIR/.logs"

if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ROOT_DIR/.env"
  set +a
fi

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

PIDS=()
mkdir -p "$LOG_DIR"

cleanup() {
  if [ "${#PIDS[@]}" -gt 0 ]; then
    echo "\nStopping processes..."
    for pid in "${PIDS[@]}"; do
      if kill -0 "$pid" >/dev/null 2>&1; then
        kill "$pid" >/dev/null 2>&1 || true
      fi
    done
  fi
}
trap cleanup EXIT INT TERM

have_cmd() { command -v "$1" >/dev/null 2>&1; }

python_has_pip() {
  local py="$1"
  "$py" -c "import pip" >/dev/null 2>&1
}

python_has_backend_deps() {
  local py="$1"
  "$py" -c "import fastapi, uvicorn, pydantic, indic_transliteration, edge_tts, openai, dotenv" >/dev/null 2>&1
}

wait_for_http() {
  local url="$1"
  local retries="${2:-30}"
  local delay="${3:-0.25}"

  if ! have_cmd curl; then
    return 0
  fi

  local i
  for ((i=1; i<=retries; i++)); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

is_port_free() {
  local host="$1"
  local port="$2"
  /usr/bin/python3 - "$host" "$port" <<'PY' >/dev/null 2>&1
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind((host, port))
except OSError:
    sys.exit(1)
finally:
    s.close()
sys.exit(0)
PY
}

pick_free_port() {
  local host="$1"
  local start_port="$2"
  local p="$start_port"
  while ! is_port_free "$host" "$p"; do
    p=$((p + 1))
  done
  printf '%s' "$p"
}

start_backend() {
  echo "[1/2] Starting backend..."
  cd "$BACKEND_DIR"

  if ! have_cmd python3; then
    echo "ERROR: python3 not found. Install Python 3.10+ and retry." >&2
    exit 1
  fi

  # Prefer venv if possible (cleaner). If venv creation fails (missing ensurepip),
  # fall back to user-site install with --break-system-packages.
  PY="/usr/bin/python3"
  VENV_PY="$BACKEND_DIR/.venv/bin/python"

  if [ -x "$VENV_PY" ]; then
    if python_has_pip "$VENV_PY"; then
      PY="$VENV_PY"
    else
      echo "  - found broken venv (no pip); removing $BACKEND_DIR/.venv"
      rm -rf "$BACKEND_DIR/.venv"
    fi
  fi

  if [ "$PY" = "/usr/bin/python3" ]; then
    # Try to create a venv (preferred). If venv creation fails, fall back.
    if python3 -m venv .venv >/dev/null 2>&1 && [ -x "$VENV_PY" ] && python_has_pip "$VENV_PY"; then
      PY="$VENV_PY"
    fi
  fi

  if [ "$PY" = "$VENV_PY" ]; then
    echo "  - using venv: $BACKEND_DIR/.venv"
    if ! python_has_backend_deps "$PY"; then
      "$PY" -m pip install -r requirements.txt >/dev/null
    fi
  else
    echo "  - venv not available; using system Python + user site-packages"
    echo "  - If this fails on Debian/Ubuntu, install: sudo apt install python3-venv"
    if ! python_has_backend_deps /usr/bin/python3; then
      /usr/bin/python3 -m pip install --break-system-packages -r requirements.txt >/dev/null
    fi
  fi

  local backend_port
  backend_port="$(pick_free_port "$BACKEND_HOST" "$BACKEND_PORT")"
  if [ "$backend_port" != "$BACKEND_PORT" ]; then
    echo "  - port $BACKEND_PORT busy; using $backend_port"
  fi
  BACKEND_PORT="$backend_port"

  local backend_log="$LOG_DIR/backend.log"
  "$PY" -m uvicorn app.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" >"$backend_log" 2>&1 &
  local backend_pid="$!"
  PIDS+=("$backend_pid")

  # Ensure process has not died immediately (e.g., import or bind errors)
  sleep 0.2
  if ! kill -0 "$backend_pid" >/dev/null 2>&1; then
    echo "ERROR: backend process exited early. Check $backend_log" >&2
    tail -n 50 "$backend_log" >&2 || true
    exit 1
  fi

  if wait_for_http "http://$BACKEND_HOST:$BACKEND_PORT/health" 40 0.2; then
    echo "  Backend: http://$BACKEND_HOST:$BACKEND_PORT"
  else
    echo "ERROR: backend failed to start. Check $backend_log" >&2
    tail -n 50 "$backend_log" >&2 || true
    exit 1
  fi
}

start_frontend() {
  echo "[2/2] Starting frontend..."
  cd "$FRONTEND_DIR"

  if ! have_cmd npm; then
    echo "WARN: npm not found. Frontend will NOT start." >&2
    echo "  Install Node.js + npm, then rerun to start UI:" >&2
    echo "  - Debian/Ubuntu: sudo apt install nodejs npm" >&2
    return 1
  fi

  if [ ! -d node_modules ]; then
    npm install >/dev/null
  fi

  local frontend_port
  frontend_port="$(pick_free_port "$FRONTEND_HOST" "$FRONTEND_PORT")"
  if [ "$frontend_port" != "$FRONTEND_PORT" ]; then
    echo "  - port $FRONTEND_PORT busy; using $frontend_port"
  fi
  FRONTEND_PORT="$frontend_port"

  local frontend_log="$LOG_DIR/frontend.log"
  VITE_BACKEND_URL="http://$BACKEND_HOST:$BACKEND_PORT" npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" --strictPort >"$frontend_log" 2>&1 &
  local frontend_pid="$!"
  PIDS+=("$frontend_pid")

  sleep 0.2
  if ! kill -0 "$frontend_pid" >/dev/null 2>&1; then
    echo "ERROR: frontend process exited early. Check $frontend_log" >&2
    tail -n 50 "$frontend_log" >&2 || true
    return 1
  fi

  if wait_for_http "http://$FRONTEND_HOST:$FRONTEND_PORT" 60 0.25; then
    echo "  Frontend: http://$FRONTEND_HOST:$FRONTEND_PORT"
  else
    echo "ERROR: frontend failed to start. Check $frontend_log" >&2
    tail -n 50 "$frontend_log" >&2 || true
    return 1
  fi
}

start_backend
if start_frontend; then
  :
else
  printf "\nFrontend not running. Backend-only mode is active.\n"
fi

printf "\nRunning. Press Ctrl+C to stop. Logs: %s\n" "$LOG_DIR"

# Wait for any child to exit (and keep trap cleanup)
wait -n
