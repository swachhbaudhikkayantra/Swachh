#!/usr/bin/env bash
# "Robot spins, map appears": the robot turns on the spot while SLAM builds the map live in RViz.
# It prints how many map cells are known before / during / after, so you can say
# "see, it turned this far and the map grew from X to Y cells".
# Usage: ./spin.sh [world] [turns] [rad/s]      default: office 1 0.5   (1 turn = 360 degrees)
# Afterwards the stack stays up so you can keep talking, or drive with ./steer.sh. Ctrl+C quits.
source "$(dirname "$0")/common.sh"
pick_world "${1:-office}"
TURNS="${2:-1}"
RATE="${3:-0.5}"
require_clean
trap 'stop_bg' EXIT
trap 'exit 130' INT TERM

DB="$HOME/.ros/swachh_demo_rtabmap.db"
rm -f "$DB"

start_bg sim ros2 launch vacuum_bringup sim.launch.py world:="$WORLD" use_rviz:=false \
    spawn_x:="$SX" spawn_y:="$SY"
start_rviz
wait_for_topic /clock 60 || true
sleep 6
start_bg slam ros2 launch vacuum_slam slam.launch.py environment:="$WORLD" use_rviz:=false database_path:="$DB"
wait_for_topic /rtabmap/map 60 || true
sleep 3

cat <<EOF

 SPIN IN PLACE ($WORLD): $TURNS turn(s) at $RATE rad/s.  Watch the map in RViz grow as the camera sweeps.

EOF
cd "$LOG_DIR" || exit 1
python3 - "$TURNS" "$RATE" <<'PY'
import math, sys, time
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry, OccupancyGrid

turns, rate = float(sys.argv[1]), abs(float(sys.argv[2]))
target = turns * 2 * math.pi

class Spin(Node):
    def __init__(self):
        super().__init__('demo_spin')
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_subscription(Odometry, '/odom', self.on_odom, 10)
        q = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                       reliability=ReliabilityPolicy.RELIABLE)
        self.create_subscription(OccupancyGrid, '/rtabmap/map', self.on_map, q)
        self.yaw0 = self.last = None
        self.turned = 0.0
        self.known = self.free = self.occ = 0
        self.t_print = 0.0
        self.done = False
        self.create_timer(0.1, self.tick)

    def on_odom(self, m):
        z, w = m.pose.pose.orientation.z, m.pose.pose.orientation.w
        yaw = 2 * math.atan2(z, w)
        if self.last is not None:
            d = (yaw - self.last + math.pi) % (2 * math.pi) - math.pi
            self.turned += abs(d)
        self.last = yaw

    def on_map(self, m):
        d = m.data
        self.known = sum(1 for v in d if v >= 0)
        self.free = sum(1 for v in d if v == 0)
        self.occ = sum(1 for v in d if v > 50)

    def line(self, tag):
        a = self.known * m_area
        print(f"[{tag}] turned {math.degrees(self.turned):6.0f} deg | map known {self.known:6d} cells "
              f"(~{self.known*0.0025:5.1f} m2: free {self.free}, wall {self.occ})", flush=True)

    def tick(self):
        t = Twist()
        if not self.done and self.last is not None:
            if self.turned >= target:
                self.done = True
                self.pub.publish(Twist())
                self.line('done  ')
                self.t_done = time.time()
                return
            t.angular.z = rate
            self.pub.publish(t)
            if time.time() - self.t_print > 3.0:
                self.t_print = time.time()
                self.line('spin  ')
        elif self.done:
            self.pub.publish(Twist())

m_area = 0.0025
rclpy.init()
n = Spin()
print("waiting for odometry and the first map ...", flush=True)
t0 = time.time()
while (n.last is None or n.known == 0) and time.time() - t0 < 60:
    rclpy.spin_once(n, timeout_sec=0.5)
n.line('before')
try:
    while not n.done:
        rclpy.spin_once(n, timeout_sec=0.2)
    t1 = time.time()
    while time.time() - t1 < 8:       # let SLAM publish the final update
        rclpy.spin_once(n, timeout_sec=0.2)
    n.line('after ')
except KeyboardInterrupt:
    n.pub.publish(Twist())
PY
echo
echo "[demo] Spin finished. The map is still live in RViz. Save it: ./savemap.sh $WORLD   Ctrl+C to quit."
while true; do sleep 5; done
