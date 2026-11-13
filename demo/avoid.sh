#!/usr/bin/env bash
# OBSTACLE AVOIDANCE: the robot drives start -> goal in an obstacle scenario, with the Gazebo window
# and RViz (map, local costmap showing obstacle inflation, planned path) side by side.
# Usage: ./avoid.sh [scenario] [seed]      default: avoid_u_trap 101
#   avoid_u_trap          static U-shaped trap between start and goal      (paper 3/3)
#   avoid_dynamic_sudden  0.4x0.4 m box darts out from behind a wall       (paper 1/3)
#   others: avoid_dead_end avoid_narrow_gap avoid_narrow_gap_wide avoid_head_on avoid_cluster avoid_dynamic_cross
# Success = goal reached with no contact. Paper: 4/6 overall, mean minimum clearance 0.159 m.
# Output goes to ~/eval_runs/demo_<time>/ (own experiment name, not mixed with the 2026-10-25 evaluation).
# This is a DEMO run, not evaluation data.
source "$(dirname "$0")/common.sh"
SCEN="${1:-avoid_u_trap}"
SEED="${2:-101}"
if [[ "$SCEN" != avoid_* || ! -f "$WS/src/vacuum_gazebo/worlds/$SCEN.sdf" ]]; then
    echo "Unknown scenario '$SCEN'. Available:"; ls "$WS/src/vacuum_gazebo/worlds" | sed -n 's/^\(avoid_.*\)\.sdf$/  \1/p'
    exit 1
fi
pick_any_world "$SCEN"
require_clean
install_cleanup

cat <<EOF

 AVOIDANCE: $SCEN (seed $SEED)
 $WORLD_DESC
 Watch : Gazebo (the robot and obstacles) and RViz. In RViz the coloured halo around obstacles is the
         local costmap (obstacles + inflation); the magenta line is the planned path being re-planned.
 Result is printed at the end (goal reached? contact?).
 PATIENCE: the robot sits still at first. The harness waits for the controllers, Nav2 and AMCL to come up
 and for the robot to localise, THEN sends the goal. On a slow machine (simulation at ~20% of real time,
 as on the WSL laptop) that takes 1-2 minutes of wall time. Do not Ctrl+C early. The scenario is over
 when the terminal prints the result; the harness shuts everything down itself.

EOF
start_rviz
cd "$WS/src/vacuum_eval" || exit 1
run_fg python3 -m vacuum_eval.run_episode --experiment "demo_$(date +%H%M%S)" --world "$SCEN" \
    --method scripted_goals --goal-list scenario --nav-map gt --seed "$SEED" \
    --odom-noise 0 --headless 0
