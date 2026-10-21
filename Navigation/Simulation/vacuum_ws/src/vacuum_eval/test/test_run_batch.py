import glob
import os

import pytest
import yaml

from vacuum_eval import run_batch

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = yaml.safe_load(open(os.path.join(HERE, '..', 'config', 'worlds.yaml')))
CAMPS = sorted(glob.glob(os.path.join(HERE, '..', 'config', 'campaigns', '*.yaml')))
SDFS = {os.path.basename(p)[:-4] for p in
        glob.glob(os.path.join(HERE, '..', '..', 'vacuum_gazebo', 'worlds', '*.sdf'))}


def test_cross_split_refused(tmp_path):
    m = tmp_path / 'm.yaml'
    m.write_text('experiment: x\nworlds: [office]\nseeds: [1]\n')
    assert run_batch.main(['--matrix', str(m), '--split', 'dev', '--dry-run']) == 2
    m.write_text('experiment: x\nworlds: [apartment]\nseeds: [101]\n')
    assert run_batch.main(['--matrix', str(m), '--split', 'dev', '--dry-run']) == 2


def test_test_split_needs_confirm(tmp_path):
    m = tmp_path / 'm.yaml'
    m.write_text('experiment: x\nworlds: [office]\nseeds: [101]\n')
    assert run_batch.main(['--matrix', str(m), '--split', 'test', '--dry-run']) == 2
    assert run_batch.main(['--matrix', str(m), '--split', 'test', '--confirm-test-split',
                           '--dry-run']) == 0


@pytest.mark.parametrize('path', CAMPS)
def test_campaign_valid(path):
    m = yaml.safe_load(open(path))
    sp = m['split']
    assert run_batch.check_split(sp, m, CFG, True) is None
    for w in m['worlds']:
        assert w in SDFS
    for me in m['methods']:
        assert me in ('frontier', 'scripted_goals', 'responsiveness')
    assert run_batch.main(['--matrix', path, '--dry-run'] +
                          (['--confirm-test-split'] if sp == 'test' else [])) == 0


def test_campaigns_present():
    assert len(CAMPS) >= 5
