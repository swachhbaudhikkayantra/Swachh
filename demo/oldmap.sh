#!/usr/bin/env bash
# Show the COMPLETED map from the archived evaluation run (no simulation needed).
#   * RViz (demo.rviz) shows the finished map and the path the robot drove, like a live run.
#   * A picture window shows the true floor plan next to the explored maps of all 3 seeds.
# Usage: ./oldmap.sh [world]      worlds with archived exploration runs: office multi_room_loop maze_dead_ends
#   default: office. Best seed is picked automatically (office 101: 92 %, multi_room_loop 103: 89 %,
#   maze_dead_ends 102: 40 %).  Override: SEED=102 ./oldmap.sh office
# Source: ~/Swachh/results/runs/quick_exploration_noise/<world>/frontier/seed_N/  (2026-10-25 campaign,
#         odometry noise on). Ctrl+C quits.
source "$(dirname "$0")/common.sh"
W="${1:-office}"
case "$W" in
    office) ROW=0; BEST=101 ;;
    multi_room_loop) ROW=1; BEST=103 ;;
    maze_dead_ends) ROW=2; BEST=102 ;;
    *) echo "No archived exploration run for '$W'. Choose: office multi_room_loop maze_dead_ends"; exit 1 ;;
esac
SEED="${SEED:-$BEST}"
RUN="$REPO/results/runs/quick_exploration_noise/$W/frontier/seed_$SEED"
[[ -f $RUN/maps/final_map.npz ]] || { echo "Missing $RUN/maps/final_map.npz"; exit 1; }
FIG="$REPO/docs/paper_out/figures/fig_actual_vs_explored.png"

install_cleanup

start_bg rviz ros2 run rviz2 rviz2 -d "$RVIZ_CFG" --ros-args -p use_sim_time:=false

cd "$LOG_DIR" || exit 1
start_bg publisher python3 - "$RUN" "$W" "$SEED" "$ROW" "$FIG" <<'PY'
import json, sys, csv, time
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from nav_msgs.msg import OccupancyGrid
from visualization_msgs.msg import Marker
from geometry_msgs.msg import Point

run, world, seed, row, fig = sys.argv[1:6]
d = np.load(run + '/maps/final_map.npz')
data = d['data'].astype(np.int8)
res = float(d['resolution'])
s = json.load(open(run + '/summary.json'))
print(f"{world} seed {seed}: coverage {s.get('coverage_explored_pct'):.1f}%  "
      f"completeness {s.get('map_completeness_pct'):.1f}%  ATE {s.get('ate_fixed_rmse_m')}", flush=True)

pts = []
with open(run + '/trajectory.csv') as f:
    for r in csv.DictReader(f):
        try:
            pts.append((float(r['est_x']), float(r['est_y'])))
        except (KeyError, ValueError):
            pass

rclpy.init()
n = Node('demo_oldmap')
q = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL, reliability=ReliabilityPolicy.RELIABLE)
mp = n.create_publisher(OccupancyGrid, '/demo/archived_map', q)
tp = n.create_publisher(Marker, '/exploration/trajectory', q)
g = OccupancyGrid()
g.header.frame_id = 'map'
g.info.resolution = res
g.info.width, g.info.height = data.shape[1], data.shape[0]
g.info.origin.position.x = float(d['origin_x'])
g.info.origin.position.y = float(d['origin_y'])
g.info.origin.orientation.w = 1.0
g.data = data.flatten().tolist()
m = Marker()
m.header.frame_id = 'map'
m.ns, m.id, m.type, m.action = 'oldrun', 0, Marker.LINE_STRIP, Marker.ADD
m.scale.x = 0.03
m.color.r, m.color.g, m.color.b, m.color.a = 0.2, 0.5, 1.0, 1.0
m.pose.orientation.w = 1.0
m.points = [Point(x=x, y=y, z=0.02) for x, y in pts[::3]]
t0 = time.time()
while rclpy.ok():
    g.header.stamp = n.get_clock().now().to_msg()
    m.header.stamp = g.header.stamp
    mp.publish(g); tp.publish(m)
    time.sleep(1.0)
PY

# Picture window: true floor plan vs explored maps (paper Fig. 6), cropped to this world's row.
if [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" && -f $FIG ]]; then
    start_bg figure python3 - "$FIG" "$ROW" "$W" <<'PY'
import sys
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
fig, row, world = sys.argv[1], int(sys.argv[2]), sys.argv[3]
im = mpimg.imread(fig)
h = im.shape[0]
y0, y1 = int(h * (0.03 + row * 0.318)), int(h * (0.03 + (row + 1) * 0.318) + 0.01 * h)
f = plt.figure(figsize=(15, 4.6))
f.canvas.manager.set_window_title(f"{world}: actual floor plan vs explored maps (paper Fig. 6)")
ax = f.add_axes([0, 0, 1, 1]); ax.axis('off'); ax.imshow(im[y0:y1])
plt.show()
PY
fi

cat <<EOF

 COMPLETED MAP: $W, seed $SEED  (from the 2026-10-25 evaluation run, odometry noise on)
 RViz : the finished map and the blue line is where the robot drove. Grey = never seen.
 Window: true floor plan (left) next to the explored maps of all 3 seeds.
 Say  : coverage $W seed $SEED is in the line above. Warped walls = SLAM drift (maps are placed using the
        start pose only). Other seeds: SEED=102 ./oldmap.sh $W
 Note : the maze row shows the failure honestly: in 2 of 3 runs the explorer never moved.

EOF
while true; do sleep 5; done
