"""Explored/cleaned coverage and map completeness (docs/specs/03 and 10). numpy/scipy only."""

import glob
import math
import os
from typing import Dict, List, Optional

import numpy as np
from scipy import ndimage

from .common import GtGrid, Run, se2_compose, se2_compose_arrays, se2_inverse, write_csv

SWEPT_REACH_FACTOR = math.sqrt(2) / 2   # reach = res * this (half cell diagonal)
RESAMPLE_DIST_M = 0.02
RESAMPLE_YAW_RAD = 0.05
V_REF = 0.30
_S3 = np.ones((3, 3), bool)


# ---------------------------------------------------------------- maps

def as_map(m) -> dict:
    """Normalise a map (dict, NpzFile, or path to .npz) to a dict with data/resolution/origin."""
    if isinstance(m, str):
        with np.load(m) as z:
            m = {k: z[k] for k in z.files}
    elif hasattr(m, 'files'):
        m = {k: m[k] for k in m.files}
    out = dict(m)
    out['data'] = np.asarray(out['data'], dtype=np.int16)
    for k in ('resolution', 'origin_x', 'origin_y'):
        out[k] = float(out[k])
    if abs(float(out.get('origin_yaw', 0.0))) > 1e-6:
        raise ValueError('map origin_yaw must be 0')
    return out


def sample_map(m, gt: GtGrid, t_world_map=(0.0, 0.0, 0.0)) -> np.ndarray:
    """Sample the map at every GT cell centre (nearest cell). int16 array, -1 if out of bounds."""
    m = as_map(m)
    X, Y = gt.cell_centers()
    xm, ym, _ = se2_compose_arrays(se2_inverse(tuple(t_world_map)), X, Y, np.zeros_like(X))
    col = np.floor((xm - m['origin_x']) / m['resolution']).astype(int)
    row = np.floor((ym - m['origin_y']) / m['resolution']).astype(int)
    h, w = m['data'].shape
    ok = (col >= 0) & (col < w) & (row >= 0) & (row < h)
    out = np.full(gt.occ.shape, -1, np.int16)
    out[ok] = m['data'][row[ok], col[ok]]
    return out


def map_classes(sampled: np.ndarray):
    return sampled == 0, sampled >= 65


def coverage_explored(sampled: np.ndarray, gt: GtGrid) -> float:
    """Percent of a_clean cells that the map marks free."""
    n = int(gt.a_clean.sum())
    if n == 0:
        return float('nan')
    return 100.0 * int((gt.a_clean & (sampled == 0)).sum()) / n


def _ratio(a, b):
    return None if b == 0 else a / b


def completeness(sampled: np.ndarray, gt: GtGrid) -> dict:
    """Fractions in [0, 1] (None when undefined). Keys: free_recall, free_precision,
    occ_recall, occ_precision, iou_free, iou_occ, headline."""
    free, occ = map_classes(sampled)
    B = gt.boundary
    A = gt.a_clean
    free_in = int((A & free).sum())
    d_occ = ndimage.binary_dilation(occ, structure=_S3)
    d_B = ndimage.binary_dilation(B, structure=_S3)
    out = dict(
        free_recall=_ratio(free_in, int(A.sum())),
        free_precision=_ratio(free_in, int(free.sum())),
        occ_recall=_ratio(int((B & d_occ).sum()), int(B.sum())),
        occ_precision=_ratio(int((occ & d_B).sum()), int(occ.sum())),
        iou_free=_ratio(free_in, int((A | free).sum())),
        iou_occ=_ratio(int((d_occ & B).sum()), int((d_occ | B).sum())),
    )
    fr, orc = out['free_recall'], out['occ_recall']
    out['headline'] = None if fr is None or orc is None else (fr + orc) / 2
    return out


def alignment_search(m, gt: GtGrid, t_world_map, max_shift=0.30, step=0.05, max_yaw_deg=5.0,
                     yaw_step_deg=1.0):
    """Search dx, dy (map frame, metres) and dyaw (deg) maximising occ_recall + occ_precision.
    The tested transform is T_world_map o (dx, dy, dyaw). Ties keep the smaller shift.
    Returns (dx, dy, dyaw_deg, sampled_best)."""
    m = as_map(m)
    n = int(round(max_shift / step))
    shifts = [k * step for k in range(-n, n + 1)]
    ny = int(round(max_yaw_deg / yaw_step_deg))
    yaws = [k * yaw_step_deg for k in range(-ny, ny + 1)]
    cands = sorted(((dx, dy, dyw) for dx in shifts for dy in shifts for dyw in yaws),
                   key=lambda c: (abs(c[0]) + abs(c[1]) + abs(c[2]) * 1e-3, c))
    B = gt.boundary
    d_B = ndimage.binary_dilation(B, structure=_S3)
    nB = int(B.sum())
    best, best_score, best_s = None, -1.0, None
    for dx, dy, dyw in cands:
        T = se2_compose(tuple(t_world_map), (dx, dy, math.radians(dyw)))
        s = sample_map(m, gt, T)
        occ = s >= 65
        rec = (B & ndimage.binary_dilation(occ, structure=_S3)).sum() / nB if nB else 0.0
        no = int(occ.sum())
        prec = (occ & d_B).sum() / no if no else 0.0
        score = rec + prec
        if score > best_score + 1e-12:
            best, best_score, best_s = (dx, dy, dyw), score, s
    return best[0], best[1], best[2], best_s


# ---------------------------------------------------------------- swept area

def _interval_cells(traj: np.ndarray, gt: GtGrid, width_m: float):
    """Cells touched in each original sample interval k (rows k -> k+1).
    Returns (keys, n_intervals) with keys = sorted unique int64 k*H*W + flat_cell."""
    H, W = gt.occ.shape
    HW = H * W
    traj = np.asarray(traj, float)
    n_int = len(traj) - 1
    if n_int < 1:
        return np.zeros(0, np.int64), 0
    p0, p1 = traj[:-1], traj[1:]
    dpos = np.hypot(p1[:, 0] - p0[:, 0], p1[:, 1] - p0[:, 1])
    dyaw = np.arctan2(np.sin(p1[:, 2] - p0[:, 2]), np.cos(p1[:, 2] - p0[:, 2]))
    nsub = np.maximum(np.maximum(np.ceil(dpos / RESAMPLE_DIST_M - 1e-9),
                                 np.ceil(np.abs(dyaw) / RESAMPLE_YAW_RAD - 1e-9)), 1).astype(int)
    kid = np.repeat(np.arange(n_int), nsub + 1)
    start = np.cumsum(np.concatenate([[0], nsub + 1]))[:-1]
    s = np.arange(len(kid)) - np.repeat(start, nsub + 1)
    f = s / np.repeat(nsub, nsub + 1)
    x = p0[kid, 0] + f * (p1[kid, 0] - p0[kid, 0])
    y = p0[kid, 1] + f * (p1[kid, 1] - p0[kid, 1])
    yaw = p0[kid, 2] + f * dyaw[kid]
    hw = width_m / 2
    sn, cs = np.sin(yaw), np.cos(yaw)
    ax, ay = x - sn * hw, y + cs * hw
    bx, by = x + sn * hw, y - cs * hw
    pm = kid[:-1] == kid[1:]          # consecutive resampled pairs inside one interval
    k0 = np.nonzero(pm)[0]
    k1 = k0 + 1
    kid_p = kid[k0]
    half = int(math.ceil((hw + RESAMPLE_DIST_M) / gt.res)) + 2
    off = np.arange(-half, half + 1)
    mx = 0.5 * (x[k0] + x[k1])
    my = 0.5 * (y[k0] + y[k1])
    ci = np.floor((mx - gt.x0) / gt.res).astype(int)
    cj = np.floor((my - gt.y0) / gt.res).astype(int)
    shp = (len(k0), len(off), len(off))
    I = np.broadcast_to(ci[:, None, None] + off[None, None, :], shp)
    J = np.broadcast_to(cj[:, None, None] + off[None, :, None], shp)
    px = gt.x0 + (I + 0.5) * gt.res
    py = gt.y0 + (J + 0.5) * gt.res
    tol = 1e-9

    def tri(p, q, r):
        def cr(u, v, w):
            return ((v[0] - u[0]) * (py - u[1]) - (v[1] - u[1]) * (px - u[0]))
        d1, d2, d3 = cr(p, q, r), cr(q, r, p), cr(r, p, q)
        neg = (d1 < -tol) | (d2 < -tol) | (d3 < -tol)
        pos = (d1 > tol) | (d2 > tol) | (d3 > tol)
        return ~(neg & pos)

    def pt(arrx, arry, idx):
        return (arrx[idx][:, None, None], arry[idx][:, None, None])

    A0, B0 = pt(ax, ay, k0), pt(bx, by, k0)
    A1, B1 = pt(ax, ay, k1), pt(bx, by, k1)
    inside = tri(A0, B0, B1) | tri(A0, B1, A1)
    ok = inside & (I >= 0) & (I < W) & (J >= 0) & (J < H)
    kk = np.broadcast_to(kid_p[:, None, None], I.shape)
    keys = np.unique(kk[ok].astype(np.int64) * HW + (J[ok] * W + I[ok]))
    return keys, n_int


def swept_grid(traj_gt: np.ndarray, t: np.ndarray, gt: GtGrid, width_m: float):
    """traj_gt: (N, 3) x, y, yaw. Returns (swept bool[H,W], visits uint16[H,W]), restricted
    to a_clean. A visit is counted once per contiguous run of sample intervals touching a cell."""
    H, W = gt.occ.shape
    HW = H * W
    keys, _ = _interval_cells(traj_gt, gt, width_m)
    swept = np.zeros(HW, bool)
    visits = np.zeros(HW, np.int64)
    if len(keys):
        cell = keys % HW
        prev = keys - HW
        pos = np.minimum(np.searchsorted(keys, prev), len(keys) - 1)
        new = ~(keys[pos] == prev)
        swept[cell] = True
        visits = np.bincount(cell[new], minlength=HW)
    a = gt.a_clean.reshape(-1)
    swept &= a
    visits = np.where(a, visits, 0)
    return swept.reshape(H, W), np.minimum(visits, 65535).astype(np.uint16).reshape(H, W)


def swept_curve(traj_gt: np.ndarray, t: np.ndarray, gt: GtGrid, width_m: float,
                sample_times) -> np.ndarray:
    """Cleaned coverage (%) at each sample time using only rows with t <= sample time.
    Single pass; equals swept_grid() on the truncated trajectory."""
    t = np.asarray(t, float)
    H, W = gt.occ.shape
    HW = H * W
    keys, n_int = _interval_cells(traj_gt, gt, width_m)
    nA = int(gt.a_clean.sum())
    sample_times = np.asarray(sample_times, float)
    if nA == 0:
        return np.full(len(sample_times), np.nan)
    first_k = np.full(HW, -1, np.int64)
    if len(keys):
        k = keys // HW
        cell = keys % HW
        uc, idx = np.unique(cell, return_index=True)   # first occurrence = smallest k
        first_k[uc] = k[idx]
    fk = first_k[(first_k >= 0) & gt.a_clean.reshape(-1)]
    cum = np.cumsum(np.bincount(fk, minlength=max(n_int, 1)))[:max(n_int, 1)] if n_int else \
        np.zeros(1, np.int64)
    out = np.zeros(len(sample_times))
    for i, T in enumerate(sample_times):
        rows = int(np.searchsorted(t, T, side='right'))
        m = rows - 1                       # intervals fully inside
        out[i] = 0.0 if m < 1 or n_int == 0 else 100.0 * cum[min(m, n_int) - 1] / nA
    return out


def cleaning_keys(swept, visits, gt: GtGrid, episode_sim_sec: float, distance_gt_m: float,
                  width_m: float, v_ref: float = V_REF) -> dict:
    res2 = gt.res ** 2
    nA = int(gt.a_clean.sum())
    sw = swept & gt.a_clean
    n_sw = int(sw.sum())
    cov = 100.0 * n_sw / nA if nA else None
    swept_m2 = n_sw * res2
    overlap = float(visits[sw].astype(np.int64).sum()) / n_sw if n_sw else None
    out = dict(coverage_cleaned_pct=cov, swept_area_m2=swept_m2,
               missed_area_m2=(nA - n_sw) * res2, overlap_ratio=overlap,
               redundancy_pct=None if overlap is None else 100.0 * (overlap - 1.0),
               cleaned_m2_per_min=swept_m2 / (episode_sim_sec / 60.0) if episode_sim_sec else None,
               cleaned_m2_per_m=swept_m2 / distance_gt_m if distance_gt_m else None)
    out['cleaning_efficiency'] = None if cov is None or overlap is None else (cov / 100.0) / overlap
    ref_time = nA * res2 / (width_m * v_ref)
    out['cleaning_efficiency_time'] = (None if cov is None or not episode_sim_sec else
                                       (cov / 100.0) / (episode_sim_sec / ref_time))
    return out


# ---------------------------------------------------------------- run level

def _first_reach(t, y, thr):
    idx = np.nonzero(np.asarray(y) >= thr)[0]
    return float(t[idx[0]]) if len(idx) else None


def _auc(t, y, T):
    """Mean of the curve over [0, T], holding the first value back to 0 and the last to T."""
    if T <= 0 or len(t) == 0:
        return None
    t = np.concatenate([[0.0], np.clip(t, 0, T), [T]])
    y = np.concatenate([[y[0]], y, [y[-1]]])
    return float(np.trapz(y, t) / T) if hasattr(np, 'trapz') else float(np.trapezoid(y, t) / T)


def _load_snapshots(run: Run):
    snaps = getattr(run, 'map_snapshots', None)
    out = []
    if snaps:
        for s in snaps:
            if isinstance(s, tuple):
                out.append((float(s[0]), as_map(s[1])))
            else:
                m = as_map(s)
                out.append((float(np.asarray(s['t'])), m))
    elif run.run_dir:
        for p in sorted(glob.glob(os.path.join(run.run_dir, 'maps', 'map_*.npz'))):
            with np.load(p) as z:
                if 't' in z.files:
                    out.append((float(z['t']), as_map(p)))
    return sorted(out, key=lambda a: a[0])


def _final_map(run: Run):
    m = getattr(run, 'maps_final', None)
    if m is None and run.run_dir:
        p = os.path.join(run.run_dir, 'maps', 'final_map.npz')
        if os.path.exists(p):
            m = p
    return None if m is None else as_map(m)


COVERAGE_KEYS = (
    ['coverage_explored_pct', 'missed_explored_m2', 'map_completeness_pct',
     'map_completeness_aligned_pct', 'map_free_recall_pct', 'map_free_precision_pct',
     'map_occ_recall_pct', 'map_occ_precision_pct', 'map_iou_free_pct', 'map_iou_occ_pct',
     'map_align_dx_m', 'map_align_dy_m', 'map_align_dyaw_deg', 'coverage_explored_auc',
     'coverage_cleaned_auc', 'coverage_cleaned_pct', 'swept_area_m2', 'missed_area_m2',
     'overlap_ratio', 'redundancy_pct', 'cleaned_m2_per_min', 'cleaned_m2_per_m',
     'cleaning_efficiency', 'cleaning_efficiency_time'] +
    ['t_to_%d_%s_s' % (p, k) for k in ('explored', 'cleaned') for p in (50, 80, 95)])


def _pct(v):
    return None if v is None else 100.0 * v


def compute_coverage(run: Run, gt: GtGrid, write_outputs: bool = True) -> dict:
    """Flat dict of all spec 03 / spec 10 keys; 'notes' holds a list of strings.
    Missing inputs give None values plus a note."""
    out = {k: None for k in COVERAGE_KEYS}
    notes: List[str] = []
    meta = run.meta or {}
    tw = (float(meta.get('spawn_x', 0.0)), float(meta.get('spawn_y', 0.0)),
          float(meta.get('spawn_yaw', 0.0)))
    width = float(meta.get('swath_width_m', 0.25))
    t0, t1 = float(run.episode_start_t), float(run.episode_end_t)
    T = max(t1 - t0, 0.0)

    # --- explored / completeness
    fm = _final_map(run)
    snaps = _load_snapshots(run)
    sampled_final = None
    if fm is None:
        notes.append('no final map')
    else:
        sampled_final = sample_map(fm, gt, tw)
        out['coverage_explored_pct'] = coverage_explored(sampled_final, gt)
        out['missed_explored_m2'] = (int(gt.a_clean.sum()) -
                                     int((gt.a_clean & (sampled_final == 0)).sum())) * gt.res ** 2
        c = completeness(sampled_final, gt)
        out['map_completeness_pct'] = _pct(c['headline'])
        out['map_free_recall_pct'] = _pct(c['free_recall'])
        out['map_free_precision_pct'] = _pct(c['free_precision'])
        out['map_occ_recall_pct'] = _pct(c['occ_recall'])
        out['map_occ_precision_pct'] = _pct(c['occ_precision'])
        out['map_iou_free_pct'] = _pct(c['iou_free'])
        out['map_iou_occ_pct'] = _pct(c['iou_occ'])
        dx, dy, dyaw, s_al = alignment_search(fm, gt, tw)
        out['map_align_dx_m'], out['map_align_dy_m'], out['map_align_dyaw_deg'] = dx, dy, dyaw
        out['map_completeness_aligned_pct'] = _pct(completeness(s_al, gt)['headline'])
        if math.hypot(dx, dy) > 0.20 or abs(dyaw) > 3.0:
            notes.append('map frame offset vs spawn pose exceeds tolerance')

    # --- cleaned
    traj = getattr(run, 'trajectory', None)
    tr_t = tr = None
    if traj is None or 'gt_x' not in traj:
        notes.append('no trajectory: cleaned keys unavailable')
    else:
        tt = np.asarray(traj['t'], float)
        P = np.column_stack([traj['gt_x'], traj['gt_y'], traj['gt_yaw']]).astype(float)
        sel = np.isfinite(P).all(axis=1) & (tt >= t0) & ((tt <= t1) if t1 > t0 else True)
        tr_t, tr = tt[sel], P[sel]
        if len(tr) < 2:
            notes.append('fewer than 2 trajectory rows in episode window')
            tr = None
    if tr is not None:
        dist = float(np.hypot(np.diff(tr[:, 0]), np.diff(tr[:, 1])).sum())
        sw, vis = swept_grid(tr, tr_t, gt, width)
        out.update(cleaning_keys(sw, vis, gt, T, dist, width))
        cur_c = swept_curve(tr, tr_t, gt, width, tr_t)
        tq = tr_t - t0
        for p in (50, 80, 95):
            out['t_to_%d_cleaned_s' % p] = _first_reach(tq, cur_c, p)
        out['coverage_cleaned_auc'] = _auc(tq, cur_c, T)

    # --- explored curve + curve csv
    pts = [(t - t0, coverage_explored(sample_map(m, gt, tw), gt)) for t, m in snaps if t >= t0]
    if fm is not None:
        pts.append((T, out['coverage_explored_pct']))
    if pts:
        te = np.array([p[0] for p in pts])
        ce = np.array([p[1] for p in pts])
        for p in (50, 80, 95):
            out['t_to_%d_explored_s' % p] = _first_reach(te, ce, p)
        out['coverage_explored_auc'] = _auc(te, ce, T)
    elif fm is not None:
        notes.append('no map snapshots: explored curve unavailable')

    if write_outputs and run.run_dir and os.path.isdir(run.run_dir) and pts:
        te = np.array([p[0] for p in pts])
        cc = (swept_curve(tr, tr_t, gt, width, te + t0) if tr is not None
              else [None] * len(te))
        write_csv(os.path.join(run.run_dir, 'coverage_curve.csv'),
                  ['t_ep', 'coverage_explored_pct', 'coverage_cleaned_pct'],
                  [[a, b, c] for a, b, c in zip(te, [p[1] for p in pts], cc)])
    if write_outputs and run.run_dir and os.path.isdir(run.run_dir) and sampled_final is not None:
        _save_missed_png(os.path.join(run.run_dir, 'missed_explored.png'), gt, sampled_final)
    out['notes'] = notes
    return out


def _save_missed_png(path, gt: GtGrid, sampled):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    img = np.ones(gt.occ.shape + (3,))
    img[gt.occ] = (0.0, 0.0, 0.0)
    img[gt.a_clean & (sampled != 0)] = (1.0, 0.0, 0.0)
    h, w = gt.occ.shape
    fig, ax = plt.subplots(figsize=(8, 8 * h / max(w, 1)))
    ax.imshow(img, origin='lower', extent=(gt.x0, gt.x0 + w * gt.res, gt.y0, gt.y0 + h * gt.res))
    ax.set_title('unexplored cleanable cells (red)')
    fig.savefig(path, dpi=100, bbox_inches='tight')
    plt.close(fig)
