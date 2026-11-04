"""Data-derived figures for the paper (no simulator needed): test-world layouts and robot trajectories
over the ground-truth floor plan. Everything is read from the run files; nothing is typed in."""
import csv, glob, json, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = os.path.expanduser('~/eval_runs_victus/')
OUT = os.path.expanduser('~/Swachh/docs/paper_out/figures/')
WORLDS = ['office', 'multi_room_loop', 'maze_dead_ends', 'two_rooms_door', 'avoid_u_trap', 'avoid_dynamic_sudden']


def grid(world):
    z = np.load(ROOT + '_gt/%s.npz' % world, allow_pickle=True)
    occ, reach = z['occ'], z['a_reach']
    x0, y0, res = float(z['x0']), float(z['y0']), float(z['res'])
    h, w = occ.shape
    return occ, reach, (x0, x0 + w * res, y0, y0 + h * res)


def draw_world(ax, world):
    occ, reach, ext = grid(world)
    img = np.ones(occ.shape + (3,))
    img[reach] = (0.88, 0.93, 0.98)        # reachable floor
    img[occ] = (0.12, 0.12, 0.12)          # obstacles and walls
    ax.imshow(img, origin='lower', extent=ext, interpolation='nearest')
    ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
    return ext


def traj(path):
    xs, ys, ts = [], [], []
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                xs.append(float(r['gt_x'])); ys.append(float(r['gt_y'])); ts.append(float(r['t_rel']))
            except (ValueError, KeyError):
                pass
    return np.array(xs), np.array(ys), np.array(ts)


def fig_worlds():
    fig, axs = plt.subplots(2, 3, figsize=(10, 6))
    for ax, w in zip(axs.ravel(), WORLDS):
        draw_world(ax, w)
        ax.set_title(w.replace('_', ' '), fontsize=10)
    fig.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=(0.12, 0.12, 0.12)),
                        plt.Rectangle((0, 0), 1, 1, color=(0.88, 0.93, 0.98))],
               labels=['walls and obstacles', 'reachable floor'], loc='lower center', ncol=2, frameon=False)
    fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(OUT + 'fig_test_worlds.png', dpi=200); plt.close(fig)


def fig_trajectories(campaign, worlds, variant, name, title_key):
    seeds = sorted({int(p.split('seed_')[1].split('/')[0]) for p in
                    glob.glob(ROOT + campaign + '/*/*/seed_*/summary.json')})
    fig, axs = plt.subplots(len(seeds), len(worlds), figsize=(3.2 * len(worlds), 2.6 * len(seeds)), squeeze=False)
    for j, w in enumerate(worlds):
        for i, s in enumerate(seeds):
            ax = axs[i][j]
            d = ROOT + '%s/%s/%s/seed_%d/' % (campaign, w, variant, s)
            if not os.path.exists(d + 'summary.json'):
                ax.axis('off'); continue
            draw_world(ax, w)
            x, y, t = traj(d + 'trajectory.csv')
            if len(x):
                sc = ax.scatter(x, y, c=t, s=1.2, cmap='viridis')
                ax.plot(x[0], y[0], 'o', color='tab:green', ms=5)
            sm = json.load(open(d + 'summary.json'))
            val = sm.get(title_key)
            ax.set_title('%s, seed %d%s' % (w.replace('_', ' '), s,
                         '' if val is None else ', %s %.0f %%' % ('coverage' if title_key.startswith('coverage') else 'GT-verified success', val)), fontsize=7)
    fig.tight_layout(); fig.savefig(OUT + name, dpi=200); plt.close(fig)


def read_pgm(path):
    with open(path, 'rb') as f:
        f.readline(); w, h = map(int, f.readline().split()); f.readline()
        return np.frombuffer(f.read(), dtype=np.uint8).reshape(h, w)


def explored_on_gt_grid(ep_dir, world):
    """Resample the final SLAM map onto the ground-truth grid in the world frame.
    The SLAM map frame starts at the robot's spawn pose: world = R(yaw) * map + (spawn_x, spawn_y).
    Returns an array: -1 unknown, 0 free, 1 occupied (nearest cell), plus the GT extent."""
    import yaml
    meta = yaml.safe_load(open(ep_dir + 'run_meta.yaml'))
    sx, sy, yaw = float(meta['spawn_x']), float(meta['spawn_y']), float(meta['spawn_yaw'])
    my = yaml.safe_load(open(ep_dir + 'maps/final_map.yaml'))
    res, (ox, oy) = float(my['resolution']), my['origin'][:2]
    pgm = read_pgm(ep_dir + 'maps/final_map.pgm')[::-1]        # row 0 = lowest y
    occ, reach, ext = grid(world)
    h, w = occ.shape
    gres = (ext[1] - ext[0]) / w
    xs = ext[0] + (np.arange(w) + 0.5) * gres
    ys = ext[2] + (np.arange(h) + 0.5) * gres
    X, Y = np.meshgrid(xs, ys)
    c, s_ = np.cos(yaw), np.sin(yaw)
    mx = c * (X - sx) + s_ * (Y - sy)                          # inverse of world = R*map + spawn
    my_ = -s_ * (X - sx) + c * (Y - sy)
    ci = np.floor((mx - ox) / res).astype(int)
    ri = np.floor((my_ - oy) / res).astype(int)
    ok = (ci >= 0) & (ci < pgm.shape[1]) & (ri >= 0) & (ri < pgm.shape[0])
    out = -np.ones(occ.shape, dtype=int)
    v = np.full(occ.shape, 205, dtype=np.uint8)
    v[ok] = pgm[ri[ok], ci[ok]]
    out[v >= 250] = 0
    out[v <= 5] = 1
    return out, ext, occ, reach


def fig_gt_vs_explored():
    worlds = ['office', 'multi_room_loop', 'maze_dead_ends']
    seeds = [101, 102, 103]
    fig, axs = plt.subplots(len(worlds), 1 + len(seeds), figsize=(11.5, 2.9 * len(worlds)))
    for i, w in enumerate(worlds):
        draw_world(axs[i][0], w)
        axs[i][0].set_title('%s: actual' % w.replace('_', ' '), fontsize=8)
        for j, s in enumerate(seeds):
            d = ROOT + 'quick_exploration_noise/%s/frontier/seed_%d/' % (w, s)
            ex, ext, occ, reach = explored_on_gt_grid(d, w)
            img = np.ones(ex.shape + (3,)) * 0.80                   # unknown
            img[ex == 0] = (0.97, 0.97, 0.97)
            img[ex == 1] = (0.10, 0.10, 0.10)
            ax = axs[i][j + 1]
            ax.imshow(img, origin='lower', extent=ext, interpolation='nearest')
            ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
            sm = json.load(open(d + 'summary.json'))
            ax.set_title('explored, seed %d (coverage %.0f %%)' % (s, sm['coverage_explored_pct']), fontsize=8)
            # alignment check: share of explored-occupied cells within 1 cell of a true obstacle
            from scipy.ndimage import binary_dilation
            near = binary_dilation(occ, iterations=2)
            n_occ = int((ex == 1).sum())
            print('%s seed %d: explored occupied cells %d, within 2 cells of true obstacle: %.0f %%' % (
                w, s, n_occ, 100.0 * (near & (ex == 1)).sum() / max(n_occ, 1)))
    fig.tight_layout(); fig.savefig(OUT + 'fig_actual_vs_explored.png', dpi=200); plt.close(fig)


COLORS = {'office': 'tab:green', 'multi_room_loop': 'tab:orange', 'maze_dead_ends': 'tab:blue',
          'two_rooms_door': 'tab:purple'}


def fig_coverage_curves():
    """Per-episode coverage over time (all 9 episodes, no confidence band)."""
    fig, ax = plt.subplots(figsize=(6.5, 4))
    seen = set()
    for w in ['office', 'multi_room_loop', 'maze_dead_ends']:
        for p in sorted(glob.glob(ROOT + 'quick_exploration_noise/%s/frontier/seed_*/coverage_curve.csv' % w)):
            t, c = [], []
            with open(p) as f:
                for r in csv.DictReader(f):
                    t.append(float(r['t_ep'])); c.append(float(r['coverage_explored_pct']))
            ax.plot(t, c, color=COLORS[w], lw=1.3, alpha=0.85,
                    label=None if w in seen else w.replace('_', ' '))
            seen.add(w)
    ax.set_xlabel('Episode time (s)'); ax.set_ylabel('Explored share of reachable area (%)')
    ax.set_ylim(0, 100); ax.grid(alpha=0.3); ax.legend(frameon=False)
    ax.set_title('Exploration coverage over time, one line per episode', fontsize=9)
    fig.tight_layout(); fig.savefig(OUT + 'fig_coverage_vs_time.png', dpi=200); plt.close(fig)


def fig_nav_success():
    """Navigation success by world: Nav2-reported versus ground-truth-verified, pooled over goals."""
    V = json.load(open(os.path.expanduser('~/Swachh/docs/paper_out/paper_values.json')))
    names = ['maze_dead_ends', 'office', 'two_rooms_door', 'pooled']
    fig, ax = plt.subplots(figsize=(6.5, 4)); width = 0.38
    for k, (key, lab, col) in enumerate((('nav2_success', 'Nav2-reported', 'lightsteelblue'),
                                         ('gt_success', 'ground-truth verified (0.30 m)', 'tab:blue'))):
        pct = [V['navigation'][n][key]['pct'] for n in names]
        lo = [V['navigation'][n][key]['pct'] - V['navigation'][n][key]['ci_lo'] for n in names]
        hi = [V['navigation'][n][key]['ci_hi'] - V['navigation'][n][key]['pct'] for n in names]
        xs = np.arange(len(names)) + (k - 0.5) * width
        ax.bar(xs, pct, width, color=col, label=lab, yerr=[lo, hi], capsize=3)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(['%s\n(%d goals)' % (n.replace('_', ' '), V['navigation'][n]['goals_total']) for n in names], fontsize=8)
    ax.set_ylabel('Goals reached (%)'); ax.set_ylim(0, 100); ax.grid(axis='y', alpha=0.3)
    ax.legend(frameon=False, fontsize=8)
    ax.set_title('Navigation success, pooled over goals (95 % bootstrap interval)', fontsize=9)
    fig.tight_layout(); fig.savefig(OUT + 'fig_nav_success.png', dpi=200); plt.close(fig)


def fig_ate_points():
    """Absolute trajectory error per episode (every point shown; hollow marker = odometry corrupted by contact)."""
    fig, ax = plt.subplots(figsize=(6.5, 4))
    worlds = ['office', 'multi_room_loop', 'maze_dead_ends']
    for i, w in enumerate(worlds):
        for p in sorted(glob.glob(ROOT + 'quick_exploration_noise/%s/frontier/seed_*/summary.json' % w)):
            j = json.load(open(p))
            v = j.get('ate_fixed_rmse_m')
            if v is None:
                continue
            bad = j.get('odom_corrupted_by_contact') == 1
            ax.scatter(i + (int(p.split('seed_')[1][:3]) - 102) * 0.06, v, s=45, color=COLORS[w],
                       facecolors='none' if bad else COLORS[w], linewidths=1.6)
    ax.scatter([], [], s=45, color='k', label='odometry intact')
    ax.scatter([], [], s=45, facecolors='none', edgecolors='k', linewidths=1.6, label='odometry corrupted by contact')
    ax.set_xticks(range(len(worlds))); ax.set_xticklabels([w.replace('_', ' ') for w in worlds])
    ax.set_ylabel('ATE (m)'); ax.set_ylim(bottom=0); ax.grid(axis='y', alpha=0.3); ax.legend(frameon=False, fontsize=8)
    ax.set_title('Trajectory error per exploration episode (episodes without a value are omitted)', fontsize=8)
    fig.tight_layout(); fig.savefig(OUT + 'fig_ate_points.png', dpi=200); plt.close(fig)


def fig_costmaps():
    """Costmap layers from one live run: SLAM map, global costmap, local costmap (captured from the running stack).
    Costmap cell values: -1 unknown, 0 free, 1..98 inflation gradient, 99 inscribed, 100 lethal obstacle."""
    zs = np.load(os.path.expanduser('~/Swachh/docs/paper_out/data/costmap_series_office.npz'))
    n = int(zs['count'][0])
    k = int(np.argmax([(zs['local_%d' % i] >= 1).sum() for i in range(n)]))   # rule: most obstacle/inflation cells in the local costmap
    z = {key: zs['%s_%d' % (key, k)] for key in ('slam', 'global', 'local')}
    z.update({key + '_meta': zs['%s_meta_%d' % (key, k)] for key in ('slam', 'global', 'local')})
    robot = zs['pose_%d' % k]
    print('costmap figure: snapshot %d of %d (rule: max local obstacle+inflation cells)' % (k, n))
    from matplotlib.colors import ListedColormap, BoundaryNorm
    import matplotlib.patches as mp

    def paint(a, slam=False):
        img = np.ones(a.shape + (3,))
        if slam:
            img[a == -1] = (0.80, 0.80, 0.80); img[a == 0] = (0.97, 0.97, 0.97); img[a >= 65] = (0.10, 0.10, 0.10)
            return img
        img[a == -1] = (0.80, 0.80, 0.80)
        infl = (a >= 1) & (a <= 98)
        t = (a[infl] - 1) / 97.0                                  # 0 (far) .. 1 (near)
        img[infl] = np.stack([np.ones_like(t), 0.92 - 0.55 * t, 0.65 - 0.55 * t], axis=1)
        img[a == 99] = (0.75, 0.10, 0.10)                          # inscribed
        img[a == 100] = (0.10, 0.10, 0.10)                         # lethal obstacle
        return img

    def crop(a, meta, pad=6):
        known = np.where(a != -1)
        y0, y1, x0, x1 = known[0].min() - pad, known[0].max() + pad, known[1].min() - pad, known[1].max() + pad
        y0, x0 = max(y0, 0), max(x0, 0); y1, x1 = min(y1, a.shape[0]), min(x1, a.shape[1])
        res, ox, oy = meta
        return a[y0:y1, x0:x1], [ox + x0 * res, ox + x1 * res, oy + y0 * res, oy + y1 * res]

    fig, axs = plt.subplots(1, 3, figsize=(12, 4))
    for ax, key, title, slam in ((axs[0], 'slam', 'SLAM occupancy grid (static layer)', True),
                                 (axs[1], 'global', 'Global costmap', False),
                                 (axs[2], 'local', 'Local costmap (4 x 4 m rolling window)', False)):
        a, ext = crop(z[key], z[key + '_meta'], pad=6 if key != 'local' else 0)
        ax.imshow(paint(a, slam), origin='lower', extent=ext, interpolation='nearest')
        ax.set_title(title, fontsize=9); ax.set_aspect('equal'); ax.set_xlabel('x (m)', fontsize=8)
        if np.all(np.isfinite(robot)):
            ax.plot(robot[0], robot[1], marker='^', color='tab:green', ms=7, mec='k', ls='none')
        ax.tick_params(labelsize=7)
    axs[1].legend(handles=[mp.Patch(color=(0.10, 0.10, 0.10), label='lethal obstacle'),
                           mp.Patch(color=(0.75, 0.10, 0.10), label='inscribed (robot cannot enter)'),
                           mp.Patch(color=(1.0, 0.55, 0.30), label='inflation (cost falls with distance)'),
                           mp.Patch(color=(0.80, 0.80, 0.80), label='unknown')],
                  loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=2, fontsize=7, frameon=False)
    fig.tight_layout(); fig.savefig(OUT + 'fig_costmap_layers.png', dpi=200); plt.close(fig)


if __name__ == '__main__':
    fig_worlds()
    fig_trajectories('quick_exploration_noise', ['office', 'multi_room_loop', 'maze_dead_ends'], 'frontier',
                     'fig_exploration_trajectories.png', 'coverage_explored_pct')
    fig_trajectories('quick_navigation', ['office', 'two_rooms_door', 'maze_dead_ends'], 'scripted_goals_random20',
                     'fig_navigation_trajectories.png', 'nav_success_gt_pct')
    fig_gt_vs_explored()
    fig_coverage_curves(); fig_nav_success(); fig_ate_points(); fig_costmaps()
    print('figures written to', OUT)
