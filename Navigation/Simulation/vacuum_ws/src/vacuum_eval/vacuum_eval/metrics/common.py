"""Shared helpers for the offline metric modules (docs/specs/00 section 0.10).

Pure Python + numpy. No ROS imports here.
"""

import csv
import json
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

SE2 = Tuple[float, float, float]


def wrap_angle(a):
    """Wrap to (-pi, pi]. Works on floats and numpy arrays."""
    return np.arctan2(np.sin(a), np.cos(a)) if isinstance(a, np.ndarray) \
        else math.atan2(math.sin(a), math.cos(a))


def se2_compose(a: SE2, b: SE2) -> SE2:
    """a o b : pose b expressed in the frame of a, returned in a's parent frame."""
    c, s = math.cos(a[2]), math.sin(a[2])
    return (a[0] + c * b[0] - s * b[1], a[1] + s * b[0] + c * b[1],
            wrap_angle(a[2] + b[2]))


def se2_inverse(a: SE2) -> SE2:
    c, s = math.cos(a[2]), math.sin(a[2])
    return (-(c * a[0] + s * a[1]), -(-s * a[0] + c * a[1]), wrap_angle(-a[2]))


def se2_compose_arrays(t: SE2, xs: np.ndarray, ys: np.ndarray, yaws: np.ndarray):
    """Vectorised t o (x, y, yaw) for arrays. Returns (X, Y, YAW) arrays."""
    c, s = math.cos(t[2]), math.sin(t[2])
    return (t[0] + c * xs - s * ys, t[1] + s * xs + c * ys, wrap_angle(t[2] + yaws))


def load_csv(path: str) -> Dict[str, np.ndarray]:
    """Read a CSV with a header into {column: array}. Numeric columns become float
    arrays (empty field -> nan); columns containing any non-numeric text stay
    object arrays of str."""
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        cols: Dict[str, list] = {name: [] for name in (reader.fieldnames or [])}
        for row in reader:
            for k in cols:
                cols[k].append(row[k])
    out: Dict[str, np.ndarray] = {}
    for k, v in cols.items():
        try:
            out[k] = np.array([float(x) if x != '' else np.nan for x in v], dtype=float)
        except ValueError:
            out[k] = np.array(v, dtype=object)
    return out


def write_csv(path: str, columns: List[str], rows: List[list]) -> None:
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(columns)
        w.writerows(rows)


def write_json(path: str, obj) -> None:
    with open(path, 'w') as f:
        json.dump(obj, f, indent=2, sort_keys=True, default=_json_default)


def read_json(path: str):
    with open(path) as f:
        return json.load(f)


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f'not JSON serialisable: {type(o)}')


@dataclass
class GtGrid:
    """Ground-truth grid of a world (docs/specs/03 section 3.2). Arrays are [row=j (y), col=i (x)].

    Cell (i, j) has centre (x0 + (i + 0.5) * res, y0 + (j + 0.5) * res) in the world frame.
    """
    occ: np.ndarray                 # bool, obstacle cells
    a_clean: np.ndarray             # bool, cleanable (free, connected to the seed)
    navigable: np.ndarray           # bool, robot-centre navigable (dist >= r_inscribed) & a_clean
    boundary: np.ndarray            # bool, obstacle cells with a 4-neighbour in a_clean
    dist_to_obstacle: np.ndarray    # float32 metres to the nearest obstacle cell centre
    obs_id: np.ndarray              # int16, -1 for free cells else index into obs_names
    obs_names: List[str]
    x0: float
    y0: float
    res: float
    world_name: str = ''
    a_reach: Optional[np.ndarray] = None   # bool, navigable component containing the spawn
    A_clean_m2: float = 0.0
    A_reach_m2: float = 0.0

    @property
    def shape(self):
        return self.occ.shape

    def world_to_cell(self, x, y):
        """Return integer (i, j) for world coordinates (floor; may be out of range)."""
        return (np.floor((np.asarray(x) - self.x0) / self.res).astype(int),
                np.floor((np.asarray(y) - self.y0) / self.res).astype(int))

    def cell_centers(self):
        """Return (X, Y) arrays of cell-centre world coordinates, shape == occ.shape."""
        h, w = self.occ.shape
        xs = self.x0 + (np.arange(w) + 0.5) * self.res
        ys = self.y0 + (np.arange(h) + 0.5) * self.res
        return np.meshgrid(xs, ys)


@dataclass
class Run:
    """In-memory view of one run directory (docs/specs/02 section 2.4).

    `meta` is run_meta.yaml as a dict. CSV tables are {column: array} dicts or None
    if the file does not exist. `episode_start_t` / `episode_end_t` are absolute sim
    seconds (docs/specs/02 section 2.1).
    """
    run_dir: str = ''
    meta: dict = field(default_factory=dict)
    trajectory: Optional[Dict[str, np.ndarray]] = None
    cmd_vel: Optional[Dict[str, np.ndarray]] = None
    goal_events: Optional[Dict[str, np.ndarray]] = None
    feedback: Optional[Dict[str, np.ndarray]] = None
    plans: Optional[Dict[str, np.ndarray]] = None
    collisions_raw: Optional[Dict[str, np.ndarray]] = None
    loop_events: Optional[Dict[str, np.ndarray]] = None
    dyn_obstacles: Optional[Dict[str, np.ndarray]] = None
    rates: Optional[Dict[str, np.ndarray]] = None
    responsiveness_events: Optional[Dict[str, np.ndarray]] = None
    events: Optional[Dict[str, np.ndarray]] = None
    episode_start_t: float = 0.0
    episode_end_t: float = 0.0


def load_run(run_dir: str) -> Run:
    """Load every raw file that exists in `run_dir`. Episode window is filled in by
    compute_metrics (spec 02 section 2.8), not here."""
    import yaml
    run = Run(run_dir=run_dir)
    meta_path = os.path.join(run_dir, 'run_meta.yaml')
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            run.meta = yaml.safe_load(f) or {}
    for attr, fname in [('trajectory', 'trajectory.csv'), ('cmd_vel', 'cmd_vel.csv'),
                        ('goal_events', 'goal_events.csv'), ('feedback', 'feedback.csv'),
                        ('plans', 'plans.csv'), ('collisions_raw', 'collisions_raw.csv'),
                        ('loop_events', 'loop_events.csv'),
                        ('dyn_obstacles', 'dyn_obstacles.csv'), ('rates', 'rates.csv'),
                        ('responsiveness_events', 'responsiveness_events.csv'),
                        ('events', 'events.csv')]:
        path = os.path.join(run_dir, fname)
        if os.path.exists(path):
            setattr(run, attr, load_csv(path))
    return run
