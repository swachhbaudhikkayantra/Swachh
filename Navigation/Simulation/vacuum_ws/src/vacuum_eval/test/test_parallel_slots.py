import os
import threading

import numpy as np

from vacuum_eval import compute_metrics as cm
from vacuum_eval import run_batch, run_episode as re_


def test_slot_env():
    assert re_.slot_env(0) == (0, 'vacuum_slot0')
    assert re_.slot_env(3) == (13, 'vacuum_slot3')
    e = re_.build_ros_env(2)
    assert 'ROS_DOMAIN_ID=12;' in e and 'GZ_PARTITION=vacuum_slot2' in e and 'ROS_LOCALHOST_ONLY=1' in e
    assert 'ROS_DOMAIN_ID=0;' in re_.build_ros_env(0)


def test_lock(tmp_path):
    r = str(tmp_path)
    assert re_.acquire_slot_lock(1, r, pid=111, alive=lambda p: True)
    assert not re_.acquire_slot_lock(1, r, pid=222, alive=lambda p: True)
    assert re_.acquire_slot_lock(1, r, pid=222, alive=lambda p: False)  # stale
    assert re_.acquire_slot_lock(2, r, pid=333, alive=lambda p: True)  # other slot independent
    re_.release_slot_lock(1, r, pid=222)
    assert not os.path.exists(re_._lock_path(1, r))


def test_partition_scan(tmp_path):
    for pid, part in ((101, 'vacuum_slot0'), (102, 'vacuum_slot1')):
        d = tmp_path / str(pid)
        d.mkdir()
        (d / 'environ').write_bytes(b'A=1\0GZ_PARTITION=' + part.encode() + b'\0')
        (d / 'cmdline').write_bytes(b'gz\0sim\0')
    assert re_.pids_with_partition('vacuum_slot1', str(tmp_path)) == [102]
    assert re_.pids_with_partition('vacuum_slot5', str(tmp_path)) == []


def test_lean_bag():
    assert '/clock' in re_.bag_topics(0).split()
    t = re_.bag_topics(1).split()
    assert '/clock' not in t and '/joint_states' not in t and '/tf' in t and '/tf_static' in t


def test_run_jobs_slots():
    jobs = [('j%d' % i, [str(i)]) for i in range(6)]
    seen, lk = [], threading.Lock()

    def runner(args, slot):
        with lk:
            seen.append(slot)
        return 0
    res = run_batch.run_jobs(jobs, 3, runner, stagger=0, out=lambda *_: None)
    assert len(res) == 6 and set(seen) <= {0, 1, 2}
    assert all(v[1] == 0 for v in res.values())


def test_gt_cache_atomic(tmp_path, monkeypatch):
    calls = {}

    def fake_save(gt, path):
        calls['tmp'] = path
        open(path, 'wb').write(b'x')
    monkeypatch.setattr(cm.gt_grid, 'save', fake_save)
    monkeypatch.setattr(cm.gt_grid, 'build', lambda *a, **k: object())
    monkeypatch.setattr(cm, 'resolve_sdf', lambda p: p)
    cfg = {'worlds': {'w': {'sdf_file': 'f', 'reachable_seed': [0, 0]}}}
    cm.gt_grid_for('w', cfg, gt_dir=str(tmp_path))
    assert calls['tmp'] != str(tmp_path / 'w.npz') and (tmp_path / 'w.npz').exists()
    assert os.listdir(tmp_path) == ['w.npz']
