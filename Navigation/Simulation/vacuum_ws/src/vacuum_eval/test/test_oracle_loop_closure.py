"""Known-answer oracle for metrics/loop_closure.py (spec 08: 1.0 m, 60 deg, 30 s)."""
import numpy as np
import pytest

from vacuum_eval.metrics.common import Run
from vacuum_eval.metrics.loop_closure import compute_loop_closure_metrics


def _run(rows, dist=200.0):
    a = np.array(rows, float)
    le = {'t': a[:, 0], 'ref_id': a[:, 1], 'loop_closure_id': a[:, 2],
          'proximity_detection_id': a[:, 3], 'gt_x': a[:, 4], 'gt_y': a[:, 5],
          'gt_yaw': a[:, 6]}
    tr = {'t': np.linspace(0, 100, 101), 'gt_x': np.linspace(0, dist, 101),
          'gt_y': np.zeros(101)}
    return Run(loop_events=le, trajectory=tr, episode_start_t=0.0, episode_end_t=100.0)


# rows: (t, ref, loop_closure_id, prox, x, y, yaw)
ROWS = [
    (0, 1, 0, 0, 0, 0, 0), (10, 2, 0, 0, 5, 0, 0), (20, 3, 0, 0, 10, 0, 0),
    (30, 4, 0, 0, 10, 5, 0),
    (60, 5, 1, 0, 0.5, 0.0, 0.1),    # closes to node1: 0.5 m, 0.1 rad -> TRUE
    (65, 9, 0, 0, 20, 20, 0),        # fresh node separates revisit episodes
    (70, 6, 2, 0, 5.4, 0.3, 0.0),    # to node2: 0.5 m -> TRUE
    (75, 10, 0, 0, 30, 30, 0),
    (80, 7, 3, 0, 10, 0.2, 0.2),     # to node3: 0.2 m -> TRUE
    (85, 11, 0, 0, 40, 40, 0),
    (90, 8, 2, 0, 10, 5, 0),         # claims node2 (5,0): 7.1 m away -> FALSE
]
# Hand derivation: 4 accepted, 3 true -> precision 75%.
# Revisits (node >=30 s newer than a node within 1 m/60 deg): 5 (vs 1), 6 (vs 2),
# 7 (vs 3), 8 (vs 4, 60 s older, same pose). Each is separated by a fresh node ->
# 4 revisit episodes; detected = those whose ref has a true closure = 5,6,7 -> 3/4 = 75%.
# lc_per_100m = 100 * 4 accepted / 200 m = 2.


def test_oracle_loop_closure_precision_recall():
    m = compute_loop_closure_metrics(_run(ROWS), pos_tol_m=1.0, yaw_tol_deg=60.0)
    assert m['lc_n_accepted'] == 4
    assert m['lc_n_true'] == 3 and m['lc_n_false'] == 1
    assert m['lc_precision_pct'] == pytest.approx(75.0)
    assert m['lc_n_revisits'] == 4
    assert m['lc_n_revisits_detected'] == 3
    assert m['lc_recall_pct'] == pytest.approx(75.0)
    assert m['lc_f1_pct'] == pytest.approx(75.0)
    assert m['lc_per_100m'] == pytest.approx(2.0, rel=1e-6)


def test_oracle_loop_closure_yaw_tolerance():
    # Same place but yaw differs by 90 deg (> 60 deg) -> false; by 50 deg -> true.
    rows = [(0, 1, 0, 0, 0, 0, 0), (40, 2, 1, 0, 0.1, 0, np.radians(90)),
            (80, 3, 1, 0, 0.1, 0, np.radians(50))]
    m = compute_loop_closure_metrics(_run(rows), pos_tol_m=1.0, yaw_tol_deg=60.0)
    assert m['lc_n_accepted'] == 2 and m['lc_n_true'] == 1
    assert m['lc_precision_pct'] == pytest.approx(50.0)


def test_oracle_loop_closure_default_tolerances():
    # Defaults are 0.30 m / 30 deg. All three accepted closures target node 1 at (0,0,0).
    # t=30: 0.2 m, 20 deg -> both within tolerance -> TRUE
    # t=50: 0.4 m, 0 deg  -> 0.4 > 0.30 m -> FALSE
    # t=70: 0.1 m, 35 deg -> 35 > 30 deg -> FALSE
    # accepted 3, true 1, false 2 -> precision 100 * 1/3.
    rows = [(0, 1, 0, 0, 0, 0, 0),
            (30, 2, 1, 0, 0.2, 0, np.radians(20)),
            (50, 3, 1, 0, 0.4, 0, 0),
            (70, 4, 1, 0, 0.1, 0, np.radians(35))]
    m = compute_loop_closure_metrics(_run(rows))
    assert m['lc_n_accepted'] == 3
    assert m['lc_n_true'] == 1 and m['lc_n_false'] == 2
    assert m['lc_precision_pct'] == pytest.approx(100.0 / 3.0)
