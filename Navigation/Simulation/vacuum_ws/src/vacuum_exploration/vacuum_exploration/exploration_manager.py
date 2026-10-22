#!/usr/bin/env python3
"""
exploration_manager.py  —  Stage 4B: Autonomous Exploration Orchestrator
─────────────────────────────────────────────────────────────────────────
The Exploration Manager owns the exploration lifecycle.

FSM States:
  IDLE              → Initial state. Transitions immediately to WAITING_FOR_MAP.
  WAITING_FOR_MAP   → Waits for RTAB-Map to publish a map with free cells.
  DETECT_FRONTIERS  → Checks the latest frontier list from FrontierDetector.
  SELECT_GOAL       → Uses GoalSelector to pick the best non-blacklisted frontier.
  SEND_GOAL         → Sends NavigateToPose action goal to Nav2.
  NAVIGATING        → Waits for Nav2 result. Monitors timeout + oscillation.
  GOAL_REACHED      → Records success, resets counters, loops back.
  RECOVERING        → Records failure, blacklists frontier, loops back.
  FINISHED          → All completion conditions satisfied. Exploration done.

Recovery logic:
  - Goal timeout         → cancel goal → blacklist frontier → RECOVERING
  - Nav2 ABORTED         → blacklist frontier → RECOVERING
  - Oscillation detected → cancel goal → blacklist frontier → RECOVERING
  - 3 consecutive failures → tighten min_frontier_size threshold temporarily

Completion conditions (ALL must be true):
  1. No frontiers for N consecutive detection cycles
  2. Map has not grown (free cells) by > threshold in last patience_sec
  3. Robot is stationary (velocity < threshold)

Blacklist persistence:
  Failed frontiers are stored with expiry timestamp.
  After blacklist_expiry_sec, the frontier is eligible again.

Publications:
  /exploration/status       (std_msgs/String — JSON)  — FSM state + metrics
  /exploration/goal_events  (std_msgs/String — JSON)  — one event at goal start and end
  /exploration/finished     (std_msgs/Bool, transient-local) — true once FINISHED
"""

import json
import math
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, List, Optional, Set

import numpy as np
from scipy import ndimage
import rclpy
import rclpy.time
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseArray, PoseStamped, Twist
from nav_msgs.msg import OccupancyGrid, Odometry
from nav2_msgs.action import NavigateToPose
from std_msgs.msg import Bool, String
from visualization_msgs.msg import Marker, MarkerArray

from tf2_ros import Buffer, TransformListener

from vacuum_exploration.frontier_detector import Frontier
from vacuum_exploration.goal_selector import GoalSelector


# ─────────────────────────────────────────────────────────────────────────────
#  Pure decision helpers (no ROS; unit-tested in test_goal_selection_guard.py)
# ─────────────────────────────────────────────────────────────────────────────

def goal_too_close_to_robot(goal_xy, robot_xy, min_goal_distance: float) -> bool:
    """True if the snapped goal is within min_goal_distance of the robot (same frame)."""
    if robot_xy is None:
        return False
    return math.hypot(goal_xy[0] - robot_xy[0], goal_xy[1] - robot_xy[1]) < min_goal_distance


def frontier_length_m(size_cells: int, resolution: float) -> float:
    """Frontier length in metres = cells * map resolution."""
    return size_cells * resolution


def frontier_big_enough(size_cells: int, resolution: float, min_size_m: float) -> bool:
    return frontier_length_m(size_cells, resolution) >= min_size_m


def no_information_gain(reached_xy, frontier_xys, blacklist_radius: float,
                        free_at_send: int, free_now: int, growth_threshold: int) -> bool:
    """After a SUCCEEDED goal: True if a frontier near the reached one is still present
    and the map grew by fewer than growth_threshold free cells since the goal was sent."""
    still_there = any(
        math.hypot(fx - reached_xy[0], fy - reached_xy[1]) <= blacklist_radius
        for fx, fy in frontier_xys)
    return still_there and (free_now - free_at_send) < growth_threshold


# ─────────────────────────────────────────────────────────────────────────────
#  FSM State Enum
# ─────────────────────────────────────────────────────────────────────────────

class ExplorationState(Enum):
    IDLE              = 'IDLE'
    WAITING_FOR_MAP   = 'WAITING_FOR_MAP'
    DETECT_FRONTIERS  = 'DETECT_FRONTIERS'
    SELECT_GOAL       = 'SELECT_GOAL'
    SEND_GOAL         = 'SEND_GOAL'
    NAVIGATING        = 'NAVIGATING'
    GOAL_REACHED      = 'GOAL_REACHED'
    RECOVERING        = 'RECOVERING'
    FINISHED          = 'FINISHED'


# ─────────────────────────────────────────────────────────────────────────────
#  Blacklisted Frontier Entry
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BlacklistEntry:
    """Record of a frontier that has been marked as temporarily unreachable."""
    frontier_id:       int
    centroid_x:        float
    centroid_y:        float
    failure_count:     int
    last_failure_time: float  # ROS time in seconds
    expiry_sec:        float = 60.0

    def is_expired(self, current_time: float) -> bool:
        return (current_time - self.last_failure_time) > self.expiry_sec


# ─────────────────────────────────────────────────────────────────────────────
#  Exploration Manager Node
# ─────────────────────────────────────────────────────────────────────────────

class ExplorationManager(Node):

    def __init__(self):
        super().__init__('exploration_manager')

        # ── Parameters ────────────────────────────────────────────────────────
        self.declare_parameter('goal_timeout',                   30.0)
        self.declare_parameter('retry_count',                    3)
        self.declare_parameter('blacklist_expiry_sec',           60.0)
        self.declare_parameter('no_frontier_consecutive_checks', 5)
        self.declare_parameter('map_growth_patience_sec',        15.0)
        self.declare_parameter('map_growth_threshold',           10)
        self.declare_parameter('stationary_vel_threshold',       0.02)
        self.declare_parameter('oscillation_distance',           0.30)
        self.declare_parameter('oscillation_timeout_sec',        15.0)
        self.declare_parameter('blacklist_radius',               0.50)
        # RTAB-Map publishes no map until the robot has moved (verified 2026-10-20), so
        # with no map after bootstrap_wait_sec the robot turns in place for bootstrap_spin_sec.
        # Frontier centroids lie on the edge of unknown space and are often unplannable
        # ("no valid path found"). Goals are snapped to the nearest known-free cell
        # that is at least goal_snap_clearance_m from any non-free cell.
        self.declare_parameter('goal_snap_clearance_m',          0.30)
        self.declare_parameter('goal_snap_max_m',                1.50)
        self.declare_parameter('bootstrap_wait_sec',             3.0)
        self.declare_parameter('bootstrap_spin_sec',             8.0)
        self.declare_parameter('bootstrap_spin_wz',              0.4)
        # Goal selector weights
        self.declare_parameter('weight_info_gain',               1.0)
        self.declare_parameter('weight_distance',                1.5)
        self.declare_parameter('weight_obstacle_penalty',        0.8)
        self.declare_parameter('min_goal_distance',              0.30)
        # Manager-side minimum frontier length in METRES (= detector cells * map resolution).
        # The detector's own min_frontier_size is in cells; this one is resolution-independent.
        self.declare_parameter('min_frontier_size_m',            0.5)

        p = lambda name: self.get_parameter(name).value
        self._goal_timeout             = p('goal_timeout')
        self._retry_count              = p('retry_count')
        self._blacklist_expiry         = p('blacklist_expiry_sec')
        self._no_frontier_checks_req   = p('no_frontier_consecutive_checks')
        self._map_growth_patience      = p('map_growth_patience_sec')
        self._map_growth_threshold     = p('map_growth_threshold')
        self._stationary_vel_thresh    = p('stationary_vel_threshold')
        self._oscillation_dist         = p('oscillation_distance')
        self._oscillation_timeout      = p('oscillation_timeout_sec')
        self._blacklist_radius         = p('blacklist_radius')
        self._snap_clearance           = p('goal_snap_clearance_m')
        self._snap_max                 = p('goal_snap_max_m')
        self._bootstrap_wait           = p('bootstrap_wait_sec')
        self._bootstrap_spin           = p('bootstrap_spin_sec')
        self._bootstrap_wz             = p('bootstrap_spin_wz')
        self._min_goal_distance        = p('min_goal_distance')
        self._min_frontier_size_m      = p('min_frontier_size_m')
        self._wait_map_since: Optional[float] = None
        self._frontiers_skipped = 0
        self._frontier_msgs = 0                  # detection cycles received
        self._pending_gain_check = None          # (x, y, free_at_send, msg_count_at_success)
        self._free_at_send = 0
        self._tf_warned = False
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)

        # ── Goal Selector ─────────────────────────────────────────────────────
        self._selector = GoalSelector(
            weight_info_gain=        p('weight_info_gain'),
            weight_distance=         p('weight_distance'),
            weight_obstacle_penalty= p('weight_obstacle_penalty'),
            min_goal_distance=       p('min_goal_distance'),
        )

        # ── FSM State ──────────────────────────────────────────────────────────
        self._state = ExplorationState.IDLE

        # ── Frontier data (from FrontierDetector) ─────────────────────────────
        self._frontiers:          List[Frontier] = []
        self._current_frontier:   Optional[Frontier] = None

        # ── Blacklist ─────────────────────────────────────────────────────────
        self._blacklist:          List[BlacklistEntry] = []
        self._blacklisted_ids:    Set[int] = set()
        self._failure_counter:    dict = {}  # frontier_id → count

        # ── Nav2 Action Client ────────────────────────────────────────────────
        self._nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self._goal_handle = None
        self._goal_result: Optional[int] = None  # GoalStatus code
        self._goal_accepted = False
        self._goal_seq = 0                       # guards stale callbacks (also bumped on cancel)
        self._event_seq = 0                      # 1-based goal number used in goal_events
        self._goal_rejected = False
        self._goal_error_code = 0
        self._goal_sent_time: Optional[float] = None
        self._goal_xy = (0.0, 0.0)                # snapped goal actually sent
        self._osc_ref = None                     # (x, y, t) reference pose for oscillation check
        self._robot_ang_vel = 0.0

        # ── Metrics / tracking ────────────────────────────────────────────────
        self._goals_sent      = 0
        self._goals_completed = 0
        self._goals_failed    = 0
        self._session_start   = self.get_clock().now().nanoseconds / 1e9

        # ── Navigation timing ─────────────────────────────────────────────────
        self._goal_start_time:     Optional[float] = None
        self._last_robot_x:        Optional[float] = None
        self._last_robot_y:        Optional[float] = None
        self._last_move_time:      Optional[float] = None

        # ── Completion tracking ───────────────────────────────────────────────
        self._no_frontier_count  = 0
        self._map_free_history:  Deque[tuple] = deque(maxlen=60)  # (time, free_cells)
        self._robot_linear_vel   = 0.0

        # ── Map data ─────────────────────────────────────────────────────────
        self._latest_map: Optional[OccupancyGrid] = None
        self._map_free = 0
        self._map_unknown = 0

        # ── Subscriptions ─────────────────────────────────────────────────────
        map_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.VOLATILE,
            depth=1,
        )
        self.create_subscription(
            OccupancyGrid, '/rtabmap/map', self._map_callback, map_qos)
        self.create_subscription(
            PoseArray, '/frontiers/centroids', self._frontiers_callback, 10)
        self.create_subscription(
            Odometry, '/odom', self._odom_callback, 10)

        # ── Publishers ────────────────────────────────────────────────────────
        self._status_pub        = self.create_publisher(String, '/exploration/status', 10)
        self._selected_goal_pub = self.create_publisher(PoseStamped, '/exploration/current_goal', 10)
        self._selected_marker_pub = self.create_publisher(MarkerArray, '/exploration/selected_marker', 10)
        self._goal_events_pub = self.create_publisher(
            String, '/exploration/goal_events',
            QoSProfile(depth=50, reliability=QoSReliabilityPolicy.RELIABLE))
        self._cmd_pub = self.create_publisher(Twist, '/cmd_vel_nav', 10)
        self._finished_pub = self.create_publisher(
            Bool, '/exploration/finished',
            QoSProfile(depth=1, reliability=QoSReliabilityPolicy.RELIABLE,
                       durability=QoSDurabilityPolicy.TRANSIENT_LOCAL))

        # ── FSM Timer (10 Hz) ─────────────────────────────────────────────────
        self._fsm_timer = self.create_timer(0.10, self._fsm_tick)

        self.get_logger().info('ExplorationManager started. Waiting for Nav2...')

    # ── Subscription callbacks ─────────────────────────────────────────────────

    def _map_callback(self, msg: OccupancyGrid) -> None:
        self._latest_map = msg
        arr = np.asarray(msg.data, dtype=np.int8)
        free = int(np.count_nonzero(arr == 0))
        self._map_free = free
        self._map_unknown = int(np.count_nonzero(arr == -1))
        t = self.get_clock().now().nanoseconds / 1e9
        self._map_free_history.append((t, free))

    def _frontiers_callback(self, msg: PoseArray) -> None:
        """Reconstruct Frontier list from PoseArray published by FrontierDetector."""
        frontiers = []
        self._frontier_msgs += 1
        res = self._latest_map.info.resolution if self._latest_map is not None else None
        for i, pose in enumerate(msg.poses):
            if res is not None and not frontier_big_enough(
                    max(1, int(pose.position.z)), res, self._min_frontier_size_m):
                continue
            frontiers.append(Frontier(
                id=len(frontiers),
                centroid_x=pose.position.x,
                centroid_y=pose.position.y,
                size=max(1, int(pose.position.z)),  # size encoded in z
            ))
        self._frontiers = frontiers

    def _odom_callback(self, msg: Odometry) -> None:
        self._robot_linear_vel = abs(msg.twist.twist.linear.x)
        self._robot_ang_vel = abs(msg.twist.twist.angular.z)
        rx = msg.pose.pose.position.x
        ry = msg.pose.pose.position.y
        t  = self.get_clock().now().nanoseconds / 1e9

        # Progress = displacement of at least `oscillation_distance` from a reference
        # pose; in-place rotation (recoveries) also counts as activity.
        if self._osc_ref is None:
            self._osc_ref = (rx, ry, t)
        else:
            ox, oy, _ = self._osc_ref
            if math.hypot(rx - ox, ry - oy) >= self._oscillation_dist:
                self._osc_ref = (rx, ry, t)
                self._last_move_time = t
        if self._robot_ang_vel >= 0.05:
            self._last_move_time = t

        self._last_robot_x = rx
        self._last_robot_y = ry

    def _robot_xy_map(self):
        """Robot (x, y) in the map frame via TF map->base_footprint.

        /odom is in the odom frame, which drifts relative to map once SLAM corrects it, so
        it must not be compared with map-frame goals. Falls back to odom if TF is missing.
        """
        try:
            t = self._tf_buffer.lookup_transform('map', 'base_footprint', rclpy.time.Time())
            return (t.transform.translation.x, t.transform.translation.y)
        except Exception:
            if not self._tf_warned:
                self._tf_warned = True
                self.get_logger().warning('TF map->base_footprint unavailable; using odom pose.')
            if self._last_robot_x is None:
                return None
            return (self._last_robot_x, self._last_robot_y)

    # ── FSM tick ───────────────────────────────────────────────────────────────

    def _fsm_tick(self) -> None:
        current_time = self.get_clock().now().nanoseconds / 1e9

        # Purge expired blacklist entries
        self._purge_blacklist(current_time)

        # State machine
        if self._state == ExplorationState.IDLE:
            self.get_logger().info('Exploration started. Waiting for map...')
            self._state = ExplorationState.WAITING_FOR_MAP

        elif self._state == ExplorationState.WAITING_FOR_MAP:
            if self._wait_map_since is None:
                self._wait_map_since = current_time
            if self._map_has_free_cells():
                self.get_logger().info('Map received with free cells. Beginning frontier detection.')
                self._last_move_time = current_time
                self._state = ExplorationState.DETECT_FRONTIERS
            else:
                waited = current_time - self._wait_map_since
                if self._bootstrap_wait <= waited < self._bootstrap_wait + self._bootstrap_spin:
                    tw = Twist()
                    tw.angular.z = self._bootstrap_wz
                    self._cmd_pub.publish(tw)
                    if waited - self._bootstrap_wait < 0.15:
                        self.get_logger().info('No map yet - turning in place to start SLAM.')

        elif self._state == ExplorationState.DETECT_FRONTIERS:
            self._check_no_gain(current_time)
            if self._frontiers:
                self._no_frontier_count = 0
                self._state = ExplorationState.SELECT_GOAL
            else:
                self._no_frontier_count += 1
                self.get_logger().info(
                    f'No frontiers detected ({self._no_frontier_count}/'
                    f'{self._no_frontier_checks_req})'
                )
                if self._check_completion(current_time):
                    self._state = ExplorationState.FINISHED

        elif self._state == ExplorationState.SELECT_GOAL:
            rxy = self._robot_xy_map() or (0.0, 0.0)
            robot_x, robot_y = rxy
            chosen = self._selector.select_best(
                frontiers=self._frontiers,
                robot_x=robot_x,
                robot_y=robot_y,
                blacklisted_ids=self._effective_blacklisted_ids(),
                occupancy_grid=self._latest_map,
            )
            if chosen is None:
                self.get_logger().warning('No eligible frontier after scoring. Re-detecting...')
                self._state = ExplorationState.DETECT_FRONTIERS
            else:
                self._current_frontier = chosen
                self.get_logger().info(
                    f'Selected frontier #{chosen.id} at '
                    f'({chosen.centroid_x:.2f}, {chosen.centroid_y:.2f}) '
                    f'size={chosen.size}'
                )
                self._publish_selected_marker(chosen)
                self._state = ExplorationState.SEND_GOAL

        elif self._state == ExplorationState.SEND_GOAL:
            if not self._nav_client.wait_for_server(timeout_sec=5.0):
                self.get_logger().error('Nav2 NavigateToPose action server not available!')
                self._state = ExplorationState.DETECT_FRONTIERS
                return
            snapped = self._snap_goal(self._current_frontier)
            if snapped is None:
                self.get_logger().warning(
                    f'No free cell with {self._snap_clearance:.2f} m clearance within '
                    f'{self._snap_max:.1f} m of frontier #{self._current_frontier.id}; '
                    'blacklisting without sending a goal.')
                self._blacklist_frontier(self._current_frontier, current_time, 'no_snap')
                self._current_frontier = None
                self._state = ExplorationState.DETECT_FRONTIERS
                return
            if goal_too_close_to_robot(snapped, self._robot_xy_map(), self._min_goal_distance):
                self.get_logger().warning(
                    f'Snapped goal ({snapped[0]:.2f}, {snapped[1]:.2f}) for frontier '
                    f'#{self._current_frontier.id} is within {self._min_goal_distance:.2f} m '
                    'of the robot; not sending.')
                self._blacklist_frontier(self._current_frontier, current_time, 'goal_at_robot')
                self._frontiers_skipped += 1
                self._current_frontier = None
                self._state = ExplorationState.DETECT_FRONTIERS
                return
            self._goal_xy = snapped
            self._free_at_send = self._map_free
            self._send_nav_goal(self._current_frontier)
            self._goal_start_time = current_time
            self._last_move_time  = current_time
            self._osc_ref = None
            self._goals_sent += 1
            self._emit_goal_event('started', current_time)
            self._state = ExplorationState.NAVIGATING

        elif self._state == ExplorationState.NAVIGATING:
            # Check goal result
            if self._goal_result is not None:
                if self._goal_result == GoalStatus.STATUS_SUCCEEDED:
                    self._emit_goal_event('ended', current_time, 'succeeded')
                    f = self._current_frontier
                    self._pending_gain_check = (
                        f.centroid_x, f.centroid_y, self._free_at_send, self._frontier_msgs)
                    self._state = ExplorationState.GOAL_REACHED
                else:
                    self._emit_goal_event(
                        'ended', current_time,
                        'rejected' if self._goal_rejected else 'nav_aborted')
                    self._blacklist_frontier(self._current_frontier, current_time, 'nav2_failure')
                    self._state = ExplorationState.RECOVERING
                self._goal_result = None
                return

            # Check timeout
            elapsed = current_time - (self._goal_start_time or current_time)
            if elapsed > self._goal_timeout:
                self.get_logger().warning(
                    f'Goal timeout ({elapsed:.1f}s). Blacklisting frontier #{self._current_frontier.id}')
                self._cancel_goal()
                self._emit_goal_event('ended', current_time, 'timeout')
                self._blacklist_frontier(self._current_frontier, current_time, 'timeout')
                self._state = ExplorationState.RECOVERING
                return

            # Check oscillation (robot not moving while navigating)
            last_move = self._last_move_time or current_time
            if (current_time - last_move) > self._oscillation_timeout:
                self.get_logger().warning('Oscillation detected. Cancelling goal.')
                self._cancel_goal()
                self._emit_goal_event('ended', current_time, 'oscillation')
                self._blacklist_frontier(self._current_frontier, current_time, 'oscillation')
                self._state = ExplorationState.RECOVERING

        elif self._state == ExplorationState.GOAL_REACHED:
            self._goals_completed += 1
            self.get_logger().info(
                f'Goal reached! Completed={self._goals_completed} Failed={self._goals_failed}')
            self._current_frontier = None
            self._state = ExplorationState.DETECT_FRONTIERS

        elif self._state == ExplorationState.RECOVERING:
            self._goals_failed += 1
            # Adaptive threshold: if many failures, tighten min_frontier_size
            if self._goals_failed > 0 and self._goals_failed % 5 == 0:
                self.get_logger().warning(
                    f'{self._goals_failed} failures — temporarily tightening frontier filter.')
            self._current_frontier = None
            self._state = ExplorationState.DETECT_FRONTIERS

        elif self._state == ExplorationState.FINISHED:
            self.get_logger().info(
                '\n═══════════════════════════════════════\n'
                '  EXPLORATION COMPLETE\n'
                f'  Goals completed : {self._goals_completed}\n'
                f'  Goals failed    : {self._goals_failed}\n'
                f'  Elapsed         : {(current_time - self._session_start):.1f} s\n'
                '═══════════════════════════════════════'
            )
            # Publish final status and the finished signal once, then stop the FSM
            # timer; status keeps publishing at 1 Hz so late subscribers see FINISHED.
            self._publish_status(current_time)
            self._finished_pub.publish(Bool(data=True))
            self._fsm_timer.cancel()
            self.create_timer(1.0, lambda: self._publish_status(
                self.get_clock().now().nanoseconds / 1e9))
            return

        # Publish status every tick
        self._publish_status(current_time)

    # ── Helper: completion check ───────────────────────────────────────────────

    def _check_completion(self, current_time: float) -> bool:
        """All three completion conditions must be simultaneously true."""
        # Condition 1: consecutive no-frontier detections
        cond1 = self._no_frontier_count >= self._no_frontier_checks_req

        # Condition 2: map has not grown significantly in patience window
        cond2 = False
        if len(self._map_free_history) >= 2:
            oldest_t, oldest_free = self._map_free_history[0]
            newest_t, newest_free = self._map_free_history[-1]
            window = newest_t - oldest_t
            if window >= self._map_growth_patience:
                growth = newest_free - oldest_free
                cond2 = growth < self._map_growth_threshold

        # Condition 3: robot is stationary
        cond3 = self._robot_linear_vel < self._stationary_vel_thresh

        if cond1 and cond2 and cond3:
            self.get_logger().info(
                f'Completion conditions met: no_frontiers={cond1} '
                f'map_stable={cond2} stationary={cond3}')
            return True
        return False

    def _check_no_gain(self, current_time: float) -> None:
        """Blacklist a reached frontier that persists without map growth (2 cycles max)."""
        pg = self._pending_gain_check
        if pg is None or self._frontier_msgs <= pg[3]:
            return
        x, y, free0, n0 = pg
        if no_information_gain((x, y), [(f.centroid_x, f.centroid_y) for f in self._frontiers],
                               self._blacklist_radius, free0, self._map_free,
                               self._map_growth_threshold):
            self._blacklist_frontier(Frontier(id=-1, centroid_x=x, centroid_y=y, size=1),
                                     current_time, 'no_information_gain')
            self._frontiers_skipped += 1
            self._pending_gain_check = None
        elif self._frontier_msgs >= n0 + 2:
            self._pending_gain_check = None

    def _map_has_free_cells(self) -> bool:
        return self._latest_map is not None and self._map_free > 0

    # ── Helper: blacklist management ───────────────────────────────────────────

    def _blacklist_frontier(
        self, frontier: Frontier, current_time: float, reason: str
    ) -> None:
        # Frontier ids are list indices and change between detector cycles, so
        # blacklist entries are matched by centroid proximity instead.
        existing = next(
            (b for b in self._blacklist
             if math.hypot(b.centroid_x - frontier.centroid_x,
                           b.centroid_y - frontier.centroid_y) <= self._blacklist_radius),
            None)
        if existing:
            existing.failure_count    += 1
            existing.last_failure_time = current_time
            count = existing.failure_count
        else:
            count = 1
            self._blacklist.append(BlacklistEntry(
                frontier_id=       frontier.id,
                centroid_x=        frontier.centroid_x,
                centroid_y=        frontier.centroid_y,
                failure_count=     count,
                last_failure_time= current_time,
                expiry_sec=        self._blacklist_expiry,
            ))
        self.get_logger().warning(
            f'Blacklisted frontier at ({frontier.centroid_x:.2f}, '
            f'{frontier.centroid_y:.2f}) (reason={reason}, count={count})'
        )

    def _effective_blacklisted_ids(self) -> Set[int]:
        """Ids of the current frontiers lying within blacklist_radius of an entry."""
        ids = set()
        for f in self._frontiers:
            for b in self._blacklist:
                if math.hypot(b.centroid_x - f.centroid_x,
                              b.centroid_y - f.centroid_y) <= self._blacklist_radius:
                    ids.add(f.id)
                    break
        return ids

    def _purge_blacklist(self, current_time: float) -> None:
        expired = [b for b in self._blacklist if b.is_expired(current_time)]
        for entry in expired:
            self._blacklist.remove(entry)
            self.get_logger().info(
                f'Blacklist entry at ({entry.centroid_x:.2f}, {entry.centroid_y:.2f}) '
                'removed (expired)')

    def _snap_goal(self, frontier: Frontier):
        """Nearest known-free cell (with clearance) to the frontier centroid, or None."""
        m = self._latest_map
        if m is None:
            return None
        res = m.info.resolution
        w, h = m.info.width, m.info.height
        arr = np.asarray(m.data, dtype=np.int8).reshape(h, w)
        free = arr == 0
        # distance (m) from every free cell to the nearest non-free cell (unknown/occupied)
        clearance = ndimage.distance_transform_edt(free) * res
        ok = clearance >= self._snap_clearance
        if not ok.any():
            return None
        ox, oy = m.info.origin.position.x, m.info.origin.position.y
        js, is_ = np.nonzero(ok)
        xs = ox + (is_ + 0.5) * res
        ys = oy + (js + 0.5) * res
        d = np.hypot(xs - frontier.centroid_x, ys - frontier.centroid_y)
        k = int(np.argmin(d))
        if d[k] > self._snap_max:
            return None
        return (float(xs[k]), float(ys[k]))

    # ── Goal events (docs/specs/01 section 1.5) ───────────────────────────────

    def _emit_goal_event(self, event: str, t: float, result: str = '') -> None:
        f = self._current_frontier
        msg = {
            'goal_seq': self._event_seq,
            'event':    event,
            't_sent':   self._goal_sent_time if self._goal_sent_time is not None else t,
            't_end':    t if event == 'ended' else None,
            'x':        self._goal_xy[0] if f else None,
            'y':        self._goal_xy[1] if f else None,
            'result':   result if event == 'ended' else 'started',
            'nav2_error_code': self._goal_error_code if event == 'ended' else 0,
            'frontier_x': f.centroid_x if f else None,
            'frontier_y': f.centroid_y if f else None,
        }
        self._goal_events_pub.publish(String(data=json.dumps(msg)))

    # ── Nav2 Action Client helpers ─────────────────────────────────────────────

    def _send_nav_goal(self, frontier: Frontier) -> None:
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.stamp    = self.get_clock().now().to_msg()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.pose.position.x = self._goal_xy[0]
        goal_msg.pose.pose.position.y = self._goal_xy[1]
        goal_msg.pose.pose.position.z = 0.0
        goal_msg.pose.pose.orientation.w = 1.0

        # Every goal gets a sequence number; callbacks of earlier goals carry their own
        # number and are ignored once a newer goal exists (stale-result race).
        self._goal_seq += 1
        self._event_seq += 1
        seq = self._goal_seq
        self._goal_handle = None
        self._goal_result = None
        self._goal_rejected = False
        self._goal_error_code = 0
        self._goal_sent_time = self.get_clock().now().nanoseconds / 1e9

        send_future = self._nav_client.send_goal_async(
            goal_msg,
            feedback_callback=self._goal_feedback_callback,
        )
        send_future.add_done_callback(lambda fut, s=seq: self._goal_response_callback(fut, s))

        # Publish goal as PoseStamped for RViz
        ps = PoseStamped()
        ps.header = goal_msg.pose.header
        ps.pose   = goal_msg.pose.pose
        self._selected_goal_pub.publish(ps)

    def _goal_response_callback(self, future, seq: int) -> None:
        handle = future.result()
        if seq != self._goal_seq:
            # A newer goal was sent (or this one timed out) before the reply arrived.
            if handle.accepted:
                handle.cancel_goal_async()
            return
        self._goal_handle = handle
        if not handle.accepted:
            self.get_logger().error('Goal rejected by Nav2!')
            self._goal_rejected = True
            self._goal_result = GoalStatus.STATUS_ABORTED
            return
        self.get_logger().info('Goal accepted by Nav2.')
        result_future = handle.get_result_async()
        result_future.add_done_callback(lambda fut, s=seq: self._goal_result_callback(fut, s))

    def _goal_result_callback(self, future, seq: int) -> None:
        if seq != self._goal_seq:
            return                      # result of a cancelled/older goal
        result = future.result()
        self._goal_error_code = int(getattr(result.result, 'error_code', 0))
        self._goal_result = result.status

    def _goal_feedback_callback(self, feedback_msg) -> None:
        # Could log distance remaining here if needed
        pass

    def _cancel_goal(self) -> None:
        if self._goal_handle is not None:
            self._goal_handle.cancel_goal_async()
            self._goal_handle = None
        # Results arriving for this goal are ignored from now on.
        self._goal_seq += 1

    # ── RViz marker for selected frontier ─────────────────────────────────────

    def _publish_selected_marker(self, frontier: Frontier) -> None:
        ma = MarkerArray()
        m = Marker()
        m.header.stamp    = self.get_clock().now().to_msg()
        m.header.frame_id = 'map'
        m.ns              = 'selected_frontier'
        m.id              = 0
        m.type            = Marker.SPHERE
        m.action          = Marker.ADD
        m.pose.position.x = frontier.centroid_x
        m.pose.position.y = frontier.centroid_y
        m.pose.position.z = 0.25
        m.pose.orientation.w = 1.0
        m.scale.x = m.scale.y = m.scale.z = 0.45
        m.color.r = 1.0    # red = selected frontier
        m.color.g = 0.0
        m.color.b = 0.0
        m.color.a = 1.0
        m.lifetime.sec = 5
        ma.markers.append(m)
        self._selected_marker_pub.publish(ma)

    # ── Status publisher ───────────────────────────────────────────────────────

    def _publish_status(self, current_time: float) -> None:
        coverage_pct = 0.0
        total_relevant = self._map_free + self._map_unknown
        if total_relevant > 0:
            coverage_pct = (self._map_free / total_relevant) * 100.0

        status = {
            'state':               self._state.value,
            'frontier_id':         self._current_frontier.id if self._current_frontier else -1,
            # free/(free+unknown) of the live map. NOT real coverage (see docs/specs/03).
            'coverage_pct':        round(coverage_pct, 2),
            'map_free_ratio_pct':  round(coverage_pct, 2),
            'goals_completed':     self._goals_completed,
            'goals_failed':        self._goals_failed,
            'frontiers_remaining': len(self._frontiers),
            'blacklisted_count':   len(self._blacklist),
            'frontiers_skipped':   self._frontiers_skipped,
            'elapsed_sec':         round(current_time - self._session_start, 1),
        }
        msg = String()
        msg.data = json.dumps(status)
        self._status_pub.publish(msg)


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main(args=None):
    rclpy.init(args=args)
    node = ExplorationManager()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, StopIteration):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
