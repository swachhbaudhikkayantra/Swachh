#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# cmd_vel_relay.py
# ─────────────────────────────────────────────────────────────────────────────
# Subscribes to the standard /cmd_vel (geometry_msgs/msg/Twist) published by
# teleop nodes and publishes a stamped /diff_drive_controller/cmd_vel
# (geometry_msgs/msg/TwistStamped) with correct simulation time headers.
# Required because Jazzy's diff_drive_controller requires stamped velocities.
# ─────────────────────────────────────────────────────────────────────────────

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TwistStamped

class CmdVelRelay(Node):
    def __init__(self):
        super().__init__('cmd_vel_relay')
        # input_topic lets a second instance stamp Nav2's smoothed output
        # (/cmd_vel_smoothed); the controller only subscribes to the stamped topic.
        self.declare_parameter('input_topic', '/cmd_vel')
        self.sub = self.create_subscription(
            Twist, self.get_parameter('input_topic').value, self._callback, 10)
        self.pub = self.create_publisher(
            TwistStamped, '/diff_drive_controller/cmd_vel', 10)
        self.get_logger().info("CmdVelRelay (Twist -> TwistStamped) started successfully.")

    def _callback(self, msg: Twist):
        stamped_msg = TwistStamped()
        stamped_msg.header.stamp = self.get_clock().now().to_msg()
        stamped_msg.header.frame_id = 'base_footprint'
        stamped_msg.twist = msg
        self.pub.publish(stamped_msg)

def main(args=None):
    rclpy.init(args=args)
    node = CmdVelRelay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
