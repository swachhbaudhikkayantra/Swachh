| # | Metric | Headline key | Campaign | Value (pooled over worlds, valid episodes) |
|---|---|---|---|---|
| 1 | Coverage (explored) | `coverage_explored_pct` | partial | 54.1 % [48.5, 59.7] cluster CI, n=2, 1 worlds (campaign invalid=2, failed=0) |
| 1 | Coverage (cleaned, secondary) | `coverage_cleaned_pct` | partial | 0.7 % [0.7, 0.7] cluster CI, n=2, 1 worlds (campaign invalid=2, failed=0) |
| 2 | Steps: goals | `n_goals` | partial | 0.0 count [0.0, 0.0] cluster CI, n=2, 1 worlds (campaign invalid=2, failed=0) |
| 2 | Steps: command ticks | `n_cmd_ticks` | partial | 420.0 count [420.0, 420.0] cluster CI, n=2, 1 worlds (campaign invalid=2, failed=0) |
| 2 | Steps: recoveries | `n_recoveries` | partial | 0.0 count [0.0, 0.0] cluster CI, n=2, 1 worlds (campaign invalid=2, failed=0) |
| 3 | Total collisions | `n_collisions` | partial | 0.0 count [0.0, 0.0] cluster CI, n=2, 1 worlds (campaign invalid=2, failed=0) |
| 4 | Obstacle avoidance | `avoidance_pct` | partial | 100.0 % [100.0, 100.0] cluster CI, n=1, 1 worlds (campaign invalid=2, failed=0) |
| 5 | Responsiveness | `responsiveness_pct` | partial | 100.0 % [100.0, 100.0] cluster CI, n=2, 1 worlds (campaign invalid=2, failed=0) |
| 6 | ATE (fixed frame) | `ate_fixed_rmse_m` | partial | 0.110 m [0.110, 0.111] cluster CI, n=2, 1 worlds (campaign invalid=2, failed=0) |
| 7 | RPE (1 m) | `rpe_trans_rmse_m_1m` | partial | 0.141 m [0.138, 0.144] cluster CI, n=2, 1 worlds (campaign invalid=2, failed=0) |
| 8 | Map completeness | `map_completeness_pct` | partial | 38.3 % [33.9, 42.8] cluster CI, n=2, 1 worlds (campaign invalid=2, failed=0) |
| 9 | Avoidance trial success | `avoid_trial_success_pct` | no | no data (campaign invalid=2, failed=0) |
| 10 | Navigation success (GT) | `nav_success_gt_pct` | no | no data (campaign invalid=2, failed=0) |
| 11 | Loop closure precision | `lc_precision_pct` | partial | 76.3 % [69.2, 83.3] cluster CI, n=2, 1 worlds (campaign invalid=2, failed=0) |
| 11 | Loop closure recall | `lc_recall_pct` | partial | 100.0 % [100.0, 100.0] cluster CI, n=2, 1 worlds (campaign invalid=2, failed=0) |
| 12 | Path length ratio | `path_length_ratio_mean` | no | no data (campaign invalid=2, failed=0) |
| 14 | Cleaning efficiency (secondary) | `cleaning_efficiency` | partial | 0.002 - [0.002, 0.002] cluster CI, n=2, 1 worlds (campaign invalid=2, failed=0) |

| # | Metric | Key | Campaign | Value |
|---|---|---|---|---|
| A1 | Time to 50 % explored | `t_to_50_explored_s` | partial | 59.3 s [55.9, 62.7], n=2 |
| A1 | Explored AUC | `coverage_explored_auc` | partial | 40.6 % [39.3, 41.9], n=2 |
| A2 | Overlap ratio | `overlap_ratio` | partial | 3.829 - [3.792, 3.865], n=2 |
| A3 | Missed area | `missed_area_m2` | partial | 38.908 m2 [38.905, 38.910], n=2 |
| A4 | Distance (GT) | `distance_gt_m` | partial | 4.116 m [4.111, 4.120], n=2 |
| A4 | Energy proxy | `energy_proxy_m2ps` | partial | 1.469 m2/s [1.466, 1.472], n=2 |
| A5 | Min clearance | `min_clearance_m` | partial | 0.480 m [0.378, 0.582], n=2 |
| A8 | Planning latency | `plan_latency_ms_mean` | no | no data |
| A9 | Path smoothness | `smooth_curvature_rms_1pm` | partial | 0.000 1/m [0.000, 0.000], n=2 |
| A10 | Odometry drift ratio | `odom_drift_ratio` | partial | 0.024 - [0.024, 0.024], n=2 |
| A12 | True RTF | `rtf_true_mean` | partial | 0.981 - [0.963, 1.000], n=2 |
| A14 | AMCL localization error | `loc_error_mean_m` | no | no data |
