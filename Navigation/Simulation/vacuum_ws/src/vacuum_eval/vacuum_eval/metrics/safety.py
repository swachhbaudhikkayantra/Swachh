"""Safety metrics: collisions, clearance, encounters (docs/specs/06). No ROS."""

import math
import re
from typing import Dict, List, Optional

import numpy as np
from scipy.spatial import cKDTree

from . import geometry
from .common import GtGrid, Run
from .navigation import compute_navigation_metrics, _row_dt, _s, _f

HALF_L, HALF_W = 0.150, 0.125
QUERY_R = 1.2
CAP = 1.0
DEFAULT_WALLS = r'^wall_|^ceiling$'


def _cfg(worlds_cfg, gt):
    cfg = worlds_cfg or {}
    if 'worlds' in cfg:
        ws = cfg['worlds'] or {}
        nm = str(gt.world_name)
        if nm in ws:
            cfg = ws[nm]
        else:  # GT stores the SDF <world name>, e.g. 'apartment_world' for key 'apartment'
            for k, v in ws.items():
                if nm == k + '_world' or (isinstance(v, dict) and nm == v.get('world_name_in_sdf')):
                    cfg = v
                    break
    return cfg


# ---------------------------------------------------------------- collisions
def collision_events(rows, gap_s: float = 0.5) -> List[dict]:
    """rows: dict with arrays `t` and `other_model` (already window-filtered).
    Returns events {other_model, t_start, t_end, n_rows}, sorted by model then time."""
    if not rows or 't' not in rows or len(rows['t']) == 0:
        return []
    t = np.asarray(rows['t'], float)
    mdl = [_s(m) for m in rows['other_model']]
    groups: Dict[str, List[float]] = {}
    for tt, m in zip(t, mdl):
        groups.setdefault(m, []).append(float(tt))
    events = []
    for m in sorted(groups):
        ts = sorted(groups[m])
        cur = [ts[0], ts[0], 1]
        for v in ts[1:]:
            if v - cur[1] > gap_s:
                events.append({'other_model': m, 't_start': cur[0], 't_end': cur[1], 'n_rows': cur[2]})
                cur = [v, v, 1]
            else:
                cur[1] = v
                cur[2] += 1
        events.append({'other_model': m, 't_start': cur[0], 't_end': cur[1], 'n_rows': cur[2]})
    return events


# ---------------------------------------------------------------- dynamic obstacles
def _dyn_series(traj_t, dyn, cfg):
    """{name: (x[N], y[N], yaw[N], size)} matched to trajectory times (nearest row)."""
    out = {}
    if not dyn or 'name' not in dyn or len(dyn['name']) == 0:
        return out
    names = np.array([_s(n) for n in dyn['name']])
    dcfg = cfg.get('dynamic_obstacles', {}) or {}
    for n in sorted(set(names)):
        m = names == n
        t = np.asarray(dyn['t'], float)[m]
        o = np.argsort(t)
        t = t[o]
        if len(t) == 0:
            continue
        idx = np.clip(np.searchsorted(t, traj_t), 1, max(len(t) - 1, 1)) if len(t) > 1 else np.zeros(len(traj_t), int)
        if len(t) > 1:
            left = idx - 1
            idx = np.where(np.abs(traj_t - t[left]) <= np.abs(traj_t - t[idx]), left, idx)
        x = np.asarray(dyn['x'], float)[m][o][idx]
        y = np.asarray(dyn['y'], float)[m][o][idx]
        yaw = np.asarray(dyn['yaw'], float)[m][o][idx] if 'yaw' in dyn else np.zeros(len(idx))
        size = (dcfg.get(n) or {}).get('size', [0.4, 0.4])
        out[n] = (x, y, yaw, (float(size[0]), float(size[1])))
    return out


def _perimeter(size, step=0.02):
    sx, sy = size[0] / 2.0, size[1] / 2.0
    nx = max(int(math.ceil(size[0] / step)), 1)
    ny = max(int(math.ceil(size[1] / step)), 1)
    xs = np.linspace(-sx, sx, nx + 1)
    ys = np.linspace(-sy, sy, ny + 1)
    pts = ([(x, -sy) for x in xs] + [(x, sy) for x in xs] +
           [(-sx, y) for y in ys] + [(sx, y) for y in ys])
    return np.array(pts)


def _rect_dist(px, py, gx, gy, gyaw):
    """Distance from robot rectangle at (gx,gy,gyaw) to points (world), floor 0."""
    c, s = math.cos(gyaw), math.sin(gyaw)
    dx, dy = px - gx, py - gy
    rx = c * dx + s * dy
    ry = -s * dx + c * dy
    return np.hypot(np.maximum(np.abs(rx) - HALF_L, 0.0), np.maximum(np.abs(ry) - HALF_W, 0.0))


def _distances(traj, gt: GtGrid, dyn, cfg=None, radius=QUERY_R):
    """Per-obstacle distance series {name: float[N]} (inf when out of range)."""
    cfg = cfg or {}
    gx = np.asarray(traj['gt_x'], float)
    gy = np.asarray(traj['gt_y'], float)
    gyaw = np.asarray(traj['gt_yaw'], float)
    n = len(gx)
    res = {}
    names = list(gt.obs_names)
    jj, ii = np.nonzero(gt.boundary)
    if len(jj):
        cx = gt.x0 + (ii + 0.5) * gt.res
        cy = gt.y0 + (jj + 0.5) * gt.res
        lab = np.asarray(gt.obs_id)[jj, ii].astype(int)
        tree = cKDTree(np.column_stack([cx, cy]))
        for k in sorted(set(lab.tolist())):
            nm = names[k] if 0 <= k < len(names) else '_unknown'
            res.setdefault(nm, np.full(n, np.inf))
        for r in range(n):
            if not (np.isfinite(gx[r]) and np.isfinite(gy[r])):
                continue
            ids = tree.query_ball_point([gx[r], gy[r]], radius)
            if not ids:
                continue
            ids = np.asarray(ids)
            yaw = gyaw[r] if np.isfinite(gyaw[r]) else 0.0
            d = _rect_dist(cx[ids], cy[ids], gx[r], gy[r], yaw) - gt.res / 2.0
            d = np.maximum(d, 0.0)
            for k in np.unique(lab[ids]):
                nm = names[k] if 0 <= k < len(names) else '_unknown'
                m = lab[ids] == k
                res[nm][r] = min(res[nm][r], d[m].min())
    for nm, (x, y, yaw, size) in _dyn_series(np.asarray(traj['t'], float), dyn, cfg).items():
        per = _perimeter(size)
        arr = np.full(n, np.inf)
        for r in range(n):
            if not (np.isfinite(gx[r]) and np.isfinite(x[r])):
                continue
            c, s = math.cos(yaw[r]), math.sin(yaw[r])
            wx = x[r] + c * per[:, 0] - s * per[:, 1]
            wy = y[r] + s * per[:, 0] + c * per[:, 1]
            arr[r] = _rect_dist(wx, wy, gx[r], gy[r], gyaw[r] if np.isfinite(gyaw[r]) else 0.0).min()
        res[nm] = arr
    return res


def _get_shapes(gt: GtGrid, cfg):
    """Exact obstacle shapes {model: [shape]} from gt.shapes, else the world's SDF
    (worlds.yaml `sdf_file`); None when unavailable (grid fallback)."""
    sh = getattr(gt, 'shapes', None)
    if sh:
        return sh
    try:
        from ..compute_metrics import resolve_sdf
        if cfg.get('sdf_file'):
            return geometry.load_obstacles(resolve_sdf(cfg['sdf_file']))
    except Exception:
        return None
    return None


def _distances_exact(traj, shapes, dyn, cfg):
    """Per-obstacle SIGNED exact distance series (negative = overlap)."""
    gx, gy, gyaw = (np.asarray(traj[k], float) for k in ('gt_x', 'gt_y', 'gt_yaw'))
    res = geometry.trajectory_distances(gx, gy, gyaw, shapes)
    yawr = np.where(np.isfinite(gyaw), gyaw, 0.0)
    for nm, (x, y, yaw, size) in _dyn_series(np.asarray(traj['t'], float), dyn, cfg).items():
        res[nm] = geometry.rect_rect_distance(gx, gy, yawr, x, y, yaw, size[0] / 2, size[1] / 2)
    return res


def clearance_series(traj, gt: GtGrid, dyn=None, cfg=None) -> np.ndarray:
    """Per-row min over obstacles of d_k, capped at 1.0 m (spec 06 section 6.5)."""
    n = len(traj['gt_x'])
    d = _distances(traj, gt, dyn, cfg)
    out = np.full(n, CAP)
    for arr in d.values():
        out = np.minimum(out, arr)
    bad = ~(np.isfinite(np.asarray(traj['gt_x'], float)) & np.isfinite(np.asarray(traj['gt_y'], float)))
    out[bad] = np.nan
    return out


def _encounters_from(t, dist: Dict[str, np.ndarray], d_enc, merge_s, min_s):
    out = {}
    for nm in sorted(dist):
        below = dist[nm] < d_enc
        segs = []
        r = 0
        n = len(t)
        while r < n:
            if below[r]:
                s = r
                while r + 1 < n and below[r + 1]:
                    r += 1
                segs.append([float(t[s]), float(t[r])])
            r += 1
        merged = []
        for sg in segs:
            if merged and sg[0] - merged[-1][1] < merge_s:
                merged[-1][1] = sg[1]
            else:
                merged.append(sg)
        out[nm] = [(a, b) for a, b in merged if b - a >= min_s]
    return out


def encounters(traj, gt: GtGrid, dyn=None, d_enc=0.5, merge_s=2.0, min_s=0.5, cfg=None):
    """{obstacle_name: [(t0, t1)]} (spec 06 section 6.6)."""
    return _encounters_from(np.asarray(traj['t'], float), _distances(traj, gt, dyn, cfg),
                            d_enc, merge_s, min_s)


# ---------------------------------------------------------------- geometry fallback
def _rect_overlap(c1, h1, yaw1, c2, h2, yaw2):
    """Separating-axis test for two oriented rectangles (half extents h)."""
    def axes(y):
        return [(math.cos(y), math.sin(y)), (-math.sin(y), math.cos(y))]

    def corners(c, h, y):
        co, si = math.cos(y), math.sin(y)
        return [(c[0] + co * sx * h[0] - si * sy * h[1], c[1] + si * sx * h[0] + co * sy * h[1])
                for sx in (-1, 1) for sy in (-1, 1)]
    ca, cb = corners(c1, h1, yaw1), corners(c2, h2, yaw2)
    for ax in axes(yaw1) + axes(yaw2):
        pa = [p[0] * ax[0] + p[1] * ax[1] for p in ca]
        pb = [p[0] * ax[0] + p[1] * ax[1] for p in cb]
        if max(pa) < min(pb) or max(pb) < min(pa):
            return False
    return True


def _geometry_rows_exact(traj, shapes, dyn, cfg):
    ts, models = [], []
    tt = np.asarray(traj['t'], float)
    for nm, d in sorted(_distances_exact(traj, shapes, dyn, cfg).items()):
        for r in np.nonzero(d <= 0.0)[0]:
            ts.append(float(tt[r]))
            models.append(nm)
    return {'t': np.array(ts), 'other_model': models}


def _geometry_rows(traj, gt: GtGrid, dyn, cfg):
    """Rows {t, other_model} where the robot rectangle touches an obstacle."""
    ts, models = [], []
    gx, gy, gyaw, tt = (np.asarray(traj[k], float) for k in ('gt_x', 'gt_y', 'gt_yaw', 't'))
    names = list(gt.obs_names)
    dser = _dyn_series(tt, dyn, cfg)
    # clearance <= 0 (centre-in-rectangle test can miss a touching/overlapping cell)
    touching = {nm: np.asarray(a) <= 0.0 for nm, a in _distances(traj, gt, dyn, cfg).items()}
    R = 0.2
    rr = int(math.ceil(R / gt.res)) + 1
    h, w = gt.occ.shape
    for r in range(len(tt)):
        if not (np.isfinite(gx[r]) and np.isfinite(gy[r])):
            continue
        yaw = gyaw[r] if np.isfinite(gyaw[r]) else 0.0
        ci = int(math.floor((gx[r] - gt.x0) / gt.res))
        cj = int(math.floor((gy[r] - gt.y0) / gt.res))
        i0, i1, j0, j1 = max(ci - rr, 0), min(ci + rr + 1, w), max(cj - rr, 0), min(cj + rr + 1, h)
        hit = set()
        if i0 < i1 and j0 < j1:
            sj, si = np.nonzero(gt.occ[j0:j1, i0:i1])
            if len(sj):
                px = gt.x0 + (si + i0 + 0.5) * gt.res
                py = gt.y0 + (sj + j0 + 0.5) * gt.res
                c, s = math.cos(yaw), math.sin(yaw)
                rx = c * (px - gx[r]) + s * (py - gy[r])
                ry = -s * (px - gx[r]) + c * (py - gy[r])
                inside = (np.abs(rx) <= HALF_L) & (np.abs(ry) <= HALF_W)
                for k in np.unique(np.asarray(gt.obs_id)[sj[inside] + j0, si[inside] + i0]):
                    hit.add(names[k] if 0 <= k < len(names) else '_unknown')
        for nm, (x, y, dyaw, size) in dser.items():
            if _rect_overlap((gx[r], gy[r]), (HALF_L, HALF_W), yaw,
                             (x[r], y[r]), (size[0] / 2, size[1] / 2), dyaw[r]):
                hit.add(nm)
        for nm, mk in touching.items():
            if mk[r]:
                hit.add(nm)
        for nm in sorted(hit):
            ts.append(float(tt[r]))
            models.append(nm)
    return {'t': np.array(ts), 'other_model': models}


# ---------------------------------------------------------------- main
def compute_safety_metrics(run: Run, gt: GtGrid, worlds_cfg: dict) -> dict:
    cfg = _cfg(worlds_cfg, gt)
    snap = (run.meta or {}).get('config_snapshot') or {}
    gap_s = float(snap.get('collision_gap_s', 0.5))
    d_enc = float(snap.get('d_enc_m', 0.5))
    wall_re = re.compile(cfg.get('wall_models', DEFAULT_WALLS))
    t0 = float(run.episode_start_t)
    t1 = float(run.episode_end_t)
    if t1 <= t0:
        t1 = float('inf')
    notes: List[str] = []
    out: Dict[str, object] = {}

    # trajectory in window
    tr = run.trajectory
    traj = None
    if tr and 't' in tr and len(tr['t']):
        t = np.asarray(tr['t'], float)
        ok = (t >= t0) & (t <= t1) & np.isfinite(tr['gt_x']) & np.isfinite(tr['gt_y'])
        traj = {k: np.asarray(tr[k], float)[ok] for k in ('t', 'gt_x', 'gt_y', 'gt_yaw')}
        if len(traj['t']) == 0:
            traj = None

    # contact events
    contact_alive = True
    if run.events and 'event' in run.events:
        for k in range(len(run.events['event'])):
            if _s(run.events['event'][k]) == 'contact_topic_alive' and _f(run.events['detail'][k]) == 0:
                contact_alive = False
    raw = run.collisions_raw
    use_contact = raw is not None and contact_alive
    contact_rows = None
    if raw is not None and 't' in raw and len(raw['t']):
        tt = np.asarray(raw['t'], float)
        m = (tt >= t0) & (tt <= t1)
        robot = str((run.meta or {}).get('robot_model') or 'vacuum_robot')
        keep = [i for i in np.nonzero(m)[0]
                if not (_s(raw['other_model'][i]) == 'vacuum_robot'
                        or _s(raw['other_model'][i]).startswith(robot))]
        contact_rows = {'t': tt[keep], 'other_model': [raw['other_model'][i] for i in keep]}
    elif raw is not None:
        contact_rows = {'t': np.array([]), 'other_model': []}

    geom_events = None
    if traj is not None:
        shapes = _get_shapes(gt, cfg)
        grid_events = collision_events(_geometry_rows(traj, gt, run.dyn_obstacles, cfg), gap_s)
        if shapes:
            geom_events = collision_events(
                _geometry_rows_exact(traj, shapes, run.dyn_obstacles, cfg), gap_s)
            out['geometry_source'] = 'exact'
            out['geometric_collisions_grid'] = len(grid_events)
        else:
            geom_events = grid_events
            out['geometry_source'] = 'grid'
            notes.append('no SDF shapes: grid-based geometry (approximate)')
    if use_contact:
        events = collision_events(contact_rows, gap_s)
        out['collision_source'] = 'contact'
    else:
        events = geom_events if geom_events is not None else []
        out['collision_source'] = 'geometry'
        if geom_events is None:
            notes.append('no trajectory: geometric collision fallback unavailable')
    out['n_collisions'] = len(events)
    out['n_collision_obstacles'] = len({e['other_model'] for e in events})
    out['collision_contact_time_s'] = float(sum(e['t_end'] - e['t_start'] for e in events))
    out['collision_first_t_ep'] = (min(e['t_start'] for e in events) - t0) if events and np.isfinite(t0) else None
    out['n_collisions_geom'] = len(geom_events) if geom_events is not None else None
    out['geometric_collisions'] = out['n_collisions_geom']   # cross-check when contact is source
    if geom_events is not None and abs(len(events) - len(geom_events)) > 2:
        notes.append('contact vs geometry disagree: contact=%d geom=%d' % (len(events), len(geom_events)))

    # clearance / encounters
    keys = ['min_clearance_m', 'mean_clearance_m', 'clearance_p05_m', 'time_below_020m_s', 'time_below_010m_s']
    if traj is None:
        for k in keys:
            out[k] = None
        for k in ('avoidance_pct', 'avoidance_pct_all'):
            out[k] = None
        for k in ('n_encounters', 'n_encounters_free', 'n_encounters_all', 'n_encounters_free_all'):
            out[k] = 0
        notes.append('no GT trajectory rows in episode window')
    else:
        grid_dist = _distances(traj, gt, run.dyn_obstacles, cfg)
        if shapes:
            sdist = _distances_exact(traj, shapes, run.dyn_obstacles, cfg)
            dist = {k: np.maximum(v, 0.0) for k, v in sdist.items()}
            pen = np.min(np.stack(list(sdist.values())), axis=0) if sdist else np.zeros(1)
            out['max_penetration_m'] = float(max(0.0, -pen.min()))
            gclr = np.full(len(traj['t']), CAP)
            for arr in grid_dist.values():
                gclr = np.minimum(gclr, arr)
            out['min_clearance_grid_m'] = float(gclr.min())
            genc = _encounters_from(traj['t'], grid_dist, d_enc, 2.0, 0.5)
            out['n_encounters_grid'] = sum(len(v) for k, v in genc.items() if not wall_re.search(k))
        else:
            dist = grid_dist
        clr = np.full(len(traj['t']), CAP)
        for arr in dist.values():
            clr = np.minimum(clr, arr)
        out['min_clearance_m'] = float(clr.min())
        out['mean_clearance_m'] = float(clr.mean())
        out['clearance_p05_m'] = float(np.percentile(clr, 5))
        rdt = _row_dt(traj['t'])
        out['time_below_020m_s'] = float(np.sum(rdt[clr < 0.20]))
        out['time_below_010m_s'] = float(np.sum(rdt[clr < 0.10]))
        if use_contact and out['min_clearance_m'] <= 0.0 and not events:
            notes.append('min_clearance <= 0 but no contact events: check contact sensor')
        enc = _encounters_from(traj['t'], dist, d_enc, 2.0, 0.5)
        n_all = n_free_all = n_ex = n_free_ex = 0
        for nm, lst in enc.items():
            is_wall = bool(wall_re.search(nm))
            for (a, b) in lst:
                hit = any(e['other_model'] == nm and e['t_start'] <= b + 0.5 and e['t_end'] >= a
                          for e in events)
                n_all += 1
                n_free_all += (not hit)
                if not is_wall:
                    n_ex += 1
                    n_free_ex += (not hit)
        out['n_encounters'] = n_ex
        out['n_encounters_free'] = n_free_ex
        out['n_encounters_all'] = n_all
        out['n_encounters_free_all'] = n_free_all
        out['avoidance_pct'] = 100.0 * n_free_ex / n_ex if n_ex else None
        out['avoidance_pct_all'] = 100.0 * n_free_all / n_all if n_all else None
        if n_ex == 0:
            notes.append('no encounters')

    # trial keys
    nav = compute_navigation_metrics(run, gt)
    gt_pct = nav.get('nav_success_gt_pct')
    reached = None if gt_pct is None else int(gt_pct >= 100.0)
    out['trial_goal_reached'] = reached
    out['trial_collisions'] = out['n_collisions']
    end_reason = (run.meta or {}).get('end_reason')
    if reached is None or end_reason is None:
        out['trial_success'] = None
    else:
        out['trial_success'] = int(reached == 1 and out['n_collisions'] == 0 and end_reason == 'goals_done')
    out['trial_time_s'] = (t1 - t0) if np.isfinite(t1) and np.isfinite(t0) and t1 > t0 else None
    out['notes'] = notes
    return out
