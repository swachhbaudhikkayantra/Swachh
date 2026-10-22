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


def test_holm_hand():
    # p = .01,.04,.03,.005 ; sorted .005,.01,.03,.04 -> *4,*3,*2,*1 = .02,.03,.06,.04 -> mono .02,.03,.06,.06
    adj = ag.holm_adjust([0.01, 0.04, 0.03, 0.005])
    assert np.allclose(adj, [0.03, 0.06, 0.06, 0.02])


def test_cluster_bootstrap_coverage():
    rng = np.random.default_rng(0)
    m, truth, cover, reps = 8, 0.6, 0, 200
    for r in range(reps):
        # beta-distributed per-episode p (ICC ~ 1/(a+b+1)=0.1), mean 0.6
        pe = rng.beta(5.4, 3.6, size=30)
        s = rng.binomial(m, pe).astype(float)
        lo, hi = ag.cluster_bootstrap_ci(s, np.full(30, m), B=500, seed=r)
        cover += lo <= 100 * truth <= hi
    assert 0.88 <= cover / reps <= 0.99


def test_invalid_excluded_and_keys():
    rows = [dict(world='w', method='m', odom_noise='0', seed=str(i), status=st,
                 x=str(v), nav_goals_succeeded=str(s), nav_goals_total='4')
            for i, (st, v, s) in enumerate([('ok', 1, 4), ('ok', 3, 2), ('ok', 2, 3),
                                            ('invalid', 99, 0), ('failed', 99, 0)])]
    out = ag.aggregate(rows, B=200)
    st = [r for r in out if r['kind'] == 'stat' and r['metric'] == 'x'][0]
    assert st['n'] == 3 and st['n_invalid'] == 1 and st['n_failed'] == 1
    assert st['boot_ci_lo'] <= st['mean'] <= st['boot_ci_hi']
    p = [r for r in out if r['kind'] == 'pooled'][0]
    assert np.isclose(p['pooled_pct'], 75.0) and 'cluster_ci_lo' in p
    assert 'ignores clustering' in p['wilson_note']


def _mk(tmp_path, name, gpu, lean, meta=False, method='frontier'):
    d = tmp_path / name
    d.mkdir(parents=True)
    hdr = ['world', 'method', 'odom_noise', 'seed', 'status', 'x']
    row = ['w', method, 0, 0, 'ok', 5.0]
    if gpu is not None and not meta:
        hdr += ['gpu', 'lean']
        row += [gpu, lean]
    with open(d / 'summary.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(hdr)
        w.writerow(row)
        row[3] = 1
        row[5] = 6.0
        w.writerow(row)
    if meta:
        (d / 'run_meta.yaml').write_text(f'gpu: {gpu}\nlean: {lean}\n')


def test_gpu_lean_not_pooled(tmp_path):
    _mk(tmp_path, 'a', None, None)
    _mk(tmp_path, 'b', 1, 0, meta=True)
    _mk(tmp_path, 'c', 0, 1)
    out = tmp_path / 'agg.csv'
    ag.main(['--root', str(tmp_path), '--out', str(out)])
    rows = [r for r in csv.DictReader(open(out)) if r['kind'] == 'stat' and r['metric'] == 'x']
    assert sorted((r['gpu'], r['lean'], r['n']) for r in rows) == [
        ('0', '0', '2'), ('0', '1', '2'), ('1', '0', '2')]


def test_compare_only_equal_gpu_lean(tmp_path):
    _mk(tmp_path, 'a', 0, 0, method='m1')
    _mk(tmp_path, 'b', 1, 0, method='m2')
    _mk(tmp_path, 'c', 0, 0, method='m2')
    rows = ag.aggregate(ag.load_summaries(str(tmp_path)), B=50)
    comps = [r for r in rows if r['kind'] == 'compare']
    assert len(comps) == 1 and comps[0]['gpu'] == '0' and comps[0]['lean'] == '0'
