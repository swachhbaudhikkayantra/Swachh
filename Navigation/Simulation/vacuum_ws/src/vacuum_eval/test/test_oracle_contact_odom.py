"""Known-answer oracles for metrics/contact_odom.py."""
import math

import numpy as np
import pytest

from vacuum_eval.metrics.common import Run
from vacuum_eval.metrics.contact_odom import compute_contact_odom_metrics
from vacuum_eval.metrics.trajectory import compute_trajectory_metrics

T0 = 100.0


def build(slip=True, contact=(20.0, 25.0), shift=0.0):
    t = T0 + np.arange(0, 60.0, 0.1)
    rel = t - T0
    gt_yaw = 0.5 * rel
    rate = np.where((rel >= 20) & (rel < 25), 1.0 if slip else 0.5, 0.5)
    odom_yaw = np.concatenate([[0.0], np.cumsum(rate[:-1] * 0.1)])
    x, y = 0.5 * rel, 0.2 * np.sin(rel / 5)
    tr = {'t': t, 'gt_x': x, 'gt_y': y, 'gt_yaw': gt_yaw,
          'est_x': x + 0.05, 'est_y': y, 'est_yaw': gt_yaw,
          'odom_x': x + 0.1, 'odom_y': y, 'odom_yaw': odom_yaw, 'est_ok': np.ones(len(t))}
    col = None
    if contact is not None:
        ct = T0 + np.arange(contact[0], contact[1], 0.05) + shift
        col = {'t': ct, 'other_model': np.array(['wall'] * len(ct), dtype=object)}
    return Run(meta={'t_world_map': [0, 0, 0], 'spawn_x': 0.0, 'spawn_y': 0.0, 'spawn_yaw': 0.0},
               trajectory=tr, collisions_raw=col, episode_start_t=T0, episode_end_t=float(t[-1]))


def test_slip_detected():
    m = compute_contact_odom_metrics(build())
    assert m['contact_odom_n_events'] == 1
    assert m['contact_odom_yaw_excess_deg'] == pytest.approx(143.2, abs=1.0)
    assert m['odom_corrupted_by_contact'] == 1
    assert m['t_odom_corrupt_ep_s'] == pytest.approx(20.0, abs=0.1)
    assert m['ate_fixed_rmse_m_pre_corrupt'] is not None


def test_no_collisions():
    run = build(contact=None)
    m = compute_contact_odom_metrics(run)
    full = compute_trajectory_metrics(run)
    assert m['odom_corrupted_by_contact'] == 0 and m['contact_odom_n_events'] == 0
    assert m['contact_odom_yaw_excess_deg'] == 0.0 and m['t_odom_corrupt_ep_s'] is None
    assert m['ate_fixed_rmse_m_pre_corrupt'] == pytest.approx(full['ate_fixed_rmse_m'])
    assert m['ate_odom_fixed_rmse_m_pre_corrupt'] == pytest.approx(full['ate_odom_fixed_rmse_m'])


def test_contact_without_slip():
    m = compute_contact_odom_metrics(build(slip=False))
    assert m['contact_odom_n_events'] == 1
    assert m['contact_odom_yaw_excess_max_deg'] < 0.5
    assert m['odom_corrupted_by_contact'] == 0


def test_contact_outside_episode_ignored():
    run = build(contact=(20.0, 25.0), shift=-50.0)   # before episode start
    m = compute_contact_odom_metrics(run)
    assert m['contact_odom_n_events'] == 0 and m['odom_corrupted_by_contact'] == 0
