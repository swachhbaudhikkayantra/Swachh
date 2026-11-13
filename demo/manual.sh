#!/usr/bin/env bash
# MANUAL MODE in simulation: you steer the simulated robot while SLAM builds the map live in RViz.
# Opens: Gazebo, RTAB-Map, RViz (demo.rviz: live map, robot trail, camera), the Tk steering-button
# window, and arrow-key teleop in THIS terminal. Use whichever you like; both drive the robot.
# Usage: ./manual.sh [world]       default: office
# Keys (click this terminal first): arrows = drive/spin, space or s = stop,
#       q/z = linear speed +/-10%, w/x = angular speed +/-10%, Esc or Ctrl+C = quit (stops everything).
# Optional 3D loop-closure viewer: ./manual.sh office --viz
# The REAL robot's manual mode (HMI + Arduino) is ./hmi.sh.
source "$(dirname "$0")/common.sh"
pick_world "${1:-office}"
VIZ=0; [[ "${2:-}" == "--viz" ]] && VIZ=1
require_clean

install_cleanup

DB="$HOME/.ros/swachh_demo_rtabmap.db"
rm -f "$DB"

start_bg sim ros2 launch vacuum_bringup sim.launch.py world:="$WORLD" use_rviz:=false \
    spawn_x:="$SX" spawn_y:="$SY"
start_rviz
wait_for_topic /clock 60 || true
sleep 6
start_bg slam ros2 launch vacuum_slam slam.launch.py environment:="$WORLD" use_rviz:=false database_path:="$DB"
sleep 5

if [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    start_bg steer_gui bash "$NAV/steer_gui.sh"
    if (( VIZ )); then
        start_bg rtabmap_viz ros2 run rtabmap_viz rtabmap_viz --ros-args \
            -r rgb/image:=/camera/color/image_raw -r depth/image:=/camera/depth/image_rect_raw \
            -r rgb/camera_info:=/camera/color/camera_info -r odom:=/odom
    fi
else
    echo "[demo] No display: RViz and the steering window are skipped."
fi

cat <<EOF

 MANUAL MODE (simulation, $WORLD).  Click this terminal, then drive with the arrow keys,
 or use the buttons in the steering window.
 Show : drive somewhere new and the map grows there; drive back and it stays (it is remembered).
 Say  : same single command path as the real HMI; here it drives the simulated robot.
        Drive slowly and steadily; RTAB-Map corrects drift when it recognises a place (loop closure).
 Save : ./savemap.sh $WORLD (another terminal)

EOF
python3 "$WS/install/vacuum_controller/lib/vacuum_controller/teleop_arrows.py"
