| # | Metric | Headline key | Campaign | Value (pooled over worlds, valid episodes) |
|---|---|---|---|---|
| 1 | Coverage (explored) | `coverage_explored_pct` | no | no data (campaign invalid=0, failed=0) |
| 1 | Coverage (cleaned, secondary) | `coverage_cleaned_pct` | yes | 6.2 % [5.5, 7.4] cluster CI, n=6, 2 worlds (campaign invalid=0, failed=0) |
| 2 | Steps: goals | `n_goals` | yes | 0.0 count [0.0, 0.0] cluster CI, n=6, 2 worlds (campaign invalid=0, failed=0) |
| 2 | Steps: command ticks | `n_cmd_ticks` | yes | 770.0 count [379.7, 1350.5] cluster CI, n=6, 2 worlds (campaign invalid=0, failed=0) |
| 2 | Steps: recoveries | `n_recoveries` | yes | 2.2 count [0.0, 5.0] cluster CI, n=6, 2 worlds (campaign invalid=0, failed=0) |
| 3 | Total collisions | `n_collisions` | yes | 0.2 count [0.0, 0.5] cluster CI, n=6, 2 worlds (campaign invalid=0, failed=0) |
| 4 | Obstacle avoidance | `avoidance_pct` | yes | 80.0 % [25.0, 100.0] cluster CI, n=5, 2 worlds (campaign invalid=0, failed=0) |
| 5 | Responsiveness | `responsiveness_pct` | partial | 33.3 % [0.0, 100.0] cluster CI, n=3, 1 worlds (campaign invalid=0, failed=0) |
| 6 | ATE (fixed frame) | `ate_fixed_rmse_m` | yes | 0.131 m [0.065, 0.214] cluster CI, n=6, 2 worlds (campaign invalid=0, failed=0) |
| 7 | RPE (1 m) | `rpe_trans_rmse_m_1m` | yes | 0.163 m [0.072, 0.267] cluster CI, n=6, 2 worlds (campaign invalid=0, failed=0) |
| 8 | Map completeness | `map_completeness_pct` | no | no data (campaign invalid=0, failed=0) |
| 9 | Avoidance trial success | `avoid_trial_success_pct` | no | no data (campaign invalid=0, failed=0) |
| 10 | Navigation success (GT) | `nav_success_gt_pct` | yes | 83.3 % [33.3, 100.0] cluster CI, n=6, 2 worlds (campaign invalid=0, failed=0) |
| 11 | Loop closure precision | `lc_precision_pct` | no | no data (campaign invalid=0, failed=0) |
| 11 | Loop closure recall | `lc_recall_pct` | no | no data (campaign invalid=0, failed=0) |
| 12 | Path length ratio | `path_length_ratio_mean` | yes | 1.549 - [1.072, 2.171] cluster CI, n=6, 2 worlds (campaign invalid=0, failed=0) |
| 14 | Cleaning efficiency (secondary) | `cleaning_efficiency` | yes | 0.057 - [0.053, 0.063] cluster CI, n=6, 2 worlds (campaign invalid=0, failed=0) |

| # | Metric | Key | Campaign | Value |
|---|---|---|---|---|
| A1 | Time to 50 % explored | `t_to_50_explored_s` | no | no data |
| A1 | Explored AUC | `coverage_explored_auc` | no | no data |
| A2 | Overlap ratio | `overlap_ratio` | yes | 1.085 - [1.000, 1.188], n=6 |
| A3 | Missed area | `missed_area_m2` | yes | 22.173 m2 [21.967, 22.281], n=6 |
| A4 | Distance (GT) | `distance_gt_m` | yes | 6.657 m [5.213, 8.687], n=6 |
| A4 | Energy proxy | `energy_proxy_m2ps` | yes | 3.606 m2/s [2.943, 4.546], n=6 |
| A5 | Min clearance | `min_clearance_m` | yes | 0.159 m [0.076, 0.227], n=6 |
| A8 | Planning latency | `plan_latency_ms_mean` | yes | 3.3 ms [0.0, 8.7], n=6 |
| A9 | Path smoothness | `smooth_curvature_rms_1pm` | yes | 3.642 1/m [1.245, 6.309], n=6 |
| A10 | Odometry drift ratio | `odom_drift_ratio` | yes | 0.020 - [0.006, 0.044], n=6 |
| A12 | True RTF | `rtf_true_mean` | yes | 0.911 - [0.812, 1.000], n=6 |
| A14 | AMCL localization error | `loc_error_mean_m` | yes | 0.112 m [0.059, 0.174], n=6 |
