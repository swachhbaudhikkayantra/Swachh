#!/usr/bin/env bash
# Tour of the worlds: each opens in Gazebo for N seconds, then the next one loads.
# Usage: ./tour.sh [seconds] [world ...]
#   ./tour.sh                 25 s each, default list
#   ./tour.sh 40 office maze_dead_ends avoid_u_trap
# Press Enter to skip to the next world early. Ctrl+C ends the tour.
source "$(dirname "$0")/common.sh"
SECS="${1:-25}"
[[ $# -gt 0 ]] && shift
LIST=("$@")
[[ ${#LIST[@]} -eq 0 ]] && LIST=(office multi_room_loop maze_dead_ends two_rooms_door corridor symmetric_hall apartment avoid_u_trap avoid_dynamic_sudden)
require_clean
trap 'stop_bg' EXIT
trap 'exit 130' INT TERM

n=0
for w in "${LIST[@]}"; do
    n=$((n + 1))
    pick_any_world "$w"
    echo
    echo "==== [$n/${#LIST[@]}] $WORLD ===="
    echo " $WORLD_DESC"
    PIDS=()
    start_bg "tour_$WORLD" ros2 launch vacuum_bringup sim.launch.py "${WORLD_ARGS[@]}" \
        spawn_x:="$SX" spawn_y:="$SY" use_rviz:=false
    wait_for_topic /clock 60 || true
    echo " (Enter = next world, Ctrl+C = quit; moving on in ${SECS}s)"
    if [[ -t 0 ]]; then read -r -t "$SECS" _ || true; else sleep "$SECS"; fi
    stop_bg
    PIDS=()
    for _ in $(seq 1 30); do pgrep -u "$USER" -f '[g]z sim' >/dev/null || break; sleep 1; done
done
echo "Tour finished."
