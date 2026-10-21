# 04 — Trajectory Accuracy: ATE, RPE, Drift, Localization Error

Covers: #6 ATE, #7 RPE, A10 (odometry drift, SLAM tracking gaps), A14 (AMCL error, Stage 5). Depends on: 00, 01 (ground truth + `odom_mode:=eval`), 02 (`trajectory.csv`).
Module: `vacuum_eval/metrics/trajectory.py`. Implemented in numpy only; **`evo` is not used** (not installed). Optional cross-check against `evo` in test T-040.

---

## 4.1 Inputs and sample selection

From `trajectory.csv` rows with `episode_start_t ≤ t ≤ episode_end_t`. Columns used: `gt_x, gt_y, gt_yaw` (frame `world`), `est_x, est_y, est_yaw` (frame `map`, SLAM or AMCL), `odom_x, odom_y, odom_yaw` (frame `odom`), `est_ok`.

A row is **valid for SLAM metrics** iff `gt_*` and `est_*` are non-empty and `est_ok = 1`; **valid for odometry metrics** iff `gt_*` and `odom_*` non-empty. Ground truth and estimate are sampled in the same recorder tick, so **no time association step exists** (this is intentional; the max sample skew is one message period, ≤ 0.033 s at 30 Hz sources).

If fewer than 100 valid rows or GT path length `< 2.0 m` → all keys of that metric group `null`, note `"insufficient motion for ATE/RPE"`.

## 4.2 Frame alignment of the estimates

`t_world_map` = `run_meta.t_world_map` (list `[x, y, yaw]`); default = spawn pose `[spawn_x, spawn_y, spawn_yaw]`. For Stage-5 AMCL runs it must be the world pose of the saved map's origin (the spawn pose of the mapping run that produced the map). The odom frame always equals the spawn pose (odom origin = robot start): `t_world_odom = [spawn_x, spawn_y, spawn_yaw]`.

`est_w = t_world_map ∘ (est_x, est_y, est_yaw)`, `odom_w = t_world_odom ∘ (odom_x, odom_y, odom_yaw)` (SE(2) composition, spec 00 §0.10).

## 4.3 ATE (#6)

Position error `e_i = hypot(est_w.x_i − gt_x_i, est_w.y_i − gt_y_i)` for valid rows.

| Key | Definition |
|---|---|
| `ate_fixed_rmse_m` | `sqrt(mean(e_i²))` using the fixed `t_world_map` (**primary**) |
| `ate_fixed_mean_m`, `ate_fixed_max_m` | mean and max of `e_i` |
| `ate_yaw_rmse_deg` | `sqrt(mean(wrap(est_w.yaw_i − gt_yaw_i)²))` in degrees |
| `ate_aligned_rmse_m` | RMSE after the best rigid 2D alignment (no scale), below |
| `ate_samples` | number of valid rows |

**Rigid 2D alignment (Umeyama without scale), exact:** let `E_i = (est_w.x_i, est_w.y_i)`, `G_i = (gt_x_i, gt_y_i)`, means `Ē, Ḡ`, centred `e_i = E_i − Ē`, `g_i = G_i − Ḡ`.
`θ = atan2( Σ (e_i.x·g_i.y − e_i.y·g_i.x), Σ (e_i.x·g_i.x + e_i.y·g_i.y) )`, `R = [[cosθ, −sinθ],[sinθ, cosθ]]`, `t = Ḡ − R·Ē`. Aligned error `a_i = ‖R·E_i + t − G_i‖`, `ate_aligned_rmse_m = sqrt(mean(a_i²))`. **No scale correction anywhere.** (The legacy `evaluate_trajectory.py` used `--correct_scale`; do not reproduce.)

Why two numbers: fixed shows true global error including any frame offset between SLAM map and world; aligned shows internal consistency of the trajectory shape. The paper headline is `ate_fixed_rmse_m`; report aligned alongside.

## 4.4 RPE (#7)

Relative-pose error between pairs `(i, j)`, `j > i`:
`ΔG = se2_inverse(gt_i) ∘ gt_j`, `ΔE = se2_inverse(est_w_i) ∘ est_w_j`, `Err = se2_inverse(ΔG) ∘ ΔE`; translation error `hypot(Err.x, Err.y)`, rotation error `|wrap(Err.yaw)|`.

Two pair definitions (both reported):

| Suffix | Pair rule |
|---|---|
| `_1m` | cumulative GT path length `s` (sum of consecutive valid-row GT position increments); for every i, `j` = the first row with `s_j − s_i ≥ 1.0 m`; skip i if none |
| `_5s` | `j` = the row with `t_j − t_i` closest to 5.0 s within ±0.05 s; skip if none |

Keys per suffix: `rpe_trans_rmse_m_<sfx>`, `rpe_trans_mean_m_<sfx>`, `rpe_rot_rmse_deg_<sfx>`, `rpe_pairs_<sfx>`. Headline for the paper: `rpe_trans_rmse_m_1m` (units: metres of error per metre travelled = dimensionless drift fraction) and `rpe_rot_rmse_deg_1m`.

Same computation with `odom_w` in place of `est_w` gives `rpe_odom_trans_rmse_m_1m`, `rpe_odom_rot_rmse_deg_1m`, `ate_odom_fixed_rmse_m`, `ate_odom_aligned_rmse_m` (the odometry baseline).

`ate_improvement_pct = 100·(ate_odom_fixed_rmse_m − ate_fixed_rmse_m)/ate_odom_fixed_rmse_m` (null if the odometry ATE < 0.02 m, i.e. the clean-odometry case where there is nothing to improve).

## 4.5 Start-alignment check (mandatory; referenced by spec 00)

Mean over the first 5 s of valid rows from `episode_start_t` of `hypot` and `|wrap yaw|` between `est_w` and GT: keys `start_offset_m`, `start_offset_deg`. If `start_offset_m > 0.10` or `start_offset_deg > 5`, append note `"SLAM map frame is not at spawn pose; fixed ATE is dominated by frame offset"` (and then trust `ate_aligned_rmse_m`).

## 4.6 Drift and tracking gaps (A10)

| Key | Definition |
|---|---|
| `odom_final_error_m` | position error `odom_w` vs GT at the last valid odom row |
| `odom_drift_ratio` | `odom_final_error_m / distance_gt_m` |
| `slam_final_error_m`, `slam_drift_ratio` | same with `est_w` |
| `n_est_gaps` | number of maximal runs of consecutive rows with `est_ok = 0` lasting ≥ 1.0 s (TF map→base_footprint missing: SLAM/AMCL lost or not started) |
| `est_gap_total_s` | total duration of those runs |

`distance_gt_m` is the GT path length over the episode (spec 02 §2.2).

## 4.7 AMCL localization error (A14, Stage 5 only)

Applies only when `run_meta.localization_mode == "amcl"`. The estimate is then TF `map→base_footprint` published by AMCL. Use §4.2 with `t_world_map` = mapping run's spawn pose. Keys: `loc_error_mean_m`, `loc_error_p95_m` (95th percentile of `e_i`), `loc_converge_s` = first `t_ep` such that `e_i < 0.25 m` for all rows in `[t_ep, t_ep + 10 s]` (null if never), `loc_lost_events` = number of times `e_i` rises from < 0.25 to > 1.0 m. AMCL needs an initial pose: the harness publishes it once to `/initialpose` (`geometry_msgs/PoseWithCovarianceStamped`, frame `map`, covariance diag [0.25, 0.25, 0, 0, 0, 0.068]) from `run_meta.amcl_initial_pose`, and logs `events.csv: amcl_initial_pose_sent`. Initial pose error is an experimental factor (`0` = exact, or a sampled offset recorded in `run_meta`).

## 4.8 Noise requirement

ATE/RPE reported to the paper must come from runs with `--odom-noise 1` (odometry has drift to correct); `--odom-noise 0` runs are the reference. Both are always run (spec 02 §2.10).

## 4.9 Function contract

```
compute_trajectory_metrics(run: Run) -> dict    # all keys above, null where not computable
umeyama_2d(E: ndarray[N,2], G: ndarray[N,2]) -> (R: ndarray[2,2], t: ndarray[2])
rpe(gt: ndarray[N,3], est: ndarray[N,3], pair_indices: list[(i,j)]) -> (trans_err: ndarray, rot_err_rad: ndarray)
```

## 4.10 Verification notes

| Check | Expected | Observed |
|---|---|---|
| Identical gt/est → ATE=0, RPE=0 | exact 0 (≤1e-9) | |
| est = gt translated by (0.5, 0): fixed ATE = 0.5, aligned ATE ≈ 0 | yes | |
| Synthetic circle with 1 %/m heading drift → RPE rot ≈ 0.57°/m ± 5 % | yes | |
| Cross-check with `evo_ape tum --align` (optional) | match within 1e-3 m | |

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-10-20 | GT and estimate sampled in the same tick | Removes timestamp association error |
| 2026-10-20 | No scale correction | Hides real scale error in monocular-like pipelines; our sensors are metric |
