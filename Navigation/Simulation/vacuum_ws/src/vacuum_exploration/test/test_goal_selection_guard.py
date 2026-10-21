"""Pure-function tests for the goal-selection guards (no running ROS needed)."""
import sys
import types
from unittest import mock

try:
    import vacuum_exploration.exploration_manager as em
except Exception:
    for name in ['rclpy', 'rclpy.time', 'rclpy.action', 'rclpy.node', 'rclpy.qos',
                 'action_msgs', 'action_msgs.msg', 'geometry_msgs', 'geometry_msgs.msg',
                 'nav_msgs', 'nav_msgs.msg', 'nav2_msgs', 'nav2_msgs.action',
                 'std_msgs', 'std_msgs.msg', 'visualization_msgs',
                 'visualization_msgs.msg', 'tf2_ros']:
        sys.modules.setdefault(name, mock.MagicMock())
    sys.modules['rclpy.node'].Node = type('Node', (), {})
    import vacuum_exploration.exploration_manager as em


def test_goal_at_robot_skipped():
    assert em.goal_too_close_to_robot((1.0, 1.0), (1.1, 1.1), 0.30)


def test_goal_far_sent():
    assert not em.goal_too_close_to_robot((1.0, 1.0), (2.0, 1.0), 0.30)


def test_unknown_robot_pose_does_not_block():
    assert not em.goal_too_close_to_robot((1.0, 1.0), None, 0.30)


def test_frontier_size_in_metres():
    assert em.frontier_length_m(10, 0.05) == 0.5
    assert em.frontier_big_enough(10, 0.05, 0.5)
    assert not em.frontier_big_enough(8, 0.05, 0.5)


def test_no_gain_blacklists():
    assert em.no_information_gain((1, 1), [(1.2, 1.1)], 0.5, 1000, 1005, 10)


def test_gain_ok_when_map_grew():
    assert not em.no_information_gain((1, 1), [(1.2, 1.1)], 0.5, 1000, 1050, 10)


def test_no_gain_when_frontier_gone():
    assert not em.no_information_gain((1, 1), [(5, 5)], 0.5, 1000, 1000, 10)
