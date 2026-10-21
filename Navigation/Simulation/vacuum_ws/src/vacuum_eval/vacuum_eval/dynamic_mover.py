#!/usr/bin/env python3
"""Drive a dynamic Gazebo model along waypoints via /model/<name>/cmd_vel (spec 09 section 9.6)."""
import math

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node


def velocity_towards(pos, wp, speed, stop_dist=0.05):
    """World-frame (vx, vy, reached) towards wp; zero within stop_dist."""
    dx, dy = wp[0] - pos[0], wp[1] - pos[1]
    d = math.hypot(dx, dy)
    if d <= stop_dist:
        return 0.0, 0.0, True
    return speed * dx / d, speed * dy / d, False


def parse_trigger(s):
    """'time' -> ('time', None); 'robot_x_beyond:<x>' -> ('robot_x', x)."""
    if s.startswith('robot_x_beyond:'):
        return 'robot_x', float(s.split(':', 1)[1])
    return 'time', None


class DynamicMover(Node):
    def __init__(self):
        super().__init__('dynamic_mover')
        self.declare_parameter('model', 'dyn_box_1')
        self.declare_parameter('waypoints', [0.0, 0.0])  # flat x,y,x,y...
        self.declare_parameter('speed', 0.25)
        self.declare_parameter('start_delay_s', 0.0)
        self.declare_parameter('start_trigger', 'time')
        self.declare_parameter('rate_hz', 20.0)
        m = self.get_parameter('model').value
        flat = list(self.get_parameter('waypoints').value)
        self.wps = [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]
        self.speed = float(self.get_parameter('speed').value)
        self.delay = float(self.get_parameter('start_delay_s').value)
        self.trig = parse_trigger(self.get_parameter('start_trigger').value)
        self.pos = None
        self.robot_x = None
        self.t_trigger = None
        self.started = False
        self.wi = 0
        self.pub = self.create_publisher(Twist, f'/model/{m}/cmd_vel', 10)
        self.create_subscription(Odometry, f'/ground_truth/model/{m}', self.on_dyn, 10)
        self.create_subscription(Odometry, '/ground_truth/odom', self.on_robot, 10)
        self.create_timer(1.0 / float(self.get_parameter('rate_hz').value), self.tick)

    def on_dyn(self, msg):
        p = msg.pose.pose.position
        self.pos = (p.x, p.y)

    def on_robot(self, msg):
        self.robot_x = msg.pose.pose.position.x

    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def tick(self):
        t = self.now()
        if self.pos is None or not self.wps:
            return
        if self.t_trigger is None:
            if self.trig[0] == 'time':
                self.t_trigger = t
            elif self.robot_x is not None and self.robot_x > self.trig[1]:
                self.t_trigger = t
            else:
                return
        if t - self.t_trigger < self.delay:
            return
        if not self.started:
            self.started = True
            self.get_logger().info(f'obstacle_start t={t:.3f}')
        tw = Twist()
        if self.wi < len(self.wps):
            vx, vy, reached = velocity_towards(self.pos, self.wps[self.wi], self.speed)
            if reached:
                self.wi += 1
            tw.linear.x, tw.linear.y = vx, vy
        self.pub.publish(tw)


def main(args=None):
    rclpy.init(args=args)
    node = DynamicMover()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()


if __name__ == '__main__':
    main()
