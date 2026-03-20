#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/openclaw_castor_heartbeat.sh"
"$SCRIPT_DIR/openclaw_castor_poll.sh"
