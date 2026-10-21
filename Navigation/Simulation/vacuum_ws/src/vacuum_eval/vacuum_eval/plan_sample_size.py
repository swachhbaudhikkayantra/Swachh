"""Episodes needed for a target CI half-width (clustered proportions, continuous).

python3 -m vacuum_eval.plan_sample_size --metric-kind proportion --p 0.6 \
    --goals-per-episode 8 --icc 0.1 --target-halfwidth 0.10
python3 -m vacuum_eval.plan_sample_size --metric-kind continuous --sd 5 --target-halfwidth 2
python3 -m vacuum_eval.plan_sample_size --from-root RUNS --metric nav_goals_succeeded
"""

import argparse
import math
import os

import numpy as np
from scipy import stats


def design_effect(m, icc):
    return 1.0 + (m - 1.0) * icc


def episodes_proportion(p, m, icc, halfwidth, z=1.96):
    """Episodes so the normal-approx CI of a pooled proportion has the half-width."""
    n_goals = z * z * p * (1 - p) / halfwidth ** 2
    return int(math.ceil(n_goals * design_effect(m, icc) / m)), n_goals


def episodes_continuous(sd, halfwidth, conf=0.95):
    """Smallest n with t_{.975,n-1} * sd / sqrt(n) <= halfwidth (iterative)."""
    n = 2
    while n < 100000:
        if stats.t.ppf(0.5 + conf / 2, n - 1) * sd / math.sqrt(n) <= halfwidth:
            return n
        n += 1
    return n


def anova_icc(groups):
    """One-way ANOVA ICC estimate from per-episode lists of 0/1 outcomes."""
    groups = [np.asarray(g, float) for g in groups if len(g) > 0]
    k = len(groups)
    N = sum(g.size for g in groups)
    if k < 2 or N <= k:
        return float('nan')
    gm = sum(g.sum() for g in groups) / N
    ssb = sum(g.size * (g.mean() - gm) ** 2 for g in groups)
    ssw = sum(((g - g.mean()) ** 2).sum() for g in groups)
    msb, msw = ssb / (k - 1), ssw / (N - k)
    m0 = (N - sum(g.size ** 2 for g in groups) / N) / (k - 1)
    d = msb + (m0 - 1) * msw
    return float(max(0.0, (msb - msw) / d)) if d > 0 else float('nan')


def estimate_from_root(root, metric):
    """Return dict(p, m, icc, sd, n) from summary.csv rows (status ok/partial)."""
    from vacuum_eval import aggregate as ag
    rows = [r for r in ag.load_summaries(os.path.expanduser(root))
            if r.get('status') in ('ok', 'partial')]
    pair = dict(ag.RATE_PAIRS)
    est = dict(n=len(rows), p=None, m=None, icc=None, sd=None)
    if metric in pair:
        tot = pair[metric]
        groups, s, t = [], [], []
        for r in rows:
            sv = ag._num(r.get(metric))
            tv = 1.0 if tot is None else ag._num(r.get(tot))
            if sv is None or tv is None or not np.isfinite(sv) or not np.isfinite(tv) \
                    or tv <= 0:
                continue
            s.append(sv)
            t.append(tv)
            groups.append([1.0] * int(round(sv)) + [0.0] * int(round(tv - sv)))
        if t:
            est.update(p=sum(s) / sum(t), m=float(np.mean(t)), icc=anova_icc(groups))
    else:
        v = np.array([ag._num(r.get(metric)) for r in rows], dtype=float)
        v = v[np.isfinite(v)]
        if v.size >= 2:
            est['sd'] = float(v.std(ddof=1))
    return est


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--metric-kind', choices=['proportion', 'continuous'])
    ap.add_argument('--p', type=float)
    ap.add_argument('--goals-per-episode', type=float)
    ap.add_argument('--icc', type=float)
    ap.add_argument('--sd', type=float)
    ap.add_argument('--target-halfwidth', type=float, default=0.10)
    ap.add_argument('--episode-wall-min', type=float, default=45.0)
    ap.add_argument('--from-root')
    ap.add_argument('--metric')
    a = ap.parse_args(argv)
    if a.from_root:
        if not a.metric:
            ap.error('--from-root requires --metric')
        e = estimate_from_root(a.from_root, a.metric)
        print(f'estimated from {e["n"]} episodes: {e}')
        if e['p'] is not None:
            a.metric_kind = 'proportion'
            a.p = e['p'] if a.p is None else a.p
            a.goals_per_episode = a.goals_per_episode or e['m']
            if a.icc is None:
                a.icc = 0.0 if e['icc'] is None or not np.isfinite(e['icc']) else e['icc']
        elif e['sd'] is not None:
            a.metric_kind = 'continuous'
            a.sd = e['sd'] if a.sd is None else a.sd
        else:
            ap.error('could not estimate from data')
    if a.metric_kind == 'proportion':
        if None in (a.p, a.goals_per_episode, a.icc):
            ap.error('proportion needs --p --goals-per-episode --icc')
        n, ng = episodes_proportion(a.p, a.goals_per_episode, a.icc, a.target_halfwidth)
        print(f'design effect = {design_effect(a.goals_per_episode, a.icc):.3f}; '
              f'independent goals needed = {ng:.1f}')
    elif a.metric_kind == 'continuous':
        if a.sd is None:
            ap.error('continuous needs --sd')
        n = episodes_continuous(a.sd, a.target_halfwidth)
    else:
        ap.error('--metric-kind required')
    print(f'episodes needed: {n}')
    print(f'wall-time estimate: {n * a.episode_wall_min / 60:.1f} h '
          f'({n} x {a.episode_wall_min:g} min)')
    return n


if __name__ == '__main__':
    main()
