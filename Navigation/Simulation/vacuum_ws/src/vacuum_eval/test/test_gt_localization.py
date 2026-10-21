import math

from vacuum_eval.gt_localization_node import compose_map_to_odom as c


def close(a, b):
    return all(abs(x - y) < 1e-9 for x, y in zip(a, b))


def test_identity():
    assert close(c((0, 0, 0), (1, 2, 0.3), (1, 2, 0.3)), (0, 0, 0))


def test_odom_offset_translation():
    assert close(c((0, 0, 0), (3, 1, 0), (1, 1, 0)), (2, 0, 0))


def test_odom_rotated():
    # base at world (1,0,pi/2); odom sees base at (0,1,0): odom frame = world rotated +pi/2
    # map->odom = world_base * inv(odom_base) = (1,0,pi/2)*(0,-1,0) = (1+1, 0+0, pi/2)
    r = c((0, 0, 0), (1, 0, math.pi / 2), (0, 1, 0))
    assert close(r, (2, 0, math.pi / 2))


def test_map_origin_shift():
    # map frame at world (1,0,0): base at world (3,0,0) is (2,0) in map
    assert close(c((1, 0, 0), (3, 0, 0), (0, 0, 0)), (2, 0, 0))


def test_map_origin_rotated():
    # map at world (0,0,pi/2); base world (0,2,0) -> map (2,0,-pi/2)
    assert close(c((0, 0, math.pi / 2), (0, 2, 0), (0, 0, 0)), (2, 0, -math.pi / 2))
