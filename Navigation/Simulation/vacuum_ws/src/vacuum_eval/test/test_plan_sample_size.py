import math

from vacuum_eval import plan_sample_size as ps


def test_proportion_hand():
    # goals = 1.96^2*.24/.01 = 92.198; DE = 1+7*.1 = 1.7; /8 -> 19.59 -> 20
    n, ng = ps.episodes_proportion(0.6, 8, 0.1, 0.10)
    assert abs(ng - 92.198) < 0.01 and n == 20
    assert ps.episodes_proportion(0.6, 8, 0.0, 0.10)[0] == 12


def test_continuous_hand():
    # sd=2,hw=1: n=18 -> t(17)=2.110*2/4.243=0.995 <=1 ; n=17 -> 2.120*2/4.123=1.028
    assert ps.episodes_continuous(2.0, 1.0) == 18


def test_cli_prints(capsys):
    n = ps.main(['--metric-kind', 'proportion', '--p', '0.6', '--goals-per-episode', '8',
                 '--icc', '0.1', '--target-halfwidth', '0.10', '--episode-wall-min', '30'])
    assert n == 20 and 'wall-time' in capsys.readouterr().out
    assert math.isclose(ps.design_effect(8, 0.1), 1.7)


def test_icc_estimate():
    assert ps.anova_icc([[1, 1, 1], [0, 0, 0], [1, 1, 1], [0, 0, 0]]) > 0.95
