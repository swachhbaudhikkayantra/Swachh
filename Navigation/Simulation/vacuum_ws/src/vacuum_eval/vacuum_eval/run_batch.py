#!/usr/bin/env python3
"""Sequential batch runner (docs/specs/02 section 2.10).

Matrix yaml: experiment, worlds, methods, seeds, odom_noise (lists), optional headless, goal_lists, nav_maps, stacks (method specific),
timeout_sim_sec, runs_root, pause_sec."""

import argparse
import hashlib
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


def load_splits():
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(here, '..', 'config', 'worlds.yaml'),
              os.path.join(here, 'config', 'worlds.yaml')):
        if os.path.isfile(p):
            return yaml.safe_load(open(p))
    raise FileNotFoundError('worlds.yaml')


def check_split(split, m, cfg, confirm):
    """Return an error string (caller exits 2) or None."""
    other = 'test' if split == 'dev' else 'dev'
    bad_w = [w for w in m['worlds'] if w in cfg['splits'][other] or w not in cfg['splits'][split]]
    bad_s = [s for s in m['seeds'] if s in cfg['seeds'][other] or s not in cfg['seeds'][split]]
    if bad_w:
        return 'worlds not in %s split: %s' % (split, bad_w)
    if bad_s:
        return 'seeds not in %s split: %s' % (split, bad_s)
    if split == 'test' and not confirm:
        return 'test split requires --confirm-test-split'
    return None


def git_commit():
    try:
        import subprocess
        return subprocess.check_output(['git', '-C', os.path.dirname(os.path.abspath(__file__)),
                                        'rev-parse', 'HEAD'], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:  # noqa: BLE001
        return None


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
    ap.add_argument('--split', choices=['dev', 'test'], default=None,
                    help='refuse worlds/seeds outside this split (default: matrix key split, if any)')
    ap.add_argument('--confirm-test-split', action='store_true',
                    help='required to run the frozen test split')
    a = ap.parse_args(argv)
    mpath = os.path.expanduser(a.matrix)
    raw = open(mpath, 'rb').read()
    m = yaml.safe_load(raw)
    chash = hashlib.sha256(raw).hexdigest()
    split = a.split or m.get('split')
    if a.split and m.get('split') and m['split'] != a.split:
        print('error: matrix declares split %s but --split %s' % (m['split'], a.split),
              file=sys.stderr)
        return 2
    if split:
        err = check_split(split, m, load_splits(), a.confirm_test_split)
        if err:
            print('error: ' + err, file=sys.stderr)
            return 2
    if not a.dry_run:
        mr = os.path.join(os.path.expanduser(m.get('runs_root', '~/eval_runs')), m['experiment'])
        os.makedirs(mr, exist_ok=True)
        with open(os.path.join(mr, 'batch_manifest.json'), 'w') as f:
            json.dump({'campaign': os.path.abspath(mpath), 'campaign_sha256': chash,
                       'git_commit': git_commit(), 'split': split, 'time': time.time()}, f,
                      indent=1)
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
