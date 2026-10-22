# 13. Pre-registration (freeze before final data)

Frozen at the git commit recorded in each experiment's `batch_manifest.json` (with the campaign file SHA-256). Anything not listed here is exploratory.

## 13.1 Metrics (headline summary.json keys; units)
- `coverage_explored_pct` (%): SLAM-map free cells inside the reachable GT area / reachable GT area (a_reach dilated by the inscribed radius, within a_clean), final value; `coverage_explored_auc` is its time-average. `*_aclean_pct` variants (whole free area) are secondary.
- `coverage_cleaned_pct` (%): swept area (swath 0.25 m) / reachable GT area; secondary, with `cleaning_efficiency` = (coverage_cleaned/100) / overlap_ratio (dimensionless, 0-1) and `cleaned_m2_per_m`. Secondary until a coverage planner exists.
- `map_completeness_pct` (%): (free recall + occupied-boundary recall)/2 of the final SLAM map vs the GT grid using the FIXED spawn transform (no alignment search); `map_iou_free_pct` likewise. `map_completeness_aligned_diag_pct` is a diagnostic only (alignment optimised on the scored map).
- `ate_fixed_rmse_m` (m): absolute trajectory error of SLAM pose vs GT in the fixed (map) frame; `ate_aligned_rmse_m` aligned variant.
- `nav_success_gt_pct` (%, headline): goals Nav2 reported succeeded AND ground-truth position within 0.30 m of the goal at the success time / goals attempted (canceled goals count as failures; goals truncated by the episode end are excluded and counted). `nav_success_gt_strict_pct` uses 0.15 m; `nav_success_pct` is Nav2's own report (secondary).
- `path_length_ratio_mean` (-): executed path length / shortest GT path, successful goals.
- `n_collisions` (count), `min_clearance_m` (m), `avoidance_pct` (%): collisions, minimum obstacle distance, and share of encounters passed without contact.
- `trial_success` (0/1, avoid_* scenarios): goal reached without collision.
- `responsiveness_pct` (%): share of command/stop/goal/obstacle events met within deadlines. This is **wall-clock controller latency** (lat_*_ms), not a task outcome.
- `lc_precision_pct` (%): accepted RTAB-Map loop closures whose computed relative transform matches the GT relative pose within 0.10 m / 5 deg (`lc_reg_*` keys); `lc_recall_pct` (%): GT revisits (within 1.0 m / 60 deg of a node >= `lc_min_time_gap_s` older) that produced an accepted closure; `lc_f1_pct`. Same-pose (0.30 m/30 deg) and loose (1.0 m/60 deg) precision are secondary.
- `rtf_true_mean` (-, sim-time/wall-time), `cpu_total_mean_pct` (%), `ram_used_peak_mb` (MB): resources. Gazebo's /stats real_time_factor field must not be used (it reported 1.00 while the true rate was ~0.49).

## 13.2 Tolerances and thresholds
All in `vacuum_eval/config/eval_defaults.yaml`: `collision_gap_s`, `encounter_distance_m`, `deadline_*_s`, `lc_pos_tol_m`, `lc_yaw_tol_deg`, `lc_min_time_gap_s`, `swath_width_m`, `r_inscribed_m`, `robot_body_z_*`, `grid_*`, `odom_noise.*`, `validity.*`. Not tunable after freeze.

## 13.3 Validity / exclusion
An episode gets `status: invalid` (excluded from statistics but listed and counted) if: image drop > 10 % (`max_img_drop_pct`), RTAB-Map update gap > 5 s (`max_rtabmap_gap_s`), or RTAB-Map updates < 0.5 per second of the expected rate (`min_rtabmap_update_frac`). No other post-hoc exclusions. Failed/partial episodes are kept with their status; invalid runs are re-run once with the same seed only for infrastructure faults, and both attempts are reported.

## 13.4 Split, seeds, lengths
- Dev (tuning allowed): apartment, empty_room, cluttered_room, avoid_head_on, avoid_cluster, avoid_narrow_gap_wide, avoid_dynamic_cross; seeds 1-5.
- Test (frozen, no tuning after first test run): office, corridor, two_rooms_door, multi_room_loop, maze_dead_ends, symmetric_hall, avoid_narrow_gap, avoid_u_trap, avoid_dead_end, avoid_dynamic_sudden; seeds 101-110.
- Reasoning: dev holds simple baselines and easier avoidance variants; test holds structurally hard layouts and hardest scenarios. Machine-readable in `worlds.yaml` (`split`, `splits`, `seeds`); enforced by `run_batch.py --split` and `--confirm-test-split`.
- Campaigns (`config/campaigns/`): exploration 600 s, odom noise 0 and 1; navigation 1200 s cap, goal lists random20 and long_range, GT nav map; avoidance 10 trials per scenario; responsiveness bare and loaded, 3 seeds. symmetric_hall (deliberately identical textures) is in final_exploration to measure false loop closures / perceptual aliasing.

## 13.5 Statistics
Episode is the unit (goals/encounters within an episode are not independent). Report mean, median, per-world breakdown; 95 % CIs by cluster bootstrap (resample seeds within world, then worlds; 10 000 resamples); success rates also pooled with Wilson intervals. Method/noise comparisons: paired by (world, seed), Holm correction across the family of headline metrics.

## 13.5b Reported regardless of outcome
All invalid/failed counts, every world and seed in the test split that was run, unfavourable metrics, negative loop-closure results, and any deviation from this document.

## 13.5c Health flags
Health flags never exclude episodes. All statuses (including UNMEASURABLE, SUSPECT, LOW_N, BAD) are reported, and an unmeasurable metric is reported as not measurable with its reason and fallback.

## 13.6 Change log
| Date | Change | Reason |
|---|---|---|
| 2026-10-21 | Initial draft | Task B of doc 14 |
| 2026-10-21 | Added symmetric_hall to final_exploration campaign (6 worlds, 120 episodes) | Measure false loop closures |
| 2026-10-21 | Corrected 13.1 to the implemented definitions: reachable coverage denominator, unaligned completeness headline, GT nav success at success time, transform-based loop-closure truth, true RTF | Draft had pre-fix definitions |
| 2026-10-22 | Added secondary diagnostic keys (module `metrics/contact_odom.py`): `contact_odom_n_events`, `contact_odom_yaw_excess_deg` (sum over contact events of \|Δodom_yaw − ΔGT_yaw\|, event window ± `collision_gap_s`), `contact_odom_yaw_excess_max_deg`, `odom_corrupted_by_contact` (max event excess > `contact_odom_corrupt_deg` = 15 deg in eval_defaults.yaml), `t_odom_corrupt_ep_s`, and `ate_fixed_rmse_m_pre_corrupt` / `ate_odom_fixed_rmse_m_pre_corrupt` / `ate_improvement_pct_pre_corrupt` (same ATE definitions, episode cut at the first corrupting contact). **Rule:** the flag is a reporting stratifier, never an exclusion (13.3 unchanged); the ATE headline is reported over all valid episodes, and additionally with/without flagged episodes and as a median. Headline keys unchanged. | Pilot 2: wheel slip during a chair contact (Spin recovery while pressed against it) put +123 deg into odometry yaw; SLAM followed; ATE 3.10 m vs 0.119 m before the contact. Council `council/2026-10-22-031950/` |
| 2026-10-22 | Dev-split stack change: SLAM-map static layer added to the local costmap; explore BT runs BackUp before Spin. Pilot 1/2 numbers come from the earlier stacks and are not pooled with later runs. | Same event; the BT's ClearEntireCostmap wipes STVL before every Spin, so no decay length could keep the obstacle |
| 2026-10-22 | Added rule 13.5c: health flags (`health_<metric>`: OK, LOW_N, UNMEASURABLE, SUSPECT, BAD, NA, with reasons) are diagnosis triggers and stratifiers only; they never exclude an episode, and every status is reported. Floors and min-n are in `docs/FAILURE_MODES.md`. Only 13.3 infrastructure faults allow a single same-seed rerun, with both attempts reported. | Failure-mode playbook, so bad or unmeasurable metrics are reported, not filtered |
