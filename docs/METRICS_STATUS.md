# Metrics status tracker (live)

Single source of truth for **what has actually been measured**. Updated by the orchestrator after every run that changes a status. Definitions: `docs/METRICS_TO_BE_MEASURED.md` (what/why), `docs/specs/` (how), `docs/specs/13_preregistration.md` (frozen final definitions). The "Status" column inside METRICS_TO_BE_MEASURED.md is historical (day 1) and is not maintained.

Stage legend:
- **Code**: implemented and unit/oracle tested.
- **Valid run**: produced a value in at least one episode that passed the validity gates (images flowing, RTAB-Map alive), on the current pipeline.
- **Campaign**: measured on the pre-registered test split with enough episodes for the planned confidence interval. Only this stage counts for the paper.

Last update: 2026-10-25 ~19:45, reduced 4-hour test campaign done on victus (see section CAMPAIGN RESULTS below). Older text below is the 2026-10-22 dev status.


## CAMPAIGN RESULTS 2026-10-25 (reduced 4-hour campaign on victus; test split) — stage "Campaign"

Machine: victus, RTX 5050 Laptop, headless EGL; freeze commit 92c7757 plus logged deviations (goal-start tolerance, extra navigation seeds 103/104). 31 test episodes: responsiveness 4 (2 valid), avoidance 6, exploration 9 (odometry noise on), navigation 12. Only `status: invalid` excluded (2 bare responsiveness episodes). rtf_true_mean 0.729-1.000, none < 0.7. Values: pooled mean with episode-level cluster-bootstrap 95 % CI from `~/eval_runs/<campaign>/report/` (n small: per-world CIs are wide). Health flags never exclude. Reduced-campaign limitations: `docs/FOUR_HOUR_PLAN.md`, `docs/EXECUTION_LOG.md`.

**The navigation campaign (#10, #12, A14) measures Nav2 + AMCL on a ground-truth map (`--nav-map gt`), not the RTAB-Map pipeline.** Its ATE/RPE are AMCL estimate errors. SLAM metrics (#6-#8, #11) come from the exploration campaign.

| # | Metric | Source campaign | Value (95 % CI) | Health (episodes) / notes |
|---|---|---|---|---|
| 1 | Coverage explored | exploration | 61.4 % [18.5, 88.0], n=9 | office 83.8, multi_room_loop 86.3, maze_dead_ends 14.3 (2 of 3 maze episodes never moved: explorer's 0.30 m goal-clearance rule found no sendable frontier); health OK 2 / SUSPECT 5 / BAD 4 (U 20 = campaigns that do not explore) |
| 2 | Steps per episode | exploration | goals 15.2 [6.3, 21.0]; recoveries 81.9 [31, 116] | navigation: recoveries 147.6 [107, 184] per episode |
| 3 | Total collisions | exploration / navigation / avoidance | 1.8 [0.4, 3.9] / 1.9 [0.5, 3.7] / 0.2 [0, 0.5] per episode | contact sensors; OK 29, U 2 |
| 4 | % obstacle avoidance | exploration / navigation / avoidance | 98.4 % / 93.2 % / 80.0 % | |
| 5 | Responsiveness (wall-clock controller latency) | responsiveness (loaded stack only, n=2) | cmd->motion 171.7 / 160.4 ms (p95 222 / 189); stop 270.4 / 249.7 ms; responsiveness_pct 100 % | bare stack invalid by design (RTAB-Map validity rules; user decision); loaded/101 ran with 3 concurrent sims (+5-10 % latency) |
| 6 | ATE (SLAM) | exploration | 0.572 m [0.326, 0.858], n=7 | odom_corrupted_by_contact in 4 of 9 exploration episodes; ATE health over all campaigns OK 10 / SUSPECT 14 / BAD 3 / U 4 |
| 7 | RPE (1 m) | exploration | 0.250 m [0.136, 0.438] | |
| 8 | Map completeness | exploration | 47.7 % [15.1, 70.6] | maze_dead_ends low (see #1) |
| 9 | Avoidance trial success | avoidance | 66.7 % (4 of 6): avoid_u_trap 3/3, avoid_dynamic_sudden 1/3 | computed from per-episode `trial_success`; make_report's pooled row is empty (report-generator gap, not fixed under the freeze); LOW_N |
| 10 | Navigation success (GT-verified) | navigation (Nav2 + AMCL, GT map) | 23.4 % [2.8, 46.7], n=12 (178 goals; Nav2 reports 89 succeeded = 50 %) | BAD 14 / SUSPECT 4. Dominant failure: START_OCCUPIED (205): AMCL estimate 0.2-0.3 m off puts the footprint into wall cells (98 % / 97 % of events) while the true footprint is free (0-1 %); not the planner. Nav2's own success is higher (NAV_GT_DIVERGENCE) |
| 11 | Loop closure precision / recall | exploration | 36.8 % [19.9, 94.3] / 28.2 % [12.6, 40.9] | BAD 5 |
| 12 | Path length ratio | navigation | 1.209 [1.087, 1.273], n=9 | LOW_N 13 |
| 13 | Method comparison | - | ON HOLD | |
| 14 | Cleaning efficiency (secondary) | exploration | 0.055 [0.023, 0.084] | |
| A12 | True RTF | all | 0.729-1.000 | exploration 3-slot waves 0.73-0.75 |
| A14 | AMCL localization error | navigation | 0.318 m [0.183, 0.509] | the root of the START_OCCUPIED failures |
| A15 | Noise robustness | - | not measured | noise-off condition dropped |

## Core metrics (user's list)

| # | Metric | Headline key | Code | Valid run | Campaign | Value so far / what is missing |
|---|---|---|---|---|---|---|
| 1 | Coverage | `coverage_explored_pct`, `coverage_cleaned_pct` | yes | yes | no | pilot2: 90.4 % explored, 30.4 % cleaned (pilot1: 62.4 / 3.3, 210 s) |
| 2 | Steps per episode | `n_goals`, `n_cmd_ticks`, `n_recoveries` | yes | yes | no | pilot2: 27 goals (pilot1 355 was the goal-loop bug, now fixed), 34 584 cmd ticks, 260 recoveries |
| 3 | Total collisions | `n_collisions` (`collision_source`) | yes | yes | no | pilot2: 3 contact-sensor events, all with chair_1 (pilot1: 0); cause in "Pilot 2 findings" below |
| 4 | % obstacle avoidance | `avoidance_pct` | yes | yes | no | pilot2: 97.0 % of 33 encounters (exploration context); the scenario value comes with #9 |
| 5 | % responsiveness | `responsiveness_pct` (wall-clock controller latency) | yes | partial | no | pilot2: 88.9 %, goal events only (24 of 27 within 2 s); cmd/stop latencies need the responsiveness run (R4) |
| 6 | ATE | `ate_fixed_rmse_m` | yes | yes | no | pilot2: **3.10 m** (odometry 2.99 m, improvement -3.8 %), caused by contact-induced odometry corruption. Before the first corrupting contact: 0.119 m vs odometry 0.256 m (+53.4 %). Pilot1: 0.066 m |
| 7 | RPE | `rpe_trans_rmse_m_1m` | yes | yes | no | pilot2: 0.130 m per 1 m, 24.2 deg per 1 m (rotation inflated by the yaw jump) |
| 8 | Map completeness | `map_completeness_pct` (unaligned) | yes | yes | no | pilot2: 74.8 % (pilot1 45.4 %) |
| 9 | Obstacle-avoidance success rate | `avoid_trial_success_pct` | yes | no | no | the 8 avoid_* scenario worlds have never been launched (R5) |
| 10 | Navigation success rate | `nav_success_gt_pct` (+ `_strict`) | yes | yes | no | pilot2: **15.4 %** (4 of 26 frontier goals; 14 aborted, 8 timed out; 209 "no valid path"). Scripted goals with gt/amcl/slam localization (R3) separate navigation from localization |
| 11 | Loop-closure success | `lc_precision_pct`, `lc_recall_pct` | yes | partial | no | pilot2: 181 accepted; precision 43.6 %, recall 100 % after the R2 convention fix (`loop_to_ref`), which the R2 agent is verifying |
| 12 | Path length ratio | `path_length_ratio_mean` | yes | yes | no | pilot2: 2.48 (only n = 4 successful goals) |
| 13 | Method comparison | - | - | - | - | ON HOLD (user decision) |
| 14 | Cleaning efficiency (secondary) | `cleaning_efficiency` | yes | yes | no | pilot2: 0.141 (the explorer is not a cleaner; secondary until a coverage planner exists) |

**Counts:** valid run = 10 yes (1, 2, 3, 4, 6, 7, 8, 10, 12, 14), 2 partial (5, 11), 1 no (9); campaign = 0 of 13.

## Additional metrics (A1-A15)

| # | Metric | Key | Valid run | Missing |
|---|---|---|---|---|
| A1 | Coverage vs time, time to 50/80/95 % | `t_to_50_explored_s`, `coverage_curve.csv` | yes | pilot2: 50 % at 12.8 s, 80 % at 80.3 s |
| A2 | Overlap / redundancy | `overlap_ratio` | yes | pilot2: 2.16 |
| A3 | Missed area | `missed_area_m2` | yes | - |
| A4 | Distance, energy proxy | `distance_gt_m`, `energy_proxy_m2ps` | yes | pilot2: 72.0 m |
| A5 | Clearance | `min_clearance_m` (exact geometry) | yes | - |
| A6 | Recovery count | `n_recoveries` | yes | - |
| A7 | Stuck / timeout count | `end_reason`, `n_stuck_goals` | yes | pilot2: 8 stuck goals |
| A8 | Planning time | `plan_latency_ms_mean` | yes | pilot2: 5.3 s mean, 20.2 s p95 (slow sim, RTF 0.29) |
| A9 | Path smoothness | `smooth_curvature_rms_1pm` | yes | - |
| A10 | Drift / tracking gaps | `odom_drift_ratio`, `n_est_gaps` | yes | - |
| A11 | CPU / RAM per process | `cpu_*`, `rss_*` | yes | - |
| A12 | Real-time factor | `rtf_true_mean` | yes | pilot2 0.29 |
| A13 | Repeatability | aggregate std / CV | no | needs multiple seeds |
| A14 | AMCL localization error | `loc_error_mean_m` | no | scripted AMCL run (R3) |
| A15 | Noise robustness | aggregate `delta_*` | no | needs noise on/off pairs |
| D1 | Contact-induced odometry corruption (diagnostic, new 2026-10-22) | `odom_corrupted_by_contact`, `contact_odom_yaw_excess_deg`, `ate_*_pre_corrupt` | yes | pilot2: flag 1, 145 deg excess over 3 contact events, first at 273.3 s (episode time). It is a stratifier, never an exclusion (13.6) |

## Pilot 2 findings (R1, 2026-10-22)

Run: `~/eval_runs/pilot2/apartment/frontier/seed_002` (apartment, frontier, seed 2, 600 s, odom noise off).

R1 acceptance:
- **Valid:** `episode_valid` true, image drop 0 %. **Pass.**
- **RTAB-Map alive:** 586 updates in 600 s, max gap 1.16 s. **Pass.**
- **No goal loop:** `n_goals` is 27. `frontiers_skipped` is present in `/exploration/status` and stays 0 (the new guards never fired). **Pass.**
- **ATE improvement > 0:** **Fail** on the headline (-3.8 %), explained below. Before the corrupting contact it was +53.4 %.
- **Compared with pilot 1:** coverage 62.4 → 90.4 %, map completeness 45.4 → 74.8 %. ATE 0.066 m (210 s) became 3.10 m (600 s), or 0.119 m over the first 273 s.
- **STVL side effects:** STVL contributed to the 3 new collisions (decay plus no persistent memory; see below). Its effect on planner failures can't be shown from the data, since no costmap was recorded and goals already failed from t = 105 s, before any contact.

**The yaw jump is a real navigation failure. It is not a simulator artefact and not a recording bug.**
- **Not a recording bug:** `/diff_drive_controller/odom` equals the integral of the wheel joints, within 2.3 deg per 0.5 s. An independent recomputation reproduces ATE 3.098 / 2.985 m exactly.
- **Not physics:** contact z is always exactly the chassis bottom or top face (0.043 / 0.143 m), so there was no climbing or tilt. chair_1 is a static 0.45 × 0.45 × 0.9 m box. GT speeds stay bounded (≤ 0.3 m/s, ≤ 1.0 rad/s) and the trajectory is continuous.
- **Mechanism:**
  - chair_1 was behind the robot and was last seen by the camera about 28 s earlier. It had decayed out of the 15 s local STVL; the local costmap had no static layer.
  - MPPI drove an arc into the chair (contact 318.4–324.3 s, sim time).
  - The planner reported "start occupied". The BT ran ClearEntireCostmap and then a 90 deg Spin while the robot was pressed against the chair. Spin's collision check uses the local costmap, which no longer held the chair.
  - Wheels are velocity-commanded, so the blocked wheels slipped. Over 319–324 s they integrated about 232 deg of yaw while the body turned about 105 deg.
- **Effect:** the odometry yaw error went from -10 to +113 deg. Outside contact windows, the net wheel-vs-GT yaw excess over the whole episode is 0.1 deg. RTAB-Map followed the odometry and never recovered (SLAM yaw error 117–123 deg until the end).
- **Camera blind zone:** the depth min range is 0.20 m. At 279 s the robot was 1 cm from the chair with the chair in the FOV, and the scan returned 0 valid hits on it.

**Council** (`council/2026-10-22-031950/`, Sonnet-only):
- **Episode:** it stays valid and failed, and the headline ATE is kept.
- **New keys:** diagnostic keys were added as a stratifier, never as an exclusion. The ATE headline is also reported with and without flagged episodes, and as a median.
- **Stack fix:** the local costmap gets the SLAM-map static layer, and the explore BT runs BackUp before Spin.
- **Rejected:** no wheel torque limits (a guessed value would be a fudge factor), and no 3D-GT tilt rule (no tilt was seen).
- **Open:** the 8 cm axle offset (Spin collision checks rotate about the wrong point) is a documented limitation, not fixed.

**Still open:** nav success 15.4 % (209 "no valid path" and 40 "start occupied" messages) is the bigger problem. R3 (scripted goals with gt/amcl/slam localization) is the next step for it.

## Runs still needed before the campaign (dev split only)

1. **R1 confirmation** (stack fix; user runs it): apartment, frontier, seeds 2 and 1, 600 s. Stopping rule (pre-declared): `odom_corrupted_by_contact` = 0 and no Spin while in contact in both runs. Otherwise, revisit (axle offset, contact-aware recovery).
2. Scripted-goals runs (gt map; gt, AMCL and slam localization) for metrics 10, 12 and A14 (R3).
3. One responsiveness run (bare and loaded) for metric 5 (R4).
4. Dev avoidance scenarios (avoid_head_on, avoid_cluster, avoid_dynamic_cross) for metrics 3, 4 and 9 (R5).
5. Then the sample-size planner fixes episode counts, and the test-split campaign (`config/campaigns/final_*.yaml`) moves metrics to "Campaign".
