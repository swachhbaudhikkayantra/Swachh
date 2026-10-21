# 13. Pre-registration (freeze before final data)

Frozen at the git commit recorded in each experiment's `batch_manifest.json` (with the campaign file SHA-256). Anything not listed here is exploratory.

## 13.1 Metrics (headline summary.json keys; units)
- `coverage_explored_pct` (%): SLAM-map free cells inside GT free area / GT free area, final value; `coverage_explored_auc` is its time-average.
- `coverage_cleaned_pct` (%): swept area / GT free area (swath 0.25 m); secondary, with `cleaning_efficiency` (secondary: cleaned area per path length, m2/m).
- `map_iou_free_pct`, `map_completeness_pct` (%): map quality vs GT after alignment.
- `ate_fixed_rmse_m` (m): absolute trajectory error of SLAM pose vs GT in the fixed (map) frame; `ate_aligned_rmse_m` aligned variant.
- `nav_success_pct` (%): scripted goals reached within tolerance / goals attempted (`nav_success_gt_pct` uses GT pose).
- `path_length_ratio_mean` (-): executed path length / shortest GT path, successful goals.
- `n_collisions` (count), `min_clearance_m` (m), `avoidance_pct` (%): collisions, minimum obstacle distance, and share of encounters passed without contact.
- `trial_success` (0/1, avoid_* scenarios): goal reached without collision.
- `responsiveness_pct` (%): share of command/stop/goal/obstacle events met within deadlines. This is **wall-clock controller latency** (lat_*_ms), not a task outcome.
- `lc_precision_pct`, `lc_recall_pct`, `lc_f1_pct` (%): loop closures vs GT revisits.
- `rtf_mean` (-), `cpu_total_mean_pct` (%), `ram_used_peak_mb` (MB): resources.

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

## 13.6 Change log
| Date | Change | Reason |
|---|---|---|
| 2026-10-21 | Initial draft | Task B of doc 14 |
| 2026-10-21 | Added symmetric_hall to final_exploration campaign (6 worlds, 120 episodes) | Measure false loop closures |
