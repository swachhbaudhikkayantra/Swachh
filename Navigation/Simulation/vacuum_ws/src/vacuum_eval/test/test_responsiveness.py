import math

import numpy as np

from vacuum_eval.metrics.common import Run
from vacuum_eval.metrics.responsiveness import (compute_responsiveness_metrics,
                                                obstacle_events, topic_rate_health,
                                                DEFAULT_DEADLINES)


def step_run(rows):
    """rows: (event, t_a, t_b or nan)."""
    ev = np.array([r[0] for r in rows], dtype=object)
    ta = np.array([r[1] for r in rows], float)
    tb = np.array([r[2] for r in rows], float)
    return Run(responsiveness_events={'event': ev, 't_a': ta, 't_b': tb, 'latency_s': tb - ta},
               meta={'stack': 'bare'})


def test_t070_latency_met_and_goal_motion():
    r = step_run([('cmd_motion', 10.0, 10.3)])
    t = np.arange(0, 20, 0.1)
    vx = np.where(t >= 5.3, 0.2, 0.0)
    r.trajectory = {'t': t, 'gt_vx': vx, 'gt_wz': np.zeros_like(t)}
    r.goal_events = {'t': np.array([5.0]), 'src': np.array(['explore'], dtype=object),
                     'event': np.array(['started'], dtype=object)}
    m = compute_responsiveness_metrics(r)
    assert abs(m['lat_cmd_motion_ms_mean'] - 300) < 1e-6
    assert m['resp_cmd_pct'] == 100.0
    assert abs(m['lat_goal_motion_ms_mean'] - 300) < 1e-6 and m['resp_goal_pct'] == 100.0
    assert m['resp_n_events'] == 2 and m['responsiveness_pct'] == 100.0
    assert m['resp_stack'] == 'bare'


def test_t071_missing_and_late():
    r = step_run([('cmd_motion', 10.0, 10.3), ('stop', 20.0, np.nan),
                  ('cmd_motion', 30.0, 30.8), ('stop', 40.0, 42.0)])
    m = compute_responsiveness_metrics(r)
    assert m['resp_n_events'] == 4 and m['resp_n_met'] == 1
    assert m['responsiveness_pct'] == 25.0 and m['resp_stop_pct'] == 0.0
    assert abs(m['lat_cmd_motion_ms_mean'] - 550) < 1e-6   # missed one excluded (>1.5 s only)
    assert m['lat_stop_ms_mean'] is None                   # 2.0 s > 3x deadline -> null
    assert m['lat_obstacle_ms_mean'] is None and m['resp_obstacle_pct'] is None
    # deadline override
    m2 = compute_responsiveness_metrics(r, deadlines={'cmd_motion': 1.0})
    assert m2['resp_n_met'] == 2


def obstacle_run(obs_xy, vx_after=0.0):
    t = np.arange(0, 10, 0.1)
    n = len(t)
    tr = {'t': t, 'gt_x': np.zeros(n), 'gt_y': np.zeros(n), 'gt_yaw': np.zeros(n),
          'gt_vx': np.full(n, 0.3), 'gt_wz': np.zeros(n)}
    do = {'t': t, 'name': np.array(['dyn_box_1'] * n, dtype=object),
          'x': np.full(n, obs_xy[0]), 'y': np.full(n, obs_xy[1]), 'yaw': np.zeros(n)}
    cvx = np.where(t < 5.0, 0.3, vx_after)
    cv = {'t': t, 'source': np.array(['smoothed'] * n, dtype=object), 'vx': cvx,
          'vy': np.zeros(n), 'wz': np.zeros(n)}
    return Run(trajectory=tr, dyn_obstacles=do, cmd_vel=cv, episode_start_t=0.0,
               episode_end_t=10.0)


def test_t072_t_a_rule_fov():
    ahead = obstacle_run((1.4 + 0.2 + 0.15, 0.0))     # centre 1.75 -> clearance ~1.4 m, in FOV
    ev = obstacle_events(ahead, DEFAULT_DEADLINES)
    assert len(ev) == 1 and abs(ev[0]['t_a'] - 1.0) < 1e-6   # needs 1.0 s of motion history
    behind = obstacle_run((-1.75, 0.0))
    assert obstacle_events(behind, DEFAULT_DEADLINES) == []
    m = compute_responsiveness_metrics(ahead)
    assert m['resp_n_events'] == 1


def test_obstacle_response_latency():
    r = obstacle_run((1.75, 0.0))
    # t_a = 1.0 but the robot only slows at 5.0 -> latency 4.0 s > 3 s -> missed
    ev = obstacle_events(r, DEFAULT_DEADLINES)[0]
    assert ev['latency_s'] is None and not ev['met']
    # robot already reacts: cmd drops at 1.5
    t = r.cmd_vel['t']
    r.cmd_vel['vx'] = np.where((t < 1.45), 0.3, 0.0)
    ev = obstacle_events(r, DEFAULT_DEADLINES)[0]
    assert ev['met'] and 0.4 < ev['latency_s'] <= 0.6


def test_t075_rate_floor_gap():
    n = 30
    t = np.arange(1, n + 1, dtype=float)
    z = np.full(n, 30.0)
    odom = z.copy()
    odom[10:13] = 0
    rates = {'t': t, 'n_odom': odom, 'n_depth': z, 'n_color': z, 'n_cmd_nav': np.zeros(n),
             'n_cmd_smoothed': np.zeros(n), 'n_tf_map_odom': np.ones(n), 'n_scan': z}
    r = Run(rates=rates, episode_start_t=0.0, episode_end_t=100.0)
    pct, flags = topic_rate_health(r)
    assert flags['odom'].sum() == 3
    assert abs(pct['odom'] - 90.0) < 1e-9
    assert pct['cmd_nav'] is None          # no active goal -> not evaluated
    m = compute_responsiveness_metrics(r)
    assert m['topic_ok_pct_min'] == 90.0 and m['resp_stack'] == 'episode'
    # with an active goal the zero cmd rates fail
    r.goal_events = {'t': np.array([5.0, 15.0]), 'src': np.array(['explore'] * 2, dtype=object),
                     'event': np.array(['started', 'ended'], dtype=object)}
    pct, flags = topic_rate_health(r)
    assert pct['cmd_nav'] == 0.0 and flags['cmd_nav'].sum() > 0


def test_wall_clock_latency_primary():
    ev = np.array(['cmd_motion', 'stop'], dtype=object)
    r = Run(responsiveness_events={
        'event': ev, 't_a': np.array([10.0, 20.0]), 't_b': np.array([10.1, 20.1]),
        'latency_s': np.array([0.1, 0.1]), 'wall_latency_s': np.array([0.3, 0.2])},
        meta={'stack': 'bare'})
    m = compute_responsiveness_metrics(r)
    assert m['resp_definition'] == 'wall_clock_controller_latency'
    assert abs(m['lat_cmd_motion_ms_mean'] - 300) < 1e-6
    assert abs(m['lat_stop_ms_p95'] - 200) < 1e-6
    assert abs(m['lat_cmd_motion_ms_mean_sim'] - 100) < 1e-6
    assert 'wall-clock stamps missing' not in m['notes']
    r.responsiveness_events['wall_latency_s'] = np.array([0.7, 0.2])   # > 0.5 s deadline
    assert compute_responsiveness_metrics(r)['resp_cmd_pct'] == 0.0


def test_wall_clock_fallback_note():
    m = compute_responsiveness_metrics(step_run([('cmd_motion', 10.0, 10.3)]))
    assert abs(m['lat_cmd_motion_ms_mean'] - 300) < 1e-6
    assert abs(m['lat_cmd_motion_ms_mean_sim'] - 300) < 1e-6
    assert 'wall-clock stamps missing' in m['notes']
    assert m['resp_definition'] == 'wall_clock_controller_latency'
