import numpy as np

from vacuum_eval.check_lc_direction import closure_errors, verdict
from vacuum_eval.metrics.common import Run
from vacuum_eval.metrics.loop_closure import expected_tf


def build(conv, n=3, poses=None):
    pb = [(1.0, 0.5, 0.3), (-0.8, 1.2, -0.6), (0.4, -0.9, 1.0)][:n]
    ids = {'t': [], 'ref_id': [], 'loop_closure_id': [], 'gt_x': [], 'gt_y': [], 'gt_yaw': [],
           'lc_tx': [], 'lc_ty': [], 'lc_tyaw': []}

    def add(t, r, l, p, tf=(np.nan,) * 3):
        for k, v in zip(ids, (t, r, l) + tuple(p) + tuple(tf)):
            ids[k].append(v)
    pa = (0.0, 0.0, 0.0, 0.0)
    for i, p in enumerate(pb):
        add(10.0 * (i + 1), i + 1, 0, p)
        # one ref node at origin per closure
    for i, p in enumerate(pb):
        rid = 100 + i
        add(500.0 + i, rid, i + 1, (0, 0, 0), expected_tf(pa, (0,) + p, conv))
    return Run(loop_events={k: np.array(v, float) for k, v in ids.items()},
               episode_start_t=0.0, episode_end_t=1000.0)


def test_ref_to_loop_winner():
    win, st = verdict(closure_errors(build('ref_to_loop')))
    assert win == 'ref_to_loop' and st['ref_to_loop'][2] == 3


def test_loop_to_ref_winner():
    win, _ = verdict(closure_errors(build('loop_to_ref')))
    assert win == 'loop_to_ref'


def test_ambiguous_identity_and_empty():
    # zero relative pose: both conventions agree -> ambiguous
    r = build('ref_to_loop')
    r.loop_events['gt_x'][:] = 0
    r.loop_events['gt_y'][:] = 0
    r.loop_events['gt_yaw'][:] = 0
    r.loop_events['lc_tx'][3:] = 0
    r.loop_events['lc_ty'][3:] = 0
    r.loop_events['lc_tyaw'][3:] = 0
    assert verdict(closure_errors(r))[0] is None
    assert verdict([])[0] is None


def test_help_exits_zero(capsys):
    import pytest
    from vacuum_eval.check_lc_direction import main
    with pytest.raises(SystemExit) as e:
        main(['--help'])
    assert e.value.code == 0
    assert 'usage' in capsys.readouterr().out.lower()
