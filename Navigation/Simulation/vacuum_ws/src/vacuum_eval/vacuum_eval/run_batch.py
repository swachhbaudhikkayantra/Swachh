#!/usr/bin/env python3
"""Sequential batch runner (docs/specs/02 section 2.10).

Matrix yaml: experiment, worlds, methods, seeds, odom_noise (lists), optional headless, goal_lists, nav_maps, stacks (method specific),
timeout_sim_sec, runs_root, pause_sec."""

import argparse
import itertools
import json
import os
import sys
import time

import yaml

from vacuum_eval import run_episode


def variants(method, m):
    """[(dir_name, extra_args)] for the method-specific matrix keys goal_lists, nav_maps, stacks."""
    if method == 'scripted_goals':
        out = []
        for nm in m.get('nav_maps', ['gt']):
            for gl in m.get('goal_lists', [None]):
                out.append((run_episode.method_dir_name(method, gl, nm),
                            ['--nav-map', nm] + (['--goal-list', gl] if gl else [])))
        return out
    if method == 'responsiveness':
        return [(run_episode.method_dir_name(method, stack=st), ['--stack', st])
                for st in m.get('stacks', ['bare'])]
    return [(method, [])]


def finished(runs_root, exp, world, method, seed):
    p = os.path.join(os.path.expanduser(runs_root), exp, world, method, 'seed_%03d' % seed,
                     'summary.json')
    try:
        return json.load(open(p)).get('status') == 'ok'
    except Exception:  # noqa: BLE001
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description='Run a matrix of episodes')
    ap.add_argument('--matrix', required=True)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    m = yaml.safe_load(open(os.path.expanduser(a.matrix)))
    root = m.get('runs_root', '~/eval_runs')
    combos = [(w, me, s, n, vd, va)
              for w, me, s, n in itertools.product(m['worlds'], m.get('methods', ['frontier']),
                                                   m['seeds'], m.get('odom_noise', [0]))
              for vd, va in variants(me, m)]
    pause = float(m.get('pause_sec', 10))
    status = []
    for i, (w, me, s, n, vd, va) in enumerate(combos, 1):
        tag = '%s/%s/seed_%03d/noise%d' % (w, vd, s, n)
        # odom_noise is not part of the run-dir path: give noisy runs their own experiment slug
        exp = m['experiment'] + ('_noise' if n else '')
        if finished(root, exp, w, vd, s) and not a.force:
            status.append((tag, 'skipped'))
        elif a.dry_run:
            status.append((tag, 'dry'))
        else:
            args = ['--experiment', exp, '--world', w, '--method', me, '--seed', str(s),
                    '--odom-noise', str(int(n)), '--headless', str(int(m.get('headless', 1))),
                    '--runs-root', root] + va
            if m.get('timeout_sim_sec'):
                args += ['--timeout-sim-sec', str(m['timeout_sim_sec'])]
            if a.force:
                args.append('--force')
            rc = run_episode.main(args)
            status.append((tag, 'rc=%d' % rc))
            time.sleep(pause)
        print('[%d/%d] %s %s' % (i, len(combos), *status[-1]), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
