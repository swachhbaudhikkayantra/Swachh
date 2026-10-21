# 05 — Navigation Metrics

Covers: #10 navigation success rate, #12 path length ratio, A4 distance/energy, A6 recoveries, A7 (goal-level timeouts), A8 planning latency, A9 smoothness. Also defines the scripted-goal test mode ("`scripted_goals`" method) used for navigation-only experiments.
Depends on: 00, 01 (§1.4 velocity loop fix, §1.5 goal events), 02 (`goal_events.csv`, `plans.csv`, `feedback.csv`, `trajectory.csv`), 03 (`navigable`, `a_reach`, GT grid).
Module: `vacuum_eval/metrics/navigation.py`; nodes: `goal_sender.py`.

---

## 5.1 Goal records

A **goal record** is built from `goal_events.csv` as follows.

- Method `frontier`: pair each `src=explore, event=started` row with the `ended` row of the same `goal_seq`. Fields: `t_start, t_end, x, y` (goal position, frame `map`), `result`.
- Method `scripted_goals`: same with `src=scripted`.
- A goal with a `started` row but no `ended` row before `episode_end_t` has `result = unfinished`.
- Goal position in the world frame: `goal_w = t_world_map ∘ (x, y, 0)` (spec 04 §4.2).

Only goals with `t_start ≥ episode_start_t` and `t_start ≤ episode_end_t` are considered.

## 5.2 Navigation success rate (#10)

Result classes: `succeeded`, failures = `{nav_aborted, timeout, oscillation, rejected}`, ignored = `{canceled_by_manager, unfinished}`.

| Key | Definition |
|---|---|
| `nav_goals_total` | `#succeeded + #failures` |
| `nav_goals_succeeded` | `#succeeded` |
| `nav_goals_failed` | `#failures` |
| `nav_goals_canceled` | `#canceled_by_manager`; `nav_goals_unfinished` = `#unfinished` |
| `nav_success_pct` | `100 · succeeded / total` (null if total = 0) |
| `nav_fail_aborted`, `nav_fail_timeout`, `nav_fail_oscillation`, `nav_fail_rejected` | counts (A7 goal level) |
| `nav_success_gt_pct` | Independent check: a goal counts as reached iff the GT position at `t_end` is within `0.30 m` of `goal_w` (the Nav2 goal checker tolerance `xy_goal_tolerance`, `nav2_params.yaml`); percentage over the same `total` |
| `goal_time_mean_s`, `goal_time_median_s` | `t_end − t_start` over succeeded goals |

`nav_success_pct` is what Nav2 reported; `nav_success_gt_pct` is whether the robot really arrived. A large gap means localisation error (noisy odometry) is making the robot believe it arrived.

## 5.3 Path length ratio (#12)

For each **succeeded** goal with `shortest ≥ 0.5 m`:

- `actual` = GT path length between `t_start` and `t_end`: `Σ hypot(Δx, Δy)` over consecutive `trajectory.csv` GT positions in that interval (10 Hz).
- `shortest` = length of the shortest obstacle-free path for the robot centre from the GT position at `t_start` to `goal_w`, computed on `navigable` (spec 03 §3.2.8) as follows:
  1. Start/goal cells = the nearest `navigable` cell to each point within 0.30 m (else the goal is skipped and counted in `ratio_skipped`).
  2. 8-connected A* on `navigable`, step cost 1 (orthogonal) and √2 (diagonal) times `res`, Euclidean heuristic; no diagonal moves that cut a corner between two blocked cells.
  3. **String-pulling:** from the cell path, greedily keep the farthest waypoint visible from the current waypoint where visibility = every cell along the Bresenham line is `navigable`. 
  4. `shortest` = polyline length `[start_point, waypoints…, goal_point]`, using the true continuous start and goal points as end points.
- `ratio_g = actual / shortest`.

Keys: `path_length_ratio_mean` (**headline**), `path_length_ratio_median`, `path_length_ratio_p90`, `path_length_ratio_n`, `ratio_skipped`. Ideal 1.0; values below ~0.97 indicate a bug (shortest too long or `actual` truncated).

Also `plan_length_ratio_mean`: ratio of the **first** `/plan` length after the goal's `accepted` status (from `plans.csv`) to `shortest`; separates global-planner quality from controller wandering.

## 5.4 Planning latency and replanning (A8)

Goals are matched to Nav2 `goal_events.csv` `src=nav2_status` rows by time: the Nav2 `accepted` row nearest after the goal's `t_start` (within 2 s).
- `plan_latency_ms_mean/p95` = `1000·(t of first plans.csv row after accepted − t_accepted)` per goal (this is end-to-end: BT start + planner compute; it is **not** the pure planner time. Pure planner time is available from the `planner_server` log line "Computed path" only if debug logging is on and is out of scope).
- `replans_per_goal_mean` = mean of `(number of plans.csv rows with t in [accepted, end]) − 1`.

## 5.5 Recoveries (A6)

- `number_of_recoveries` from `feedback.csv`: per goal uuid take the **maximum** value; `n_recoveries = Σ` over goals; `recoveries_per_goal_mean`.
- By type: the recorder also records the behaviour-server action status topics `/spin/_action/status`, `/backup/_action/status`, `/wait/_action/status` as `goal_events.csv` rows `src=behavior_spin|behavior_backup|behavior_wait` with `event` = status name (same mapping as nav2_status). Keys `recov_spin_n, recov_backup_n, recov_wait_n` = number of `accepted` rows in the episode window. (**Required recorder addition** — add these three subscriptions to spec 02 §2.4 `goal_events.csv`; already listed there as an obligation by this spec.)
- `n_stuck_goals` = `nav_fail_timeout + nav_fail_oscillation` (A7).

## 5.6 Distance and energy (A4)

All from GT rows in the window, sampled at 10 Hz:
- `distance_gt_m` (spec 02) and `distance_odom_m` (from `odom_*`), `distance_ratio_odom_gt = distance_odom_m / distance_gt_m`.
- Wheel speeds: `vL = gt_vx − gt_wz·b/2`, `vR = gt_vx + gt_wz·b/2` with `b = 0.268 m`. `energy_proxy_m2ps = Σ (vL² + vR²)·Δt` with `Δt` = difference of consecutive row times. Unit m²/s.
- `mean_speed_mps`, `time_stationary_s` (rows with `|gt_vx| < 0.02` and `|gt_wz| < 0.05`, times 0.1 s), `time_rotating_inplace_s` (`|gt_vx| < 0.05` and `|gt_wz| ≥ 0.05`).

## 5.7 Smoothness (A9)

Using rows with `|gt_vx| ≥ 0.05 m/s` (excludes in-place rotation):
- curvature `κ = gt_wz / gt_vx`; `smooth_curvature_rms_1pm = sqrt(mean κ²)`, `smooth_curvature_var = var(κ)`.
- linear jerk: `a_k = (gt_vx_{k+1} − gt_vx_k)/Δt`, `j_k = (a_{k+1} − a_k)/Δt`; `smooth_jerk_rms_mps3 = sqrt(mean j²)`.
Note 10 Hz sampling of 30 Hz data makes jerk noisy; the number is only comparable between runs made with this exact pipeline.

## 5.8 Scripted-goal mode (`scripted_goals`)

Purpose: navigation metrics independent of exploration. Used for #10, #12, A6, A8, A9 and (with obstacles) #9.

**Map source:** `--nav-map gt` (default) or `slam`.
- `gt`: the harness exports the GT grid as a Nav2 map: `python3 -m vacuum_eval.metrics.gt_grid --world W --export-map <run_dir>/gt_map` writing `gt_map.pgm` + `gt_map.yaml` with the grid's `x0, y0, res`, free=254 (cells in `a_clean`), occupied=0 (cells in `occ`), unknown=205 (everything else, i.e. outside walls) so that **`map` frame ≡ `world` frame** (`t_world_map = [0, 0, 0]` recorded in `run_meta`). Localisation: `ros2 launch vacuum_nav2 nav2_localization.launch.py map_path:=<run_dir>/gt_map.yaml` with the initial pose published at the spawn pose (`/initialpose`, exact). `localization_mode: amcl`.
- `slam`: Nav2 + RTAB-Map online as in `nav2.launch.py`, `t_world_map` = spawn pose.

**Goal lists** are generated by the harness before launch into `<run_dir>/goals.yaml` (list of `{x, y, yaw}` in `world`), using `rng = default_rng(seed + 2000)`:

| List name | Rule |
|---|---|
| `fixed` | the world's hand-picked list from `worlds.yaml: goal_lists.fixed` (keeps them in order) |
| `random20` | 20 goals sampled sequentially from cells of `a_reach` with `dist_to_obstacle ≥ 0.40 m`, requiring Euclidean distance from the previous goal ≥ 1.5 m and a GT-grid shortest path ≥ 1.5 m; uniform over eligible cells; `yaw` uniform |
| `near_wall` | 10 goals at cells with `0.20 ≤ dist_to_obstacle ≤ 0.35 m` (same other rules) |
| `long_range` | 6 goals: the eligible cell farthest (path distance) from the previous goal, alternating ends of the map |

`goal_sender.py` (ROS node): parameters `goals_file`, `frame` (`map`), `t_world_map` (3 floats), `goal_timeout_sim_sec` (120). For each goal: convert world→map (`se2_inverse(t_world_map) ∘ goal`), send `NavigateToPose` (`nav2_msgs/action/NavigateToPose`, action `navigate_to_pose`, `behavior_tree` empty = default), publish `/eval/goal_events` JSON `{"goal_seq", "event": "started", "t_start", "x", "y", ...}` before sending, and at the end `{..., "event":"ended", "result", "t_end", "nav2_error_code"}`; result mapping: action SUCCEEDED → `succeeded`; ABORTED → `nav_aborted`; goal rejected → `rejected`; own timeout → cancel the goal, `timeout`; own cancel never used otherwise. After the last goal publish `/eval/done` (`std_msgs/Bool`, true, transient-local). Wait 1.0 s sim between goals. Goals are sent **one at a time**.

## 5.9 Function contract

```
compute_navigation_metrics(run: Run, gt: GtGrid) -> dict       # all keys above
shortest_path_length(gt: GtGrid, start_xy, goal_xy) -> float|None   # A* + string-pulling as in §5.3
```

## 5.10 Verification notes

| Check | Expected | Observed |
|---|---|---|
| Straight corridor goal, no obstacles: `shortest` equals Euclidean distance (±0.01 m) | yes | |
| Goal behind a wall segment: shortest > Euclidean | yes | |
| Goal inside furniture (not navigable): skipped, counted | yes | |
| Replay of a recorded run recomputes identical keys | yes | |

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-10-20 | `canceled_by_manager` and `unfinished` excluded from the success denominator | They are decisions of the exploration logic or the end of the episode, not navigation failures |
| 2026-10-20 | Scripted-goal navigation tests use a map derived from the ground truth by default | Isolates the planner/controller from SLAM quality |
| 2026-10-20 | `plan_latency` is named latency, not planner time | Measured end-to-end on topics |

## Decision 2026-10-21
- `nav_success_gt_pct`: succeeded goals whose GT position at the time Nav2 reported success is within 0.30 m of the goal; `nav_success_gt_strict_pct` uses 0.15 m. Nav2's own tolerance is no longer reused (circularity removed). Denominator is all counted goals.
- `canceled` (goal_sender) is a failure (`nav_fail_canceled`) and stays in the denominator, except goals canceled by the harness at episode end (t_end within 1 s of episode_end_t): excluded and counted in `nav_goals_truncated`.
- Time-based keys (`time_stationary_s`, `time_rotating_inplace_s`) use the actual per-row dt from `t` (diff clipped to [0, 1.0] s).

## 2026-10-21 - Localization source option (`--localization`)

`run_episode --localization {auto,slam,amcl,gt}` (scripted_goals). `auto` keeps the old behaviour
(nav-map gt -> AMCL, slam -> RTAB-Map). `gt` (requires `--nav-map gt`) runs plain `nav2.launch.py`
(AMCL cannot be disabled by a launch argument of `nav2_localization.launch.py`), serves the exported
GT map with `nav2_map_server` (lifecycle configure/activate via a bash wrapper) and starts
`gt_localization_node`, which publishes TF map->odom = T_map_world * T_world_base(GT) * inv(T_odom_base)
at 30 Hz with the GT stamp. map_origin_x/y/yaw default 0 because the exported GT map frame equals world.
The /initialpose step is skipped; run_meta records `localization_mode: gt`. This separates navigation
failures from localization error. validity.py skips RTAB-Map rules only for `amcl`; it needs a change
to also skip for `gt`.
