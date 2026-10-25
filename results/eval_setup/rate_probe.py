import time, sys, rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image
from rosgraph_msgs.msg import Clock
rclpy.init(); n = Node('rate_probe')
q = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST, depth=10)
c = {'odom': 0, 'depth': 0, 'color': 0}; clk = []
n.create_subscription(Odometry, '/odom', lambda m: c.__setitem__('odom', c['odom']+1), q)
n.create_subscription(Image, '/camera/depth/image_rect_raw', lambda m: c.__setitem__('depth', c['depth']+1), q, raw=True) if False else None
n.create_subscription(Image, '/camera/depth/image_rect_raw', lambda m: c.__setitem__('depth', c['depth']+1), q)
n.create_subscription(Image, '/camera/color/image_raw', lambda m: c.__setitem__('color', c['color']+1), q)
n.create_subscription(Clock, '/clock', lambda m: clk.append(m.clock.sec + m.clock.nanosec*1e-9), q)
T = float(sys.argv[1]); t0 = time.time()
while time.time() - t0 < 8: rclpy.spin_once(n, timeout_sec=0.1)   # warm-up
for k in c: c[k] = 0
clk.clear(); t0 = time.time()
while time.time() - t0 < T: rclpy.spin_once(n, timeout_sec=0.05)
w = time.time() - t0; s = clk[-1] - clk[0] if len(clk) > 1 else float('nan')
print('wall %.1f s, sim %.1f s, rtf %.3f, clock msgs %d' % (w, s, s/w, len(clk)))
for k, v in c.items(): print('%s: %d msgs  = %.1f /wall-s  = %.1f /sim-s' % (k, v, v/w, v/s))
