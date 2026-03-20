#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/openclaw_castor_common.sh"

load_castor_env

current_load="$(state_get current_load 0)"
max_load="$(state_get max_load "$CASTOR_MAX_LOAD")"

if (( current_load >= max_load )); then
  log "skip poll because current_load=$current_load max_load=$max_load"
  exit 0
fi

categories_json="$(csv_to_json_array "$CASTOR_AGENT_CATEGORIES")"
payload="$(python3 - "$categories_json" <<'PY'
import json
import sys

categories = json.loads(sys.argv[1])
print(json.dumps({"categories": categories, "max_tasks": 3}, ensure_ascii=False))
PY
)"

response_file="$(mktemp)"
http_code="$(
  curl -sS -o "$response_file" -w '%{http_code}' \
    -X POST "$CASTOR_BASE_URL/api/v1/tasks/poll" \
    -H "Authorization: Bearer $CASTOR_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$payload"
)"

if [[ "$http_code" != "200" ]]; then
  log "poll failed with HTTP $http_code"
  cat "$response_file"
  rm -f "$response_file"
  exit 1
fi

cp "$response_file" "$CASTOR_LAST_POLL_FILE"

summary="$(python3 - "$response_file" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
tasks = data.get("tasks", [])
first_task_id = tasks[0].get("task_id") if tasks else ""
print(f"{len(tasks)}|{first_task_id}")
PY
)"

task_count="${summary%%|*}"
first_task_id="${summary#*|}"
log "poll completed with task_count=$task_count"
if [[ -n "$first_task_id" ]]; then
  log "first available task_id=$first_task_id"
fi

cat "$response_file"
rm -f "$response_file"
