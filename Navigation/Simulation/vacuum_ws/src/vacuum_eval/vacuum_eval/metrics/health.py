"""Per-metric HEALTH classification (OK / LOW_N / UNMEASURABLE / SUSPECT / BAD / NA).

Runs LAST on the merged summary dict. Floors are pre-registered diagnosis triggers, never exclusions.
Precedence: UNMEASURABLE > SUSPECT > LOW_N > BAD > OK; all reasons are kept in a list.
"""

import math

DEFAULTS = {
    'min_n': {'goals': 5, 'encounters': 3, 'lc_accepted': 5, 'lc_revisits': 3, 'resp_events': 10},
    'floors': {'nav_success_gt_pct': 50, 'coverage_explored_pct': 70, 'map_completeness_pct': 60,
               'ate_fixed_rmse_m': 0.30, 'lc_precision_pct': 50, 'avoidance_pct': 80},
    'suspect': {'nav_gt_divergence_pp': 30, 'min_rtf': 0.15, 'frame_offset_m': 0.5,
                'map_align_shift_m': 0.5, 'lc_rot_bias_margin_deg': 2.0},
}
UPPER_FLOOR = ('ate_fixed_rmse_m',)          # BAD if value is ABOVE the floor
STATUS_ORDER = ('UNMEASURABLE', 'SUSPECT', 'LOW_N', 'BAD', 'OK')
ODOM_AFFECTED = ('ate_fixed_rmse_m', 'rpe_trans_rmse_m_1m', 'map_completeness_pct', 'coverage_explored_pct')
OFFSET_AFFECTED = ('ate_fixed_rmse_m', 'map_completeness_pct', 'coverage_explored_pct')
PCT_METRICS = ('coverage_explored_pct', 'avoidance_pct', 'responsiveness_pct', 'map_completeness_pct',
               'nav_success_gt_pct', 'lc_precision_pct', 'lc_recall_pct')
GT_METRICS = ('coverage_explored_pct', 'map_completeness_pct', 'nav_success_gt_pct', 'avoidance_pct',
              'n_collisions')
# metric -> (events key, min_n key)
EVENTS = {'n_goals': ('n_goals', 'goals'), 'avoidance_pct': ('n_encounters', 'encounters'),
          'responsiveness_pct': ('resp_n_events', 'resp_events'),
          'nav_success_gt_pct': ('nav_goals_total', 'goals'),
          'lc_precision_pct': ('lc_n_accepted', 'lc_accepted'), 'lc_recall_pct': ('lc_n_revisits', 'lc_revisits'),
          'path_length_ratio_mean': ('path_length_ratio_n', 'goals')}
METRICS = ['coverage_explored_pct', 'n_goals', 'n_collisions', 'avoidance_pct', 'responsiveness_pct',
           'ate_fixed_rmse_m', 'rpe_trans_rmse_m_1m', 'map_completeness_pct', 'trial_success',
           'nav_success_gt_pct', 'lc_precision_pct', 'lc_recall_pct', 'path_length_ratio_mean',
           'cleaning_efficiency']
# fallbacks to report when a metric is UNMEASURABLE / LOW_N / SUSPECT (used by make_report)
FALLBACKS = {'lc_precision_pct': ['lc_precision_samepose_pct', 'lc_precision_loose_pct'],
             'ate_fixed_rmse_m': ['ate_fixed_rmse_m_pre_corrupt'],
             'nav_success_gt_pct': ['nav_success_pct'],
             'rpe_trans_rmse_m_1m': ['rpe_trans_rmse_m_5s']}
FALLBACK_LABELS = {'nav_success_pct': 'nav_success_pct (Nav2-reported)'}


def _num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _merge(cfg):
    out = {k: dict(v) for k, v in DEFAULTS.items()}
    for k, v in (cfg or {}).items():
        if isinstance(v, dict) and k in out:
            out[k].update(v)
    return out


def _applicable(metric, s):
    world, method = str(s.get('world') or ''), str(s.get('method') or '')
    if metric == 'trial_success':
        return world.startswith('avoid')
    if metric == 'responsiveness_pct':
        return method != 'frontier'
    if metric in ('lc_precision_pct', 'lc_recall_pct'):
        return any(k in s for k in ('lc_n_nodes', 'lc_n_accepted', 'lc_n_revisits', 'lc_precision_pct'))
    return True


def _classify(metric, s, c):
    ev_key, min_key = EVENTS.get(metric, (None, None))
    val = _num(s.get(metric))
    notes = ' '.join(str(n) for n in (s.get('notes') or []))
    unm, sus, low, bad = [], [], [], []
    if s.get('status') == 'invalid':
        unm.append('INVALID_EPISODE')
    if val is None:
        if metric in GT_METRICS and 'ground-truth' in notes:
            unm.append('GT_MISSING')
        elif metric == 'map_completeness_pct' and 'map' in notes.lower() and s.get('map_completeness_pct') is None \
                and 'ground-truth' not in notes:
            unm.append('MAP_MISSING')
        elif ev_key and _num(s.get(ev_key)) == 0:
            unm.append('NO_EVENTS')
        elif metric == 'n_goals' and _num(s.get('n_cmd_ticks')) == 0:
            unm.append('NO_EVENTS')
        elif 'INVALID_EPISODE' not in unm:
            unm.append('NO_DATA')
    elif ev_key and _num(s.get(ev_key)) == 0 and metric != 'n_goals':
        unm.append('NO_EVENTS')
    if val is not None:
        sp = c['suspect']
        if _num(s.get('odom_corrupted_by_contact')) == 1 and metric in ODOM_AFFECTED:
            sus.append('ODOM_CORRUPTED')
        if metric in OFFSET_AFFECTED:
            so = _num(s.get('start_offset_m'))
            dx, dy = _num(s.get('map_align_dx_m')), _num(s.get('map_align_dy_m'))
            shift = math.hypot(dx, dy) if dx is not None and dy is not None else None
            if (so is not None and so > sp['frame_offset_m']) or \
                    (shift is not None and shift > sp['map_align_shift_m']):
                sus.append('FRAME_OFFSET')
        if (metric in PCT_METRICS and not 0 <= val <= 100) or \
                (metric not in ('trial_success',) and val < 0 and metric != 'ate_aligned'):
            sus.append('RANGE')
        if metric == 'nav_success_gt_pct':
            nav = _num(s.get('nav_success_pct'))
            if nav is not None and nav - val > sp['nav_gt_divergence_pp']:
                sus.append('NAV_GT_DIVERGENCE')
        rtf = _num(s.get('rtf_true_mean'))
        if rtf is not None and rtf < sp['min_rtf']:
            sus.append('LOW_RTF')
        if metric == 'lc_precision_pct':
            med = _num(s.get('lc_rot_err_median_deg'))
            tol = _num(s.get('lc_reg_rot_tol_deg')) or c.get('lc_reg_rot_tol_deg')
            if med is not None and tol is not None and tol < med <= tol + sp['lc_rot_bias_margin_deg']:
                sus.append('LC_ROT_BIAS')
        if ev_key:
            n = _num(s.get(ev_key))
            mn = c['min_n'].get(min_key)
            if n is not None and mn is not None and 0 < n < mn:
                low.append('LOW_N:%d/%d' % (n, mn))
        fl = c['floors'].get(metric)
        if fl is not None:
            if metric in UPPER_FLOOR and val > fl:
                bad.append('BELOW_FLOOR:%.4g>%.4g' % (val, fl))
            elif metric not in UPPER_FLOOR and val < fl:
                bad.append('BELOW_FLOOR:%.4g<%.4g' % (val, fl))
    reasons = unm + sus + low + bad
    status = 'UNMEASURABLE' if unm else 'SUSPECT' if sus else 'LOW_N' if low else 'BAD' if bad else 'OK'
    return status, reasons


def compute_health(summary, cfg=None):
    """summary: merged summary dict. cfg: the `health:` block (partial ok). Returns flat dict of health_* keys."""
    c = _merge(cfg)
    if isinstance(cfg, dict) and cfg.get('lc_reg_rot_tol_deg') is not None:
        c['lc_reg_rot_tol_deg'] = float(cfg['lc_reg_rot_tol_deg'])
    out, counts = {}, {'OK': 0, 'BAD': 0, 'SUSPECT': 0, 'UNMEASURABLE': 0}
    for m in METRICS:
        if not _applicable(m, summary):
            out['health_' + m], out['health_%s_reasons' % m] = 'NA', []
            continue
        st, rs = _classify(m, summary, c)
        out['health_' + m], out['health_%s_reasons' % m] = st, rs
        if st in counts:
            counts[st] += 1
    for k, key in (('OK', 'health_n_ok'), ('BAD', 'health_n_bad'), ('SUSPECT', 'health_n_suspect'),
                   ('UNMEASURABLE', 'health_n_unmeasurable')):
        out[key] = counts[k]
    return out
