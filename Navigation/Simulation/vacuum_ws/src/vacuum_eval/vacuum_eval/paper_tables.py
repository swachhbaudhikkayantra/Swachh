"""Compute every number used in paper sections 7.3 and 7.4 from raw per-episode summary.json files.

No value is typed in by hand. The script:
  1. reads each episode's summary.json under a results root (test split campaigns),
  2. computes per-world and pooled statistics with numpy (episode = statistical unit),
  3. takes confidence intervals from the repository's own bootstrap helpers (same seed and B as
     the campaign reports), so they match results.md,
  4. cross-checks its means against the repository's aggregate.csv and lists any mismatch,
  5. writes paper_values.json, paper_tables.md and (optionally) fills a text template whose
     {{path|fmt}} tokens are replaced from the computed values.

Usage:
  PYTHONPATH=<src>/vacuum_eval python3 -m vacuum_eval.paper_tables \
      --root ~/eval_runs_victus --out ~/Swachh/docs/paper_out [--template T.md --filled F.md]
"""

import argparse
import csv
import glob
import json
import math
import os
import re
import sys
from collections import OrderedDict, defaultdict

import numpy as np

from vacuum_eval.aggregate import (BOOT_B, bootstrap_mean_ci, cluster_bootstrap_ci, group_stats,
                                   wilson_interval)
from vacuum_eval.make_report import pooled_cluster_ci

OK_STATUS = ('ok', 'partial')   # same rule as vacuum_eval.aggregate
SEED = 12345

CAMPAIGNS = OrderedDict([
    ('exploration', 'quick_exploration_noise'),
    ('navigation', 'quick_navigation'),
    ('avoidance', 'quick_avoidance'),
    ('responsiveness', 'quick_responsiveness'),
])


# ----------------------------------------------------------------------------- loading
def num(x):
    """-> float or None (None, '', NaN and non-numeric all become None)."""
    if x is None or isinstance(x, bool):
        return float(x) if isinstance(x, bool) else None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def load_campaign(root, name):
    """-> list of episode dicts (summary.json content plus _path, _world, _seed)."""
    eps = []
    for p in sorted(glob.glob(os.path.join(root, name, '*', '*', 'seed_*', 'summary.json'))):
        with open(p) as f:
            j = json.load(f)
        parts = p.split(os.sep)
        j['_path'] = p
        j['_world'] = parts[-4]
        j['_variant'] = parts[-3]
        j['_seed'] = int(parts[-2].split('_')[1])
        eps.append(j)
    return eps


def valid(eps):
    return [e for e in eps if e.get('status') in OK_STATUS]


def vals(eps, key):
    out = []
    for e in eps:
        v = num(e.get(key))
        if v is not None:
            out.append(v)
    return out


def stat(eps, key):
    """Mean, SD, n, bootstrap CI (repo helper) of an episode-level metric."""
    v = vals(eps, key)
    g = group_stats(v)
    lo, hi = bootstrap_mean_ci(v, BOOT_B, SEED)
    return dict(n=g['n'], mean=g['mean'], sd=g['std'], min=g['min'], max=g['max'],
                ci_lo=None if math.isnan(lo) else lo, ci_hi=None if math.isnan(hi) else hi)


def hier(eps, key):
    """Pre-registered pooled mean: unweighted mean of episodes, CI by the repository's two-stage
    bootstrap (resample worlds, then seeds inside each world). Same call as make_report."""
    r = pooled_cluster_ci(valid(eps), key)
    if r is None:
        return dict(n=0, mean=None, sd=None, min=None, max=None, ci_lo=None, ci_hi=None,
                    method='world-cluster', nworlds=0)
    v = vals(valid(eps), key)
    return dict(n=r['n'], mean=r['mean'], sd=None if math.isnan(r['std']) else r['std'],
                min=min(v), max=max(v), ci_lo=r['lo'], ci_hi=r['hi'], method='world-cluster',
                nworlds=r['nworlds'])


def pooled_rate(eps, succ_fn, tot_fn):
    """Pooled sum(succ)/sum(tot) in percent with the repo's episode-level cluster bootstrap."""
    s, t = [], []
    for e in eps:
        a, b = succ_fn(e), tot_fn(e)
        if a is None or b is None:
            continue
        s.append(a)
        t.append(b)
    if not t or sum(t) == 0:
        return dict(k=0, n=0, episodes=0, pct=None, ci_lo=None, ci_hi=None)
    lo, hi = cluster_bootstrap_ci(s, t, BOOT_B, SEED)
    return dict(k=sum(s), n=sum(t), episodes=sum(1 for x in t if x > 0), pct=100.0 * sum(s) / sum(t),
                ci_lo=None if math.isnan(lo) else lo, ci_hi=None if math.isnan(hi) else hi)


def gt_successes(e, key_pct):
    """Number of goals counted by a percent metric, from percent x total goals. Must be integral."""
    p, tot = num(e.get(key_pct)), num(e.get('nav_goals_total'))
    if p is None or tot is None:
        return None
    k = p * tot / 100.0
    if abs(k - round(k)) > 1e-6:
        raise ValueError('non-integral goal count for %s in %s: %r' % (key_pct, e['_path'], k))
    return int(round(k))


def reachable_area(root, world):
    z = np.load(os.path.join(root, '_gt', world + '.npz'), allow_pickle=True)
    return float(z['A_reach_m2']), float(z['A_clean_m2'])


def census(eps):
    c = defaultdict(int)
    for e in eps:
        c[e.get('status', '?')] += 1
    return dict(c)


def flag_counts(eps, metric):
    c = defaultdict(int)
    for e in eps:
        c[str(e.get('health_' + metric, 'NA'))] += 1
    return dict(c)


def by_world(eps):
    d = OrderedDict()
    for e in eps:
        d.setdefault(e['_world'], []).append(e)
    return d


# ----------------------------------------------------------------------------- campaigns
EXPLORATION_METRICS = [
    ('coverage_explored_pct', 'Coverage (%)'),
    ('map_completeness_pct', 'Map completeness (%)'),
    ('ate_fixed_rmse_m', 'ATE (m)'),
    ('rpe_trans_rmse_m_1m', 'RPE (m per m)'),
    ('lc_recall_pct', 'Loop-closure recall (%)'),
    ('n_collisions', 'Collisions per episode'),
    ('n_est_gaps', 'Tracking gaps per episode'),
    ('ate_improvement_pct', 'ATE improvement over odometry (%)'),
    ('cleaning_efficiency', 'Cleaning efficiency'),
    ('ate_odom_fixed_rmse_m', 'Odometry-only ATE (m)'),
]


def explo_block(eps):
    v = valid(eps)
    b = OrderedDict(n_total=len(eps), n_valid=len(v), census=census(eps))
    for k, _ in EXPLORATION_METRICS:
        b[k] = stat(v, k)
        b[k]['health'] = flag_counts(v, k) if ('health_' + k) in (v[0] if v else {}) else {}
    b['lc_precision'] = pooled_rate(v, lambda e: num(e.get('lc_n_true')),
                                    lambda e: num(e.get('lc_n_accepted')))
    b['lc_precision_mean'] = stat(v, 'lc_precision_pct')
    b['lc_accepted_per_episode'] = stat(v, 'lc_n_accepted')
    b['corrupted'] = dict(k=int(sum(1 for e in v if num(e.get('odom_corrupted_by_contact')) == 1)),
                          n=len(v))
    clean = [e for e in v if num(e.get('odom_corrupted_by_contact')) != 1]
    b['ate_uncorrupted'] = stat(clean, 'ate_fixed_rmse_m')
    b['ate_pre_corrupt'] = stat(v, 'ate_fixed_rmse_m_pre_corrupt')
    b['rtf'] = stat(v, 'rtf_true_mean')
    return b


def explore(root, eps):
    out = OrderedDict()
    for w, es in by_world(eps).items():
        b = explo_block(es)
        b['reachable_m2'], b['cleanable_m2'] = reachable_area(root, w)
        out[w] = b
    pb = explo_block(eps)
    keys = [k for k, _ in EXPLORATION_METRICS]
    for k in keys:
        pb[k + '_episode_bootstrap'] = pb[k]
        pb[k] = hier(eps, k)
    pb['lc_precision_mean'] = hier(eps, 'lc_precision_pct')
    pb['ate_pre_corrupt'] = hier(eps, 'ate_fixed_rmse_m_pre_corrupt')
    out['pooled'] = pb
    return out


def explore_episodes(eps):
    rows = []
    for e in sorted(eps, key=lambda x: (x['_world'], x['_seed'])):
        rows.append(dict(world=e['_world'], seed=e['_seed'], status=e.get('status'),
                         goals=num(e.get('nav_goals_total')), coverage=num(e.get('coverage_explored_pct')),
                         end=e.get('end_reason'), collisions=num(e.get('n_collisions')),
                         corrupted=num(e.get('odom_corrupted_by_contact')),
                         rtf=num(e.get('rtf_true_mean'))))
    return rows


def no_goal_episodes(eps):
    out = OrderedDict()
    for w, es in by_world(valid(eps)).items():
        out[w] = dict(k=int(sum(1 for e in es if (num(e.get('nav_goals_total')) or 0) == 0)), n=len(es))
    out['pooled'] = dict(k=sum(v['k'] for v in out.values()), n=sum(v['n'] for v in out.values()))
    return out


def diagnostic(root):
    """Localisation diagnostic on a dev world (not part of the test results)."""
    out = OrderedDict()
    for label, name in (('amcl', 'dev8h_nav_amcl'), ('gt_localization', 'diag_gt_localization')):
        ps = sorted(glob.glob(os.path.join(root, name, 'apartment', '*', 'seed_*', 'summary.json')))
        if not ps:
            continue
        j = json.load(open(ps[0]))
        k = gt_successes(dict(j, _path=ps[0]), 'nav_success_gt_pct')
        out[label] = dict(goals=num(j.get('nav_goals_total')), nav2=num(j.get('nav_goals_succeeded')),
                          gt=k, gt_pct=num(j.get('nav_success_gt_pct')), path=ps[0].replace(root, ''))
    return out


def nav_block(eps):
    v = valid(eps)
    b = OrderedDict(n_total=len(eps), n_valid=len(v), census=census(eps))
    b['goals_total'] = int(sum(vals(v, 'nav_goals_total')))
    b['nav2_success'] = pooled_rate(v, lambda e: num(e.get('nav_goals_succeeded')),
                                    lambda e: num(e.get('nav_goals_total')))
    b['gt_success'] = pooled_rate(v, lambda e: gt_successes(e, 'nav_success_gt_pct'),
                                  lambda e: num(e.get('nav_goals_total')))
    b['gt_strict'] = pooled_rate(v, lambda e: gt_successes(e, 'nav_success_gt_strict_pct'),
                                 lambda e: num(e.get('nav_goals_total')))
    b['goals_unfinished'] = int(sum(vals(v, 'nav_goals_unfinished')))
    for k in ('path_length_ratio_mean', 'n_recoveries', 'n_collisions', 'n_goals',
              'nav_fail_aborted', 'nav_fail_timeout', 'rtf_true_mean', 'nav_success_gt_pct',
              'nav_success_pct', 'nav_success_gt_strict_pct'):
        b[k] = stat(v, k)
    b['stuck_episodes'] = dict(k=int(sum(1 for e in v if e.get('end_reason') == 'stuck')), n=len(v))
    b['goals_done_episodes'] = dict(
        k=int(sum(1 for e in v if e.get('end_reason') == 'goals_done')), n=len(v))
    b['gt_success_per_episode'] = [
        dict(world=e['_world'], seed=e['_seed'], goals=num(e.get('nav_goals_total')),
             gt=gt_successes(e, 'nav_success_gt_pct'), nav2=num(e.get('nav_goals_succeeded')),
             end=e.get('end_reason')) for e in v]
    return b


def navigation(eps):
    out = OrderedDict()
    for w, es in by_world(eps).items():
        out[w] = nav_block(es)
    pb = nav_block(eps)
    for k in ('nav_success_gt_pct', 'nav_success_pct', 'nav_success_gt_strict_pct',
              'path_length_ratio_mean', 'n_recoveries', 'n_collisions'):
        pb[k + '_hier'] = hier(eps, k)
    out['pooled'] = pb
    return out


def avoid_block(eps):
    v = valid(eps)
    b = OrderedDict(n_total=len(eps), n_valid=len(v), census=census(eps))
    ts = vals(v, 'trial_success')
    k, n = int(sum(ts)), len(ts)
    lo, hi = wilson_interval(k, n) if n else (float('nan'), float('nan'))
    b['trial_success'] = dict(k=k, n=n, pct=100.0 * k / n if n else None,
                              wilson_lo=100 * lo if n else None, wilson_hi=100 * hi if n else None)
    b['goal_reached'] = dict(k=int(sum(vals(v, 'trial_goal_reached'))), n=len(vals(v, 'trial_goal_reached')))
    b['collisions_total'] = int(sum(vals(v, 'n_collisions')))
    b['trial_collisions_total'] = int(sum(vals(v, 'trial_collisions')))
    for key in ('min_clearance_m', 'avoidance_pct', 'nav_success_gt_pct', 'rtf_true_mean'):
        b[key] = stat(v, key)
    b['per_episode'] = [dict(world=e['_world'], seed=e['_seed'], trial=num(e.get('trial_success')),
                             reached=num(e.get('trial_goal_reached')),
                             collisions=num(e.get('trial_collisions')),
                             clearance=num(e.get('min_clearance_m')),
                             obstacle_resp_ms=num(e.get('lat_obstacle_ms_mean')),
                             obstacle_resp_met=num(e.get('resp_obstacle_pct')),
                             replans=num(e.get('replans_per_goal_mean')),
                             encounters=num(e.get('n_encounters')),
                             time_s=num(e.get('trial_time_s'))) for e in v]
    b['replans_per_goal'] = stat(v, 'replans_per_goal_mean')
    b['trial_time_s'] = stat(v, 'trial_time_s')
    b['obstacle_resp_ms'] = stat(v, 'lat_obstacle_ms_mean')
    b['obstacle_resp_events'] = dict(k=int(sum(1 for e in v if num(e.get('resp_obstacle_pct')) == 100.0)),
                                     n=len(vals(v, 'resp_obstacle_pct')))
    return b


def avoidance(eps):
    out = OrderedDict()
    for w, es in by_world(eps).items():
        out[w] = avoid_block(es)
    out['pooled'] = avoid_block(eps)
    return out


def responsiveness(eps):
    out = OrderedDict()
    for variant in sorted({e['_variant'] for e in eps}):
        es = [e for e in eps if e['_variant'] == variant]
        v = valid(es)
        b = OrderedDict(n_total=len(es), n_valid=len(v), census=census(es))
        for key in ('lat_cmd_motion_ms_mean', 'lat_cmd_motion_ms_p95', 'lat_stop_ms_mean',
                    'lat_stop_ms_p95', 'rtf_true_mean'):
            b[key] = stat(v, key)
        # share of command and stop latencies within the 0.5 s deadline, from per-episode p95
        b['p95_cmd_under_500ms'] = dict(k=int(sum(1 for x in vals(v, 'lat_cmd_motion_ms_p95') if x < 500)),
                                        n=len(vals(v, 'lat_cmd_motion_ms_p95')))
        b['p95_stop_under_500ms'] = dict(k=int(sum(1 for x in vals(v, 'lat_stop_ms_p95') if x < 500)),
                                         n=len(vals(v, 'lat_stop_ms_p95')))
        out[variant] = b
    return out


def rtf_table(all_eps):
    out = OrderedDict()
    for name, eps in all_eps.items():
        v = vals(eps, 'rtf_true_mean')
        out[name] = dict(n=len(v), min=min(v) if v else None, max=max(v) if v else None,
                         mean=float(np.mean(v)) if v else None)
    allv = [x for eps in all_eps.values() for x in vals(eps, 'rtf_true_mean')]
    out['all'] = dict(n=len(allv), min=min(allv), max=max(allv), mean=float(np.mean(allv)))
    return out


# ----------------------------------------------------------------------------- latency and system figures
def _pct(v, q):
    return float(np.percentile(v, q)) if len(v) else None


def goal_plan_latencies(ep_dir):
    """Per-goal planning latency in ms (Nav2 accepts a goal -> first plan published), using the repository's
    own goal and plan loaders so the definition matches vacuum_eval.metrics.navigation."""
    from vacuum_eval import compute_metrics as cm
    from vacuum_eval.metrics import navigation as nv
    from vacuum_eval.metrics.common import load_run
    run = load_run(ep_dir)
    cm.determine_episode(run)
    t0, t1 = nv._window(run)
    recs = nv.goal_records(run, t0, t1)
    plans = run.plans
    out = []
    counts = dict(started=len(recs), no_accept=0, no_plan=0)
    if plans and 't' in plans and run.goal_events:
        pt = np.asarray(plans['t'], float)
        for r in recs:
            acc = nv._nav2_accepted(run, r['t_start'])
            if acc is None:
                counts['no_accept'] += 1
                continue
            after = pt[pt >= acc[0]]
            if len(after):
                out.append(1000.0 * float(after[0] - acc[0]))
            else:
                counts['no_plan'] += 1
    return out, counts


def plan_latency_block(eps):
    allv, checks = [], []
    tot = dict(started=0, no_accept=0, no_plan=0)
    for e in valid(eps):
        d = os.path.dirname(e['_path'])
        lat, cnt = goal_plan_latencies(d)
        for k in tot:
            tot[k] += cnt[k]
        allv.extend(lat)
        ref = num(e.get('plan_latency_ms_mean'))
        got = float(np.mean(lat)) if lat else None
        checks.append(dict(ep='%s/%d' % (e['_world'], e['_seed']), n=len(lat), mine=got, summary=ref,
                           ok=(got is None and ref is None) or (got is not None and ref is not None
                                                               and abs(got - ref) < 1e-6)))
    return dict(n_goals=len(allv), n_started=tot['started'], n_no_accept=tot['no_accept'],
                n_no_plan=tot['no_plan'],
                n_under_100ms=sum(1 for x in allv if x < 100), n_episodes=len(checks), median=_pct(allv, 50), p95=_pct(allv, 95),
                p99=_pct(allv, 99), max=max(allv) if allv else None,
                share_under_100ms=(100.0 * sum(1 for x in allv if x < 100) / len(allv)) if allv else None,
                mean=float(np.mean(allv)) if allv else None,
                recompute_matches_summary=all(c['ok'] for c in checks),
                n_mismatch=sum(1 for c in checks if not c['ok']))


RTABMAP_LINE = re.compile(r'rtabmap \((\d+)\): Rate=([\d.]+)s, Limit=[\d.]+s, Conversion=([\d.]+)s, '
                          r'RTAB-Map=([\d.]+)s, Maps update=([\d.]+)s pub=([\d.]+)s delay=([\d.]+)s')


def slam_update_times(eps):
    """Per-update RTAB-Map timings (ms) parsed from the stack logs of valid episodes."""
    rows = []
    per_world = defaultdict(list)
    for e in valid(eps):
        log = os.path.join(os.path.dirname(e['_path']), 'logs', 'explore_stack.log')
        if not os.path.exists(log):
            continue
        with open(log, errors='replace') as fh:
            for line in fh:
                m = RTABMAP_LINE.search(line)
                if m:
                    conv, rt, mu, pub, delay = (1000.0 * float(m.group(i)) for i in (3, 4, 5, 6, 7))
                    row = (conv + rt + mu + pub, rt, delay)
                    rows.append(row)
                    per_world[e['_world']].append(row)

    def blk(r):
        a = np.array(r) if r else np.zeros((0, 3))
        return dict(n_updates=int(len(a)),
                    total_median=_pct(a[:, 0], 50), total_p95=_pct(a[:, 0], 95),
                    rtabmap_median=_pct(a[:, 1], 50), rtabmap_p95=_pct(a[:, 1], 95),
                    delay_median=_pct(a[:, 2], 50), delay_p95=_pct(a[:, 2], 95))
    out = OrderedDict()
    for w, r in sorted(per_world.items()):
        out[w] = blk(r)
    out['pooled'] = blk(rows)
    return out


def jetson_benchmark(root_repo):
    """Parse the Jetson Orin Nano benchmark tables (Scenario A direct camera, Scenario B wireless)."""
    path = os.path.join(root_repo, 'docs', 'PROJECT_CONTEXT.md')
    out = OrderedDict(A=OrderedDict(), B=OrderedDict())
    scen = None
    for line in open(path, encoding='utf-8'):
        if line.startswith('### Scenario A'):
            scen = 'A'
        elif line.startswith('### Scenario B'):
            scen = 'B'
        elif line.startswith('## '):
            scen = None
        if scen and line.startswith('| **YOLO'):
            c = [x.strip().replace('*', '') for x in line.strip().strip('|').split('|')]
            key = '%s_%s' % (c[0].lower().replace('-', ''), c[1].lower())
            if 'SKIPPED' in line:
                out[scen][key] = dict(skipped=True)
                continue
            if scen == 'A':
                m, sd = [float(x) for x in c[4].split('±')]
                out['A'][key] = dict(latency_ms=m, latency_sd=sd, p95_ms=float(c[6]), fps=float(c[7]),
                                     power_w=float(c[9].replace('W', '')), backend=c[2])
            else:
                out['B'][key] = dict(infer_ms=float(c[4]), net_ms=float(c[5]), decode_ms=float(c[6]),
                                     e2e_ms=float(c[7]), e2e_fps=float(c[8]), backend=c[2])
    dec = [v['decode_ms'] for v in out['B'].values() if 'decode_ms' in v]
    out['B_decode_range'] = dict(min=min(dec), max=max(dec))
    return out


def serial_wire_time_ms(cmd, baud=115200, bits_per_byte=10):
    """Lower bound for transmitting one newline-terminated command at 8N1 (10 bits per byte)."""
    n = len(cmd.encode('ascii')) + 1
    return n, 1000.0 * n * bits_per_byte / baud


def stack_memory(eps):
    v = valid(eps)
    return dict(rss_rtabmap_peak_mb=stat(v, 'rss_rtabmap_peak_mb'), rtabmap_updates=stat(v, 'rtabmap_updates'))


# ----------------------------------------------------------------------------- cross-check
def crosscheck(root, name, eps):
    """Compare our per-world means with the repository's aggregate.csv (kind=stat rows)."""
    path = os.path.join(root, name, 'aggregate.csv')
    if not os.path.exists(path):
        return dict(path=path, found=False, compared=0, mismatches=[])
    ours = {}
    for w, es in by_world(valid(eps)).items():
        keys = set()
        for e in es:
            keys.update(k for k, v in e.items() if num(v) is not None and not k.startswith('_'))
        for k in keys:
            vv = vals(es, k)
            if vv:
                ours[(w, k)] = (float(np.mean(vv)), len(vv))
    compared, mism = 0, []
    with open(path, newline='') as f:
        for r in csv.DictReader(f):
            if r.get('kind') != 'stat':
                continue
            key = (r.get('world'), r.get('metric'))
            if key not in ours:
                continue
            theirs, n_theirs = num(r.get('mean')), num(r.get('n'))
            if theirs is None:
                continue
            m, n = ours[key]
            compared += 1
            if int(n_theirs) != n or abs(m - theirs) > 1e-6 * max(1.0, abs(theirs)):
                mism.append(dict(world=key[0], metric=key[1], ours=m, theirs=theirs,
                                 n_ours=n, n_theirs=int(n_theirs)))
    return dict(path=path, found=True, compared=compared, mismatches=mism)


# ----------------------------------------------------------------------------- formatting
def f(x, d=1, pct=False):
    if x is None:
        return 'n/a'
    return ('%.*f' % (d, x)) + ('%' if pct else '')


def ci(s, d=1):
    if s is None or s.get('ci_lo') is None:
        return ''
    return ' [%s, %s]' % (f(s['ci_lo'], d), f(s['ci_hi'], d))


def cell(s, d=1):
    if s is None or s.get('mean') is None:
        return 'n/a (n=0)'
    return '%s%s (n=%d)' % (f(s['mean'], d), ci(s, d), s['n'])


def prate(p, d=1):
    if p is None or p.get('pct') is None:
        return 'n/a'
    c = '' if p.get('ci_lo') is None else ' [%s, %s]' % (f(p['ci_lo'], d), f(p['ci_hi'], d))
    return '%s%%%s (%d of %d)' % (f(p['pct'], d), c, p['k'], p['n'])


def render_tables(V):
    L = []
    A = L.append
    A('# Paper tables (generated by vacuum_eval.paper_tables; do not edit by hand)\n')
    A('Means are over valid episodes (status ok or partial). Brackets are 95 percent bootstrap '
      'intervals over episodes (%d resamples, seed %d) from the repository helpers. "n" is the '
      'number of episodes with a value for that metric.\n' % (BOOT_B, SEED))

    A('## Table 8. SLAM and exploration (exploration campaign)\n')
    cols = ['World', 'Valid / run', 'Reachable m2'] + [m[1] for m in EXPLORATION_METRICS[:4]] + \
           ['Loop-closure precision (by closures)', 'Loop-closure precision (per-episode mean)',
            'Loop-closure recall (%)', 'Collisions per ep.',
            'Odometry corrupted by contact']
    A('| ' + ' | '.join(cols) + ' |')
    A('|' + '---|' * len(cols))
    for w, b in V['exploration'].items():
        row = [w, '%d / %d' % (b['n_valid'], b['n_total']),
               f(b.get('reachable_m2')) if 'reachable_m2' in b else '']
        for k, _ in EXPLORATION_METRICS[:4]:
            row.append(cell(b[k], 2 if k in ('ate_fixed_rmse_m', 'rpe_trans_rmse_m_1m') else 1))
        lcp = b['lc_precision']
        row.append(('%s, from %d episodes' % (prate(lcp), lcp['episodes'])) if lcp['episodes'] else 'n/a')
        row.append(cell(b['lc_precision_mean']))
        row.append(cell(b['lc_recall_pct']))
        row.append(cell(b['n_collisions']))
        row.append('%d of %d' % (b['corrupted']['k'], b['corrupted']['n']))
        A('| ' + ' | '.join(row) + ' |')
    A('')
    A('ATE with and without episodes whose odometry was corrupted by contact:\n')
    A('| World | ATE all valid (m) | ATE excluding corrupted (m) | ATE before first corruption (m) |')
    A('|---|---|---|---|')
    for w, b in V['exploration'].items():
        A('| %s | %s | %s | %s |' % (w, cell(b['ate_fixed_rmse_m'], 2), cell(b['ate_uncorrupted'], 2),
                                    cell(b['ate_pre_corrupt'], 2)))
    A('')

    A('Per-episode exploration detail:\n')
    A('| World | Seed | Goals sent | Coverage (%) | Ended | Collisions | Odometry corrupted | RTF |')
    A('|---|---|---|---|---|---|---|---|')
    for e in V['exploration_episodes']:
        A('| %s | %d | %s | %s | %s | %s | %s | %s |' % (
            e['world'], e['seed'], f(e['goals'], 0), f(e['coverage']), e['end'], f(e['collisions'], 0),
            f(e['corrupted'], 0), f(e['rtf'], 3)))
    A('')
    A('Episodes in which the explorer sent no goal: ' + ', '.join(
        '%s %d of %d' % (w, v['k'], v['n']) for w, v in V['no_goal_episodes'].items()) + '\n')
    A('## Table 8b. Navigation (Nav2 with AMCL on a ground-truth map)\n')
    A('Two definitions are shown. "By goals" pools all goals (successes divided by goals, 95 percent '
      'interval from an episode-level bootstrap). "Per-episode mean" is the unweighted mean of the '
      'per-episode percentages; its pooled row uses the pre-registered two-stage bootstrap '
      '(worlds, then seeds), as in the campaign reports.\n')
    cols = ['World', 'Valid / run', 'Goals', 'Nav2-reported (by goals)', 'GT-verified, 0.30 m (by goals)',
            'GT-verified, 0.30 m (per-episode mean)', 'Strict 0.15 m (by goals)', 'Path-length ratio',
            'Recoveries per ep.', 'Collisions per ep.', 'Ended stuck']
    A('| ' + ' | '.join(cols) + ' |')
    A('|' + '---|' * len(cols))
    for w, b in V['navigation'].items():
        ep = b['nav_success_gt_pct_hier'] if w == 'pooled' else b['nav_success_gt_pct']
        plr = b['path_length_ratio_mean_hier'] if w == 'pooled' else b['path_length_ratio_mean']
        rec = b['n_recoveries_hier'] if w == 'pooled' else b['n_recoveries']
        col = b['n_collisions_hier'] if w == 'pooled' else b['n_collisions']
        A('| ' + ' | '.join([w, '%d / %d' % (b['n_valid'], b['n_total']), str(b['goals_total']),
                             prate(b['nav2_success']), prate(b['gt_success']), cell(ep),
                             prate(b['gt_strict']), cell(plr, 2), cell(rec), cell(col),
                             '%d of %d' % (b['stuck_episodes']['k'], b['stuck_episodes']['n'])]) + ' |')
    A('')
    A('Per-episode detail (goals, Nav2-reported successes, GT-verified successes, end reason):\n')
    A('| World | Seed | Goals | Nav2 success | GT-verified | Ended |')
    A('|---|---|---|---|---|---|')
    for e in V['navigation']['pooled']['gt_success_per_episode']:
        A('| %s | %d | %s | %s | %s | %s |' % (e['world'], e['seed'], f(e['goals'], 0), f(e['nav2'], 0),
                                              '' if e['gt'] is None else e['gt'], e['end']))
    A('')

    A('Localisation diagnostic (development world apartment, seed 1; not part of the test results):\n')
    A('| Localisation | Goals | Nav2-reported successes | GT-verified successes | GT-verified (%) |')
    A('|---|---|---|---|---|')
    for k, d in V['diagnostic'].items():
        A('| %s | %s | %s | %s | %s |' % (k, f(d['goals'], 0), f(d['nav2'], 0), d['gt'], f(d['gt_pct'])))
    A('')
    A('## Table 9. Obstacle avoidance\n')
    cols = ['Scenario', 'Valid / run', 'Trials reaching goal without contact', 'Goal reached',
            'Contact events (total)', 'Minimum clearance (m)']
    A('| ' + ' | '.join(cols) + ' |')
    A('|' + '---|' * len(cols))
    for w, b in V['avoidance'].items():
        t = b['trial_success']
        ts = 'n/a' if t['pct'] is None else '%s%% (%d of %d), Wilson [%s, %s]' % (
            f(t['pct']), t['k'], t['n'], f(t['wilson_lo']), f(t['wilson_hi']))
        A('| ' + ' | '.join([w, '%d / %d' % (b['n_valid'], b['n_total']), ts,
                             '%d of %d' % (b['goal_reached']['k'], b['goal_reached']['n']),
                             str(b['trial_collisions_total']),
                             cell(b['min_clearance_m'], 3)]) + ' |')
    A('')

    A('## Table 10. Responsiveness (wall-clock, office)\n')
    cols = ['Stack', 'Valid / run', 'Command to motion mean (ms)', 'Stop mean (ms)',
            'Command P95 (ms)', 'Stop P95 (ms)']
    A('| ' + ' | '.join(cols) + ' |')
    A('|' + '---|' * len(cols))
    for w, b in V['responsiveness'].items():
        A('| ' + ' | '.join([w, '%d / %d' % (b['n_valid'], b['n_total']),
                             cell(b['lat_cmd_motion_ms_mean']), cell(b['lat_stop_ms_mean']),
                             cell(b['lat_cmd_motion_ms_p95']), cell(b['lat_stop_ms_p95'])]) + ' |')
    A('')

    A('## Real-time factor and validity\n')
    A('| Campaign | Episodes with RTF | Min | Max | Mean |')
    A('|---|---|---|---|---|')
    for k, r in V['rtf'].items():
        A('| %s | %d | %s | %s | %s |' % (k, r['n'], f(r['min'], 3), f(r['max'], 3), f(r['mean'], 3)))
    A('')
    A('| Campaign | Status counts |')
    A('|---|---|')
    for k, c in V['census'].items():
        A('| %s | %s |' % (k, ', '.join('%s: %d' % (a, b) for a, b in sorted(c.items()))))
    A('')

    A('## Cross-check against the repository aggregate.csv\n')
    for k, c in V['crosscheck'].items():
        if not c['found']:
            A('- %s: aggregate.csv not found (%s)' % (k, c['path']))
            continue
        A('- %s: compared %d per-world means; mismatches: %d' % (k, c['compared'], len(c['mismatches'])))
        for m in c['mismatches'][:10]:
            A('  - %(world)s %(metric)s: ours %(ours)s (n=%(n_ours)d), repo %(theirs)s (n=%(n_theirs)d)' % m)
    A('')
    return '\n'.join(L)


# ----------------------------------------------------------------------------- templating
TOKEN = re.compile(r'\{\{\s*([a-zA-Z0-9_.\-]+)\s*(?:\|\s*([a-z0-9_]+))?\s*\}\}')


def lookup(V, path):
    cur = V
    for part in path.split('.'):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit():
            cur = cur[int(part)]
        else:
            raise KeyError(path)
    return cur


def fmt(val, spec):
    if val is None:
        return 'n/a'
    if spec in (None, ''):
        return str(val)
    m = re.fullmatch(r'f(\d)', spec)
    if m:
        return '%.*f' % (int(m.group(1)), val)
    if spec == 'int':
        return str(int(round(val)))
    raise ValueError('unknown format ' + spec)


def fill(template, V):
    missing = []

    def sub(m):
        try:
            return fmt(lookup(V, m.group(1)), m.group(2))
        except KeyError:
            missing.append(m.group(1))
            return '{{MISSING:%s}}' % m.group(1)
    out = TOKEN.sub(sub, template)
    return out, missing


# ----------------------------------------------------------------------------- main
def compute(root):
    raw = OrderedDict((k, load_campaign(root, v)) for k, v in CAMPAIGNS.items())
    V = OrderedDict()
    V['exploration'] = explore(root, raw['exploration'])
    V['navigation'] = navigation(raw['navigation'])
    V['avoidance'] = avoidance(raw['avoidance'])
    V['responsiveness'] = responsiveness(raw['responsiveness'])
    V['exploration_episodes'] = explore_episodes(raw['exploration'])
    V['no_goal_episodes'] = no_goal_episodes(raw['exploration'])
    V['diagnostic'] = diagnostic(root)
    V['plan_latency'] = OrderedDict(navigation=plan_latency_block(raw['navigation']),
                                    avoidance=plan_latency_block(raw['avoidance']))
    V['slam_update'] = slam_update_times(raw['exploration'])
    V['memory'] = stack_memory(raw['exploration'])
    V['jetson'] = jetson_benchmark(os.path.expanduser('~/Swachh'))
    n, ms = serial_wire_time_ms('ARM:PICK:bottle,10.0,5.0,30.0,0.85')
    V['serial'] = dict(example_bytes=n, wire_ms=ms, baud=115200)
    from vacuum_eval.metrics import responsiveness as rs
    V['obstacle_def'] = dict(clearance_m=rs.OBS_CLEARANCE_M, fov_half_deg=float(np.degrees(rs.HFOV_HALF)),
                             vx_frac=rs.OBS_VX_FRAC, wz=rs.OBS_WZ, deadline_s=rs.DEFAULT_DEADLINES['obstacle'],
                             moving_vx=rs.OBS_V_MOVING)
    V['rtf'] = rtf_table(raw)
    V['census'] = OrderedDict((k, census(v)) for k, v in raw.items())
    V['crosscheck'] = OrderedDict((k, crosscheck(root, CAMPAIGNS[k], raw[k])) for k in raw)
    V['meta'] = dict(boot_B=BOOT_B, seed=SEED, root=root,
                     n_episodes={k: len(v) for k, v in raw.items()})
    return V


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True, help='folder holding quick_* campaign folders and _gt/')
    ap.add_argument('--out', required=True)
    ap.add_argument('--template', help='text with {{path|fmt}} tokens')
    ap.add_argument('--filled', help='output path for the filled template')
    a = ap.parse_args(argv)
    root = os.path.expanduser(a.root)
    out = os.path.expanduser(a.out)
    os.makedirs(out, exist_ok=True)
    V = compute(root)
    with open(os.path.join(out, 'paper_values.json'), 'w') as fh:
        json.dump(V, fh, indent=1, default=str)
    with open(os.path.join(out, 'paper_tables.md'), 'w') as fh:
        fh.write(render_tables(V))
    bad = sum(len(c['mismatches']) for c in V['crosscheck'].values())
    print('wrote', out, '| cross-check mismatches:', bad)
    if a.template:
        with open(os.path.expanduser(a.template), encoding='utf-8') as fh:
            text, missing = fill(fh.read(), V)
        with open(os.path.expanduser(a.filled), 'w', encoding='utf-8') as fh:
            fh.write(text)
        if missing:
            print('MISSING TOKENS:', sorted(set(missing)))
            return 2
        print('filled', a.filled)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
