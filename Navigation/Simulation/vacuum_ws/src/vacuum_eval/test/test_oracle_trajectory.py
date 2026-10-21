"""Known-answer oracles for metrics/trajectory.py. Expectations are computed by hand
or by a separate numpy implementation written here (never by the module under test)."""
import math
import os

import numpy as np
import pytest
import yaml

from vacuum_eval.metrics.common import Run
from vacuum_eval.metrics.trajectory import compute_trajectory_metrics


def make_run(t, gt, est=None, odom=None, meta=None):
    n = len(t)
    nan = np.full(n, np.nan)
    tr = {'t': t, 't_rel': t - t[0], 'gt_x': gt[:, 0], 'gt_y': gt[:, 1], 'gt_yaw': gt[:, 2],
          'est_x': est[:, 0] if est is not None else nan,
          'est_y': est[:, 1] if est is not None else nan,
          'est_yaw': est[:, 2] if est is not None else nan,
          'odom_x': odom[:, 0] if odom is not None else nan,
          'odom_y': odom[:, 1] if odom is not None else nan,
          'odom_yaw': odom[:, 2] if odom is not None else nan,
          'est_ok': np.ones(n)}
    return Run(meta=meta or {'t_world_map': [0, 0, 0]}, trajectory=tr,
               episode_start_t=float(t[0]), episode_end_t=float(t[-1]))


def square_path(n_side=100, side=4.0):
    """400 poses around a 4x4 m square, CCW, starting at the origin."""
    s = np.arange(n_side) / n_side * side
    z, o = np.zeros(n_side), np.full(n_side, side)
    x = np.concatenate([s, o, side - s, z])
    y = np.concatenate([z, s, o, side - s])
    yaw = np.concatenate([z, z + math.pi / 2, z + math.pi, z - math.pi / 2])
    return np.stack([x, y, yaw], axis=1)


def kabsch_rmse(E, G):
    """Own rigid 2D alignment (SVD / Kabsch, no scale), returns RMSE after aligning E->G."""
    Ec, Gc = E - E.mean(0), G - G.mean(0)
    U, _, Vt = np.linalg.svd(Ec.T @ Gc)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1, d]) @ U.T
    A = Ec @ R.T + G.mean(0)
    return math.sqrt(np.mean(np.sum((A - G) ** 2, axis=1)))


def test_oracle_ate_translation_offset():
    # Hand derivation: every estimate point is displaced by (0.3,-0.4), |d| = 0.5 for all
    # 400 samples, so fixed RMSE = sqrt(mean(0.5^2)) = 0.5 exactly. A rigid alignment
    # absorbs a pure translation, so aligned RMSE = 0.
    gt = square_path()
    t = np.arange(400) * 0.1
    est = gt + np.array([0.3, -0.4, 0.0])
    m = compute_trajectory_metrics(make_run(t, gt, est=est))
    assert m['ate_fixed_rmse_m'] == pytest.approx(0.5, abs=1e-9)
    assert m['ate_aligned_rmse_m'] == pytest.approx(0.0, abs=1e-6)
    assert m['ate_samples'] == 400


def test_oracle_ate_rotation_about_start():
    # Estimate = GT rotated 2 deg about GT[0]=(0,0). Position error of point p is
    # |R(2deg)p - p| = 2 sin(1deg) |p|, so fixed RMSE = 2 sin(1deg) sqrt(mean |p|^2).
    gt = square_path()
    t = np.arange(400) * 0.1
    th = math.radians(2.0)
    R = np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
    est_xy = gt[:, :2] @ R.T
    est = np.column_stack([est_xy, gt[:, 2] + th])
    expected_fixed = 2 * math.sin(th / 2) * math.sqrt(np.mean(np.sum(gt[:, :2] ** 2, axis=1)))
    expected_aligned = kabsch_rmse(est_xy, gt[:, :2])     # ~0: pure rotation is rigid
    m = compute_trajectory_metrics(make_run(t, gt, est=est))
    assert m['ate_fixed_rmse_m'] == pytest.approx(expected_fixed, rel=1e-6)
    assert expected_aligned < 1e-9
    assert m['ate_aligned_rmse_m'] == pytest.approx(expected_aligned, abs=1e-6)
    assert m['ate_yaw_rmse_deg'] == pytest.approx(2.0, abs=1e-6)


def test_oracle_ate_aligned_with_noise_matches_kabsch():
    # Non-trivial aligned residual: deterministic perturbation, expectation from own SVD.
    gt = square_path()
    t = np.arange(400) * 0.1
    est_xy = gt[:, :2] + 0.05 * np.stack([np.sin(np.arange(400) * 0.37),
                                          np.cos(np.arange(400) * 0.23)], axis=1) + [0.3, 0.2]
    est = np.column_stack([est_xy, gt[:, 2]])
    m = compute_trajectory_metrics(make_run(t, gt, est=est))
    assert m['ate_aligned_rmse_m'] == pytest.approx(kabsch_rmse(est_xy, gt[:, :2]), rel=1e-6)
    fixed = math.sqrt(np.mean(np.sum((est_xy - gt[:, :2]) ** 2, axis=1)))
    assert m['ate_fixed_rmse_m'] == pytest.approx(fixed, rel=1e-9)


def test_oracle_rpe_scale_error():
    # Straight line 5 m, GT pairs exactly 1 m apart (GT spacing 0.02 m -> 50 steps).
    # Estimate x' = 1.01 x -> relative translation 1.01 m vs 1.00 m -> error 0.01 m per pair.
    n = 251
    x = np.arange(n) * 0.02
    gt = np.stack([x, np.zeros(n), np.zeros(n)], axis=1)
    est = gt.copy()
    est[:, 0] *= 1.01
    t = np.arange(n) * 0.1
    m = compute_trajectory_metrics(make_run(t, gt, est=est))
    assert m['rpe_pairs_1m'] > 150
    assert m['rpe_trans_rmse_m_1m'] == pytest.approx(0.01, abs=5e-4)
    assert m['rpe_trans_mean_m_1m'] == pytest.approx(0.01, abs=5e-4)
    assert m['rpe_rot_rmse_deg_1m'] == pytest.approx(0.0, abs=1e-6)


def test_oracle_rpe_heading_drift_on_circle():
    # Circle radius 5 m driven CCW, sampled every 0.01 m of arc. Estimate position == GT,
    # estimate yaw = GT yaw + k*s with k = 1.5 deg per metre of arc. For a pair 1 m of GT
    # path apart the relative yaw error is k*1 m = 1.5 deg for every pair (no wrapping,
    # total drift 47 deg). Chord vs arc differs by <0.2% so the pair separation is ~1 m.
    k_deg = 1.5
    r = 5.0
    n = int(2 * math.pi * r / 0.01)
    s = np.arange(n) * 0.01
    ang = s / r
    gt = np.stack([r * np.cos(ang), r * np.sin(ang), ang + math.pi / 2], axis=1)
    est = gt.copy()
    est[:, 2] = gt[:, 2] + math.radians(k_deg) * s
    t = np.arange(n) * 0.05
    m = compute_trajectory_metrics(make_run(t, gt, est=est))
    assert m['rpe_rot_rmse_deg_1m'] == pytest.approx(k_deg, rel=0.01)


# ---------------------------------------------------------------- real data replay
RUN = os.path.expanduser('~/eval_runs/tune1/apartment/frontier/seed_002')


@pytest.mark.skipif(not os.path.isdir(RUN), reason='recorded run folder missing')
def test_oracle_replay_real_run_distance_and_odom_ate():
    import csv
    import json
    meta = yaml.safe_load(open(os.path.join(RUN, 'run_meta.yaml')))
    summ = json.load(open(os.path.join(RUN, 'summary.json')))
    rows = list(csv.DictReader(open(os.path.join(RUN, 'trajectory.csv'))))

    def col(k):
        return np.array([float(r[k]) if r[k] != '' else np.nan for r in rows])
    t, trel = col('t'), col('t_rel')
    t0 = t[0] - trel[0]
    start = t0 + summ['bringup_sim_sec']
    end = start + summ['episode_sim_sec']
    gx, gy = col('gt_x'), col('gt_y')
    ox, oy, oyaw = col('odom_x'), col('odom_y'), col('odom_yaw')
    sel = (t >= start) & (t <= end) & ~np.isnan(gx) & ~np.isnan(gy)

    # GT path length: sum of consecutive Euclidean steps inside the episode window
    dist = float(np.sum(np.hypot(np.diff(gx[sel]), np.diff(gy[sel]))))
    assert dist == pytest.approx(summ['distance_gt_m'], rel=0.02)

    # odom -> world: p_w = spawn + Rot(spawn_yaw) * p_odom
    sx, sy, syaw = meta['spawn_x'], meta['spawn_y'], meta['spawn_yaw']
    c, s = math.cos(syaw), math.sin(syaw)
    wx = sx + c * ox[sel] - s * oy[sel]
    wy = sy + s * ox[sel] + c * oy[sel]
    G = np.stack([gx[sel], gy[sel]], axis=1)
    E = np.stack([wx, wy], axis=1)
    fixed = math.sqrt(np.mean(np.sum((E - G) ** 2, axis=1)))
    assert fixed == pytest.approx(summ['ate_odom_fixed_rmse_m'], rel=0.02)
    assert kabsch_rmse(E, G) == pytest.approx(summ['ate_odom_aligned_rmse_m'], rel=0.02)
