#!/usr/bin/env bash
# Live one-line status of the explorer (run in a second terminal while ./explore.sh runs).
# Shows state, goals done/failed, frontiers left, elapsed time.
# It deliberately does NOT print the explorer's coverage_pct: the code says that is
# free/(free+unknown) of the live map, "NOT real coverage" -- do not quote it as the paper's coverage.
source "$(dirname "$0")/common.sh"
cd "$LOG_DIR" || exit 1
exec python3 - <<'EOF'
import json, time, rclpy
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
from std_msgs.msg import String

class S(Node):
    def __init__(self):
        super().__init__('demo_status')
        self.last = 0.0
        self.create_subscription(String, '/exploration/status', self.cb, 10)
    def cb(self, m):
        try:
            d = json.loads(m.data)
        except ValueError:
            return
        now = time.monotonic()
        if now - self.last < 2.0:   # the topic runs at ~10 Hz; print every 2 s
            return
        self.last = now
        print(f"t={d.get('elapsed_sec', 0):6.1f}s  state={d.get('state')}  "
              f"goals ok/failed={d.get('goals_completed')}/{d.get('goals_failed')}  "
              f"frontiers left={d.get('frontiers_remaining')}  blacklisted={d.get('blacklisted_count')}",
              flush=True)

rclpy.init()
n = S()
print("Waiting for /exploration/status ... (Ctrl+C to quit)")
try:
    rclpy.spin(n)
except (KeyboardInterrupt, ExternalShutdownException):
    pass
EOF
