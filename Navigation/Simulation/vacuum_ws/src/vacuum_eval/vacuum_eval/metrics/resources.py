"""CPU / RAM / real-time-factor metrics (docs/specs/02 sections 2.4, 2.8)."""

import os
import re

import numpy as np

from vacuum_eval.metrics.common import load_csv

_BASE_KEYS = ['rtf_mean', 'rtf_p05', 'rtf_min', 'ram_used_peak_mb']


def _load(run, attr, fname):
    tbl = getattr(run, attr, None)
    if tbl is not None:
        return tbl
    path = os.path.join(run.run_dir, fname)
    return load_csv(path) if os.path.exists(path) else None


def _window(tbl, t0, t1):
    t = np.asarray(tbl['t'], dtype=float)
    return (t >= t0) & (t <= t1)


def _stat(vals, fn):
    vals = np.asarray(vals, dtype=float)
    vals = vals[np.isfinite(vals)]
    return float(fn(vals)) if vals.size else None


def compute_resource_metrics(run) -> dict:
    out = {k: None for k in _BASE_KEYS}
    t0, t1 = run.episode_start_t, run.episode_end_t

    rtf = _load(run, 'rtf', 'rtf.csv')
    if rtf is not None and 'rtf' in rtf and 't' in rtf:
        v = np.asarray(rtf['rtf'], dtype=float)[_window(rtf, t0, t1)]
        out['rtf_mean'] = _stat(v, np.mean)
        out['rtf_p05'] = _stat(v, lambda x: np.percentile(x, 5))
        out['rtf_min'] = _stat(v, np.min)

    res = _load(run, 'resources', 'resources.csv')
    if res is not None and 't' in res:
        m = _window(res, t0, t1)
        for col in res:
            g = re.fullmatch(r'cpu_(.+)_pct', col)
            if g:
                v = np.asarray(res[col], dtype=float)[m]
                out[f'cpu_{g.group(1)}_mean_pct'] = _stat(v, np.mean)
                out[f'cpu_{g.group(1)}_peak_pct'] = _stat(v, np.max)
                continue
            g = re.fullmatch(r'rss_(.+)_mb', col)
            if g:
                out[f'rss_{g.group(1)}_peak_mb'] = _stat(
                    np.asarray(res[col], dtype=float)[m], np.max)
        if 'ram_used_mb' in res:
            out['ram_used_peak_mb'] = _stat(
                np.asarray(res['ram_used_mb'], dtype=float)[m], np.max)
    return out
