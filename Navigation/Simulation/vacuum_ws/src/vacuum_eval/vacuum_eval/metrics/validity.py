"""Per-episode validity gates (docs/specs/02): image drops and RTAB-Map stalls."""

import hashlib
import json
import os

import numpy as np
import yaml

from .common import load_csv

VALIDITY_KEYS = ['img_color_rate_hz_p05', 'img_depth_rate_hz_p05', 'img_drop_pct', 'img_depth_rate_hz_mean',
                 'rtabmap_updates', 'rtabmap_max_gap_s', 'rtf_true_mean', 'config_hash',
                 'episode_valid', 'invalid_reasons']
_DEFAULTS = {'camera_hz': 30.0, 'max_img_drop_pct': 10.0, 'max_rtabmap_gap_s': 5.0,
             'min_rtabmap_update_frac': 0.5}
_SRC = '/home/hrishikesh/Swachh/Navigation/Simulation/vacuum_ws/src'
_CFG_FILES = ['vacuum_nav2/config/nav2_params.yaml', 'vacuum_slam/config/rtabmap.yaml',
              'vacuum_controller/config/controllers.yaml']


def load_thresholds():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'config',
                     'eval_defaults.yaml')
    out = dict(_DEFAULTS)
    try:
        with open(p) as f:
            out.update((yaml.safe_load(f) or {}).get('validity') or {})
    except Exception:  # noqa: BLE001
        pass
    return out


def config_hash(meta):
    h = hashlib.sha256()
    h.update(json.dumps((meta or {}).get('config_snapshot'), sort_keys=True,
                        default=str).encode())
    for rel in _CFG_FILES:
        try:
            with open(os.path.join(_SRC, rel), 'rb') as f:
                h.update(f.read())
        except OSError:
            h.update(b'missing:' + rel.encode())
    return h.hexdigest()[:12]


def _p05(tbl, col, t0, t1):
    if not tbl or col not in tbl or 't' not in tbl:
        return None
    t = np.asarray(tbl['t'], float)
    v = np.asarray(tbl[col], float)[(t >= t0) & (t <= t1)]
    v = v[np.isfinite(v)]
    return float(np.percentile(v, 5)) if v.size else None


def compute_validity(run, thresholds=None):
    th = dict(load_thresholds(), **(thresholds or {}))
    t0, t1 = float(run.episode_start_t), float(run.episode_end_t)
    dur = max(t1 - t0, 0.0)
    reasons = []
    out = {'img_color_rate_hz_p05': _p05(run.rates, 'n_color', t0, t1),
           'img_depth_rate_hz_p05': _p05(run.rates, 'n_depth', t0, t1)}
    drop = None
    n_arr = None
    r = run.rates
    if r and 'n_depth' in r and 't' in r and dur > 0:
        t = np.asarray(r['t'], float)
        n = np.nansum(np.asarray(r['n_depth'], float)[(t >= t0) & (t <= t1)])
        n_arr = n
        drop = float(min(100.0, max(0.0, 100.0 * (1.0 - n / (th['camera_hz'] * dur)))))
    out['img_drop_pct'] = drop
    out['img_depth_rate_hz_mean'] = (float(np.nansum(n_arr) / dur) if n_arr is not None else None)
    # RTAB-Map updates
    le = run.loop_events
    st = np.array([])
    if le and 't' in le:
        t = np.asarray(le['t'], float)
        st = np.sort(t[(t >= t0) & (t <= t1)])
    out['rtabmap_updates'] = int(st.size)
    out['rtabmap_max_gap_s'] = float(np.diff(st).max()) if st.size >= 2 else dur
    # true RTF
    rtf = None
    p = os.path.join(run.run_dir or '', 'rtf.csv')
    if run.run_dir and os.path.exists(p):
        try:
            d = load_csv(p)
            v = np.asarray(d.get('rtf', []), float)
            v = v[np.isfinite(v)]
            rtf = float(v.mean()) if v.size else None
        except Exception:  # noqa: BLE001
            pass
    out['rtf_true_mean'] = rtf
    out['config_hash'] = config_hash(run.meta)
    if drop is not None and drop > th['max_img_drop_pct']:
        reasons.append('img_drop_pct %.1f > %.1f' % (drop, th['max_img_drop_pct']))
    # AMCL and ground-truth-localization runs have no RTAB-Map; skip its rules there and
    # when no table was recorded
    slam = run.loop_events is not None and \
        (run.meta or {}).get('localization_mode') not in ('amcl', 'gt')
    if slam and out['rtabmap_max_gap_s'] > th['max_rtabmap_gap_s']:
        reasons.append('rtabmap_max_gap_s %.1f > %.1f' % (out['rtabmap_max_gap_s'],
                                                          th['max_rtabmap_gap_s']))
    if slam and st.size < th['min_rtabmap_update_frac'] * dur:
        reasons.append('rtabmap_updates %d < %.0f' % (st.size,
                                                      th['min_rtabmap_update_frac'] * dur))
    out['episode_valid'] = not reasons
    out['invalid_reasons'] = reasons
    return out
