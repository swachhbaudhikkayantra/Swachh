#!/usr/bin/env python3
"""Offline orchestrator: run_dir -> summary.json / summary.csv (docs/specs/02 section 2.8)."""

import argparse
import csv
import math
import os
import sys

import numpy as np
import yaml

from vacuum_eval.metrics import (coverage, gt_grid, loop_closure, navigation, resources,
                                 responsiveness, safety, trajectory)
from vacuum_eval.metrics.common import load_run, write_json

MODULE_ORDER = ['resources', 'coverage', 'trajectory', 'navigation', 'safety',
                'responsiveness', 'loop_closure', 'counters']
ALWAYS_KEYS = ['experiment', 'world', 'method', 'seed', 'odom_noise', 'spawn_x', 'spawn_y',
               'spawn_yaw', 'status', 'end_reason', 'episode_sim_sec', 'bringup_sim_sec',
               'wall_elapsed_sec', 'n_cmd_ticks', 'n_goals', 'distance_gt_m', 'notes']
HARNESS_REASONS = ('crash', 'aborted_by_user', 'bringup_failed')
FAILED_REASONS = ('no_motion', 'crash', 'bringup_failed')
MOTION_EPS = 0.01
STUCK_WINDOW_S = 180.0
STUCK_DIST_M = 0.30


def _config_dir():
    try:
        from ament_index_python.packages import get_package_share_directory
        d = os.path.join(get_package_share_directory('vacuum_eval'), 'config')
        if os.path.isdir(d):
            return d
    except Exception:
        pass
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config')


def resolve_sdf(p):
    """Resolve '<share>/vacuum_gazebo/worlds/x.sdf' or 'vacuum_gazebo/worlds/x.sdf' to a file path."""
    p = os.path.expanduser(str(p))
    if os.path.isabs(p) and os.path.exists(p):
        return p
    rel = p[len('<share>/'):] if p.startswith('<share>/') else p
    try:
        from ament_index_python.packages import get_package_share_directory
        share_root = os.path.dirname(get_package_share_directory('vacuum_gazebo'))
        cand = os.path.join(share_root, rel)
        if os.path.exists(cand):
            return cand
    except Exception:
        pass
    here = os.path.dirname(os.path.abspath(__file__))
    src_root = os.path.abspath(os.path.join(here, '..', '..'))      # .../src
    cand = os.path.join(src_root, rel.replace('vacuum_gazebo/worlds', 'vacuum_gazebo/worlds', 1))
    return cand if os.path.exists(cand) else p


def load_worlds_cfg(path=None):
    """worlds.yaml merged with worlds_scenarios.yaml (both have a top-level 'worlds' map)."""
    path = path or os.path.join(_config_dir(), 'worlds.yaml')
    cfg = {}
    if os.path.exists(path):
        with open(path) as f:
            cfg = yaml.safe_load(f) or {}
    scen = os.path.join(os.path.dirname(path), 'worlds_scenarios.yaml')
    if os.path.exists(scen):
        with open(scen) as f:
            extra = yaml.safe_load(f) or {}
        base = cfg.setdefault('worlds', {})
        base.update(extra.get('worlds', extra))
    return cfg


def world_entry(worlds_cfg, world):
    w = (worlds_cfg or {}).get('worlds', worlds_cfg or {})
    return (w or {}).get(world) or {}


def gt_grid_for(world, worlds_cfg, gt_dir=None):
    """Cached GT grid at <gt_dir>/<world>.npz (default ~/eval_runs/_gt); built from worlds.yaml if absent."""
    gt_dir = gt_dir or os.path.expanduser('~/eval_runs/_gt')
    path = os.path.join(gt_dir, '%s.npz' % world)
    if os.path.exists(path):
        return gt_grid.load(path)
    ent = world_entry(worlds_cfg, world)
    if not ent.get('sdf_file') or not ent.get('reachable_seed'):
        raise FileNotFoundError('no GT grid %s and no sdf_file/reachable_seed in worlds.yaml' % path)
    gt = gt_grid.build(resolve_sdf(ent['sdf_file']), tuple(ent['reachable_seed']))
    os.makedirs(gt_dir, exist_ok=True)
    gt_grid.save(gt, path)
    return gt


# ------------------------------------------------------------------ episode window
def _arr(tbl, key):
    return np.asarray(tbl[key], dtype=float) if tbl and key in tbl else np.array([])


def find_episode_start(cmd_vel):
    """First ctrl_stamped row with |vx|>0.01 or |wz|>0.01, else None."""
    if not cmd_vel or 'source' not in cmd_vel or len(cmd_vel['source']) == 0:
        return None
    src = np.asarray(cmd_vel['source']).astype(str)
    m = (src == 'ctrl_stamped') & ((np.abs(_arr(cmd_vel, 'vx')) > MOTION_EPS) |
                                   (np.abs(_arr(cmd_vel, 'wz')) > MOTION_EPS))
    idx = np.flatnonzero(m)
    return float(_arr(cmd_vel, 't')[idx[0]]) if idx.size else None


def find_stuck(traj, t_from, window=STUCK_WINDOW_S, dist=STUCK_DIST_M):
    """Return the sim time at which the stuck rule first fires (end of the window), or None.

    GT sampled every 1 s from t_from; fires when the max displacement from the window's first
    sample stays below `dist` for `window` seconds. Rotation does not prevent it (spec T-024)."""
    if not traj or 'gt_x' not in traj:
        return None
    t = _arr(traj, 't')
    x, y = _arr(traj, 'gt_x'), _arr(traj, 'gt_y')
    ok = np.isfinite(t) & np.isfinite(x) & np.isfinite(y) & (t >= t_from)
    t, x, y = t[ok], x[ok], y[ok]
    if t.size == 0:
        return None
    grid = np.arange(t[0], t[-1] + 1e-9, 1.0)
    idx = np.clip(np.searchsorted(t, grid, side='right') - 1, 0, t.size - 1)
    gx, gy, gt_ = x[idx], y[idx], grid
    n = int(round(window))
    for i in range(0, len(gt_) - n):
        d = np.hypot(gx[i:i + n + 1] - gx[i], gy[i:i + n + 1] - gy[i])
        if d.max() < dist:
            return float(gt_[i + n])
    return None


def determine_episode(run, notes=None):
    """Fill run.episode_start_t/end_t; return dict(end_reason, status_failed, bringup)."""
    meta = run.meta or {}
    traj_t = _arr(run.trajectory, 't')
    t_first = float(traj_t[0]) if traj_t.size else 0.0
    t_last = float(traj_t[-1]) if traj_t.size else 0.0
    start = find_episode_start(run.cmd_vel)
    meta_reason = meta.get('end_reason')
    if start is None:
        run.episode_start_t = run.episode_end_t = t_first
        reason = meta_reason if meta_reason in HARNESS_REASONS else 'no_motion'
        return dict(end_reason=reason, t0=t_first, has_start=False)
    run.episode_start_t = start
    timeout = float(meta.get('episode_timeout_sim_sec') or 1200.0)
    cands = []
    ev = run.events
    if ev and 'event' in ev:
        names = np.asarray(ev['event']).astype(str)
        det = np.asarray(ev['detail']).astype(str) if 'detail' in ev else np.array([''] * len(names))
        et = _arr(ev, 't')
        for i, n in enumerate(names):
            if n == 'finished_signal' and et.size and et[i] >= start:
                scripted = 'done' in det[i].lower() or 'goals' in det[i].lower() or \
                    meta.get('method') == 'scripted_goals'
                cands.append((float(et[i]), 'goals_done' if scripted else 'finished'))
    cands.append((start + timeout, 'timeout'))
    ts = find_stuck(run.trajectory, start)
    if ts is not None:
        cands.append((ts, 'stuck'))
    cands.append((t_last, 'timeout' if t_last - start >= timeout else 'trajectory_end'))
    t_end, reason = min(cands, key=lambda c: c[0])
    if reason == 'trajectory_end':
        reason = meta_reason if meta_reason in HARNESS_REASONS + ('timeout', 'stuck') else 'crash'
        if meta_reason is None and notes is not None:
            notes.append('episode ended at last trajectory row without an end signal; end_reason=crash')
    elif meta_reason in HARNESS_REASONS:
        reason, t_end = meta_reason, min(t_end, t_last)
    run.episode_end_t = float(max(t_end, start))
    return dict(end_reason=reason, t0=t_first, has_start=True)


# ------------------------------------------------------------------ modules
def _counters(run):
    t0, t1 = run.episode_start_t, run.episode_end_t
    out = {'n_cmd_ticks': 0, 'n_goals': 0, 'distance_gt_m': 0.0}
    c = run.cmd_vel
    if c and 'source' in c:
        t = _arr(c, 't')
        m = (np.asarray(c['source']).astype(str) == 'ctrl_stamped') & (t >= t0) & (t <= t1)
        out['n_cmd_ticks'] = int(m.sum())
    g = run.goal_events
    if g and 'src' in g:
        src = np.asarray(g['src']).astype(str)
        ev = np.asarray(g['event']).astype(str)
        t = _arr(g, 't')
        m = np.isin(src, ['explore', 'scripted']) & (ev == 'started')
        if t.size:
            m &= (t >= t0) & (t <= t1)
        out['n_goals'] = int(m.sum())
    tr = run.trajectory
    if tr and 'gt_x' in tr:
        t = _arr(tr, 't')
        m = (t >= t0) & (t <= t1)
        x, y = _arr(tr, 'gt_x')[m], _arr(tr, 'gt_y')[m]
        ok = np.isfinite(x) & np.isfinite(y)
        x, y = x[ok], y[ok]
        out['distance_gt_m'] = float(np.hypot(np.diff(x), np.diff(y)).sum()) if x.size > 1 else 0.0
    return out


def _need_gt(ctx):
    if 'gt' not in ctx:
        try:
            ctx['gt'] = gt_grid_for(ctx['run'].meta.get('world'), ctx['worlds_cfg'], ctx.get('gt_dir'))
            ctx['gt_error'] = None
        except Exception as e:  # noqa: BLE001
            ctx['gt'] = None
            ctx['gt_error'] = e
    if ctx['gt'] is None:
        raise RuntimeError('ground-truth grid unavailable: %s' % ctx['gt_error'])
    return ctx['gt']


MODULES = {
    'resources': lambda c: resources.compute_resource_metrics(c['run']),
    'coverage': lambda c: coverage.compute_coverage(c['run'], _need_gt(c)),
    'trajectory': lambda c: trajectory.compute_trajectory_metrics(c['run']),
    'navigation': lambda c: navigation.compute_navigation_metrics(c['run'], _need_gt(c)),
    'safety': lambda c: safety.compute_safety_metrics(c['run'], _need_gt(c), c['worlds_cfg']),
    'responsiveness': lambda c: responsiveness.compute_responsiveness_metrics(c['run']),
    'loop_closure': lambda c: loop_closure.compute_loop_closure_metrics(c['run']),
    'counters': lambda c: _counters(c['run']),
}

_KEYS = {
    'resources': lambda: list(resources._BASE_KEYS),
    'coverage': lambda: list(coverage.COVERAGE_KEYS),
    'trajectory': lambda: list(trajectory.SLAM_KEYS) + list(trajectory.ODOM_KEYS),
    'counters': lambda: ['n_cmd_ticks', 'n_goals', 'distance_gt_m'],
}


def _null_keys(name):
    try:
        return _KEYS[name]()
    except Exception:  # noqa: BLE001
        return []


def compute(run_dir, only=None, gt_dir=None, worlds_cfg=None):
    run = load_run(run_dir)
    notes = []
    info = determine_episode(run, notes)
    meta = run.meta or {}
    reason = info['end_reason']
    status = 'failed' if reason in FAILED_REASONS else 'ok'
    ctx = {'run': run, 'gt_dir': gt_dir,
           'worlds_cfg': worlds_cfg if worlds_cfg is not None else load_worlds_cfg()}
    summary = {}
    names = [m for m in MODULE_ORDER if only is None or m in only]
    for name in names:
        try:
            res = dict(MODULES[name](ctx) or {})
            notes.extend(str(n) for n in (res.pop('notes', None) or []))
            summary.update(res)
        except Exception as e:  # noqa: BLE001
            for k in _null_keys(name):
                summary[k] = None
            notes.append('%s: %s' % (name, e))
            if status == 'ok':
                status = 'partial'
    dur = run.episode_end_t - run.episode_start_t
    base = {k: meta.get(k) for k in ['experiment', 'world', 'method', 'seed', 'odom_noise',
                                     'spawn_x', 'spawn_y', 'spawn_yaw']}
    base['odom_noise'] = None if base['odom_noise'] is None else int(bool(base['odom_noise']))
    base.update(status=status, end_reason=reason,
                episode_sim_sec=float(dur) if info['has_start'] else None,
                bringup_sim_sec=float(run.episode_start_t - info['t0']) if info['has_start'] else None,
                wall_elapsed_sec=meta.get('wall_elapsed_sec'))
    for k in ('n_cmd_ticks', 'n_goals', 'distance_gt_m'):
        base[k] = summary.get(k)
    out = dict(summary)
    out.update(base)
    out['notes'] = notes
    return out


def write_summary(run_dir, out):
    write_json(os.path.join(run_dir, 'summary.json'), out)
    keys = sorted(out)
    row = []
    for k in keys:
        v = out[k]
        if k == 'notes':
            v = '|'.join(v)
        elif v is None:
            v = ''
        elif isinstance(v, (bool, np.bool_)):
            v = int(v)
        elif isinstance(v, (float, np.floating)) and not math.isfinite(v):
            v = ''
        row.append(v)
    with open(os.path.join(run_dir, 'summary.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(keys)
        w.writerow(row)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Compute metrics of one run directory')
    ap.add_argument('run_dir')
    ap.add_argument('--only', default=None, help='comma-separated module names')
    ap.add_argument('--gt-dir', default=None)
    a = ap.parse_args(argv)
    run_dir = os.path.expanduser(a.run_dir)
    only = [s for s in a.only.split(',') if s] if a.only else None
    out = compute(run_dir, only, a.gt_dir)
    write_summary(run_dir, out)
    print('%s status=%s end_reason=%s episode_sim_sec=%s' %
          (run_dir, out['status'], out['end_reason'], out['episode_sim_sec']))
    return 3 if out['status'] == 'failed' else 0


if __name__ == '__main__':
    sys.exit(main())
