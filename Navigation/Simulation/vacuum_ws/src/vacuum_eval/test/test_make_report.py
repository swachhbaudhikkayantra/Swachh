import csv
import os

from vacuum_eval import make_report as mr


def _mk(root, world, seed, noise, status, ate, curve=True):
    d = os.path.join(root, world, 'n%s_s%d' % (noise, seed))
    os.makedirs(d)
    row = dict(world=world, method='m', odom_noise=noise, seed=seed, status=status,
               ate_fixed_rmse_m=ate, coverage_explored_pct=50 + seed, n_collisions=seed,
               nav_goals_succeeded=3, nav_goals_total=4)
    with open(os.path.join(d, 'summary.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        w.writeheader()
        w.writerow(row)
    if curve:
        with open(os.path.join(d, 'coverage_curve.csv'), 'w', newline='') as f:
            f.write('t_ep,coverage_explored_pct,coverage_cleaned_pct\n0,0,0\n100,%d,1\n200,%d,2\n' % (20 + seed, 40 + seed))


def test_report(tmp_path):
    root = str(tmp_path / 'exp')
    for w in ('w1', 'w2'):
        for nz in ('0', '1'):
            for s in range(4):
                _mk(root, w, s, nz, 'ok', 0.05 + 0.01 * s + 0.02 * int(nz))
    _mk(root, 'w1', 9, '0', 'invalid', 9.0)
    _mk(root, 'w2', 9, '0', 'failed', 9.0)
    out = str(tmp_path / 'out')
    figs = mr.build_report([root], out)
    assert os.path.isfile(os.path.join(root, 'aggregate.csv'))
    md = open(os.path.join(out, 'results.md')).read()
    assert 'ate_fixed_rmse_m' in md and 'pooled' in md
    assert 'Reported regardless of outcome' in md
    assert 'failed=1, invalid=1, ok=16' in md
    assert 'INSUFFICIENT DATA' in md  # e.g. lc metrics absent
    assert 'delta_ate_fixed_rmse_m' in md
    names = {os.path.basename(f) for f in figs}
    assert {'coverage_vs_time.png', 'ate_box.png', 'nav_success.png', 'collisions.png'} <= names
    st = open(os.path.join(out, 'metrics_status_update.md')).read()
    assert '| 6 | ATE (fixed frame) | `ate_fixed_rmse_m` | yes |' in st
    assert '`lc_precision_pct` | no |' in st


def test_empty_root(tmp_path):
    root = str(tmp_path / 'e')
    os.makedirs(root)
    mr.build_report([root], str(tmp_path / 'o'))
    assert 'nothing has been run' in open(str(tmp_path / 'o' / 'results.md')).read()
