#!/bin/bash
# watchdog.sh - auto-restart public agents if they stop.
# Deploy: nohup bash watchdog.sh >> logs/watchdog.log 2>&1 &

AGENTS="newsprove socialprove"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$DIR/logs/watchdog.log"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)  [watchdog]  $*"; }

mkdir -p "$DIR/logs" "$DIR/state"
cd "$DIR" || exit 1

log "watchdog started (PID=$$)"

while true; do
    for agent in $AGENTS; do
        if ! pgrep -f "${agent}.py" > /dev/null 2>&1; then
            log "RESTART ${agent} (was not running)"
            nohup python3 "${agent}.py" >> "logs/${agent}.log" 2>&1 &
            echo $! > "state/${agent}.pid"
            log "${agent} restarted (PID=$!)"
        fi
    done
    sleep 300
done
