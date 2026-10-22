#!/usr/bin/env python3
"""
diagnose - explain WHY a run's metrics are what they are.

    python3 -m vacuum_eval.diagnose <run_dir> [--png out.png]

Reads only files the recorder already wrote (trajectory/cmd_vel/goal_events/plans CSVs,
logs/*.log, summary.json) and prints:
  1. where the episode time went (moving / rotating in place / stationary / recovering)
  2. every goal with its outcome and how long it took
  3. planner / controller failure messages, counted, with the dominant cause
  4. localization vs navigation (did Nav2 'succeed' at the wrong place?)
  5. where the robot sat still (stuck spots, in world coordinates)
  6. a ranked list of likely causes
Optional --png draws the GT trajectory (colour = speed), stuck spots and goals.
"""
import argparse
import collections
import glob
import json
import os
import re

import numpy as np

from vacuum_eval.metrics.common import load_csv


def _f(a):
    return np.asarray(a, dtype=float)


def time_breakdown(traj, cmd):
    t, vx, wz = _f(traj['t']), _f(traj['gt_vx']), _f(traj['gt_wz'])
    ok = np.isfinite(t) & np.isfinite(vx) & np.isfinite(wz)
    t, vx, wz = t[ok], vx[ok], wz[ok]
    dt = np.diff(t, prepend=t[0])
    moving = np.abs(vx) >= 0.05
    rot = (~moving) & (np.abs(wz) >= 0.05)
    still = ~(moving | rot)
    tot = max(dt.sum(), 1e-9)
    out = {'moving_pct': 100 * dt[moving].sum() / tot, 'rotating_in_place_pct': 100 * dt[rot].sum() / tot,
           'stationary_pct': 100 * dt[still].sum() / tot, 'total_s': tot}
    # commanded but not moving: command magnitude vs actual speed
    if cmd and 'source' in cmd and len(cmd['t']):
        src = np.asarray(cmd['source']).astype(str)
        m = src == 'ctrl_stamped'
        ct, cvx, cwz = _f(cmd['t'])[m], _f(cmd['vx'])[m], _f(cmd['wz'])[m]
        if ct.size:
            out['cmd_active_pct'] = 100 * np.mean((np.abs(cvx) > 0.01) | (np.abs(cwz) > 0.01))
            out['cmd_mean_vx'] = float(np.mean(np.abs(cvx)))
    return out


def stuck_spots(traj, min_s=8.0, radius=0.15):
    t, x, y = _f(traj['t']), _f(traj['gt_x']), _f(traj['gt_y'])
    ok = np.isfinite(x) & np.isfinite(y)
    t, x, y = t[ok], x[ok], y[ok]
    spots, i = [], 0
    while i < len(t):
        j = i
        while j + 1 < len(t) and np.hypot(x[j + 1] - x[i], y[j + 1] - y[i]) < radius:
            j += 1
        if t[j] - t[i] >= min_s:
            spots.append((float(x[i]), float(y[i]), float(t[j] - t[i]), float(t[i])))
            i = j + 1
        else:
            i += 1
    return spots


def goals(ge):
    rows = []
    if not ge or 'src' not in ge:
        return rows
    src = np.asarray(ge['src']).astype(str)
    ev = np.asarray(ge['event']).astype(str)
    res = np.asarray(ge['result']).astype(str)
    seq = np.asarray(ge['goal_seq']).astype(str)
    t = _f(ge['t'])
    x, y = _f(ge['x']), _f(ge['y'])
    code = np.asarray(ge['nav2_error_code']).astype(str)
    started = {}
    for k in range(len(src)):
        if src[k] not in ('explore', 'scripted'):
            continue
        if ev[k] == 'started' or res[k] == 'started':
            started[(src[k], seq[k])] = (t[k], x[k], y[k])
        elif ev[k] == 'ended':
            t0 = started.get((src[k], seq[k]), (np.nan, x[k], y[k]))
            rows.append(dict(seq=seq[k], t_start=t0[0], dur=t[k] - t0[0], x=x[k], y=y[k],
                             result=res[k], code=code[k]))
    return rows


def log_failures(run_dir):
    pats = [('planner: no valid path', r'failed to plan.*no valid path'),
            ('planner: start occupied', r'failed to plan.*Start occupied'),
            ('planner: goal occupied', r'failed to plan.*Goal occupied'),
            ('controller: failed to make progress', r'Failed to make progress'),
            ('controller: no valid trajectories (MPPI)', r'(?i)no valid (trajectories|control)|collision.*trajector'),
            ('controller: missed 20 Hz loop', r'Control loop missed'),
            ('drive controller: command timed out', r'Velocity command timed out'),
            ('costmap: cleared by recovery', r'Received request to clear'),
            ('tf: transform timeout / extrapolation', r'(?i)extrapolation|transform.*timeout|Timed out waiting for transform'),
            ('bt: failed to get result (halt)', r'Failed to get result for .* in node halt')]
    cnt = collections.Counter()
    for f in glob.glob(os.path.join(run_dir, 'logs', '*.log')):
        with open(f, errors='ignore') as fh:
            for line in fh:
                for name, p in pats:
                    if re.search(p, line):
                        cnt[name] += 1
                        break
    return cnt


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('run_dir')
    ap.add_argument('--png')
    a = ap.parse_args(argv)
    d = os.path.expanduser(a.run_dir)
    traj = load_csv(os.path.join(d, 'trajectory.csv'))
    cmdp = os.path.join(d, 'cmd_vel.csv')
    cmd = load_csv(cmdp) if os.path.exists(cmdp) else None
    gep = os.path.join(d, 'goal_events.csv')
    ge = load_csv(gep) if os.path.exists(gep) else None
    sm = json.load(open(os.path.join(d, 'summary.json'))) if os.path.exists(os.path.join(d, 'summary.json')) else {}

    print('RUN', d)
    print('  status=%s end_reason=%s episode=%ss rtf=%s' % (sm.get('status'), sm.get('end_reason'),
          sm.get('episode_sim_sec'), None if sm.get('rtf_mean') is None else round(sm['rtf_mean'], 2)))

    tb = time_breakdown(traj, cmd)
    print('\n1. WHERE THE TIME WENT (ground-truth motion)')
    print('   moving forward/back %.0f%% | rotating in place %.0f%% | stationary %.0f%%'
          % (tb['moving_pct'], tb['rotating_in_place_pct'], tb['stationary_pct']))
    if 'cmd_active_pct' in tb:
        print('   a velocity command was active %.0f%% of the time; mean |vx| commanded %.3f m/s'
              % (tb['cmd_active_pct'], tb['cmd_mean_vx']))

    gl = goals(ge)
    print('\n2. GOALS (%d ended)' % len(gl))
    for g in gl:
        print('   #%s  to (%.2f, %.2f)  %-12s %5.1fs  nav2_code=%s' %
              (g['seq'], g['x'], g['y'], g['result'], g['dur'], g['code']))
    res_count = collections.Counter(g['result'] for g in gl)
    if res_count:
        print('   outcome counts:', dict(res_count))

    fl = log_failures(d)
    print('\n3. FAILURE MESSAGES IN LOGS')
    for k, v in fl.most_common():
        print('   %5d  %s' % (v, k))

    print('\n4. LOCALIZATION vs NAVIGATION')
    for k in ['loc_error_mean_m', 'loc_error_p95_m', 'loc_converge_s', 'start_offset_m', 'start_offset_deg',
              'odom_drift_ratio', 'nav_success_pct', 'nav_success_gt_pct', 'n_est_gaps']:
        if sm.get(k) is not None:
            print('   %-20s %s' % (k, round(sm[k], 3) if isinstance(sm[k], float) else sm[k]))

    sp = stuck_spots(traj)
    print('\n5. WHERE THE ROBOT SAT STILL (>=8 s within 15 cm), world coordinates')
    for x, y, dur, t0 in sp[:10]:
        print('   (%.2f, %.2f) for %.0fs starting t=%.0f' % (x, y, dur, t0))
    if not sp:
        print('   none')

    # ranked causes
    causes = []
    n_goal = max(len(gl), 1)
    if fl['planner: start occupied'] + fl['planner: no valid path'] > 0.3 * max(sum(fl.values()), 1):
        causes.append((fl['planner: start occupied'] + fl['planner: no valid path'],
                       'PLANNER cannot find a path (%d "no valid path", %d "start occupied"): costmap is blocking the robot - '
                       'inflation/robot_radius too large for this room, a footprint smaller than the chassis, or obstacle-layer '
                       'ghosts from the depth scan' % (fl['planner: no valid path'], fl['planner: start occupied'])))
    if fl['drive controller: command timed out'] > 20:
        causes.append((fl['drive controller: command timed out'],
                       'COMMAND GAPS: diff_drive_controller braked %d times because commands stopped arriving for 0.5 s '
                       '(slow sim / smoother at low rate) -> jerky motion' % fl['drive controller: command timed out']))
    if tb['stationary_pct'] > 40:
        causes.append((tb['stationary_pct'], 'ROBOT IDLE %.0f%% of the episode (waiting, planning, or stuck)' % tb['stationary_pct']))
    if tb['rotating_in_place_pct'] > 25:
        causes.append((tb['rotating_in_place_pct'], 'SPINNING %.0f%% of the time: Nav2 recovery spins/bootstrap turns, not cleaning' % tb['rotating_in_place_pct']))
    if sm.get('loc_error_mean_m') and sm['loc_error_mean_m'] > 0.3:
        causes.append((sm['loc_error_mean_m'] * 100, 'LOCALIZATION error %.2f m: Nav2 believes it reached goals it did not (success by Nav2 %s%% vs by ground truth %s%%)' %
                       (sm['loc_error_mean_m'], sm.get('nav_success_pct'), sm.get('nav_success_gt_pct'))))
    if sm.get('rtf_mean') and sm['rtf_mean'] < 0.6:
        causes.append(((1 - sm['rtf_mean']) * 100, 'SLOW SIM (real-time factor %.2f): controllers see stale data, 20 Hz loops are missed' % sm['rtf_mean']))
    if sp and sum(s[2] for s in sp) > 0.25 * tb['total_s']:
        causes.append((sum(s[2] for s in sp), 'STUCK SPOTS account for %.0f s - see section 5 for where' % sum(s[2] for s in sp)))
    if sm.get('coverage_explored_pct') and sm.get('coverage_cleaned_pct') and sm['coverage_cleaned_pct'] < 0.4 * sm['coverage_explored_pct']:
        causes.append((10, 'LOW CLEANED vs EXPLORED: the explorer drives to frontiers (it is not a coverage planner), and the swath is only 0.25 m wide; '
                           'driven distance %.1f m x 0.25 m = %.1f m2 at best' % (sm.get('distance_gt_m', 0), 0.25 * sm.get('distance_gt_m', 0))))
    causes.sort(key=lambda c: -c[0])
    print('\n6. LIKELY CAUSES (ranked)')
    for _, c in causes:
        print('   -', c)
    if not causes:
        print('   nothing stands out')

    if any(k.startswith('health_') for k in sm):
        print('\n7. METRIC HEALTH (ok=%s bad=%s suspect=%s unmeasurable=%s)' % (
            sm.get('health_n_ok'), sm.get('health_n_bad'), sm.get('health_n_suspect'),
            sm.get('health_n_unmeasurable')))
        for k in sorted(sm):
            if k.startswith('health_') and not k.endswith('_reasons') and not k.startswith('health_n_'):
                print('   %-28s %-13s %s' % (k[7:], sm[k], ', '.join(sm.get(k + '_reasons') or [])))

    if a.png:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        x, y = _f(traj['gt_x']), _f(traj['gt_y'])
        v = np.abs(_f(traj['gt_vx']))
        fig, ax = plt.subplots(figsize=(7, 6))
        sc = ax.scatter(x, y, c=v, s=4, cmap='viridis')
        for sx, sy, dur, _ in sp:
            ax.add_patch(plt.Circle((sx, sy), 0.15, color='red', fill=False))
            ax.text(sx, sy, '%.0fs' % dur, color='red', fontsize=7)
        for g in gl:
            ax.plot(g['x'], g['y'], 'x', color='green' if g['result'] == 'succeeded' else 'orange')
        ax.set_aspect('equal')
        plt.colorbar(sc, label='|vx| m/s')
        ax.set_title('trajectory (colour=speed), red=stuck, x=goals (green ok)')
        fig.savefig(a.png, dpi=110)
        print('\nwrote', a.png)


if __name__ == '__main__':
    main()
