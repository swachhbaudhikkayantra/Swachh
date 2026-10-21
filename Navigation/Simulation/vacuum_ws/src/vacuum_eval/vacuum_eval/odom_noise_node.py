#!/usr/bin/env python3
"""
odom_noise_node - evaluation odometry with controllable drift (docs/specs/01 section 1.3).

Sits in the odometry path when sim.launch.py is started with odom_mode:=eval:
  /diff_drive_controller/odom (clean) -> this node -> /odom + TF odom->base_footprint
The controller's own odom TF is disabled in that mode, so RTAB-Map and Nav2 see
exactly one odom source. With enable_noise:=false the output equals the input.

Noise acts on motion increments and is temporally correlated (independent
per-message noise would average out and produce no drift):
  once per run (first two draws of default_rng(seed)):
    b_lin = 1 + sigma_scale_lin * N(0,1)      persistent distance scale error
    b_ang = 1 + sigma_scale_ang * N(0,1)      persistent rotation scale error
  per message (two further draws e1, e2 ~ N(0,1), always consumed):
    d'      = d * b_lin
    dtheta' = dtheta * b_ang + sigma_rw_per_sqrt_m * sqrt(|d|) * e1
                             + sigma_rw_per_sqrt_rad * sqrt(|dtheta|) * e2
  (random-walk variance proportional to distance travelled / angle turned).
"""

import math

import numpy as np
import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from tf2_ros import TransformBroadcaster


def wrap_angle(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


def quat_to_yaw(q) -> float:
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class OdomNoiseNode(Node):

    def __init__(self):
        super().__init__('odom_noise_node')
        self.declare_parameter('enable_noise', False)
        self.declare_parameter('seed', 0)
        self.declare_parameter('sigma_scale_lin', 0.02)
        self.declare_parameter('sigma_scale_ang', 0.03)
        self.declare_parameter('sigma_rw_per_sqrt_m', 0.02)
        self.declare_parameter('sigma_rw_per_sqrt_rad', 0.03)
        self.declare_parameter('publish_tf', True)

        self._rng = np.random.default_rng(int(self.get_parameter('seed').value))
        z = self._rng.normal(size=2)
        self._b_lin = 1.0 + float(self.get_parameter('sigma_scale_lin').value) * z[0]
        self._b_ang = 1.0 + float(self.get_parameter('sigma_scale_ang').value) * z[1]
        self._prev_clean = None          # (x, y, yaw) of the previous clean sample
        self._pose = None                # noisy (X, Y, Theta)
        self._n = 0

        qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)
        self._pub = self.create_publisher(Odometry, '/odom', qos)
        self._tf = TransformBroadcaster(self)
        self.create_subscription(
            Odometry, '/diff_drive_controller/odom', self._cb, qos)
        self.get_logger().info(
            f"odom_noise_node: enable_noise={self.get_parameter('enable_noise').value} "
            f"seed={self.get_parameter('seed').value} "
            f'b_lin={self._b_lin:.4f} b_ang={self._b_ang:.4f}')

    def _cb(self, msg: Odometry) -> None:
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y
        yaw = quat_to_yaw(msg.pose.pose.orientation)

        enable = bool(self.get_parameter('enable_noise').value)
        s_rw_m = float(self.get_parameter('sigma_rw_per_sqrt_m').value)
        s_rw_r = float(self.get_parameter('sigma_rw_per_sqrt_rad').value)

        if self._prev_clean is None:
            self._pose = (x, y, yaw)
        else:
            px, py, pyaw = self._prev_clean
            dxw, dyw = x - px, y - py
            dx = math.cos(pyaw) * dxw + math.sin(pyaw) * dyw
            dy = -math.sin(pyaw) * dxw + math.cos(pyaw) * dyw
            dth = wrap_angle(yaw - pyaw)
            d = math.hypot(dx, dy)

            e1, e2 = self._rng.normal(size=2)         # always consume the draws
            if enable:
                dx, dy = dx * self._b_lin, dy * self._b_lin
                dth = (dth * self._b_ang + s_rw_m * math.sqrt(d) * e1
                       + s_rw_r * math.sqrt(abs(dth)) * e2)

            X, Y, T = self._pose
            X += math.cos(T) * dx - math.sin(T) * dy
            Y += math.sin(T) * dx + math.cos(T) * dy
            T = wrap_angle(T + dth)
            self._pose = (X, Y, T)
        self._prev_clean = (x, y, yaw)
        self._n += 1

        X, Y, T = self._pose
        out = Odometry()
        out.header = msg.header
        out.child_frame_id = msg.child_frame_id
        out.pose.pose.position.x = X
        out.pose.pose.position.y = Y
        out.pose.pose.position.z = msg.pose.pose.position.z
        out.pose.pose.orientation.z = math.sin(T / 2.0)
        out.pose.pose.orientation.w = math.cos(T / 2.0)
        out.pose.covariance = msg.pose.covariance
        out.twist = msg.twist
        self._pub.publish(out)

        if self.get_parameter('publish_tf').value:
            tf = TransformStamped()
            tf.header = msg.header
            tf.child_frame_id = msg.child_frame_id
            tf.transform.translation.x = X
            tf.transform.translation.y = Y
            tf.transform.rotation.z = math.sin(T / 2.0)
            tf.transform.rotation.w = math.cos(T / 2.0)
            self._tf.sendTransform(tf)


def main(args=None):
    rclpy.init(args=args)
    node = OdomNoiseNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
