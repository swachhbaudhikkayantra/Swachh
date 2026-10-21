#!/usr/bin/env python3
"""
ground_truth_node - robot ground-truth pose for evaluation (docs/specs/01 section 1.2).

Subscribes /ground_truth/odom_raw (nav_msgs/Odometry from the gz OdometryPublisher
plugin on the robot model, bridged by gz_bridge.yaml) and republishes the pose in
frame 'world' on /ground_truth/odom with a twist from finite differences.
(The ros_gz_bridge Pose_V -> TFMessage conversion drops entity names, so
/world/<name>/pose/info cannot identify the robot.)
"""

import math

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy


def wrap_angle(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


def quat_to_yaw(q) -> float:
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class GroundTruthNode(Node):

    def __init__(self):
        super().__init__('ground_truth_node')
        qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)
        self.create_subscription(Odometry, '/ground_truth/odom_raw', self._cb, qos)
        self._odom_pub = self.create_publisher(Odometry, '/ground_truth/odom', 10)

        self._prev = None            # (t_sec, x, y, yaw)
        self._last_seen_t = None
        self._logged_first = False
        self._warned = False
        self.create_timer(1.0, self._watchdog)

    def _stamp_sec(self, stamp) -> float:
        t = stamp.sec + stamp.nanosec * 1e-9
        if t == 0.0:
            t = self.get_clock().now().nanoseconds * 1e-9
        return t

    def _header_stamp(self, msg):
        s = msg.header.stamp
        if s.sec == 0 and s.nanosec == 0:
            return self.get_clock().now().to_msg()
        return s

    def _cb(self, msg: Odometry) -> None:
        self._publish_robot(msg)

    def _publish_robot(self, tf) -> None:
        x = tf.pose.pose.position.x
        y = tf.pose.pose.position.y
        yaw = quat_to_yaw(tf.pose.pose.orientation)
        t = self._stamp_sec(tf.header.stamp)
        self._last_seen_t = self.get_clock().now().nanoseconds * 1e-9
        self._warned = False

        odom = Odometry()
        odom.header.stamp = self._header_stamp(tf)
        odom.header.frame_id = 'world'
        odom.child_frame_id = 'base_footprint'
        odom.pose.pose.position.x = x
        odom.pose.pose.position.y = y
        odom.pose.pose.orientation.z = math.sin(yaw / 2.0)
        odom.pose.pose.orientation.w = math.cos(yaw / 2.0)

        if self._prev is not None:
            pt, px, py, pyaw = self._prev
            dt = t - pt
            if dt > 1e-4:
                dx, dy = x - px, y - py
                odom.twist.twist.linear.x = (dx * math.cos(yaw) + dy * math.sin(yaw)) / dt
                odom.twist.twist.linear.y = (-dx * math.sin(yaw) + dy * math.cos(yaw)) / dt
                odom.twist.twist.angular.z = wrap_angle(yaw - pyaw) / dt
                self._prev = (t, x, y, yaw)
            else:
                return                      # skip duplicate / out-of-order sample
        else:
            self._prev = (t, x, y, yaw)

        if not self._logged_first:
            self._logged_first = True
            self.get_logger().info(
                f'first ground-truth sample: x={x:.3f} y={y:.3f} yaw={yaw:.3f}')
        self._odom_pub.publish(odom)

    def _watchdog(self) -> None:
        now = self.get_clock().now().nanoseconds * 1e-9
        if self._last_seen_t is None or now - self._last_seen_t > 2.0:
            if not self._warned and now > 5.0:
                self._warned = True
                self.get_logger().warn(
                    'no samples on /ground_truth/odom_raw for >2 s')


def main(args=None):
    rclpy.init(args=args)
    node = GroundTruthNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
