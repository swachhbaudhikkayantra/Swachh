#!/usr/bin/env bash
# Show a Gazebo world with the robot in it (no SLAM, no navigation). Good for "multiple worlds".
# Usage: ./world.sh [world]        default: office
#   exploration worlds: apartment office corridor empty_room cluttered_room two_rooms_door
#                       multi_room_loop maze_dead_ends symmetric_hall
#   avoidance worlds:   avoid_u_trap avoid_dynamic_sudden avoid_dead_end avoid_narrow_gap
#                       avoid_narrow_gap_wide avoid_head_on avoid_cluster avoid_dynamic_cross
# See them all one after another: ./tour.sh      Stop with Ctrl+C.
source "$(dirname "$0")/common.sh"
pick_any_world "${1:-office}"
require_clean

cat <<EOF

 WORLD: $WORLD   (robot spawns at $SX,$SY)
 $WORLD_DESC
 Robot: 0.30 x 0.25 m box, one forward RGB-D camera, wheel odometry, no lidar, no sensor noise.
$( [[ $WORLD == avoid_dynamic_* ]] && echo ' (The moving box only moves during ./avoid.sh, which starts the mover node.)' )
EOF
exec ros2 launch vacuum_bringup sim.launch.py "${WORLD_ARGS[@]}" spawn_x:="$SX" spawn_y:="$SY" use_rviz:=false
