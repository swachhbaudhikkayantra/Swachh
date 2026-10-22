import math

import numpy as np

from vacuum_eval.metrics.common import Run
from vacuum_eval.metrics.loop_closure import (compute_loop_closure_metrics, node_poses,
                                              revisit_episodes)


def make(rows, with_traj=True):
    """rows: list of (t, ref, lc, prox, x, y, yaw)."""
    a = np.array(rows, float)
    le = {'t': a[:, 0], 'ref_id': a[:, 1], 'loop_closure_id': a[:, 2],
          'proximity_detection_id': a[:, 3], 'gt_x': a[:, 4], 'gt_y': a[:, 5], 'gt_yaw': a[:, 6]}
    r = Run(loop_events=le, episode_start_t=0.0, episode_end_t=float(a[-1, 0]))
    if with_traj:
        s = np.linspace(0, 2 * math.pi, 100)
        r.trajectory = {'t': np.linspace(0, a[-1, 0], 100), 'gt_x': 3 * np.cos(s),
                        'gt_y': 3 * np.sin(s)}
    return r


def circle_rows(closures=None, n=10):
    """Node k (1..n) every 10 s on a circle; node n is 0.2 m from node 1."""
    closures = closures or {}
    rows = []
    for k in range(1, n + 1):
        ang = 2 * math.pi * (k - 1) / (n - 1)
        x, y = 3 * math.cos(ang), 3 * math.sin(ang)
        if k == n:
            x, y = 3 * math.cos(0) + 0.2, 0.0
        rows.append((10.0 * k, k, closures.get(k, 0), 0, x, y, math.pi / 2 if k == n else ang + math.pi / 2))
    return rows


def test_t080_true_closure():
    m = compute_loop_closure_metrics(make(circle_rows({10: 1})))
    assert m['lc_n_accepted'] == 1 and m['lc_n_true'] == 1 and m['lc_n_false'] == 0
    assert m['lc_precision_pct'] == 100.0 and m['lc_recall_pct'] == 100.0
    assert m['lc_n_revisits'] == 1 and m['lc_f1_pct'] == 100.0
    assert m['lc_per_100m'] is not None


def test_t081_false_closure():
    m = compute_loop_closure_metrics(make(circle_rows({10: 4})))
    assert m['lc_n_false'] == 1 and m['lc_precision_pct'] == 0.0
    assert m['lc_recall_pct'] == 0.0


def test_t082_revisit_no_closure():
    m = compute_loop_closure_metrics(make(circle_rows()))
    assert m['lc_n_revisits'] == 1 and m['lc_recall_pct'] == 0.0
    assert m['lc_precision_pct'] is None and m['lc_f1_pct'] is None


def test_helpers_and_proximity():
    rows = circle_rows({10: 1}) + [(110.0, 11, 0, 3, 0.0, 0.0, 0.0), (111.0, 10, 1, 0, 0, 0, 0)]
    r = make(rows)
    nodes = node_poses(r.loop_events)
    assert nodes[1][0] == 10.0 and list(nodes)[:2] == [1, 2]
    eps = revisit_episodes(nodes, 1.0, math.radians(60), 30.0)
    assert eps == [{10}] or any(10 in e for e in eps)
    m = compute_loop_closure_metrics(r)
    assert m['n_proximity_links'] == 1 and m['lc_n_accepted'] == 1   # duplicate pair counted once
    assert m['lc_n_info_msgs'] == 12


def test_tight_vs_loose_tolerance():
    # node 10 is 0.5 m from node 1: true at old 1.0 m tolerance, false at 0.30 m
    rows = circle_rows({10: 1})
    a = list(rows[-1])
    a[4] = 3.0 + 0.5
    rows[-1] = tuple(a)
    m = compute_loop_closure_metrics(make(rows))
    assert m['lc_n_true'] == 0 and m['lc_n_false'] == 1 and m['lc_precision_pct'] == 0.0
    assert m['lc_n_true_loose'] == 1 and m['lc_precision_loose_pct'] == 100.0


def test_yaw_tolerance_default():
    rows = circle_rows({10: 1})
    a = list(rows[-1])
    a[6] = math.pi / 2 - math.radians(45)  # node 1 yaw is pi/2; 45 deg off
    rows[-1] = tuple(a)
    m = compute_loop_closure_metrics(make(rows))
    assert m['lc_n_true'] == 0 and m['lc_n_true_loose'] == 1


def _reg_run(tf, a=(0.0, 0.0, 0.0), b=(1.0, 1.0, math.pi / 2)):
    """Ref node 2 (current, 40 s) at a closes to loop node 1 (old) at b; tf is ref->loop,
    i.e. inv(Pa)*Pb. Default: Pa=(0,0,0) -> (1, 1, 90 deg)."""
    rows = [(0, 1, 0, 0, b[0], b[1], b[2]), (40, 2, 1, 0, a[0], a[1], a[2])]
    r = make(rows)
    r.loop_events['lc_tx'] = np.array([np.nan, tf[0]])
    r.loop_events['lc_ty'] = np.array([np.nan, tf[1]])
    r.loop_events['lc_tyaw'] = np.array([np.nan, tf[2]])
    return r


def test_reg_correct_transform_far_apart_nodes():
    # Nodes 1.41 m apart: old position test says false, but transform matches GT.
    m = compute_loop_closure_metrics(_reg_run((1.0, 1.0, math.pi / 2)),
                                     convention='ref_to_loop')
    assert m['lc_n_true'] == 1 and m['lc_precision_pct'] == 100.0
    assert m['lc_precision_samepose_pct'] == 0.0
    assert m['lc_precision_loose_pct'] == 0.0   # 1.41 m > 1.0 m


def test_reg_wrong_transform_same_place():
    # Nodes at the same pose (GT rel = 0,0,0) but RTAB-Map says 0.5 m off -> false.
    r = _reg_run((0.5, 0.0, 0.0), b=(0.0, 0.0, 0.0))
    m = compute_loop_closure_metrics(r)
    assert m['lc_n_true'] == 0 and m['lc_precision_pct'] == 0.0
    assert m['lc_precision_samepose_pct'] == 100.0


def test_reg_rotated_frame_and_rot_tol():
    # Pa=(1,0,90deg), Pb=(1,2,90deg): rel = (2, 0, 0). Tx=2.05 ok; yaw error 6 deg fails.
    a, b = (1.0, 0.0, math.pi / 2), (1.0, 2.0, math.pi / 2)
    assert compute_loop_closure_metrics(_reg_run((2.05, 0.0, 0.0), a, b),
                                        convention='ref_to_loop')['lc_n_true'] == 1
    assert compute_loop_closure_metrics(
        _reg_run((2.0, 0.0, math.radians(6)), a, b), convention='ref_to_loop')['lc_n_true'] == 0


def test_reg_missing_columns_fallback():
    r = _reg_run((0, 0, 0), b=(0.1, 0.0, 0.0))
    for k in ('lc_tx', 'lc_ty', 'lc_tyaw'):
        del r.loop_events[k]
    m = compute_loop_closure_metrics(r)
    assert m['lc_n_true'] == 1 and any('lack lc_tx' in n for n in m['notes'])


def _tf_run(convention, lc_pose_b=(1.0, 0.5, 0.3)):
    from vacuum_eval.metrics.loop_closure import expected_tf
    pa = (0.0, 0.0, 0.0, 0.0)
    pb = (0.0, *lc_pose_b)
    tf = expected_tf(pa, pb, convention)
    rows = [(10.0, 1, 0, 0, pb[1], pb[2], pb[3]), (100.0, 2, 1, 0, 0.0, 0.0, 0.0)]
    a = np.array(rows, float)
    le = {'t': a[:, 0], 'ref_id': a[:, 1], 'loop_closure_id': a[:, 2],
          'proximity_detection_id': a[:, 3], 'gt_x': a[:, 4], 'gt_y': a[:, 5], 'gt_yaw': a[:, 6],
          'lc_tx': np.array([np.nan, tf[0]]), 'lc_ty': np.array([np.nan, tf[1]]),
          'lc_tyaw': np.array([np.nan, tf[2]])}
    return Run(loop_events=le, episode_start_t=0.0, episode_end_t=100.0)


def test_convention_param():
    r = _tf_run('loop_to_ref')
    assert compute_loop_closure_metrics(r, convention='loop_to_ref')['lc_n_true'] == 1
    assert compute_loop_closure_metrics(r, convention='ref_to_loop')['lc_n_true'] == 0
    r2 = _tf_run('ref_to_loop')
    assert compute_loop_closure_metrics(r2)['lc_n_true'] == 0   # yaml default is loop_to_ref
    assert compute_loop_closure_metrics(r)['lc_n_true'] == 1    # yaml default (no meta)
    assert compute_loop_closure_metrics(r2, convention='ref_to_loop')['lc_n_true'] == 1
    r.meta = {'config_snapshot': {'lc_transform_convention': 'loop_to_ref'}}
    assert compute_loop_closure_metrics(r)['lc_n_true'] == 1    # from meta


def test_reg_error_medians():
    r = _reg_run((1.0 + 0.05, 1.0, math.pi / 2 + math.radians(2)))
    m = compute_loop_closure_metrics(r, convention='ref_to_loop')
    assert abs(m['lc_trans_err_median_m'] - 0.05) < 1e-9
    assert abs(m['lc_rot_err_median_deg'] - 2.0) < 1e-6


def test_reg_error_medians_null_without_columns():
    r = _reg_run((0, 0, 0), b=(0.1, 0.0, 0.0))
    for k in ('lc_tx', 'lc_ty', 'lc_tyaw'):
        del r.loop_events[k]
    m = compute_loop_closure_metrics(r)
    assert m['lc_rot_err_median_deg'] is None and m['lc_trans_err_median_m'] is None
