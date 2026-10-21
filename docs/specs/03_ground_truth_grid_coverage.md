# 03 — Ground-Truth Grid, Coverage, Map Completeness

Covers: #1 average coverage (explored flavour; cleaned flavour is finished in spec 10), #8 map completeness %, A1 coverage-vs-time, A3 missed area (explored side).
Depends on: 00, 01 (ground truth), 02 (raw files `trajectory.csv`, `maps/*.npz`, `run_meta.yaml`), 09 (worlds must be readable and sealed).

Module: `vacuum_eval/metrics/gt_grid.py` (builds the grid), `vacuum_eval/metrics/coverage.py` (uses it).

---

## 3.1 What the SDF files look like (verified 2026-10-20)

All four existing worlds contain: `<model name="...">` with `<static>true</static>` and `<pose>x y z roll pitch yaw</pose>`; one `<link name="link">` per model; collisions named `col` with geometry `box`, `cylinder` (axis = model z), `sphere`, or the ground `plane`. **No `<include>`, no meshes, no nested models, no per-link or per-collision `<pose>` in the existing files.** The rasteriser must still handle `<pose>` on `<link>` and `<collision>` (compose model∘link∘collision) because new worlds may use them (spec 09 allows them). Anything else (mesh, polyline, capsule, ellipsoid, `<include>`, nested `<model>`, non-zero roll/pitch on a collision-bearing pose, `<frame>`/`relative_to`) → raise `UnsupportedSdf("<what> in model <name>")`; never silently skip.

## 3.2 Ground-truth grid construction (`gt_grid.build(sdf_path, spawn_xy, resolution=0.05)`)

**Constants** (from `eval_defaults.yaml`): `grid_resolution_m = 0.05`, `robot_body_z_lo = 0.03`, `robot_body_z_hi = 0.25`, `r_inscribed_m = 0.125`, `grid_margin_m = 0.50`.

1. Parse with `xml.etree.ElementTree`. `world_name = root.find('world').get('name')`.
2. For every `<model>` directly under `<world>`: pose `Pm`; for every `<link>`: pose `Pl` (default 0); for every `<collision>`: pose `Pc` (default 0). Absolute pose = `Pm ∘ Pl ∘ Pc` (full 6-DoF composition, but roll and pitch must be 0 → else `UnsupportedSdf`). Pose text is six floats; fewer floats → remaining are 0.
3. For each collision with geometry:
   - `box` size `(sx, sy, sz)`: z interval `[z−sz/2, z+sz/2]`, footprint = rectangle `sx × sy` rotated by yaw.
   - `cylinder` radius `r`, length `L`: z interval `[z−L/2, z+L/2]`, footprint = disc radius `r`.
   - `sphere` radius `r`: z interval `[z−r, z+r]`, footprint = disc radius `r` (conservative: full radius).
   - `plane`: ignored (ground).
4. **Obstacle rule:** a collision is an obstacle iff its z interval overlaps `(robot_body_z_lo, robot_body_z_hi)`, i.e. `z_hi_obj > 0.03 and z_lo_obj < 0.25`. Consequences: the 2 cm rug is not an obstacle; the ceiling (z=3.0, thickness defined by SDF) is not an obstacle; walls, furniture bodies, pillars are.
5. **Grid extents:** `minx = min(footprint x) − grid_margin_m`, similarly for others, over all obstacle footprints; `x0 = floor(minx / res)·res`, `y0` likewise; `W = ceil((maxx + margin − x0)/res)`, `H = ...`. Cell `(i, j)` (column i along x, row j along y) has centre `(x0 + (i+0.5)·res, y0 + (j+0.5)·res)`. Arrays are indexed `[j, i]`; row 0 = lowest y.
6. **Rasterisation:** for each obstacle footprint compute the boolean mask of cells whose centre is inside it (rectangle: transform centre into the rectangle frame, test `|px| ≤ sx/2 and |py| ≤ sy/2`; disc: `hypot ≤ r`). `occ` = union. Vectorise with numpy over the footprint's bounding box only.
7. **Cleanable area:** `a_clean` = connected component of `~occ` containing the cell of `reachable_seed` (from `worlds.yaml`), **4-connectivity** (`scipy.ndimage.label` with default structure). **Seal check:** if `a_clean` contains any cell in the outermost ring of the grid → `WorldNotSealed` error (the world has a gap to the outside or no outer wall). `A_clean_m2 = a_clean.sum() · res²`.
8. **Navigable (robot centre) area:** `d = scipy.ndimage.distance_transform_edt(~occ) · res` (distance of each free cell centre to the nearest obstacle cell centre); `navigable = (d ≥ r_inscribed_m) & a_clean`; `a_reach` = connected component of `navigable` containing the spawn cell (4-conn). Used by spec 05 (shortest paths) and 06.
9. **Boundary cells** `B`: obstacle cells having at least one 4-neighbour in `a_clean` (the surfaces the robot can see).
10. **Output:** `~/eval_runs/_gt/<world>.npz` with `occ`, `a_clean`, `navigable`, `boundary` (bool arrays), `dist_to_obstacle` (float32, metres), `x0, y0, res`, `world_name`, `A_clean_m2`, `A_reach_m2`; and `<world>.png` (matplotlib: occ black, a_clean white, navigable light green, spawn candidates red dots) for human review. CLI: `python3 -m vacuum_eval.metrics.gt_grid --world apartment` (reads `worlds.yaml` for sdf path and seed).
    Also `obs_id` (int16, same shape; −1 for free cells, else index into `obs_names`) and `obs_names` (model names in SDF order); a cell covered by several obstacles gets the lowest index. Required by spec 06.
11. Determinism: same SDF → byte-identical arrays.

## 3.3 Map ↔ ground-truth alignment

- The SLAM map frame equals `world` transformed by `T_world_map = (spawn_x, spawn_y, spawn_yaw)` (spec 00 §0.3). To sample a map for a GT cell centre `p_world`: `p_map = se2_inverse(T_world_map) ∘ p_world`; `col = floor((p_map.x − origin_x)/map_res)`, `row = floor((p_map.y − origin_y)/map_res)` (map `origin_yaw` is 0 for RTAB-Map's grid; assert). Out of bounds → unknown (−1). Nearest-cell sampling (no interpolation).
- Map classes: `map_free = (v == 0)`, `map_occ = (v ≥ 65)`, `map_unknown = (v == −1)`; values 1–64 are treated as unknown-ish "uncertain" and counted as none of free/occ (RTAB-Map normally emits only −1/0/100).
- **Alignment check (mandatory per run):** the module also evaluates a small search over `dx, dy ∈ {−0.30,…,0.30}` step 0.05 m and `dyaw ∈ {−5°,…,+5°}` step 1°, maximising `occ_recall + occ_precision` (defined in §3.5) at the final map; it reports the best shift as `map_align_dx_m, map_align_dy_m, map_align_dyaw_deg` and the completeness with the best shift as `map_completeness_aligned_pct`. The primary numbers use the **fixed** (spawn-defined) transform. If the best shift magnitude exceeds 0.20 m or 3°, append note `"map frame offset vs spawn pose exceeds tolerance"`.

## 3.4 Coverage (#1, explored flavour)

`coverage_explored_pct = 100 · |{c ∈ a_clean : map_free(c)}| / |a_clean|`

computed on the **final map** (`maps/final_map.npz`, saved at `episode_end_t`) → key `coverage_explored_pct`. Notes:
- The denominator is the ground truth, never the map. Unknown and out-of-bounds cells inside `a_clean` count as not covered.
- Obstacles marked free by the map do not matter (the numerator is limited to `a_clean`).
- The old `exploration_status.coverage_pct` / `exploration_metrics.coverage_pct` (`free/(free+unknown)` of the live map) must **not** be reported in results.

### Coverage over time (A1)
For each snapshot `maps/map_*.npz` with `t ≥ episode_start_t` (and the final map), compute the same quantity; write `coverage_curve.csv` in the run dir with columns `t_ep` (= `t − episode_start_t`), `coverage_explored_pct`, `coverage_cleaned_pct` (the latter from spec 10 §10.4, evaluated at the same `t`). Keys: `t_to_50_explored_s`, `t_to_80_explored_s`, `t_to_95_explored_s` (first `t_ep` where the explored coverage ≥ threshold; `null` if never; resolution = snapshot period 5 s), and the same three for `cleaned` (resolution = trajectory sampling 0.1 s). Also `coverage_explored_auc` = trapezoid area under the explored curve over `[0, episode_sim_sec]` divided by `episode_sim_sec` (mean coverage level over the episode, %).

### Explored missed area (A3 explored side)
`missed_explored_m2 = (|a_clean| − |{c ∈ a_clean: map_free(c)}|) · res²`. Also write `missed_explored.png` (red = unexplored cleanable cells over the GT outline) in the run dir.

## 3.5 Map completeness % (#8)

All on the final map, over the ground-truth grid cells.

- `free_recall = |a_clean ∩ map_free| / |a_clean|` (equals §3.4 fraction)
- `free_precision = |a_clean ∩ map_free| / |{c ∈ GT bbox: map_free(c)}|` (map-free cells outside `a_clean`, e.g. inside furniture or outside walls, are false positives; GT bbox = the grid extent)
- `occ_recall = |B ∩ dilate(map_occ, 1)| / |B|` where `dilate(·,1)` is a 3×3 binary dilation (tolerance of one cell = 0.05 m).
- `occ_precision = |map_occ ∩ dilate(B, 1)| / |{c ∈ GT bbox: map_occ(c)}|` (`null` if no map_occ cells).
- `iou_free = |a_clean ∩ map_free| / |a_clean ∪ (map_free ∩ GT bbox)|`
- `iou_occ = |dilate(map_occ,1) ∩ B| / |dilate(map_occ,1) ∪ B|` (both restricted to GT bbox)
- **Headline:** `map_completeness_pct = 100 · (free_recall + occ_recall) / 2`

Keys: `map_completeness_pct, map_completeness_aligned_pct, map_free_recall_pct, map_free_precision_pct, map_occ_recall_pct, map_occ_precision_pct, map_iou_free_pct, map_iou_occ_pct, map_align_dx_m, map_align_dy_m, map_align_dyaw_deg`.

Interpretation to put in the paper: #1 asks "how much of the floor was seen"; #8 additionally asks "were the walls and obstacles put in the right place". `occ_precision` can be below 100 % legitimately if the depth camera sees surfaces above the 0.25 m robot band and the RTAB-Map grid keeps them (check `rtabmap.yaml` `Grid/MaxObstacleHeight`; if unset it should be set to 0.25 for evaluation and recorded in `run_meta.yaml`).

## 3.6 `coverage` module contract

```
compute_coverage(run: Run, gt: GtGrid) -> dict   # keys listed above + coverage_curve.csv + missed_explored.png
```
Inputs: `run.meta` (spawn), `run.maps_final`, `run.map_snapshots`, `run.episode_start_t`, `run.episode_end_t`. If `final_map.npz` is missing: all keys `null`, note `"no final map"`.

## 3.7 Verification notes (fill during implementation)

| Check | Expected | Observed |
|---|---|---|
| `gt_grid --world apartment` `A_clean_m2` | approx. interior area (5.0 × 6.0 = 30.0 m² from wall inner faces: x∈[−3.0, 3.0], y∈[−2.5, 2.5]) minus furniture footprints with z-overlap, minus nothing else | |
| `rug` is not in `occ` | true | |
| Corridor with gaps → `WorldNotSealed` | raised | |
| Fixed vs aligned map shift on a drive-around map | < 0.20 m, < 3° | |
| `RTAB-Map Grid/MaxObstacleHeight` | value in effect | |

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-10-20 | Cells are 0.05 m; centre-inclusion rasterisation | Matches RTAB-Map's typical cell size (verify) and keeps area error < 2 % on furniture |
| 2026-10-20 | Denominator = connected free area from the spawn, not the whole room | Unreachable pockets (enclosed by furniture) must not penalise any method |
| 2026-10-20 | Fixed alignment is primary, searched alignment is diagnostic | The map frame is defined by the start pose; a search could hide a real SLAM frame error |
