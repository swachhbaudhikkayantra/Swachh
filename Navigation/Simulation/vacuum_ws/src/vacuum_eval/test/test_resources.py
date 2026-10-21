import numpy as np

from vacuum_eval.metrics.common import Run
from vacuum_eval.metrics.resources import compute_resource_metrics


def _w(p, header, rows):
    p.write_text(header + '\n' + '\n'.join(','.join(map(str, r)) for r in rows) + '\n')


def test_resources_window(tmp_path):
    _w(tmp_path / 'rtf.csv', 't,t_rel,wall_dt,sim_dt,rtf',
       [(t, t, 1, 1, r) for t, r in zip(range(10), [0.1, 1, 1, 0.5, 1, 1, 1, 1, 1, 0.2])])
    _w(tmp_path / 'resources.csv', 't,t_rel,cpu_total_pct,ram_used_mb,cpu_gz_pct,rss_gz_mb',
       [(t, t, 10, 1000 + t, 100 + t, 500 + t) for t in range(10)])
    run = Run(run_dir=str(tmp_path), episode_start_t=2.0, episode_end_t=6.0)
    m = compute_resource_metrics(run)
    v = np.array([1, 0.5, 1, 1, 1])
    assert np.isclose(m['rtf_mean'], v.mean())
    assert np.isclose(m['rtf_min'], 0.5)
    assert np.isclose(m['rtf_p05'], np.percentile(v, 5))
    assert m['cpu_gz_mean_pct'] == 104.0
    assert m['cpu_gz_peak_pct'] == 106.0
    assert m['rss_gz_peak_mb'] == 506.0
    assert m['ram_used_peak_mb'] == 1006.0


def test_resources_missing(tmp_path):
    m = compute_resource_metrics(Run(run_dir=str(tmp_path), episode_end_t=5.0))
    assert m['rtf_mean'] is None and m['ram_used_peak_mb'] is None
