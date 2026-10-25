| # | Metric | Headline key | Campaign | Value (pooled over worlds, valid episodes) |
|---|---|---|---|---|
| 1 | Coverage (explored) | `coverage_explored_pct` | no | no data (campaign invalid=0, failed=0) |
| 1 | Coverage (cleaned, secondary) | `coverage_cleaned_pct` | yes | 16.3 % [7.6, 27.3] cluster CI, n=12, 3 worlds (campaign invalid=0, failed=0) |
| 2 | Steps: goals | `n_goals` | yes | 14.4 count [10.1, 19.0] cluster CI, n=12, 3 worlds (campaign invalid=0, failed=0) |
| 2 | Steps: command ticks | `n_cmd_ticks` | yes | 4933.9 count [2182.9, 8249.6] cluster CI, n=12, 3 worlds (campaign invalid=0, failed=0) |
| 2 | Steps: recoveries | `n_recoveries` | yes | 147.6 count [107.0, 183.6] cluster CI, n=12, 3 worlds (campaign invalid=0, failed=0) |
| 3 | Total collisions | `n_collisions` | yes | 1.9 count [0.5, 3.7] cluster CI, n=12, 3 worlds (campaign invalid=0, failed=0) |
| 4 | Obstacle avoidance | `avoidance_pct` | yes | 93.2 % [81.2, 100.0] cluster CI, n=8, 2 worlds (campaign invalid=0, failed=0) |
| 5 | Responsiveness | `responsiveness_pct` | yes | 40.8 % [5.4, 77.2] cluster CI, n=12, 3 worlds (campaign invalid=0, failed=0) |
| 6 | ATE (fixed frame) | `ate_fixed_rmse_m` | yes | 0.380 m [0.199, 0.636] cluster CI, n=12, 3 worlds (campaign invalid=0, failed=0) |
| 7 | RPE (1 m) | `rpe_trans_rmse_m_1m` | yes | 0.265 m [0.195, 0.353] cluster CI, n=12, 3 worlds (campaign invalid=0, failed=0) |
| 8 | Map completeness | `map_completeness_pct` | no | no data (campaign invalid=0, failed=0) |
| 9 | Avoidance trial success | `avoid_trial_success_pct` | no | no data (campaign invalid=0, failed=0) |
| 10 | Navigation success (GT) | `nav_success_gt_pct` | yes | 23.4 % [2.8, 46.7] cluster CI, n=12, 3 worlds (campaign invalid=0, failed=0) |
| 11 | Loop closure precision | `lc_precision_pct` | no | no data (campaign invalid=0, failed=0) |
| 11 | Loop closure recall | `lc_recall_pct` | no | no data (campaign invalid=0, failed=0) |
| 12 | Path length ratio | `path_length_ratio_mean` | yes | 1.209 - [1.087, 1.273] cluster CI, n=9, 3 worlds (campaign invalid=0, failed=0) |
| 14 | Cleaning efficiency (secondary) | `cleaning_efficiency` | yes | 0.103 - [0.063, 0.146] cluster CI, n=12, 3 worlds (campaign invalid=0, failed=0) |

| # | Metric | Key | Campaign | Value |
|---|---|---|---|---|
| A1 | Time to 50 % explored | `t_to_50_explored_s` | no | no data |
| A1 | Explored AUC | `coverage_explored_auc` | no | no data |
| A2 | Overlap ratio | `overlap_ratio` | yes | 1.475 - [1.143, 1.839], n=12 |
| A3 | Missed area | `missed_area_m2` | yes | 31.654 m2 [22.957, 38.106], n=12 |
| A4 | Distance (GT) | `distance_gt_m` | yes | 38.119 m [15.223, 66.223], n=12 |
| A4 | Energy proxy | `energy_proxy_m2ps` | yes | 19.701 m2/s [7.917, 34.246], n=12 |
| A5 | Min clearance | `min_clearance_m` | yes | 0.045 m [0.000, 0.110], n=12 |
| A8 | Planning latency | `plan_latency_ms_mean` | yes | 9310.6 ms [581.8, 25251.1], n=12 |
| A9 | Path smoothness | `smooth_curvature_rms_1pm` | yes | 3.009 1/m [1.966, 3.864], n=12 |
| A10 | Odometry drift ratio | `odom_drift_ratio` | yes | 0.025 - [0.009, 0.061], n=12 |
| A12 | True RTF | `rtf_true_mean` | yes | 1.000 - [1.000, 1.000], n=12 |
| A14 | AMCL localization error | `loc_error_mean_m` | yes | 0.318 m [0.183, 0.509], n=12 |
