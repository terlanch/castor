#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/openclaw_castor_common.sh"

load_castor_env

current_load="$(state_get current_load 0)"
max_load="$(state_get max_load "$CASTOR_MAX_LOAD")"
healthy="$(state_get healthy "$CASTOR_HEALTHY")"
status="$(derive_status "$current_load" "$healthy")"

payload="$(python3 - "$status" "$current_load" "$max_load" "$healthy" <<'PY'
import json
import sys

status = sys.argv[1]
current_load = int(sys.argv[2])
max_load = int(sys.argv[3])
healthy = sys.argv[4].lower() == "true"

print(
    json.dumps(
        {
            "status": status,
            "current_load": current_load,
            "max_load": max_load,
            "healthy": healthy,
        },
        ensure_ascii=False,
    )
)
PY
)"

response_file="$(mktemp)"
http_code="$(
  curl -sS -o "$response_file" -w '%{http_code}' \
    -X POST "$CASTOR_BASE_URL/api/v1/agents/heartbeat" \
    -H "Authorization: Bearer $CASTOR_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$payload"
)"

if [[ "$http_code" != "200" ]]; then
  log "heartbeat failed with HTTP $http_code"
  cat "$response_file"
  rm -f "$response_file"
  exit 1
fi

last_heartbeat_at="$(python3 - "$response_file" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(data.get("last_heartbeat_at", ""))
PY
)"

state_set \
  "current_load=$current_load" \
  "max_load=$max_load" \
  "healthy=$( [[ "$healthy" == "true" ]] && printf 'true' || printf 'false' )" \
  "status=\"$status\"" \
  "last_heartbeat_at=\"$last_heartbeat_at\""

log "heartbeat sent with status=$status current_load=$current_load max_load=$max_load"
cat "$response_file"
rm -f "$response_file"
