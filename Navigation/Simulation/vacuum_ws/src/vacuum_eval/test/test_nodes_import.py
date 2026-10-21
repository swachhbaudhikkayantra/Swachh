import math

from vacuum_eval.goal_sender import world_to_map
from vacuum_eval.dynamic_mover import parse_trigger, velocity_towards
from vacuum_eval.responsiveness_test import is_still, latency, onset_reached, trial_plan


def test_world_to_map_identity_and_rotation():
    assert world_to_map((1, 2, 0.5), (0, 0, 0)) == (1, 2, 0.5)
    x, y, yaw = world_to_map((1, 1, math.pi / 2), (1, 0, math.pi / 2))
    assert abs(x - 1) < 1e-9 and abs(y - 0) < 1e-9 and abs(yaw) < 1e-9


def test_velocity_towards():
    assert velocity_towards((0, 0), (3, 4), 1.0)[:2] == (0.6, 0.8)
    assert velocity_towards((0, 0), (0.01, 0), 1.0)[2] is True


def test_trigger():
    assert parse_trigger('time') == ('time', None)
    assert parse_trigger('robot_x_beyond:1.5') == ('robot_x', 1.5)


def test_step_logic():
    assert is_still(0.01, 0.0) and not is_still(0.1, 0.0)
    assert onset_reached('fwd', -0.1, 0, 0.2, 0.5)
    assert not onset_reached('rot', 0, 0.2, 0.2, 0.5)
    assert latency(1.0, 1.25) == 0.25 and latency(1.0, None) is None
    p = trial_plan(2)
    assert [x[1] for x in p] == ['fwd', 'rot', 'fwd', 'rot'] and p[0][2] == 1 and p[2][2] == -1
