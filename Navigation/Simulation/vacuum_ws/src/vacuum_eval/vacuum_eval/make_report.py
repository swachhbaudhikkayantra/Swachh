"""Final-results report (requirement R9, pre-registration 13.1/13.5/13.5b).

python3 -m vacuum_eval.make_report --root ~/eval_runs/<exp> [--root ...] --out DIR

Writes results.md, figures/*.png and metrics_status_update.md.
Uses aggregate.csv per root (built with vacuum_eval.aggregate if missing).
"""
import argparse
import csv
import glob
import os
from collections import defaultdict

import numpy as np

from vacuum_eval import aggregate as agg
from vacuum_eval.metrics import health as hl

PALETTE = ['#0072B2', '#E69F00', '#009E73', '#D55E00', '#CC79A7', '#56B4E9', '#F0E442']
MIN_N = 3   # fewer valid episodes than this -> "insufficient data"

# (row#, name, summary key, unit, pooled-rate key or None)
CORE = [
    (1, 'Coverage (explored)', 'coverage_explored_pct', '%', None),
    (1, 'Coverage (cleaned, secondary)', 'coverage_cleaned_pct', '%', None),
    (2, 'Steps: goals', 'n_goals', 'count', None),
    (2, 'Steps: command ticks', 'n_cmd_ticks', 'count', None),
    (2, 'Steps: recoveries', 'n_recoveries', 'count', None),
    (3, 'Total collisions', 'n_collisions', 'count', None),
    (4, 'Obstacle avoidance', 'avoidance_pct', '%', None),
    (5, 'Responsiveness', 'responsiveness_pct', '%', 'resp_n_met'),
    (6, 'ATE (fixed frame)', 'ate_fixed_rmse_m', 'm', None),
    (7, 'RPE (1 m)', 'rpe_trans_rmse_m_1m', 'm', None),
    (8, 'Map completeness', 'map_completeness_pct', '%', None),
    (9, 'Avoidance trial success', 'avoid_trial_success_pct', '%', 'trial_success'),
    (10, 'Navigation success (GT)', 'nav_success_gt_pct', '%', 'nav_goals_succeeded'),
    (11, 'Loop closure precision', 'lc_precision_pct', '%', 'lc_n_true'),
    (11, 'Loop closure recall', 'lc_recall_pct', '%', None),
    (12, 'Path length ratio', 'path_length_ratio_mean', '-', None),
    (14, 'Cleaning efficiency (secondary)', 'cleaning_efficiency', '-', None),
]
EXTRAS = [
    ('A1', 'Time to 50 % explored', 't_to_50_explored_s', 's'),
    ('A1', 'Explored AUC', 'coverage_explored_auc', '%'),
    ('A2', 'Overlap ratio', 'overlap_ratio', '-'),
    ('A3', 'Missed area', 'missed_area_m2', 'm2'),
    ('A4', 'Distance (GT)', 'distance_gt_m', 'm'),
    ('A4', 'Energy proxy', 'energy_proxy_m2ps', 'm2/s'),
    ('A5', 'Min clearance', 'min_clearance_m', 'm'),
    ('A8', 'Planning latency', 'plan_latency_ms_mean', 'ms'),
    ('A9', 'Path smoothness', 'smooth_curvature_rms_1pm', '1/m'),
    ('A10', 'Odometry drift ratio', 'odom_drift_ratio', '-'),
    ('A12', 'True RTF', 'rtf_true_mean', '-'),
    ('A14', 'AMCL localization error', 'loc_error_mean_m', 'm'),
]


# ---------------------------------------------------------------- loading
def _f(x):
    try:
        v = float(x)
        return v if np.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _read_csv(p):
    with open(p, newline='') as f:
        return list(csv.DictReader(f))


def load_root(root):
    """Return (aggregate rows, summary rows) for one experiment root."""
    root = os.path.expanduser(root)
    exp = os.path.basename(os.path.normpath(root))
    summ = agg.load_summaries(root)
    ap = os.path.join(root, 'aggregate.csv')
    if os.path.isfile(ap):
        rows = _read_csv(ap)
    else:
        rows = agg.aggregate(summ)
        try:
            agg.write_aggregate(ap, rows)
        except OSError:
            pass
        rows = [{k: ('' if v is None else v) for k, v in r.items()} for r in rows]
    for r in rows:
        r['experiment'] = exp
    for r in summ:
        r['experiment'] = exp
        r['_root'] = root
    return rows, summ


def _fmt(v, nd=3):
    v = _f(v)
    return '-' if v is None else ('%.*f' % (nd, v))


def _nd(unit):
    return 1 if unit in ('%', 's', 'ms', 'count') else 3


# ---------------------------------------------------------------- stats
def pooled_cluster_ci(srows, key, B=2000, seed=12345):
    """Mean over worlds-of-seeds with cluster bootstrap: resample worlds, then seeds in world."""
    byw = defaultdict(list)
    for r in srows:
        if r.get('status') in ('ok', 'partial'):
            v = _f(r.get(key))
            if v is not None:
                byw[r.get('world', '')].append(v)
    if not byw:
        return None
    worlds = sorted(byw)
    allv = np.concatenate([byw[w] for w in worlds])
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(B):
        ws = rng.choice(len(worlds), len(worlds))
        vals = []
        for i in ws:
            a = np.asarray(byw[worlds[i]])
            vals.append(a[rng.integers(0, len(a), len(a))])
        means.append(np.concatenate(vals).mean())
    lo, hi = np.percentile(means, [2.5, 97.5])
    return dict(mean=float(allv.mean()), std=float(allv.std(ddof=1)) if allv.size > 1 else float('nan'),
                lo=float(lo), hi=float(hi), n=int(allv.size), nworlds=len(worlds))


def counts(summ):
    """status counts per (experiment, world, odom_noise)."""
    c = defaultdict(lambda: defaultdict(int))
    for r in summ:
        c[(r.get('experiment', ''), r.get('world', ''), r.get('odom_noise', ''))][r.get('status', '')] += 1
    return c


# ---------------------------------------------------------------- tables
def metric_table(key, unit, arows, summ):
    stats = [r for r in arows if r.get('kind') == 'stat' and r.get('metric') == key]
    if not stats:
        return None
    nd = _nd(unit)
    L = ['| experiment | world | noise | method | n | mean ± sd | 95 % boot CI | n_invalid | n_failed | note |',
         '|---|---|---|---|---|---|---|---|---|---|']
    for r in sorted(stats, key=lambda r: (r['experiment'], r['world'], r.get('odom_noise', ''), r.get('method', ''))):
        n = int(_f(r.get('n')) or 0)
        note = 'INSUFFICIENT DATA (n<%d)' % MIN_N if n < MIN_N else ''
        if n == 0:
            L.append('| %s | %s | %s | %s | 0 | - | - | %s | %s | NO DATA |' % (
                r['experiment'], r['world'], r.get('odom_noise', ''), r.get('method', ''),
                r.get('n_invalid', ''), r.get('n_failed', '')))
            continue
        L.append('| %s | %s | %s | %s | %d | %s ± %s | [%s, %s] | %s | %s | %s |' % (
            r['experiment'], r['world'], r.get('odom_noise', ''), r.get('method', ''), n,
            _fmt(r.get('mean'), nd), _fmt(r.get('std'), nd), _fmt(r.get('boot_ci_lo'), nd),
            _fmt(r.get('boot_ci_hi'), nd), r.get('n_invalid', ''), r.get('n_failed', ''), note))
    # pooled over worlds, per experiment/noise/method (cluster bootstrap)
    groups = defaultdict(list)
    for s in summ:
        groups[(s['experiment'], s.get('odom_noise', ''), s.get('method', ''))].append(s)
    for (e, nz, m), rs in sorted(groups.items()):
        p = pooled_cluster_ci(rs, key)
        if p is None:
            continue
        note = '' if p['n'] >= MIN_N else 'INSUFFICIENT DATA (n<%d)' % MIN_N
        L.append('| %s | **pooled** (%d worlds) | %s | %s | %d | %s ± %s | [%s, %s] cluster | | | %s |' % (
            e, p['nworlds'], nz, m, p['n'], _fmt(p['mean'], nd), _fmt(p['std'], nd),
            _fmt(p['lo'], nd), _fmt(p['hi'], nd), note))
    return L


def pooled_rate_table(key, arows):
    rs = [r for r in arows if r.get('kind') == 'pooled' and r.get('metric') == key]
    if not rs:
        return None
    L = ['| experiment | world | noise | method | events | episodes | pooled % | 95 % cluster CI | naive Wilson (ignores clustering) | n_invalid | n_failed |',
         '|---|---|---|---|---|---|---|---|---|---|---|']
    for r in sorted(rs, key=lambda r: (r['experiment'], r['world'], r.get('odom_noise', ''))):
        L.append('| %s | %s | %s | %s | %s | %s | %s | [%s, %s] | [%s, %s] | %s | %s |' % (
            r['experiment'], r['world'], r.get('odom_noise', ''), r.get('method', ''),
            r.get('n', ''), r.get('n_episodes', ''), _fmt(r.get('pooled_pct'), 1),
            _fmt(r.get('cluster_ci_lo'), 1), _fmt(r.get('cluster_ci_hi'), 1),
            _fmt(r.get('wilson_naive_lo_pct'), 1), _fmt(r.get('wilson_naive_hi_pct'), 1),
            r.get('n_invalid', ''), r.get('n_failed', '')))
    return L


def noise_table(arows, keys):
    rs = [r for r in arows if r.get('kind') == 'noise_delta' and r.get('metric', '')[6:] in keys]
    if not rs:
        return None
    L = ['| experiment | world | method | metric | delta (noise 1 - noise 0) |', '|---|---|---|---|---|']
    for r in sorted(rs, key=lambda r: (r['experiment'], r['world'], r['metric'])):
        L.append('| %s | %s | %s | %s | %s |' % (r['experiment'], r['world'], r.get('method', ''),
                                                  r['metric'], _fmt(r.get('delta'), 4)))
    return L


def compare_table(arows, keys):
    rs = [r for r in arows if r.get('kind') == 'compare' and r.get('metric') in keys]
    if not rs:
        return None
    L = ['| experiment | world | noise | A vs B | metric | n | p | p_holm | Cliff delta |', '|---|---|---|---|---|---|---|---|---|']
    for r in sorted(rs, key=lambda r: (_f(r.get('p_holm')) if _f(r.get('p_holm')) is not None else 9)):
        L.append('| %s | %s | %s | %s vs %s | %s | %s | %s | %s | %s |' % (
            r['experiment'], r['world'], r.get('odom_noise', ''), r.get('method', ''), r.get('method_b', ''),
            r['metric'], r.get('n', ''), _fmt(r.get('p_value'), 4), _fmt(r.get('p_holm'), 4),
            _fmt(r.get('cliffs_delta'), 3)))
    return L


def reported_regardless(summ, roots):
    L = ['## Reported regardless of outcome (pre-registration 13.5b)', '']
    c = counts(summ)
    if not c:
        L.append('No episodes found: nothing has been run in the given roots.')
    else:
        L += ['| experiment | world | noise | ok | partial | invalid | failed | total |', '|---|---|---|---|---|---|---|---|']
        tot = defaultdict(int)
        for k in sorted(c):
            d = c[k]
            t = sum(d.values())
            L.append('| %s | %s | %s | %d | %d | %d | %d | %d |' % (k[0], k[1], k[2], d.get('ok', 0),
                     d.get('partial', 0), d.get('invalid', 0), d.get('failed', 0), t))
            for s, v in d.items():
                tot[s] += v
        L += ['', 'Totals: ' + ', '.join('%s=%d' % (s or 'unknown', v) for s, v in sorted(tot.items())), '']
        bad = [r for r in summ if r.get('status') in ('invalid', 'failed')]
        if bad:
            L += ['Invalid/failed episodes (excluded from statistics, listed here):', '']
            for r in bad:
                L.append('- %s / %s / noise %s / seed %s: %s %s' % (
                    r['experiment'], r.get('world', ''), r.get('odom_noise', ''), r.get('seed', ''),
                    r.get('status'), (r.get('notes') or r.get('end_reason') or '')))
    L += ['', '### Deviations from the pre-registration', '']
    dev = False
    for root in roots:
        for name in ('deviations.md', 'DEVIATIONS.md'):
            p = os.path.join(os.path.expanduser(root), name)
            if os.path.isfile(p):
                L += ['From `%s`:' % p, ''] + open(p).read().splitlines() + ['']
                dev = True
    if not dev:
        L.append('None recorded (no deviations.md in the given roots). Check batch_manifest.json git commit against the frozen document.')
    L += ['', 'Unfavourable results and negative loop-closure results are shown in the tables above without filtering.', '']
    return L


# ---------------------------------------------------------------- figures
def _plt():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    return plt


def fig_coverage(summ, figdir):
    byw = defaultdict(list)
    for s in summ:
        if s.get('status') not in ('ok', 'partial'):
            continue
        for p in glob.glob(os.path.join(s['_path'] and os.path.dirname(s['_path']), 'coverage_curve.csv')):
            rows = _read_csv(p)
            t = [_f(r.get('t_ep')) for r in rows]
            c = [_f(r.get('coverage_explored_pct')) for r in rows]
            ok = [(a, b) for a, b in zip(t, c) if a is not None and b is not None]
            if len(ok) >= 2:
                byw[s.get('world', '')].append(np.array(ok))
    if not byw:
        return None
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for i, w in enumerate(sorted(byw)):
        curves = byw[w]
        tmax = min(c[-1, 0] for c in curves)
        grid = np.linspace(0, tmax, 100)
        Y = np.array([np.interp(grid, c[:, 0], c[:, 1]) for c in curves])
        m = Y.mean(0)
        col = PALETTE[i % len(PALETTE)]
        ax.plot(grid, m, color=col, label='%s (n=%d)' % (w, len(curves)))
        if len(curves) > 1:
            h = 1.96 * Y.std(0, ddof=1) / np.sqrt(len(curves))
            ax.fill_between(grid, m - h, m + h, color=col, alpha=0.2)
    ax.set_xlabel('Episode time (s)')
    ax.set_ylabel('Explored coverage (% of reachable area)')
    ax.set_title('Coverage vs time (mean, 95 % CI)')
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)
    return _save(fig, figdir, 'coverage_vs_time.png')


def _save(fig, figdir, name):
    p = os.path.join(figdir, name)
    fig.tight_layout()
    fig.savefig(p, dpi=150)
    import matplotlib.pyplot as plt
    plt.close(fig)
    return p


def fig_box(summ, key, ylabel, figdir, name):
    d = defaultdict(list)
    for s in summ:
        v = _f(s.get(key))
        if s.get('status') in ('ok', 'partial') and v is not None:
            d[(s.get('world', ''), s.get('odom_noise', ''))].append(v)
    if not d:
        return None
    plt = _plt()
    worlds = sorted({k[0] for k in d})
    noises = sorted({k[1] for k in d})
    fig, ax = plt.subplots(figsize=(max(6, 1.3 * len(worlds)), 4.5))
    wd = 0.8 / len(noises)
    for j, nz in enumerate(noises):
        pos, dat = [], []
        for i, w in enumerate(worlds):
            if d.get((w, nz)):
                pos.append(i + (j - (len(noises) - 1) / 2) * wd)
                dat.append(d[(w, nz)])
        bp = ax.boxplot(dat, positions=pos, widths=wd * 0.9, patch_artist=True)
        for b in bp['boxes']:
            b.set_facecolor(PALETTE[j % len(PALETTE)])
            b.set_alpha(0.7)
        ax.plot([], [], 's', color=PALETTE[j % len(PALETTE)], label='odom noise %s' % (nz or 'n/a'))
    ax.set_xticks(range(len(worlds)))
    ax.set_xticklabels(worlds, rotation=30, ha='right', fontsize=8)
    ax.set_ylabel(ylabel)
    ax.set_xlabel('World')
    ax.legend(fontsize=8)
    ax.grid(axis='y', alpha=0.3)
    return _save(fig, figdir, name)


def fig_nav(arows, figdir):
    rs = [r for r in arows if r.get('kind') == 'pooled' and r.get('metric') == 'nav_goals_succeeded'
          and _f(r.get('pooled_pct')) is not None]
    if not rs:
        return None
    plt = _plt()
    rs = sorted(rs, key=lambda r: (r['world'], r.get('odom_noise', '')))
    lab = ['%s\nnoise %s' % (r['world'], r.get('odom_noise', '')) for r in rs]
    y = np.array([_f(r['pooled_pct']) for r in rs])
    lo = np.array([_f(r.get('cluster_ci_lo')) if _f(r.get('cluster_ci_lo')) is not None else np.nan for r in rs])
    hi = np.array([_f(r.get('cluster_ci_hi')) if _f(r.get('cluster_ci_hi')) is not None else np.nan for r in rs])
    # cluster CI may be returned as fraction or percent; scale to percent when clearly fraction
    if np.nanmax(hi) <= 1.0 and np.nanmax(y) > 1.0:
        lo, hi = lo * 100, hi * 100
    err = np.vstack([np.nan_to_num(y - lo), np.nan_to_num(hi - y)])
    fig, ax = plt.subplots(figsize=(max(6, 0.9 * len(rs)), 4.5))
    ax.bar(range(len(rs)), y, yerr=np.abs(err), color=PALETTE[0], capsize=4)
    ax.set_xticks(range(len(rs)))
    ax.set_xticklabels(lab, rotation=30, ha='right', fontsize=7)
    ax.set_ylabel('Navigation success (% of goals, 95 % cluster CI)')
    ax.set_xlabel('World / odometry noise')
    ax.set_ylim(0, 105)
    ax.grid(axis='y', alpha=0.3)
    return _save(fig, figdir, 'nav_success.png')


def make_figures(arows, summ, figdir):
    os.makedirs(figdir, exist_ok=True)
    made = [fig_coverage(summ, figdir),
            fig_box(summ, 'ate_fixed_rmse_m', 'ATE RMSE, fixed frame (m)', figdir, 'ate_box.png'),
            fig_box(summ, 'rpe_trans_rmse_m_1m', 'RPE translational RMSE per 1 m (m)', figdir, 'rpe_box.png'),
            fig_nav(arows, figdir),
            fig_box(summ, 'n_collisions', 'Collisions per episode (count)', figdir, 'collisions.png')]
    return [m for m in made if m]


# ---------------------------------------------------------------- status update
def status_update(arows, summ):
    L = ['| # | Metric | Headline key | Campaign | Value (pooled over worlds, valid episodes) |', '|---|---|---|---|---|']
    pooled_keys = {}
    for r in arows:
        if r.get('kind') == 'pooled':
            pooled_keys.setdefault(r['metric'], []).append(r)
    for num, name, key, unit, rate in CORE:
        nd = _nd(unit)
        p = pooled_cluster_ci(summ, key)
        nw = len({s.get('world') for s in summ if _f(s.get(key)) is not None and s.get('status') in ('ok', 'partial')})
        if p is None:
            camp, val = 'no', 'no data'
        else:
            camp = 'yes' if p['n'] >= MIN_N and nw >= 2 else 'partial'
            val = '%s %s [%s, %s] cluster CI, n=%d, %d worlds' % (
                _fmt(p['mean'], nd), unit, _fmt(p['lo'], nd), _fmt(p['hi'], nd), p['n'], nw)
        ninv = sum(1 for s in summ if s.get('status') == 'invalid')
        nf = sum(1 for s in summ if s.get('status') == 'failed')
        L.append('| %d | %s | `%s` | %s | %s (campaign invalid=%d, failed=%d) |' % (num, name, key, camp, val, ninv, nf))
    L += ['', '| # | Metric | Key | Campaign | Value |', '|---|---|---|---|---|']
    for num, name, key, unit in EXTRAS:
        p = pooled_cluster_ci(summ, key)
        if p is None:
            L.append('| %s | %s | `%s` | no | no data |' % (num, name, key))
        else:
            L.append('| %s | %s | `%s` | %s | %s %s [%s, %s], n=%d |' % (
                num, name, key, 'yes' if p['n'] >= MIN_N else 'partial', _fmt(p['mean'], _nd(unit)), unit,
                _fmt(p['lo'], _nd(unit)), _fmt(p['hi'], _nd(unit)), p['n']))
    return L


# ---------------------------------------------------------------- metric health
def _reasons(v):
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v]
    if not v:
        return []
    return [x.strip(" '\"") for x in str(v).strip('[]').replace('|', ',').split(',') if x.strip(" '\"")]


def health_section(summ):
    """'Metric health' markdown lines: status counts per metric, top reasons, fallbacks to report."""
    L = ['## Metric health', '',
         'Per-episode classification (precedence UNMEASURABLE > SUSPECT > LOW_N > BAD > OK). BAD floors are '
         'pre-registered diagnosis triggers, not exclusions.', '']
    if not any(('health_' + m) in r for r in summ for m in hl.METRICS):
        return L + ['No health_* keys in the summaries (recompute with compute_metrics).', '']
    L += ['| metric | OK | LOW_N | UNMEASURABLE | SUSPECT | BAD | NA | top reasons | fallback to report |',
          '|---|---|---|---|---|---|---|---|---|']
    for m in hl.METRICS:
        cnt, rs = defaultdict(int), defaultdict(int)
        for r in summ:
            st = r.get('health_' + m)
            if st in (None, ''):
                continue
            cnt[st] += 1
            for x in _reasons(r.get('health_%s_reasons' % m)):
                rs[x.split(':')[0]] += 1
        if not cnt:
            continue
        top = ', '.join('%s x%d' % (k, v) for k, v in sorted(rs.items(), key=lambda kv: -kv[1])[:3]) or '-'
        fb = '-'
        if cnt['UNMEASURABLE'] or cnt['LOW_N'] or cnt['SUSPECT']:
            names = []
            for k in hl.FALLBACKS.get(m, []):
                if any(_f(r.get(k)) is not None for r in summ):
                    names.append(hl.FALLBACK_LABELS.get(k, k))
            fb = ', '.join('`%s`' % n for n in names) or '-'
        L.append('| `%s` | %d | %d | %d | %d | %d | %d | %s | %s |' % (
            m, cnt['OK'], cnt['LOW_N'], cnt['UNMEASURABLE'], cnt['SUSPECT'], cnt['BAD'], cnt['NA'], top, fb))
    L.append('')
    return L


# ---------------------------------------------------------------- main
def build_report(roots, out):
    arows, summ = [], []
    for r in roots:
        a, s = load_root(r)
        arows += a
        summ += s
    os.makedirs(out, exist_ok=True)
    figs = make_figures(arows, summ, os.path.join(out, 'figures'))
    L = ['# Final results', '',
         'Roots: ' + ', '.join('`%s`' % r for r in roots), '',
         'Unit of analysis is the episode (pre-registration 13.5). Statistics use status ok/partial episodes only. '
         'Mean ± sd, bootstrap CI (per world) or cluster bootstrap CI (pooled: worlds, then seeds). '
         'Rows with n < %d are marked INSUFFICIENT DATA.' % MIN_N, '']
    missing = []
    fam = [('Core metrics', [(n, k, u, rate) for _, n, k, u, rate in CORE]),
           ('Additional metrics (A1-A15)', [('%s %s' % (a, n), k, u, None) for a, n, k, u in EXTRAS])]
    for title, items in fam:
        L += ['## ' + title, '']
        for name, key, unit, rate in items:
            t = metric_table(key, unit, arows, summ)
            L.append('### %s (`%s`, %s)' % (name, key, unit))
            L.append('')
            if t is None:
                L += ['INSUFFICIENT DATA: metric not present in any aggregate.', '']
                missing.append(key)
                continue
            L += t + ['']
            if rate:
                rt = pooled_rate_table(rate, arows)
                if rt:
                    L += ['Pooled rate (`%s`):' % rate, ''] + rt + ['']
            nt = noise_table(arows, {key})
            if nt:
                L += ['Noise on vs off:', ''] + nt + ['']
    allkeys = {k for _, _, k, _, _ in CORE} | {k for _, _, k, _ in EXTRAS}
    ct = compare_table(arows, allkeys)
    L += ['## Method comparisons (Holm-adjusted across the family)', '']
    L += (ct + ['']) if ct else ['No method comparisons in the data (method comparison is on hold).', '']
    L += ['## Figures', ''] + ['![%s](figures/%s)' % (os.path.basename(f), os.path.basename(f)) for f in figs] + ['']
    if missing:
        L += ['Metrics with no data: ' + ', '.join('`%s`' % m for m in missing), '']
    L += health_section(summ)
    L += reported_regardless(summ, roots)
    with open(os.path.join(out, 'results.md'), 'w') as f:
        f.write('\n'.join(L) + '\n')
    with open(os.path.join(out, 'metrics_status_update.md'), 'w') as f:
        f.write('\n'.join(status_update(arows, summ)) + '\n')
    return figs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', action='append', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    figs = build_report(a.root, os.path.expanduser(a.out))
    print('report written to %s (%d figures)' % (a.out, len(figs)))


if __name__ == '__main__':
    main()
