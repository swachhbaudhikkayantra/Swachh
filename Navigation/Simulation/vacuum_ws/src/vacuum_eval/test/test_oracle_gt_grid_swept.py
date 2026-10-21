"""Known-answer oracles for metrics/gt_grid.py and the swept-area functions of coverage.py."""
import math
import os

import numpy as np
import pytest
import yaml

from vacuum_eval.metrics import gt_grid
from vacuum_eval.metrics.coverage import cleaning_keys, swept_grid

DEFAULTS = os.path.join(os.path.dirname(__file__), '..', 'config', 'eval_defaults.yaml')


def _defaults():
    return yaml.safe_load(open(DEFAULTS))


def _box(name, x, y, z, yaw, sx, sy, sz):
    return ('<model name="%s"><static>true</static><pose>%g %g %g 0 0 %g</pose><link name="l">'
            '<collision name="c"><geometry><box><size>%g %g %g</size></box></geometry>'
            '</collision></link></model>' % (name, x, y, z, yaw, sx, sy, sz))


def _room(half_x, half_y, gap=False, extra=()):
    t, h = 0.2, 2.0
    L = 2 * half_x + 2 * t
    m = [_box('n', 0, half_y + t / 2, h / 2, 0, L, t, h),
         _box('s', 0, -half_y - t / 2, h / 2, 0, L, t, h),
         _box('e', half_x + t / 2, 0, h / 2, 0, t, 2 * half_y, h)]
    if gap:   # west wall covers y in [-half_y, half_y-1.0] only
        m.append(_box('w', -half_x - t / 2, -0.5, h / 2, 0, t, 2 * half_y - 1.0, h))
    else:
        m.append(_box('w', -half_x - t / 2, 0, h / 2, 0, t, 2 * half_y, h))
    return m + list(extra)


def _write(path, models):
    path.write_text('<?xml version="1.0"?><sdf version="1.9"><world name="w">%s</world></sdf>'
                    % ''.join(models))
    return str(path)


def test_oracle_gt_grid_area_rug_and_overhead(tmp_path):
    d = _defaults()
    z_hi = d['robot_body_z_hi']
    # Interior 4 x 3 m = 12 m2. Box A 1.0x0.5 (axis aligned) = 0.5 m2. Box B 0.8x0.4 rotated
    # 45 deg = 0.32 m2 (rotation preserves area). Boxes are disjoint and clear of the walls.
    # Rug 2 cm high (z 0..0.02) and an overhead slab whose underside is 0.1 m above the
    # robot band are NOT obstacles. Expected A_clean = 12 - 0.5 - 0.32 = 11.18.
    extra = [_box('A', 0.5, 0.2, 0.5, 0, 1.0, 0.5, 1.0),
             _box('B', -1.0, -0.5, 0.5, math.pi / 4, 0.8, 0.4, 1.0),
             _box('rug', 0.0, -1.0, 0.01, 0, 1.0, 1.0, 0.02),
             _box('overhead', 1.2, 0.9, z_hi + 0.35, 0, 0.6, 0.6, 0.5)]
    gt = gt_grid.build(_write(tmp_path / 'r.sdf', _room(2.0, 1.5, extra=extra)),
                       (-1.5, 1.0), robot_body_z_lo=d['robot_body_z_lo'],
                       robot_body_z_hi=z_hi, r_inscribed_m=d['r_inscribed_m'])
    assert gt.A_clean_m2 == pytest.approx(11.18, rel=0.02)
    # rug and overhead cells must be free
    for (x, y) in [(0.0, -1.0), (1.2, 0.9)]:
        i, j = gt.world_to_cell(x, y)
        assert not gt.occ[j, i] and gt.a_clean[j, i]
    # tall boxes are obstacles
    for (x, y) in [(0.5, 0.2), (-1.0, -0.5)]:
        i, j = gt.world_to_cell(x, y)
        assert gt.occ[j, i]


def test_oracle_gt_grid_wall_gap_not_sealed(tmp_path):
    p = _write(tmp_path / 'gap.sdf', _room(2.0, 1.5, gap=True))
    with pytest.raises(gt_grid.WorldNotSealed):
        gt_grid.build(p, (0.0, 0.0))


# ---------------------------------------------------------------- swept area
@pytest.fixture(scope='module')
def big_gt(tmp_path_factory):
    p = tmp_path_factory.mktemp('sw') / 'big.sdf'
    return gt_grid.build(_write(p, _room(4.0, 4.0)), (0.0, 0.0))


def _keys(gt, traj, width=0.25):
    sw, vis = swept_grid(np.asarray(traj, float), np.arange(len(traj)) * 0.1, gt, width)
    return cleaning_keys(sw, vis, gt, 60.0, 3.0, width), sw, vis


TIE = pytest.mark.xfail(reason='swath edge (+-0.125) coincides with cell centres at y=0: '
                        'inclusive tie counts 6 rows not 5 -> 0.90 vs 0.75 m2 (+20%, spec T-100 '
                        'allows 5%)', strict=False)
Y0 = [0.0, 0.025]


@pytest.mark.parametrize('y0', Y0)
def test_oracle_swept_straight_line(big_gt, y0):
    # 3 m straight drive x 0.25 m swath = 0.75 m2.
    x = np.arange(-1.5, 1.5 + 1e-9, 0.05)
    traj = np.stack([x, np.full_like(x, y0), np.zeros_like(x)], axis=1)
    k, _, _ = _keys(big_gt, traj)
    assert k['swept_area_m2'] == pytest.approx(0.75, rel=0.05)
    assert k['overlap_ratio'] == pytest.approx(1.0, abs=0.02)


def test_oracle_swept_quarter_arc(big_gt):
    # Radius 1 m, 90 deg, swath 0.25 -> annulus sector r in [0.875,1.125]:
    # area = (theta/2)(r2^2 - r1^2) = (pi/4)(1.265625 - 0.765625) = (pi/4)(0.5) = 0.3927 m2.
    a = np.radians(np.arange(0, 90.001, 1.0))
    traj = np.stack([np.cos(a), np.sin(a), a + math.pi / 2], axis=1)
    k, _, _ = _keys(big_gt, traj)
    assert k['swept_area_m2'] == pytest.approx(math.pi / 4 * 0.5, rel=0.05)


@pytest.mark.parametrize('y0', Y0)
def test_oracle_swept_same_line_twice(big_gt, y0):
    # Out along +x then back along -x over the identical strip: every strip cell is visited
    # in two separate runs of intervals -> mean visits ~2, swept area still ~0.75 m2.
    x = np.arange(-1.5, 1.5 + 1e-9, 0.05)
    out = np.stack([x, np.full_like(x, y0), np.zeros_like(x)], axis=1)
    back = np.stack([x[::-1], np.full_like(x, y0), np.full_like(x, math.pi)], axis=1)
    k, sw, vis = _keys(big_gt, np.vstack([out, back]))
    assert k['swept_area_m2'] == pytest.approx(0.75, rel=0.08)
    # interior of the strip (away from the turn-around ends): cells with |x|<1.0
    X, Y = big_gt.cell_centers()
    core = sw & (np.abs(X) < 1.0) & (np.abs(Y - y0) < 0.1)
    assert core.sum() > 20
    assert vis[core].mean() == pytest.approx(2.0, abs=0.05)
    assert k['overlap_ratio'] == pytest.approx(2.0, abs=0.15)
