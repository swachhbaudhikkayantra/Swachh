"""Unit tests for vacuum_eval.paper_tables (synthetic data, no run folders needed)."""
import pytest

from vacuum_eval import paper_tables as pt


def _ep(world, seed, total, gt_pct, nav2, status='ok'):
    return dict(status=status, world=world, _world=world, _seed=seed, _path='x',
                nav_goals_total=total, nav_success_gt_pct=gt_pct, nav_goals_succeeded=nav2)


def test_gt_successes_integral():
    assert pt.gt_successes(_ep('a', 1, 20, 25.0, 5), 'nav_success_gt_pct') == 5
    assert pt.gt_successes(_ep('a', 1, 8, 12.5, 1), 'nav_success_gt_pct') == 1
    assert pt.gt_successes(_ep('a', 1, 20, None, 5), 'nav_success_gt_pct') is None


def test_gt_successes_rejects_fractional():
    with pytest.raises(ValueError):
        pt.gt_successes(_ep('a', 1, 7, 10.0, 1), 'nav_success_gt_pct')


def test_pooled_rate_known_values():
    eps = [_ep('a', 1, 10, 50.0, 5), _ep('a', 2, 10, 0.0, 0), _ep('b', 3, 20, 25.0, 10)]
    r = pt.pooled_rate(eps, lambda e: pt.gt_successes(e, 'nav_success_gt_pct'),
                       lambda e: pt.num(e['nav_goals_total']))
    assert (r['k'], r['n'], r['episodes']) == (10, 40, 3)
    assert r['pct'] == pytest.approx(25.0)


def test_pooled_rate_counts_only_contributing_episodes():
    eps = [dict(a=3, b=4), dict(a=0, b=0), dict(a=0, b=0)]
    r = pt.pooled_rate(eps, lambda e: e['a'], lambda e: e['b'])
    assert r['episodes'] == 1 and r['pct'] == pytest.approx(75.0)


def test_num_handles_missing():
    assert pt.num(None) is None and pt.num('') is None and pt.num(float('nan')) is None
    assert pt.num('2.5') == 2.5


def test_stat_mean_sd():
    s = pt.stat([dict(x=1.0), dict(x=2.0), dict(x=3.0), dict(x=None)], 'x')
    assert s['n'] == 3 and s['mean'] == pytest.approx(2.0) and s['sd'] == pytest.approx(1.0)


def test_template_fill_and_missing():
    V = dict(a=dict(b=12.345), c=None)
    out, miss = pt.fill('x {{a.b|f1}} y {{a.b|int}} z {{c}} {{nope}}', V)
    assert out.startswith('x 12.3 y 12 z n/a') and miss == ['nope']
