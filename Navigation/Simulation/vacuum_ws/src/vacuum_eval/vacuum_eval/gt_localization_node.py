"""Perfect localization: publishes TF map->odom from ground truth.

map->odom = T_map_world * T_world_base(GT) * inv(T_odom_base).
Parameters map_origin_x/y/yaw: pose of the map frame in world. Default 0,0,0 because for gt-map
scripted runs the exported GT map frame equals world. SE(2) only.
"""
import math

import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from tf2_ros import Buffer, TransformBroadcaster, TransformListener


def _mul(a, b):
    c, s = math.cos(a[2]), math.sin(a[2])
    return (a[0] + c * b[0] - s * b[1], a[1] + s * b[0] + c * b[1], a[2] + b[2])


def _inv(a):
    c, s = math.cos(a[2]), math.sin(a[2])
    return (-(c * a[0] + s * a[1]), s * a[0] - c * a[1], -a[2])


def _wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


def compose_map_to_odom(map_in_world, base_in_world, base_in_odom):
    """Each arg (x, y, yaw). Returns map->odom (x, y, yaw), yaw wrapped to (-pi, pi]."""
    t_map_world = _inv(map_in_world)
    r = _mul(_mul(t_map_world, base_in_world), _inv(base_in_odom))
    return (r[0], r[1], _wrap(r[2]))


def yaw_of(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


class GtLocalization(Node):
    def __init__(self):
        super().__init__('gt_localization')
        self._o = tuple(self.declare_parameter(k, 0.0).value
                        for k in ('map_origin_x', 'map_origin_y', 'map_origin_yaw'))
        self._gt = None
        self._buf = Buffer()
        self._lst = TransformListener(self._buf, self)
        self._br = TransformBroadcaster(self)
        self.create_subscription(Odometry, '/ground_truth/odom', self._cb, 10)
        self.create_timer(1.0 / 30.0, self._tick)

    def _cb(self, m):
        p = m.pose.pose
        self._gt = ((p.position.x, p.position.y, yaw_of(p.orientation)), m.header.stamp)

    def _tick(self):
        if self._gt is None:
            return
        pose, stamp = self._gt
        try:
            t = self._buf.lookup_transform('odom', 'base_footprint', rclpy.time.Time())
        except Exception:  # noqa: BLE001
            return
        tr = t.transform
        x, y, yaw = compose_map_to_odom(self._o, pose,
                                        (tr.translation.x, tr.translation.y, yaw_of(tr.rotation)))
        out = TransformStamped()
        out.header.stamp = stamp
        out.header.frame_id = 'map'
        out.child_frame_id = 'odom'
        out.transform.translation.x = x
        out.transform.translation.y = y
        out.transform.rotation.z = math.sin(yaw / 2)
        out.transform.rotation.w = math.cos(yaw / 2)
        self._br.sendTransform(out)


def main():
    rclpy.init()
    n = GtLocalization()
    try:
        rclpy.spin(n)
    except KeyboardInterrupt:
        pass
    n.destroy_node()
    rclpy.try_shutdown()
