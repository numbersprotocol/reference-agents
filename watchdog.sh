#!/bin/bash
# watchdog.sh — auto-restart any agent or synctrigger that has died
# Runs every 5 minutes, uses minimal memory (sleep-heavy)
# Deploy: nohup bash watchdog.sh >> logs/watchdog.log 2>&1 &

AGENTS="provart newsprove agentlog dataprove socialprove researchprove codeprove"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$DIR/logs/watchdog.log"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)  [watchdog]  $*"; }

cd "$DIR" || exit 1

log "watchdog started (PID=$$)"

while true; do
    # --- check each agent ---
    for agent in $AGENTS; do
        if ! pgrep -f "${agent}.py" > /dev/null 2>&1; then
            log "RESTART ${agent} (was not running)"
            nohup python3 "${agent}.py" >> "logs/${agent}.log" 2>&1 &
            log "${agent} restarted (PID=$!)"
        fi
    done

    # --- check synctrigger ---
    if ! pgrep -f "synctrigger.py" > /dev/null 2>&1; then
        log "RESTART synctrigger (was not running)"
        nohup python3 synctrigger.py >> logs/synctrigger.log 2>&1 &
        log "synctrigger restarted (PID=$!)"
    fi

    sleep 300   # check every 5 minutes
done
