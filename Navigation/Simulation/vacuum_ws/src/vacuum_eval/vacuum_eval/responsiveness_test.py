#!/usr/bin/env python3
"""Step-response test node (spec 07 section 7.4). Writes responsiveness_events.csv."""
import csv
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool

DEADLINE = 0.5


def is_still(vx, wz):
    return abs(vx) <= 0.02 and abs(wz) <= 0.05


def onset_reached(variant, vx, wz, v_step, wz_step):
    if variant == 'fwd':
        return abs(vx) >= 0.5 * abs(v_step)
    return abs(wz) >= 0.5 * abs(wz_step)


def latency(t_a, t_b):
    return None if t_b is None else t_b - t_a


def trial_plan(n_trials):
    """[(trial, variant, direction)] alternating fwd/rot; fwd alternates +/-."""
    plan, fwd = [], 0
    for i in range(2 * n_trials):
        if i % 2 == 0:
            plan.append((i + 1, 'fwd', 1.0 if fwd % 2 == 0 else -1.0))
            fwd += 1
        else:
            plan.append((i + 1, 'rot', 1.0))
    return plan


class ResponsivenessTest(Node):
    def __init__(self):
        super().__init__('responsiveness_test')
        for k, v in (('n_trials', 10), ('v_step', 0.2), ('wz_step', 0.5), ('settle_s', 3.0),
                     ('run_s', 1.5), ('output_file', 'responsiveness_events.csv')):
            self.declare_parameter(k, v)
        g = lambda k: self.get_parameter(k).value
        self.v, self.wz = float(g('v_step')), float(g('wz_step'))
        self.settle, self.run_s = float(g('settle_s')), float(g('run_s'))
        self.plan = trial_plan(int(g('n_trials')))
        self.out = g('output_file')
        self.rows = []
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.done_pub = self.create_publisher(Bool, '/eval/done', QoSProfile(
            depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.create_subscription(Odometry, '/ground_truth/odom', self.on_odom, 50)
        self.vx = self.wzm = None
        self.t_still = None
        self.i = 0
        self.state = 'settle'
        self.t_a = None
        self.wall_a = None
        self.t_run = None
        self.cur = None
        self.create_timer(0.1, self.tick)

    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def twist(self, vx, wz):
        m = Twist()
        m.linear.x, m.angular.z = vx, wz
        return m

    def on_odom(self, msg):
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        vx, wz = msg.twist.twist.linear.x, msg.twist.twist.angular.z
        self.vx, self.wzm = vx, wz
        if self.state == 'settle':
            if is_still(vx, wz):
                if self.t_still is None:
                    self.t_still = t
            else:
                self.t_still = None
        elif self.state == 'wait_onset' and t > self.t_a:
            trial, variant, d = self.cur
            if onset_reached(variant, vx, wz, self.v, self.wz):
                self.record(trial, variant, 'cmd_motion', self.t_a, t, time.time())
                self.t_run = t
                self.state = 'run'
        elif self.state == 'wait_stop' and t > self.t_a:
            if is_still(vx, wz):
                self.record(self.cur[0], self.cur[1], 'stop', self.t_a, t, time.time())
                self.next_trial()

    def record(self, trial, variant, event, t_a, t_b, wall_b=None):
        L = latency(t_a, t_b)
        wa = self.wall_a
        wl = None if (wall_b is None or wa is None) else wall_b - wa
        self.rows.append([trial, variant, event, f'{t_a:.4f}',
                          '' if t_b is None else f'{t_b:.4f}', '' if L is None else f'{L:.4f}',
                          '' if wa is None else f'{wa:.4f}',
                          '' if wall_b is None else f'{wall_b:.4f}',
                          '' if wl is None else f'{wl:.4f}'])

    def next_trial(self):
        self.i += 1
        self.t_still = None
        self.state = 'settle'

    def tick(self):
        t = self.now()
        if self.state == 'settle':
            if self.i >= len(self.plan):
                self.finish()
                return
            if self.t_still is not None and self.vx is not None and t - self.t_still >= self.settle:
                self.cur = self.plan[self.i]
                _, variant, d = self.cur
                self.cmd = self.twist(d * self.v, 0.0) if variant == 'fwd' else self.twist(0.0, self.wz)
                self.t_a = self.now()
                self.wall_a = time.time()
                self.cmd_pub.publish(self.cmd)
                self.state = 'wait_onset'
        elif self.state == 'wait_onset':
            self.cmd_pub.publish(self.cmd)
            if t - self.t_a > 3 * DEADLINE:
                self.record(self.cur[0], self.cur[1], 'cmd_motion', self.t_a, None)
                self.t_run = t
                self.state = 'run'
        elif self.state == 'run':
            self.cmd_pub.publish(self.cmd)  # 10 Hz keepalive vs cmd_vel_timeout
            if t - self.t_run >= self.run_s:
                self.t_a = self.now()
                self.wall_a = time.time()
                self.cmd_pub.publish(self.twist(0.0, 0.0))
                self.state = 'wait_stop'
        elif self.state == 'wait_stop':
            self.cmd_pub.publish(self.twist(0.0, 0.0))
            if t - self.t_a > 3 * DEADLINE:
                self.record(self.cur[0], self.cur[1], 'stop', self.t_a, None)
                self.next_trial()

    def finish(self):
        with open(self.out, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['trial', 'variant', 'event', 't_a', 't_b', 'latency_s',
                        'wall_t_a', 'wall_t_b', 'wall_latency_s'])
            w.writerows(self.rows)
        self.done_pub.publish(Bool(data=True))
        self.state = 'finished'
        self.get_logger().info(f'wrote {self.out}')


def main(args=None):
    rclpy.init(args=args)
    node = ResponsivenessTest()
    try:
        while rclpy.ok() and node.state != 'finished':
            rclpy.spin_once(node, timeout_sec=0.1)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()


if __name__ == '__main__':
    main()
