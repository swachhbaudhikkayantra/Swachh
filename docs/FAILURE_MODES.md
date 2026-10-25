# Failure-mode playbook (simulation evaluation, Q1 paper)

Use when a metric is bad or unmeasurable. Codes are those written to `summary.json` as `health_<metric>` and `health_<metric>_reasons`. Related: `specs/13_preregistration.md` (frozen rules), `METRICS_STATUS.md`, `RUNBOOK.md` section 11.

## 0. Codes and precedence

`OK`; `LOW_N:<count>/<min>`; `NA` (not applicable).
UNMEASURABLE: `NO_DATA`, `NO_EVENTS`, `INVALID_EPISODE`, `GT_MISSING`, `MAP_MISSING`.
SUSPECT: `ODOM_CORRUPTED`, `FRAME_OFFSET`, `RANGE`, `NAV_GT_DIVERGENCE`, `LOW_RTF`, `LC_ROT_BIAS`.
BAD: `BELOW_FLOOR:<value><op><floor>`.
Precedence: UNMEASURABLE > SUSPECT > LOW_N > BAD > OK.

Floors are diagnosis triggers, never exclusions: nav_success_gt_pct 50, coverage_explored_pct 70, map_completeness_pct 60, ate_fixed_rmse_m 0.30 (bad if above), lc_precision_pct 50, avoidance_pct 80. Minimum n: goals 5, encounters 3, lc_accepted 5, lc_revisits 3, resp_events 10.

Decisions: **FIX+RERUN** (artefact or bug, infrastructure only), **REPORT** (genuine result), **FALLBACK** (use a secondary key already computed), **COUNCIL** (judgment call).

## 1. Per-metric tables

Common first step for any non-OK status: open `summary.json` (`status`, `end_reason`, `episode_valid`, `img_drop_pct`, `rtf_true_mean`, `odom_corrupted_by_contact`), then the `diagnose` output for the episode.

### 1 Coverage (`coverage_explored_pct`, `coverage_cleaned_pct`)
| Failure mode | Detected by | First step | Decision |
|---|---|---|---|
| Episode invalid (DDS image drops > 10 %, RTAB-Map gap) | UNMEASURABLE:INVALID_EPISODE | check `img_drop_pct`, `rtabmap_max_gap_s` | FIX+RERUN once, same seed, report both |
| GT free-space grid missing | UNMEASURABLE:GT_MISSING | check world SDF to grid step | FIX+RERUN (offline recompute, no sim needed) |
| Frontier unreachable / goal loop (n_goals huge, `frontiers_skipped` > 0) | BELOW_FLOOR:..<70; `n_stuck_goals`, `n_goals` | `/exploration/status`, goals list | REPORT if explorer genuinely stalls; FIX+RERUN if loop bug |
| Low RTF, 600 s cap not enough sim progress | SUSPECT:LOW_RTF | `rtf_true_mean` | REPORT (sim-time cap is fixed); flag in text |
| Contact corruption stalls exploration | SUSPECT:ODOM_CORRUPTED | `t_odom_corrupt_ep_s` | REPORT, stratified |
| Cleaned coverage low because explorer is not a cleaner | `coverage_cleaned_pct` low, explored high | none | REPORT (design limit, say so) |

### 2 Steps (`n_goals`, `n_cmd_ticks`, `n_recoveries`)
| Failure mode | Detected by | First step | Decision |
|---|---|---|---|
| Goal loop (pilot1: 355 goals) | `n_goals` far above peers; `frontiers_skipped` | goal log | FIX+RERUN if bug recurs; else REPORT |
| No goals sent | UNMEASURABLE:NO_DATA | check exploration node alive | FIX+RERUN |
| Many recoveries from tight rooms / Smac DUBIN failures ("no valid path") | `n_recoveries`, planner failure count | planner log | REPORT (planner fixed by user decision) |

### 3 Collisions (`n_collisions`, `collision_source`)
| Failure mode | Detected by | First step | Decision |
|---|---|---|---|
| Contact sensor absent, fell back to geometry | `collision_source` != contact | check contact topic bridge | FALLBACK to geometric count, state source; FIX+RERUN if bridge broken |
| STVL decay forgets obstacle behind robot (pilot2 chair_1, R1) | collisions with static objects, `min_clearance_m`, `odom_corrupted_by_contact` | costmap/collision timeline; was a Spin issued while in contact? | Fix already applied in R1 (local-costmap static layer + BackUp before Spin). If it still recurs after the R1 confirmation runs: COUNCIL (contact-aware recovery / axle offset); otherwise REPORT remaining collisions as genuine |
| Camera blind zone below 0.20 m | collisions with 0 depth hits | scan hits at contact time | REPORT, note sensor limit |

### 4 Obstacle avoidance (`avoidance_pct`)
| Failure mode | Detected by | First step | Decision |
|---|---|---|---|
| No obstacle encounters | UNMEASURABLE:NO_EVENTS | check `encounter_distance_m`, world | REPORT as not measurable (empty world) or FIX if trajectory log empty |
| < 3 encounters | LOW_N:<c>/3 | pool across episodes | REPORT pooled with n |
| Below 80 | BELOW_FLOOR:..<80 | list failed encounters, min clearance | REPORT; COUNCIL if cause unclear |
| Encounter counted after odometry corruption | SUSPECT:ODOM_CORRUPTED | `t_odom_corrupt_ep_s` | REPORT with and without |

### 5 Responsiveness (`responsiveness_pct`, `lat_*_ms`)
| Failure mode | Detected by | First step | Decision |
|---|---|---|---|
| Goal events only (no cmd/stop events yet) | LOW_N:<c>/10 or partial | confirm which `lat_*` keys exist | FALLBACK to the goal-latency keys, state event types |
| Wall-clock latency inflated by slow sim | SUSPECT:LOW_RTF | `rtf_true_mean` | REPORT as sim-load result, not hardware latency |
| Latency log missing | UNMEASURABLE:NO_DATA | check relay node | FIX+RERUN |

### 6 ATE (`ate_fixed_rmse_m`)
| Failure mode | Detected by | First step | Decision |
|---|---|---|---|
| Contact-induced odometry corruption (pilot2: 3.10 m vs 0.119 m pre-contact) | SUSPECT:ODOM_CORRUPTED; `odom_corrupted_by_contact` | `contact_odom_yaw_excess_deg`, `t_odom_corrupt_ep_s` | REPORT headline; FALLBACK `ate_fixed_rmse_m_pre_corrupt`; report with/without and median (item 19) |
| Axle 8 cm behind `base_footprint` (item 20) | no automatic flag (FRAME_OFFSET is unrelated: it means the map frame is not at the spawn pose) | in-place spins move GT ~0.10 m while odometry reports 0; see `docs/specs/14` item 20 | REPORT as a documented limitation in every paper table footnote; COUNCIL only if it is shown to change a result's ranking |
| RTAB-Map follows bad odometry, never recovers (item 21) | SUSPECT:ODOM_CORRUPTED + SLAM yaw error persists | SLAM yaw error time series | REPORT as SLAM finding |
| GT pose missing | UNMEASURABLE:GT_MISSING | bag topics | FIX+RERUN |
| Too few poses / SLAM never started | UNMEASURABLE:NO_DATA | RTAB-Map updates | FIX+RERUN if infra, else REPORT |
| Above 0.30 with no flag | BELOW_FLOOR:..>0.30 | trajectory plot vs GT | REPORT; COUNCIL if cause unclear |

### 7 RPE (`rpe_trans_rmse_m_1m`, rot)
| Failure mode | Detected by | First step | Decision |
|---|---|---|---|
| Rotation inflated by one yaw jump | SUSPECT:ODOM_CORRUPTED | per-window RPE | REPORT translation as headline, rot with caveat |
| Path shorter than 1 m window | UNMEASURABLE:NO_DATA | `distance_gt_m` | REPORT |

### 8 Map completeness (`map_completeness_pct`, unaligned)
| Failure mode | Detected by | First step | Decision |
|---|---|---|---|
| No saved map | UNMEASURABLE:MAP_MISSING | check map save step / RTAB-Map db | FIX+RERUN if save failed, else REPORT |
| Textureless walls: no features, sparse map | BELOW_FLOOR:..<60 | `/rtabmap` feature counts, map picture | REPORT (genuine perception limit) |
| Map yaw-rotated after corrupted odometry; unaligned score drops | SUSPECT:ODOM_CORRUPTED | aligned-completeness secondary key | FALLBACK to the aligned key, report both |

### 9 Avoidance trial success (`avoid_trial_success_pct`)
| Failure mode | Detected by | First step | Decision |
|---|---|---|---|
| Scenario world never launched / trial log empty | UNMEASURABLE:NO_DATA | launch log | FIX+RERUN |
| Scenario geometry makes success impossible (narrow gap < robot width) | 0 % everywhere | check SDF gap vs `r_inscribed_m` | FIX world only on dev split; on test, REPORT |
| Dynamic obstacle timing shifted by low RTF | SUSPECT:LOW_RTF | `rtf_true_mean` | REPORT with caveat |

### 10 Navigation success (`nav_success_gt_pct`, `_strict`)
| Failure mode | Detected by | First step | Decision |
|---|---|---|---|
| < 5 goals | LOW_N:<c>/5 | pool | REPORT pooled with n |
| Goal reached by GT but not by controller estimate (localization error) | SUSPECT:NAV_GT_DIVERGENCE | compare `_strict` vs GT key; scripted gt/amcl/slam | REPORT both; localization ablation separates causes |
| AMCL error | `loc_error_mean_m` | scripted AMCL run | REPORT (genuine) |
| Smac DUBIN fails in tight rooms ("no valid path", pilot2 15.4 %) | BELOW_FLOOR:..<50; many aborts | planner log | REPORT (planner fixed by user decision) |
| Goal loop / unreachable goals | many timeouts, same goal repeated | goal log | FIX+RERUN if bug; REPORT if goal truly unreachable (count as failure per 13.1) |
| Contact corruption mid-episode | SUSPECT:ODOM_CORRUPTED | `t_odom_corrupt_ep_s` | REPORT with/without |

### 11 Loop closure (`lc_precision_pct`, `lc_recall_pct`, `lc_f1_pct`)
| Failure mode | Detected by | First step | Decision |
|---|---|---|---|
| RTAB-Map never accepts a closure | UNMEASURABLE:NO_EVENTS (precision); LOW_N:<c>/5 | `lc_accepted`; check revisits exist and textures | REPORT "not measurable under these conditions" plus recall 0 % if revisits exist |
| Too few GT revisits | LOW_N:<c>/3 | pool across episodes | REPORT pooled with n |
| Textureless walls / symmetric_hall aliasing: wrong closures | BELOW_FLOOR:..<50 | `lc_reg_*` errors, same-pose vs loose precision | REPORT (symmetric_hall is meant to measure this) |
| Direction/convention error in truth (fixed 2026-10-22, `loop_to_ref`) | SUSPECT:LC_ROT_BIAS | rot error mean sign | FIX+RERUN offline recompute from bag |
| Corrupted odometry makes closure transforms wrong | SUSPECT:ODOM_CORRUPTED | compare pre-corruption closures | REPORT with/without |
| Image drops | UNMEASURABLE:INVALID_EPISODE | `img_drop_pct` | FIX+RERUN once |

### 12 Path length ratio (`path_length_ratio_mean`)
| Failure mode | Detected by | First step | Decision |
|---|---|---|---|
| Few successful goals (pilot2 n = 4) | LOW_N:<c>/5 | pool | REPORT pooled with n |
| No successful goals | UNMEASURABLE:NO_EVENTS | none | REPORT as not measurable |
| Ratio absurd (> 10) | SUSPECT:RANGE | per-goal list | COUNCIL |

### 13 Method comparison
ON HOLD (user decision). No failure modes tracked until reopened.

### 14 Cleaning efficiency (`cleaning_efficiency`), secondary
| Failure mode | Detected by | First step | Decision |
|---|---|---|---|
| Low because the explorer does not clean | low value, healthy coverage | none | REPORT as secondary, state design limit |
| Coverage denominator missing | UNMEASURABLE:GT_MISSING | grid | FIX+RERUN offline |

### Key extras
| Metric | Failure mode | Detected by | Decision |
|---|---|---|---|
| `rtf_true_mean` | Low RTF (pilot2 0.29); Gazebo `/stats` RTF is wrong (1.00 vs true 0.49) | SUSPECT:LOW_RTF | REPORT; never use `/stats` |
| `odom_corrupted_by_contact` | stratifier | flag = 1 | never an exclusion |
| `plan_latency_ms_mean` | inflated by low RTF | SUSPECT:LOW_RTF | REPORT with RTF |
| `loc_error_mean_m` | AMCL scripted run not done | UNMEASURABLE:NO_DATA | run R3, else report not measured |
| `min_clearance_m` | out of physical range | SUSPECT:RANGE | COUNCIL |

## 2. Decision flow

1. Read the health code. `OK` or `NA`: done.
2. Is it an infrastructure fault (DDS image drops, crashed node, missing bag, failed map save)? Yes: FIX+RERUN once with the same seed. Both attempts are reported.
3. Artefact test, ask both:
   - Would this happen on the real robot with the same software? If yes, it is a genuine result: REPORT.
   - Is it caused by our measurement (wrong frame, convention, GT, sensor we added only in sim) or by the system under test? Measurement: fix the code, recompute offline from the bag, no rerun needed. System: REPORT.
4. If a secondary key already computed separates the cause (`_pre_corrupt`, `_strict`, aligned map), use it as a FALLBACK next to the headline, never instead of it.
5. If steps 2-4 do not settle it: COUNCIL (section 5).

**Rerun policy:** only infrastructure faults, once, same seed, both attempts reported. Never rerun to get a better number. Never drop an episode for a bad value. Health flags never exclude episodes (13.3 and 13.5b).

**Frozen once the test split starts:** metric definitions, tolerances and floors, validity gates, world and seed lists, campaign files, planner and controller stack, health codes and floors. Allowed: bug fixes in measurement code only if the fix and its reason are recorded in the 13.6 change log and all affected episodes are recomputed (not only the favourable ones). Stack changes after the first test episode: not allowed; report the limitation instead.

## 3. Metric unmeasurable across the campaign

- Never drop it silently. Keep the row in every table with status `not measurable under these conditions`, the reason code, and the fallback key.
- Example: no loop closures ever accepted. Report `lc_accepted = 0`, recall 0 % over `lc_revisits` revisits, precision undefined (NO_EVENTS), with the textureless-wall or RTAB-Map explanation if diagnosed.
- LOW_N: pool events across episodes, report the pooled n, and widen the CI statement accordingly. Do not claim per-world results with n below the minimum.
- Unmeasurable because of our fault (GT_MISSING, MAP_MISSING): fix and recompute; if impossible, say so in the limitations section.

## 4. Paper wording templates

**Bad result.** "On the test split, <metric> was <value> (95 % CI <lo>-<hi>, n = <episodes> episodes), below the pre-registered diagnostic floor of <floor>. We investigated the cause (<cause>) and consider it a property of the system, not of the measurement. We report it unchanged."

**Unmeasurable metric.** "<Metric> could not be measured under these conditions: <reason> (<code>). Across <N> episodes there were <k> qualifying events (minimum <min>). We therefore report <fallback key> as a substitute and do not draw conclusions about <metric>."

**Suspect episode subset.** "<k> of <N> episodes were flagged <code> (<definition>). Flagged episodes are included in the headline. We additionally report the metric without them (<value>) and the median over all episodes (<value>). The flag is a stratifier, not an exclusion."

**Simulation-only limitations.** "All results come from Gazebo simulation at a real-time factor of about <rtf>. Wheel slip, depth-camera noise, motor torque and contact dynamics are simulated approximations and the robot axle offset (8 cm behind base_footprint) is modelled as built. Latency figures are wall-clock under simulation load and do not transfer to hardware. Results should be read as a comparison of behaviour under identical simulated conditions, not as predictions of real-world performance."

## 5. Escalation

**Sonnet-only council** (`~/.claude/skills/llm-council`): judgment calls where the evidence is in the data but the interpretation is not: artefact versus genuine ambiguous cases, SUSPECT:RANGE values, whether a flagged subset changes the conclusion, whether an axle-offset effect changes method ordering, which fallback key to headline.

**User:** anything that changes the frozen set (definitions, floors, split, seeds, planner or stack changes), any exclusion or deviation from the preregistration, hardware or time decisions (rerun budgets, machine choice), reopening the on-hold method comparison (#13), and anything the council cannot resolve or that affects a claim in the paper abstract.


## Failure modes found in the 2026-10-25 campaign (details: `EVALUATION_FINDINGS_2026-10-25.md`)

| Symptom | Diagnosis | Action |
|---|---|---|
| nav_success_gt low; nav2.log full of `"Start occupied"`; error 205 in goal_events | Planner start (= AMCL estimate) in a wall's inscribed zone: ~36 % localization error, ~60 % robot truly within footprint of a wall, no recovery moves it | Report as measured. Check with `--localization gt` (dev). Candidate: START_OCCUPIED recovery (nav v2), AMCL likelihood settings |
| Exploration robot never moves, `No free cell with 0.30 m clearance` then `No eligible frontier` ~1000x, stuck at 180 s | First map is a sliver (robot faces a wall after the bootstrap spin); `_snap_goal` counts unknown as blocked; no fallback | Genuine, not infra: report, do not rerun. Candidate: explorer stall fallback |
| AMCL stuck 0.5 m / 10 deg off for minutes (maze) | Loose sigma_hit/z_rand, recovery off, 69 deg FOV, flat walls | Report; candidate AMCL settings |
| LC precision BAD with rotation errors 7-15 deg | GT taken at Info arrival (lag 0.1-0.4 s) | Report as lower bound; offline recompute from node stamps |
| G1_clock fails on slot 0 only after a network change | Stale `ros2` daemon for domain 0 | `ros2 daemon stop` (or kill the daemon by PID), rerun once (infra) |
| MPPI "control loop missed" > 5/min, jittery cmd_vel | CPU oversubscribed (3 sims on 16 threads) | Use --parallel 2 for SLAM workloads |
