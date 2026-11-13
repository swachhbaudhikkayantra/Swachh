#!/usr/bin/env bash
# Stop every leftover demo process (Gazebo, ROS nodes, RViz, harness, teleop, steering window).
# You normally do NOT need this: Ctrl+C in any demo script now stops everything it started.
# Use it only if a terminal was closed or killed. Escalates SIGINT -> SIGTERM -> SIGKILL.
# Refuses to run while an evaluation campaign (run_batch started by someone else) is active:
# stop that with  kill -INT <harness PID>.
source "$(dirname "$0")/common.sh"

if pgrep -u "$USER" -f '^python3 -m vacuum_eval[.]run_batch' >/dev/null; then
    echo "[stop] An evaluation campaign (run_batch) is active. Not touching anything."
    echo "       Stop it with: kill -INT <harness PID>   (pgrep -af 'vacuum_eval[.]run_batch')"
    exit 1
fi

PIDS_LEFT="$(stack_pids)"
if [[ -z "$PIDS_LEFT" ]]; then echo "[stop] Nothing to stop."; exit 0; fi
echo "[stop] Stopping: $(echo "$PIDS_LEFT" | tr '\n' ' ')"
if kill_stack; then
    echo "[stop] All stopped."
else
    echo "[stop] Still alive:"
    # shellcheck disable=SC2086
    ps -o pid,etime,cmd -p $(stack_pids | tr '\n' ',' | sed 's/,$//') | cut -c1-140
    exit 1
fi
