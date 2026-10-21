"""Navigation metrics (docs/specs/05). Pure numpy/scipy/stdlib, no ROS."""

import heapq
import math
from typing import Dict, List, Optional

import numpy as np

from .common import GtGrid, Run, se2_compose

SQRT2 = math.sqrt(2.0)
FAIL_RESULTS = ('nav_aborted', 'timeout', 'oscillation', 'rejected')
WHEEL_BASE = 0.268
GOAL_TOL = 0.30
MIN_SHORTEST = 0.5
SNAP_RADIUS = 0.30


# ---------------------------------------------------------------- helpers
def _s(v) -> str:
    if v is None:
        return ''
    if isinstance(v, float) and math.isnan(v):
        return ''
    return str(v)


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float('nan')


def _stat(vals, fn):
    return float(fn(vals)) if len(vals) else None


def _window(run: Run):
    t0 = float(run.episode_start_t)
    t1 = float(run.episode_end_t)
    if t1 <= t0:
        t1 = float('inf')
    return t0, t1


def _t_world_map(run: Run):
    m = run.meta or {}
    t = m.get('t_world_map')
    if t is not None and len(t) == 3:
        return tuple(float(v) for v in t)
    if 'spawn_x' in m:
        return (float(m['spawn_x']), float(m.get('spawn_y', 0.0)),
                float(m.get('spawn_yaw', 0.0)))
    return (0.0, 0.0, 0.0)


def _gt_traj(run: Run, t0: float, t1: float):
    """GT rows inside the window with valid GT. Returns dict of arrays or None."""
    tr = run.trajectory
    if not tr or 't' not in tr or len(tr['t']) == 0:
        return None
    t = np.asarray(tr['t'], dtype=float)
    ok = (t >= t0) & (t <= t1) & np.isfinite(tr['gt_x']) & np.isfinite(tr['gt_y'])
    out = {'t': t[ok], 'x': np.asarray(tr['gt_x'], float)[ok],
           'y': np.asarray(tr['gt_y'], float)[ok]}
    for k, c in (('vx', 'gt_vx'), ('wz', 'gt_wz'), ('ox', 'odom_x'), ('oy', 'odom_y')):
        out[k] = np.asarray(tr[c], float)[ok] if c in tr else np.full(ok.sum(), np.nan)
    return out


def _gt_all(run: Run):
    tr = run.trajectory
    if not tr or 't' not in tr or len(tr['t']) == 0:
        return None
    t = np.asarray(tr['t'], float)
    ok = np.isfinite(tr['gt_x']) & np.isfinite(tr['gt_y'])
    if not ok.any():
        return None
    return t[ok], np.asarray(tr['gt_x'], float)[ok], np.asarray(tr['gt_y'], float)[ok]


def _gt_at(gtall, t):
    tt, xx, yy = gtall
    return float(np.interp(t, tt, xx)), float(np.interp(t, tt, yy))


# ---------------------------------------------------------------- shortest path
def _snap(gt: GtGrid, xy):
    """Nearest navigable cell (i, j) within SNAP_RADIUS of the point, else None."""
    h, w = gt.navigable.shape
    ci = int(math.floor((xy[0] - gt.x0) / gt.res))
    cj = int(math.floor((xy[1] - gt.y0) / gt.res))
    r = int(math.ceil(SNAP_RADIUS / gt.res)) + 1
    i0, i1 = max(ci - r, 0), min(ci + r + 1, w)
    j0, j1 = max(cj - r, 0), min(cj + r + 1, h)
    if i0 >= i1 or j0 >= j1:
        return None
    sub = gt.navigable[j0:j1, i0:i1]
    jj, ii = np.nonzero(sub)
    if len(jj) == 0:
        return None
    cx = gt.x0 + (ii + i0 + 0.5) * gt.res
    cy = gt.y0 + (jj + j0 + 0.5) * gt.res
    d = np.hypot(cx - xy[0], cy - xy[1])
    k = int(np.argmin(d))
    if d[k] > SNAP_RADIUS + 1e-9:
        return None
    return int(ii[k] + i0), int(jj[k] + j0)


def _astar(nav: np.ndarray, s, g):
    """8-connected A* on bool grid; cells are (i, j). Returns list of cells or None."""
    h, w = nav.shape
    if s == g:
        return [s]
    nbrs = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
            (1, 1, SQRT2), (1, -1, SQRT2), (-1, 1, SQRT2), (-1, -1, SQRT2)]

    def hh(c):
        return math.hypot(c[0] - g[0], c[1] - g[1])

    best = {s: 0.0}
    parent = {}
    heap = [(hh(s), 0.0, s)]
    closed = set()
    while heap:
        _, cost, c = heapq.heappop(heap)
        if c in closed:
            continue
        if c == g:
            path = [c]
            while c in parent:
                c = parent[c]
                path.append(c)
            return path[::-1]
        closed.add(c)
        ci, cj = c
        for di, dj, sc in nbrs:
            ni, nj = ci + di, cj + dj
            if ni < 0 or nj < 0 or ni >= w or nj >= h or not nav[nj, ni]:
                continue
            if di != 0 and dj != 0 and not nav[cj, ni] and not nav[nj, ci]:
                continue  # corner cut between two blocked cells
            n = (ni, nj)
            nc = cost + sc
            if nc < best.get(n, float('inf')):
                best[n] = nc
                parent[n] = c
                heapq.heappush(heap, (nc + hh(n), nc, n))
    return None


def _bresenham_visible(nav: np.ndarray, a, b) -> bool:
    x0, y0 = a
    x1, y1 = b
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    while True:
        if not nav[y0, x0]:
            return False
        if x0 == x1 and y0 == y1:
            return True
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy


def _string_pull(nav, path):
    if len(path) <= 2:
        return list(path)
    out = [path[0]]
    i = 0
    n = len(path)
    while i < n - 1:
        j = n - 1
        while j > i + 1 and not _bresenham_visible(nav, path[i], path[j]):
            j -= 1
        out.append(path[j])
        i = j
    return out


def shortest_path_length(gt: GtGrid, start_xy, goal_xy) -> Optional[float]:
    """Spec 05 section 5.3. None if a point has no navigable cell within 0.30 m or
    no path exists."""
    s = _snap(gt, start_xy)
    g = _snap(gt, goal_xy)
    if s is None or g is None:
        return None
    path = _astar(gt.navigable, s, g)
    if path is None:
        return None
    wp = _string_pull(gt.navigable, path)
    pts = [(float(start_xy[0]), float(start_xy[1]))]
    for (i, j) in wp[1:-1]:
        pts.append((gt.x0 + (i + 0.5) * gt.res, gt.y0 + (j + 0.5) * gt.res))
    pts.append((float(goal_xy[0]), float(goal_xy[1])))
    return float(sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts[:-1], pts[1:])))


# ---------------------------------------------------------------- goal records
def goal_records(run: Run, t0: float, t1: float) -> List[dict]:
    ge = run.goal_events
    if not ge or 'src' not in ge:
        return []
    method = (run.meta or {}).get('method')
    srcs = {'frontier': ('explore',), 'scripted_goals': ('scripted',)}.get(
        method, ('explore', 'scripted'))
    twm = _t_world_map(run)
    started, ended, order = {}, {}, []
    n = len(ge['src'])
    for k in range(n):
        if _s(ge['src'][k]) not in srcs:
            continue
        seq = _f(ge['goal_seq'][k])
        if math.isnan(seq):
            continue
        key = (_s(ge['src'][k]), int(seq))
        ev = _s(ge['event'][k])
        if ev == 'started' and key not in started:
            started[key] = k
            order.append(key)
        elif ev == 'ended' and key not in ended:
            ended[key] = k
    recs = []
    for key in order:
        k = started[key]
        ts = _f(ge['t'][k])
        if not (t0 <= ts <= t1):
            continue
        x, y = _f(ge['x'][k]), _f(ge['y'][k])
        wx, wy, _ = se2_compose(twm, (x, y, 0.0))
        rec = {'seq': key[1], 't_start': ts, 'x': x, 'y': y, 'goal_w': (wx, wy),
               't_end': None, 'result': 'unfinished'}
        if key in ended:
            ke = ended[key]
            te = _f(ge['t'][ke])
            if te <= t1:
                rec['t_end'] = te
                rec['result'] = _s(ge['result'][ke]) or 'unfinished'
        recs.append(rec)
    return recs


def _nav2_accepted(run: Run, t_start: float):
    ge = run.goal_events
    best = None
    for k in range(len(ge['src'])):
        if _s(ge['src'][k]) == 'nav2_status' and _s(ge['event'][k]) in ('accepted', 'executing'):
            ta = _f(ge['t'][k])
            if ta >= t_start and ta - t_start <= 2.0:
                if best is None or ta < best[0]:
                    best = (ta, _s(ge['uuid'][k]) if 'uuid' in ge else '')
    return best


# ---------------------------------------------------------------- main
def compute_navigation_metrics(run: Run, gt: GtGrid) -> dict:
    t0, t1 = _window(run)
    notes: List[str] = []
    out: Dict[str, object] = {}
    recs = goal_records(run, t0, t1)
    gtall = _gt_all(run)

    succ = [r for r in recs if r['result'] == 'succeeded']
    fails = [r for r in recs if r['result'] in FAIL_RESULTS]
    canc = [r for r in recs if r['result'] == 'canceled_by_manager']
    unf = [r for r in recs if r['result'] == 'unfinished']
    other = [r for r in recs if r['result'] not in
             ('succeeded', 'canceled_by_manager', 'unfinished') + FAIL_RESULTS]
    if other:
        notes.append('goals with unknown result ignored: %d' % len(other))
    total = len(succ) + len(fails)
    out['nav_goals_total'] = total
    out['nav_goals_succeeded'] = len(succ)
    out['nav_goals_failed'] = len(fails)
    out['nav_goals_canceled'] = len(canc)
    out['nav_goals_unfinished'] = len(unf)
    out['nav_success_pct'] = 100.0 * len(succ) / total if total else None
    out['nav_fail_aborted'] = sum(r['result'] == 'nav_aborted' for r in fails)
    out['nav_fail_timeout'] = sum(r['result'] == 'timeout' for r in fails)
    out['nav_fail_oscillation'] = sum(r['result'] == 'oscillation' for r in fails)
    out['nav_fail_rejected'] = sum(r['result'] == 'rejected' for r in fails)

    # GT-based success
    if total and gtall is not None:
        reached = 0
        for r in succ + fails:
            if r['t_end'] is None:
                continue
            px, py = _gt_at(gtall, r['t_end'])
            if math.hypot(px - r['goal_w'][0], py - r['goal_w'][1]) <= GOAL_TOL:
                reached += 1
        out['nav_success_gt_pct'] = 100.0 * reached / total
    else:
        out['nav_success_gt_pct'] = None
        if total:
            notes.append('nav_success_gt_pct: no GT trajectory')
    gtimes = [r['t_end'] - r['t_start'] for r in succ]
    out['goal_time_mean_s'] = _stat(gtimes, np.mean)
    out['goal_time_median_s'] = _stat(gtimes, np.median)

    # path length ratio
    ratios, plan_ratios, skipped = [], [], 0
    plans = run.plans
    for r in succ:
        if gtall is None:
            break
        sp = _gt_at(gtall, r['t_start'])
        shortest = shortest_path_length(gt, sp, r['goal_w'])
        if shortest is None:
            skipped += 1
            continue
        if shortest < MIN_SHORTEST:
            continue
        traj = _gt_traj(run, r['t_start'], r['t_end'])
        if traj is None or len(traj['t']) < 2:
            continue
        actual = float(np.sum(np.hypot(np.diff(traj['x']), np.diff(traj['y']))))
        ratios.append(actual / shortest)
        if plans and 't' in plans and 'length_m' in plans:
            acc = _nav2_accepted(run, r['t_start'])
            if acc is not None:
                pt = np.asarray(plans['t'], float)
                idx = np.nonzero(pt >= acc[0])[0]
                if len(idx):
                    plan_ratios.append(float(plans['length_m'][idx[0]]) / shortest)
    out['path_length_ratio_mean'] = _stat(ratios, np.mean)
    out['path_length_ratio_median'] = _stat(ratios, np.median)
    out['path_length_ratio_p90'] = _stat(ratios, lambda v: np.percentile(v, 90))
    out['path_length_ratio_n'] = len(ratios)
    out['ratio_skipped'] = skipped
    out['plan_length_ratio_mean'] = _stat(plan_ratios, np.mean)

    # planning latency / replans
    lat, repl = [], []
    if plans and 't' in plans and run.goal_events:
        pt = np.asarray(plans['t'], float)
        for r in recs:
            acc = _nav2_accepted(run, r['t_start'])
            if acc is None:
                continue
            after = pt[pt >= acc[0]]
            if len(after):
                lat.append(1000.0 * (after[0] - acc[0]))
            end = r['t_end'] if r['t_end'] is not None else t1
            repl.append(max(int(np.sum((pt >= acc[0]) & (pt <= end))) - 1, 0))
    out['plan_latency_ms_mean'] = _stat(lat, np.mean)
    out['plan_latency_ms_p95'] = _stat(lat, lambda v: np.percentile(v, 95))
    out['replans_per_goal_mean'] = _stat(repl, np.mean)

    # recoveries
    fb = run.feedback
    n_rec = None
    if fb and 'uuid' in fb and len(fb['uuid']):
        best: Dict[str, float] = {}
        ft = np.asarray(fb['t'], float) if 't' in fb else np.full(len(fb['uuid']), t0 if np.isfinite(t0) else 0.0)
        for k in range(len(fb['uuid'])):
            if not (t0 <= ft[k] <= t1):
                continue
            v = _f(fb['number_of_recoveries'][k])
            if math.isnan(v):
                continue
            u = _s(fb['uuid'][k])
            best[u] = max(best.get(u, 0.0), v)
        n_rec = int(sum(best.values()))
    elif fb is not None:
        n_rec = 0
    out['n_recoveries'] = n_rec
    out['recoveries_per_goal_mean'] = (n_rec / total) if (n_rec is not None and total) else None
    ge = run.goal_events
    for name in ('spin', 'backup', 'wait'):
        c = 0
        seen = set()
        if ge and 'src' in ge:
            for k in range(len(ge['src'])):
                # the recorder may miss the short-lived 'accepted' status; count a behaviour
                # once, by uuid, when either 'accepted' or 'executing' is seen
                if (_s(ge['src'][k]) == 'behavior_' + name
                        and _s(ge['event'][k]) in ('accepted', 'executing')
                        and t0 <= _f(ge['t'][k]) <= t1):
                    u = _s(ge['uuid'][k]) if 'uuid' in ge else ''
                    if u and u in seen:
                        continue
                    if u:
                        seen.add(u)
                    c += 1
        out['recov_%s_n' % name] = c
    out['n_stuck_goals'] = out['nav_fail_timeout'] + out['nav_fail_oscillation']

    # distance / energy / smoothness
    tj = _gt_traj(run, t0, t1)
    keys_null = ['distance_gt_m', 'distance_odom_m', 'distance_ratio_odom_gt',
                 'energy_proxy_m2ps', 'mean_speed_mps', 'time_stationary_s',
                 'time_rotating_inplace_s', 'smooth_curvature_rms_1pm',
                 'smooth_curvature_var', 'smooth_jerk_rms_mps3']
    if tj is None or len(tj['t']) < 2:
        for k in keys_null:
            out[k] = None
        notes.append('no GT trajectory rows in episode window')
        out['notes'] = notes
        return out
    t, x, y, vx, wz = tj['t'], tj['x'], tj['y'], tj['vx'], tj['wz']
    dgt = float(np.sum(np.hypot(np.diff(x), np.diff(y))))
    out['distance_gt_m'] = dgt
    ook = np.isfinite(tj['ox']) & np.isfinite(tj['oy'])
    if ook.sum() >= 2:
        dod = float(np.sum(np.hypot(np.diff(tj['ox'][ook]), np.diff(tj['oy'][ook]))))
        out['distance_odom_m'] = dod
        out['distance_ratio_odom_gt'] = dod / dgt if dgt > 0 else None
    else:
        out['distance_odom_m'] = None
        out['distance_ratio_odom_gt'] = None
    vok = np.isfinite(vx) & np.isfinite(wz)
    if vok.sum() == 0:
        for k in keys_null[3:]:
            out[k] = None
        out['notes'] = notes
        return out
    dt = np.diff(t)
    vL = vx - wz * WHEEL_BASE / 2.0
    vR = vx + wz * WHEEL_BASE / 2.0
    e = (vL[:-1] ** 2 + vR[:-1] ** 2) * dt
    out['energy_proxy_m2ps'] = float(np.nansum(e))
    dur = t[-1] - t[0]
    out['mean_speed_mps'] = dgt / dur if dur > 0 else None
    out['time_stationary_s'] = float(np.sum(vok & (np.abs(vx) < 0.02) & (np.abs(wz) < 0.05)) * 0.1)
    out['time_rotating_inplace_s'] = float(np.sum(vok & (np.abs(vx) < 0.05) & (np.abs(wz) >= 0.05)) * 0.1)

    mv = vok & (np.abs(vx) >= 0.05)
    if mv.any():
        kap = wz[mv] / vx[mv]
        out['smooth_curvature_rms_1pm'] = float(np.sqrt(np.mean(kap ** 2)))
        out['smooth_curvature_var'] = float(np.var(kap))
    else:
        out['smooth_curvature_rms_1pm'] = None
        out['smooth_curvature_var'] = None
    if len(t) >= 3:
        with np.errstate(divide='ignore', invalid='ignore'):
            a = np.diff(vx) / dt
            j = np.diff(a) / dt[:-1]
        good = mv[:-2] & mv[1:-1] & mv[2:] & np.isfinite(j)
        out['smooth_jerk_rms_mps3'] = float(np.sqrt(np.mean(j[good] ** 2))) if good.any() else None
    else:
        out['smooth_jerk_rms_mps3'] = None
    out['notes'] = notes
    return out


# ---------------------------------------------------------------- goal lists
def _graph_dist(nav: np.ndarray, start, res):
    """Path distance (m) from start cell (i, j) to every cell, inf if unreachable."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra
    h, w = nav.shape
    idx = np.arange(h * w).reshape(h, w)
    rows, cols, wts = [], [], []
    for di, dj, c in ((1, 0, 1.0), (0, 1, 1.0), (1, 1, SQRT2), (1, -1, SQRT2)):
        j0, j1 = max(0, -dj), h - max(0, dj)
        i0, i1 = 0, w - di
        a = (slice(j0, j1), slice(i0, i1))
        b = (slice(j0 + dj, j1 + dj), slice(i0 + di, i1 + di))
        ok = nav[a] & nav[b]
        if di and dj:
            ok &= nav[(slice(j0, j1), slice(i0 + di, i1 + di))] | nav[(slice(j0 + dj, j1 + dj), slice(i0, i1))]
        rows.append(idx[a][ok])
        cols.append(idx[b][ok])
        wts.append(np.full(ok.sum(), c * res))
    r, c_, v = np.concatenate(rows), np.concatenate(cols), np.concatenate(wts)
    g = coo_matrix((v, (r, c_)), shape=(h * w, h * w)).tocsr()
    d = dijkstra(g, directed=False, indices=start[1] * w + start[0])
    return d.reshape(h, w)


def generate_goal_lists(gt: GtGrid, rng_seed: int, spawn_xy=None, fixed=None,
                        n_random: int = 20, n_near_wall: int = 10, n_long: int = 6,
                        min_euclid: float = 1.5, min_path: float = 1.5,
                        max_tries: int = 400) -> Dict[str, List[dict]]:
    """Spec 05 section 5.8. `rng_seed` seeds numpy default_rng directly (the caller
    passes seed + 2000). Returns {list_name: [{x, y, yaw}]}; 'fixed' only if given."""
    base = gt.a_reach if gt.a_reach is not None else gt.navigable
    d = np.asarray(gt.dist_to_obstacle, dtype=float)
    res = gt.res

    def centre(i, j):
        return gt.x0 + (i + 0.5) * res, gt.y0 + (j + 0.5) * res

    def sequential(mask, n, rng):
        jj, ii = np.nonzero(mask)
        cx = gt.x0 + (ii + 0.5) * res
        cy = gt.y0 + (jj + 0.5) * res
        prev = (float(spawn_xy[0]), float(spawn_xy[1])) if spawn_xy is not None else None
        goals = []
        for _ in range(n):
            ok = np.ones(len(ii), bool) if prev is None else \
                np.hypot(cx - prev[0], cy - prev[1]) >= min_euclid
            cand = np.nonzero(ok)[0]
            chosen = None
            tries = 0
            while len(cand) and tries < max_tries:
                k = int(rng.integers(len(cand)))
                c = cand[k]
                tries += 1
                if prev is None:
                    chosen = c
                    break
                sp = shortest_path_length(gt, prev, (cx[c], cy[c]))
                if sp is not None and sp >= min_path:
                    chosen = c
                    break
                cand = np.delete(cand, k)
            if chosen is None:
                break
            yaw = float(rng.uniform(-math.pi, math.pi))
            goals.append({'x': float(cx[chosen]), 'y': float(cy[chosen]), 'yaw': yaw})
            prev = (float(cx[chosen]), float(cy[chosen]))
        return goals

    out: Dict[str, List[dict]] = {}
    if fixed is not None:
        out['fixed'] = [dict(g) for g in fixed]
    rng = np.random.default_rng(rng_seed)
    out['random20'] = sequential(base & (d >= 0.40), n_random, rng)
    out['near_wall'] = sequential(base & (d >= 0.20) & (d <= 0.35), n_near_wall, rng)

    elig = base & (d >= 0.40)
    goals = []
    if elig.any():
        if spawn_xy is not None:
            prev = _snap(gt, spawn_xy)
        else:
            prev = None
        if prev is None:
            jj, ii = np.nonzero(elig)
            prev = (int(ii[0]), int(jj[0]))
        for _ in range(n_long):
            dist = _graph_dist(gt.navigable, prev, res)
            dd = np.where(elig & np.isfinite(dist), dist, -1.0)
            j, i = np.unravel_index(int(np.argmax(dd)), dd.shape)
            if dd[j, i] <= 0:
                break
            x, y = centre(i, j)
            goals.append({'x': float(x), 'y': float(y),
                          'yaw': float(rng.uniform(-math.pi, math.pi))})
            prev = (int(i), int(j))
    out['long_range'] = goals
    return out
