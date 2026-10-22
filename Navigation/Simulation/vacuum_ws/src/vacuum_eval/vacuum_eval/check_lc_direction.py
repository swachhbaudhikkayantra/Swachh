"""Check RTAB-Map loop-closure transform direction against ground truth.

Usage: python3 -m vacuum_eval.check_lc_direction <run_dir> [<run_dir> ...]
Exit 0 = clear winner, 2 = ambiguous / no data.
"""

import argparse
import math
import sys

import numpy as np

from .metrics.common import load_run, wrap_angle
from .metrics.loop_closure import expected_tf, node_poses

TRANS_OK_M = 0.10
ROT_OK_DEG = 5.0


def closure_errors(run):
    """[(ref, loop, {convention: (trans_err_m, rot_err_deg)})] for accepted closures."""
    le = run.loop_events
    if le is None or not all(k in le for k in ('ref_id', 'loop_closure_id', 'lc_tx', 'lc_ty', 'lc_tyaw')):
        return []
    nodes = node_poses(le)
    out, seen = [], set()
    for k in range(len(le['ref_id'])):
        a, b = int(le['ref_id'][k]), int(le['loop_closure_id'][k])
        if b <= 0 or (a, b) in seen or a not in nodes or b not in nodes:
            continue
        tf = (float(le['lc_tx'][k]), float(le['lc_ty'][k]), float(le['lc_tyaw'][k]))
        pa, pb = nodes[a], nodes[b]
        if any(math.isnan(v) for v in tf + pa[1:] + pb[1:]):
            continue
        seen.add((a, b))
        errs = {}
        for conv in ('ref_to_loop', 'loop_to_ref'):
            g = expected_tf(pa, pb, conv)
            errs[conv] = (math.hypot(g[0] - tf[0], g[1] - tf[1]),
                          abs(math.degrees(wrap_angle(g[2] - tf[2]))))
        out.append((a, b, errs))
    return out


def verdict(rows):
    """Returns (winner or None, stats {conv: (median_t, median_r, n_ok)})."""
    stats = {}
    for conv in ('ref_to_loop', 'loop_to_ref'):
        if not rows:
            stats[conv] = (float('nan'), float('nan'), 0)
            continue
        t = np.array([r[2][conv][0] for r in rows])
        r_ = np.array([r[2][conv][1] for r in rows])
        stats[conv] = (float(np.median(t)), float(np.median(r_)),
                       int(np.sum((t <= TRANS_OK_M) & (r_ <= ROT_OK_DEG))))
    good = [c for c, (mt, mr, _) in stats.items() if mt < TRANS_OK_M and mr < ROT_OK_DEG]
    return (good[0] if len(good) == 1 else None), stats


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='Check RTAB-Map loop-closure transform direction against ground truth.',
        epilog='Exit 0 = clear winner, 2 = ambiguous / no data.')
    ap.add_argument('run_dirs', nargs='*', metavar='run_dir')
    a = ap.parse_args(argv)
    if not a.run_dirs:
        ap.print_usage()
        return 2
    rows = []
    for d in a.run_dirs:
        rows += closure_errors(load_run(d))
    print('%6s %6s | %s | %s' % ('ref', 'loop', 'ref_to_loop (m, deg)', 'loop_to_ref (m, deg)'))
    for a, b, e in rows:
        print('%6d %6d | %9.3f %9.2f | %9.3f %9.2f' % ((a, b) + e['ref_to_loop'] + e['loop_to_ref']))
    win, stats = verdict(rows)
    if not rows:
        print('VERDICT: no accepted closures with lc_tx/ty/tyaw; ambiguous')
        return 2
    for c, (mt, mr, n) in stats.items():
        print('%s: median trans %.3f m, rot %.2f deg, %d/%d closures within tol' % (c, mt, mr, n, len(rows)))
    if win is None:
        print('VERDICT: ambiguous (neither or both conventions look correct)')
        return 2
    print('VERDICT: %s (%d/%d closures support it)' % (win, stats[win][2], len(rows)))
    print('Set in eval_defaults.yaml:\nlc_transform_convention: %s' % win)
    return 0


if __name__ == '__main__':
    sys.exit(main())
