"""Loop-closure precision / recall from loop_events.csv (docs/specs/08)."""

import math
from typing import Dict, List, Set, Tuple

import numpy as np

from .common import Run, wrap_angle

LC_POS_TOL_M = 0.30       # default truth tolerances (eval_defaults lc_pos_tol_m / lc_yaw_tol_deg)
LC_YAW_TOL_DEG = 30.0
LC_POS_TOL_LOOSE_M = 1.0  # old tolerances, reported as *_loose only
LC_YAW_TOL_LOOSE_DEG = 60.0
LC_MIN_TIME_GAP_S = 30.0
LC_REG_TRANS_TOL_M = 0.10  # headline truth: RTAB-Map transform vs GT relative transform
LC_REG_ROT_TOL_DEG = 5.0
# Revisit (recall) stays position-based: a place where a closure was possible.
LC_REVISIT_POS_M = 1.0
LC_REVISIT_YAW_DEG = 60.0


def rel_se2(pa, pb):
    """SE(2) pose of b expressed in a's frame (inv(Pa) * Pb); p = (t, x, y, yaw)."""
    dx, dy = pb[1] - pa[1], pb[2] - pa[2]
    c, s = math.cos(pa[3]), math.sin(pa[3])
    return c * dx + s * dy, -s * dx + c * dy, wrap_angle(pb[3] - pa[3])


def _reg_correct(pa, pb, tf, trans_tol, rot_tol) -> bool:
    """tf = (tx, ty, tyaw) from ref (pa) to loop node (pb), pose_b = pose_a * T."""
    if any(math.isnan(v) for v in pa[1:] + pb[1:] + tuple(tf)):
        return False
    gx, gy, gyaw = rel_se2(pa, pb)
    return (math.hypot(gx - tf[0], gy - tf[1]) <= trans_tol
            and abs(wrap_angle(gyaw - tf[2])) <= rot_tol)


def node_poses(rows) -> Dict[int, Tuple[float, float, float, float]]:
    """{ref_id: (t_first, gt_x, gt_y, gt_yaw)} from the first row of each ref_id,
    in order of first appearance. `rows` is a {column: array} dict."""
    nodes: Dict[int, Tuple[float, float, float, float]] = {}
    if rows is None or 'ref_id' not in rows:
        return nodes
    n = len(rows['ref_id'])
    for k in range(n):
        rid = int(rows['ref_id'][k])
        if rid in nodes:
            continue
        nodes[rid] = (float(rows['t'][k]), float(rows['gt_x'][k]),
                      float(rows['gt_y'][k]), float(rows['gt_yaw'][k]))
    return nodes


def _close(pa, pb, pos_tol, yaw_tol) -> bool:
    d = (pa[1:], pb[1:])
    if any(math.isnan(v) for v in d[0] + d[1]):
        return False
    return (math.hypot(pa[1] - pb[1], pa[2] - pb[2]) <= pos_tol
            and abs(wrap_angle(pa[3] - pb[3])) <= yaw_tol)


def revisit_episodes(nodes, pos_tol, yaw_tol, min_gap_s) -> List[Set[int]]:
    """Maximal runs of consecutive nodes (by first appearance) that revisit an earlier
    node at least min_gap_s older. yaw_tol is in radians."""
    items = sorted(nodes.items(), key=lambda kv: kv[1][0])
    episodes: List[Set[int]] = []
    cur: Set[int] = set()
    for i, (rid, p) in enumerate(items):
        rev = any(q[0] <= p[0] - min_gap_s and _close(p, q, pos_tol, yaw_tol)
                  for _, q in items[:i])
        if rev:
            cur.add(rid)
        elif cur:
            episodes.append(cur)
            cur = set()
    if cur:
        episodes.append(cur)
    return episodes


def compute_loop_closure_metrics(run: Run, pos_tol_m: float = LC_POS_TOL_M,
                                 yaw_tol_deg: float = LC_YAW_TOL_DEG,
                                 reg_trans_tol_m: float = LC_REG_TRANS_TOL_M,
                                 reg_rot_tol_deg: float = LC_REG_ROT_TOL_DEG) -> dict:
    keys = ['lc_n_info_msgs', 'lc_n_nodes', 'lc_n_accepted', 'lc_n_true', 'lc_n_false',
            'lc_n_revisits', 'lc_n_revisits_detected', 'lc_precision_pct', 'lc_recall_pct',
            'lc_f1_pct', 'n_proximity_links', 'lc_per_100m',
            'lc_n_true_loose', 'lc_n_false_loose', 'lc_precision_loose_pct',
            'lc_precision_samepose_pct', 'lc_n_true_samepose']
    out = {k: None for k in keys}
    notes: List[str] = []
    out['notes'] = notes
    le = run.loop_events
    if le is None or 'ref_id' not in le:
        notes.append('loop_events.csv missing')
        return out
    t = np.asarray(le['t'], float)
    win = (t >= run.episode_start_t) & (t <= run.episode_end_t)
    rows = {k: v[win] for k, v in le.items()}
    all_nodes = node_poses(le)       # lookup includes nodes created before the window
    nodes = {r: p for r, p in node_poses(rows).items()}
    pos_tol, yaw_tol = pos_tol_m, math.radians(yaw_tol_deg)

    out['lc_n_info_msgs'] = int(win.sum())
    out['lc_n_nodes'] = len(nodes)
    lc_id = np.asarray(rows['loop_closure_id'], float)
    prox = np.asarray(rows['proximity_detection_id'], float)
    ref = np.asarray(rows['ref_id'], float)
    acc = set()
    for a, b in zip(ref[lc_id > 0], lc_id[lc_id > 0]):
        acc.add((int(a), int(b)))
    tfs = {}
    if all(k in rows for k in ('lc_tx', 'lc_ty', 'lc_tyaw')):
        for k in range(len(ref)):
            if lc_id[k] > 0:
                v = (float(rows['lc_tx'][k]), float(rows['lc_ty'][k]), float(rows['lc_tyaw'][k]))
                if not any(math.isnan(x) for x in v):
                    tfs.setdefault((int(ref[k]), int(lc_id[k])), v)
    same = {(a, b) for a, b in acc if a in all_nodes and b in all_nodes
            and _close(all_nodes[a], all_nodes[b], pos_tol, yaw_tol)}
    out['lc_n_true_samepose'] = len(same)
    out['lc_precision_samepose_pct'] = 100.0 * len(same) / len(acc) if acc else None
    true_pairs = set()
    n_fallback = 0
    for a, b in acc:
        if a not in all_nodes or b not in all_nodes:
            continue
        if (a, b) in tfs:
            if _reg_correct(all_nodes[a], all_nodes[b], tfs[(a, b)], reg_trans_tol_m,
                            math.radians(reg_rot_tol_deg)):
                true_pairs.add((a, b))
        else:
            n_fallback += 1
            if (a, b) in same:
                true_pairs.add((a, b))
    if n_fallback:
        notes.append('lc truth: %d/%d closures lack lc_tx/ty/tyaw; used position tolerance '
                     '(%.2f m/%g deg) for them' % (n_fallback, len(acc), pos_tol_m, yaw_tol_deg))
    loose = sum(1 for a, b in acc if a in all_nodes and b in all_nodes and _close(
        all_nodes[a], all_nodes[b], LC_POS_TOL_LOOSE_M, math.radians(LC_YAW_TOL_LOOSE_DEG)))
    out['lc_n_true_loose'] = loose
    out['lc_n_false_loose'] = len(acc) - loose
    out['lc_precision_loose_pct'] = 100.0 * loose / len(acc) if acc else None
    out['lc_n_accepted'] = len(acc)
    out['lc_n_true'] = len(true_pairs)
    out['lc_n_false'] = len(acc) - len(true_pairs)
    out['n_proximity_links'] = int(np.sum((prox > 0) & ~(lc_id > 0)))

    eps = revisit_episodes(nodes, LC_REVISIT_POS_M, math.radians(LC_REVISIT_YAW_DEG),
                           LC_MIN_TIME_GAP_S)
    true_refs = {a for a, _ in true_pairs}
    out['lc_n_revisits'] = len(eps)
    out['lc_n_revisits_detected'] = sum(1 for e in eps if e & true_refs)

    prec = 100.0 * len(true_pairs) / len(acc) if acc else None
    rec = 100.0 * out['lc_n_revisits_detected'] / len(eps) if eps else None
    out['lc_precision_pct'], out['lc_recall_pct'] = prec, rec
    if prec is not None and rec is not None:
        out['lc_f1_pct'] = 0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec)

    dist = None
    tr = run.trajectory
    if tr is not None and 't' in tr and 'gt_x' in tr:
        tt = np.asarray(tr['t'], float)
        m = (tt >= run.episode_start_t) & (tt <= run.episode_end_t)
        xy = np.stack([np.asarray(tr['gt_x'], float)[m], np.asarray(tr['gt_y'], float)[m]], axis=1)
        xy = xy[~np.isnan(xy).any(axis=1)]
        if len(xy) > 1:
            dist = float(np.sum(np.hypot(*np.diff(xy, axis=0).T)))
    if dist and dist > 0:
        out['lc_per_100m'] = 100.0 * len(acc) / dist
    elif dist is None:
        notes.append('lc_per_100m: no trajectory')
    return out
