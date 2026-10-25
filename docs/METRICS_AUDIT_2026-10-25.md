# Metrics completeness audit, 2026-10-25 (test split, reduced 4-hour campaign on victus)

**Audience:** the paper authors and the next evaluation run.
**Scope:** every metric in `docs/REQUIREMENTS.md` / `docs/METRICS_STATUS.md` / `docs/specs/`: the 14 user metrics (#13 on hold) and the extras A1-A15.
**How it was made:**
- No simulation was run and no code, config or result was changed.
- Values are pooled over valid episodes of the campaign that should provide the metric. They use the report's own episode-level cluster bootstrap (`make_report.pooled_cluster_ci`) applied to the per-episode `summary.json` files.
- The script is saved as `results/metrics_audit_table.py`.
- Three independent Sonnet verifiers (metrics 1-5, 6-14, A1-A15) recomputed one value per metric from the raw CSV/NPZ files in `~/eval_runs` and compared them, with a 2 % tolerance.

**Campaigns:**
- `quick_exploration_noise`: 9 episodes, RTAB-Map + Nav2 + frontier explorer, odometry noise on. office and multi_room_loop ran with 3 concurrent simulations; maze_dead_ends with 2.
- `quick_navigation`: 12 episodes, **Nav2 + AMCL on a ground-truth map**, 2 slots.
- `quick_avoidance`: 6 episodes, AMCL on a GT map, 3 slots.
- `quick_responsiveness`: 4 episodes, of which 2 bare are invalid by design.

Status legend:
- **MEASURED:** faithful, no caveat needed.
- **MEASURED-CAVEAT:** a value exists but must be reported with the stated caveat.
- **UNMEASURABLE:** no valid value.
- **NOT RUN:** the experiment was not part of this campaign.

Evidence paths:
- `EL` = `docs/EXECUTION_LOG.md` (the audit entries of 2026-10-25).
- `EF` = `docs/EVALUATION_FINDINGS_2026-10-25.md`.
- Runs are under `~/eval_runs/`.

## 1. Metric table

| ID and name | Campaign | Value, pooled (95 % CI) | n eps with data / in campaign | n valid | Health flags (episodes) | Status | Reason if not MEASURED (evidence) |
|---|---|---|---|---|---|---|---|
| #1 Coverage explored (%) | exploration | 61.4 [18.5, 88.0] | 9 / 9 | 9 | OK 2, SUSPECT 5, BAD 2 | MEASURED-CAVEAT | 2 maze episodes never moved (explorer stall), so the 7 moving runs average 78.8 %. The free-only definition costs 2-6 pp. 6 of 9 ran at 3 slots. (EL "AUDIT 3", "STEP 1 (b)") |
| #2 Steps per episode: goals / recoveries | exploration | goals 15.2 [6.3, 21.0]; recoveries 81.9 | 9 / 9 | 9 | OK 9 | MEASURED-CAVEAT | 70-80 % of recoveries are instant costmap clears. (EL "AUDIT 2") |
| #3 Total collisions per episode | exploration / navigation / avoidance | 1.78 [0.44, 3.89] / 1.92 [0.50, 3.67] / 0.17 | 9 / 9; 12 / 12; 6 / 6 | 9 / 12 / 6 | OK (all) | MEASURED-CAVEAT | Counts contact bursts split by more than 0.5 s, so one jam counts 3-7 times. Wheels are not in the sensor (optimistic). 3-slot load on exploration. (EL "AUDIT 9") |
| #4 % obstacle avoidance | exploration; avoidance | 98.4 [96.9, 100] (n=6); 80.0 [25, 100] (n=5) | 6 / 9; 5 / 6 | 6; 5 | exploration UNMEAS 3 (maze is walls only); avoidance LOW_N 5, UNMEAS 1 | MEASURED-CAVEAT | Walls are excluded by design, so maze_dead_ends has no encounters. Avoidance denominators are 1-3 encounters. (EL "AUDIT 9") |
| #5 Responsiveness: step cmd->motion / stop latency (ms) | responsiveness (loaded) | 166.1 [160.4, 171.7] / 260.0 [249.7, 270.4] | 2 / 4 | 2 | OK 2 (bare: UNMEAS, invalid) | MEASURED-CAVEAT | n=2. Bare is invalid by construction (user decision). The goal-to-motion % values (41-74 %) are confounded by planning and are not this metric. The value is mostly the acceleration ramp. (EL "AUDIT 4") |
| #6 ATE, SLAM fixed frame (m) | exploration | 0.572 [0.326, 0.858] | 7 / 9 | 7 | SUSPECT 5, BAD 2, UNMEAS 2 | MEASURED-CAVEAT | 2 maze runs had no motion. Contact-odometry corruption in 4 of 9. FRAME_OFFSET flags are a mislabel of drift. 3-slot load. (EL "AUDIT (SLAM ATE/LC)") |
| #7 RPE, 1 m (m) | exploration | 0.250 [0.136, 0.438] | 7 / 9 | 7 | OK 3, SUSPECT 4, UNMEAS 2 | MEASURED-CAVEAT | Same as #6. |
| #8 Map completeness (%) | exploration | 47.7 [15.1, 70.6] | 9 / 9 | 9 | OK 1, SUSPECT 5, BAD 3 | MEASURED-CAVEAT | 2 stalled maze runs (moving runs 62.9 %). 1-cell wall tolerance (+5-8 pp at 2 cells). Office 103 has genuine yaw drift. (EL "AUDIT 3") |
| #9 Avoidance trial success (%) | avoidance | 66.7 [16.7, 100] (4 of 6) | 6 / 6 | 6 | OK 6 | MEASURED-CAVEAT | **The report row is blank** (make_report.py:35 key bug); the value is computed from `trial_success`. n=6. u_trap 3/3, dynamic_sudden 1/3. (EL "STEP 1 (d)") |
| #10 Navigation success, GT-verified (%) | navigation | 23.4 [2.8, 46.7] (178 goals) | 12 / 12 | 12 | OK 2, SUSPECT 1, BAD 9 | MEASURED-CAVEAT | **Nav2 + AMCL on a GT map, not RTAB-Map.** Dominant failure is START_OCCUPIED (AMCL error plus robot at walls). Nav2 self-reports about 50 %. (EF §3) |
| #11 Loop-closure precision / recall (%) | exploration | 36.8 [19.9, 94.3] (n=7) / 28.2 [12.6, 40.9] (n=9) | 7 / 9; 9 / 9 | 7; 9 | OK 2, BAD 5, UNMEAS 2 | MEASURED-CAVEAT | **Precision is a lower bound:** GT is taken at RTAB-Map Info arrival, not at the node stamp (0.1-0.4 s lag, rotation error vs a 5 deg tolerance). A diagnostic time shift gives 52-77 %. (EL "AUDIT 8", "AUDIT (SLAM ATE/LC)") |
| #12 Path length ratio | navigation | 1.209 [1.087, 1.273] | 9 / 12 | 9 | OK 6, LOW_N 3, UNMEAS 3 | MEASURED-CAVEAT | Unweighted mean of per-episode means, over successful goals only. 3 episodes had no successful goal. (verifier 2) |
| #13 Method comparison | — | — | — | — | — | NOT RUN | ON HOLD (user decision; specs/11_baselines_on_hold.md) |
| #14 Cleaning efficiency (secondary) | exploration | 0.0545 [0.0226, 0.0842] | 9 / 9 | 9 | OK 9 | MEASURED-CAVEAT | The explorer is not a cleaner (secondary metric). 3-slot load on 6 of 9. |
| A1 Time to 50 % explored (s) | exploration | 67.7 [39.8, 124.7] | 7 / 9 | 7 | (coverage flags) | MEASURED-CAVEAT | The 2 stalled maze runs never reach 50 % (censored). |
| A1 Explored AUC (%) | exploration | 52.9 [21.2, 74.6] | 9 / 9 | 9 | (coverage flags) | MEASURED | — |
| A2 Overlap ratio | exploration | 1.95 [1.44, 2.45] | 9 / 9 | 9 | none | MEASURED | Not independently recomputed (needs the swept grid). |
| A3 Missed area (m²) | exploration | 37.6 [33.7, 40.7] | 9 / 9 | 9 | none | MEASURED | Not independently recomputed (needs the GT grid). |
| A4 Distance GT (m) / energy proxy (m²/s) | exploration | 44.2 [19.7, 59.7] / 23.2 [10.3, 31.4] | 9 / 9 | 9 | none | MEASURED | Energy proxy not independently recomputed. |
| A5 Min clearance (m) | avoidance | 0.159 [0.076, 0.227] | 6 / 6 | 6 | none | MEASURED-CAVEAT | Wheels protrude about 1.8 cm beyond the footprint, so it is optimistic. Not independently recomputed. (EL "AUDIT 9") |
| A6 Recoveries per episode | navigation | 147.6 [107.0, 183.6] | 12 / 12 | 12 | none | MEASURED-CAVEAT | 70-80 % are instant costmap clears; goals saturate at 15. (EL "AUDIT 2") |
| A7 Stuck / timeout goals | navigation | 0 goals (timeout + oscillation); 7 of 12 episodes ended by the stuck rule (exploration 2 of 9) | 12 / 12 | 12 | none | MEASURED-CAVEAT | The definition counts only timeout/oscillation, but all 89 failed goals were aborts. Episode-level stuck counts are the informative number. (`~/eval_runs/quick_navigation/*/*/seed_*/summary.json`) |
| A8 "Planning latency" (ms) | navigation | mean 9311 [582, 25251]; per-goal median ~10 ms (nav) / ~30 ms (explore) | 12 / 12 | 12 | none | MEASURED-CAVEAT | It is time to first successful plan, dominated by stuck goals. Report the median. (EL "AUDIT 2") |
| A9 Path smoothness (1/m) | navigation | 3.01 [1.97, 3.86] | 12 / 12 | 12 | none | MEASURED | Not independently recomputed. |
| A10 Odometry drift ratio | exploration | 0.086 [0.022, 0.126] | 7 / 9 | 7 | none | MEASURED | Not independently recomputed. 2 maze runs had no motion. |
| A11 CPU total mean (%) | exploration | 85.5 [66.0, 96.4] | 9 / 9 | 9 | none | MEASURED-CAVEAT | Inflated by 3 concurrent simulations in 6 of 9 runs. (EL "AUDIT 7") |
| A12 True real-time factor | all test campaigns | 0.927 [0.848, 0.982]; range 0.729-1.000 | 31 / 31 | 29 | none fired (LOW_RTF never fired) | MEASURED | — |
| A13 Repeatability (CV across seeds) | exploration / navigation | coverage CV office 0.13, multi_room_loop 0.04, maze 1.55 (sample CV); nav-success CV office 0.58, two_rooms 0.21, maze 1.73 | 3-4 seeds per world | — | — | MEASURED-CAVEAT | No report table exists (computed here). n=3-4 seeds per world. |
| A14 AMCL localization error (m) | navigation | 0.318 [0.183, 0.509] | 12 / 12 | 12 | — | MEASURED-CAVEAT | Large maze bias (wrong particle mode, recovery off); depth HFOV is 69 deg, not 86. (EL "AUDIT 6") |
| A15 Noise robustness | — | — | 0 | — | — | NOT RUN | The noise-off condition was dropped from the reduced plan (docs/FOUR_HOUR_PLAN.md, docs/EIGHT_HOUR_PLAN.md §2). |

**Totals:**
- MEASURED: 7 rows (A1 AUC, A2, A3, A4, A9, A10, A12).
- MEASURED-CAVEAT: 21 rows (30 rows in total).
- UNMEASURABLE: 0 at metric level (episode-level UNMEASURABLE entries are listed in the flags column).
- NOT RUN: 2 (#13, A15).

## 2. Independent verification (3 Sonnet verifiers, raw CSV/NPZ, tolerance 2 %)

| Rows | Result |
|---|---|
| #1, #2, #3 (exploration and navigation), #4, #4a, #5 cmd->motion, #5 stop | AGREE, 0 % (all episodes for #1-#3). #4/#4a checked the formula and pooling, not encounter detection. |
| #6, #7, #8, #9, #10, #11p, #11r, #12, #14 | AGREE, 0-0.08 %. #12 used the library's shortest-path denominator, so that part is not independent. |
| A1, A1b, A4, A6, A7, A11, A12 | AGREE (A1b -0.14 %, A4 +0.62 %, A6 +1.07 %, A11 -0.52 %) |
| **A8** | **DISAGREE −3.45 %** (8989 vs 9311 ms; worst episode 11.8 %). The metric's goal window and truncation handling was not replicated. Recomputed with the metric's "first executing within 2 s of goal start" rule. The metric itself is mislabelled anyway (§1). |
| **A14** | **DISAGREE −2.98 %** (0.308 vs 0.318 m; worst episode 5.6 %). The verifier used all est_ok rows; the metric uses the AMCL-converged window. Marginal. |
| A2, A3, A4e, A5, A9, A10 | INFEASIBLE from the raw CSVs alone (they need the GT/swept grids). Not verified. |
| Pooling | In every row, the table's pooled mean equals the plain mean of per-episode `summary.json` values over status-ok episodes. |

Minor notes from the verifiers:
- `n_goals` in navigation counts 1-2 fewer goals than the raw "started" events, because goals started outside the episode window are excluded.
- `n_recoveries` raw vs summary differ by 0-3 % for the same windowing reason.

## 3. Lists

### (a) Report-generator cells that are blank or wrong (correct value from raw data)
1. **#9 avoidance trial success:**
   - Every report shows "no data" (`make_report.py:35` uses key `avoid_trial_success_pct`, which no summary has).
   - Correct value: **66.7 % [16.7, 100], 4 of 6** (u_trap 3/3, dynamic_sudden 1/3).
2. **#5 responsiveness:**
   - In `quick_responsiveness/report` the row shows `responsiveness_pct` 100 % (pass/fail of the step deadline), not the latency. Correct headline: **cmd->motion 166.1 ms [160.4, 171.7], stop 260.0 ms [249.7, 270.4]**, loaded, n=2.
   - In the exploration and navigation reports, #5 is goal-to-motion averaged per run (navigation 40.8 %). It is confounded, and the spec says to pool counts: navigation pooled = 87/173 = **50.3 %**. It should not be called responsiveness.
3. **A8:** the reports show the mean (nav 9311 ms, explore 5457 ms). The informative value is the **per-goal median, about 10 ms (nav) / 30 ms (explore)**, labelled "time to first successful plan".
4. **#10 and #12 in `quick_avoidance/report`:** 83.3 % and 1.549 come from single-goal trials (n=1 per episode). They are not the navigation metrics and should be removed or marked not applicable.
5. **#1, #8, #11 in `quick_responsiveness/report`:** coverage 54.1 %, completeness 38.3 % and LC 76.3 % come from step-test runs with the explorer disabled. Not applicable.
6. **A7:** reported 0 stuck goals. The informative value is **7 of 12 navigation episodes ended by the stuck rule** (exploration 2 of 9); all 89 failed goals were aborts.
7. **#11 LC precision:** the cell is numerically right but has no lower-bound note (GT timing bias).
8. **A13:** no repeatability table is produced; the CVs are in §1.

### (b) Health flags that look misapplied (~72 entries + others; from EL "AUDIT 5")

| Flag pattern | Episodes / entries | Why misapplied |
|---|---|---|
| UNMEASURABLE (NO_DATA / MAP_MISSING / NO_EVENTS) on coverage, completeness, LC precision, LC recall in AMCL runs | 12 navigation + 6 avoidance × 4 metrics = **72 entries** | No SLAM in these stacks. Should be NA (`health.py` `_applicable` misses AMCL). |
| BAD (BELOW_FLOOR) on coverage and completeness in loaded responsiveness | 2 episodes × 2 = 4 | The explorer is disabled in step tests. |
| UNMEASURABLE (INVALID_EPISODE) on every metric of bare responsiveness | 2 episodes | Invalid via the RTAB-Map gate by construction (image drop 0, 80/80 step events met). Kept invalid by user decision. |
| nav_success BAD / SUSPECT / UNMEAS in frontier exploration | 9 episodes | Metric #10 applies to scripted goals only. |
| LOW_N on nav_success (5) and path ratio (6) in single-goal avoidance trials | 11 entries | n=1 by design. |
| FRAME_OFFSET in AMCL navigation | 7 episodes | It is AMCL start convergence (0.105-0.154 m), not a frame offset. |
| FRAME_OFFSET in SLAM exploration (multi_room_loop 101, 102) | 2 episodes | It fires on late map drift (alignment shift), not a start offset. |
| NAV_GT_DIVERGENCE edge cases | two_rooms 101/104 at exactly 30 pp are not flagged; n=1 avoidance gives 100 pp | Strict ">30" on 5-pp steps. |
| Precedence hides BAD | 16 of 59 BELOW_FLOOR breaches show as SUSPECT/LOW_N | Report floor breaches separately. |
| LC_ROT_BIAS never fires | 5 BAD LC episodes | The (5, 7] deg window misses medians of 7-13 deg. |

### (c) Metrics that carry the 3-slot load caveat
- **Exploration office and multi_room_loop, seeds 101-103 (6 of 9 exploration episodes, rtf 0.73-0.75):**
  - Core metrics: #1, #2, #3, #4, #6, #7, #8, #11, #14.
  - Extras: A1, A2, A3, A4, A6/A8 (exploration values), A10, A11.
  - Strongest concern: collisions, recoveries and stuck behaviour (controller-loop misses of 6-17/min against under 2/min).
  - End-state coverage and map metrics are only marginally affected.
- **Avoidance, all 6 episodes (3 slots; dynamic_sudden rtf 0.80-0.85):** #3 (avoidance), #4a, #9, A5.
- **Responsiveness loaded/101 (ran concurrently):** #5, about +5-10 % latency compared with the serial loaded/102.
- **Not affected:** navigation (#10, #12, A6-A9, A14) ran at 2 slots with rtf 1.0. Maze exploration ran at 2 slots.
