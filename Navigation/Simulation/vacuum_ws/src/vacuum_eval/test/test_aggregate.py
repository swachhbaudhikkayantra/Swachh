import csv

import numpy as np
from scipy import stats

from vacuum_eval import aggregate as ag


def test_T027_wilson():
    lo, hi = ag.wilson_interval(8, 10)
    assert abs(lo - 0.490) < 0.002 and abs(hi - 0.943) < 0.002


def test_T027_stats_and_cli(tmp_path):
    vals = [10.0, 12.5, 11.0]
    for i, v in enumerate(vals):
        d = tmp_path / 'w' / 'frontier' / f'seed_{i:03d}'
        d.mkdir(parents=True)
        with open(d / 'summary.csv', 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['world', 'method', 'odom_noise', 'seed', 'status', 'x',
                        'nav_goals_succeeded', 'nav_goals_total'])
            w.writerow(['w', 'frontier', 0, i, 'ok', v, 4, 5])
    out = tmp_path / 'agg.csv'
    ag.main(['--root', str(tmp_path), '--out', str(out)])
    rows = list(csv.DictReader(open(out)))
    r = [x for x in rows if x['kind'] == 'stat' and x['metric'] == 'x'][0]
    a = np.array(vals)
    assert int(r['n']) == 3
    assert np.isclose(float(r['mean']), a.mean())
    assert np.isclose(float(r['std']), a.std(ddof=1))
    ci = stats.t.ppf(0.975, 2) * a.std(ddof=1) / np.sqrt(3)
    assert np.isclose(float(r['ci95_halfwidth']), ci)
    p = [x for x in rows if x['kind'] == 'pooled' and x['metric'] == 'nav_goals_succeeded'][0]
    assert np.isclose(float(p['pooled_pct']), 80.0)
    g = ag.group_stats(vals)
    assert np.isclose(g['mean'], a.mean())


def test_compare_and_noise():
    a = np.arange(1.0, 9.0)
    c = ag.compare_methods(a, a + 5 + np.arange(8) * 0.1, paired=True)
    assert c['test'] == 'wilcoxon' and c['cliffs_delta'] < -0.8
    assert ag.compare_methods(a[:4], a[:4] + 1, paired=True)['test'] == 'mannwhitneyu'
    rows = [dict(world='w', method='m', odom_noise=str(n), seed=str(s), status='ok',
                 x=str(n * 2 + s)) for n in (0, 1) for s in range(3)]
    out = ag.aggregate(rows)
    d = [r for r in out if r['kind'] == 'noise_delta'][0]
    assert d['delta'] == 2.0
