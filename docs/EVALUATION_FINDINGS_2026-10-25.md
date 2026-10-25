# Evaluation findings, 2026-10-25 (victus, reduced 4-hour test campaign)

**Audience:** the authors writing the paper, and whoever runs the next evaluation.
**Sources:** `docs/EXECUTION_LOG.md` (dated entries with the raw numbers), the campaign reports in `~/eval_runs/quick_*/report/`, `results/RESULTS_SO_FAR.md`, and 12 independent read-only audits run by Sonnet subagents. Each audit re-derived its numbers from the raw CSVs, logs and rosbags.
**Status of the code:** frozen at commit `92c7757`, plus the logged deviations (goal-start tolerance, extra navigation seeds 103/104). Nothing below was "fixed" in the measured v1 system. Section 6 lists the fixes as candidates for the next campaign.

---

## 1. What was measured

| Campaign | Episodes | Stack | Notes |
|---|---|---|---|
| quick_responsiveness | 4 (2 valid) | office, bare + loaded | Bare is invalid by construction (RTAB-Map gate; user decision to keep) |
| quick_avoidance | 6 | Nav2 + AMCL on GT map | 3 concurrent sims |
| quick_exploration_noise | 9 | RTAB-Map + Nav2 + frontier explorer, odometry noise on | office and multi_room_loop at 3 slots (RTF ~0.74); maze_dead_ends at 2 slots |
| quick_navigation | 12 (seeds 101-104) | **Nav2 + AMCL on a ground-truth map, not the RTAB-Map pipeline** | 2 slots, RTF 1.0 |

- **Validity:** 29 of 31 test episodes are valid; the 2 invalid ones are the bare responsiveness runs.
- **Real-time factor:** `rtf_true_mean` ranged 0.729-1.000, and no episode was below 0.7.
- **Spot-checks:** all 3 agree with the raw CSVs within 2%.

## 2. Headline numbers and how to read them

| # | Metric | Value | Read it as |
|---|---|---|---|
| 1 | Coverage explored | 61.4 % [18.5, 88.0] | Faithful. The 2 stuck maze episodes pull it down ~20 pp; the 7 moving runs average 78.8 %. The free-only definition costs another 2-6 pp (wall-rim cells). |
| 8 | Map completeness | 47.7 % | Faithful. The 1-cell (0.05 m) wall tolerance is strict (+5-8 pp at 2 cells). Office 103 is genuine SLAM yaw drift (~8 deg). |
| 6/7 | ATE / RPE (SLAM) | 0.572 m / 0.250 m per 1 m | Genuine drift plus contact-corrupted odometry (4 of 9). Uncorrupted runs also exceed the 0.30 m floor. |
| 11 | Loop-closure precision / recall | 36.8 % / 28.2 % | **Lower bound.** GT is attached at RTAB-Map Info arrival, not at the node stamp (0.1-0.4 s lag, 1-21 deg yaw error vs a 5 deg tolerance). A diagnostic time shift gives 52-77 %. |
| 10 | Navigation success, GT-verified | 23.4 % [2.8, 46.7] (178 goals) | Nav2 + AMCL on a GT map. Nav2 itself reports ~50 %. Section 3 covers the failure mode. |
| 12 | Path length ratio | 1.21 | Successful goals only (n=9 episodes). |
| 9 | Avoidance trial success | 66.7 % [16.7, 100.0], n=6 | u_trap 3/3, dynamic_sudden 1/3. The report shows "no data" because of a key bug in `make_report.py:35`, so this value comes from the per-episode `trial_success`. |
| 5 | Responsiveness | Step response 160-172 ms (cmd -> 50 % of the commanded speed), stop 250-270 ms, loaded stack, n=2 | Mostly the configured acceleration ramp plus ~45 ms of pipeline delay. The goal-to-motion percentages (41 %, 74 %) include planning and stuck goals, so they are **not** controller responsiveness. |
| 3 | Collisions | 1.8 / 1.9 / 0.2 per episode (explore / nav / avoid) | Contact **bursts** split by more than 0.5 s, not distinct impacts. One jam counts as 3-7. Report contact time and unique obstacles as well. |
| A8 | "Planning latency" | Median 10-30 ms | It is "time to first successful plan". The 5-9 s means come from goals stuck on START_OCCUPIED or no-valid-path. |
| A6 | Recoveries | ~82 (explore) / ~148 (nav) per episode | Real BT counters, but 70-80 % are instant costmap clears. |
| A14 | AMCL error | 0.318 m | Section 3. |

## 3. Navigation failure mode (the most important finding)

- **Dominant failure is START_OCCUPIED (Nav2 error 205), not NO_VALID_PATH (208).** 1242 planner "Start occupied" lines across the 12 episodes. The planner start is always the AMCL estimate.
  - About 36 % of events are localization-caused: the estimate sits in a wall's inscribed zone while the true pose is free. This is dominant in office 101-103.
  - About 60 % are the robot genuinely ending up within footprint range of a wall. v1 has no recovery that moves it away: costmap clears and Spin do not help, because the static map still holds the wall.
  - About 4 % are unexplained by map walls.
- **Ground-truth localization removes most of it.** On the dev world apartment, seed 1, `--localization gt` reached 95 % GT-verified success (19 of 20) against 31.6 % with AMCL, and Nav2's own verdict matched ground truth. This is n=1 and dev, but it shows the planner can do the task when localization is right.
- **Why AMCL is poor here** (audit of the scan and AMCL settings):
  1. `sigma_hit` 0.2 and `z_rand` 0.4 are too loose for a noise-free depth scan.
  2. Recovery is off (`recovery_alpha_*` = 0), so a wrong mode is never corrected. In the maze, the filter sits 0.6 m / 10-13 deg off for hundreds of seconds while the scan contradicts it.
  3. **The depth camera's horizontal FOV is 69.4 deg, not 86 deg.** `_gazebo.xacro:172` uses the colour HFOV, so y and yaw are weakly observable in corridors.
  4. Maze geometry: long parallel walls and flat end walls.
  5. The 8 cm axle offset (0.06-0.11 m unmodelled shift per in-place spin) and 2-4 % odometry under-rotation.
  - Ruled out: the initial pose (exact) and the scan frame (matches GT to 1.2 cm).
- **Nav2 vs GT divergence (e.g. two_rooms_door 80-95 % vs 40-65 %)** is real AMCL error under identical 0.30 m tolerances. It is not a timing or frame bug, and the goal lists are unbiased.

## 4. Exploration failure mode in maze_dead_ends

- Seeds 101 and 103 never moved. The cause is **not** narrow corridors: they are 1.0-1.1 m wide.
- **What happened:** the bootstrap spin stops after ~0.8 rad when the first map arrives, so the robot faces a wall 0.5-0.75 m away and the first map is a 0.5-0.7 m² sliver.
- **Why no goal:** `_snap_goal` (`exploration_manager.py` ~624-645) counts unknown cells as blocked, so no cell reaches the 0.30 m clearance and the only frontier is blacklisted.
- **Why it never recovers:** there is no fallback. The RECOVERING state only increments a counter, so the robot waits until the harness stuck rule fires at 180 s.
- **Classification:** deterministic and spawn-pose dependent, not an infrastructure fault, and not rerun.

## 5. Measurement and reporting issues (none change the frozen values; state them in the paper)

| Issue | Effect | Where |
|---|---|---|
| Loop-closure GT at message arrival | LC precision biased down (lower bound) | `recorder_node.py:380-386` |
| `rates.csv` counts by recorder arrival; slow callbacks still serialised | `topic_ok_pct_*` understated 3-6 pp in loaded runs (`img_drop_pct` unaffected) | `recorder_node.py` default callback group, `on_wall`, `on_map` |
| Arrival-stamped cmd_vel/goal/plan/contact rows | p95 0.06-0.09 s late in loaded runs; small latency biases | `recorder_node.py` `row(t=None)` |
| Metric-9 pooled row empty | Report shows "no data" | `make_report.py:35`, `status_update()` |
| Health flags misapplied to campaigns | ~72 spurious UNMEASURABLE, BAD coverage in loaded responsiveness, nav-success flags on frontier and single-goal runs, FRAME_OFFSET on AMCL start convergence | `health.py` `_applicable` |
| Flag precedence hides BAD | 16 of 59 floor breaches shown as SUSPECT/LOW_N | `health.py:128`, `make_report.health_section` |
| FRAME_OFFSET label | Fires on late map drift (alignment shift), not a start offset | `health.py:95-100` |
| LC_ROT_BIAS window never fires | Medians 7-13 deg lie outside (5, 7] | `health.py:111-115` |
| Alignment yaw search clipped at ±5 deg | Aligned completeness diagnostic understated | `coverage.py:107` |
| `encounter_distance_m` read as `d_enc_m` | Latent; same default today | `safety.py:298` |
| Code defaults differ from yaml (0.5 vs 0.10/0.20) | None in these runs (yaml snapshot used) | `health.py:13-14` |
| 3-slot runs | Control-loop misses 6-17/min (vs <2), jittery commands; no outcome effect detectable at n=6 | office and multi_room_loop exploration, avoidance |

**Paper wording to use:**
- **Applicability:** coverage, completeness and LC apply to SLAM exploration only; navigation success and path ratio to scripted navigation only; trial_success to avoidance only; the step response to the responsiveness runs.
- **Flags:** health flags are per-episode diagnostics, never exclusions.
- **Navigation:** "the navigation campaign measures Nav2 + AMCL on a ground-truth map".
- **Sensor:** the camera FOV is 69 deg.

## 6. Candidate fixes for the next campaign (not applied; each changes the measured system or the metric pipeline, so each needs a decision, a pre-registration row and fresh runs)

1. **Recorder:**
   - Stamp LC nodes, cmd_vel (TwistStamped), contacts and goals with header stamps.
   - Move `on_wall` and `on_map` into their own callback groups.
   - Count rates by header stamp.
   - A loop-closure recomputation from node stamps stored in `rtabmap.db` is possible offline, without new runs.
2. **Metrics/report:**
   - Fix the metric-9 key.
   - Make the health applicability campaign-aware.
   - List floor breaches independently of precedence.
   - Relabel A8 and report its median.
   - Split goal-to-motion from step response.
   - Report collision contact time.
   - Fix `d_enc_m`.
   - Widen the alignment search.
3. **Localization (AMCL):** `sigma_hit` ~0.05-0.1, `z_hit` ~0.9 / `z_rand` ~0.05-0.1, small `recovery_alpha_*`.
4. **Robot model (user decision):**
   - Set the depth HFOV to 86 deg, or document 69 deg.
   - Treat the axle offset in odometry/TF.
5. **Navigation BT:** a START_OCCUPIED recovery that actually moves the robot. **Tested as "nav v2" (BackUp 0.15 m + Spin, plus AMCL 1000-3000 particles and 0.10 m / 0.10 rad updates) on a dev A/B: it FAILED the pre-fixed rule.** Pooled GT success went from 16 % (4/25) to 31 % (9/29), but START_OCCUPIED was not reduced (247 vs 260) and seed 2 was worse (1 vs 3 GT goals). BackUp mostly aborts with "Collision Ahead" when the footprint already touches the wall. Not run on the test split. A recovery that works needs a different mechanism, e.g. a collision-check-free short reverse, or relocalization, decided and pre-registered separately.
6. **Explorer:**
   - A stall fallback: after N failed snaps, rotate 360 deg or drive briefly.
   - In `_snap_goal`, measure clearance from occupied cells only (an explorer contract decision).
7. **Infrastructure:** 2 parallel slots maximum on this 16-thread machine for SLAM workloads; restart the `ros2` daemon after any network change (see `REMOTE_MACHINE.md`).
