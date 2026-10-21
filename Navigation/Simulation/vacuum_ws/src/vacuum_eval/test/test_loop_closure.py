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
