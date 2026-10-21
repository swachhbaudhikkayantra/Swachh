"""Aggregate many summary.csv files (docs/specs/02 section 2.9).

python3 -m vacuum_eval.aggregate --root DIR --out aggregate.csv [--paired-by seed]
"""

import argparse
import csv
import glob
import math
import os
from collections import defaultdict

import numpy as np
from scipy import stats

GROUP_KEYS = ('world', 'method', 'odom_noise')
ID_COLS = set(GROUP_KEYS) | {'seed', 'status', 'notes', 'experiment', 'end_reason'}
RATE_PAIRS = [('nav_goals_succeeded', 'nav_goals_total'),
              ('trial_success', None),
              ('lc_n_true', 'lc_n_accepted'),
              ('resp_n_met', 'resp_n_events')]
OUT_COLS = ['kind', 'world', 'method', 'odom_noise', 'metric', 'n', 'mean', 'std',
            'median', 'min', 'max', 'ci95_halfwidth', 'cv', 'n_failed', 'pooled_pct',
            'wilson_lo_pct', 'wilson_hi_pct', 'method_b', 'test', 'p_value',
            'cliffs_delta', 'n_tests', 'delta']


def wilson_interval(k, n, z=1.96):
    """Wilson score interval for k successes of n; returns (lo, hi) as fractions."""
    if n <= 0:
        return (float('nan'), float('nan'))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def group_stats(values):
    """n, mean, std(ddof=1), median, min, max, ci95_halfwidth, cv of finite values."""
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    n = int(v.size)
    out = dict(n=n, mean=None, std=None, median=None, min=None, max=None,
               ci95_halfwidth=None, cv=None)
    if n == 0:
        return out
    out.update(mean=float(v.mean()), median=float(np.median(v)),
               min=float(v.min()), max=float(v.max()))
    if n >= 2:
        sd = float(v.std(ddof=1))
        out['std'] = sd
        out['ci95_halfwidth'] = float(stats.t.ppf(0.975, n - 1) * sd / math.sqrt(n))
        if out['mean'] != 0:
            out['cv'] = sd / abs(out['mean'])
    return out


def cliffs_delta(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.size == 0 or b.size == 0:
        return float('nan')
    gt = (a[:, None] > b[None, :]).sum()
    lt = (a[:, None] < b[None, :]).sum()
    return float((gt - lt) / (a.size * b.size))


def compare_methods(a, b, paired=False):
    """Wilcoxon signed-rank if paired with equal n>=6, else two-sided Mann-Whitney U."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    use_w = bool(paired) and a.size == b.size and a.size >= 6
    p = float('nan')
    try:
        if use_w:
            p = float(stats.wilcoxon(a, b).pvalue)
        elif a.size and b.size:
            p = float(stats.mannwhitneyu(a, b, alternative='two-sided').pvalue)
    except ValueError:
        pass
    return dict(test='wilcoxon' if use_w else 'mannwhitneyu', p_value=p,
                cliffs_delta=cliffs_delta(a, b))


def _num(x):
    try:
        return float(x) if x not in ('', None) else float('nan')
    except ValueError:
        return None


def load_summaries(root):
    rows = []
    for p in sorted(glob.glob(os.path.join(root, '**', 'summary.csv'), recursive=True)):
        with open(p, newline='') as f:
            for r in csv.DictReader(f):
                r['_path'] = p
                rows.append(r)
    return rows


def _numeric_keys(rows):
    keys = []
    for k in sorted({k for r in rows for k in r if k != '_path'}):
        if k in ID_COLS:
            continue
        vals = [_num(r.get(k)) for r in rows]
        if all(v is not None for v in vals) and any(np.isfinite(v) for v in vals):
            keys.append(k)
    return keys


def aggregate(rows, paired_by=None):
    """Return list of output dict rows."""
    out = []
    keys = _numeric_keys(rows)
    groups = defaultdict(list)
    for r in rows:
        groups[tuple(r.get(k, '') for k in GROUP_KEYS)].append(r)
    gstat = {}
    for gk in sorted(groups):
        allr = groups[gk]
        okr = [r for r in allr if r.get('status') in ('ok', 'partial')]
        n_failed = sum(1 for r in allr if r.get('status') == 'failed')
        base = dict(zip(GROUP_KEYS, gk))
        for k in keys:
            vals = [_num(r.get(k)) for r in okr]
            s = group_stats(vals)
            gstat[(gk, k)] = (s, okr)
            out.append(dict(kind='stat', metric=k, n_failed=n_failed, **base, **s))
        for succ, tot in RATE_PAIRS:
            ks = 0.0
            kn = 0.0
            for r in okr:
                sv = _num(r.get(succ))
                if sv is None or not np.isfinite(sv):
                    continue
                tv = 1.0 if tot is None else _num(r.get(tot))
                if tv is None or not np.isfinite(tv):
                    continue
                ks += sv
                kn += tv
            if kn > 0:
                lo, hi = wilson_interval(ks, kn)
                out.append(dict(kind='pooled', metric=succ, n_failed=n_failed,
                                n=int(kn), pooled_pct=100 * ks / kn,
                                wilson_lo_pct=100 * lo, wilson_hi_pct=100 * hi, **base))
    # method comparison: same world and odom_noise
    ntests = 0
    comps = []
    wn = defaultdict(list)
    for gk in sorted(groups):
        wn[(gk[0], gk[2])].append(gk[1])
    for (w, nz), methods in sorted(wn.items()):
        for i in range(len(methods)):
            for j in range(i + 1, len(methods)):
                ma, mb = methods[i], methods[j]
                for k in keys:
                    _, ra = gstat[((w, ma, nz), k)]
                    _, rb = gstat[((w, mb, nz), k)]
                    if paired_by:
                        da = {r.get(paired_by): _num(r.get(k)) for r in ra}
                        db = {r.get(paired_by): _num(r.get(k)) for r in rb}
                        common = sorted(set(da) & set(db))
                        a = np.array([da[c] for c in common])
                        b = np.array([db[c] for c in common])
                        m = np.isfinite(a) & np.isfinite(b)
                        a, b, paired = a[m], b[m], True
                    else:
                        a = np.array([_num(r.get(k)) for r in ra])
                        b = np.array([_num(r.get(k)) for r in rb])
                        a, b, paired = a[np.isfinite(a)], b[np.isfinite(b)], False
                    if a.size == 0 or b.size == 0:
                        continue
                    c = compare_methods(a, b, paired)
                    ntests += 1
                    comps.append(dict(kind='compare', world=w, method=ma, method_b=mb,
                                      odom_noise=nz, metric=k, n=int(min(a.size, b.size)),
                                      **c))
    for c in comps:
        c['n_tests'] = ntests
    out.extend(comps)
    # noise delta
    for (w, m) in sorted({(g[0], g[1]) for g in groups}):
        for k in keys:
            s0 = gstat.get(((w, m, '0'), k))
            s1 = gstat.get(((w, m, '1'), k))
            if s0 and s1 and s0[0]['mean'] is not None and s1[0]['mean'] is not None:
                out.append(dict(kind='noise_delta', world=w, method=m, metric='delta_' + k,
                                delta=s1[0]['mean'] - s0[0]['mean']))
    return out


def write_aggregate(path, out_rows):
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLS, restval='', extrasaction='ignore')
        w.writeheader()
        for r in out_rows:
            w.writerow({k: ('' if v is None else v) for k, v in r.items()})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--out', default='aggregate.csv')
    ap.add_argument('--paired-by', default=None)
    a = ap.parse_args(argv)
    rows = load_summaries(os.path.expanduser(a.root))
    write_aggregate(a.out, aggregate(rows, a.paired_by))
    print(f'{len(rows)} summaries -> {a.out}')


if __name__ == '__main__':
    main()
