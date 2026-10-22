from vacuum_eval.metrics import health as h


def base(**kw):
    s = dict(world='apartment', method='rtabmap', status='ok', rtf_true_mean=0.5, odom_corrupted_by_contact=0,
             coverage_explored_pct=90, n_goals=10, n_cmd_ticks=100, n_collisions=0, avoidance_pct=95,
             n_encounters=10, responsiveness_pct=90, resp_n_events=20, ate_fixed_rmse_m=0.1,
             rpe_trans_rmse_m_1m=0.1, map_completeness_pct=80, nav_success_gt_pct=80, nav_success_pct=80,
             nav_goals_total=10, lc_precision_pct=90, lc_n_accepted=10, lc_recall_pct=90, lc_n_revisits=5,
             lc_n_nodes=50, path_length_ratio_mean=1.2, path_length_ratio_n=8, cleaning_efficiency=0.3,
             start_offset_m=0.1, notes=[])
    s.update(kw)
    return s


def st(m, **kw):
    o = h.compute_health(base(**kw))
    return o['health_' + m], o['health_%s_reasons' % m]


def test_ok_and_counts():
    o = h.compute_health(base())
    assert o['health_coverage_explored_pct'] == 'OK'
    assert o['health_trial_success'] == 'NA'
    assert o['health_n_ok'] == 13 and o['health_n_bad'] == 0


def test_na():
    assert st('trial_success')[0] == 'NA'
    assert st('responsiveness_pct', method='frontier')[0] == 'NA'
    s = base()
    for k in ('lc_n_nodes', 'lc_n_accepted', 'lc_n_revisits', 'lc_precision_pct', 'lc_recall_pct'):
        s.pop(k)
    assert h.compute_health(s)['health_lc_precision_pct'] == 'NA'
    assert st('trial_success', world='avoid_static', trial_success=1)[0] == 'OK'


def test_low_n():
    assert st('nav_success_gt_pct', nav_goals_total=3) == ('LOW_N', ['LOW_N:3/5'])
    assert st('lc_recall_pct', lc_n_revisits=2)[1] == ['LOW_N:2/3']


def test_unmeasurable():
    assert st('ate_fixed_rmse_m', ate_fixed_rmse_m=None) == ('UNMEASURABLE', ['NO_DATA'])
    assert st('avoidance_pct', avoidance_pct=None, n_encounters=0) == ('UNMEASURABLE', ['NO_EVENTS'])
    assert st('lc_precision_pct', lc_precision_pct=None, lc_n_accepted=0)[1] == ['NO_EVENTS']
    assert 'INVALID_EPISODE' in st('n_collisions', status='invalid')[1]
    assert st('coverage_explored_pct', coverage_explored_pct=None,
              notes=['coverage: ground-truth grid unavailable: x'])[1] == ['GT_MISSING']
    assert st('map_completeness_pct', map_completeness_pct=None, notes=['x: map missing'])[1] == ['MAP_MISSING']


def test_suspect():
    assert st('ate_fixed_rmse_m', odom_corrupted_by_contact=1)[1][0] == 'ODOM_CORRUPTED'
    assert st('rpe_trans_rmse_m_1m', odom_corrupted_by_contact=1)[0] == 'SUSPECT'
    assert st('map_completeness_pct', start_offset_m=2.0)[1] == ['FRAME_OFFSET']
    assert 'FRAME_OFFSET' in st('coverage_explored_pct', map_align_dx_m=1.0, map_align_dy_m=1.0)[1]
    assert st('coverage_explored_pct', coverage_explored_pct=120)[1] == ['RANGE']
    assert st('cleaning_efficiency', cleaning_efficiency=-1)[1] == ['RANGE']
    assert st('nav_success_gt_pct', nav_success_pct=90, nav_success_gt_pct=50)[1] == ['NAV_GT_DIVERGENCE']
    assert st('n_collisions', rtf_true_mean=0.1) == ('SUSPECT', ['LOW_RTF'])
    assert st('lc_precision_pct', lc_rot_err_median_deg=6.0, lc_reg_rot_tol_deg=5.0)[1] == ['LC_ROT_BIAS']
    assert st('lc_precision_pct', lc_rot_err_median_deg=9.0, lc_reg_rot_tol_deg=5.0)[0] == 'OK'


def test_bad_and_precedence():
    assert st('coverage_explored_pct', coverage_explored_pct=50) == ('BAD', ['BELOW_FLOOR:50<70'])
    assert st('ate_fixed_rmse_m', ate_fixed_rmse_m=0.5) == ('BAD', ['BELOW_FLOOR:0.5>0.3'])
    s, r = st('nav_success_gt_pct', nav_success_gt_pct=10, nav_success_pct=10, nav_goals_total=3)
    assert s == 'LOW_N' and r == ['LOW_N:3/5', 'BELOW_FLOOR:10<50']
    s, r = st('ate_fixed_rmse_m', ate_fixed_rmse_m=3.0, odom_corrupted_by_contact=1)
    assert s == 'SUSPECT' and len(r) == 2
