import math
import os

import numpy as np
import pytest

from vacuum_eval.metrics import gt_grid
from vacuum_eval.metrics.common import Run
from vacuum_eval.metrics.coverage import (alignment_search, completeness, compute_coverage,
                                          coverage_explored, sample_map)

BOX = ('<model name="{n}"><static>true</static><pose>{p}</pose><link name="link">'
       '<collision name="col"><geometry>{g}</geometry></collision></link></model>')


def box(n, p, s):
    return BOX.format(n=n, p=p, g='<box><size>%s</size></box>' % s)


def write_sdf(path, models, name='w'):
    txt = ('<?xml version="1.0"?><sdf version="1.9"><world name="%s">%s</world></sdf>'
           % (name, ''.join(models)))
    path.write_text(txt)
    return str(path)


def walls(half=3.0, t=0.2, gap=False, h=2.5):
    c = half + t / 2
    L = 2 * half + 2 * t
    north = box('wall_n', '0 %g %g 0 0 0' % (c, h / 2), '%g %g %g' % (L, t, h))
    south = box('wall_s', '0 %g %g 0 0 0' % (-c, h / 2), '%g %g %g' % (L, t, h))
    east = box('wall_e', '%g 0 %g 0 0 0' % (c, h / 2), '%g %g %g' % (t, 2 * half, h))
    west_len = 2 * half - (1.0 if gap else 0.0)
    west = box('wall_w', '%g %g %g 0 0 0' % (-c, 0.5 if gap else 0.0, h / 2),
               '%g %g %g' % (t, west_len, h))
    return [north, south, east, west]


@pytest.fixture
def room_gt(tmp_path):
    p = write_sdf(tmp_path / 'room.sdf', walls() + [box('cube', '1 1 0.5 0 0 0', '1 1 1')])
    return gt_grid.build(p, (-2.0, -2.0))


def gt_to_map(gt, shift=(0.0, 0.0), unknown_x_above=None):
    data = np.full(gt.occ.shape, -1, np.int8)
    data[gt.a_clean] = 0
    data[gt.occ] = 100
    if unknown_x_above is not None:
        X, _ = gt.cell_centers()
        data[X > unknown_x_above] = -1
    return dict(data=data, resolution=gt.res, origin_x=gt.x0 + shift[0], origin_y=gt.y0 + shift[1])


def test_t030_area(room_gt):
    assert abs(room_gt.A_clean_m2 - 35.0) <= 0.4
    assert room_gt.world_name == 'w'
    assert room_gt.obs_names[-1] == 'cube'
    assert room_gt.boundary.any() and room_gt.a_reach is not None and room_gt.A_reach_m2 > 0
    assert room_gt.obs_id.dtype == np.int16 and room_gt.obs_id[room_gt.occ].min() >= 0


def test_t031_rug_not_obstacle(tmp_path):
    p = write_sdf(tmp_path / 'r.sdf', walls() + [box('rug', '0 0 0.01 0 0 0', '2 2 0.02')])
    gt = gt_grid.build(p, (-2.0, -2.0))
    i, j = gt.world_to_cell(0.0, 0.0)
    assert not gt.occ[j, i]
    assert abs(gt.A_clean_m2 - 36.0) <= 0.4


def test_t032_not_sealed(tmp_path):
    p = write_sdf(tmp_path / 'g.sdf', walls(gap=True))
    with pytest.raises(gt_grid.WorldNotSealed):
        gt_grid.build(p, (0.0, 0.0))


def test_t033_unsupported(tmp_path):
    mesh = BOX.format(n='m', p='0 0 0 0 0 0', g='<mesh><uri>x.dae</uri></mesh>')
    p = write_sdf(tmp_path / 'm.sdf', walls() + [mesh])
    with pytest.raises(gt_grid.UnsupportedSdf):
        gt_grid.build(p, (0.0, 0.0))
    tilted = box('t', '0 0 0.5 0.3 0 0', '1 1 1')
    p2 = write_sdf(tmp_path / 't.sdf', walls() + [tilted])
    with pytest.raises(gt_grid.UnsupportedSdf):
        gt_grid.build(p2, (0.0, 0.0))


def test_link_collision_pose_composition(tmp_path):
    m = ('<model name="m"><pose>1 0 0 0 0 0</pose><link name="link"><pose>0 1 0 0 0 1.5707963</pose>'
         '<collision name="col"><pose>1 0 0.5 0 0 0</pose><geometry><box><size>1 0.2 1</size></box>'
         '</geometry></collision></link></model>')
    p = write_sdf(tmp_path / 'c.sdf', walls() + [m])
    gt = gt_grid.build(p, (-2.0, -2.0))
    i, j = gt.world_to_cell(1.0, 2.0)   # model (1,0) + link (0,1) + rotated (1,0)->(0,1)
    assert gt.occ[j, i]


def test_save_load_export_deterministic(room_gt, tmp_path):
    f = str(tmp_path / 'g.npz')
    gt_grid.save(room_gt, f)
    g2 = gt_grid.load(f)
    assert np.array_equal(g2.occ, room_gt.occ) and g2.obs_names == room_gt.obs_names
    assert g2.A_clean_m2 == room_gt.A_clean_m2
    pgm, yml = gt_grid.export_nav2_map(room_gt, str(tmp_path / 'm'))
    assert os.path.getsize(pgm) > room_gt.occ.size
    assert 'origin' in open(yml).read()


def test_cli(tmp_path):
    p = write_sdf(tmp_path / 'room.sdf', walls())
    out = str(tmp_path / 'o.npz')
    assert gt_grid.main(['--sdf', p, '--seed', '0', '0', '--out', out,
                         '--png', str(tmp_path / 'o.png'),
                         '--export-map', str(tmp_path / 'pre')]) == 0
    assert os.path.exists(out) and os.path.exists(str(tmp_path / 'o.png'))


def test_t034_exact_map(room_gt):
    s = sample_map(gt_to_map(room_gt), room_gt, (0, 0, 0))
    assert coverage_explored(s, room_gt) == pytest.approx(100.0)
    assert completeness(s, room_gt)['headline'] * 100 >= 99
    run = Run(meta=dict(spawn_x=0.0, spawn_y=0.0, spawn_yaw=0.0))
    run.maps_final = gt_to_map(room_gt)
    res = compute_coverage(run, room_gt)
    assert res['coverage_explored_pct'] == pytest.approx(100.0)
    assert res['map_completeness_pct'] >= 99
    assert res['coverage_cleaned_pct'] is None and res['notes']


def test_missing_final_map(room_gt):
    res = compute_coverage(Run(), room_gt)
    assert res['coverage_explored_pct'] is None and 'no final map' in res['notes']


def test_t036_shift(room_gt):
    m = gt_to_map(room_gt, shift=(0.15, 0.0))
    fixed = completeness(sample_map(m, room_gt, (0, 0, 0)), room_gt)['headline']
    dx, dy, dyaw, s = alignment_search(m, room_gt, (0, 0, 0))
    aligned = completeness(s, room_gt)['headline']
    assert fixed < aligned
    assert abs(abs(dx) - 0.15) <= 0.06 and dx < 0
    assert abs(dy) <= 0.06
    run = Run(meta=dict(spawn_x=0.0, spawn_y=0.0, spawn_yaw=0.0))
    run.maps_final = m
    res = compute_coverage(run, room_gt)
    assert res['map_completeness_aligned_pct'] > res['map_completeness_pct']


def test_t037_half_unknown(room_gt):
    m = gt_to_map(room_gt, unknown_x_above=0.0)
    s = sample_map(m, room_gt, (0, 0, 0))
    assert coverage_explored(s, room_gt) == pytest.approx(50.0, abs=3.0)


def test_spawn_transform(room_gt):
    # map frame = spawn pose (1, 0.5, 0.4) in world; map holding GT seen from that frame
    T = (1.0, 0.5, 0.4)
    c, s_ = math.cos(T[2]), math.sin(T[2])
    res = 0.05
    n = 400
    ox = oy = -10.0
    xs = ox + (np.arange(n) + 0.5) * res
    MX, MY = np.meshgrid(xs, xs)
    wx = T[0] + c * MX - s_ * MY
    wy = T[1] + s_ * MX + c * MY
    i, j = room_gt.world_to_cell(wx, wy)
    ok = (i >= 0) & (i < room_gt.occ.shape[1]) & (j >= 0) & (j < room_gt.occ.shape[0])
    data = np.full((n, n), -1, np.int8)
    ii, jj = i[ok], j[ok]
    data[ok] = np.where(room_gt.occ[jj, ii], 100, np.where(room_gt.a_clean[jj, ii], 0, -1))
    m = dict(data=data, resolution=res, origin_x=ox, origin_y=oy)
    assert coverage_explored(sample_map(m, room_gt, T), room_gt) > 95.0
