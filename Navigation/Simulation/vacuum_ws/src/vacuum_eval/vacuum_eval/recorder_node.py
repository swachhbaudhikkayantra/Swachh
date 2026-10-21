#!/usr/bin/env python3
"""recorder_node - raw evaluation data writer (spec 02 section 2.4)."""
import csv
import json
import math
import os

import numpy as np
import psutil
import rclpy
from action_msgs.msg import GoalStatusArray
from geometry_msgs.msg import Twist, TwistStamped
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import OccupancyGrid, Odometry, Path
from rclpy.clock import Clock, ClockType
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from ros_gz_interfaces.msg import Contacts
from rtabmap_msgs.msg import Info
from sensor_msgs.msg import Image, LaserScan
from std_msgs.msg import Bool, Empty, String
from tf2_msgs.msg import TFMessage
from tf2_ros import Buffer, TransformListener

RELIABLE = QoSProfile(depth=50, reliability=ReliabilityPolicy.RELIABLE,
                      durability=DurabilityPolicy.VOLATILE)
BEST_EFFORT = QoSProfile(depth=50, reliability=ReliabilityPolicy.BEST_EFFORT,
                         durability=DurabilityPolicy.VOLATILE)
LATCHED = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                     durability=DurabilityPolicy.TRANSIENT_LOCAL)

STATUS_NAMES = {1: 'accepted', 2: 'executing', 3: 'canceling',
                4: 'succeeded', 5: 'canceled', 6: 'aborted'}

GROUPS = [
    ('gz', ['gz sim', 'gz-sim']),
    ('rtabmap', ['rtabmap']),
    ('nav2', ['controller_server', 'planner_server', 'bt_navigator', 'behavior_server',
              'smoother_server', 'velocity_smoother', 'amcl', 'map_server',
              'lifecycle_manager', 'collision_monitor']),
    ('bridge', ['parameter_bridge', 'ros_gz_bridge', 'topic_tools']),
    ('explore', ['exploration_manager', 'frontier_detector', 'frontier_visualizer',
                 'exploration_metrics']),
    ('eval', ['vacuum_eval', 'recorder_node', 'ground_truth_node', 'odom_noise_node']),
    ('other_ros', ['/opt/ros/jazzy', 'vacuum_ws/install']),
]


def yaw_of(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def f6(v):
    if v is None:
        return ''
    if isinstance(v, float):
        return '%.6f' % v
    return v


def uuid_hex(u):
    return bytes(bytearray(u)).hex()


def group_of(cmd):
    for g, keys in GROUPS:
        if any(k in cmd for k in keys):
            return g
        if g == 'gz' and 'ruby' in cmd and 'gz' in cmd:
            return g
    return None


class Recorder(Node):
    def __init__(self):
        super().__init__('recorder_node')
        self.declare_parameter('run_dir', '')
        self.declare_parameter('sample_hz', 10.0)
        self.declare_parameter('map_snapshot_period_sec', 5.0)
        self.declare_parameter('robot_model_name', 'vacuum_robot')
        self.declare_parameter('extra_models', [''])
        p = self.get_parameter
        self.run_dir = p('run_dir').value
        if not self.run_dir:
            raise RuntimeError('parameter run_dir is required')
        self.robot = p('robot_model_name').value
        self.snap_period = float(p('map_snapshot_period_sec').value)
        self.extra = [m for m in p('extra_models').value if m]
        os.makedirs(os.path.join(self.run_dir, 'maps'), exist_ok=True)

        self.t0 = None
        self.stop = False
        self.files = {}
        self.writers = {}
        self.gt = None          # (t_recv, x, y, yaw, vx, wz)
        self.odom = None
        self.dyn = {}
        self.first_gt = self.first_est = self.episode_started = False
        self.plan_seq = 0
        self.status_last = {}
        self.counts = dict.fromkeys(
            ['n_odom', 'n_depth', 'n_color', 'n_cmd_nav', 'n_cmd_smoothed',
             'n_tf_map_odom', 'n_scan', 'n_plan'], 0)
        self.last_map = None
        self.last_snap_t = None
        self.contacts_seen = 0
        self.ground_dropped = 0

        self.open('events', ['event', 'detail'])
        self.open('trajectory', ['gt_x', 'gt_y', 'gt_yaw', 'gt_vx', 'gt_wz',
                                 'odom_x', 'odom_y', 'odom_yaw',
                                 'est_x', 'est_y', 'est_yaw', 'est_ok'])
        self.open('cmd_vel', ['source', 'vx', 'vy', 'wz'])
        self.open('goal_events', ['src', 'goal_seq', 'event', 'result', 'x', 'y',
                                  'nav2_error_code', 'uuid'])
        self.open('feedback', ['uuid', 'distance_remaining', 'number_of_recoveries',
                               'navigation_time_sec'])
        self.open('plans', ['plan_seq', 'n_poses', 'length_m', 'start_x', 'start_y',
                            'end_x', 'end_y'])
        self.open('rates', ['n_odom', 'n_depth', 'n_color', 'n_cmd_nav', 'n_cmd_smoothed',
                            'n_tf_map_odom', 'n_scan', 'n_plan'])
        self.open('collisions_raw', ['sensor', 'own_entity', 'other_entity', 'other_model',
                                     'px', 'py', 'pz'])
        self.open('loop_events', ['ref_id', 'loop_closure_id', 'proximity_detection_id',
                                  'gt_x', 'gt_y', 'gt_yaw', 'est_x', 'est_y', 'est_yaw'])
        if self.extra:
            self.open('dyn_obstacles', ['name', 'x', 'y', 'yaw', 'vx', 'vy', 'wz'])
        self.open('rtf', ['wall_dt', 'sim_dt', 'rtf'])
        self.res_cols = ['cpu_total_pct', 'ram_used_mb']
        for g, _ in GROUPS:
            self.res_cols += ['cpu_%s_pct' % g, 'rss_%s_mb' % g]
        self.open('resources', self.res_cols)
        self.event('recorder_started', self.run_dir)

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self, spin_thread=True)

        cs = self.create_subscription
        cs(Odometry, '/ground_truth/odom', self.on_gt, RELIABLE)
        cs(Odometry, '/odom', self.on_odom, RELIABLE)
        for m in self.extra:
            cs(Odometry, '/ground_truth/model/' + m,
               lambda msg, m=m: self.on_dyn(m, msg), RELIABLE)
        cs(Twist, '/cmd_vel', lambda m: self.on_cmd('teleop', m), RELIABLE)
        cs(Twist, '/cmd_vel_nav', self.on_cmd_nav, RELIABLE)
        cs(Twist, '/cmd_vel_smoothed', lambda m: self.on_cmd('smoothed', m), RELIABLE)
        cs(TwistStamped, '/diff_drive_controller/cmd_vel', self.on_cmd_ctrl, RELIABLE)
        cs(String, '/exploration/goal_events', lambda m: self.on_goal_json('explore', m), RELIABLE)
        cs(String, '/eval/goal_events', lambda m: self.on_goal_json('scripted', m), RELIABLE)
        for src, act in [('nav2_status', 'navigate_to_pose'), ('behavior_spin', 'spin'),
                         ('behavior_backup', 'backup'), ('behavior_wait', 'wait')]:
            cs(GoalStatusArray, '/%s/_action/status' % act,
               lambda m, s=src: self.on_status(s, m), RELIABLE)
        cs(NavigateToPose.Impl.FeedbackMessage, '/navigate_to_pose/_action/feedback',
           self.on_feedback, RELIABLE)
        cs(Path, '/plan', self.on_plan, RELIABLE)
        for sensor in ('chassis', 'camera', 'camera_mount'):
            cs(Contacts, '/vacuum_robot/contacts/' + sensor,
               lambda m, s=sensor: self.on_contacts(s, m), RELIABLE)
        cs(Info, '/rtabmap/info', self.on_info, RELIABLE)
        cs(OccupancyGrid, '/rtabmap/map', self.on_map, LATCHED)
        cs(Empty, '/eval/stop', self.on_stop, RELIABLE)
        cs(Bool, '/exploration/finished', lambda m: self.on_finish(m, 'exploration_finished'), LATCHED)
        cs(Bool, '/eval/done', lambda m: self.on_finish(m, 'eval_done'), RELIABLE)
        # rate counters (images raw: no deserialisation)
        cs(Image, '/camera/depth/image_rect_raw', lambda m: self.bump('n_depth'), BEST_EFFORT, raw=True)
        cs(Image, '/camera/color/image_raw', lambda m: self.bump('n_color'), BEST_EFFORT, raw=True)
        cs(LaserScan, '/scan_from_depth', lambda m: self.bump('n_scan'), BEST_EFFORT)
        cs(TFMessage, '/tf', self.on_tf, QoSProfile(
            depth=100, reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE))

        self.create_timer(1.0 / float(p('sample_hz').value), self.on_sample)
        self.create_timer(1.0, self.on_rates)
        self.wall_timer = self.create_timer(
            1.0, self.on_wall, clock=Clock(clock_type=ClockType.SYSTEM_TIME))
        self.proc_cache = {}
        self.first_res = True
        self.last_wall = None
        self.last_sim = None
        psutil.cpu_percent(interval=None)

    # ---- file helpers ----
    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def open(self, name, cols, stamped=True):
        path = os.path.join(self.run_dir, name + '.csv')
        # events.csv is shared with the harness (which may have written rows already)
        append = name == 'events' and os.path.exists(path) and os.path.getsize(path) > 0
        fh = open(path, 'a' if append else 'w', newline='', buffering=1)
        w = csv.writer(fh)
        if not append:
            w.writerow((['t', 't_rel'] if stamped else []) + cols)
        fh.flush()
        self.files[name] = fh
        self.writers[name] = (w, stamped)

    def row(self, name, vals, t=None):
        w, stamped = self.writers[name]
        if stamped:
            if t is None:
                t = self.now()
            if name == 'events':
                # events may precede the first clock message / the first trajectory row:
                # they never define t0 and carry empty times until the clock runs
                if t and t > 0.0:
                    rel = f6(t - self.t0) if self.t0 is not None else ''
                    vals = [f6(t), rel] + [f6(v) for v in vals]
                else:
                    vals = ['', ''] + [f6(v) for v in vals]
            else:
                if self.t0 is None:
                    self.t0 = t
                vals = [f6(t), f6(t - self.t0)] + [f6(v) for v in vals]
        else:
            vals = [f6(v) for v in vals]
        w.writerow(vals)
        self.files[name].flush()

    def event(self, ev, detail=''):
        self.row('events', [ev, detail])

    def bump(self, k):
        self.counts[k] += 1

    # ---- callbacks ----
    def on_gt(self, m):
        pp, tw = m.pose.pose, m.twist.twist
        self.gt = (self.now(), pp.position.x, pp.position.y, yaw_of(pp.orientation),
                   tw.linear.x, tw.angular.z)

    def on_odom(self, m):
        pp = m.pose.pose
        self.odom = (self.now(), pp.position.x, pp.position.y, yaw_of(pp.orientation))
        self.bump('n_odom')

    def on_dyn(self, name, m):
        pp, tw = m.pose.pose, m.twist.twist
        self.dyn[name] = (self.now(), pp.position.x, pp.position.y, yaw_of(pp.orientation),
                          tw.linear.x, tw.linear.y, tw.angular.z)

    def est_pose(self):
        try:
            tf = self.tf_buffer.lookup_transform('map', 'base_footprint', Time(),
                                                 timeout=Duration(seconds=0.05))
        except Exception:
            return None
        tr = tf.transform
        return tr.translation.x, tr.translation.y, yaw_of(tr.rotation)

    def on_sample(self):
        t = self.now()
        if self.t0 is None:
            self.t0 = t
        gt = self.gt if self.gt and t - self.gt[0] <= 0.2 else None
        od = self.odom if self.odom and t - self.odom[0] <= 0.2 else None
        est = self.est_pose()
        if gt and not self.first_gt:
            self.first_gt = True
            self.event('first_gt_sample', f6(t))
        if est and not self.first_est:
            self.first_est = True
            self.event('first_est_sample', f6(t))
        v = [gt[1], gt[2], gt[3], gt[4], gt[5]] if gt else [None] * 5
        v += list(od[1:4]) if od else [None] * 3
        v += list(est) if est else [None] * 3
        v.append(1 if est else 0)
        self.row('trajectory', v, t)
        for name, d in self.dyn.items():
            if t - d[0] <= 0.2:
                self.row('dyn_obstacles', [name] + list(d[1:]), t)

    def on_cmd(self, src, m):
        self.row('cmd_vel', [src, m.linear.x, m.linear.y, m.angular.z])

    def on_cmd_nav(self, m):
        self.bump('n_cmd_nav')
        self.on_cmd('nav', m)

    def on_cmd_ctrl(self, m):
        self.bump('n_cmd_smoothed')   # spec 7.5 lists /diff_drive_controller/cmd_vel here
        tw = m.twist
        self.row('cmd_vel', ['ctrl_stamped', tw.linear.x, tw.linear.y, tw.angular.z])
        if not self.episode_started and (abs(tw.linear.x) > 0.01 or abs(tw.angular.z) > 0.01):
            self.episode_started = True
            self.event('episode_start', f6(self.now()))

    def on_goal_json(self, src, msg):
        try:
            d = json.loads(msg.data)
        except Exception:
            return
        res = d.get('result')
        ev = d.get('event')
        if ev not in ('started', 'ended'):
            ev = 'started' if res == 'started' else 'ended'
        if ev == 'started':
            res = 'started'
        self.row('goal_events', [src, d.get('goal_seq'), ev, res, d.get('x'), d.get('y'),
                                 d.get('nav2_error_code'), ''])

    def on_status(self, src, msg):
        for s in msg.status_list:
            u = uuid_hex(s.goal_info.goal_id.uuid)
            key = (src, u)
            if self.status_last.get(key) == s.status:
                continue
            self.status_last[key] = s.status
            if s.status in STATUS_NAMES:
                self.row('goal_events', [src, '', STATUS_NAMES[s.status], '', '', '', '', u])

    def on_feedback(self, msg):
        fb = msg.feedback
        nt = fb.navigation_time
        self.row('feedback', [uuid_hex(msg.goal_id.uuid), float(fb.distance_remaining),
                              int(fb.number_of_recoveries), nt.sec + nt.nanosec * 1e-9])

    def on_plan(self, msg):
        self.bump('n_plan')
        self.plan_seq += 1
        ps = [(q.pose.position.x, q.pose.position.y) for q in msg.poses]
        n = len(ps)
        length = sum(math.hypot(ps[i + 1][0] - ps[i][0], ps[i + 1][1] - ps[i][1])
                     for i in range(n - 1))
        s = ps[0] if n else (None, None)
        e = ps[-1] if n else (None, None)
        self.row('plans', [self.plan_seq, n, float(length), s[0], s[1], e[0], e[1]])

    def on_contacts(self, sensor, msg):
        self.contacts_seen += 1
        for c in msg.contacts:
            n1, n2 = c.collision1.name, c.collision2.name
            if n1.split('::')[0] == self.robot:
                own, other = n1, n2
            elif n2.split('::')[0] == self.robot:
                own, other = n2, n1
            else:
                own, other = n1, n2
            model = other.split('::')[0]
            if model == 'ground_plane':
                self.ground_dropped += 1
                continue
            pos = c.positions[0] if c.positions else None
            self.row('collisions_raw', [sensor, own, other, model,
                                        pos.x if pos else None, pos.y if pos else None,
                                        pos.z if pos else None])

    def on_info(self, msg):
        t = self.now()
        gt = self.gt if self.gt and t - self.gt[0] <= 0.2 else None
        est = self.est_pose()
        self.row('loop_events', [msg.ref_id, msg.loop_closure_id, msg.proximity_detection_id]
                 + (list(gt[1:4]) if gt else [None] * 3)
                 + (list(est) if est else [None] * 3), t)

    def on_tf(self, msg):
        for tr in msg.transforms:
            if tr.header.frame_id.lstrip('/') == 'map' and tr.child_frame_id.lstrip('/') == 'odom':
                self.counts['n_tf_map_odom'] += 1

    def on_rates(self):
        c = self.counts
        self.row('rates', [c[k] for k in ['n_odom', 'n_depth', 'n_color', 'n_cmd_nav',
                                          'n_cmd_smoothed', 'n_tf_map_odom', 'n_scan',
                                          'n_plan']])
        for k in c:
            c[k] = 0

    def on_finish(self, msg, detail):
        if msg.data:
            self.event('finished_signal', detail)

    # ---- maps ----
    def on_map(self, msg):
        t = self.now()
        self.last_map = (msg, t)
        if self.t0 is None:
            self.t0 = t
        if self.last_snap_t is None or t - self.last_snap_t >= self.snap_period:
            self.last_snap_t = t
            self.write_npz(os.path.join(self.run_dir, 'maps', 'map_%08.2f.npz' % (t - self.t0)),
                           msg, t)

    @staticmethod
    def grid(msg):
        return np.asarray(msg.data, dtype=np.int8).reshape(msg.info.height, msg.info.width)

    def write_npz(self, path, msg, t):
        o = msg.info.origin
        np.savez(path, data=self.grid(msg), resolution=np.float64(msg.info.resolution),
                 origin_x=np.float64(o.position.x), origin_y=np.float64(o.position.y),
                 origin_yaw=np.float64(yaw_of(o.orientation)),
                 t=np.float64(t), t_rel=np.float64(t - self.t0))

    def write_final_map(self):
        if self.last_map is None:
            self.event('final_map_missing', 'no /rtabmap/map received')
            return
        msg, t = self.last_map
        d = os.path.join(self.run_dir, 'maps')
        self.write_npz(os.path.join(d, 'final_map.npz'), msg, t)
        g = self.grid(msg)
        img = np.full(g.shape, 205, dtype=np.uint8)
        img[(g >= 0) & (g < 25)] = 254
        img[g > 65] = 0
        img = np.flipud(img)
        with open(os.path.join(d, 'final_map.pgm'), 'wb') as fh:
            fh.write(b'P5\n%d %d\n255\n' % (g.shape[1], g.shape[0]))
            fh.write(img.tobytes())
        o = msg.info.origin
        with open(os.path.join(d, 'final_map.yaml'), 'w') as fh:
            fh.write('image: final_map.pgm\nresolution: %.6f\norigin: [%.6f, %.6f, 0.0]\n'
                     'negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.25\n'
                     % (msg.info.resolution, o.position.x, o.position.y))

    # ---- stop ----
    def on_stop(self, _):
        if self.stop:
            return
        self.event('stop_received', f6(self.now()))
        try:
            self.write_final_map()
        except Exception as e:  # keep finalising
            self.event('final_map_error', str(e))
        self.event('contact_topic_alive', 1 if self.contacts_seen else 0)
        self.event('ground_contacts_dropped', self.ground_dropped)
        self.event('recorder_stopped', f6(self.now()))
        for fh in self.files.values():
            fh.close()
        self.stop = True

    # ---- wall timer: resources + rtf ----
    def on_wall(self):
        if self.stop:
            return
        import time
        wall = time.monotonic()
        sim = self.now()
        if self.last_wall is not None:
            wd, sd = wall - self.last_wall, sim - self.last_sim
            self.row('rtf', [wd, sd, sd / wd if wd > 0 else None], sim)
        self.last_wall, self.last_sim = wall, sim

        cpu = {g: 0.0 for g, _ in GROUPS}
        rss = {g: 0.0 for g, _ in GROUPS}
        alive = set()
        for proc in psutil.process_iter():
            pid = proc.pid
            alive.add(pid)
            try:
                ent = self.proc_cache.get(pid)
                if ent is None or ent[0].create_time() != proc.create_time():
                    cmd = ' '.join(proc.cmdline())
                    ent = (proc, group_of(cmd))
                    self.proc_cache[pid] = ent
                    ent[0].cpu_percent(interval=None)
                    if ent[1] is None:
                        continue
                if ent[1] is None:
                    continue
                cpu[ent[1]] += ent[0].cpu_percent(interval=None)
                rss[ent[1]] += ent[0].memory_info().rss / 2 ** 20
            except (psutil.Error, OSError):
                continue
        for pid in list(self.proc_cache):
            if pid not in alive:
                del self.proc_cache[pid]
        total = psutil.cpu_percent(interval=None)
        vals = [None if self.first_res else total,
                psutil.virtual_memory().used / 2 ** 20]
        for g, _ in GROUPS:
            vals += [None if self.first_res else cpu[g], rss[g]]
        self.first_res = False
        self.row('resources', vals, sim)


def main(args=None):
    rclpy.init(args=args)
    node = Recorder()
    try:
        while rclpy.ok() and not node.stop:
            rclpy.spin_once(node, timeout_sec=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        if not node.stop:
            node.event('recorder_stopped', 'interrupted')
            for fh in node.files.values():
                fh.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
