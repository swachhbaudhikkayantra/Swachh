#!/usr/bin/env python3
"""Sequential batch runner (docs/specs/02 section 2.10).

Matrix yaml: experiment, worlds, methods, seeds, odom_noise (lists), optional headless, goal_lists, nav_maps, stacks (method specific),
timeout_sim_sec, runs_root, pause_sec."""

import argparse
import hashlib
import itertools
import json
import os
import queue
import subprocess
import sys
import threading
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


def run_jobs(jobs, k, runner, stagger=60.0, sleep=time.sleep, out=print):
    """Run jobs [(tag, args)] on K slots (0..K-1); each slot takes the next job when free.
    First start of slot i is delayed i*stagger s. runner(args, slot)->rc.
    Returns {tag: (slot, rc)} and prints a progress table row per completion."""
    q = queue.Queue()
    for j in jobs:
        q.put(j)
    results, lock, done = {}, threading.Lock(), [0]

    def worker(slot):
        if slot and stagger:
            sleep(slot * stagger)
        while True:
            try:
                tag, args = q.get_nowait()
            except queue.Empty:
                return
            try:
                rc = runner(args, slot)
            except Exception as e:  # noqa: BLE001
                rc = 99
                out('slot %d error: %r' % (slot, e))
            with lock:
                results[tag] = (slot, rc)
                done[0] += 1
                out('[%d/%d] slot=%d rc=%d %s' % (done[0], len(jobs), slot, rc, tag))

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(max(1, min(k, len(jobs) or 1)))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return results


def subprocess_runner(args, slot):
    return subprocess.call([sys.executable, '-m', 'vacuum_eval.run_episode'] + args +
                           ['--slot', str(slot)])


def inprocess_runner(args, slot):
    return run_episode.main(args + ['--slot', str(slot)])


def prebuild_gt(m):
    from vacuum_eval import compute_metrics as cm
    cfg = cm.load_worlds_cfg()
    for w in m['worlds']:
        cm.gt_grid_for(w, cfg)
        print('gt ready: %s' % w, flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Run a matrix of episodes')
    ap.add_argument('--matrix', required=True)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--parallel', type=int, default=None,
                    help='K parallel slots (default: matrix key parallel, else 1)')
    ap.add_argument('--stagger-sec', type=float, default=60.0)
    ap.add_argument('--lean', type=int, choices=[0, 1], default=None,
                    help='default 1 for batch (matrix key lean overrides default)')
    ap.add_argument('--gpu', type=int, choices=[0, 1], default=None)
    ap.add_argument('--prebuild-gt', action='store_true',
                    help='build all worlds GT grids, then run (with --dry-run: build and exit)')
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
    if a.prebuild_gt:
        prebuild_gt(m)
        if a.dry_run:
            return 0
    k = max(1, int(a.parallel if a.parallel is not None else m.get('parallel', 1)))
    lean = int(a.lean if a.lean is not None else m.get('lean', 1))
    gpu = int(a.gpu if a.gpu is not None else m.get('gpu', 0))
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
    status, jobs = [], []
    for i, (w, me, sd, n, vd, va) in enumerate(combos, 1):
        tag = '%s/%s/seed_%03d/noise%d' % (w, vd, sd, n)
        # odom_noise is not part of the run-dir path: give noisy runs their own experiment slug
        exp = m['experiment'] + ('_noise' if n else '')
        if finished(root, exp, w, vd, sd) and not a.force:
            status.append((tag, 'skipped'))
        elif a.dry_run:
            status.append((tag, 'dry'))
        else:
            args = ['--experiment', exp, '--world', w, '--method', me, '--seed', str(sd),
                    '--odom-noise', str(int(n)), '--headless', str(int(m.get('headless', 1))),
                    '--runs-root', root, '--lean', str(lean), '--gpu', str(gpu)] + va
            if m.get('timeout_sim_sec'):
                args += ['--timeout-sim-sec', str(m['timeout_sim_sec'])]
            if a.force:
                args.append('--force')
            jobs.append((tag, args))
            continue
        print('[%d/%d] %s %s' % (i, len(combos), *status[-1]), flush=True)
    if jobs:
        if k == 1:
            for tag, args in jobs:
                rc = inprocess_runner(args, 0)
                print('[slot 0] rc=%d %s' % (rc, tag), flush=True)
                time.sleep(pause)
        else:
            run_jobs(jobs, k, subprocess_runner, a.stagger_sec)
    return 0


if __name__ == '__main__':
    sys.exit(main())
