"""Pure planning parts of run_episode (command lines, goals, scenario jitter, GT map export)."""
import argparse
import os

import numpy as np
import yaml

from vacuum_eval import run_batch, run_episode as re


def ns(**kw):
    d = dict(world='apartment', method='frontier', seed=3, odom_noise=0, headless=1,
             stack='bare', nav_map='gt', goal_list=None)
    d.update(kw)
    return argparse.Namespace(**d)


SPAWN = (1.0, -2.0, 0.5)
SCEN = {'scenario': {'start': [-2, 0, 0.0], 'goal': [2, 0, 0.0]},
        'dynamic_obstacles': {'dyn_box_1': {'size': [0.4, 0.4], 'waypoints': [[0, -1.6], [0, 1.6]],
                                            'speed': 0.25, 'start_delay_s': 0.0}}}


def plan(a, ent=None, **kw):
    return re.method_plan(a, ent or {}, SPAWN, '/r', sdf='/w.sdf', goals_file='/r/goals.yaml', **kw)


def test_frontier_unchanged_and_noise_flags():
    p = plan(ns(odom_noise=1))
    c = p['stack'][0].cmd
    assert 'exploration.launch.py environment:=apartment' in c and 'start_manager' not in c
    assert 'odom_noise:=true odom_noise_seed:=1003' in c
    assert p['gates'] == ['G4_tf', 'G5_nav', 'G6_map'] and not p['late']


def test_scripted_gt_plan():
    p = plan(ns(method='scripted_goals'))
    names = [s.name for s in p['stack']]
    assert names == ['sim', 'nav2']
    assert 'world_file:=/w.sdf' in p['stack'][0].cmd and 'extra_bridge' not in p['stack'][0].cmd
    assert 'nav2_localization.launch.py map_path:=/r/gt_map.yaml' in p['stack'][1].cmd
    assert p['gates'] == ['G5_nav', 'initialpose', 'G4_tf', 'G6_map_server']
    gs = p['late'][0]
    assert gs.name == 'goal_sender' and not gs.critical
    assert 'goals_file:=/r/goals.yaml' in gs.cmd and 't_world_map:="[0.000000, 0.000000, 0.000000]"' in gs.cmd


def test_scripted_slam_plan():
    p = plan(ns(method='scripted_goals', nav_map='slam', world='avoid_head_on'))
    assert [s.name for s in p['stack']] == ['sim', 'slam', 'nav2']
    assert 'slam.launch.py' in p['stack'][1].cmd and 'environment:=room' in p['stack'][1].cmd
    assert 'nav2.launch.py' in p['stack'][2].cmd
    assert 't_world_map:="[1.000000, -2.000000, 0.500000]"' in p['late'][0].cmd


def test_dynamic_plan_bridge_and_mover():
    p = plan(ns(method='scripted_goals', world='avoid_dynamic_cross'), SCEN,
             bridge_cfg='/b.yaml', delays=[1.25])
    assert 'extra_bridge_config:=/b.yaml' in p['stack'][0].cmd
    assert p['extra_models'] == ['dyn_box_1']
    m = p['late'][1]
    assert m.name == 'dynamic_mover_dyn_box_1' and 'start_delay_s:=1.2500' in m.cmd
    assert 'waypoints:="[0.0000, -1.6000, 0.0000, 1.6000]"' in m.cmd
    assert 'extra_models:=dyn_box_1' in re.eval_cmd('/r', p['extra_models'])
    assert 'extra_models' not in re.eval_cmd('/r')
    # static scenario worlds get no bridge
    q = plan(ns(method='scripted_goals'), {'scenario': SCEN['scenario']}, bridge_cfg='/b.yaml')
    assert 'extra_bridge' not in q['stack'][0].cmd


def test_responsiveness_plans():
    b = plan(ns(method='responsiveness', stack='bare'))
    assert [s.name for s in b['stack']] == ['sim'] and b['gates'] == []
    assert 'responsiveness_events.csv' in b['late'][0].cmd and not b['late'][0].critical
    l = plan(ns(method='responsiveness', stack='loaded'))
    assert 'start_manager:=false' in l['stack'][0].cmd and l['gates'][0] == 'G4_tf'


def test_meta_extras():
    e = re.meta_extras(ns(method='scripted_goals'), SCEN, SPAWN, 'scenario')
    assert e['localization_mode'] == 'amcl' and e['t_world_map'] == [0.0, 0.0, 0.0]
    assert e['nav_map'] == 'gt' and e['goal_list'] == 'scenario'
    assert e['dynamic_obstacles']['dyn_box_1']['size'] == [0.4, 0.4]
    e = re.meta_extras(ns(method='scripted_goals', nav_map='slam'), {}, SPAWN, 'fixed')
    assert e['t_world_map'] == list(SPAWN) and e['localization_mode'] == 'rtabmap'
    assert re.meta_extras(ns(method='responsiveness', stack='loaded'), {}, SPAWN)['stack'] == 'loaded'
    assert re.meta_extras(ns(), {}, SPAWN) == {}


def test_scenario_draws_deterministic_and_bounded():
    a = re.scenario_draws(7, [-2, 0, 0.0], 2)
    assert a == re.scenario_draws(7, [-2, 0, 0.0], 2)
    assert a != re.scenario_draws(8, [-2, 0, 0.0], 2)
    (x, y, yaw), d = a
    assert abs(x + 2) <= 0.10 and abs(y) <= 0.10 and abs(yaw) <= 0.2
    assert len(d) == 2 and all(0 <= v <= 2 for v in d)
    rng = np.random.default_rng(3007)
    assert abs(x - (-2 + rng.uniform(-0.1, 0.1))) < 1e-12


def test_goal_selection_and_yaml(tmp_path):
    ent = {'scenario': SCEN['scenario'], 'goal_lists': {'fixed': [[1, 2, 0.5], [3, 4]]}}
    assert re.select_goals('scenario', 1, ent, SPAWN) == [{'x': 2.0, 'y': 0.0, 'yaw': 0.0}]
    assert re.select_goals('fixed', 1, ent, SPAWN)[1] == {'x': 3.0, 'y': 4.0, 'yaw': 0.0}
    p = tmp_path / 'g.yaml'
    re.write_goals(str(p), re.select_goals('fixed', 1, ent, SPAWN))
    assert yaml.safe_load(open(p)) == [{'x': 1.0, 'y': 2.0, 'yaw': 0.5},
                                       {'x': 3.0, 'y': 4.0, 'yaw': 0.0}]


def test_generated_goals_deterministic(monkeypatch):
    calls = []

    def fake(gt, rng_seed, spawn_xy=None, fixed=None):
        calls.append((rng_seed, spawn_xy))
        return {'random20': [{'x': float(rng_seed), 'y': 0.0, 'yaw': 0.0}]}
    monkeypatch.setattr(re, 'generate_goal_lists', fake)
    g1 = re.select_goals('random20', 5, {}, SPAWN, gt=object())
    g2 = re.select_goals('random20', 5, {}, SPAWN, gt=object())
    assert g1 == g2 and calls[0] == (2005, (1.0, -2.0))


def test_export_gt_map_call(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(re.cm, 'gt_grid_for', lambda w, c: seen.setdefault('w', w) or 'GT')
    monkeypatch.setattr(re.gt_grid, 'export_nav2_map', lambda gt, prefix: (prefix + '.pgm', prefix + '.yaml'))
    out = re.export_gt_map('office', {}, str(tmp_path))
    assert seen['w'] == 'office' and out[1] == str(tmp_path / 'gt_map.yaml')


def test_initialpose_and_dirs():
    c = re.initialpose_cmd((1.0, 2.0, 0.0))
    assert '/initialpose' in c and 'x: 1.000000' in c and 'w: 1.000000' in c
    assert re.method_dir_name('frontier') == 'frontier'
    assert re.method_dir_name('scripted_goals', 'fixed', 'slam') == 'scripted_goals_fixed_slam'
    assert re.method_dir_name('responsiveness', stack='loaded') == 'responsiveness_loaded'
    v = run_batch.variants('scripted_goals', {'goal_lists': ['fixed', 'random20']})
    assert [d for d, _ in v] == ['scripted_goals_fixed', 'scripted_goals_random20']
    assert run_batch.variants('frontier', {}) == [('frontier', [])]


def test_localization_gt_plan_and_meta():
    a = ns(method='scripted_goals', localization='gt')
    names = [s.name for s in plan(a)['stack']]
    assert names == ['sim', 'nav2', 'map_server', 'gt_localization']
    assert 'nav2_localization' not in ' '.join(s.cmd for s in plan(a)['stack'])
    assert 'initialpose' not in plan(a)['gates']
    assert re.meta_extras(a, {}, SPAWN, 'g')['localization_mode'] == 'gt'
    assert re.meta_extras(ns(method='scripted_goals'), {}, SPAWN, 'g')['localization_mode'] == 'amcl'
    assert re.meta_extras(ns(method='scripted_goals', nav_map='slam', localization='slam'),
                          {}, SPAWN, 'g')['localization_mode'] == 'rtabmap'
