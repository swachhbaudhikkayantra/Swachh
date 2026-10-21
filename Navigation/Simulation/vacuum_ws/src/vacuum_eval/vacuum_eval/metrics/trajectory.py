"""Trajectory accuracy: ATE, RPE, drift, tracking gaps, AMCL error (docs/specs/04)."""

import math
from typing import List, Optional, Tuple

import numpy as np

from .common import Run, se2_compose_arrays, wrap_angle

MIN_ROWS = 100
MIN_PATH_M = 2.0
ODOM_ATE_MIN_M = 0.02
START_WINDOW_S = 5.0
START_OFFSET_M = 0.10
START_OFFSET_DEG = 5.0
GAP_MIN_S = 1.0
AMCL_OK_M = 0.25
AMCL_LOST_M = 1.0
AMCL_CONVERGE_WINDOW_S = 10.0

FRAME_NOTE = 'SLAM map frame is not at spawn pose; fixed ATE is dominated by frame offset'
INSUFFICIENT_NOTE = 'insufficient motion for ATE/RPE'

SLAM_KEYS = [
    'ate_fixed_rmse_m', 'ate_fixed_mean_m', 'ate_fixed_max_m', 'ate_yaw_rmse_deg',
    'ate_aligned_rmse_m', 'ate_samples',
    'rpe_trans_rmse_m_1m', 'rpe_trans_mean_m_1m', 'rpe_rot_rmse_deg_1m', 'rpe_pairs_1m',
    'rpe_trans_rmse_m_5s', 'rpe_trans_mean_m_5s', 'rpe_rot_rmse_deg_5s', 'rpe_pairs_5s',
    'start_offset_m', 'start_offset_deg', 'slam_final_error_m', 'slam_drift_ratio',
    'n_est_gaps', 'est_gap_total_s', 'ate_improvement_pct']
ODOM_KEYS = ['rpe_odom_trans_rmse_m_1m', 'rpe_odom_rot_rmse_deg_1m',
             'ate_odom_fixed_rmse_m', 'ate_odom_aligned_rmse_m',
             'odom_final_error_m', 'odom_drift_ratio']
AMCL_KEYS = ['loc_error_mean_m', 'loc_error_p95_m', 'loc_converge_s', 'loc_lost_events']


def umeyama_2d(E: np.ndarray, G: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Rigid 2D alignment without scale mapping E onto G. Returns (R, t): G ~ R E + t."""
    E = np.asarray(E, dtype=float)
    G = np.asarray(G, dtype=float)
    Em, Gm = E.mean(axis=0), G.mean(axis=0)
    e, g = E - Em, G - Gm
    theta = math.atan2(float(np.sum(e[:, 0] * g[:, 1] - e[:, 1] * g[:, 0])),
                       float(np.sum(e[:, 0] * g[:, 0] + e[:, 1] * g[:, 1])))
    c, s = math.cos(theta), math.sin(theta)
    R = np.array([[c, -s], [s, c]])
    return R, Gm - R @ Em


def _rel(a, b):
    """se2_inverse(a) o b for arrays of poses (N,3) -> (N,3)."""
    c, s = np.cos(a[:, 2]), np.sin(a[:, 2])
    dx, dy = b[:, 0] - a[:, 0], b[:, 1] - a[:, 1]
    return np.stack([c * dx + s * dy, -s * dx + c * dy, wrap_angle(b[:, 2] - a[:, 2])], axis=1)


def rpe(gt: np.ndarray, est: np.ndarray, pair_indices: List[Tuple[int, int]]):
    """Relative pose error for index pairs. Returns (trans_err, rot_err_rad) arrays."""
    if len(pair_indices) == 0:
        return np.zeros(0), np.zeros(0)
    idx = np.asarray(pair_indices, dtype=int)
    dg = _rel(gt[idx[:, 0]], gt[idx[:, 1]])
    de = _rel(est[idx[:, 0]], est[idx[:, 1]])
    err = _rel(dg, de)
    return np.hypot(err[:, 0], err[:, 1]), np.abs(wrap_angle(err[:, 2]))


def _pairs_1m(gt_xy: np.ndarray) -> List[Tuple[int, int]]:
    s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(gt_xy, axis=0).T))])
    pairs = []
    for i in range(len(s)):
        j = int(np.searchsorted(s, s[i] + 1.0 - 1e-12, side='left'))
        if j < len(s):
            pairs.append((i, j))
    return pairs


def _pairs_5s(t: np.ndarray) -> List[Tuple[int, int]]:
    pairs = []
    for i in range(len(t)):
        k = int(np.searchsorted(t, t[i] + 5.0))
        cands = [c for c in (k - 1, k) if i < c < len(t)]
        if not cands:
            continue
        j = min(cands, key=lambda c: abs(t[c] - t[i] - 5.0))
        if abs(t[j] - t[i] - 5.0) <= 0.05 + 1e-9:
            pairs.append((i, j))
    return pairs


def _stack(tr, a, b, c):
    return np.stack([np.asarray(tr[a], float), np.asarray(tr[b], float),
                     np.asarray(tr[c], float)], axis=1)


def _path_len(xy: np.ndarray) -> float:
    return float(np.sum(np.hypot(*np.diff(xy, axis=0).T))) if len(xy) > 1 else 0.0


def _p_est_group(t, gt, w, pfx, out):
    """ATE/RPE of world-frame poses `w` against `gt`; writes keys into out.
    pfx '' -> SLAM keys, 'odom' -> odometry keys. Returns the error array."""
    e = np.hypot(w[:, 0] - gt[:, 0], w[:, 1] - gt[:, 1])
    R, tt = umeyama_2d(w[:, :2], gt[:, :2])
    a = np.linalg.norm((w[:, :2] @ R.T + tt) - gt[:, :2], axis=1)
    p1, p5 = _pairs_1m(gt[:, :2]), _pairs_5s(t)
    tr1, ro1 = rpe(gt, w, p1)
    if pfx == '':
        out['ate_fixed_rmse_m'] = float(np.sqrt(np.mean(e ** 2)))
        out['ate_fixed_mean_m'] = float(np.mean(e))
        out['ate_fixed_max_m'] = float(np.max(e))
        dy = wrap_angle(w[:, 2] - gt[:, 2])
        out['ate_yaw_rmse_deg'] = float(np.degrees(np.sqrt(np.mean(dy ** 2))))
        out['ate_aligned_rmse_m'] = float(np.sqrt(np.mean(a ** 2)))
        out['ate_samples'] = int(len(e))
        tr5, ro5 = rpe(gt, w, p5)
        for sfx, tr, ro, pp in (('1m', tr1, ro1, p1), ('5s', tr5, ro5, p5)):
            out['rpe_pairs_' + sfx] = len(pp)
            if len(pp):
                out['rpe_trans_rmse_m_' + sfx] = float(np.sqrt(np.mean(tr ** 2)))
                out['rpe_trans_mean_m_' + sfx] = float(np.mean(tr))
                out['rpe_rot_rmse_deg_' + sfx] = float(np.degrees(np.sqrt(np.mean(ro ** 2))))
    else:
        out['ate_odom_fixed_rmse_m'] = float(np.sqrt(np.mean(e ** 2)))
        out['ate_odom_aligned_rmse_m'] = float(np.sqrt(np.mean(a ** 2)))
        if len(p1):
            out['rpe_odom_trans_rmse_m_1m'] = float(np.sqrt(np.mean(tr1 ** 2)))
            out['rpe_odom_rot_rmse_deg_1m'] = float(np.degrees(np.sqrt(np.mean(ro1 ** 2))))
    return e


def _gaps(t, ok):
    """Maximal runs of est_ok == 0 lasting >= 1.0 s (span t_last - t_first)."""
    bad = ~(ok == 1)
    n, total, i = 0, 0.0, 0
    while i < len(bad):
        if bad[i]:
            j = i
            while j + 1 < len(bad) and bad[j + 1]:
                j += 1
            d = t[j] - t[i]
            if d >= GAP_MIN_S - 1e-9:
                n += 1
                total += d
            i = j + 1
        else:
            i += 1
    return n, float(total)


def _amcl(t, e, t_start, out):
    out['loc_error_mean_m'] = float(np.mean(e))
    out['loc_error_p95_m'] = float(np.percentile(e, 95))
    bad = np.concatenate([[0], np.cumsum(e >= AMCL_OK_M)])
    conv = None
    for i in range(len(t)):
        if t[-1] < t[i] + AMCL_CONVERGE_WINDOW_S - 1e-9:
            break
        j = int(np.searchsorted(t, t[i] + AMCL_CONVERGE_WINDOW_S + 1e-9, side='right'))
        if bad[j] - bad[i] == 0:
            conv = float(t[i] - t_start)
            break
    out['loc_converge_s'] = conv
    lost, armed = 0, False
    for v in e:
        if v < AMCL_OK_M:
            armed = True
        elif v > AMCL_LOST_M and armed:
            lost += 1
            armed = False
    out['loc_lost_events'] = lost


def compute_trajectory_metrics(run: Run) -> dict:
    notes: List[str] = []
    out = {k: None for k in SLAM_KEYS + ODOM_KEYS}
    amcl = run.meta.get('localization_mode') == 'amcl'
    if amcl:
        out.update({k: None for k in AMCL_KEYS})
    out['notes'] = notes
    tr = run.trajectory
    if tr is None or 't' not in tr:
        notes.append(INSUFFICIENT_NOTE)
        return out
    t_all = np.asarray(tr['t'], float)
    win = (t_all >= run.episode_start_t) & (t_all <= run.episode_end_t)
    col = lambda k: np.asarray(tr[k], float)[win] if k in tr else np.full(int(win.sum()), np.nan)
    t = t_all[win]
    gt = np.stack([col('gt_x'), col('gt_y'), col('gt_yaw')], axis=1)
    est = np.stack([col('est_x'), col('est_y'), col('est_yaw')], axis=1)
    odo = np.stack([col('odom_x'), col('odom_y'), col('odom_yaw')], axis=1)
    est_ok = col('est_ok')
    gt_ok = ~np.isnan(gt).any(axis=1)

    spawn = (float(run.meta.get('spawn_x', 0.0)), float(run.meta.get('spawn_y', 0.0)),
             float(run.meta.get('spawn_yaw', 0.0)))
    twm = tuple(float(v) for v in run.meta.get('t_world_map', spawn))
    two = spawn

    def to_world(p, T):
        X, Y, Yaw = se2_compose_arrays(T, p[:, 0], p[:, 1], p[:, 2])
        return np.stack([X, Y, Yaw], axis=1)

    # distance_gt_m: GT path length over all valid GT rows of the episode
    dist_gt = _path_len(gt[gt_ok, :2])
    out['distance_gt_m'] = dist_gt

    # SLAM / AMCL group
    v = gt_ok & ~np.isnan(est).any(axis=1) & (est_ok == 1)
    if v.sum() < MIN_ROWS or _path_len(gt[v, :2]) < MIN_PATH_M:
        notes.append(INSUFFICIENT_NOTE)
    else:
        tv, gv = t[v], gt[v]
        ew = to_world(est[v], twm)
        e = _p_est_group(tv, gv, ew, '', out)
        # start-alignment check
        m = tv <= run.episode_start_t + START_WINDOW_S
        if m.any():
            out['start_offset_m'] = float(np.mean(e[m]))
            out['start_offset_deg'] = float(np.degrees(np.mean(np.abs(wrap_angle(ew[m, 2] - gv[m, 2])))))
            if out['start_offset_m'] > START_OFFSET_M or out['start_offset_deg'] > START_OFFSET_DEG:
                notes.append(FRAME_NOTE)
        out['slam_final_error_m'] = float(e[-1])
        if dist_gt > 0:
            out['slam_drift_ratio'] = float(e[-1] / dist_gt)
        if amcl:
            _amcl(tv, e, run.episode_start_t, out)
    if 'est_ok' in tr:
        out['n_est_gaps'], out['est_gap_total_s'] = _gaps(t, est_ok)

    # odometry group
    vo = gt_ok & ~np.isnan(odo).any(axis=1)
    if vo.sum() < MIN_ROWS or _path_len(gt[vo, :2]) < MIN_PATH_M:
        if INSUFFICIENT_NOTE not in notes:
            notes.append(INSUFFICIENT_NOTE)
    else:
        ow = to_world(odo[vo], two)
        eo = _p_est_group(t[vo], gt[vo], ow, 'odom', out)
        out['odom_final_error_m'] = float(eo[-1])
        if dist_gt > 0:
            out['odom_drift_ratio'] = float(eo[-1] / dist_gt)
        if out['ate_fixed_rmse_m'] is not None and out['ate_odom_fixed_rmse_m'] >= ODOM_ATE_MIN_M:
            o = out['ate_odom_fixed_rmse_m']
            out['ate_improvement_pct'] = 100.0 * (o - out['ate_fixed_rmse_m']) / o
    return out
