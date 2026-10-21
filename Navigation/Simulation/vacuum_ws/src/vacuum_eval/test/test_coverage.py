import math

import numpy as np
import pytest

from vacuum_eval.metrics import gt_grid
from vacuum_eval.metrics.common import Run
from vacuum_eval.metrics.coverage import (cleaning_keys, compute_coverage, swept_curve,
                                          swept_grid)

W = 0.25
OX, OY = 0.013, 0.017   # avoid exact alignment with cell-centre lines
R = 0.05 * math.sqrt(2) / 2


@pytest.fixture(scope='module')
def empty_gt(tmp_path_factory):
    d = tmp_path_factory.mktemp('sdf')
    from test_gt_grid import walls, write_sdf
    p = write_sdf(d / 'empty.sdf', walls())
    return gt_grid.build(p, (0.0, 0.0))


def line(x0, y0, x1, y1, step=0.03):
    n = max(int(math.hypot(x1 - x0, y1 - y0) / step), 1)
    yaw = math.atan2(y1 - y0, x1 - x0)
    f = np.linspace(0, 1, n + 1)
    return np.column_stack([OX + x0 + f * (x1 - x0), OY + y0 + f * (y1 - y0),
                            np.full(n + 1, yaw)])


def times(traj):
    return np.arange(len(traj)) * 0.1


def test_t100_straight(empty_gt):
    tr = line(-2, 0, 2, 0)
    sw, vis = swept_grid(tr, times(tr), empty_gt, W)
    area = sw.sum() * empty_gt.res ** 2
    assert area == pytest.approx(1.0, rel=0.05)
    assert vis[sw].max() == 1


def test_t101_twice(empty_gt):
    tr = line(-2, 0, 2, 0)
    tr2 = np.vstack([tr, line(2, 0, -2, 0)])
    sw, vis = swept_grid(tr2, times(tr2), empty_gt, W)
    k = cleaning_keys(sw, vis, empty_gt, 80.0, 8.0, W)
    mid = sw & (np.abs(empty_gt.cell_centers()[0]) < 1.5)
    assert vis[mid].mean() == pytest.approx(2.0, abs=0.05)
    assert 1.9 <= k['overlap_ratio'] <= 2.05


def test_t102_rotation(empty_gt):
    yaw = np.linspace(0, 2 * math.pi, 73)
    tr = np.column_stack([np.full(73, OX), np.full(73, OY), yaw])
    sw, vis = swept_grid(tr, times(tr), empty_gt, W)
    area = sw.sum() * empty_gt.res ** 2
    assert area == pytest.approx(math.pi * 0.125 ** 2, rel=0.10)


def test_t103_boustrophedon(empty_gt):
    pieces = []
    ys = np.arange(-2.95, 2.96, 0.25)
    for n, y in enumerate(ys):
        a, b = (-3.0, 3.0) if n % 2 == 0 else (3.0, -3.0)
        pieces.append(line(a, y, b, y))
        if n + 1 < len(ys):
            seg = line(b, y, b, ys[n + 1])
            seg[:, 2] = 0.0 if b > 0 else math.pi
            pieces.append(seg)
    tr = np.vstack(pieces)
    sw, vis = swept_grid(tr, times(tr), empty_gt, W)
    k = cleaning_keys(sw, vis, empty_gt, len(tr) * 0.1, 1.0, W)
    assert k['coverage_cleaned_pct'] > 97.0
    assert 1.0 <= k['overlap_ratio'] <= 1.1
    assert 0 < k['cleaning_efficiency'] <= 1.0


def test_t104_incremental(empty_gt):
    tr = np.vstack([line(-2, 0, 2, 0), line(2, 0, 2, 2), line(2, 2, -1, 1)])
    t = times(tr)
    samples = [t[10], t[60], t[len(t) // 2], t[-30], t[-1]]
    cur = swept_curve(tr, t, empty_gt, W, samples)
    for T, c in zip(samples, cur):
        keep = t <= T
        sw, _ = swept_grid(tr[keep], t[keep], empty_gt, W)
        assert c == 100.0 * (sw & empty_gt.a_clean).sum() / empty_gt.a_clean.sum()
    assert np.all(np.diff(cur) >= 0)


def test_compute_coverage_with_trajectory(empty_gt, tmp_path):
    tr = line(-2, 0, 2, 0)
    t = 100.0 + times(tr)
    run = Run(run_dir=str(tmp_path), meta=dict(spawn_x=0.0, spawn_y=0.0, spawn_yaw=0.0,
                                                swath_width_m=W),
              trajectory=dict(t=t, gt_x=tr[:, 0], gt_y=tr[:, 1], gt_yaw=tr[:, 2]),
              episode_start_t=100.0, episode_end_t=float(t[-1]))
    data = np.full(empty_gt.occ.shape, -1, np.int8)
    data[empty_gt.a_clean] = 0
    data[empty_gt.occ] = 100
    m = dict(data=data, resolution=0.05, origin_x=empty_gt.x0, origin_y=empty_gt.y0)
    run.maps_final = m
    run.map_snapshots = [(100.0, dict(m, data=np.full_like(data, -1))), (t[-1] / 2 + 50, m)]
    r = compute_coverage(run, empty_gt)
    assert r['coverage_cleaned_pct'] > 2.5 and r['overlap_ratio'] == pytest.approx(1.0, abs=0.01)
    assert r['t_to_95_explored_s'] is not None and r['coverage_explored_auc'] > 0
    assert r['t_to_50_cleaned_s'] is None
    assert (tmp_path / 'coverage_curve.csv').exists() and (tmp_path / 'missed_explored.png').exists()
