# 09. Evaluation metrics: what each number means and exactly how it is computed

Scope: the offline metric code in `Navigation/Simulation/vacuum_ws/src/vacuum_eval/vacuum_eval/metrics/` (14 modules), the orchestrator `compute_metrics.py`, the statistics in `aggregate.py` / `make_report.py`, and the config `config/eval_defaults.yaml`. The docs (`docs/METRICS_TO_BE_MEASURED.md`, `METRICS_STATUS.md`, `METRICS_AUDIT_2026-10-25.md`, `docs/specs/`) were read as context only.

**Rule used in this file:** formulas come from the code. Where the docs say something different, a "Doc vs code" note says so. Where I could not verify something from the code in scope, it is marked "not verified".

Abbreviations: GT = ground truth (true robot pose from Gazebo and true floor plan from the world SDF). `M/` = `vacuum_eval/metrics/`. "Episode" = the window described in section 2.

---

## 1. The big picture

### 1.1 Data flow

```
 run directory (raw CSVs + run_meta.yaml + maps/*.npz)
        |  common.load_run
        v
 compute_metrics.compute()          decides the episode window [t0, t1], status, end_reason
        |
        +-- resources      (A11, A12)                       M/resources.py
        +-- coverage       (#1, #8, #14, A1, A2, A3)        M/coverage.py   (uses GT grid)
        +-- trajectory     (#6, #7, A10, A14, A4 distance)  M/trajectory.py
        +-- contact_odom   (diagnostic D1)                  M/contact_odom.py
        +-- navigation     (#2, #10, #12, A4, A6-A9)        M/navigation.py (uses GT grid)
        +-- safety         (#3, #4, #9, A5)                 M/safety.py     (uses GT grid + exact geometry)
        +-- responsiveness (#5)                             M/responsiveness.py
        +-- loop_closure   (#11)                            M/loop_closure.py
        +-- validity       (episode_valid, RTF, image drops) M/validity.py
        +-- counters       (n_cmd_ticks, n_goals, distance_gt_m)
        v
 health.compute_health()  LAST: OK / LOW_N / SUSPECT / BAD / UNMEASURABLE / NA per headline metric
        v
 summary.json / summary.csv per episode   -->  aggregate.py / make_report.py (pooling, CIs)
```

Supporting modules: `common.py` (CSV/JSON IO, SE(2) helpers, the `GtGrid` and `Run` containers), `gt_grid.py` (SDF to grid), `geometry.py` (exact robot-vs-obstacle distances).

### 1.2 The ten-line summary of what is measured

| Question | Metric(s) | Measured against |
|---|---|---|
| How much of the floor did the robot see / build a map of? | #1 explored coverage, #8 map completeness, A1 curve | GT grid from the SDF |
| How much floor did the vacuum actually sweep? | #14 cleaning efficiency, A2, A3 | GT grid + GT trajectory |
| How long/busy was the episode? | #2 steps, A4, A6, A7 | Harness logs |
| Did it hit things? Did it pass obstacles cleanly? | #3, #4, #9, A5 | Contact sensor + exact geometry |
| Did it reach goals, and how directly? | #10, #12, A8, A9 | GT pose at Nav2 result time, A* on GT grid |
| How accurate is localisation/SLAM? | #6 ATE, #7 RPE, A10, A14 | GT pose |
| Does SLAM close loops correctly? | #11 | GT relative transform between nodes |
| How fast does the stack react? | #5 | Step-test timing |
| Is the run trustworthy? | A11, A12, validity gates, health flags | Rates, RTF, thresholds |

### 1.3 Bias to remember across everything

- Most "percent" metrics are **episode-level** numbers. The campaign tables then pool episodes (section 14). With 2-4 episodes per world the confidence intervals are wide.
- The headline coverage/cleaning numbers use the **reachable area** as the denominator, not all free floor (section 3.4).
- The navigation campaign of 2026-10-25 ran Nav2 + AMCL on a ground-truth map, not RTAB-Map. So #10, #12 and A14 describe that pipeline; the SLAM metrics (#6, #7, #8, #11) come from the exploration campaign (`METRICS_STATUS.md`, `METRICS_AUDIT`).
- Health flags are diagnosis labels. They never remove an episode. Only `status: invalid` (validity gates, section 2.3) is excluded.

---

## 2. Episode definition, status and validity (shared by every metric)

### 2.1 Episode window (`compute_metrics.determine_episode`)

| Item | Rule in code |
|---|---|
| Start `t0` | First `cmd_vel` row with `source == 'ctrl_stamped'` and `abs(vx) > 0.01` or `abs(wz) > 0.01` (`MOTION_EPS = 0.01`). If none: `end_reason = no_motion` (unless meta gives a harness reason), the window has zero length. |
| End `t1` | The earliest of: a `finished_signal` event at/after the start (`goals_done` if the detail contains "done"/"goals" or method is `scripted_goals`, else `finished`); `t0 + episode_timeout_sim_sec` (default 1200 s) -> `timeout`; the **stuck rule**; the last trajectory row. |
| Stuck rule (`find_stuck`) | GT position sampled on a 1 s grid from `t0`. Fires at time `grid[i+180]` when the maximum displacement from sample `i` over the next 180 s is below 0.30 m (`STUCK_WINDOW_S = 180`, `STUCK_DIST_M = 0.30`). Rotating in place does not stop it firing. |
| If episode ends at the last trajectory row | `end_reason` taken from meta (`timeout`, `stuck` or a harness reason), else `crash`. |
| Status | `failed` if end_reason in (`no_motion`, `crash`, `bringup_failed`); `partial` if any metric module raised an exception (its keys are set to None and a note is added); `invalid` if validity gates fail (2.3); else `ok`. |
| Fields | `episode_sim_sec = t1 - t0`, `bringup_sim_sec = t0 - first trajectory time`. |

Caveat: the 4-hour campaign had 2 maze episodes that never moved, which fed the metrics as 0 or None (see #1).

### 2.2 Time and frames

- All times are simulation seconds, except the primary step-test latencies of #5, which are wall-clock (2.5 and section 11).
- Frames: GT poses are in the Gazebo world frame. SLAM/AMCL poses are in the map frame and are mapped to the world with `t_world_map`; if absent, with the spawn pose (`spawn_x`, `spawn_y`, `spawn_yaw`). Wheel odometry is mapped with the spawn pose.
- SE(2) helpers in `common.py`: `wrap_angle` to (-pi, pi], `se2_compose(a, b)` = pose b expressed in a's frame returned in a's parent frame, `se2_inverse`.

### 2.3 Validity gates (`M/validity.py`) -> `status: invalid`

| Gate | Computation | Threshold (`eval_defaults.yaml`, code default identical) |
|---|---|---|
| Image drop | `drop = 100 * (1 - sum(n_depth in window) / (camera_hz * duration))`, clipped to [0, 100]. `n_depth` is the per-window depth image count in `rates.csv` | `camera_hz = 30`, invalid if `drop > 10 %` |
| RTAB-Map max gap | Largest gap between consecutive `loop_events.csv` rows in the window (`duration` if fewer than 2 rows) | invalid if `> 5 s` |
| RTAB-Map update count | Number of `loop_events` rows in the window | invalid if `< 0.5 * duration` (i.e. below 0.5 updates per second) |
| RTF (reported, not a gate) | Mean of `rtf.csv: rtf` over all rows (note: whole file, not the window) -> `rtf_true_mean` | none; `LOW_RTF` health flag at < 0.15 |

The two RTAB-Map gates are skipped when the run's `localization_mode` is `amcl` or `gt`, or when no `loop_events.csv` exists. Also reported: `img_color_rate_hz_p05`, `img_depth_rate_hz_p05` (5th percentile of per-window counts), `img_depth_rate_hz_mean`, and a 12-hex-digit `config_hash` (SHA-256 of the config snapshot plus the three config files `nav2_params.yaml`, `rtabmap.yaml`, `controllers.yaml` read from a hard-coded source path).

Bias: the bare responsiveness stack has no RTAB-Map updates by design, so the gate marked those episodes invalid (user decision to keep them invalid, `METRICS_AUDIT`).

---

## 3. Ground-truth grid and coverage machinery (used by #1, #8, #12, #14, A1-A3, A5)

### 3.1 GT grid rasterisation (`M/gt_grid.build`)

Inputs: the world SDF, a `reachable_seed` (x, y) known to be free floor (from `config/worlds.yaml`), the spawn point, resolution (0.05 m).

Constants in code: `ROBOT_BODY_Z_LO = 0.03`, `ROBOT_BODY_Z_HI = 0.25`, `R_INSCRIBED_M = 0.125`, `GRID_MARGIN_M = 0.50`.

Algorithm:

1. **Parse** (`_parse_world`): every `<model>` -> `<link>` -> `<collision>`; pose = model pose composed with link pose composed with collision pose (x, y, z, yaw). Supported shapes: `box`, `cylinder`, `sphere`; `plane` is skipped. It raises `UnsupportedSdf` for `<include>` (world or model level), nested models, `<frame>`, `relative_to` poses, non-zero roll/pitch, or any other geometry.
2. **Obstacle rule:** a collision is an obstacle iff its z interval overlaps the robot body band: `z_hi_obj > 0.03 and z_lo_obj < 0.25`. The z interval is `z +/- size_z/2` (box), `z +/- length/2` (cylinder), `z +/- radius` (sphere). So a 2 cm rug is not an obstacle and the ceiling is not.
3. **Grid extent:** the union of obstacle footprint bounding boxes, plus 0.5 m margin on each side; origin `x0 = floor(minx/res)*res`, same for y; width/height = `ceil(span/res)`.
4. **Rasterise:** cell centres `(x0+(i+0.5)res, y0+(j+0.5)res)`. A cell is occupied if its centre lies inside the shape (box: rotated local coordinates `|lx| <= sx/2 + 1e-12` and `|ly| <= sy/2 + 1e-12`; cylinder/sphere: `hypot <= r + 1e-12`). Shapes are treated as vertical prisms, so a sphere is rasterised as a full-radius disc. `obs_id` stores the model index per cell; for overlaps, the lowest model index wins.
5. **Cleanable area `a_clean`:** connected component of free cells (scipy `label`, 4-connectivity) that contains the seed cell. It raises `WorldNotSealed` if `a_clean` touches the outer ring of the grid (this is how an unsealed world, e.g. the old corridor, is detected). `A_clean_m2 = a_clean.sum() * res^2`.
6. **Clearance:** `dist_to_obstacle = EDT(~occ) * res` (metres from each cell centre to the nearest obstacle cell).
7. **Navigable (robot centre can stand there):** `navigable = (dist >= 0.125) & a_clean`. **`a_reach`:** the 4-connected component of `navigable` containing the spawn cell (`A_reach_m2` its area).
8. **Boundary:** obstacle cells with at least one 4-neighbour in `a_clean` (the wall/furniture surface cells that a map could actually observe). Used by #8 and A5.

Doc vs code: `config/eval_defaults.yaml` says `robot_body_z_hi: 0.30` ("was 0.25: unified obstacle band top"), but `compute_metrics.gt_grid_for` calls `gt_grid.build(sdf, seed)` with no overrides, and `geometry.load_obstacles` also defaults to `gt_grid.ROBOT_BODY_Z_HI`. So the code uses **0.25**. (Grids are also cached as `~/eval_runs/_gt/<world>.npz` and reused; I did not inspect how those cached files were built.) `docs/specs/03` also says 0.25.

Biases/caveats:
- 5 cm cell quantisation: curved and rotated surfaces are staircased. Wall thickness is whatever the SDF says.
- Only obstacles in the 0.03-0.25 m band count. Anything higher (a table top that the depth camera sees) is ignored by the GT, which can lower `occ_precision` of the map (the spec says so; `Grid/MaxObstacleHeight` was not checked here).
- `R_INSCRIBED_M = 0.125` is half the robot width. The robot footprint is 0.30 x 0.25 m, so `navigable` is a necessary condition, not a guarantee of collision-free poses at all headings.

### 3.2 Map sampling and classes (`M/coverage.py`)

- The SLAM map (`maps/final_map.npz` or snapshots `maps/map_*.npz`) holds `data` (int16 occupancy, `origin_x/y`, `resolution`, `origin_yaw` must be 0).
- `sample_map(map, gt, T_world_map)`: for every GT cell centre `(X, Y)` (world), map it to the map frame with `inverse(T_world_map)`, take the **nearest map cell** (floor index) and copy its value; out of bounds gives -1. `T_world_map` = spawn pose (`tw`) for headline numbers.
- Classes: **free = value 0**, **occupied = value >= 65**, everything else (including -1 and values 1-64) is unknown/other.

### 3.3 Reach mask (`reach_mask`)

`reach = {cells in a_clean within 0.125 m (EDT) of a_reach}`. If `a_reach` is absent it falls back to `navigable`. This is the cleanable area the robot body can actually brush: the robot-centre reachable set dilated by the inscribed radius, restricted to `a_clean`. It is the **denominator of the headline coverage and cleaning numbers**. `*_aclean_*` keys use all of `a_clean` instead.

### 3.4 What this means for the denominator

A cell counts as "should be covered" only if the robot body could reach it. Furniture gaps narrower than 0.25 m or corners the body cannot enter are excluded. This makes percentages higher than an all-free-floor denominator. The "free-only" definition (value == 0 only) also costs 2-6 percentage points, since inflated/unknown fringe cells next to walls are not counted (`METRICS_AUDIT`, #1).

---

## 4. Metric #1: average coverage (explored) and cleaned coverage

**Meaning:** how much of the true floor the robot has (a) seen in its map and (b) physically swept. The existing live `coverage_pct` in the old exploration logger (`free/(free+unknown)`) is not used because its denominator grows with the map.

### 4.1 Explored coverage (`coverage.coverage_explored`, `compute_coverage`)

```
coverage_explored_pct = 100 * |reach ∩ {sampled_final == 0}| / |reach|
coverage_explored_aclean_pct = same with a_clean in place of reach
missed_explored_m2 = (|reach| - |reach ∩ free|) * res^2        (also _aclean_ variant)
```

- Input: `maps/final_map.npz` sampled at GT cell centres with the spawn transform; no alignment search is applied to the headline.
- Unit: percent; higher is better. Value is None if no final map exists (note "no final map").
- Health: floor 70 % (BAD below), SUSPECT for `ODOM_CORRUPTED` / `FRAME_OFFSET`, UNMEASURABLE for missing map. See section 13.

Caveats:
- If the robot never moved (maze_dead_ends seeds with explorer stalls), the value is near the spawn-room fraction, so the pooled mean (61.4 %) is dragged down; moving runs average 78.8 % (`METRICS_AUDIT`).
- Occupied/unknown fringe cells count as not-explored, so a perfect map still scores < 100 %.
- A map that is shifted/rotated relative to the spawn frame scores low (this is "FRAME_OFFSET" territory).

### 4.2 Curve, time-to-X and area-under-curve (A1)

- Explored curve points: one per map snapshot `(t - t0, coverage_explored)` with `t >= t0`, plus the final point `(T, final value)` where `T = t1 - t0`.
- `t_to_{50,80,95}_explored_s` = time of the **first curve point** with value >= threshold (None if never reached). Resolution is the snapshot spacing (about 5 s in the pilot map files, not verified for all runs).
- `coverage_explored_auc` = `trapz(y, t) / T` with the first value held back to t = 0 and the last value held to t = T (`_auc`), i.e. the mean coverage over the episode.
- The same quantities for cleaned coverage use the cleaned curve (section 8): `t_to_*_cleaned_s`, `coverage_cleaned_auc`.
- `coverage_curve.csv` (`t_ep`, `coverage_explored_pct`, `coverage_cleaned_pct`) is written in the run directory, plus `missed_explored.png`.

Caveat: if the episode never reaches 50 %, the metric is simply None (right-censored); the campaign mean of "time to 50 %" therefore only averages the successful episodes (7 of 9 in the 2026-10-25 run).

---

## 5. Metric #8: map completeness

**Meaning:** how *correct* the map is, as opposed to how much was seen. It combines how much true free floor is marked free and how many true wall surfaces are marked occupied.

`coverage.completeness(sampled, gt)` returns (all as fractions; the summary multiplies by 100):

| Key | Formula (A = `a_clean`, B = `boundary`, free = map==0, occ = map>=65, dil = 3x3 binary dilation) |
|---|---|
| `free_recall` | `|A ∩ free| / |A|` |
| `free_precision` | `|A ∩ free| / |free|` (denominator = all map-free cells, including those outside `a_clean`) |
| `occ_recall` | `|B ∩ dil(occ)| / |B|` |
| `occ_precision` | `|occ ∩ dil(B)| / |occ|` |
| `iou_free` | `|A ∩ free| / |A ∪ free|` |
| `iou_occ` | `|dil(occ) ∩ B| / |dil(occ) ∪ B|` |
| **`headline`** | **`(free_recall + occ_recall) / 2`** |

Summary keys: `map_completeness_pct` = headline x 100; `map_free_recall_pct`, `map_free_precision_pct`, `map_occ_recall_pct`, `map_occ_precision_pct`, `map_iou_free_pct`, `map_iou_occ_pct`.

**Doc vs code:** `METRICS_TO_BE_MEASURED.md` describes #8 as "IoU of free and occupied cells vs the GT grid plus fraction of true wall cells found". The code headline is the **mean of free recall and occupied recall**, not IoU. The two IoUs are only stored as secondary keys. Also note free recall uses `a_clean`, not the reach mask, so #8's free half has a different denominator than #1's headline.

Alignment diagnostic (`alignment_search`): brute-force search over `dx, dy` in [-0.30, 0.30] m (step 0.05 m) and `dyaw` in [-5, +5] deg (step 1 deg), maximising `occ_recall + occ_precision`; ties go to the smallest shift (candidates are sorted by `|dx|+|dy|+|dyaw|*1e-3`). Reported as `map_align_dx_m`, `map_align_dy_m`, `map_align_dyaw_deg`, and the completeness at the best alignment as `map_completeness_aligned_diag_pct` (alias `map_completeness_aligned_pct`, deprecated). The aligned version is optimistic because the alignment is fitted on the very map being scored; **the headline uses the fixed spawn transform**. A note is added if the shift exceeds 0.20 m or 3 deg.

Caveats (from code plus audit):
- The 3x3 dilation gives the occupied recall/precision a **1-cell (5 cm) tolerance**; at 2 cells the audit measured +5-8 percentage points.
- The occupancy class threshold 65 and the "free == 0 exactly" rule are fixed; probabilistic grids with values 1-64 are neither.
- Stalled runs give low values (moving runs 62.9 % vs pooled 47.7 %).
- Genuine yaw drift in the SLAM map lowers it, which is intended.

---

## 6. Metric #14: cleaning efficiency (secondary), and A2, A3

**Meaning:** how much of the floor the vacuum swath actually covered, and how much overlap (re-sweeping) it paid. The sim has no real cleaning model, so this is computed geometrically from the GT trajectory. The explorer is not a cleaning planner, so this is a secondary metric.

### 6.1 Swept area algorithm (`coverage._interval_cells`, `swept_grid`)

Input: GT poses `(x, y, yaw)` at trajectory rows inside the episode window with all-finite values; swath width `meta['swath_width_m']` (default 0.25 m = the robot chassis width, a placeholder not confirmed by the user).

1. For each consecutive pair of GT rows (an "interval") compute `dpos` and wrapped `dyaw`. Subdivide into `nsub = max(ceil(dpos/0.02), ceil(|dyaw|/0.05), 1)` steps (`RESAMPLE_DIST_M = 0.02`, `RESAMPLE_YAW_RAD = 0.05`), with linear interpolation of x, y, and (shortest-path) yaw.
2. At every resampled pose, the swath is a **line segment perpendicular to the heading, of full width `w`, centred on the robot centre**: endpoints `(x - sin(yaw) w/2, y + cos(yaw) w/2)` and `(x + sin(yaw) w/2, y - cos(yaw) w/2)`. (The swath has no length along the heading; the swept region is the quadrilateral between two consecutive segments.)
3. Each pair of consecutive resampled segments inside one interval forms a quadrilateral, split into two triangles. Every grid cell centre within a window around the pair's midpoint is tested for being inside either triangle (orientation tests on cross products).
4. **Tie rule:** sample points are displaced by `TIE_EPS_X = 3.1e-7`, `TIE_EPS_Y = 1.7e-7` m so a cell centre exactly on a swath edge counts for one side only (the comment in the code attributes a +20 % bias to double counting).
5. Cells are restricted to `a_clean`. `swept` = touched at least once. `visits` = number of **separate contiguous runs of intervals** touching the cell (so staying on a cell for many ticks counts once; leaving and returning counts again). Stored as uint16 (capped at 65535).

### 6.2 Keys (`coverage.cleaning_keys`)

Let `reach` be the reach mask, `n_sw = |swept ∩ reach|`, `nA = |reach|`, `res2 = res^2`.

| Key | Formula |
|---|---|
| `coverage_cleaned_pct` | `100 * n_sw / nA` |
| `missed_area_m2` (**A3**) | `(nA - n_sw) * res2` |
| `swept_area_m2` | `n_sw * res2` |
| `overlap_ratio` (**A2**) | `sum(visits[swept ∩ reach]) / n_sw`; 1.0 means every swept cell was swept once |
| `redundancy_pct` | `100 * (overlap_ratio - 1)` |
| **`cleaning_efficiency`** (**#14**) | **`(coverage_cleaned_pct / 100) / overlap_ratio`** |
| `cleaned_m2_per_min` | `swept_area_m2 / (episode_sim_sec / 60)` |
| `cleaned_m2_per_m` | `swept_area_m2 / distance_gt_m` |
| `cleaning_efficiency_time` | `(cov/100) / (T / ref_time)`, with `ref_time = nA * res2 / (swath_width * V_REF)` and `V_REF = 0.30 m/s`; i.e. coverage relative to the ideal time for a perfect boustrophedon at 0.30 m/s |
| `*_aclean` variants | The same with `a_clean` instead of `reach` (only `coverage_cleaned_aclean_pct`, `missed_area_aclean_m2`, `cleaning_efficiency_aclean`) |

`coverage_cleaned_pct` is also provided as a curve (`swept_curve`): for each sample time it counts the fraction of `reach` cells first touched in intervals fully inside `t <= T` (an interval is counted only when its end row is <= the sample time). It equals `swept_grid` on the truncated trajectory.

Doc vs code: `METRICS_TO_BE_MEASURED.md` defines efficiency as `C / R` with `R = total swept visits / unique swept cells`. The code does exactly that (`R = overlap_ratio`), but the visit counting is "contiguous run of intervals", not per tick, and the area is the reach mask.

Caveats:
- 0.25 m swath width is an unconfirmed assumption; a different brush width scales every cleaned number.
- The swath is evaluated from GT only, so it ignores that the real brush has a different footprint than the chassis, and ignores skipped cleaning in rotation/slow motion.
- `cleaning_efficiency` is small for an explorer (0.055 pooled) because coverage is low and overlap about 2; it is not a statement about a coverage planner.
- A value is None when `n_sw == 0` (no motion).

---

## 7. Metric #2: steps per episode (and A6, A7)

**Meaning:** how long and how busy an episode is. The docs ask for three step notions, all implemented.

| Key | Definition (file / function) |
|---|---|
| `n_cmd_ticks` | Count of `cmd_vel.csv` rows with `source == 'ctrl_stamped'` in `[t0, t1]` (`compute_metrics._counters`) |
| `n_goals` | Count of `goal_events.csv` rows with `event == 'started'` and `src in (explore, scripted)` in the window (`_counters`) |
| `n_recoveries` | For each goal UUID in `feedback.csv` inside the window take the **maximum** `number_of_recoveries`, then sum over UUIDs (`navigation.compute_navigation_metrics`). None if there is no feedback table; 0 if the table exists but is empty |
| `recov_spin_n`, `recov_backup_n`, `recov_wait_n` (**A6** detail) | Count of unique UUIDs of `behavior_spin/backup/wait` status rows with `event in (accepted, executing)` in the window |
| `episode_sim_sec` | `t1 - t0` |

A6 (recovery count) = `n_recoveries`. A7: `n_stuck_goals = nav_fail_timeout + nav_fail_oscillation` plus the episode-level `end_reason` (`stuck`, `timeout`).

Caveats:
- 70-80 % of recoveries are instant costmap clears (audit), so `n_recoveries` mostly measures how often Nav2 asked for help, not time lost.
- The navigation counts `n_goals` can be 1-2 lower than raw "started" events because goals started outside the window are dropped.
- A7 as coded counts only timeouts/oscillation goals; all 89 failed navigation goals in the campaign were aborts, so A7 reads 0 although 7 of 12 navigation episodes ended by the stuck rule (`METRICS_AUDIT`). The episode-level `end_reason` is the informative number.

---

## 8. Metrics #3, #4, #9 and A5: collisions, avoidance, clearance (`M/safety.py`, `M/geometry.py`)

### 8.1 Robot footprint and exact geometry (`geometry.py`)

- Footprint: rectangle 0.30 x 0.25 m, `ROBOT_HALF_L = 0.150`, `ROBOT_HALF_W = 0.125`, centred on `base_footprint` (same constants in `safety.HALF_L/HALF_W`). Wheels protrude about 1.8 cm beyond this per the audit, so clearance is slightly optimistic.
- Obstacles come from the SDF with the same z-band rule as the GT grid: boxes (oriented rectangles) and discs (cylinders, spheres).
- Signed distance (`shape_distance`): positive = gap, 0 = touching, negative = minus the minimum-translation penetration depth.
  - Rect vs rect (`rect_rect_distance`): separating-axis test on the four axes; if some axis has a gap >= 0 the distance is the exact minimum of vertex-to-rectangle distances in both directions; otherwise the (negative) largest axis gap.
  - Rect vs disc: distance from the disc centre to the rectangle minus radius.
- Dynamic obstacles (`dyn_obstacles.csv`) are matched to trajectory rows by nearest time and treated as rectangles of size `[0.4, 0.4]` m unless `worlds.yaml dynamic_obstacles` gives a size.

### 8.2 Metric #3: total collisions (`collision_events`, `compute_safety_metrics`)

- Source: contact sensor rows in `collisions_raw.csv` (excluding contacts whose `other_model` is the robot itself), if the table exists and no `contact_topic_alive == 0` event was logged. Otherwise a geometric fallback is used (rows where the exact signed distance to any obstacle is <= 0; a grid-based fallback if no SDF shapes). `collision_source` records which.
- Grouping: rows are grouped by `other_model`; within a model, a new event starts when the gap to the previous row exceeds `collision_gap_s = 0.5 s` (config `collision_gap_s`, `snap['collision_gap_s']`).
- `n_collisions` = number of events, `n_collision_obstacles` = number of distinct models, `collision_contact_time_s` = sum of (t_end - t_start), `collision_first_t_ep` = first start minus t0.
- Cross-check: `n_collisions_geom` (exact geometry events); a note is added if contact and geometry counts differ by more than 2. `geometric_collisions_grid` is the grid-based count, `max_penetration_m` the deepest overlap.

Caveats (audit): the 0.5 s burst rule means **one physical jam can count as 3-7 collisions**. Wheels are not in the contact sensor, so some wheel-first contacts are missed (optimistic). Contact vs geometry may disagree in either direction. The 3-concurrent-simulation load raised controller-loop misses on exploration runs, which plausibly increases contacts (causality not proven).

### 8.3 Metric #4: % obstacle avoidance

**Meaning:** of the times the robot came close to an obstacle, how many ended without touching it.

1. Per obstacle (model name), from the exact signed distance series clipped at 0 (`dist = max(sdist, 0)`; the grid distance is used if no shapes), find runs of rows with `dist < d_enc` (`d_enc = 0.5 m`, `encounter_distance_m`). Merge runs separated by less than 2.0 s; drop runs shorter than 0.5 s (`_encounters_from`). Each remaining run is an **encounter**.
2. Encounter is **hit** if any collision event of the same model has `e.t_start <= b + 0.5` and `e.t_end >= a`, where `[a, b]` is the encounter.
3. Walls are excluded from the headline: `wall_re` from `worlds.yaml wall_models` (default `^wall_|^ceiling$`). So
   - `n_encounters = number of non-wall encounters`, `n_encounters_free = number not hit`,
   - **`avoidance_pct = 100 * n_encounters_free / n_encounters`** (None if no encounters, note "no encounters"),
   - `avoidance_pct_all`, `n_encounters_all`, `n_encounters_free_all` include walls.

Caveats: the denominators are tiny in the campaign (1-3 encounters per avoidance episode), so the avoidance mean is dominated by sparse binomial noise. Worlds made of walls only (maze) have no encounters at all (UNMEASURABLE). The metric was checked for its pooling formula, not for encounter detection (`METRICS_AUDIT` verification table).

### 8.4 Metric #9: avoidance trial success

For one scripted trial (`avoid_*` worlds): `nav_success_gt_pct` is taken from `navigation` (section 9) and

```
trial_goal_reached = 1 if nav_success_gt_pct >= 100 else 0
trial_success = 1 if trial_goal_reached == 1 and n_collisions == 0 and end_reason == 'goals_done'
                else 0          (None if either input is None)
```

The rate is the share of trials with `trial_success == 1`, pooled at the aggregate stage (`RATE_PAIRS` entry `('trial_success', None)`, denominator 1 per episode). Caveat: the report row for #9 is blank in the generated campaign reports because `make_report.py` looks for the key `avoid_trial_success_pct`, which no summary contains (`METRICS_AUDIT`); I confirmed the key is the one referenced at `make_report.py:35`. n = 6 trials in the campaign (LOW_N).

### 8.5 A5: clearance

`clr[r] = min over obstacles of dist_k[r]` (signed distance clipped at 0), capped at `CAP = 1.0 m` per row (`clr` starts at 1.0).

| Key | Definition |
|---|---|
| `min_clearance_m` | `min(clr)` |
| `mean_clearance_m` | `mean(clr)` |
| `clearance_p05_m` | 5th percentile |
| `time_below_020m_s`, `time_below_010m_s` | Sum of per-row durations where `clr < 0.20` / `< 0.10`. Per-row duration = `diff(t)` clipped to [0, 1.0] s; last row repeats the previous duration (0.1 s for a single row) |
| `min_clearance_grid_m` | Same minimum from the grid-based distance (cross-check, not the headline) |

The grid distance (`_distances`) uses boundary cells within `QUERY_R = 1.2 m`, robot-rectangle-to-cell-centre distance minus `res/2`, floored at 0, per obstacle model via a KD-tree. Walls are included in the clearance (unlike #4). Because clearance is capped at 1.0 m and the floor is 0, the minimum is bounded to [0, 1].

---

## 9. Navigation: #10 success, #12 path length ratio, A4, A8, A9 (`M/navigation.py`)

### 9.1 Goal records (`goal_records`)

From `goal_events.csv`, take rows with `src` in (`explore`, `scripted`) (the method sets which: `frontier` -> explore, `scripted_goals` -> scripted, else both). A goal is identified by `(src, goal_seq)`; the first `started` row gives `t_start` and the goal `(x, y)` in map frame, which is converted to the world frame with `t_world_map` (spawn pose if missing). The first `ended` row gives `t_end` and `result`. Goals started more than 1 s before the episode start (`GOAL_PRE_START_TOL_S`) or after the end are dropped; an `ended` row after `t1` leaves the goal `unfinished`.

Classification:
- `succeeded` -> success.
- failures: result in (`nav_aborted`, `timeout`, `oscillation`, `rejected`), or `canceled` by anything other than the harness at the episode end (a `canceled` ended within 1.0 s of `t1`, `HARNESS_END_S`, is **truncation** and ignored).
- ignored: `canceled_by_manager` (counted as `nav_goals_canceled`), `unfinished`, unknown results.
- `nav_goals_total = succeeded + failed`.

### 9.2 Metric #10: navigation success

```
nav_success_pct         = 100 * n_succeeded / nav_goals_total          (Nav2's own verdict)
nav_success_gt_pct      = 100 * |{succeeded goals whose GT position at t_end is within 0.30 m of the goal}| / nav_goals_total
nav_success_gt_strict_pct   same with 0.15 m
```

- GT position at `t_end` is linearly interpolated from the (all-time) GT trajectory. The goal point is the world-frame goal. Failed goals can never count as reached (the `reached` loop skips non-succeeded ones).
- `GOAL_TOL = 0.30`, `GOAL_TOL_STRICT = 0.15`.
- **Headline for the paper is `nav_success_gt_pct`**, because Nav2's own xy tolerance is not reused (independent check). Fallback label `nav_success_pct (Nav2-reported)`.
- Also stored: `nav_fail_aborted/timeout/oscillation/rejected/canceled`, `goal_time_mean_s`, `goal_time_median_s` (over succeeded goals: `t_end - t_start`).

Doc vs code: the original spec asked for the Nav2 action result count only (`METRICS_TO_BE_MEASURED.md`). The code's headline is GT-verified and uses the denominator of all succeeded + failed goals.

Health: `NAV_GT_DIVERGENCE` is SUSPECT if Nav2's success minus GT success exceeds 30 percentage points. In the campaign, the dominant failure was a Nav2 + AMCL issue (AMCL estimate 0.2-0.3 m off puts the footprint into wall cells in the costmap), not the planner (`METRICS_STATUS.md`). Reported as measured: 23.4 % GT-verified vs about 50 % Nav2-reported.

### 9.3 Metric #12: path length ratio

For each **succeeded** goal:

1. `start` = GT position interpolated at `t_start`; `goal` = world goal.
2. `shortest = shortest_path_length(gt, start, goal)`:
   - Snap both points to the nearest `navigable` cell within `SNAP_RADIUS = 0.30 m`, else None (counted in `ratio_skipped`).
   - 8-connected A* on `gt.navigable` (diagonal cost sqrt(2); diagonal moves are blocked only if both orthogonal neighbours are blocked, "corner cut between two blocked cells"; heuristic is Euclidean in cells).
   - String-pulling with Bresenham line-of-sight tests on `navigable`.
   - Length = polyline from the exact start point through the pulled waypoint cell centres to the exact goal point.
3. Skip if `shortest < MIN_SHORTEST = 0.5 m` (the goal was at the start).
4. `actual` = sum of GT step lengths between rows with `t_start <= t <= t_end`.
5. `ratio = actual / shortest`.

`path_length_ratio_mean/median/p90` are over those goals in an episode; `path_length_ratio_n` is the count. Pooling across episodes is the **unweighted mean of per-episode means** (audit), so an episode with one goal weighs as much as one with ten. There is also `plan_length_ratio_mean`: Nav2's first plan after acceptance (`plans.csv: length_m`) divided by `shortest`.

Caveats: successful goals only (selection bias towards easy goals); the denominator ignores the robot rectangle at heading (centre-based `navigable` grid only); the numerator includes spins and recoveries, so the ratio rises when the robot is jammed. 1.0 is not strictly reachable because the string-pulled path is a good approximation, not the exact optimum, and the actual path includes the first turning.

### 9.4 Goal list generator (`generate_goal_lists`)

Used to create scripted-goal lists, seeded with `numpy.default_rng(seed)` (the caller passes `seed + 2000`):
- `random20`: 20 goals from `a_reach & (dist >= 0.40 m)`, each at least 1.5 m Euclidean and 1.5 m shortest-path from the previous (initially the spawn), with up to 400 tries each; random yaw.
- `near_wall`: 10 goals with `0.20 <= dist <= 0.35 m`.
- `long_range`: 6 goals, each the farthest reachable cell by Dijkstra distance (`_graph_dist`) from the previous, with `dist >= 0.40`.
- `fixed`: passed through if given.

### 9.5 A4 (distance, energy proxy), A9 (smoothness), A8 (planning latency)

| Key | Formula |
|---|---|
| `distance_gt_m` | `sum(hypot(diff(gt_x), diff(gt_y)))` over rows in the window with finite GT. (Written by `trajectory`, `navigation` and `counters`; all three use the same sum; the final value is the counters one.) |
| `distance_odom_m`, `distance_ratio_odom_gt` | The same on `odom_x, odom_y`; ratio `dod / dgt` |
| `energy_proxy_m2ps` | `sum_i (vL_i^2 + vR_i^2) * dt_i`, with `vL = gt_vx - gt_wz * 0.268/2`, `vR = gt_vx + gt_wz * 0.268/2` (`WHEEL_BASE = 0.268`), using GT body velocities `gt_vx`, `gt_wz`. Units m^2/s. Differs from the doc's "integral of v^2 dt" by using wheel speeds, so it penalises spinning |
| `mean_speed_mps` | `distance_gt_m / (t_last - t_first)` of the window rows |
| `time_stationary_s` | Sum of row durations where `abs(vx) < 0.02 and abs(wz) < 0.05` |
| `time_rotating_inplace_s` | Where `abs(vx) < 0.05 and abs(wz) >= 0.05` |
| `smooth_curvature_rms_1pm` (**A9**) | RMS of `kappa = wz / vx` over rows with `abs(vx) >= 0.05`; also `smooth_curvature_var` |
| `smooth_jerk_rms_mps3` | RMS of `d^2 vx/dt^2`-style jerk: `a = diff(vx)/dt`, `j = diff(a)/dt[:-1]`, only over triples of rows that are all moving |
| `plan_latency_ms_mean/p95` (**A8**) | For each goal, find the first Nav2 status row (`src == nav2_status`, event `accepted` or `executing`) at or after `t_start` and within 2 s; latency = `1000 * (first plans.csv row with t >= acceptance - acceptance)`. Mean and 95th percentile over goals. `replans_per_goal_mean` = number of plan rows from acceptance to `t_end` (or `t1`) minus one, floored at 0 |

Caveats:
- A9 curvature at low speed is noisy (`wz/vx` blows up), hence the 0.05 m/s floor; 3.01 1/m RMS in the campaign mostly reflects in-place-style turning with small `vx`.
- **A8 is mislabelled as planning time.** It is the time from acceptance to the first plan row, dominated by stuck goals; the audit says the per-goal median (about 10 ms nav, 30 ms explore) is informative, but the code produces mean and p95 only; **no median key exists in `navigation.py`**. Doc (`METRICS_TO_BE_MEASURED`) says "time from goal accepted to plan received", which matches the code.
- An independent verifier got 8989 ms vs 9311 ms for A8 (the goal window and truncation handling were not replicated), and 0.308 vs 0.318 m for A14.

---

## 10. Trajectory accuracy: #6 ATE, #7 RPE, A10, A14, and diagnostic D1 (`M/trajectory.py`, `M/contact_odom.py`)

### 10.1 Inputs and selection

Rows of `trajectory.csv` inside the episode window with columns `gt_x/y/yaw`, `est_x/y/yaw` (SLAM or AMCL estimate in the map frame), `odom_x/y/yaw` (wheel odometry), `est_ok` (1 when an estimate exists).

- SLAM/AMCL group is evaluated only if there are >= `MIN_ROWS = 100` valid rows (GT finite, estimate finite, `est_ok == 1`) and the GT path over those rows is >= `MIN_PATH_M = 2.0 m`; otherwise the note "insufficient motion for ATE/RPE" is added and all keys stay None.
- The estimate is mapped into the world frame: `world_est = t_world_map ∘ est` (`t_world_map` from run meta, default = spawn pose). Odometry: `spawn ∘ odom`.

### 10.2 Metric #6: ATE

```
e_i = hypot(world_est_x - gt_x, world_est_y - gt_y)             (per valid row)
ate_fixed_rmse_m    = sqrt(mean(e_i^2))     <-- headline (no alignment: the SLAM frame is tied to spawn)
ate_fixed_mean_m, ate_fixed_max_m
ate_yaw_rmse_deg    = RMS of wrap(est_yaw - gt_yaw) in degrees
ate_aligned_rmse_m  = RMSE after the best 2D rigid transform (rotation + translation, NO scale) of the estimated xy onto the GT xy
```

The rigid alignment is `umeyama_2d`: `theta = atan2(sum(e x g cross), sum(e . g))` on mean-centred points (a closed-form 2D Kabsch/Umeyama without scale), `t = mean(G) - R mean(E)`. It is not the headline.

Doc vs code: `METRICS_TO_BE_MEASURED.md` describes ATE as RMSE "with rigid alignment (SE3) only". The code headline `ate_fixed_rmse_m` is the **unaligned fixed-frame** error with the world frame from the spawn pose; the aligned number is a secondary diagnostic key. The health floor (0.30 m, BAD if above) is on the fixed-frame number.

Other keys: `ate_samples` (count), `start_offset_m` (mean fixed error over the first 5 s, `START_WINDOW_S`), `start_offset_deg` (mean absolute yaw error over those rows; a note is added if > 0.10 m or > 5 deg), `slam_final_error_m` (error at the last valid row), `slam_drift_ratio = slam_final_error_m / distance_gt_m`.

Odometry: `ate_odom_fixed_rmse_m`, `ate_odom_aligned_rmse_m`, `odom_final_error_m`, `odom_drift_ratio` (**A10**) = `odom_final_error / distance_gt`. `ate_improvement_pct = 100 * (ate_odom - ate_slam) / ate_odom`, only if `ate_odom >= ODOM_ATE_MIN_M = 0.02 m`.

Caveats:
- ATE is dominated by a single large event if the odometry yaw jumps after a collision (D1 below). Four of nine exploration episodes were affected, which is why the headline value (0.572 m) is reported alongside `ate_fixed_rmse_m_pre_corrupt`.
- A wrong initial frame inflates the fixed-frame ATE ("FRAME_OFFSET"); the audit says this flag in practice fires on late drift rather than a start offset.
- ATE depends on the odometry noise setting (the campaign ran with noise on).

### 10.3 Metric #7: RPE

For index pairs `(i, j)`: `dg = inverse(gt_i) ∘ gt_j`, `de = inverse(est_i) ∘ est_j`, `err = inverse(dg) ∘ de`; translation error = `hypot(err_x, err_y)`, rotation error = `|wrap(err_yaw)|`.

- **1 m pairs (`_pairs_1m`, the headline):** with `s` the cumulative GT path length, each row `i` is paired with the first `j` where `s[j] >= s[i] + 1.0`. `rpe_trans_rmse_m_1m`, `rpe_trans_mean_m_1m`, `rpe_rot_rmse_deg_1m`, `rpe_pairs_1m`.
- **5 s pairs (`_pairs_5s`):** pair `j` is the row nearest to `t[i] + 5 s`, accepted only if within 0.05 s. Keys with suffix `_5s`.
- RPE overlaps heavily (every row starts a pair), so the pair count is not an independent sample size.
- The same 1 m RPE is computed for odometry: `rpe_odom_trans_rmse_m_1m`, `rpe_odom_rot_rmse_deg_1m`.

Caveat: the rotation part is inflated by a single yaw jump (pilot2: 24 deg per 1 m).

### 10.4 A14: AMCL localisation error (AMCL runs only)

Applies when `run_meta.localization_mode == 'amcl'`. Using the same error array `e` as ATE (all valid rows):

- `loc_error_mean_m = mean(e)`, `loc_error_p95_m = percentile(e, 95)`.
- `loc_converge_s`: the first row time `t_i` (relative to episode start) such that every row in `[t_i, t_i + 10 s]` has `e < AMCL_OK_M = 0.25`. Requires `t[-1] >= t_i + 10`. None if never.
- `loc_lost_events`: counted when `e > 1.0 m` (`AMCL_LOST_M`) after having been below 0.25 m (re-arms when it drops below 0.25 m again).

Note on the audit: the audit states that the metric "uses the AMCL-converged window". **In the code of `trajectory.py` I see no such window; `loc_error_mean_m` is over all valid rows (`est_ok == 1`).** Any convergence-window effect would have to come from upstream (what the recorder marks `est_ok`), which I did not verify.

### 10.5 Estimator gaps

`n_est_gaps`, `est_gap_total_s`: maximal runs of rows with `est_ok != 1` that last at least 1.0 s (`GAP_MIN_S`); duration is `t_last - t_first` of the run.

### 10.6 D1: contact-induced odometry corruption (`M/contact_odom.py`) -- a diagnostic stratifier, never an exclusion

When the robot is pressed against an obstacle, wheel slip makes odometry integrate yaw the body did not turn. For every merged contact event window `[t_start - 0.5, t_end + 0.5]` (merged if closer than 0.5 s, `PAD_S = 0.5`):

```
excess_deg = | (odom_yaw_unwrapped[j] - odom_yaw_unwrapped[i]) - (gt_yaw_unwrapped[j] - gt_yaw_unwrapped[i]) |   in degrees
```

where i, j are the first/last trajectory rows in the window and yaw is unwrapped over the whole episode. Keys: `contact_odom_n_events`, `contact_odom_yaw_excess_deg` (sum), `contact_odom_yaw_excess_max_deg`, `odom_corrupted_by_contact = 1 if max > 15 deg` (`CORRUPT_DEG`, overridable via `contact_odom_corrupt_deg`), `t_odom_corrupt_ep_s` (first corrupting event start relative to episode start), and `ate_*_pre_corrupt`: the ATE recomputed with the episode truncated at the first corrupting event (full ATE if none).

Health uses it: `ODOM_CORRUPTED` makes #6, #7, #8, #1 SUSPECT.

---

## 11. Metric #5: responsiveness (`M/responsiveness.py`)

**Meaning:** how quickly the control stack reacts. Three kinds of events are pooled into `responsiveness_pct`, but the audit says the *headline* is the step-response latency, not the pooled percent.

### 11.1 Events

| Kind | How defined | Deadline (`DEFAULT_DEADLINES`) |
|---|---|---|
| `cmd_motion` (step response) | From `responsiveness_events.csv`: a commanded velocity step; latency = time to reach the onset condition. The step test node (`responsiveness_test.py`) uses **50 % of the commanded step** (`abs(vx) >= 0.5*abs(v_step)` for forward, `abs(wz) >= 0.5*abs(wz_step)` for rotation), with defaults `v_step = 0.2` m/s, `wz_step = 0.5` rad/s, 10 trials per variant. Latency = `wall_latency_s` (wall clock) if that column exists, else the sim `latency_s` | 0.5 s |
| `stop` | Same table: commanded zero, latency until the robot is still (`abs(vx) <= 0.02`, `abs(wz) <= 0.05`) | 0.5 s |
| `goal_motion` | For every `started` goal (explore/scripted) in the window: first trajectory row after `t_a` with `abs(gt_vx) >= 0.05` or `abs(gt_wz) >= 0.10` | 2.0 s |
| `obstacle` | First time (by GT) a dynamic obstacle is within 1.5 m, inside the camera half-FOV (0.6056 rad), while the smoothed command speed had min >= 0.05 m/s over the previous second; response = first smoothed `cmd_vel` after that with `vx <= 0.7 * v_ref` or `abs(wz) >= 0.3` (`v_ref` = mean `vx` in the previous second, must be >= 0.05) | 1.0 s |

**Miss rule:** a response later than `3 * deadline` counts as no response (`L = None`). An event is "met" if `L <= deadline`.

### 11.2 Keys

- `responsiveness_pct = 100 * n_met / n_events` over **all** event kinds pooled, plus per-kind `resp_cmd_pct`, `resp_stop_pct`, `resp_goal_pct`, `resp_obstacle_pct` and `lat_<kind>_ms_mean`, `lat_<kind>_ms_p95` (milliseconds, over responses that exist).
- `lat_cmd_motion_ms_mean_sim`, `lat_stop_ms_mean_sim` and p95 variants: the same step events measured with sim time instead of wall time.
- `resp_definition = 'wall_clock_controller_latency'`; `resp_stack` = `bare` / `loaded` / `episode` from run meta. A note "wall-clock stamps missing" if step events have no wall column.
- Topic-rate health (`topic_rate_health`): for each window in `rates.csv` check the topic count against a floor (`DEFAULT_RATE_FLOOR`: odom, depth, color 27; cmd_nav, cmd_smoothed 16 (only while a goal is active); tf_map_odom 1; scan 9). `topic_ok_pct_<name>` = share of windows meeting the floor; `topic_ok_pct_min` = the minimum.

### 11.3 Caveats

- **Doc vs code:** `METRICS_TO_BE_MEASURED.md` says "cmd -> 90 % of commanded velocity". The code's threshold is 50 % of the step.
- The wall-clock latency is a controller loop latency, mostly the acceleration ramp (audit), measured on the loaded stack with n = 2 episodes.
- Concurrent simulations add roughly 5-10 % latency.
- Goal-to-motion percentages (41-74 %) are confounded by planning time and should not be called responsiveness.
- With fewer than 10 events the health flag is LOW_N (`resp_events: 10`).
- `responsiveness_pct = 100 %` on step events only says every step met 0.5 s, not how fast.

---

## 12. Metric #11: loop-closure precision and recall (`M/loop_closure.py`)

**Meaning:** of the loop closures RTAB-Map accepted, how many are geometrically correct, and of the real revisits, how many did SLAM close.

### 12.1 Inputs

`loop_events.csv`: one row per RTAB-Map `Info` message, with `t`, `ref_id` (the current node), `loop_closure_id` (>0 when a closure was accepted, the matched node), `proximity_detection_id`, GT pose `gt_x, gt_y, gt_yaw` at row time, and the registered transform `lc_tx, lc_ty, lc_tyaw`.

### 12.2 Node poses

`node_poses`: for each `ref_id`, the GT pose from its **first** row (first time the node appears in an Info message). Nodes created before the window are still available for lookups (`all_nodes`) but `lc_n_nodes` counts only nodes first seen in the window.

### 12.3 Accepted closures and truth

- `acc` = set of distinct `(ref_id, loop_closure_id)` pairs with `loop_closure_id > 0` in the window.
- **Headline correctness (`_reg_correct`)** for a pair with a recorded transform `tf`:
  `expected = rel_se2(pa, pb)` (convention `ref_to_loop`) or `rel_se2(pb, pa)` (convention `loop_to_ref`), where `pa`, `pb` are the GT node poses. The closure is **true** iff `hypot(expected_xy - tf_xy) <= 0.10 m` (`LC_REG_TRANS_TOL_M`) and `|wrap(expected_yaw - tf_yaw)| <= 5 deg` (`LC_REG_ROT_TOL_DEG`). The closure is correct when RTAB-Map's measured relative transform matches the GT relative transform.
- If a pair has no recorded transform (fallback), it counts as true if the two GT node poses are within `LC_POS_TOL_M = 0.30 m` and `LC_YAW_TOL_DEG = 30 deg` ("samepose"). A note records how many closures used this fallback.
- Convention: `default_convention` reads `lc_transform_convention` from the run's config snapshot or `eval_defaults.yaml`. `eval_defaults.yaml` sets **`loop_to_ref`** (verified on pilot2: median translation error 0.032 m vs 0.699 m for `ref_to_loop`); the code's built-in fallback is `ref_to_loop`.

### 12.4 Outputs

| Key | Formula |
|---|---|
| `lc_n_accepted` | `|acc|` |
| `lc_n_true`, `lc_n_false` | counts of true pairs / `|acc| - n_true` |
| **`lc_precision_pct`** | `100 * n_true / n_accepted` (None if none accepted) |
| `lc_precision_samepose_pct` | share of accepted pairs whose GT poses are within 0.30 m and 30 deg (position-only criterion) |
| `lc_precision_loose_pct` | same with 1.0 m and 60 deg tolerances (old tolerances) |
| `lc_rot_err_median_deg`, `lc_trans_err_median_m` | median error between the measured and GT-expected transform over accepted pairs that have transforms |
| `n_proximity_links` | rows with `proximity_detection_id > 0` and no loop closure |
| `lc_per_100m` | `100 * n_accepted / distance_gt` |
| `lc_n_revisits`, `lc_n_revisits_detected` | revisit episodes, and those with a true closure (below) |
| **`lc_recall_pct`** | `100 * revisits_detected / n_revisits` |
| `lc_f1_pct` | `2PR/(P+R)` |

**Revisit episodes (`revisit_episodes`):** nodes are sorted by first appearance. A node is a *revisit* if some earlier node (at least `LC_MIN_TIME_GAP_S = 30 s` older) has GT position within `LC_REVISIT_POS_M = 1.0 m` and GT yaw within `LC_REVISIT_YAW_DEG = 60 deg`. Maximal runs of consecutive revisit nodes form one episode. An episode is **detected** if any of its nodes is the `ref_id` of a **true** pair.

### 12.5 Caveats

- **Precision is a lower bound** (audit): the GT pose of a node is taken at the Info message arrival, not at the node's sensor stamp (about 0.1-0.4 s lag), and a 5 deg rotation tolerance is tight for that lag; a diagnostic time shift raised precision to 52-77 % against the reported 36.8 %.
- The 5 deg / 0.10 m tolerances are strict; recall only credits a closure when the *ref* node is in the revisit episode (loop node is not checked).
- The health `LC_ROT_BIAS` flag looks at median rotation error in (5, 7] deg; the audit showed it never fired because real medians were 7-13 deg.
- Few accepted closures (`LOW_N` under 5) make precision noisy.
- Recall counts revisit *episodes* (not nodes), so denominators are small (3-9 per episode).

---

## 13. Health flags (`M/health.py`) and sanity flags

Computed last from the merged summary; they never exclude an episode. Statuses and **precedence: UNMEASURABLE > SUSPECT > LOW_N > BAD > OK** (all reasons are still stored in `health_<metric>_reasons`); `NA` if the metric does not apply.

Metrics covered: `coverage_explored_pct, n_goals, n_collisions, avoidance_pct, responsiveness_pct, ate_fixed_rmse_m, rpe_trans_rmse_m_1m, map_completeness_pct, trial_success, nav_success_gt_pct, lc_precision_pct, lc_recall_pct, path_length_ratio_mean, cleaning_efficiency`.

Applicability (`_applicable`): `trial_success` only for worlds starting with `avoid`; `responsiveness_pct` only if method != `frontier`; LC metrics only if the summary has an `lc_*` key. (The audit lists 72 UNMEASURABLE entries from AMCL runs for metrics that need SLAM, because `_applicable` does not look at AMCL.)

| Flag | Rule (thresholds from `eval_defaults.yaml health:`) |
|---|---|
| UNMEASURABLE reasons | `INVALID_EPISODE` (status invalid); value missing: `GT_MISSING`, `MAP_MISSING`, `NO_EVENTS` (the event count key is 0), else `NO_DATA`; also `NO_EVENTS` if the event count is 0 even with a value |
| SUSPECT `ODOM_CORRUPTED` | `odom_corrupted_by_contact == 1` for ATE, RPE, completeness, coverage |
| SUSPECT `FRAME_OFFSET` | `start_offset_m > frame_offset_m` or map align shift `hypot(dx, dy) > map_align_shift_m` for ATE, completeness, coverage |
| SUSPECT `RANGE` | percent metric outside [0, 100], or a negative value |
| SUSPECT `NAV_GT_DIVERGENCE` | `nav_success_pct - nav_success_gt_pct > 30` percentage points |
| SUSPECT `LOW_RTF` | `rtf_true_mean < 0.15` |
| SUSPECT `LC_ROT_BIAS` | `lc_rot_err_median_deg` in (tol, tol + 2.0] with tol = the rotation tolerance |
| LOW_N | event count between 1 and min_n - 1. Min n: goals 5, encounters 3, lc_accepted 5, lc_revisits 3, resp_events 10 |
| BAD `BELOW_FLOOR` | value below floor (above for ATE): nav_success_gt 50, coverage_explored 70, map_completeness 60, ate_fixed_rmse 0.30 (upper), lc_precision 50, avoidance 80 |

Doc vs code (thresholds): the built-in `DEFAULTS` in `health.py` have `frame_offset_m: 0.5` and `map_align_shift_m: 0.5`; `eval_defaults.yaml` (which `compute_metrics._health_cfg` loads, or a run's `config_snapshot.health`) has **0.10** and **0.20**. The YAML values are what are applied in the normal pipeline; the code defaults only apply if no config is found.

Biases: the floors are pre-registered *diagnosis triggers*, not pass/fail criteria; the precedence rule hides BAD behind SUSPECT/LOW_N (the audit counted 16 of 59 floor breaches that way).

---

## 14. Statistics and aggregation (`aggregate.py`, `make_report.py`)

### 14.1 What is pooled

- Only episodes with `status in (ok, partial)` enter statistics. `invalid` and `failed` are counted separately (`n_invalid`, `n_failed`).
- Groups are keyed by `(world, method, odom_noise, gpu, lean)`.

### 14.2 Descriptive statistics (`group_stats`)

`n`, `mean`, `std` (sample, `ddof=1`), `median`, `min`, `max`, `ci95_halfwidth = t_{0.975, n-1} * sd / sqrt(n)`, and `cv = sd / |mean|` (**A13, repeatability**; None if mean is 0). Non-finite values are dropped.

### 14.3 Bootstrap

| Function | What it does | Defaults |
|---|---|---|
| `aggregate.bootstrap_mean_ci(values)` | Percentile bootstrap of the mean over episodes: `B` resamples of size n with replacement, take the 2.5th and 97.5th percentiles of the resample means | `B = 5000`, `seed = 12345` |
| `aggregate.cluster_bootstrap_ci(succ, tot)` | Episode-level bootstrap of a **pooled ratio** `sum(succ)/sum(tot) * 100`: resample *episodes* with replacement, recompute the ratio, percentile CI. Resamples with `tot == 0` are dropped. NaN if fewer than 2 episodes | `B = 5000`, `seed = 12345` |
| `make_report.pooled_cluster_ci(rows, key)` | Used for the headline table values: group episode values by world; each bootstrap resample draws worlds with replacement, then within each drawn world draws episodes with replacement, and averages everything; CI = 2.5/97.5 percentiles; also returns the mean and sample std of all pooled episode values | `B = 2000`, `seed = 12345` |

Doc vs code (bootstrap): `METRICS_AUDIT` describes the pooled CI as an "episode-level cluster bootstrap". The report code that produced the headline table (`pooled_cluster_ci`) is a **two-level (worlds, then episodes within world) bootstrap**, with B = 2000. The pre-registration (`specs/13`) says 10 000 resamples; the code defaults are 5000 (`aggregate`) and 2000 (`make_report`). `paper_tables.py` imports `BOOT_B` and `bootstrap_mean_ci` from `aggregate`, so tables made by it use B = 5000 (not verified in detail).

Consequences: with 3 worlds, resampling worlds with replacement means a CI that includes the possibility of a bootstrap sample made of a single world; with 2-4 episodes per world these CIs are very wide (e.g. coverage 61.4 [18.5, 88.0]).

### 14.4 Rates and Wilson

`aggregate.RATE_PAIRS` pools success counts: `(nav_goals_succeeded, nav_goals_total)`, `(trial_success, 1)`, `(lc_n_true, lc_n_accepted)`, `(resp_n_met, resp_n_events)`. Pooled percent = `100 * sum(successes) / sum(trials)` across episodes. Two intervals are reported:

- **Wilson score interval** (`wilson_interval(k, n, z = 1.96)`), as fractions:
  `p = k/n`, `d = 1 + z^2/n`, centre `c = (p + z^2/(2n))/d`, half-width `h = z * sqrt(p(1-p)/n + z^2/(4n^2)) / d`; interval `[max(0, c - h), min(1, c + h)]`.
- **Cluster bootstrap** (`cluster_bootstrap_ci`, above).

The Wilson interval treats every goal/closure as independent, which is wrong because goals are clustered within episodes; the report labels it "naive Wilson (ignores clustering)" and the cluster bootstrap is the reportable one (`WILSON_NOTE`).

### 14.5 Comparisons (relevant to #13 only, which is on hold)

`compare_methods`: Wilcoxon signed-rank if paired by seed with equal n >= 6, else two-sided Mann-Whitney U; `cliffs_delta`; `holm_adjust` (Holm-Bonferroni; NaNs ignored). No comparison between methods was run in the campaign.

### 14.6 Report-generator behaviours to be aware of (from `METRICS_AUDIT`, items I could partially confirm in code)

- `make_report.MIN_N = 3`: fewer than 3 valid episodes gets "INSUFFICIENT DATA".
- The #9 row uses key `avoid_trial_success_pct` (line 35) which no summary contains, so it prints blank. Correct value computed from `trial_success`: 4 of 6 = 66.7 %.
- Reports for #5, #10 and #12 in other campaigns can show values from single-goal trials or from a different event definition (audit section 3a); treat them as not applicable.

---

## 15. Real-time factor and resources: A11, A12 (`M/resources.py`, `M/validity.py`)

- **A12 true RTF:** from `rtf.csv`. In `resources`: `rtf_mean`, `rtf_p05`, `rtf_min` over rows in the episode window. In `validity`: `rtf_true_mean` over the **whole file** (not windowed). Unit: ratio (1.0 = real time); higher is better. Observed 0.729-1.000. A flag `LOW_RTF` fires under 0.15; it never did.
- **A11:** from `resources.csv`: for every column `cpu_<proc>_pct` the mean and peak over the window (`cpu_<proc>_mean_pct`, `cpu_<proc>_peak_pct`); for `rss_<proc>_mb` the peak (`rss_<proc>_peak_mb`); `ram_used_peak_mb` from `ram_used_mb`. Caveat: values include the load of other simulations running concurrently (3 slots), which inflated CPU.

---

## 16. The complete metric index (#1-#14 and A1-A15)

"Key" = column in `summary.json`. Direction: up = higher is better, down = lower is better.

| ID | Metric | Key(s) | Unit / dir | Code location | One-line formula |
|---|---|---|---|---|---|
| 1 | Average coverage (explored) | `coverage_explored_pct`, `_aclean_` | % up | `coverage.coverage_explored` | free map cells at GT cell centres in the reach mask / reach cells |
| 1b | Average coverage (cleaned) | `coverage_cleaned_pct` | % up | `coverage.swept_grid`, `cleaning_keys` | swept reach cells / reach cells |
| 2 | Steps per episode | `n_goals`, `n_cmd_ticks`, `n_recoveries`, `episode_sim_sec` | count down | `compute_metrics._counters`, `navigation` | counts in the window |
| 3 | Total collisions | `n_collisions` (+`collision_source`) | count down | `safety.collision_events` | contact bursts split by > 0.5 s per model |
| 4 | % obstacle avoidance | `avoidance_pct` | % up | `safety.compute_safety_metrics` | encounters (< 0.5 m, merged 2 s, >= 0.5 s, non-wall) without contact / all |
| 5 | Responsiveness | `responsiveness_pct`, `lat_cmd_motion_ms_mean`, `lat_stop_ms_mean` | % up / ms down | `responsiveness.compute_responsiveness_metrics` | events within deadlines; headline = step latency |
| 6 | ATE | `ate_fixed_rmse_m` | m down | `trajectory._p_est_group` | RMSE of xy error after mapping the estimate by spawn / `t_world_map` |
| 7 | RPE | `rpe_trans_rmse_m_1m` (+`_5s`, rot) | m, deg down | `trajectory.rpe`, `_pairs_1m` | RMS translation error of relative motion over 1 m path pairs |
| 8 | Map completeness | `map_completeness_pct` | % up | `coverage.completeness` | (free recall + occupied recall)/2 |
| 9 | Avoidance trial success | `trial_success` | % up | `safety.compute_safety_metrics` | goal reached and 0 collisions and `goals_done` |
| 10 | Navigation success | `nav_success_gt_pct` (+`nav_success_pct`) | % up | `navigation.compute_navigation_metrics` | succeeded goals with GT within 0.30 m / (succeeded + failed) |
| 11 | Loop-closure precision / recall | `lc_precision_pct`, `lc_recall_pct` | % up | `loop_closure.compute_loop_closure_metrics` | transform match (0.10 m, 5 deg); detected revisit episodes |
| 12 | Path length ratio | `path_length_ratio_mean` | ratio down (>= ~1) | `navigation.shortest_path_length` | GT path length / A* on `navigable` (succeeded goals) |
| 13 | Method comparison | none | none | `aggregate.compare_methods` exists | ON HOLD; not run |
| 14 | Cleaning efficiency | `cleaning_efficiency` | ratio up | `coverage.cleaning_keys` | cleaned fraction / overlap ratio |
| A1 | Coverage vs time | `t_to_{50,80,95}_{explored,cleaned}_s`, `coverage_explored_auc`, `coverage_cleaned_auc`, `coverage_curve.csv` | s down / % up | `coverage` | first crossing; mean of curve |
| A2 | Overlap / redundancy | `overlap_ratio`, `redundancy_pct` | ratio down | `coverage.cleaning_keys` | `sum visits / swept cells` |
| A3 | Missed area | `missed_area_m2`, `missed_explored_m2` | m^2 down | `coverage.cleaning_keys` | `(reach - swept) * res^2` |
| A4 | Distance, energy proxy | `distance_gt_m`, `energy_proxy_m2ps` | m, m^2/s down | `navigation` | path sum; `sum (vL^2+vR^2) dt` |
| A5 | Min/mean clearance | `min_clearance_m`, `mean_clearance_m`, `clearance_p05_m`, `time_below_*` | m up / s down | `safety` | exact signed distance, capped 1.0 m |
| A6 | Recovery count | `n_recoveries`, `recov_{spin,backup,wait}_n` | count down | `navigation` | max recoveries per goal UUID, summed |
| A7 | Stuck / timeout | `n_stuck_goals`, `end_reason` | count down | `navigation`, `compute_metrics.find_stuck` | timeout + oscillation goals; stuck rule |
| A8 | Planning time | `plan_latency_ms_mean`, `_p95`, `replans_per_goal_mean` | ms down | `navigation` | acceptance to first plan row |
| A9 | Path smoothness | `smooth_curvature_rms_1pm`, `smooth_jerk_rms_mps3` | 1/m down | `navigation` | RMS of `wz/vx` over `abs(vx) >= 0.05` |
| A10 | SLAM tracking-lost / drift | `odom_drift_ratio`, `slam_drift_ratio`, `n_est_gaps`, `est_gap_total_s` | ratio, count down | `trajectory` | final error / GT distance; runs of `est_ok != 1` >= 1 s |
| A11 | CPU and RAM | `cpu_*_mean_pct`, `cpu_*_peak_pct`, `rss_*_peak_mb`, `ram_used_peak_mb` | %, MB down | `resources` | window mean / max |
| A12 | Real-time factor | `rtf_true_mean`, `rtf_mean/p05/min` | ratio up | `validity`, `resources` | mean of `rtf.csv` |
| A13 | Repeatability | `cv`, `std`, `ci95_halfwidth` in aggregate output | none | `aggregate.group_stats` | `sd/|mean|`; t-interval; no per-metric repeatability table is produced |
| A14 | AMCL localisation error | `loc_error_mean_m`, `loc_error_p95_m`, `loc_converge_s`, `loc_lost_events` | m down | `trajectory._amcl` | mean/p95 of fixed-frame error (AMCL runs) |
| A15 | Noise robustness | `delta_*` in aggregate (paired noise on/off) | delta | `aggregate` (paired comparison) | not measured in the 2026-10-25 campaign (noise-off condition dropped) |
| D1 | Contact odometry corruption (diagnostic) | `odom_corrupted_by_contact`, `contact_odom_yaw_excess_*`, `ate_*_pre_corrupt` | deg | `contact_odom` | yaw excess in contact windows |

---

## 17. Summary of every place the docs and code disagree

| # | Topic | Docs say | Code does |
|---|---|---|---|
| 1 | #8 map completeness | IoU of free and occupied vs GT | Mean of free recall and occupied recall (3x3 tolerance on occupied); IoUs are secondary keys |
| 2 | #6 ATE alignment | RMSE after rigid SE3 alignment, no scale | Headline `ate_fixed_rmse_m` is unaligned (fixed world frame via spawn / `t_world_map`); aligned 2D rigid version is secondary |
| 3 | #5 step response threshold | cmd to 90 % of commanded velocity | Step test uses 50 % of the step; latency measured on wall clock |
| 4 | #11 correctness | GT pose at closure matches GT pose of the matched node | Headline compares RTAB-Map's registered transform to the GT relative transform (0.10 m, 5 deg); pose proximity (0.30 m, 30 deg) is the fallback and a secondary key |
| 5 | LC transform convention | verified `loop_to_ref` (yaml) | Code fallback default is `ref_to_loop`; the YAML value is used when the config loads |
| 6 | Robot z-band top | `eval_defaults.yaml`: 0.30 | `gt_grid.build` / `geometry.load_obstacles` default 0.25 and the YAML value is not passed in |
| 7 | Health thresholds | YAML: frame offset 0.10 m, map shift 0.20 m | Built-in defaults in `health.py` are 0.5 and 0.5 (YAML overrides in the pipeline) |
| 8 | Pooled CIs | "episode-level cluster bootstrap" (audit); 10 000 resamples (prereg) | `make_report`: worlds then episodes within world, B = 2000; `aggregate`: episodes, B = 5000 |
| 9 | A8 | "per-goal median is informative" (audit) | Only mean and p95 are produced (plus `replans_per_goal_mean`); no median key |
| 10 | A14 | "uses the AMCL-converged window" (audit) | `trajectory._amcl` averages over all valid rows (`est_ok == 1`); no convergence window in this file |
| 11 | #10 | Count of Nav2 result codes | Headline is GT-verified success: succeeded goals within 0.30 m at `t_end`, over (succeeded + failed) |
| 12 | A4 energy proxy | integral of `v^2 dt` | `sum (vL^2 + vR^2) dt` with wheel speeds from GT `vx`, `wz`, wheel base 0.268 m |
| 13 | A7 | Counts of goals/episodes hitting the time limit | `n_stuck_goals` counts only timeout + oscillation goals; abort failures and the stuck-rule episodes are not in it |
| 14 | #3 | "debounced distinct events" | 0.5 s gap per model; one jam can still produce 3-7 events |

**One-line summary:** every metric here is computed offline from per-episode CSVs against a 5 cm ground-truth grid built from the SDF (obstacle band 0.03-0.25 m, reach mask for the denominators), with episode-level health flags and bootstrap/Wilson pooling, and the code differs from the docs in 14 places listed in section 17.
