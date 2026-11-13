#!/usr/bin/env bash
# Step 3b: navigate on a saved map (Nav2 + AMCL localisation).
# Needs ~/maps/stage5/<world>.yaml  (make it with ./explore.sh then ./savemap.sh).
# Usage: ./navigate.sh [world]      default: office
# In RViz (opens ~30 s after start):
#   1. click "2D Pose Estimate" and drag at the robot's spawn point (printed below)
#   2. watch the green particle cloud converge
#   3. click "Nav2 Goal" and set goals
# Stop with Ctrl+C (also stops the simulator).
# Note: do NOT use ./start.sh navigate -- it starts the simulator without world:=, giving the empty world.
source "$(dirname "$0")/common.sh"
pick_world "${1:-office}"
require_clean

MAP="$HOME/maps/stage5/$WORLD.yaml"
if [[ ! -f $MAP ]]; then
    echo "[demo] No map at $MAP"
    echo "       Make one:  ./explore.sh $WORLD   then   ./savemap.sh $WORLD   (while it runs)"
    exit 1
fi

install_cleanup

cat <<EOF

 NAVIGATION ON A SAVED MAP  ($WORLD)
 Set the 2D Pose Estimate at spawn: x=$SX y=$SY, facing +x.
 Say: success was only 29.2% (52/178 goals, ground-truth checked). AMCL's pose often put the
      footprint inside a wall. With perfect pose: 19/20 (single dev-world episode, indicative).
      Here AMCL runs on a map the robot built itself; the paper's numbers used a ground-truth map.

EOF

start_bg sim ros2 launch vacuum_bringup sim.launch.py world:="$WORLD" use_sim_time:=true \
    use_rviz:=false spawn_x:="$SX" spawn_y:="$SY"
wait_for_topic /clock 60 || true
sleep 6
run_fg ros2 launch vacuum_nav2 nav2_localization.launch.py map_path:="$MAP" environment:="$WORLD"
