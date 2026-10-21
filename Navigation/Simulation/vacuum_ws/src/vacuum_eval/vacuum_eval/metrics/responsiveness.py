"""Responsiveness: step-test, goal-motion and obstacle reaction latencies, topic-rate
health (docs/specs/07). Times are sim seconds, except step-test (cmd_motion/stop)
primary latencies which are wall-clock controller latency (Decision 2026-10-21)."""

import math
from typing import Dict, List, Optional

import numpy as np

from .common import Run, wrap_angle

DEFAULT_DEADLINES = {'cmd_motion': 0.5, 'stop': 0.5, 'goal_motion': 2.0, 'obstacle': 1.0}
DEFAULT_RATE_FLOOR = {'odom': 27, 'depth': 27, 'color': 27, 'cmd_nav': 16, 'cmd_smoothed': 16,
                      'tf_map_odom': 1, 'scan': 9}
GOAL_GATED = ('cmd_nav', 'cmd_smoothed')
RATE_COLS = {'odom': 'n_odom', 'depth': 'n_depth', 'color': 'n_color', 'cmd_nav': 'n_cmd_nav',
             'cmd_smoothed': 'n_cmd_smoothed', 'tf_map_odom': 'n_tf_map_odom', 'scan': 'n_scan'}
MISS_FACTOR = 3.0
GOAL_VX, GOAL_WZ = 0.05, 0.10
OBS_CLEARANCE_M, HFOV_HALF = 1.5, 0.6056
OBS_V_MOVING, OBS_V_REF_MIN, OBS_VX_FRAC, OBS_WZ = 0.05, 0.05, 0.7, 0.3
ROBOT_HX, ROBOT_HY = 0.150, 0.125
DEFAULT_DYN_SIZE = (0.4, 0.4)
TYPE_KEY = {'cmd_motion': 'cmd', 'stop': 'stop', 'goal_motion': 'goal', 'obstacle': 'obstacle'}


def _obj_eq(arr, val):
    return np.array([str(x) == val for x in arr], dtype=bool)


def _event(kind, t_a, t_b, deadline) -> dict:
    """Latency record; a response later than 3x deadline counts as no response."""
    L = None
    if t_b is not None and not (isinstance(t_b, float) and math.isnan(t_b)):
        L = float(t_b) - float(t_a)
        if L > MISS_FACTOR * deadline:
            L = None
    return {'kind': kind, 't_a': float(t_a), 'latency_s': L,
            'met': L is not None and L <= deadline + 1e-9}


def _window(run: Run, t):
    if run.episode_end_t > run.episode_start_t:
        return (t >= run.episode_start_t) & (t <= run.episode_end_t)
    return np.ones(len(t), dtype=bool)


def _has_wall(run: Run) -> bool:
    re = run.responsiveness_events
    return re is not None and 'wall_latency_s' in re


def step_events(run: Run, deadlines, wall=False) -> List[dict]:
    re = run.responsiveness_events
    out = []
    if re is None or 'event' not in re:
        return out
    for k in range(len(re['event'])):
        kind = str(re['event'][k])
        if kind not in ('cmd_motion', 'stop'):
            continue
        if wall and 'wall_latency_s' in re:
            wl = float(re['wall_latency_s'][k])
            out.append(_event(kind, 0.0, None if math.isnan(wl) else wl, deadlines[kind]))
            continue
        lat = float(re['latency_s'][k]) if 'latency_s' in re else float('nan')
        t_a = float(re['t_a'][k])
        t_b = float(re['t_b'][k]) if 't_b' in re else float('nan')
        if math.isnan(t_b) and not math.isnan(lat):
            t_b = t_a + lat
        out.append(_event(kind, t_a, None if math.isnan(t_b) else t_b, deadlines[kind]))
    return out


def goal_events_list(run: Run, deadlines) -> List[dict]:
    ge, tr = run.goal_events, run.trajectory
    out = []
    if ge is None or tr is None or 'event' not in ge:
        return out
    tt = np.asarray(tr['t'], float)
    vx = np.abs(np.asarray(tr['gt_vx'], float))
    wz = np.abs(np.asarray(tr['gt_wz'], float))
    mov = (vx >= GOAL_VX) | (wz >= GOAL_WZ)
    for k in range(len(ge['event'])):
        if str(ge['event'][k]) != 'started' or str(ge['src'][k]) not in ('explore', 'scripted'):
            continue
        t_a = float(ge['t'][k])
        if run.episode_end_t > run.episode_start_t and not (
                run.episode_start_t <= t_a <= run.episode_end_t):
            continue
        idx = np.nonzero((tt > t_a) & mov)[0]
        out.append(_event('goal_motion', t_a, float(tt[idx[0]]) if len(idx) else None,
                          deadlines['goal_motion']))
    return out


def _perimeter(cx, cy, yaw, size, step=0.02):
    hx, hy = size[0] / 2, size[1] / 2
    nx, ny = max(int(round(size[0] / step)), 1), max(int(round(size[1] / step)), 1)
    xs, ys = np.linspace(-hx, hx, nx + 1), np.linspace(-hy, hy, ny + 1)
    pts = np.concatenate([np.stack([xs, np.full_like(xs, -hy)], 1),
                          np.stack([xs, np.full_like(xs, hy)], 1),
                          np.stack([np.full_like(ys, -hx), ys], 1),
                          np.stack([np.full_like(ys, hx), ys], 1)])
    c, s = math.cos(yaw), math.sin(yaw)
    return np.stack([cx + c * pts[:, 0] - s * pts[:, 1], cy + s * pts[:, 0] + c * pts[:, 1]], 1)


def _clearance(x, y, yaw, ox, oy, oyaw, size) -> float:
    """Distance from the robot rectangle to the obstacle rectangle (perimeter samples)."""
    p = _perimeter(ox, oy, oyaw, size)
    dx, dy = p[:, 0] - x, p[:, 1] - y
    c, s = math.cos(yaw), math.sin(yaw)
    px, py = c * dx + s * dy, -s * dx + c * dy
    d = np.hypot(np.maximum(np.abs(px) - ROBOT_HX, 0.0), np.maximum(np.abs(py) - ROBOT_HY, 0.0))
    return float(d.min())


def obstacle_events(run: Run, deadlines) -> List[dict]:
    do, tr, cv = run.dyn_obstacles, run.trajectory, run.cmd_vel
    out = []
    if do is None or tr is None or cv is None or 'name' not in do:
        return out
    tt = np.asarray(tr['t'], float)
    gx, gy, gyaw = (np.asarray(tr[k], float) for k in ('gt_x', 'gt_y', 'gt_yaw'))
    sm = _obj_eq(cv['source'], 'smoothed')
    ct, cvx, cwz = (np.asarray(cv[k], float)[sm] for k in ('t', 'vx', 'wz'))
    sizes = run.meta.get('dynamic_obstacles', {}) or {}
    win = _window(run, tt)
    for name in dict.fromkeys(str(n) for n in do['name']):
        m = _obj_eq(do['name'], name)
        dt_, dx_, dy_, dyaw = (np.asarray(do[k], float)[m] for k in ('t', 'x', 'y', 'yaw'))
        size = tuple(sizes.get(name, {}).get('size', DEFAULT_DYN_SIZE)) if isinstance(
            sizes.get(name, {}), dict) else DEFAULT_DYN_SIZE
        t_a = None
        for i in range(len(tt)):
            if not win[i] or np.isnan(gx[i]) or np.isnan(gy[i]) or np.isnan(gyaw[i]):
                continue
            if tt[i] < dt_[0] or tt[i] > dt_[-1]:
                continue
            ox, oy = np.interp(tt[i], dt_, dx_), np.interp(tt[i], dt_, dy_)
            oyaw = float(dyaw[np.argmin(np.abs(dt_ - tt[i]))])
            if _clearance(gx[i], gy[i], gyaw[i], ox, oy, oyaw, size) > OBS_CLEARANCE_M:
                continue
            if abs(wrap_angle(math.atan2(oy - gy[i], ox - gx[i]) - gyaw[i])) > HFOV_HALF:
                continue
            prev = (ct >= tt[i] - 1.0) & (ct <= tt[i])
            if (not prev.any() or ct[0] > tt[i] - 1.0 + 1e-9
                    or cvx[prev].min() < OBS_V_MOVING):
                continue
            t_a = float(tt[i])
            break
        if t_a is None:
            continue
        prev = (ct >= t_a - 1.0) & (ct <= t_a)
        v_ref = float(cvx[prev].mean())
        if v_ref < OBS_V_REF_MIN:
            continue
        resp = (ct > t_a) & ((cvx <= OBS_VX_FRAC * v_ref) | (np.abs(cwz) >= OBS_WZ))
        idx = np.nonzero(resp)[0]
        out.append(_event('obstacle', t_a, float(ct[idx[0]]) if len(idx) else None,
                          deadlines['obstacle']))
    return out


def topic_rate_health(run: Run, rate_floor=None):
    """Returns (pct, flags): pct {name: percent or None}; flags {name: bool array of
    windows (inside the episode window) that FAIL the floor; for goal-gated topics only
    windows with an active goal are evaluated}."""
    floors = dict(DEFAULT_RATE_FLOOR)
    floors.update(rate_floor or {})
    ra = run.rates
    pct, flags = {}, {}
    if ra is None or 't' not in ra:
        return {n: None for n in floors}, flags
    t = np.asarray(ra['t'], float)
    win = _window(run, t)
    t = t[win]
    active = np.zeros(len(t), dtype=bool)
    ge = run.goal_events
    if ge is not None and 'event' in ge:
        ivs, open_t = [], None
        for k in range(len(ge['event'])):
            if str(ge['src'][k]) not in ('explore', 'scripted'):
                continue
            ev = str(ge['event'][k])
            if ev == 'started':
                open_t = float(ge['t'][k])
            elif ev == 'ended' and open_t is not None:
                ivs.append((open_t, float(ge['t'][k])))
                open_t = None
        if open_t is not None:
            ivs.append((open_t, float('inf')))
        for a, b in ivs:
            active |= (t > a) & (t - 1.0 < b)
    for name, floor in floors.items():
        col = RATE_COLS.get(name)
        if col is None or col not in ra:
            pct[name] = None
            continue
        n = np.asarray(ra[col], float)[win]
        sel = active if name in GOAL_GATED else np.ones(len(t), dtype=bool)
        if not sel.any():
            pct[name] = None
            continue
        fail = (n < floor) & sel
        flags[name] = fail
        pct[name] = 100.0 * float(np.sum(sel & ~fail)) / float(sel.sum())
    return pct, flags


def compute_responsiveness_metrics(run: Run, deadlines: Optional[Dict[str, float]] = None,
                                   rate_floor: Optional[Dict[str, float]] = None) -> dict:
    dl = dict(DEFAULT_DEADLINES)
    dl.update(deadlines or {})
    use_wall = _has_wall(run)
    events = (step_events(run, dl, wall=use_wall) + goal_events_list(run, dl) + obstacle_events(run, dl))
    out: dict = {}
    n_all = len(events)
    n_met = sum(e['met'] for e in events)
    out['resp_n_events'] = n_all
    out['resp_n_met'] = n_met
    out['responsiveness_pct'] = 100.0 * n_met / n_all if n_all else None
    for kind, short in TYPE_KEY.items():
        ev = [e for e in events if e['kind'] == kind]
        out['resp_%s_pct' % short] = (100.0 * sum(e['met'] for e in ev) / len(ev)) if ev else None
        lat = np.array([e['latency_s'] for e in ev if e['latency_s'] is not None]) * 1000.0
        out['lat_%s_ms_mean' % kind] = float(lat.mean()) if len(lat) else None
        out['lat_%s_ms_p95' % kind] = float(np.percentile(lat, 95)) if len(lat) else None
    out['resp_definition'] = 'wall_clock_controller_latency'
    notes: List[str] = []
    if not use_wall and any(e['kind'] in ('cmd_motion', 'stop') for e in events):
        notes.append('wall-clock stamps missing')
    out['notes'] = notes
    sim = step_events(run, dl, wall=False)
    for kind in ('cmd_motion', 'stop'):
        lat = np.array([e['latency_s'] for e in sim if e['kind'] == kind
                        and e['latency_s'] is not None]) * 1000.0
        out['lat_%s_ms_mean_sim' % kind] = float(lat.mean()) if len(lat) else None
        out['lat_%s_ms_p95_sim' % kind] = float(np.percentile(lat, 95)) if len(lat) else None
    stack = run.meta.get('stack')
    out['resp_stack'] = stack if stack in ('bare', 'loaded') else 'episode'
    pct, _ = topic_rate_health(run, rate_floor)
    for name, v in pct.items():
        out['topic_ok_pct_' + name] = v
    vals = [v for v in pct.values() if v is not None]
    out['topic_ok_pct_min'] = min(vals) if vals else None
    return out
