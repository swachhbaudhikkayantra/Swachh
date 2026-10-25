#!/usr/bin/env python3
"""Episode harness (docs/specs/02 section 2.6). Launches the stack, monitors, stops, computes metrics."""

import argparse
import csv
import dataclasses
import datetime
import math
import os
import shutil
import signal
import subprocess
import sys
import time

import numpy as np
import yaml

from vacuum_eval import compute_metrics as cm
from vacuum_eval.metrics import gt_grid
from vacuum_eval.metrics.common import load_csv
from vacuum_eval.metrics.navigation import generate_goal_lists

ROS_ENV = ('source /opt/ros/jazzy/setup.bash; '
           'source ~/Swachh/Navigation/Simulation/vacuum_ws/install/setup.bash; '
           'export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp '
           'CYCLONEDDS_URI=file://$HOME/Swachh/Navigation/cyclone_dds.xml ROS_DOMAIN_ID=0; ')
_BASE_ROS_ENV = ROS_ENV
BAG_TOPICS = ('/clock /tf /tf_static /odom /diff_drive_controller/odom /ground_truth/odom_raw '
              '/ground_truth/odom /cmd_vel /cmd_vel_nav /cmd_vel_smoothed '
              '/diff_drive_controller/cmd_vel /rtabmap/map /rtabmap/info /rtabmap/mapGraph '
              '/exploration/status /exploration/goal_events /exploration/current_goal '
              '/exploration/finished /navigate_to_pose/_action/status '
              '/navigate_to_pose/_action/feedback /plan /local_plan /scan_from_depth '
              '/joint_states /vacuum_robot/contacts /eval/goal_events /eval/done')
LEAN_DROP_TOPICS = ('/clock', '/joint_states')


def bag_topics(lean=0):
    t = BAG_TOPICS.split()
    if lean:
        t = [x for x in t if x not in LEAN_DROP_TOPICS]
    return ' '.join(t)


def slot_env(slot):
    """-> (ros_domain_id, gz_partition) for a parallel slot. Slot 0 keeps domain 0."""
    slot = int(slot or 0)
    return (10 + slot if slot > 0 else 0), 'vacuum_slot%d' % slot


def build_ros_env(slot=0):
    dom, part = slot_env(slot)
    base = _BASE_ROS_ENV.replace('ROS_DOMAIN_ID=0;', 'ROS_DOMAIN_ID=%d;' % dom)
    return base + 'export GZ_PARTITION=%s ROS_LOCALHOST_ONLY=1; ' % part


def set_slot(slot):
    global ROS_ENV
    ROS_ENV = build_ros_env(slot)


def _lock_path(slot, root=None):
    return os.path.join(os.path.expanduser(root or '~/eval_runs'), '.slot%d.lock' % int(slot))


def pid_alive(pid):
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (ValueError, OSError):
        return False
    return True


def acquire_slot_lock(slot, root=None, pid=None, alive=pid_alive):
    """True if the lock was taken (stale lock with dead PID is replaced)."""
    path = _lock_path(slot, root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        old = int(open(path).read().strip())
        if alive(old):
            return False
    except (OSError, ValueError):
        pass
    tmp = '%s.%d.tmp' % (path, os.getpid())
    with open(tmp, 'w') as f:
        f.write(str(pid or os.getpid()))
    os.replace(tmp, path)
    return True


def release_slot_lock(slot, root=None, pid=None):
    path = _lock_path(slot, root)
    try:
        if int(open(path).read().strip()) == (pid or os.getpid()):
            os.remove(path)
    except (OSError, ValueError):
        pass


def pids_with_partition(partition, proc_root='/proc', name_sub='gz'):
    """PIDs whose environ has GZ_PARTITION=<partition> and whose cmdline contains name_sub."""
    out = []
    needle = b'GZ_PARTITION=' + partition.encode()
    try:
        entries = os.listdir(proc_root)
    except OSError:
        return out
    for e in entries:
        if not e.isdigit() or int(e) == os.getpid():
            continue
        try:
            env = open(os.path.join(proc_root, e, 'environ'), 'rb').read().split(b'\0')
            cmd = open(os.path.join(proc_root, e, 'cmdline'), 'rb').read()
        except OSError:
            continue
        if needle in env and name_sub.encode() in cmd:
            out.append(int(e))
    return out


def sample_spawn(seed, candidates):
    rng = np.random.default_rng(seed)
    idx = int(rng.integers(len(candidates)))
    yaw = float(rng.uniform(-math.pi, math.pi))
    return float(candidates[idx][0]), float(candidates[idx][1]), yaw


def git_info():
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        c = subprocess.check_output(['git', '-C', here, 'rev-parse', 'HEAD'], text=True,
                                    stderr=subprocess.DEVNULL).strip()
        d = bool(subprocess.check_output(['git', '-C', here, 'status', '--porcelain'], text=True,
                                         stderr=subprocess.DEVNULL).strip())
        return c, d
    except Exception:  # noqa: BLE001
        return 'unknown', False


def version_of(cmd):
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).strip().splitlines()[0]
    except Exception:  # noqa: BLE001
        return 'unknown'


def event(run_dir, name, detail='', t=''):
    p = os.path.join(run_dir, 'events.csv')
    new = not os.path.exists(p)
    with open(p, 'a', newline='') as f:
        w = csv.writer(f)
        if new:
            w.writerow(['t', 't_rel', 'event', 'detail'])
        w.writerow([t, '', name, detail])
    print('[%s] %s %s' % (datetime.datetime.now().strftime('%H:%M:%S'), name, detail), flush=True)


class Proc:
    def __init__(self, name, cmd, run_dir, critical=True):
        self.name = name
        self.critical = critical
        os.makedirs(os.path.join(run_dir, 'logs'), exist_ok=True)
        self.log = open(os.path.join(run_dir, 'logs', name + '.log'), 'w')
        self.p = subprocess.Popen(['bash', '-c', ROS_ENV + 'exec ' + cmd], stdout=self.log,
                                  stderr=subprocess.STDOUT, start_new_session=True)

    def alive(self):
        return self.p.poll() is None

    def signal(self, sig):
        try:
            os.killpg(self.p.pid, sig)
        except ProcessLookupError:
            pass

    def wait(self, sec):
        try:
            self.p.wait(sec)
            return True
        except subprocess.TimeoutExpired:
            return False


def ros(cmd, timeout):
    """Run a sourced ros2 CLI command; return (rc, stdout)."""
    try:
        r = subprocess.run(['bash', '-c', ROS_ENV + cmd], capture_output=True, text=True,
                           timeout=timeout)
        return r.returncode, r.stdout
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout.decode() if isinstance(e.stdout, bytes) else e.stdout) or ''


def _clock_value(txt):
    for ln in txt.splitlines():
        ln = ln.strip()
        if ln.startswith('sec:'):
            return int(ln.split(':')[1])
    return None


def gate_clock():
    _, a = ros('ros2 topic echo --once /clock', 20)
    time.sleep(3)
    _, b = ros('ros2 topic echo --once /clock', 20)
    va, vb = _clock_value(a), _clock_value(b)
    return va is not None and vb is not None and vb > va


def gate_controllers():
    _, o = ros('ros2 control list_controllers', 20)
    ok = 0
    for ln in o.splitlines():
        if ('joint_state_broadcaster' in ln or 'diff_drive_controller' in ln) and 'active' in ln:
            ok += 1
    return ok >= 2


def gate_gt():
    return ros('ros2 topic echo --once /ground_truth/odom --field header', 20)[0] == 0


def gate_tf():
    _, o = ros('timeout 6 ros2 run tf2_ros tf2_echo map base_footprint', 10)
    return 'Translation' in o


def gate_nav():
    return '/navigate_to_pose' in ros('ros2 action list', 15)[1]


def gate_map():
    return ros('ros2 topic echo --once /rtabmap/map --qos-durability transient_local '
               '--qos-reliability reliable --field info', 20)[0] == 0


def gate_rtabmap_alive():
    """>=3 /rtabmap/info messages within 30 wall s (identity map->odom passes G4 even if dead)."""
    _, o = ros('timeout 30 ros2 topic echo /rtabmap/info --field header.stamp.sec', 35)
    return sum(1 for ln in o.splitlines() if ln.strip().isdigit()) >= 3


def wait_gate(name, fn, budget, run_dir):
    t_end = time.time() + budget
    while time.time() < t_end:
        try:
            if fn():
                event(run_dir, 'gate_ok', name)
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    event(run_dir, 'gate_failed', name)
    return False


def preflight(root, slot=0):
    if pids_with_partition(slot_env(slot)[1]):
        print('stale simulator running in slot %d (GZ_PARTITION=%s)' % (slot, slot_env(slot)[1]),
              file=sys.stderr)
        return 2
    if not acquire_slot_lock(slot, root):
        print('slot %d is locked by a live process' % slot, file=sys.stderr)
        return 2
    try:
        if int(open('/proc/sys/net/core/rmem_max').read()) < 4194304:
            print('warning: net.core.rmem_max < 4194304', file=sys.stderr)
    except OSError:
        pass
    os.makedirs(root, exist_ok=True)
    if shutil.disk_usage(root).free < 5 * 2**30:
        print('free disk < 5 GB', file=sys.stderr)
        return 2
    return 0


# ------------------------------------------------------------------ pure planning (unit-tested)
SLAM_ENVS = ('room', 'office', 'apartment', 'corridor', 'large', 'empty_room', 'cluttered_room',
             'two_rooms_door', 'multi_room_loop', 'maze_dead_ends', 'symmetric_hall')
GOAL_LISTS = ('fixed', 'random20', 'near_wall', 'long_range', 'scenario', 'loop_tour')


@dataclasses.dataclass
class ProcessSpec:
    name: str
    cmd: str
    delay_s: float = 0.0       # wall seconds after the first stack process
    critical: bool = True      # exit of a critical process => end_reason crash


def _b(v):
    return 'true' if v else 'false'


def resolve_goal_list(a, ent):
    if a.goal_list:
        return a.goal_list
    return 'scenario' if ent.get('scenario') else 'fixed'


def method_dir_name(method, goal_list=None, nav_map='gt', stack=None):
    if method == 'scripted_goals':
        return 'scripted_goals' + ('_' + goal_list if goal_list else '') + \
            ('_slam' if nav_map == 'slam' else '')
    if method == 'responsiveness':
        return 'responsiveness_' + (stack or 'bare')
    return method


def scenario_draws(seed, start, n_dynamic=0):
    """rng=default_rng(seed+3000): spawn = start + U(+-0.10) x,y, U(+-0.2) yaw (in that order),
    then one U(0,2) start delay per dynamic obstacle. Returns (spawn, [delays])."""
    rng = np.random.default_rng(seed + 3000)
    dx, dy = rng.uniform(-0.10, 0.10), rng.uniform(-0.10, 0.10)
    dyaw = rng.uniform(-0.2, 0.2)
    spawn = (float(start[0] + dx), float(start[1] + dy), float(start[2] + dyaw))
    delays = [float(rng.uniform(0.0, 2.0)) for _ in range(n_dynamic)]
    return spawn, delays


def select_goals(goal_list, seed, ent, spawn, gt=None):
    """Goal dicts {x,y,yaw} for the chosen list (spec 05 5.8). `gt` only needed for the
    generated lists (random20, near_wall, long_range)."""
    def dicts(rows):
        return [{'x': float(r[0]), 'y': float(r[1]), 'yaw': float(r[2]) if len(r) > 2 else 0.0}
                for r in rows]
    lists = ent.get('goal_lists') or {}
    if goal_list == 'scenario':
        sc = ent.get('scenario')
        if not sc:
            raise ValueError('world has no scenario entry')
        return dicts([sc['goal']])
    if goal_list in ('fixed', 'loop_tour'):
        if goal_list not in lists:
            raise ValueError('world has no goal_lists.%s' % goal_list)
        return dicts(lists[goal_list])
    if gt is None:
        raise ValueError('goal list %s needs the GT grid' % goal_list)
    gen = generate_goal_lists(gt, seed + 2000, spawn_xy=(spawn[0], spawn[1]),
                              fixed=dicts(lists['fixed']) if 'fixed' in lists else None)
    return gen[goal_list]


def write_goals(path, goals):
    with open(path, 'w') as f:
        yaml.safe_dump([dict(x=g['x'], y=g['y'], yaw=g['yaw']) for g in goals], f)


def export_gt_map(world, worlds_cfg, run_dir):
    """Export the GT grid as <run_dir>/gt_map.{pgm,yaml} (map frame == world frame)."""
    gt = cm.gt_grid_for(world, worlds_cfg)
    return gt_grid.export_nav2_map(gt, os.path.join(run_dir, 'gt_map'))


def initialpose_cmd(spawn):
    cov = [0.0] * 36
    cov[0] = cov[7] = 0.0025
    cov[35] = 0.0025
    return ('ros2 topic pub -t 5 -r 2 /initialpose geometry_msgs/msg/PoseWithCovarianceStamped '
            '"{header: {frame_id: map}, pose: {pose: {position: {x: %.6f, y: %.6f, z: 0.0}, '
            'orientation: {z: %.6f, w: %.6f}}, covariance: %s}}"'
            % (spawn[0], spawn[1], math.sin(spawn[2] / 2), math.cos(spawn[2] / 2),
               '[' + ', '.join('%g' % c for c in cov) + ']'))


def _noise_args(a):
    return 'odom_noise:=%s odom_noise_seed:=%d' % (_b(a.odom_noise), a.seed + 1000)


def sim_cmd(a, spawn, sdf=None, extra_bridge=None):
    c = ('ros2 launch vacuum_bringup sim.launch.py %s spawn_x:=%.6f spawn_y:=%.6f '
         'spawn_yaw:=%.6f odom_mode:=eval headless:=%s use_rviz:=false %s'
         % ('world_file:=%s' % sdf if sdf else 'world:=%s' % a.world, spawn[0], spawn[1],
            spawn[2], _b(a.headless), _noise_args(a)))
    if getattr(a, 'lean', 0):
        c += ' enable_diagnostics:=false'
    if getattr(a, 'gpu', 0):
        c += ' render_gpu:=true'
    if extra_bridge:
        c += ' extra_bridge_config:=%s' % extra_bridge
    return c


def _explore_extra(a):
    c = ''
    if getattr(a, 'lean', 0):
        c += ' enable_visualizer:=false enable_legacy_metrics:=false enable_diagnostics:=false'
    if getattr(a, 'gpu', 0):
        c += ' render_gpu:=true'
    return c


def eval_cmd(run_dir, extra_models=()):
    c = 'ros2 launch vacuum_eval eval_stack.launch.py run_dir:=%s use_sim_time:=true' % run_dir
    if extra_models:
        c += ' extra_models:=%s' % ','.join(extra_models)
    return c


def dynamic_models(ent):
    return list((ent.get('dynamic_obstacles') or {}).keys())


def _loc_mode(a):
    """Effective localization source: slam (RTAB-Map), amcl or gt (perfect)."""
    loc = getattr(a, 'localization', 'auto') or 'auto'
    if loc == 'auto':
        return 'amcl' if a.nav_map == 'gt' else 'rtabmap'
    if loc == 'slam':
        return 'rtabmap'
    if loc == 'gt' and a.nav_map != 'gt':
        raise SystemExit('--localization gt requires --nav-map gt')
    if loc == 'amcl' and a.nav_map != 'gt':
        raise SystemExit('--localization amcl requires --nav-map gt')
    return loc


def meta_extras(a, ent, spawn, goal_list=None):
    ex = {}
    if a.method == 'scripted_goals':
        gt_mode = a.nav_map == 'gt'
        loc = _loc_mode(a)
        ex.update(goal_list=goal_list, nav_map=a.nav_map,
                  localization_mode=loc,
                  # v2 files are only read by nav2_localization.launch.py (AMCL); gt mode uses nav2.launch.py
                  nav_variant=('v1' if loc == 'gt' else
                               (os.environ.get('VACUUM_NAV_VARIANT') or 'v1').strip().lower()),
                  t_world_map=[0.0, 0.0, 0.0] if gt_mode else [float(v) for v in spawn])
        if ent.get('dynamic_obstacles'):
            ex['dynamic_obstacles'] = {k: {'size': list(v.get('size', [0.4, 0.4]))}
                                       for k, v in ent['dynamic_obstacles'].items()}
    elif a.method == 'responsiveness':
        ex.update(stack=a.stack, t_world_map=[float(v) for v in spawn])
    return ex


def method_plan(a, ent, spawn, run_dir, sdf=None, bridge_cfg=None, goals_file=None,
                delays=None):
    """-> dict(stack=[ProcessSpec], late=[ProcessSpec], gates=[names after G1-G3],
    extra_models=[...]). `late` processes are started after all gates pass."""
    sx, sy, syaw = spawn
    plan = dict(stack=[], late=[], gates=[], extra_models=[])
    if a.method == 'frontier':
        plan['stack'].append(ProcessSpec(
            'explore_stack',
            'ros2 launch vacuum_exploration exploration.launch.py environment:=%s '
            'spawn_x:=%.6f spawn_y:=%.6f spawn_yaw:=%.6f odom_mode:=eval headless:=%s '
            'use_rviz:=false database_path:=%s/rtabmap.db %s%s'
            % (a.world, sx, sy, syaw, _b(a.headless), run_dir, _noise_args(a),
               _explore_extra(a))))
        plan['gates'] = ['G4_tf', 'G5_nav', 'G6_map']
    elif a.method == 'scripted_goals':
        dyn = dynamic_models(ent)
        plan['extra_models'] = dyn
        plan['stack'].append(ProcessSpec(
            'sim', sim_cmd(a, spawn, sdf, bridge_cfg if dyn else None)))
        loc = _loc_mode(a)
        if loc == 'gt':
            # AMCL cannot be disabled via nav2_localization.launch.py args: plain nav2 + map_server
            plan['stack'].append(ProcessSpec(
                'nav2', 'ros2 launch vacuum_nav2 nav2.launch.py use_sim_time:=true', delay_s=12.0))
            plan['stack'].append(ProcessSpec(
                'map_server',
                "bash -c 'ros2 run nav2_map_server map_server --ros-args -p yaml_filename:=%s/gt_map.yaml "
                "-p use_sim_time:=true & sleep 3; ros2 lifecycle set /map_server configure; "
                "ros2 lifecycle set /map_server activate; wait'" % run_dir, delay_s=14.0))
            plan['stack'].append(ProcessSpec(
                'gt_localization',
                'ros2 run vacuum_eval gt_localization_node --ros-args -p use_sim_time:=true',
                delay_s=12.0))
            plan['gates'] = ['G5_nav', 'G4_tf', 'G6_map_server']
            twm = [0.0, 0.0, 0.0]
        elif a.nav_map == 'slam':
            env = a.world if a.world in SLAM_ENVS else 'room'
            plan['stack'].append(ProcessSpec(
                'slam', 'ros2 launch vacuum_slam slam.launch.py use_sim_time:=true use_rviz:=false '
                'delete_db:=true database_path:=%s/rtabmap.db environment:=%s' % (run_dir, env),
                delay_s=12.0))
            plan['stack'].append(ProcessSpec(
                'nav2', 'ros2 launch vacuum_nav2 nav2.launch.py use_sim_time:=true', delay_s=20.0))
            plan['gates'] = ['G4_tf', 'G5_nav', 'G6_map']
            twm = [sx, sy, syaw]
        else:
            plan['stack'].append(ProcessSpec(
                'nav2', 'ros2 launch vacuum_nav2 nav2_localization.launch.py map_path:=%s/gt_map.yaml '
                'use_rviz:=false use_sim_time:=true environment:=%s' % (run_dir, a.world),
                delay_s=12.0))
            plan['gates'] = ['G5_nav', 'initialpose', 'G4_tf', 'G6_map_server']
            twm = [0.0, 0.0, 0.0]
        plan['late'].append(ProcessSpec(
            'goal_sender',
            'ros2 run vacuum_eval goal_sender --ros-args -p use_sim_time:=true '
            '-p goals_file:=%s -p t_world_map:="[%.6f, %.6f, %.6f]"' % ((goals_file,) + tuple(twm)),
            critical=False))
        dobs = ent.get('dynamic_obstacles') or {}
        for i, (name, d) in enumerate(dobs.items()):
            wps = [float(c) for w in d['waypoints'] for c in w]
            delay = float(d.get('start_delay_s', 0.0)) + (delays[i] if delays else 0.0)
            plan['late'].append(ProcessSpec(
                'dynamic_mover_' + name,
                'ros2 run vacuum_eval dynamic_mover --ros-args -p use_sim_time:=true -p model:=%s '
                '-p waypoints:="[%s]" -p speed:=%.4f -p start_delay_s:=%.4f'
                % (name, ', '.join('%.4f' % c for c in wps), float(d.get('speed', 0.25)), delay),
                critical=False))
    elif a.method == 'responsiveness':
        if a.stack == 'loaded':
            plan['stack'].append(ProcessSpec(
                'explore_stack',
                'ros2 launch vacuum_exploration exploration.launch.py environment:=%s '
                'spawn_x:=%.6f spawn_y:=%.6f spawn_yaw:=%.6f odom_mode:=eval headless:=%s '
                'use_rviz:=false database_path:=%s/rtabmap.db start_manager:=false %s%s'
                % (a.world, sx, sy, syaw, _b(a.headless), run_dir, _noise_args(a),
                   _explore_extra(a))))
            plan['gates'] = ['G4_tf', 'G5_nav', 'G6_map']
        else:
            plan['stack'].append(ProcessSpec('sim', sim_cmd(a, spawn, sdf)))
        plan['late'].append(ProcessSpec(
            'responsiveness_test',
            'ros2 run vacuum_eval responsiveness_test --ros-args -p use_sim_time:=true '
            '-p output_file:=%s/responsiveness_events.csv' % run_dir, critical=False))
    else:
        raise NotImplementedError('method %s is not implemented in the harness yet' % a.method)
    return plan


def gate_map_server():
    return ros('ros2 topic echo --once /map --qos-durability transient_local '
               '--qos-reliability reliable --field info', 20)[0] == 0


GATES = {'G4_tf': gate_tf, 'G5_nav': gate_nav, 'G6_map': gate_map,
         'G6_map_server': gate_map_server, 'G7_rtabmap_alive': gate_rtabmap_alive}


def bridge_config_path():
    try:
        from ament_index_python.packages import get_package_share_directory
        p = os.path.join(get_package_share_directory('vacuum_gazebo'), 'config',
                         'gz_bridge_dynamic.yaml')
        if os.path.exists(p):
            return p
    except Exception:  # noqa: BLE001
        pass
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'vacuum_gazebo',
                        'config', 'gz_bridge_dynamic.yaml')


def tail_events(run_dir):
    p = os.path.join(run_dir, 'events.csv')
    if not os.path.exists(p):
        return [], []
    d = load_csv(p)
    return list(map(str, d.get('event', []))), list(map(str, d.get('detail', [])))


def monitor(run_dir, procs, timeout, meta_t=None):
    """Return end_reason. Wall 1 Hz poll; timeout/stuck from trajectory.csv; finish from events.csv."""
    stop = {'sig': False}
    t_mon, n_rows, t_grow, stalled = time.time(), -1, time.time(), False
    old = signal.signal(signal.SIGINT, lambda *_: stop.__setitem__('sig', True))
    try:
        while True:
            time.sleep(1.0)
            if stop['sig']:
                return 'aborted_by_user'
            for p in procs:
                if p.critical and not p.alive():
                    event(run_dir, 'process_exited', p.name)
                    return 'crash'
            lp = os.path.join(run_dir, 'loop_events.csv')
            try:
                with open(lp) as f:
                    nr = sum(1 for _ in f)
            except OSError:
                nr = 0
            if nr != n_rows:
                n_rows, t_grow = nr, time.time()
                stalled = False
            elif not stalled and time.time() - t_grow >= 20 and time.time() - t_mon >= 20:
                stalled = True
                event(run_dir, 'rtabmap_stalled', 'loop_events.csv not growing for 20 s')
            names, det = tail_events(run_dir)
            if 'finished_signal' in names:
                i = names.index('finished_signal')
                return 'goals_done' if 'done' in det[i].lower() else 'finished'
            tp = os.path.join(run_dir, 'trajectory.csv')
            cp = os.path.join(run_dir, 'cmd_vel.csv')
            if not (os.path.exists(tp) and os.path.exists(cp)):
                continue
            run = type('R', (), {})()
            run.trajectory, run.cmd_vel = load_csv(tp), load_csv(cp)
            start = cm.find_episode_start(run.cmd_vel)
            if start is None or 't' not in run.trajectory or len(run.trajectory['t']) == 0:
                continue
            now = float(run.trajectory['t'][-1])
            if now - start >= timeout:
                event(run_dir, 'timeout_reached', '', now)
                return 'timeout'
            ts = cm.find_stuck(run.trajectory, start)
            if ts is not None:
                event(run_dir, 'stuck_detected', '', ts)
                return 'stuck'
    finally:
        signal.signal(signal.SIGINT, old)


def shutdown(run_dir, procs, bag, eval_proc, slot=0):
    if eval_proc is not None and eval_proc.alive():
        ros('ros2 topic pub --once /eval/stop std_msgs/msg/Empty "{}"', 20)
        t_end = time.time() + 30
        while time.time() < t_end:
            if 'recorder_stopped' in tail_events(run_dir)[0]:
                break
            time.sleep(1)
    if bag is not None:
        bag.signal(signal.SIGINT)
        bag.wait(20)
    everyone = [p for p in procs + [eval_proc, bag] if p is not None]
    for p in everyone:
        p.signal(signal.SIGINT)
    t_end = time.time() + 15
    for p in everyone:
        p.wait(max(0.1, t_end - time.time()))
    for p in everyone:
        p.signal(signal.SIGKILL)
    # last resort: only gz processes belonging to THIS slot's partition
    for pid in pids_with_partition(slot_env(slot)[1]):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def write_meta(path, a, run_dir, spawn, worlds_ent, notes, extra=None):
    defaults_path = os.path.join(cm._config_dir(), 'eval_defaults.yaml')
    with open(defaults_path) as f:
        snap = yaml.safe_load(f)
    commit, dirty = git_info()
    meta = dict(
        experiment=a.experiment, world=a.world,
        world_name_in_sdf=worlds_ent.get('world_name_in_sdf', a.world), method=a.method,
        seed=a.seed, spawn_x=spawn[0], spawn_y=spawn[1], spawn_yaw=spawn[2],
        odom_noise=bool(a.odom_noise), odom_noise_params=snap.get('odom_noise', {}),
        noise_seed=a.seed + 1000, git_commit=commit, git_dirty=dirty, config_snapshot=snap,
        start_wall_iso=datetime.datetime.now().astimezone().isoformat(),
        episode_timeout_sim_sec=a.timeout_sim_sec,
        swath_width_m=snap.get('swath_width_m', 0.25),
        grid_resolution_m=snap.get('grid_resolution_m', 0.05), headless=bool(a.headless),
        slot=int(getattr(a, 'slot', 0)), ros_domain_id=slot_env(getattr(a, 'slot', 0))[0],
        gz_partition=slot_env(getattr(a, 'slot', 0))[1], lean=int(getattr(a, 'lean', 0)),
        gpu=int(getattr(a, 'gpu', 0)),
        versions=dict(gz=version_of(['bash', '-c', ROS_ENV + 'gz sim --version']),
                      python=sys.version.split()[0]),
        run_notes=notes)
    meta.update(extra or {})
    with open(path, 'w') as f:
        yaml.safe_dump(meta, f, sort_keys=False)
    return meta


def finish(run_dir, reason, wall0, failed_note=None):
    mp = os.path.join(run_dir, 'run_meta.yaml')
    with open(mp) as f:
        meta = yaml.safe_load(f)
    meta['end_reason'] = reason
    meta['wall_elapsed_sec'] = time.time() - wall0
    with open(mp, 'w') as f:
        yaml.safe_dump(meta, f, sort_keys=False)
    out = cm.compute(run_dir)
    if failed_note:
        out['notes'].append(failed_note)
        out['status'] = 'failed'
    cm.write_summary(run_dir, out)
    print('%s %s %s %s' % (run_dir, out['status'], out['end_reason'], out['episode_sim_sec']))
    print('VALIDITY: %s img_drop_pct=%s rtabmap_updates=%s max_gap_s=%s%s' % (
        'VALID' if out.get('episode_valid') else 'INVALID' if out.get('episode_valid') is False
        else 'UNKNOWN', out.get('img_drop_pct'), out.get('rtabmap_updates'),
        out.get('rtabmap_max_gap_s'),
        ' reasons=' + '; '.join(out.get('invalid_reasons') or []) if out.get('invalid_reasons') else ''))
    return out


def run_one(a):
    root = os.path.expanduser(a.runs_root)
    slot = int(getattr(a, 'slot', 0))
    set_slot(slot)
    rc = preflight(root, slot)
    if rc:
        return rc
    try:
        return _run_one(a, root, slot)
    finally:
        release_slot_lock(slot, root)


def _run_one(a, root, slot):
    run_dir = os.path.join(root, a.experiment, a.world,
                           method_dir_name(a.method, a.goal_list if a.method == 'scripted_goals' else None,
                                           a.nav_map, a.stack), 'seed_%03d' % a.seed)
    sp = os.path.join(run_dir, 'summary.json')
    if os.path.exists(sp) and not a.force:
        try:
            import json
            if json.load(open(sp)).get('status') == 'ok':
                print('skip (finished): %s' % run_dir)
                return 0
        except Exception:  # noqa: BLE001
            pass
    os.makedirs(run_dir, exist_ok=True)
    wall0 = time.time()
    worlds_cfg = cm.load_worlds_cfg()
    ent = cm.world_entry(worlds_cfg, a.world)
    notes = []
    goal_list, delays, sdf, goals_file = None, [], None, None
    if a.method == 'scripted_goals':
        goal_list = resolve_goal_list(a, ent)
    if goal_list == 'scenario':
        spawn, delays = scenario_draws(a.seed, ent['scenario']['start'],
                                       len(dynamic_models(ent)))
    elif ent.get('spawn_candidates'):
        spawn = sample_spawn(a.seed, ent['spawn_candidates'])
    else:
        spawn = (0.0, 0.0, 0.0)
        notes.append('worlds.yaml has no spawn_candidates for %s: spawn fixed at 0,0,0' % a.world)
    if ent.get('sdf_file') and a.method != 'frontier':
        sdf = cm.resolve_sdf(ent['sdf_file'])
    if a.timeout_sim_sec is None:
        a.timeout_sim_sec = float(ent.get('timeout_sim_sec', 1200))
    if a.method == 'scripted_goals':
        gt = None
        if goal_list in ('random20', 'near_wall', 'long_range'):
            gt = cm.gt_grid_for(a.world, worlds_cfg)
        goals_file = os.path.join(run_dir, 'goals.yaml')
        write_goals(goals_file, select_goals(goal_list, a.seed, ent, spawn, gt))
        if a.nav_map == 'gt':
            export_gt_map(a.world, worlds_cfg, run_dir)
    write_meta(os.path.join(run_dir, 'run_meta.yaml'), a, run_dir, spawn, ent, notes,
               meta_extras(a, ent, spawn, goal_list))
    event(run_dir, 'harness_started', ' '.join(notes))
    plan = method_plan(a, ent, spawn, run_dir, sdf=sdf, bridge_cfg=bridge_config_path(),
                       goals_file=goals_file, delays=delays)

    procs, bag, ev = [], None, None
    reason = None
    try:
        bag = Proc('bag', 'ros2 bag record -o %s/bag --use-sim-time -s sqlite3 %s'
                   % (run_dir, bag_topics(getattr(a, 'lean', 0))), run_dir)
        t_stack = time.time()
        for sp in plan['stack']:
            time.sleep(max(0.0, sp.delay_s - (time.time() - t_stack)))
            procs.append(Proc(sp.name, sp.cmd, run_dir, sp.critical))
        gates = [('G1_clock', gate_clock, 120), ('G2_controllers', gate_controllers, 120),
                 ('G3_gt_odom', gate_gt, 120)]
        ok = True
        for n, fn, b in gates:
            ok = ok and wait_gate(n, fn, b, run_dir)
        if ok:
            ev = Proc('eval_stack', eval_cmd(run_dir, plan['extra_models']), run_dir)
            t_budget = time.time() + 240
            for n in plan['gates'] + (['G7_rtabmap_alive'] if 'G6_map' in plan['gates'] else []):
                if n == 'initialpose':
                    ros(initialpose_cmd(spawn), 30)
                    event(run_dir, 'amcl_initial_pose_sent', '%.3f %.3f %.3f' % spawn)
                    continue
                ok = ok and wait_gate(n, GATES[n], min(120, max(1, t_budget - time.time())),
                                      run_dir)
        if not ok:
            reason = 'bringup_failed'
        else:
            for sp in plan['late']:
                procs.append(Proc(sp.name, sp.cmd, run_dir, sp.critical))
            reason = monitor(run_dir, procs + [ev], a.timeout_sim_sec)
    except KeyboardInterrupt:
        reason = 'aborted_by_user'
    except Exception as e:  # noqa: BLE001
        event(run_dir, 'harness_error', repr(e))
        reason = 'bringup_failed'
    finally:
        event(run_dir, 'stopping', reason or '')
        shutdown(run_dir, procs, bag, ev, slot)
    out = finish(run_dir, reason, wall0)
    return 0 if out['status'] in ('ok', 'partial') else 1


def build_parser():
    ap = argparse.ArgumentParser(description='Run one evaluation episode')
    ap.add_argument('--experiment', required=True)
    ap.add_argument('--world', required=True)
    ap.add_argument('--method', default='frontier', choices=['frontier', 'scripted_goals', 'responsiveness'])
    ap.add_argument('--stack', choices=['bare', 'loaded'], default='bare')
    ap.add_argument('--nav-map', choices=['gt', 'slam'], default='gt')
    ap.add_argument('--localization', choices=['auto', 'slam', 'amcl', 'gt'], default='auto',
                    help='scripted_goals localization source (auto = slam for --nav-map slam, '
                         'amcl for gt)')
    ap.add_argument('--goal-list', choices=list(GOAL_LISTS), default=None,
                    help='scripted_goals; default: scenario for avoid_* worlds else fixed')
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--odom-noise', type=int, choices=[0, 1], default=0)
    ap.add_argument('--headless', type=int, choices=[0, 1], default=1)
    ap.add_argument('--timeout-sim-sec', type=float, default=None,
                    help='default: worlds.yaml timeout_sim_sec or 1200')
    ap.add_argument('--runs-root', default='~/eval_runs')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--slot', type=int, default=0,
                    help='parallel slot N: ROS_DOMAIN_ID=10+N (0 for slot 0), GZ_PARTITION=vacuum_slotN')
    ap.add_argument('--lean', type=int, choices=[0, 1], default=0,
                    help='1 = disable optional nodes and trim the bag (batch passes 1)')
    ap.add_argument('--gpu', type=int, choices=[0, 1], default=0,
                    help='1 = render_gpu:=true (do not pool with gpu=0 results)')
    return ap


def main(argv=None):
    return run_one(build_parser().parse_args(argv))


if __name__ == '__main__':
    sys.exit(main())
