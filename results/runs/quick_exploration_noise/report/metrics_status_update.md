| # | Metric | Headline key | Campaign | Value (pooled over worlds, valid episodes) |
|---|---|---|---|---|
| 1 | Coverage (explored) | `coverage_explored_pct` | yes | 61.4 % [18.5, 88.0] cluster CI, n=9, 3 worlds (campaign invalid=0, failed=0) |
| 1 | Coverage (cleaned, secondary) | `coverage_cleaned_pct` | yes | 11.3 % [5.3, 16.2] cluster CI, n=9, 3 worlds (campaign invalid=0, failed=0) |
| 2 | Steps: goals | `n_goals` | yes | 15.2 count [6.3, 21.0] cluster CI, n=9, 3 worlds (campaign invalid=0, failed=0) |
| 2 | Steps: command ticks | `n_cmd_ticks` | yes | 7482.6 count [3192.7, 10460.4] cluster CI, n=9, 3 worlds (campaign invalid=0, failed=0) |
| 2 | Steps: recoveries | `n_recoveries` | yes | 81.9 count [31.0, 116.0] cluster CI, n=9, 3 worlds (campaign invalid=0, failed=0) |
| 3 | Total collisions | `n_collisions` | yes | 1.8 count [0.4, 3.9] cluster CI, n=9, 3 worlds (campaign invalid=0, failed=0) |
| 4 | Obstacle avoidance | `avoidance_pct` | yes | 98.4 % [96.9, 100.0] cluster CI, n=6, 2 worlds (campaign invalid=0, failed=0) |
| 5 | Responsiveness | `responsiveness_pct` | yes | 74.4 % [67.9, 80.0] cluster CI, n=7, 3 worlds (campaign invalid=0, failed=0) |
| 6 | ATE (fixed frame) | `ate_fixed_rmse_m` | yes | 0.572 m [0.326, 0.858] cluster CI, n=7, 3 worlds (campaign invalid=0, failed=0) |
| 7 | RPE (1 m) | `rpe_trans_rmse_m_1m` | yes | 0.250 m [0.136, 0.438] cluster CI, n=7, 3 worlds (campaign invalid=0, failed=0) |
| 8 | Map completeness | `map_completeness_pct` | yes | 47.7 % [15.1, 70.6] cluster CI, n=9, 3 worlds (campaign invalid=0, failed=0) |
| 9 | Avoidance trial success | `avoid_trial_success_pct` | no | no data (campaign invalid=0, failed=0) |
| 10 | Navigation success (GT) | `nav_success_gt_pct` | yes | 9.0 % [7.1, 11.1] cluster CI, n=7, 3 worlds (campaign invalid=0, failed=0) |
| 11 | Loop closure precision | `lc_precision_pct` | yes | 36.8 % [19.9, 94.3] cluster CI, n=7, 3 worlds (campaign invalid=0, failed=0) |
| 11 | Loop closure recall | `lc_recall_pct` | yes | 28.2 % [12.6, 40.9] cluster CI, n=9, 3 worlds (campaign invalid=0, failed=0) |
| 12 | Path length ratio | `path_length_ratio_mean` | yes | 1.527 - [1.054, 1.787] cluster CI, n=7, 3 worlds (campaign invalid=0, failed=0) |
| 14 | Cleaning efficiency (secondary) | `cleaning_efficiency` | yes | 0.055 - [0.023, 0.084] cluster CI, n=9, 3 worlds (campaign invalid=0, failed=0) |

| # | Metric | Key | Campaign | Value |
|---|---|---|---|---|
| A1 | Time to 50 % explored | `t_to_50_explored_s` | yes | 67.7 s [39.8, 124.7], n=7 |
| A1 | Explored AUC | `coverage_explored_auc` | yes | 52.9 % [21.2, 74.6], n=9 |
| A2 | Overlap ratio | `overlap_ratio` | yes | 1.946 - [1.437, 2.454], n=9 |
| A3 | Missed area | `missed_area_m2` | yes | 37.609 m2 [33.683, 40.654], n=9 |
| A4 | Distance (GT) | `distance_gt_m` | yes | 44.187 m [19.682, 59.666], n=9 |
| A4 | Energy proxy | `energy_proxy_m2ps` | yes | 23.184 m2/s [10.299, 31.389], n=9 |
| A5 | Min clearance | `min_clearance_m` | yes | 0.072 m [0.002, 0.196], n=9 |
| A8 | Planning latency | `plan_latency_ms_mean` | yes | 5457.4 ms [3072.8, 9614.6], n=7 |
| A9 | Path smoothness | `smooth_curvature_rms_1pm` | yes | 7.044 1/m [3.031, 7.904], n=7 |
| A10 | Odometry drift ratio | `odom_drift_ratio` | yes | 0.086 - [0.022, 0.126], n=7 |
| A12 | True RTF | `rtf_true_mean` | yes | 0.827 - [0.737, 1.000], n=9 |
| A14 | AMCL localization error | `loc_error_mean_m` | no | no data |
