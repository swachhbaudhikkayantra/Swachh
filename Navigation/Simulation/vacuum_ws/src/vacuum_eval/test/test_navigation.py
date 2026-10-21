import math

import numpy as np
from scipy import ndimage

from vacuum_eval.metrics.common import GtGrid, Run
from vacuum_eval.metrics.navigation import (compute_navigation_metrics, generate_goal_lists,
                                            shortest_path_length)

RES = 0.05


def make_gt(occ, res=RES, x0=0.0, y0=0.0):
    d = (ndimage.distance_transform_edt(~occ) * res).astype(np.float32)
    a_clean = ~occ
    navigable = (d >= 0.125) & a_clean
    return GtGrid(occ=occ, a_clean=a_clean, navigable=navigable,
                  boundary=np.zeros_like(occ), dist_to_obstacle=d,
                  obs_id=np.where(occ, 0, -1).astype(np.int16), obs_names=['obs'],
                  x0=x0, y0=y0, res=res, world_name='syn', a_reach=navigable.copy())


def corridor(w=140, h=40):
    occ = np.zeros((h, w), bool)
    occ[0:2, :] = occ[-2:, :] = occ[:, 0:2] = occ[:, -2:] = True
    return occ


def goal_events(rows):
    """rows: (src, seq, event, result, t, x, y, uuid)"""
    cols = ['src', 'goal_seq', 'event', 'result', 't', 'x', 'y', 'uuid']
    d = {c: [] for c in cols}
    for r in rows:
        for c, v in zip(cols, r):
            d[c].append(v)
    out = {}
    for c in cols:
        out[c] = np.array(d[c], dtype=object if c in ('src', 'event', 'result', 'uuid') else float)
    return out


def traj_from(points, dt=0.1, t0=0.0):
    pts = np.asarray(points, float)
    n = len(pts)
    t = t0 + dt * np.arange(n)
    return {'t': t, 'gt_x': pts[:, 0], 'gt_y': pts[:, 1], 'gt_yaw': np.zeros(n),
            'gt_vx': np.full(n, 0.2), 'gt_wz': np.zeros(n),
            'odom_x': pts[:, 0], 'odom_y': pts[:, 1]}


def test_T050_success_counts():
    rows = []
    results = ['succeeded'] * 5 + ['nav_aborted'] * 2 + ['timeout', 'canceled_by_manager']
    for k, res in enumerate(results):
        rows.append(('scripted', k, 'started', '', 10.0 * k, 1.0, 1.0, ''))
        rows.append(('scripted', k, 'ended', res, 10.0 * k + 5.0, np.nan, np.nan, ''))
    rows.append(('scripted', 9, 'started', '', 95.0, 1.0, 1.0, ''))
    run = Run(meta={'method': 'scripted_goals', 't_world_map': [0, 0, 0]},
              goal_events=goal_events(rows), episode_start_t=0.0, episode_end_t=200.0)
    m = compute_navigation_metrics(run, make_gt(corridor()))
    assert m['nav_goals_total'] == 8
    assert m['nav_success_pct'] == 62.5
    assert m['nav_goals_canceled'] == 1
    assert m['nav_goals_unfinished'] == 1
    assert m['nav_fail_aborted'] == 2 and m['nav_fail_timeout'] == 1
    assert m['n_stuck_goals'] == 1
    assert m['goal_time_mean_s'] == 5.0


def test_T051_corridor_shortest():
    gt = make_gt(corridor())
    s = shortest_path_length(gt, (0.5, 1.0), (5.5, 1.0))
    assert abs(s - 5.0) < 0.01
    s = shortest_path_length(gt, (0.5, 0.8), (5.5, 1.2))
    assert abs(s - math.hypot(5.0, 0.4)) < 0.01


def test_T052_wall_detour_and_ratio():
    occ = np.zeros((100, 100), bool)
    occ[0:2, :] = occ[-2:, :] = occ[:, 0:2] = occ[:, -2:] = True
    occ[0:70, 48:52] = True           # wall x 2.4..2.6, gap above y=3.5
    gt = make_gt(occ)
    a, b = (1.0, 1.5), (4.0, 1.5)
    euclid = 3.0
    s = shortest_path_length(gt, a, b)
    assert s > euclid + 0.5
    # perfect follower along the detour
    corner1, corner2 = (2.2, 3.6), (2.8, 3.6)
    poly = [a, corner1, corner2, b]
    pts = []
    for p, q in zip(poly[:-1], poly[1:]):
        n = max(int(math.hypot(q[0] - p[0], q[1] - p[1]) / 0.02), 1)
        for k in range(n):
            pts.append((p[0] + (q[0] - p[0]) * k / n, p[1] + (q[1] - p[1]) * k / n))
    pts.append(b)
    tr = traj_from(pts, dt=0.1)
    t_end = tr['t'][-1]
    rows = [('scripted', 0, 'started', '', 0.0, 4.0, 1.5, ''),
            ('scripted', 0, 'ended', 'succeeded', t_end, np.nan, np.nan, '')]
    run = Run(meta={'method': 'scripted_goals', 't_world_map': [0, 0, 0]}, trajectory=tr,
              goal_events=goal_events(rows), episode_start_t=0.0, episode_end_t=t_end + 1)
    m = compute_navigation_metrics(run, gt)
    assert m['path_length_ratio_n'] == 1
    assert 0.97 <= m['path_length_ratio_mean'] <= 1.3
    assert m['nav_success_gt_pct'] == 100.0


def test_T053_goal_in_obstacle_skipped():
    occ = corridor()
    occ[10:30, 60:80] = True
    gt = make_gt(occ)
    assert shortest_path_length(gt, (0.5, 1.0), (3.5, 1.0)) is None
    tr = traj_from([(0.5 + 0.02 * k, 1.0) for k in range(100)])
    rows = [('scripted', 0, 'started', '', 0.0, 3.5, 1.0, ''),
            ('scripted', 0, 'ended', 'succeeded', 9.9, np.nan, np.nan, '')]
    run = Run(meta={'method': 'scripted_goals', 't_world_map': [0, 0, 0]}, trajectory=tr,
              goal_events=goal_events(rows), episode_start_t=0.0, episode_end_t=20.0)
    m = compute_navigation_metrics(run, gt)
    assert m['ratio_skipped'] == 1
    assert m['path_length_ratio_n'] == 0 and m['path_length_ratio_mean'] is None


def test_T054_energy_proxy():
    n = 101
    tr = traj_from([(0.02 * k, 1.0) for k in range(n)])
    run = Run(meta={}, trajectory=tr, episode_start_t=0.0, episode_end_t=100.0)
    m = compute_navigation_metrics(run, make_gt(corridor()))
    assert abs(m['energy_proxy_m2ps'] - 0.8) < 1e-9
    assert abs(m['distance_gt_m'] - 2.0) < 1e-9
    assert m['smooth_curvature_rms_1pm'] == 0.0


def test_T055_curvature():
    n = 50
    tr = traj_from([(0.1 * k, 1.0) for k in range(n)])
    tr['gt_vx'][:] = 0.2
    tr['gt_wz'][:] = 0.2
    run = Run(meta={}, trajectory=tr, episode_start_t=0.0, episode_end_t=100.0)
    m = compute_navigation_metrics(run, make_gt(corridor()))
    assert abs(m['smooth_curvature_rms_1pm'] - 1.0) < 1e-9
    assert abs(m['smooth_curvature_var']) < 1e-12


def test_T057_goal_list_determinism():
    occ = np.zeros((120, 120), bool)
    occ[0:2, :] = occ[-2:, :] = occ[:, 0:2] = occ[:, -2:] = True
    occ[40:60, 50:70] = True
    gt = make_gt(occ)
    a = generate_goal_lists(gt, 2001, spawn_xy=(1.0, 1.0))
    b = generate_goal_lists(gt, 2001, spawn_xy=(1.0, 1.0))
    c = generate_goal_lists(gt, 2002, spawn_xy=(1.0, 1.0))
    assert a == b
    assert a != c
    assert len(a['random20']) == 20 and len(a['near_wall']) == 10 and len(a['long_range']) == 6
    prev = (1.0, 1.0)
    for g in a['random20']:
        assert math.hypot(g['x'] - prev[0], g['y'] - prev[1]) >= 1.5 - 1e-9
        i, j = gt.world_to_cell(g['x'], g['y'])
        assert gt.dist_to_obstacle[j, i] >= 0.40 - 1e-6
        prev = (g['x'], g['y'])
    for g in a['near_wall']:
        i, j = gt.world_to_cell(g['x'], g['y'])
        assert 0.20 - 1e-6 <= gt.dist_to_obstacle[j, i] <= 0.35 + 1e-6


def _run_goals(results, t_end_ep=200.0, ends=None, traj=None):
    rows = []
    for k, res in enumerate(results):
        te = (ends[k] if ends else 10.0 * k + 5.0)
        rows.append(('scripted', k, 'started', '', 10.0 * k, 1.0, 1.0, ''))
        rows.append(('scripted', k, 'ended', res, te, np.nan, np.nan, ''))
    return Run(meta={'method': 'scripted_goals', 't_world_map': [0, 0, 0]},
               goal_events=goal_events(rows), episode_start_t=0.0, episode_end_t=t_end_ep,
               trajectory=traj)


def test_canceled_is_failure_and_truncated_excluded():
    run = _run_goals(['succeeded', 'canceled', 'canceled'], ends=[5.0, 15.0, 199.5])
    m = compute_navigation_metrics(run, make_gt(corridor()))
    assert m['nav_goals_total'] == 2 and m['nav_fail_canceled'] == 1
    assert m['nav_goals_truncated'] == 1
    assert m['nav_success_pct'] == 50.0


def test_gt_success_tolerances_and_row_dt():
    n = 60
    t = 0.2 * np.arange(n)           # 0.2 s rows, not 0.1
    x = np.full(n, 1.0 + 0.2)        # 0.2 m from goal (1, 1)
    z = np.zeros(n)
    traj = {'t': t, 'gt_x': x, 'gt_y': np.full(n, 1.0), 'gt_yaw': z, 'gt_vx': z, 'gt_wz': z}
    m = compute_navigation_metrics(_run_goals(['succeeded'], t_end_ep=20.0, ends=[5.0], traj=traj),
                                   make_gt(corridor()))
    assert m['nav_success_gt_pct'] == 100.0 and m['nav_success_gt_strict_pct'] == 0.0
    assert abs(m['time_stationary_s'] - 0.2 * n) < 1e-6
