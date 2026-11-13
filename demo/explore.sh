#!/usr/bin/env bash
# Autonomous frontier exploration with a LIVE map in RViz (demo.rviz).
# Gazebo -> RTAB-Map (T+12 s) -> Nav2 (T+20 s) -> explorer (T+28 s). Wait ~30 s.
# Usage: ./explore.sh [world] [extra launch args...]     default: office
#   e.g. ./explore.sh multi_room_loop
# In another terminal: ./status.sh      To keep the map: ./savemap.sh <world> (while it runs)
# Stop with Ctrl+C.
source "$(dirname "$0")/common.sh"
pick_world "${1:-office}"
shift || true
require_clean
trap 'stop_bg' EXIT
trap 'exit 130' INT TERM

# Own database file, so the demo never touches ~/.ros/rtabmap.db. Start every run from a blank map.
DB="$HOME/.ros/swachh_demo_rtabmap.db"
rm -f "$DB"

cat <<EOF

 AUTONOMOUS EXPLORATION  ($WORLD, spawn $SX,$SY)   -- do not touch the keyboard
 RViz shows : live map (white free / black wall / grey unknown), green frontiers, red chosen
              frontier, yellow goal, magenta planned path, green arrows = where the robot has been,
              and the robot camera view.
 Explain    : score S = 1.0 ln(1+n) - 1.5 d - 0.8 p   (n size, d distance, p obstacle penalty)
              goals >= 0.30 m from walls; Smac Hybrid-A* plans, MPPI follows at 20 Hz;
              a goal is dropped after failure, 30 s, or <0.30 m movement in 15 s (blacklist 60 s)
 Caveat     : odometry is CLEAN by default; the paper's runs injected odometry noise.

EOF
start_rviz
ros2 launch vacuum_exploration exploration.launch.py \
    environment:="$WORLD" spawn_x:="$SX" spawn_y:="$SY" spawn_yaw:=0.0 \
    database_path:="$DB" use_rviz:=false "$@"
