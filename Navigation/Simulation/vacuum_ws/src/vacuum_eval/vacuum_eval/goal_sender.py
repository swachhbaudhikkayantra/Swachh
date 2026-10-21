#!/usr/bin/env python3
"""Scripted NavigateToPose goal sender (spec 05 section 5.8)."""
import json
import math

import rclpy
import yaml
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from action_msgs.msg import GoalStatus
from std_msgs.msg import Bool, String


def wrap_angle(a):
    return math.atan2(math.sin(a), math.cos(a))


def world_to_map(goal, t_world_map):
    """se2_inverse(t_world_map) o goal; both (x, y, yaw)."""
    tx, ty, tyaw = t_world_map
    dx, dy = goal[0] - tx, goal[1] - ty
    c, s = math.cos(tyaw), math.sin(tyaw)
    return (c * dx + s * dy, -s * dx + c * dy, wrap_angle(goal[2] - tyaw))


def load_goals(path):
    with open(path) as f:
        data = yaml.safe_load(f)
    if isinstance(data, dict):
        data = data.get('goals', [])
    out = []
    for g in data:
        if isinstance(g, dict):
            out.append((float(g['x']), float(g['y']), float(g.get('yaw', 0.0))))
        else:
            out.append((float(g[0]), float(g[1]), float(g[2]) if len(g) > 2 else 0.0))
    return out


def map_result(status):
    if status == GoalStatus.STATUS_SUCCEEDED:
        return 'succeeded'
    if status == GoalStatus.STATUS_ABORTED:
        return 'nav_aborted'
    return 'nav_aborted' if status != GoalStatus.STATUS_CANCELED else 'canceled'


class GoalSender(Node):
    def __init__(self):
        super().__init__('goal_sender')
        self.declare_parameter('goals_file', '')
        self.declare_parameter('frame', 'map')
        self.declare_parameter('t_world_map', [0.0, 0.0, 0.0])
        self.declare_parameter('goal_timeout_sim_sec', 120.0)
        self.declare_parameter('inter_goal_wait_sec', 1.0)
        self.goals = load_goals(self.get_parameter('goals_file').value)
        self.frame = self.get_parameter('frame').value
        self.twm = list(self.get_parameter('t_world_map').value)
        self.timeout = float(self.get_parameter('goal_timeout_sim_sec').value)
        self.gap = float(self.get_parameter('inter_goal_wait_sec').value)
        self.ev_pub = self.create_publisher(String, '/eval/goal_events', QoSProfile(depth=50, reliability=ReliabilityPolicy.RELIABLE))
        self.done_pub = self.create_publisher(Bool, '/eval/done', QoSProfile(
            depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.idx = 0
        self.state = 'idle'
        self.t_wait = None
        self.goal_handle = None
        self.t_start = None
        self.timed_out = False
        self.create_timer(0.1, self.tick)

    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def emit(self, d):
        self.ev_pub.publish(String(data=json.dumps(d)))

    def tick(self):
        t = self.now()
        if self.state == 'idle':
            if self.idx >= len(self.goals):
                self.done_pub.publish(Bool(data=True))
                self.state = 'finished'
                self.get_logger().info('all goals done')
                return
            if not self.client.server_is_ready():
                return
            if self.t_wait is not None and t - self.t_wait < self.gap:
                return
            self.send(self.goals[self.idx], t)
        elif self.state == 'active' and not self.timed_out and t - self.t_start > self.timeout:
            self.timed_out = True
            if self.goal_handle is not None:
                self.goal_handle.cancel_goal_async()
            else:
                self.pending_timeout = True

    def send(self, goal, t):
        seq = self.idx + 1
        mx, my, myaw = world_to_map(goal, self.twm)
        msg = NavigateToPose.Goal()
        msg.pose.header.frame_id = self.frame
        msg.pose.header.stamp = self.get_clock().now().to_msg()
        msg.pose.pose.position.x, msg.pose.pose.position.y = mx, my
        msg.pose.pose.orientation.z = math.sin(myaw / 2)
        msg.pose.pose.orientation.w = math.cos(myaw / 2)
        self.cur = {'goal_seq': seq, 'src': 'scripted', 'x': mx, 'y': my, 'yaw': myaw,
                    'world_x': goal[0], 'world_y': goal[1], 'world_yaw': goal[2]}
        self.t_start = t
        self.timed_out = False
        self.pending_timeout = False
        self.goal_handle = None
        self.state = 'active'
        self.emit(dict(self.cur, event='started', t_start=t))
        self.client.send_goal_async(msg).add_done_callback(self.on_accept)

    def on_accept(self, fut):
        gh = fut.result()
        if not gh.accepted:
            self.finish('rejected', 0)
            return
        self.goal_handle = gh
        if self.pending_timeout:
            gh.cancel_goal_async()
        gh.get_result_async().add_done_callback(self.on_result)

    def on_result(self, fut):
        r = fut.result()
        code = int(getattr(r.result, 'error_code', 0))
        self.finish('timeout' if self.timed_out else map_result(r.status), code)

    def finish(self, result, code):
        self.emit(dict(self.cur, event='ended', result=result, t_start=self.t_start,
                       t_end=self.now(), nav2_error_code=code))
        self.idx += 1
        self.t_wait = self.now()
        self.state = 'idle'


def main(args=None):
    rclpy.init(args=args)
    node = GoalSender()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()


if __name__ == '__main__':
    main()
