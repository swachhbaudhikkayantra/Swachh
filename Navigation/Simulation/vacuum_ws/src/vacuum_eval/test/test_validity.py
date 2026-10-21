import numpy as np

from vacuum_eval.metrics.common import load_run
from vacuum_eval.metrics.validity import compute_validity


def _write(d, dur, depth_hz=30, info_stamps=None):
    (d / 'run_meta.yaml').write_text('config_snapshot: {a: 1}\n')
    with open(d / 'rates.csv', 'w') as f:
        f.write('t,t_rel,n_odom,n_depth,n_color\n')
        for i in range(dur):
            f.write('%d,%d,50,%d,%d\n' % (i, i, depth_hz, depth_hz))
    with open(d / 'loop_events.csv', 'w') as f:
        f.write('t,t_rel,ref_id\n')
        for t in (info_stamps if info_stamps is not None else range(dur)):
            f.write('%s,%s,1\n' % (t, t))
    (d / 'rtf.csv').write_text('t,t_rel,wall_dt,sim_dt,rtf\n1,1,1,0.5,0.5\n2,2,1,0.7,0.7\n')
    run = load_run(str(d))
    run.episode_start_t, run.episode_end_t = 0.0, float(dur)
    return run


def test_valid(tmp_path):
    v = compute_validity(_write(tmp_path, 100))
    assert v['episode_valid'] and v['invalid_reasons'] == []
    assert v['img_drop_pct'] < 1 and v['rtabmap_updates'] >= 50
    assert abs(v['rtf_true_mean'] - 0.6) < 1e-9 and len(v['config_hash']) == 12


def test_image_drop(tmp_path):
    v = compute_validity(_write(tmp_path, 100, depth_hz=10))
    assert not v['episode_valid']
    assert any('img_drop' in r for r in v['invalid_reasons'])


def test_rtabmap_stall(tmp_path):
    v = compute_validity(_write(tmp_path, 100, info_stamps=range(0, 20)))
    assert not v['episode_valid']
    assert v['rtabmap_max_gap_s'] == 1.0 or v['rtabmap_updates'] == 20
    assert any('rtabmap_updates' in r for r in v['invalid_reasons'])
    v = compute_validity(_write(tmp_path, 100, info_stamps=[]))
    assert v['rtabmap_max_gap_s'] == 100.0
    assert any('rtabmap_max_gap' in r for r in v['invalid_reasons'])


def test_drop_clamped_and_mean_rate(tmp_path):
    v = compute_validity(_write(tmp_path, 100, depth_hz=31))
    assert v['img_drop_pct'] == 0.0
    assert abs(v['img_depth_rate_hz_mean'] - 31.0) < 1e-9
