# Metrics To Be Measured (simulation)

Audience: Claude agents (and humans) picking up the evaluation work. Read this together with `docs/HANDOFF.md` (environment, known bugs) before writing any code.

**Goal:** measure the metrics below for the Swachh cleaning robot in simulation (ROS 2 Jazzy + Gazebo Harmonic, workspace `Navigation/Simulation/vacuum_ws`), per run, into CSV files that can feed the Q1 paper.

**Status legend:** `Exists` = some code already logs it. `Partial` = code exists but is wrong or incomplete. `Missing` = nothing exists. Everything here comes from reading code plus a few checks (see section 9); **no simulation has been run yet**, so re-verify at runtime.

---

> **Implementation specs:** the exact implementation of every metric below is specified in `docs/specs/` (start at `docs/specs/README.md`). This file says *what* and *why*; the specs say *how*, with formulas, file names and acceptance tests.

## 1. Definitions used by every metric

| Term | Definition |
|---|---|
| **Episode** | One run from robot spawn until exploration reports FINISHED, the goal list ends, or a sim-time timeout (default 20 min). There is no episode concept in the code today; the run harness (section 5) must create it. |
| **Step** | Ambiguous, so report all three: one `/cmd_vel` control tick (20 Hz), one navigation goal, one recovery behaviour. |
| **Ground truth (GT)** | The robot's true pose from Gazebo and the true floor plan from the world SDF. Never use wheel `/odom` as GT. |
| **GT free area** | Reachable free floor area of a world, from rasterising SDF walls/furniture into a grid, then flood-filling from the spawn point. |
| **Swept area** | Cells under the vacuum swath along the GT trajectory. Swath width is an assumption of 0.25 m until the user confirms (vacuum mount in the URDF is a placeholder). |
| **Seed** | Gazebo is not seeded. Randomise spawn pose and odometry-noise seed per run; plain repetition does not give independent samples. |

---

## 2. Master table

Tier = order of work. Tier 1 needs almost nothing new, Tier 2 needs the GT fix, Tier 3 needs new sensors/worlds, Tier 4 needs definitions or large new code.

| # | Metric | Tier | Status | Meaning | How to measure | Inputs / needs | Unit / direction |
|---|---|---|---|---|---|---|---|
| 1 | **Average coverage** | 1 | Partial | Share of the true free floor the robot has covered/explored | Two flavours, report both. (a) Explored: SLAM map free cells that lie in GT free area ÷ GT free area. (b) Cleaned: swept area ÷ GT free area (see #14). Report final value, and mean over runs. Existing `coverage_pct` is `free/(free+unknown)` of the live map, its denominator grows with the map, so it is misleading and must not be used as the headline number | GT grid per world, `/rtabmap/map` (or saved map), GT pose | % ↑ |
| 2 | **Average steps per episode** | 1 | Missing | How long an episode is | Count `/cmd_vel` ticks, goals sent, recoveries per episode; also report episode sim-time. Average over runs | Episode harness, `/cmd_vel`, Nav2 action status | count ↓ |
| 3 | **Total collisions** | 3 | Missing | Number of contacts with walls/obstacles | Add a Gazebo `<sensor type="contact">` on the chassis (needs a `<collision>` on that link), bridge `gz.msgs.Contacts` to `ros_gz_interfaces/Contacts`, count debounced distinct events, ignore floor/wheel contacts. Cross-check geometrically: GT trajectory footprint vs SDF obstacle boxes | URDF edit (`_gazebo.xacro`), `gz_bridge.yaml`, contact system (already loaded in every world; plugin lib installed) | count ↓ |
| 4 | **% obstacle avoidance** | 3 | Missing | Share of obstacle encounters passed without contact | Encounter = robot centre within 0.5 m of an obstacle (from GT pose + SDF geometry). % = encounters with zero contact ÷ all encounters | #3 collisions, GT pose, obstacle list | % ↑ |
| 5 | **% responsiveness of system** | 3 | Missing | Share of events handled within a deadline | Events: cmd→motion (`/cmd_vel` to 90 % of commanded velocity on odom), goal→first motion, obstacle-appears→reaction (stop/replan). % = events under threshold (default 0.5 s, user may change). All timestamps must be sim time. Existing latency code mixes sim time with a monotonic wall clock, do not reuse it | New timing node, `/clock`, Nav2 actions | % ↑ |
| 6 | **Absolute trajectory error (ATE)** | 2 | Partial | Global drift of the estimated trajectory | RMSE of translation error between estimated pose (`map→base_footprint` from TF) and GT pose, rigid alignment (SE3) only, no scale correction. Run with odometry noise ON, else it is trivially tiny. Existing `evaluate_trajectory.py` compares `/odom` with `/rtabmap/odom` (topic does not exist) and uses `--correct_scale`, so it needs a rewrite | GT pose (needs bridge fix), `evo` (not installed), noisy odom wired into RTAB-Map | m ↓ |
| 7 | **Relative pose error (RPE)** | 2 | Partial | Local accuracy per unit motion | Same pose pairs as #6; error in relative motion over fixed windows (1 m and 5 s) | as #6 | m, deg ↓ |
| 8 | **Map completeness %** | 1 | Missing | How correct and complete the built map is | IoU of free and occupied cells of the saved SLAM map vs the GT grid (align first), plus fraction of true wall cells found. #1 asks "how much was seen", #8 asks "how right is the map" | GT grid, saved map (`map_saver_cli`), `scikit-image`/numpy | % ↑ |
| 9 | **Obstacle avoidance success rate** | 3 | Missing | Per-trial success of reaching a goal with an obstacle in the way | Trial = start→goal run with a placed obstacle (static first, then dynamic). Success = goal reached and zero collisions. Rate = successes ÷ trials. #4 is per encounter, #9 is per trial | #3, test worlds with placed/moving obstacles, goal lists | % ↑ |
| 10 | **Navigation success rate** | 1 | Partial | Goals reached ÷ goals sent | Count Nav2 `NavigateToPose` result codes. `exploration_manager` counts succeeded/failed but timeouts and oscillation cancels count as failures and no reason is stored. Add a failure-reason column. Fix the oscillation bug first (HANDOFF 6.2), otherwise every goal is cancelled at 15 s | Nav2 action results, bug fixes | % ↑ |
| 11 | **Loop closure success rate** | 2 | Partial | Share of true revisits that SLAM closed, and share of closures that are correct | Count closures as transitions of `loop_closure_id > 0` on `/rtabmap/info`. Precision = closures where GT pose at closure matches GT pose of the matched node ÷ all closures. Recall = true revisits (from GT trajectory) that produced a closure ÷ true revisits. Existing `benchmark_slam.py` stores the latest id as a count and is meaningless | `/rtabmap/info` (`loop_closure_id`, `ref_id` exist), GT pose | % ↑ |
| 12 | **Path length ratio** | 1 | Partial | How much longer the driven path is than the shortest path | Actual path length from GT pose (not `/odom`) ÷ shortest path on the GT grid (A* on the GT grid) start→goal. 1.0 is ideal. Odometry distance is already logged in the metrics CSV but is inflated by noise and spinning | GT pose, GT grid | ratio ↓ (≥1) |
| 13 | **Coverage comparison across methods** | 4 | **ON HOLD (user decision)** | Compare coverage % of: frontier exploration (current), modified A*, SLAM + B. A*, GA + neural net, etc. | One harness, same worlds, seeds, Nav2 controller and robot; only the goal/path generation changes. Each method is a plug-in node that publishes goals/paths. **None of the baselines exist in the repo** (only stock Nav2 Smac + frontier exploration). Definitions of the baselines are still needed from the user (section 8) | Baseline implementations, harness | % ↑ per method |
| 14 | **Overall cleaning efficiency** | 4 | Missing | How well the robot cleans per effort | No cleaning model exists in the sim. Add a virtual swept-area grid (mark cells under the swath each tick using GT pose). Report components separately: cleaned fraction C = swept ÷ GT free area; redundancy R = total swept visits ÷ unique swept cells; efficiency = C ÷ R; m² per minute; m² per metre travelled. Give the combined score only alongside the components | GT pose, GT grid, swath width | % / m²·min⁻¹ ↑ |

---

## 3. Additional suggested metrics

| # | Metric | Meaning | How to measure | Unit |
|---|---|---|---|---|
| A1 | Coverage-vs-time curve; time to 50/80/95 % | Speed of coverage | Sample coverage (#1) every second of sim time | s ↓ |
| A2 | Redundant coverage / overlap ratio | Wasted effort | R from #14 | ratio ↓ |
| A3 | Missed / unreachable area | Free cells never swept | GT free cells minus swept cells, listed | m² ↓ |
| A4 | Total distance and energy proxy | Effort | Integrate GT speed; energy proxy = ∫v² dt | m, m²/s ↓ |
| A5 | Min and mean obstacle clearance | Safety margin complementing #3 | GT pose vs SDF geometry per tick | m ↑ |
| A6 | Recovery behaviour count | Nav2 stuck handling (spin, backup, wait, clear costmap) | Count BT recovery activations / behavior-server actions | count ↓ |
| A7 | Stuck / timeout count | Episodes or goals that hit the time limit | From harness | count ↓ |
| A8 | Planning time per goal | Planner cost | Time from goal accepted to plan received | ms ↓ |
| A9 | Path smoothness | Curvature / jerk of the driven path | From GT pose series | 1/m ↓ |
| A10 | SLAM tracking-lost events / map drift | Robustness | RTAB-Map stats; map-vs-GT shift after noise | count, m ↓ |
| A11 | CPU and RAM per process | Compute cost | `psutil` per PID. Existing logger reports system-wide RAM and an invalid first CPU sample | %, MB ↓ |
| A12 | Real-time factor | Sim validity | Gazebo stats | ratio ↑ |
| A13 | Repeatability | Spread across seeds | Std dev and 95 % CI over runs | — |
| A14 | AMCL localization error (Stage 5) | Localization on a saved map | AMCL pose vs GT | m ↓ |
| A15 | Sensor noise robustness | Degradation under noise | Re-run with odometry noise and camera noise on | Δ metric |

---

## 4. What exists today (verified by reading, not by running)

- **Only metrics logger:** `vacuum_exploration/exploration_metrics.py`, 1 Hz CSV at `~/bags/stage4b/<env>/run_NN/metrics.csv`. Columns: timestamp_sec, state, frontiers_count, goals_sent, goals_succeeded, goals_failed, distance_traveled_m, coverage_pct, free_cells, unknown_cells, cpu_pct, ram_mb, elapsed_sec. `summary.txt` and `metadata.yaml` are written only at FINISHED; Ctrl-C leaves them incomplete. `started_at` is overwritten at finish; git path is wrong (`~/Swachh_Boudhik_Yantra`).
- **Run end:** FSM FINISHED needs 5 no-frontier checks, free cells growing < 10 in 15 s and speed < 0.02 m/s. No timeout, no max goals, and the process keeps running after FINISHED.
- **ATE/RPE:** `vacuum_utils/scripts/evaluate_trajectory.py` (wraps `evo_ape`/`evo_rpe`). Broken defaults as in #6. `record_stage4.sh` does not record `/ground_truth/poses`.
- **SLAM stats:** `vacuum_utils/scripts/benchmark_slam.py`. Loop-closure field misused (#11), clock mix-up, Map area counts known cells (not completeness).
- **Localization package:** AMCL-only (`localization_monitor`, `recovery_monitor`, `localization_metrics`); goal columns hard-coded to 0.
- **No baselines:** no A*, B-A*, GA, neural net or coverage planner anywhere in the repo.

## 5. Prerequisites before any metric is trustworthy

1. **Ground-truth bridge:** `vacuum_gazebo/config/gz_bridge.yaml` hardcodes `/world/vacuum_world/pose/info`. Only `empty_world.sdf` has that world name; apartment/office/corridor are `apartment_world`, `office_world`, `corridor_world`. Parametrise the world name. Convert the `Pose_V` TFMessage into a robot-only pose/Odometry stream and record it.
2. **Nav2 + exploration bugs** (HANDOFF section 6.1–6.5): velocity-smoother feedback loop, 15 s oscillation cancel, unstable frontier IDs, stale goal results. Otherwise navigation numbers measure the bugs.
3. **Odometry noise must reach SLAM:** `odometry_noise_node` publishes `/odom_noisy`, but RTAB-Map reads `/odom`. Point RTAB-Map at the noisy topic when running ATE/loop-closure tests. With perfect odometry, ATE and loop closures are not meaningful.
4. **Seal the corridor world:** its south wall has door-sized gaps to open ground, so GT free area is undefined. Seal them (or add rooms behind them).
5. **Python tooling:** `evo`, `pandas`, `scikit-image` are NOT installed (`scipy`, `numpy`, `PIL`, `matplotlib`, `yaml`, `pytest` are). Install into a venv or via apt.
6. **Run harness:** one script/launch that sets seed and spawn, launches the sim, runs until done/timeout, saves per-run CSV + rosbag + metadata, then kills everything. No world-reset service exists, so each episode is a full relaunch. Use headless Gazebo (`gz sim -s`) and `use_rviz:=false` for batches.
7. **`slam.launch.py`** ignores `delete_db`; always deletes the DB in mapping mode. Delete `~/.ros/rtabmap.db*` explicitly between runs.

## 6. Environments

| World | Name in SDF | Size (approx.) | Obstacles | Notes |
|---|---|---|---|---|
| `room` (`empty_world.sdf`) | `vacuum_world` | 100×100 m plane, no walls | none | Only world with working GT today; unbounded so no coverage denominator |
| `apartment` | `apartment_world` | 6.4×5.2 m (~25 m² free) | ~17 models (sofa, tables, chairs, shelf, plants, rug) | Default everywhere; spawn (0,0) lies on the rug (collision box 2 cm high), check |
| `office` | `office_world` | 8.4×6.4 m (~39 m² free) | ~21 models (pillars, desks, chairs, cabinets) | |
| `corridor` | `corridor_world` | 12.2×2.4 m (~23 m² free) | extinguishers, boards, bench, bins | South wall gaps need sealing |

All worlds are fully static: **no dynamic obstacles exist** (needed for #4, #9, A5). Robot has only a D435i depth/RGB camera, no lidar, no IMU, no bumper. Depth-derived scan range is 0.2–2.5 m, so obstacles closer than ~0.2 m are invisible to Nav2 costmaps.

## 6b. Proposed additional worlds (not yet built)

Prefer small hand-written SDF worlds built from boxes/cylinders (like the existing ones) over Gazebo Fuel downloads: box geometry can be rasterised into the GT grid exactly, Fuel meshes cannot, and Fuel models are heavy on a WSL laptop. Each world needs a unique SDF world name and must work with the parametrised GT bridge.

| Proposed world | Purpose | Metrics it serves |
|---|---|---|
| `empty_room` 6×6 m, walls, no obstacles | Clean baseline and coverage upper bound | #1, #8, #14, A1 |
| `cluttered_room` ~8×8 m, 15–30 % obstacle fill | Dense avoidance, narrow gaps | #3, #4, #9, A5 |
| `two_rooms_door` two rooms joined by a 0.9 m door | Door traversal, planner robustness | #10, #12 |
| `l_shape_or_multi_room` 3–4 rooms and a hall, with loops | Loop closures and revisits | #11, #6, #7 |
| `maze_dead_ends` | Recovery behaviours, stuck handling | A6, A7 |
| `dynamic_obstacles` room with moving boxes/actors | Dynamic avoidance and responsiveness | #4, #5, #9 |
| `symmetric_hall` repeated identical features | Perceptual aliasing, false loop closures | #11 precision, A10 |

Existing apartment, office and corridor (sealed) stay as the realistic set.

## 7. Experiment design

- Scale: ~3 worlds × 4 methods × 10 seeds ≈ 120 episodes (not the 486-run grid in `q1_paper_test_roadmap.md`, which assumes a LiDAR TurtleBot; LiDAR rows do not apply here).
- Report mean ± std and 95 % CI. Compare methods with Wilcoxon / Mann-Whitney.
- Each episode runs in real time (plausibly 10–20 min on this laptop); batch headless.
- Robustness runs: repeat with odometry noise and camera noise ON.

## 8. Decisions and open questions

| # | Question | Status |
|---|---|---|
| 1 | Definitions of "modified A*", "B. A*", "GA + neural net" (#13) | **ON HOLD.** User said to park #13. Do not implement baselines yet; build the harness so a method is a plug-in later |
| 2 | Vacuum swath width (width of floor cleaned as the robot drives) | Open. Using 0.25 m (robot chassis width) as a placeholder; user asked for an explanation, confirm or give the real brush/nozzle width |
| 3 | Which worlds | Open. User wants more ideal worlds added; see section 6b for the proposal |
| 4 | Responsiveness deadline 0.5 s | **Accepted** (user: go ahead) |
| 5 | Additional metrics A1–A15 | **Accepted** (user: add them). Treat as in scope, after Tier 1–2 |

## 9. Provenance

Findings come from three read-only code audits (exploration/metrics; localization/eval scripts/SLAM; Nav2/worlds/bridge/sensors) plus these checks run in Ubuntu: `ros_gz_interfaces/msg/Contacts` exists, `rtabmap_msgs/msg/Info` has `loop_closure_id`, `ref_id`, `proximity_detection_id` and `stats_keys`, the gz contact-system library is installed, and the Python module availability listed in section 5. The workspace builds (10 packages, after removing a nonexistent `rviz/` install from `vacuum_description/CMakeLists.txt`). Nothing has been launched. Line numbers cited by the audits were not individually re-checked.
