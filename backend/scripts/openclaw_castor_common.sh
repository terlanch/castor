#!/bin/bash

set -euo pipefail

OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
CASTOR_ENV_FILE="${CASTOR_ENV_FILE:-$OPENCLAW_HOME/.env}"
CASTOR_RUNTIME_DIR="${CASTOR_RUNTIME_DIR:-$OPENCLAW_HOME/castor}"
CASTOR_STATE_FILE="${CASTOR_STATE_FILE:-$CASTOR_RUNTIME_DIR/state.json}"
CASTOR_LAST_POLL_FILE="${CASTOR_LAST_POLL_FILE:-$CASTOR_RUNTIME_DIR/last_poll.json}"

log() {
  printf '[castor-cron] %s\n' "$*"
}

load_castor_env() {
  if [[ ! -f "$CASTOR_ENV_FILE" ]]; then
    log "missing env file: $CASTOR_ENV_FILE"
    exit 1
  fi

  set -a
  # shellcheck disable=SC1090
  source "$CASTOR_ENV_FILE"
  set +a

  : "${CASTOR_API_KEY:?CASTOR_API_KEY is required in ~/.openclaw/.env}"

  export CASTOR_BASE_URL="${CASTOR_BASE_URL:-http://localhost:8080}"
  export CASTOR_MAX_LOAD="${CASTOR_MAX_LOAD:-3}"
  export CASTOR_AGENT_CATEGORIES="${CASTOR_AGENT_CATEGORIES:-}"
  export CASTOR_HEALTHY="${CASTOR_HEALTHY:-true}"

  mkdir -p "$CASTOR_RUNTIME_DIR"

  if [[ ! -f "$CASTOR_STATE_FILE" ]]; then
    cat >"$CASTOR_STATE_FILE" <<EOF
{"current_load":0,"max_load":$CASTOR_MAX_LOAD,"healthy":true,"status":"idle","active_task_id":null,"last_heartbeat_at":null}
EOF
  fi
}

state_get() {
  local key="$1"
  local default_value="${2:-}"
  python3 - "$CASTOR_STATE_FILE" "$key" "$default_value" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
key = sys.argv[2]
default = sys.argv[3]

if not path.exists():
    print(default)
    raise SystemExit(0)

data = json.loads(path.read_text(encoding="utf-8"))
value = data.get(key, default)
if isinstance(value, bool):
    print(str(value).lower())
elif value is None:
    print("null")
else:
    print(value)
PY
}

state_set() {
  python3 - "$CASTOR_STATE_FILE" "$@" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
updates = sys.argv[2:]
data = {}
if path.exists():
    data = json.loads(path.read_text(encoding="utf-8"))

for pair in updates:
    key, raw_value = pair.split("=", 1)
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        value = raw_value
    data[key] = value

path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
PY
}

csv_to_json_array() {
  python3 - "$1" <<'PY'
import json
import sys

raw = sys.argv[1]
items = [item.strip() for item in raw.split(",") if item.strip()]
print(json.dumps(items, ensure_ascii=False))
PY
}

derive_status() {
  local current_load="$1"
  local healthy="$2"

  if [[ "$healthy" != "true" ]]; then
    printf 'degraded\n'
    return
  fi

  if (( current_load > 0 )); then
    printf 'busy\n'
    return
  fi

  printf 'idle\n'
}
