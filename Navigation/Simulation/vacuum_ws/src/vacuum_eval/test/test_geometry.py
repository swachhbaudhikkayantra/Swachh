import math

import numpy as np

from vacuum_eval.metrics import geometry as g

HL, HW = g.ROBOT_HALF_L, g.ROBOT_HALF_W


def rr(x, y, yaw, ox, oy, oyaw, hx, hy):
    return float(g.rect_rect_distance(x, y, yaw, ox, oy, oyaw, hx, hy))


def test_touching_boxes_zero():
    # obstacle half 0.5 square at x=1; robot right face at x+0.15 -> touching at x=0.35
    assert abs(rr(0.35, 0, 0, 1.0, 0, 0, 0.5, 0.5)) < 1e-12


def test_gap_and_overlap():
    assert abs(rr(0.25, 0, 0, 1.0, 0, 0, 0.5, 0.5) - 0.10) < 1e-12
    assert abs(rr(0.45, 0, 0, 1.0, 0, 0, 0.5, 0.5) + 0.10) < 1e-12


def test_corner_gap_is_euclidean():
    # robot corner (0.15,0.125) at origin pose; obstacle corner at (0.45,0.525) -> gap (0.3,0.4)=0.5
    assert abs(rr(0, 0, 0, 0.95, 1.025, 0, 0.5, 0.5) - 0.5) < 1e-12


def test_rotated_45_box():
    # diamond (square half 0.5 rotated 45deg) vertex at x = 1.0 - 0.5*sqrt2 along x axis
    xv = 1.0 - 0.5 * math.sqrt(2)
    d = rr(0, 0, 0, 1.0, 0, math.pi / 4, 0.5, 0.5)
    assert abs(d - (xv - HL)) < 1e-12
    assert abs(rr(xv - HL, 0, 0, 1.0, 0, math.pi / 4, 0.5, 0.5)) < 1e-12


def test_crossing_no_vertex_inside_overlaps():
    # plus-shaped overlap: long thin obstacle crossing robot
    assert rr(0, 0, 0, 0, 0, math.pi / 2, 0.05, 1.0) < 0


def test_disc():
    assert abs(float(g.rect_disc_distance(0, 0, 0, 1.0, 0, 0.5)) - (1.0 - HL - 0.5)) < 1e-12
    # centre inside robot: depth to nearest face (0.15-0.05=0.10) + r
    assert abs(float(g.rect_disc_distance(0, 0, 0, 0.05, 0.0, 0.1)) + 0.20) < 1e-12
    # robot yawed 90deg: long axis along y
    assert abs(float(g.rect_disc_distance(0, 0, math.pi / 2, 0, 1.0, 0.5)) - (1.0 - HL - 0.5)) < 1e-12


def test_vectorised():
    x = np.array([0.0, 0.25, 0.35, 0.45])
    d = g.rect_rect_distance(x, 0.0, 0.0, 1.0, 0.0, 0.0, 0.5, 0.5)
    assert np.allclose(d, [0.35, 0.10, 0.0, -0.10])


def test_load_obstacles(tmp_path):
    sdf = tmp_path / 'w.sdf'
    sdf.write_text('''<sdf version="1.9"><world name="w">
<model name="b"><pose>1 2 0 0 0 0.5</pose><link name="l"><collision name="c"><pose>0 0 0.2 0 0 0</pose>
<geometry><box><size>1 0.2 0.4</size></box></geometry></collision></link></model>
<model name="cyl"><pose>3 0 0.2 0 0 0</pose><link name="l"><collision name="c"><geometry><cylinder><radius>0.3</radius><length>0.4</length></cylinder></geometry></collision></link></model>
</world></sdf>''')
    o = g.load_obstacles(str(sdf))
    assert o['b'][0]['kind'] == 'box' and abs(o['b'][0]['yaw'] - 0.5) < 1e-12
    assert o['b'][0]['hx'] == 0.5 and o['cyl'][0]['kind'] == 'disc' and o['cyl'][0]['r'] == 0.3
    d = g.trajectory_distances([3.0 - 0.3 - HL - 0.1], [0.0], [0.0], o)
    assert abs(d['cyl'][0] - 0.1) < 1e-12
