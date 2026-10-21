import json
import math

import numpy as np
import pytest
import yaml

from vacuum_eval import compute_metrics as cm
from vacuum_eval.metrics.common import load_run, write_csv

ALWAYS = ['experiment', 'world', 'method', 'seed', 'odom_noise', 'spawn_x', 'spawn_y',
          'spawn_yaw', 'status', 'end_reason', 'episode_sim_sec', 'bringup_sim_sec',
          'wall_elapsed_sec', 'n_cmd_ticks', 'n_goals', 'distance_gt_m', 'notes']
TRAJ_COLS = ['t', 't_rel', 'gt_x', 'gt_y', 'gt_yaw', 'gt_vx', 'gt_wz', 'est_ok']


def make_run(d, motion_t=40.0, dur=100.0, gt_fn=None, events=(), timeout=1200):
    d.mkdir(exist_ok=True)
    meta = dict(experiment='syn', world='w', method='frontier', seed=1, spawn_x=0.0,
                spawn_y=0.0, spawn_yaw=0.0, odom_noise=False, episode_timeout_sim_sec=timeout,
                config_snapshot={}, swath_width_m=0.25)
    (d / 'run_meta.yaml').write_text(yaml.safe_dump(meta))
    gt_fn = gt_fn or (lambda t: (0.1 * max(t - motion_t, 0.0), 0.0))
    ts = np.arange(0.0, dur, 0.1)
    rows = [[t, t, *gt_fn(t), 0.0, 0.0, 0.0, 1] for t in ts]
    write_csv(str(d / 'trajectory.csv'), TRAJ_COLS, rows)
    cmd = []
    for t in np.arange(0.0, dur, 0.1):
        v = 0.1 if (motion_t is not None and t >= motion_t) else 0.0
        cmd.append([t, t, 'ctrl_stamped', v, 0.0, 0.0])
    write_csv(str(d / 'cmd_vel.csv'), ['t', 't_rel', 'source', 'vx', 'vy', 'wz'], cmd)
    write_csv(str(d / 'events.csv'), ['t', 't_rel', 'event', 'detail'],
              [[t, t, e, ''] for t, e in events])
    return d


def test_episode_start_and_counters(tmp_path):
    d = make_run(tmp_path / 'r', motion_t=40.0, dur=100.0)
    run = load_run(str(d))
    info = cm.determine_episode(run)
    assert run.episode_start_t == pytest.approx(40.0, abs=0.1)
    assert info['end_reason'] == 'crash'   # trajectory ended with no end signal
    out = cm.compute(str(d), only=['counters'])
    assert out['n_cmd_ticks'] > 500
    assert out['distance_gt_m'] == pytest.approx(5.9, abs=0.2)


def test_no_motion(tmp_path):
    d = make_run(tmp_path / "r", motion_t=None, gt_fn=lambda t: (0.0, 0.0))
    out = cm.compute(str(d), only=['counters'])
    assert out['end_reason'] == 'no_motion' and out['status'] == 'failed'


def test_finished_signal(tmp_path):
    d = make_run(tmp_path / 'r', events=[(80.0, 'finished_signal')])
    out = cm.compute(str(d), only=['counters'])
    assert out['end_reason'] == 'finished'
    assert out['episode_sim_sec'] == pytest.approx(40.0, abs=0.2)
    assert out['bringup_sim_sec'] == pytest.approx(40.0, abs=0.2)


def test_timeout(tmp_path):
    d = make_run(tmp_path / 'r', dur=200.0, timeout=60)
    out = cm.compute(str(d), only=['counters'])
    assert out['end_reason'] == 'timeout'
    assert out['episode_sim_sec'] == pytest.approx(60.0, abs=0.2)


def test_stuck_static(tmp_path):
    d = make_run(tmp_path / 'r', motion_t=10.0, dur=400.0, gt_fn=lambda t: (0.0, 0.0))
    out = cm.compute(str(d), only=['counters'])
    assert out['end_reason'] == 'stuck'
    assert out['episode_sim_sec'] == pytest.approx(180.0, abs=2.0)


def test_stuck_spinning(tmp_path):
    d = make_run(tmp_path / 'r', motion_t=10.0, dur=400.0, gt_fn=lambda t: (0.0, 0.0))
    tr = load_run(str(d)).trajectory
    wz = np.full(len(tr['t']), 1.0)       # 180 rad over the window >> 2 pi
    rows = [[t, t, 0.0, 0.0, 0.0, 0.0, w, 1] for t, w in zip(tr['t'], wz)]
    write_csv(str(d / 'trajectory.csv'), TRAJ_COLS, rows)
    assert cm.compute(str(d), only=['counters'])['end_reason'] == 'stuck'


def test_not_stuck_when_moving(tmp_path):
    # 0.5 m in 180 s window, slow drift: should not trigger
    d = make_run(tmp_path / 'r', motion_t=10.0, dur=250.0,
                 gt_fn=lambda t: (0.5 * min(max(t - 10, 0) / 100.0, 1.0) + 0.002 * t, 0.0))
    # moves 0.5 m in first 100 s then still; window starting at t>=110 would be static but only
    # 140 s remain -> never a full 180 s static window
    assert cm.compute(str(d), only=['counters'])['end_reason'] != 'stuck'


def test_summary_files_and_always_keys(tmp_path, monkeypatch):
    d = make_run(tmp_path / 'r', events=[(80.0, 'finished_signal')])
    out = cm.compute(str(d), worlds_cfg={}, gt_dir=str(tmp_path / 'nogt'))
    cm.write_summary(str(d), out)
    s = json.load(open(d / 'summary.json'))
    for k in ALWAYS:
        assert k in s
    assert (d / 'summary.csv').exists()
    # no GT grid available -> coverage/navigation/safety fail -> partial with notes
    assert s['status'] == 'partial'
    assert any(n.startswith('coverage:') for n in s['notes'])


def test_injected_module_failure(tmp_path, monkeypatch):
    d = make_run(tmp_path / 'r', events=[(80.0, 'finished_signal')])

    def boom(ctx):
        raise ValueError('injected')
    monkeypatch.setitem(cm.MODULES, 'trajectory', boom)
    out = cm.compute(str(d), only=['trajectory', 'counters'])
    assert out['status'] == 'partial'
    assert any('trajectory: injected' in n for n in out['notes'])
    assert out['rpe_odom_trans_rmse_m_1m'] is None
    assert out['n_cmd_ticks'] is not None
