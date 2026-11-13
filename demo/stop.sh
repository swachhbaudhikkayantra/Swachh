#!/usr/bin/env bash
# Stop leftover demo processes (Gazebo, ROS nodes, RViz, teleop). Gentle: SIGINT first, then wait.
# Usage: ./stop.sh            SIGINT, wait 10 s, list anything still alive
#        ./stop.sh --force    ... then SIGKILL whatever is still alive
# Refuses to run while an evaluation run is active (stop those with: kill -INT <harness PID>).
# Unlike Navigation/stop.sh it does not pkill -9 up front and does not delete ~/.ros/rtabmap.db.
PAT='ros2 (launch|run)|gz sim|rviz2|rtabmap|parameter_bridge|robot_state_publisher|controller_server|planner_server|bt_navigator|behavior_server|smoother_server|velocity_smoother|waypoint_follower|lifecycle_manager|map_server|amcl|exploration_|frontier_|teleop_arrows|robot_steering_gui|cmd_vel_relay|controller_manager|^(/usr)?(/bin/)?bash (\./|/[^ ]*/)?(oldmap|spin|manual|explore|navigate|avoid|tour|world|steer)[.]sh|^python3 - .*(quick_exploration_noise|fig_actual_vs_explored)'

if pgrep -u "$USER" -f 'vacuum_eval[.]run_(batch|episode)' >/dev/null; then
    echo "[stop] An evaluation run (run_batch / run_episode) is active. Not touching anything."
    echo "       Stop it with: kill -INT <harness PID>   (pgrep -af 'vacuum_eval[.]run_')"
    exit 1
fi

# Never signal this script or any of its ancestors (the shell/terminal that launched it).
ANC=" $$ "; p=$$
while [[ $p -gt 1 ]]; do
    p="$(awk '{print $4}' "/proc/$p/stat" 2>/dev/null)"
    [[ -z $p ]] && break
    ANC+="$p "
done
list() { pgrep -u "$USER" -f "$PAT" | while read -r x; do [[ $ANC == *" $x "* ]] || echo "$x"; done; }

PIDS="$(list)"
if [[ -z "$PIDS" ]]; then echo "[stop] Nothing to stop."; exit 0; fi

echo "[stop] Sending SIGINT to: $(echo "$PIDS" | tr '\n' ' ')"
# shellcheck disable=SC2086
kill -INT $PIDS 2>/dev/null || true
for _ in $(seq 1 20); do
    sleep 0.5
    [[ -z "$(list)" ]] && { echo "[stop] All stopped."; exit 0; }
done

LEFT="$(list)"
echo "[stop] Still running after 10 s:"
# shellcheck disable=SC2086
ps -o pid,etime,cmd -p $(echo "$LEFT" | tr '\n' ',' | sed 's/,$//') 2>/dev/null | cut -c1-150
if [[ "${1:-}" == "--force" ]]; then
    # shellcheck disable=SC2086
    kill -KILL $LEFT 2>/dev/null || true
    echo "[stop] Force-killed."
else
    echo "       Re-run with --force to SIGKILL them."
    exit 1
fi
