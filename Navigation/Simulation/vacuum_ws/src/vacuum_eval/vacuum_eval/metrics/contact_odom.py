"""Contact-induced odometry corruption diagnostic.

When the robot is pressed against an obstacle the wheels slip, so wheel odometry
integrates yaw the body never turned. This module measures that from existing raw
data: for every contact event (merged across models), the excess yaw is
    excess_deg = |(odom_u(t_b) - odom_u(t_a)) - (gt_u(t_b) - gt_u(t_a))|
over the event window [t_start - pad, t_end + pad] clipped to the episode, with both
yaw series unwrapped over the whole episode.

It is a diagnostic stratifier and NEVER an exclusion rule (council
2026-10-22-031950); headline keys are untouched. Keys:
  contact_odom_n_events, contact_odom_yaw_excess_deg (sum), contact_odom_yaw_excess_max_deg,
  odom_corrupted_by_contact (max > CORRUPT_DEG), t_odom_corrupt_ep_s (first corrupting
  event start, episode-relative), and ate_*_pre_corrupt: trajectory ATE recomputed on
  the episode truncated at the first corrupting event (full ATE if none).
Overrides: config_snapshot 'contact_odom_corrupt_deg', 'collision_gap_s' (pad).
"""

import dataclasses

import numpy as np

from . import safety, trajectory
from .common import Run

CORRUPT_DEG = 15.0
PAD_S = 0.5
CONTACT_ODOM_KEYS = [
    'contact_odom_n_events', 'contact_odom_yaw_excess_deg', 'contact_odom_yaw_excess_max_deg',
    'odom_corrupted_by_contact', 't_odom_corrupt_ep_s',
    'ate_fixed_rmse_m_pre_corrupt', 'ate_odom_fixed_rmse_m_pre_corrupt',
    'ate_improvement_pct_pre_corrupt']
_ATE = [('ate_fixed_rmse_m', 'ate_fixed_rmse_m_pre_corrupt'),
        ('ate_odom_fixed_rmse_m', 'ate_odom_fixed_rmse_m_pre_corrupt'),
        ('ate_improvement_pct', 'ate_improvement_pct_pre_corrupt')]
FLAG_NOTE = 'odom_corrupted_by_contact: diagnostic only, never an exclusion; headline ATE unchanged'


def _pre_ate(run, t_cut):
    try:
        m = trajectory.compute_trajectory_metrics(dataclasses.replace(run, episode_end_t=t_cut))
        return {dst: m.get(src) for src, dst in _ATE}
    except Exception:
        return {dst: None for _, dst in _ATE}


def _events(run, pad):
    cr = run.collisions_raw
    if not cr or 't' not in cr or len(cr['t']) == 0:
        return []
    t = np.asarray(cr['t'], float)
    m = (t >= run.episode_start_t) & (t <= run.episode_end_t)
    if not m.any():
        return []
    rows = {k: np.asarray(v)[m] for k, v in cr.items()}
    if 'other_model' not in rows:
        rows['other_model'] = np.array([''] * int(m.sum()), dtype=object)
    evs = sorted(safety.collision_events(rows, gap_s=pad), key=lambda e: e['t_start'])
    merged = []
    for e in evs:
        if merged and e['t_start'] <= merged[-1][1] + pad:
            merged[-1][1] = max(merged[-1][1], e['t_end'])
        else:
            merged.append([e['t_start'], e['t_end']])
    return merged


def compute_contact_odom_metrics(run: Run) -> dict:
    notes = []
    out = {k: None for k in CONTACT_ODOM_KEYS}
    out['notes'] = notes
    tr = run.trajectory
    if tr is None or not all(k in tr for k in ('t', 'gt_yaw', 'odom_yaw')):
        notes.append('contact_odom: trajectory or yaw columns missing')
        return out
    snap = (run.meta or {}).get('config_snapshot') or {}
    thr = float(snap.get('contact_odom_corrupt_deg', CORRUPT_DEG))
    pad = float(snap.get('collision_gap_s', PAD_S))

    t = np.asarray(tr['t'], float)
    g = np.asarray(tr['gt_yaw'], float)
    o = np.asarray(tr['odom_yaw'], float)
    w = (t >= run.episode_start_t) & (t <= run.episode_end_t) & np.isfinite(g) & np.isfinite(o)
    t, g, o = t[w], g[w], o[w]
    gu, ou = (np.unwrap(g), np.unwrap(o)) if len(t) else (g, o)

    excess, first_t = [], None
    for ts, te in _events(run, pad):
        a, b = max(ts - pad, run.episode_start_t), min(te + pad, run.episode_end_t)
        idx = np.flatnonzero((t >= a) & (t <= b))
        if len(idx) < 2:
            continue
        i, j = idx[0], idx[-1]
        ex = abs(np.degrees((ou[j] - ou[i]) - (gu[j] - gu[i])))
        excess.append(ex)
        if first_t is None and ex > thr:
            first_t = ts
    out['contact_odom_n_events'] = len(excess)
    out['contact_odom_yaw_excess_deg'] = float(sum(excess)) if excess else 0.0
    mx = float(max(excess)) if excess else 0.0
    out['contact_odom_yaw_excess_max_deg'] = mx
    out['odom_corrupted_by_contact'] = 1 if mx > thr else 0
    if first_t is not None:
        out['t_odom_corrupt_ep_s'] = float(first_t - run.episode_start_t)
        notes.append(FLAG_NOTE)
    out.update(_pre_ate(run, first_t if first_t is not None else run.episode_end_t))
    return out
