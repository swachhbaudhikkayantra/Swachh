import numpy as np
from scipy import ndimage

from vacuum_eval.metrics.common import GtGrid, Run
from vacuum_eval.metrics.safety import (clearance_series, collision_events,
                                        compute_safety_metrics, encounters)

RES = 0.05


def make_gt(occ, names=('box',)):
    d = (ndimage.distance_transform_edt(~occ) * RES).astype(np.float32)
    free = ~occ
    nb = np.zeros_like(occ)
    nb[1:, :] |= free[:-1, :]
    nb[:-1, :] |= free[1:, :]
    nb[:, 1:] |= free[:, :-1]
    nb[:, :-1] |= free[:, 1:]
    boundary = occ & nb
    return GtGrid(occ=occ, a_clean=free, navigable=(d >= 0.125) & free, boundary=boundary,
                  dist_to_obstacle=d, obs_id=np.where(occ, 0, -1).astype(np.int16),
                  obs_names=list(names), x0=0.0, y0=0.0, res=RES, world_name='syn')


def box_gt():
    occ = np.zeros((200, 200), bool)
    occ[100:108, 100:108] = True       # box x 5.0..5.4, y 5.0..5.4
    return make_gt(occ)


def pass_by_traj(y, x_from=4.0, x_to=6.4, v=0.5):
    n = int((x_to - x_from) / (v * 0.1)) + 1
    t = 0.1 * np.arange(n)
    return {'t': t, 'gt_x': x_from + v * t, 'gt_y': np.full(n, y), 'gt_yaw': np.zeros(n),
            'gt_vx': np.full(n, v), 'gt_wz': np.zeros(n)}


def test_T062_event_grouping():
    rows = {'t': np.array([1.0, 1.2, 1.4, 3.0]),
            'other_model': np.array(['wall_north'] * 4, dtype=object)}
    ev = collision_events(rows)
    assert len(ev) == 2
    assert ev[0]['n_rows'] == 3 and ev[0]['t_start'] == 1.0 and ev[0]['t_end'] == 1.4


def test_T063_clearance_wall():
    occ = np.zeros((100, 100), bool)
    occ[:, 40:] = True                 # wall face at x = 2.0
    gt = make_gt(occ, names=('wall_east',))
    traj = {'t': np.array([0.0]), 'gt_x': np.array([1.65]), 'gt_y': np.array([2.5]),
            'gt_yaw': np.array([0.0])}
    c = clearance_series(traj, gt, None)
    assert abs(c[0] - 0.2) < 0.03
    traj['gt_yaw'] = np.array([np.pi / 2])   # long side now toward... still bounded
    c2 = clearance_series(traj, gt, None)
    assert abs(c2[0] - (2.0 - 1.65 - 0.125)) < 0.03


def test_T064_encounter_collision_free():
    gt = box_gt()
    traj = pass_by_traj(y=5.0 - 0.125 - 0.3)
    c = clearance_series(traj, gt, None)
    assert abs(c.min() - 0.3) < 0.03
    enc = encounters(traj, gt, None)
    assert len(enc['box']) == 1
    run = Run(meta={}, trajectory={**traj, 'gt_vx': traj['gt_vx']}, episode_start_t=0.0,
              episode_end_t=100.0, collisions_raw={'t': np.array([]), 'other_model': np.array([], dtype=object)})
    m = compute_safety_metrics(run, gt, {})
    assert m['n_collisions'] == 0 and m['collision_source'] == 'contact'
    assert m['n_encounters'] == 1 and m['avoidance_pct'] == 100.0
    assert abs(m['min_clearance_m'] - 0.3) < 0.03
    assert m['time_below_020m_s'] == 0.0


def test_T065_encounter_with_contact():
    gt = box_gt()
    traj = pass_by_traj(y=5.0 - 0.125 - 0.3)
    raw = {'t': np.array([2.0, 2.1]), 'other_model': np.array(['box', 'box'], dtype=object)}
    run = Run(meta={}, trajectory=traj, episode_start_t=0.0, episode_end_t=100.0,
              collisions_raw=raw)
    m = compute_safety_metrics(run, gt, {})
    assert m['n_collisions'] == 1
    assert m['n_encounters'] == 1 and m['avoidance_pct'] == 0.0
    assert m['collision_first_t_ep'] == 2.0
    assert m['n_collisions_geom'] == 0
    assert 'no encounters' not in m['notes']


def test_T066_no_encounter_null():
    gt = box_gt()
    traj = pass_by_traj(y=2.0)
    run = Run(meta={}, trajectory=traj, episode_start_t=0.0, episode_end_t=100.0,
              collisions_raw={'t': np.array([]), 'other_model': np.array([], dtype=object)})
    m = compute_safety_metrics(run, gt, {})
    assert m['n_encounters'] == 0
    assert m['avoidance_pct'] is None
    assert 'no encounters' in m['notes']


def test_geometry_fallback_and_dynamic():
    gt = box_gt()
    traj = pass_by_traj(y=5.2)                       # drives through the box
    run = Run(meta={}, trajectory=traj, episode_start_t=0.0, episode_end_t=100.0)
    m = compute_safety_metrics(run, gt, {})
    assert m['collision_source'] == 'geometry' and m['n_collisions'] == 1
    # dynamic obstacle sitting in the robot's path
    n = len(traj['t'])
    dyn = {'t': traj['t'], 'name': np.array(['dyn_box_1'] * n, dtype=object),
           'x': np.full(n, 5.0), 'y': np.full(n, 2.0), 'yaw': np.zeros(n)}
    traj2 = pass_by_traj(y=2.0, x_from=4.0, x_to=6.0)
    dyn['t'] = traj2['t']
    dyn['name'] = dyn['name'][:len(traj2['t'])]
    dyn['x'] = dyn['x'][:len(traj2['t'])]
    dyn['y'] = dyn['y'][:len(traj2['t'])]
    dyn['yaw'] = dyn['yaw'][:len(traj2['t'])]
    cfg = {'dynamic_obstacles': {'dyn_box_1': {'size': [0.4, 0.4]}}}
    run = Run(meta={}, trajectory=traj2, dyn_obstacles=dyn, episode_start_t=0.0,
              episode_end_t=100.0)
    m = compute_safety_metrics(run, gt, cfg)
    assert m['n_collisions'] == 1 and m['n_collision_obstacles'] == 1
