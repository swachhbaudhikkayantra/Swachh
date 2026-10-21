"""Exact 2D robot-vs-obstacle geometry (no grid). No ROS, numpy only.

Signed distance convention: positive = gap between the shapes, 0 = touching,
negative = overlap (minus the minimum-translation penetration depth).
All functions broadcast over numpy arrays of robot poses (trajectory).
"""

import math
from typing import Dict, List

import numpy as np

# Robot footprint: rectangle 0.30 x 0.25 m centred on base_footprint
# (same values as safety.HALF_L/HALF_W and r_inscribed_m = 0.125 = half width).
ROBOT_HALF_L = 0.150
ROBOT_HALF_W = 0.125


def load_obstacles(sdf_path: str, z_lo: float = None, z_hi: float = None) -> Dict[str, List[dict]]:
    """{model_name: [shape]} for collisions overlapping the robot body z band, using
    gt_grid's SDF parser. Shape: {'kind': 'box', 'cx','cy','hx','hy','yaw'} or
    {'kind': 'disc', 'cx','cy','r'} (cylinders and spheres)."""
    from . import gt_grid
    z_lo = gt_grid.ROBOT_BODY_Z_LO if z_lo is None else z_lo
    z_hi = gt_grid.ROBOT_BODY_Z_HI if z_hi is None else z_hi
    _, models = gt_grid._parse_world(sdf_path)
    out: Dict[str, List[dict]] = {}
    for name, cols in models:
        for c in cols:
            lo, hi = gt_grid._z_interval(c)
            if not (hi > z_lo and lo < z_hi):
                continue
            x, y, _, yaw = c['pose']
            if c['kind'] == 'box':
                out.setdefault(name, []).append(dict(kind='box', cx=x, cy=y, hx=c['size'][0] / 2,
                                                     hy=c['size'][1] / 2, yaw=yaw))
            else:
                out.setdefault(name, []).append(dict(kind='disc', cx=x, cy=y, r=c['radius']))
    return out


def _corners(cx, cy, yaw, hx, hy):
    """(..., 4, 2) world corners of rectangles; inputs broadcast."""
    cx, cy, yaw = np.broadcast_arrays(np.asarray(cx, float), np.asarray(cy, float),
                                      np.asarray(yaw, float))
    c, s = np.cos(yaw), np.sin(yaw)
    sx = np.array([-1, -1, 1, 1.0])
    sy = np.array([-1, 1, 1, -1.0])
    lx, ly = sx * hx, sy * hy
    X = cx[..., None] + c[..., None] * lx - s[..., None] * ly
    Y = cy[..., None] + s[..., None] * lx + c[..., None] * ly
    return np.stack([X, Y], axis=-1)


def _point_rect_dist(px, py, cx, cy, yaw, hx, hy):
    """Unsigned distance from points to rectangle (0 inside)."""
    c, s = np.cos(yaw), np.sin(yaw)
    dx, dy = px - cx, py - cy
    rx = c * dx + s * dy
    ry = -s * dx + c * dy
    return np.hypot(np.maximum(np.abs(rx) - hx, 0.0), np.maximum(np.abs(ry) - hy, 0.0))


def rect_rect_distance(rx, ry, ryaw, ox, oy, oyaw, ohx, ohy,
                       rhx=ROBOT_HALF_L, rhy=ROBOT_HALF_W):
    """Signed distance between robot rectangle(s) and oriented rectangle(s) (SAT).
    Overlap: -(minimum translation depth). Disjoint: exact vertex-to-rectangle distance."""
    rx, ry, ryaw, ox, oy, oyaw = np.broadcast_arrays(*(np.asarray(v, float) for v in
                                                      (rx, ry, ryaw, ox, oy, oyaw)))
    dx, dy = ox - rx, oy - ry
    gaps = []
    for ang, in ((ryaw,), (ryaw + math.pi / 2,), (oyaw,), (oyaw + math.pi / 2,)):
        ax, ay = np.cos(ang), np.sin(ang)
        ra = rhx * np.abs(np.cos(ryaw - ang)) + rhy * np.abs(np.sin(ryaw - ang))
        rb = ohx * np.abs(np.cos(oyaw - ang)) + ohy * np.abs(np.sin(oyaw - ang))
        gaps.append(np.abs(dx * ax + dy * ay) - ra - rb)
    gmax = np.max(np.stack(gaps), axis=0)
    ca = _corners(rx, ry, ryaw, rhx, rhy)
    cb = _corners(ox, oy, oyaw, ohx, ohy)
    d1 = _point_rect_dist(ca[..., 0], ca[..., 1], ox[..., None], oy[..., None],
                          oyaw[..., None], ohx, ohy).min(axis=-1)
    d2 = _point_rect_dist(cb[..., 0], cb[..., 1], rx[..., None], ry[..., None],
                          ryaw[..., None], rhx, rhy).min(axis=-1)
    return np.where(gmax >= 0.0, np.minimum(d1, d2), gmax)


def rect_disc_distance(rx, ry, ryaw, ox, oy, r, rhx=ROBOT_HALF_L, rhy=ROBOT_HALF_W):
    """Signed distance between robot rectangle(s) and disc(s)."""
    rx, ry, ryaw, ox, oy = np.broadcast_arrays(*(np.asarray(v, float) for v in (rx, ry, ryaw, ox, oy)))
    c, s = np.cos(ryaw), np.sin(ryaw)
    qx = c * (ox - rx) + s * (oy - ry)
    qy = -s * (ox - rx) + c * (oy - ry)
    ex, ey = np.abs(qx) - rhx, np.abs(qy) - rhy
    outside = np.hypot(np.maximum(ex, 0.0), np.maximum(ey, 0.0))
    inside = np.minimum(np.maximum(ex, ey), 0.0)
    return outside + inside - r


def shape_distance(rx, ry, ryaw, shape: dict):
    if shape['kind'] == 'box':
        return rect_rect_distance(rx, ry, ryaw, shape['cx'], shape['cy'], shape['yaw'],
                                  shape['hx'], shape['hy'])
    return rect_disc_distance(rx, ry, ryaw, shape['cx'], shape['cy'], shape['r'])


def trajectory_distances(rx, ry, ryaw, obstacles: Dict[str, List[dict]]) -> Dict[str, np.ndarray]:
    """{model_name: signed distance[N]} (min over the model's shapes)."""
    rx, ry, ryaw = (np.asarray(v, float) for v in (rx, ry, ryaw))
    ryaw = np.where(np.isfinite(ryaw), ryaw, 0.0)
    out = {}
    for name, shapes in obstacles.items():
        out[name] = np.min(np.stack([shape_distance(rx, ry, ryaw, sh) for sh in shapes]), axis=0)
    return out
