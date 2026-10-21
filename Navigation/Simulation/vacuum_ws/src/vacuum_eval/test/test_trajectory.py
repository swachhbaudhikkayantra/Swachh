import math

import numpy as np

from vacuum_eval.metrics.common import Run, se2_compose, se2_inverse
from vacuum_eval.metrics.trajectory import compute_trajectory_metrics, rpe, umeyama_2d


def circle_gt(n=600, dt=0.1, radius=5.0, speed=0.5):
    t = np.arange(n) * dt
    ang = speed / radius * t
    return t, radius * np.cos(ang), radius * np.sin(ang), ang + math.pi / 2


def make(t, gt, est=None, odom=None, meta=None, ok=None):
    n = len(t)
    nan = np.full(n, np.nan)
    tr = {'t': t, 't_rel': t - t[0],
          'gt_x': gt[0], 'gt_y': gt[1], 'gt_yaw': gt[2],
          'est_x': est[0] if est else nan, 'est_y': est[1] if est else nan,
          'est_yaw': est[2] if est else nan,
          'odom_x': odom[0] if odom else nan, 'odom_y': odom[1] if odom else nan,
          'odom_yaw': odom[2] if odom else nan,
          'est_ok': np.ones(n) if ok is None else ok}
    return Run(meta=meta or {}, trajectory=tr, episode_start_t=float(t[0]),
               episode_end_t=float(t[-1]))


def test_t040_identical():
    t, x, y, yaw = circle_gt()
    r = make(t, (x, y, yaw), est=(x, y, yaw), odom=(x, y, yaw),
             meta={'spawn_x': 0, 'spawn_y': 0, 'spawn_yaw': 0})
    m = compute_trajectory_metrics(r)
    for k in ('ate_fixed_rmse_m', 'ate_aligned_rmse_m', 'ate_yaw_rmse_deg',
              'rpe_trans_rmse_m_1m', 'rpe_rot_rmse_deg_1m', 'rpe_trans_rmse_m_5s',
              'rpe_odom_trans_rmse_m_1m', 'ate_odom_fixed_rmse_m'):
        assert abs(m[k]) <= 1e-9, k
    assert m['ate_samples'] == 600
    assert m['rpe_pairs_1m'] > 0 and m['rpe_pairs_5s'] > 0
    assert m['ate_improvement_pct'] is None   # clean odometry
    assert m['n_est_gaps'] == 0


def test_t041_translation_offset():
    t, x, y, yaw = circle_gt()
    r = make(t, (x, y, yaw), est=(x + 0.5, y, yaw), meta={'t_world_map': [0, 0, 0]})
    m = compute_trajectory_metrics(r)
    assert abs(m['ate_fixed_rmse_m'] - 0.5) < 1e-9
    assert m['ate_aligned_rmse_m'] < 1e-9
    assert m['start_offset_m'] > 0.10
    assert any('not at spawn' in n for n in m['notes'])


def test_t042_yaw_drift_rpe():
    t = np.arange(600) * 0.1
    x = 0.5 * t
    y = np.zeros_like(t)
    drift = np.radians(1.0) * x   # 1 deg per metre
    r = make(t, (x, y, np.zeros_like(t)), est=(x, y, drift), meta={'t_world_map': [0, 0, 0]})
    m = compute_trajectory_metrics(r)
    assert abs(m['rpe_rot_rmse_deg_1m'] - 1.0) < 0.03


def test_t043_spawn_transform():
    t, x, y, yaw = circle_gt()
    spawn = (2.0, 1.0, math.pi / 2)
    inv = se2_inverse(spawn)
    est = np.array([se2_compose(inv, (a, b, c)) for a, b, c in zip(x, y, yaw)])
    r = make(t, (x, y, yaw), est=(est[:, 0], est[:, 1], est[:, 2]),
             meta={'spawn_x': 2.0, 'spawn_y': 1.0, 'spawn_yaw': math.pi / 2})
    m = compute_trajectory_metrics(r)
    assert m['ate_fixed_rmse_m'] < 1e-9
    assert m['start_offset_m'] < 1e-9


def test_t044_insufficient_motion():
    t = np.arange(600) * 0.1
    z = np.zeros_like(t)
    x = 0.01 * t   # 0.6 m
    r = make(t, (x, z, z), est=(x, z, z), odom=(x, z, z))
    m = compute_trajectory_metrics(r)
    assert m['ate_fixed_rmse_m'] is None and m['rpe_trans_rmse_m_1m'] is None
    assert m['ate_odom_fixed_rmse_m'] is None
    assert 'insufficient motion for ATE/RPE' in m['notes']


def test_t046_synthetic_noise_odom():
    t, x, y, yaw = circle_gt()
    rng = np.random.default_rng(1)
    drift = np.cumsum(rng.normal(0, 0.002, len(t)))
    r = make(t, (x, y, yaw), est=(x + 0.01, y, yaw), odom=(x + drift + 0.05 * t / 60, y, yaw),
             meta={'t_world_map': [0, 0, 0]})
    m = compute_trajectory_metrics(r)
    assert m['ate_odom_fixed_rmse_m'] > 0
    assert math.isfinite(m['ate_improvement_pct'])
    assert m['odom_drift_ratio'] is not None


def test_umeyama_recovers_rigid():
    rng = np.random.default_rng(0)
    G = rng.normal(size=(50, 2))
    th = 0.7
    R0 = np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
    E = (G - [1.0, 2.0]) @ R0   # = R0^-1 (G - t)
    R, t = umeyama_2d(E, G)
    assert np.allclose(E @ R.T + t, G, atol=1e-9)


def test_rpe_function_and_gaps():
    gt = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0.0]])
    est = np.array([[0, 0, 0], [1.1, 0, 0], [2, 0, 0.0]])
    tr, rot = rpe(gt, est, [(0, 1), (1, 2)])
    assert np.allclose(tr, [0.1, 0.1]) and np.allclose(rot, 0)
    t, x, y, yaw = circle_gt()
    ok = np.ones(len(t))
    ok[100:130] = 0   # span 2.9 s
    ok[200:205] = 0   # span 0.4 s, ignored
    m = compute_trajectory_metrics(make(t, (x, y, yaw), est=(x, y, yaw), ok=ok,
                                        meta={'t_world_map': [0, 0, 0]}))
    assert m['n_est_gaps'] == 1 and abs(m['est_gap_total_s'] - 2.9) < 1e-6


def test_amcl_keys():
    t, x, y, yaw = circle_gt()
    ex = x + np.where(t < 10, 0.5, 0.0)
    m = compute_trajectory_metrics(make(t, (x, y, yaw), est=(ex, y, yaw),
                                        meta={'localization_mode': 'amcl', 't_world_map': [0, 0, 0]}))
    assert abs(m['loc_converge_s'] - 10.0) < 0.2
    assert m['loc_lost_events'] == 0
    assert m['loc_error_p95_m'] > 0
