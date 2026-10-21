"""SDF -> ground-truth occupancy grid (docs/specs/03 section 3.2). numpy/scipy/stdlib only."""

import argparse
import math
import os
import xml.etree.ElementTree as ET
from typing import List, Optional, Tuple

import numpy as np
from scipy import ndimage

from .common import GtGrid

ROBOT_BODY_Z_LO = 0.03
ROBOT_BODY_Z_HI = 0.25
R_INSCRIBED_M = 0.125
GRID_MARGIN_M = 0.50


class WorldNotSealed(Exception):
    """a_clean touches the outermost ring of the grid."""


class UnsupportedSdf(Exception):
    """SDF feature the rasteriser does not handle."""


def _parse_pose(elem, where):
    """Return (x, y, z, yaw) from a <pose> child of elem (zeros if absent)."""
    if elem is None:
        return (0.0, 0.0, 0.0, 0.0)
    p = elem.find('pose')
    if p is None:
        return (0.0, 0.0, 0.0, 0.0)
    if p.get('relative_to') is not None:
        raise UnsupportedSdf('relative_to pose in ' + where)
    vals = [float(v) for v in (p.text or '').split()]
    vals += [0.0] * (6 - len(vals))
    x, y, z, r, pt, yaw = vals[:6]
    if abs(r) > 1e-9 or abs(pt) > 1e-9:
        raise UnsupportedSdf('non-zero roll/pitch in ' + where)
    return (x, y, z, yaw)


def _compose(a, b):
    c, s = math.cos(a[3]), math.sin(a[3])
    return (a[0] + c * b[0] - s * b[1], a[1] + s * b[0] + c * b[1], a[2] + b[2], a[3] + b[3])


def _parse_world(sdf_path):
    """Return (world_name, models) with models = [(name, [obstacle-candidate dicts])].
    Each collision dict: kind, pose (x, y, z, yaw), size/radius/length."""
    root = ET.parse(sdf_path).getroot()
    world = root.find('world')
    if world is None:
        raise UnsupportedSdf('no <world> element')
    for child in world:
        if child.tag == 'include':
            raise UnsupportedSdf('<include> in world')
    models = []
    for model in world.findall('model'):
        name = model.get('name', '')
        if model.find('model') is not None:
            raise UnsupportedSdf('nested <model> in model ' + name)
        if model.find('include') is not None:
            raise UnsupportedSdf('<include> in model ' + name)
        if model.find('frame') is not None:
            raise UnsupportedSdf('<frame> in model ' + name)
        where = 'model ' + name
        pm = _parse_pose(model, where)
        cols = []
        for link in model.findall('link'):
            pl = _parse_pose(link, where)
            for col in link.findall('collision'):
                pc = _parse_pose(col, where)
                pose = _compose(_compose(pm, pl), pc)
                geom = col.find('geometry')
                if geom is None:
                    continue
                kids = [g for g in geom]
                if len(kids) != 1:
                    raise UnsupportedSdf('geometry without exactly one shape in ' + where)
                g = kids[0]
                if g.tag == 'box':
                    sx, sy, sz = [float(v) for v in g.find('size').text.split()]
                    cols.append(dict(kind='box', pose=pose, size=(sx, sy, sz)))
                elif g.tag == 'cylinder':
                    cols.append(dict(kind='cylinder', pose=pose,
                                     radius=float(g.find('radius').text),
                                     length=float(g.find('length').text)))
                elif g.tag == 'sphere':
                    cols.append(dict(kind='sphere', pose=pose,
                                     radius=float(g.find('radius').text)))
                elif g.tag == 'plane':
                    continue
                else:
                    raise UnsupportedSdf('%s geometry in %s' % (g.tag, where))
        models.append((name, cols))
    return world.get('name', ''), models


def _z_interval(c):
    z = c['pose'][2]
    if c['kind'] == 'box':
        h = c['size'][2] / 2
    elif c['kind'] == 'cylinder':
        h = c['length'] / 2
    else:
        h = c['radius']
    return z - h, z + h


def _footprint_bbox(c):
    x, y, _, yaw = c['pose']
    if c['kind'] == 'box':
        hx, hy = c['size'][0] / 2, c['size'][1] / 2
        ex = abs(math.cos(yaw)) * hx + abs(math.sin(yaw)) * hy
        ey = abs(math.sin(yaw)) * hx + abs(math.cos(yaw)) * hy
    else:
        ex = ey = c['radius']
    return x - ex, x + ex, y - ey, y + ey


def build(sdf_path: str, reachable_seed_xy, spawn_xy=None, resolution: float = 0.05,
          robot_body_z_lo: float = ROBOT_BODY_Z_LO, robot_body_z_hi: float = ROBOT_BODY_Z_HI,
          r_inscribed_m: float = R_INSCRIBED_M, grid_margin_m: float = GRID_MARGIN_M) -> GtGrid:
    res = float(resolution)
    world_name, models = _parse_world(sdf_path)
    obstacles = []   # (model_index, collision)
    for mi, (_, cols) in enumerate(models):
        for c in cols:
            zlo, zhi = _z_interval(c)
            if zhi > robot_body_z_lo and zlo < robot_body_z_hi:
                obstacles.append((mi, c))
    if not obstacles:
        raise UnsupportedSdf('no obstacles found in world ' + world_name)

    bbs = np.array([_footprint_bbox(c) for _, c in obstacles])
    minx, maxx = bbs[:, 0].min() - grid_margin_m, bbs[:, 1].max() + grid_margin_m
    miny, maxy = bbs[:, 2].min() - grid_margin_m, bbs[:, 3].max() + grid_margin_m
    x0 = math.floor(minx / res) * res
    y0 = math.floor(miny / res) * res
    W = int(math.ceil((maxx - x0) / res))
    H = int(math.ceil((maxy - y0) / res))

    occ = np.zeros((H, W), bool)
    obs_id = np.full((H, W), -1, np.int16)
    for mi, c in obstacles:
        bx0, bx1, by0, by1 = _footprint_bbox(c)
        i0 = max(int(math.floor((bx0 - x0) / res)) - 1, 0)
        i1 = min(int(math.ceil((bx1 - x0) / res)) + 1, W)
        j0 = max(int(math.floor((by0 - y0) / res)) - 1, 0)
        j1 = min(int(math.ceil((by1 - y0) / res)) + 1, H)
        if i0 >= i1 or j0 >= j1:
            continue
        cx = x0 + (np.arange(i0, i1) + 0.5) * res
        cy = y0 + (np.arange(j0, j1) + 0.5) * res
        CX, CY = np.meshgrid(cx, cy)
        px, py, _, yaw = c['pose']
        dx, dy = CX - px, CY - py
        if c['kind'] == 'box':
            cs, sn = math.cos(yaw), math.sin(yaw)
            lx = cs * dx + sn * dy
            ly = -sn * dx + cs * dy
            m = (np.abs(lx) <= c['size'][0] / 2 + 1e-12) & (np.abs(ly) <= c['size'][1] / 2 + 1e-12)
        else:
            m = np.hypot(dx, dy) <= c['radius'] + 1e-12
        sub_occ = occ[j0:j1, i0:i1]
        sub_id = obs_id[j0:j1, i0:i1]
        new = m & (sub_id < 0)
        sub_id[new] = mi
        # lowest index wins: a lower mi may already be present; replace if higher
        lower = m & (sub_id > mi)
        sub_id[lower] = mi
        sub_occ |= m

    # cleanable area
    sx, sy = reachable_seed_xy
    si = int(math.floor((sx - x0) / res))
    sj = int(math.floor((sy - y0) / res))
    if not (0 <= si < W and 0 <= sj < H) or occ[sj, si]:
        raise ValueError('reachable seed %s is outside the grid or inside an obstacle'
                         % (tuple(reachable_seed_xy),))
    labels, _ = ndimage.label(~occ)
    a_clean = labels == labels[sj, si]
    ring = np.zeros_like(a_clean)
    ring[0, :] = ring[-1, :] = True
    ring[:, 0] = ring[:, -1] = True
    if (a_clean & ring).any():
        raise WorldNotSealed('cleanable area touches the grid border (world %s)' % world_name)

    dist = (ndimage.distance_transform_edt(~occ) * res).astype(np.float32)
    navigable = (dist >= r_inscribed_m) & a_clean

    a_reach = None
    A_reach = 0.0
    if spawn_xy is None:
        spawn_xy = reachable_seed_xy
    pi = int(math.floor((spawn_xy[0] - x0) / res))
    pj = int(math.floor((spawn_xy[1] - y0) / res))
    a_reach = np.zeros_like(navigable)
    if 0 <= pi < W and 0 <= pj < H and navigable[pj, pi]:
        lab2, _ = ndimage.label(navigable)
        a_reach = lab2 == lab2[pj, pi]
        A_reach = float(a_reach.sum()) * res * res

    nb = np.zeros_like(a_clean)
    nb[1:, :] |= a_clean[:-1, :]
    nb[:-1, :] |= a_clean[1:, :]
    nb[:, 1:] |= a_clean[:, :-1]
    nb[:, :-1] |= a_clean[:, 1:]
    boundary = occ & nb

    return GtGrid(occ=occ, a_clean=a_clean, navigable=navigable, boundary=boundary,
                  dist_to_obstacle=dist, obs_id=obs_id, obs_names=[n for n, _ in models],
                  x0=float(x0), y0=float(y0), res=res, world_name=world_name, a_reach=a_reach,
                  A_clean_m2=float(a_clean.sum()) * res * res, A_reach_m2=A_reach)


_ARRAYS = ('occ', 'a_clean', 'navigable', 'boundary', 'dist_to_obstacle', 'obs_id', 'a_reach')


def save(gt: GtGrid, path: str) -> None:
    np.savez_compressed(
        path, occ=gt.occ, a_clean=gt.a_clean, navigable=gt.navigable, boundary=gt.boundary,
        dist_to_obstacle=gt.dist_to_obstacle.astype(np.float32), obs_id=gt.obs_id.astype(np.int16),
        a_reach=gt.a_reach if gt.a_reach is not None else np.zeros_like(gt.occ),
        obs_names=np.array(gt.obs_names, dtype=str), x0=gt.x0, y0=gt.y0, res=gt.res,
        world_name=np.array(gt.world_name), A_clean_m2=gt.A_clean_m2, A_reach_m2=gt.A_reach_m2)


def load(path: str) -> GtGrid:
    with np.load(path, allow_pickle=False) as z:
        return GtGrid(
            occ=z['occ'], a_clean=z['a_clean'], navigable=z['navigable'], boundary=z['boundary'],
            dist_to_obstacle=z['dist_to_obstacle'], obs_id=z['obs_id'],
            obs_names=[str(s) for s in z['obs_names']], x0=float(z['x0']), y0=float(z['y0']),
            res=float(z['res']), world_name=str(z['world_name']), a_reach=z['a_reach'],
            A_clean_m2=float(z['A_clean_m2']), A_reach_m2=float(z['A_reach_m2']))


def export_nav2_map(gt: GtGrid, prefix: str) -> Tuple[str, str]:
    """Write <prefix>.pgm + <prefix>.yaml (free 254 in a_clean, occupied 0, unknown 205)."""
    img = np.full(gt.occ.shape, 205, np.uint8)
    img[gt.a_clean] = 254
    img[gt.occ] = 0
    img = img[::-1, :]
    h, w = img.shape
    pgm, yml = prefix + '.pgm', prefix + '.yaml'
    with open(pgm, 'wb') as f:
        f.write(b'P5\n%d %d\n255\n' % (w, h))
        f.write(img.tobytes())
    with open(yml, 'w') as f:
        f.write('image: %s\nresolution: %.6f\norigin: [%.6f, %.6f, 0.0]\nnegate: 0\n'
                'occupied_thresh: 0.65\nfree_thresh: 0.25\n'
                % (os.path.basename(pgm), gt.res, gt.x0, gt.y0))
    return pgm, yml


def save_png(gt: GtGrid, path: str, spawn_xy: Optional[Tuple[float, float]] = None) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    img = np.full(gt.occ.shape + (3,), 0.85)
    img[gt.a_clean] = (1.0, 1.0, 1.0)
    img[gt.navigable] = (0.8, 0.95, 0.8)
    img[gt.occ] = (0.0, 0.0, 0.0)
    h, w = gt.occ.shape
    fig, ax = plt.subplots(figsize=(8, 8 * h / max(w, 1)))
    ax.imshow(img, origin='lower', extent=(gt.x0, gt.x0 + w * gt.res, gt.y0, gt.y0 + h * gt.res))
    if spawn_xy is not None:
        ax.plot([spawn_xy[0]], [spawn_xy[1]], 'r.', ms=8)
    ax.set_title('%s  A_clean=%.2f m2' % (gt.world_name, gt.A_clean_m2))
    ax.set_xlabel('x [m]')
    ax.set_ylabel('y [m]')
    fig.savefig(path, dpi=120, bbox_inches='tight')
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Build the ground-truth grid of an SDF world')
    ap.add_argument('--sdf', required=True)
    ap.add_argument('--seed', required=True, nargs=2, type=float, metavar=('X', 'Y'))
    ap.add_argument('--spawn', nargs=2, type=float, default=None, metavar=('X', 'Y'))
    ap.add_argument('--res', type=float, default=0.05)
    ap.add_argument('--out', default=None)
    ap.add_argument('--png', default=None)
    ap.add_argument('--export-map', default=None, metavar='PREFIX')
    a = ap.parse_args(argv)
    gt = build(a.sdf, tuple(a.seed), tuple(a.spawn) if a.spawn else None, a.res)
    if a.out:
        save(gt, a.out)
    if a.png:
        save_png(gt, a.png, tuple(a.spawn) if a.spawn else tuple(a.seed))
    if a.export_map:
        export_nav2_map(gt, a.export_map)
    print('%s A_clean_m2=%.3f A_reach_m2=%.3f shape=%s' %
          (gt.world_name, gt.A_clean_m2, gt.A_reach_m2, gt.occ.shape))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
