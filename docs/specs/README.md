# Evaluation Implementation Specs — INDEX

Audience: Claude agents (and humans) who will implement the measurement system. These specs say **exactly what to build, where, with which names, formulas and thresholds**, so that two agents implementing the same spec produce the same numbers. If something here is ambiguous, that is a spec bug: fix the spec first (record the decision in the "Decisions log" at the bottom of the relevant file), then code.

Companion docs: `docs/METRICS_TO_BE_MEASURED.md` (what the metrics mean, status, tiers), `docs/HANDOFF.md` (environment, known bugs). This folder is the *how*.

## Reading order and dependencies

| File | Contents | Metrics covered | Depends on |
|---|---|---|---|
| `00_conventions.md` | Rules every file obeys: sim time, frames, units, directories, naming, CSV/JSON schemas, the new package `vacuum_eval`, tooling | all | — |
| `01_prerequisites_and_fixes.md` | Required fixes before any number is trustworthy: ground-truth bridge, odometry noise path, Nav2 velocity loop, exploration bugs, goal-event topic, sim fixes | enables all | 00 |
| `02_run_harness.md` | Episode definition, run launcher, recorder node, run directory contents, batching, seeds, statistics, compute metrics | #2, A7, A11, A12, A13 | 00, 01 |
| `03_ground_truth_grid_coverage.md` | World SDF to ground-truth grid, swept area, coverage, map completeness | #1, #8, A1, A2, A3 | 00, 01, 02 |
| `04_trajectory_accuracy.md` | ATE, RPE, SLAM drift, AMCL error | #6, #7, A10, A14 | 00, 01, 02 |
| `05_navigation_metrics.md` | Nav success, path length ratio, planning time, recoveries, smoothness, energy | #10, #12, A4, A6, A8, A9 | 00, 01, 02, 03 |
| `06_safety_collisions_avoidance.md` | Contact sensor, collisions, encounters, avoidance %, trial success, clearance, dynamic obstacles | #3, #4, #9, A5 | 00–03, 09 |
| `07_responsiveness.md` | Latency tests and the responsiveness percentage | #5 | 00, 02 |
| `08_loop_closure.md` | Loop closure counting, precision, recall | #11 | 00, 01, 02 |
| `09_worlds.md` | Corridor sealing, new worlds, SDF rules so the rasteriser can read them, dynamic obstacles | enables #1, #3, #4, #8, #9, #11 | 00 |
| `10_cleaning_efficiency.md` | Swath model and efficiency formulas | #14, A2, A3 | 03 |
| `11_baselines_on_hold.md` | **ON HOLD** plug-in interface for coverage methods (#13) | #13 | 02 |
| `12_acceptance_tests.md` | Per-metric test procedure and expected values so each implementation can be proven right | all | all |

Suggested implementation order: 00 → 01 → 09 (corridor seal + two small worlds) → 02 → 03 → 05 → 04 → 08 → 06 → 07 → 10 → 12. Item 11 is parked.

## Metric → spec map

| # | Metric | Spec file | Output key in `summary.json` |
|---|---|---|---|
| 1 | Average coverage | 03 (+10) | `coverage_explored_pct`, `coverage_cleaned_pct` |
| 2 | Average steps per episode | 02 | `n_cmd_ticks`, `n_goals`, `n_recoveries`, `episode_sim_sec` |
| 3 | Total collisions | 06 | `n_collisions` |
| 4 | % obstacle avoidance | 06 | `avoidance_pct` |
| 5 | % responsiveness | 07 | `responsiveness_pct` |
| 6 | ATE | 04 | `ate_fixed_rmse_m`, `ate_aligned_rmse_m` |
| 7 | RPE | 04 | `rpe_trans_rmse_m_1m`, `rpe_rot_rmse_deg_1m` |
| 8 | Map completeness % | 03 | `map_completeness_pct` |
| 9 | Obstacle avoidance success rate | 06 | `avoid_trial_success_pct` |
| 10 | Navigation success rate | 05 | `nav_success_pct` |
| 11 | Loop closure success rate | 08 | `lc_precision_pct`, `lc_recall_pct` |
| 12 | Path length ratio | 05 | `path_length_ratio_mean` |
| 13 | Coverage method comparison | 11 (on hold) | — |
| 14 | Cleaning efficiency | 10 | `cleaning_efficiency`, plus components |
| A1–A15 | Additional metrics | see "A-metric map" below | see each spec |

A-metric map: A1 coverage-vs-time, A2 overlap, A3 missed area → 03/10. A4 distance/energy, A6 recoveries, A8 planning time, A9 smoothness → 05. A5 clearance → 06. A7 stuck/timeouts, A11 CPU/RAM, A12 real-time factor, A13 repeatability → 02. A10 drift, A14 AMCL error → 04. A15 noise robustness → 01 + 02 (run the same suite with `odom_noise:=true`).

## Definition of done (applies to every spec)

An implementation of a spec is done only when: (1) code is in the location the spec names, (2) the spec's acceptance test in `12_acceptance_tests.md` passes and the observed values are pasted into that file under "Observed", (3) the metric appears with the exact key in `summary.json` for a real run, (4) the spec's "Decisions log" is updated if reality forced a change, (5) nothing was claimed that was not run.

## Runtime facts to confirm in the first hour (spec authors could not verify these by reading)

| # | Question | Where it matters | How |
|---|---|---|---|
| 1 | ~~Does `ros_gz_bridge` keep entity names in `Pose_V` → `TFMessage`?~~ **Answered: no** → OdometryPublisher plugin used (done, spec 01 §1.1) | 01 | — |
| 2 | ~~Rate of `/ground_truth/odom`~~ **29.3 Hz sim time** (done) | 07 | — |
| 3 | Exact collision names after URDF lumping; does the bridge support `gz.msgs.Contacts` | 06 | `gz sdf -p`, bridge launch log |
| 4 | Does `/rtabmap/info` publish, at what rate | 08 | `ros2 topic hz --use-sim-time /rtabmap/info` |
| 5 | RTAB-Map grid `cell size` and `MaxObstacleHeight` | 03 | `rtabmap.yaml` and the live `/rtabmap/map` info |
| 6 | Does headless Gazebo render the depth camera on this WSL | 01 §1.7 | launch with `headless:=true`, check depth topic rate |
| 7 | Which cmd topic actually moves the robot under Nav2 (stamped vs unstamped) | 01 §1.4 | publish test commands |
| 8 | `spawner --param-file` accepted for `enable_odom_tf:=false` | 01 §1.3 | launch in `odom_mode:=eval` |

Already verified (2026-10-20, by running): sim launches in WSL; both controllers active; robot moves from `/cmd_vel`; `/odom` and camera topics are exactly 30 Hz in sim time but ~10 Hz in wall time because the real-time factor dips; `/world/apartment_world/pose/info` carries `vacuum_robot` and all static models by name; `/odom` x equals ground-truth x to 4 decimals on straight lines, but odometry yaw under-reports rotation by ~22 % on arcs (real wheel-odometry error even with noise off).

## Decisions log (global)

| Date | Decision | Why |
|---|---|---|
| 2026-10-20 | Online code records **raw data only**; all metric math is **offline** in `compute_metrics` | Reproducible, re-runnable with changed definitions, no metric logic hidden in live nodes |
| 2026-10-20 | ATE/RPE implemented in numpy by us, not via `evo` | `evo` is not installed; fewer dependencies; `evo` is used only as an optional cross-check |
| 2026-10-20 | Corridor world must be sealed; worlds are hand-written SDF box/cylinder worlds, not Fuel downloads | The rasteriser needs exact geometry |
| 2026-10-20 | #13 baselines on hold (user) | User decision |
| 2026-10-20 | Responsiveness deadline 0.5 s; swath 0.25 m (placeholder until real brush width known) | User accepted / assumption |

## Implementation status (2026-10-20, end of first implementation pass)

Code lives in `Navigation/Simulation/vacuum_ws/src/vacuum_eval/` (+ edits listed below). `python3 -m pytest test -q` in that folder: 87 tests pass.

| Spec | Status | Evidence |
|---|---|---|
| 00 conventions, `vacuum_eval` package | done | package builds |
| 01 ground truth (odometry plugin), odom noise node, Nav2 velocity path, exploration-manager fixes, delete_db | done, run | smoke episodes |
| 01 extra findings fixed during runs | done | see "Fixes found while running" below |
| 02 recorder, `run_episode`, `run_batch`, `compute_metrics`, `aggregate` | done; `frontier`, `scripted_goals` (gt-map + AMCL) and `responsiveness` (bare) run end to end. Not yet run live: `responsiveness --stack loaded`, `--nav-map slam`, `run_batch`, `aggregate` on real data | `~/eval_runs/smoke*/` |
| 03 GT grid, coverage, completeness | done, run | smoke summaries |
| 04 ATE/RPE/drift/AMCL error | done, run | smoke summaries |
| 05 navigation metrics, goal lists | done, run | smoke4 |
| 06 safety | module done; **contact sensors do not publish** (see below) so geometry fallback is the live source; avoid_* scenarios not run live | |
| 07 responsiveness | done, run (bare): cmd→motion 155 ms mean, stop 245 ms, 40/40 within 0.5 s | smoke3 |
| 08 loop closure | module done; no loop-closure world run yet (`multi_room_loop`, `loop_tour`) | |
| 09 worlds | 9 evaluation worlds + 8 avoid_* worlds created and rasterised; only apartment run live | |
| 10 cleaning efficiency | done, run | smoke summaries |
| 11 baselines | on hold (user) | |
| 12 acceptance tests | unit tests T-0xx..T-1xx implemented; runtime ones partly observed | |

### Fixes found while running (all applied)
1. `vacuum_description/CMakeLists.txt` installed a non-existent `rviz/` dir (build failed).
2. CycloneDDS refused to start (1 MB socket-buffer minimum vs WSL 208 KB).
3. `ros_gz_bridge` drops entity names in `Pose_V` → ground truth via `gz-sim-odometry-publisher-system` plugin.
4. Nav2 commands never reached the robot: `diff_drive_controller` only subscribes to the stamped `/diff_drive_controller/cmd_vel`; added `cmd_vel_relay_nav` for `/cmd_vel_smoothed`.
5. Velocity smoother consumed its own output.
6. RTAB-Map published `/map`, `/info`... but the stack uses `/rtabmap/*` → remapped.
7. RTAB-Map publishes no map until the robot moves → bootstrap spin in the exploration manager.
8. Frontier goals unplannable → goal snapping to free cells with clearance.
9. `depthimage_to_laserscan` subscribes `/depth` and `/depth_camera_info` in this Jazzy: the old remaps (`image`, `camera_info`) left `/scan_from_depth` **empty in every earlier run** (no obstacle layer, no AMCL).
10. `navigate.xml` used a `<Wait error_code_id=...>` port that does not exist → `bt_navigator` failed to activate.
11. Recorder: `events.csv` had no timestamps and was truncated; `dyn_obstacles.csv` column renamed `name`; scripted `started` events mislabelled.
12. `compute_metrics`: `<share>` path in worlds.yaml not resolved; scenario worlds now merged.
13. Navigation metrics: `accepted` status is rarely seen → `executing` accepted as fallback.

### Performance decisions
Physics step 1 ms → 4 ms (all worlds); `/camera/depth/points` removed from the default bridge; `headless:=true` = gz server without GUI (`-r -s`); `--headless-rendering` segfaults on this WSL (no EGL GPU). Real-time factor with the full stack: 0.25 → ~0.45 (headless). A 20-min-sim episode still takes roughly 45 min wall; budget accordingly.

### Open problems
- ~~Contact sensors~~ **Resolved 2026-10-21**: Gazebo only creates contact publishers for models present when the world loads (verified with a minimal SDF model spawned at runtime vs in the world file). `sim.launch.py` now bakes the robot into the world at launch (`embed_robot:=true`, default); `collision_source` is `contact` and the first live run recorded real contacts with `coffee_table`. Note one contact generates ~1000 raw rows (many contact points per message); `collision_events` debounces them.
- **Nav2 success is low** (apartment: ~10–40 % of goals; many "no valid path"/"Start occupied"); needs costmap/planner tuning, which is a method result not a measurement bug.
- **AMCL error** ~0.6 m mean on the GT map (camera-derived scan), so Nav2 "succeeds" at goals the robot is not at (`nav_success_gt_pct` 0 % in the first scripted run).
- **Robot model**: wheel axle is 8 cm behind `base_footprint` but the controller assumes they coincide; in-place rotation under-reports yaw by ~5 %.
- RTAB-Map with external odometry does not correct drift without loop closures (SLAM ATE == odometry ATE in the noisy smoke run).


### Update 2026-10-21 (tuning pass after web research)
Applied: rug collision removed (visual only); Nav2 footprint = 0.30 x 0.25 m polygon (was radius 0.18 -> 0.16 -> polygon), inflation 0.28 / scaling 5; `cmd_vel_timeout` 0.5 -> 1.5 s; `wheel_separation_multiplier` 0.945 (odom yaw was 0.945 x true); brick/floor textures (512 px, `worlds/textures/`, PBR albedo) on wall_* and ground_plane for loop-closure features; contact sensors working (see above); `vacuum_eval.diagnose` tool added. Planner left as SmacPlannerHybrid on the user's instruction.
Same-seed apartment episode, 150 s sim, noise off: Nav2 goal success 14 % -> 62.5 % (ground-truth success 25 %), idle 42 % -> 27 %. Not yet verified: whether the yaw calibration and textures changed loop closures (still 0 accepted), RTF stayed ~0.35.
