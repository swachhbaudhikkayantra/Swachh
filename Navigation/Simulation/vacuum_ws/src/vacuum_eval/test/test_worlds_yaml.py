"""T-035: every spawn candidate and goal in worlds.yaml is free/navigable and reachable (GT rasteriser)."""
import math
import os

import pytest
import yaml

from vacuum_eval.metrics import gt_grid

HERE = os.path.dirname(os.path.abspath(__file__))
YAML = os.path.join(HERE, '..', 'config', 'worlds.yaml')
WORLDS_DIR = os.path.join(HERE, '..', '..', 'vacuum_gazebo', 'worlds')
CLEARANCE = 0.195 + 0.10   # robot radius + margin (spec 09 sec 9.7)

with open(YAML) as _f:
    CFG = yaml.safe_load(_f)['worlds']


def _cell(gt, p):
    i = int(math.floor((p[0] - gt.x0) / gt.res))
    j = int(math.floor((p[1] - gt.y0) / gt.res))
    return j, i


@pytest.mark.parametrize('name', sorted(CFG))
def test_world_points_navigable(name):
    w = CFG[name]
    sdf = os.path.join(WORLDS_DIR, os.path.basename(w['sdf_file']))
    assert os.path.isfile(sdf)
    gt = gt_grid.build(sdf, w['reachable_seed'])          # raises WorldNotSealed if open
    assert gt.world_name == w['world_name_in_sdf']
    assert len(w['spawn_candidates']) >= 8
    assert len(w['goal_lists']['fixed']) == 6
    pts = [('spawn', p) for p in w['spawn_candidates']] + \
          [('fixed', p) for p in w['goal_lists']['fixed']] + \
          [('tour', p) for p in w['goal_lists'].get('loop_tour', [])]
    seed_gt = gt_grid.build(sdf, w['reachable_seed'], spawn_xy=w['reachable_seed'])
    for kind, p in pts:
        j, i = _cell(gt, p)
        assert gt.a_clean[j, i], (name, kind, p, 'not in a_clean')
        assert gt.dist_to_obstacle[j, i] >= CLEARANCE, (name, kind, p, float(gt.dist_to_obstacle[j, i]))
        assert seed_gt.navigable[j, i] and seed_gt.a_reach[j, i], (name, kind, p, 'not navigable/reachable')
