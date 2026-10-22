# REQUIREMENTS — read this first (Swachh simulation evaluation)

**Audience:** a new Claude Code session, or a person, taking over the simulation evaluation work with no prior context.
**Last updated:** 2026-10-21, ~19:30. Pilot 2 was still running at the time of writing (see §6).

Read in this order:
0. `docs/RUNBOOK.md`: exact commands for everything left to execute (the user runs them; code complete as of 2026-10-22). `docs/FAILURE_MODES.md`: what to do when a metric is bad or unmeasurable (health codes in summary.json).
1. This file.
2. `docs/METRICS_STATUS.md`: what has actually been measured. This is the live tracker.
3. `docs/specs/13_preregistration.md`: the frozen final definitions and campaign rules.
4. `docs/specs/README.md`: the index of the implementation specs 00–14.
5. `docs/specs/14_critique_and_council_plan.md`: every critique and council item, with its status.

---

## 1. Goal

The project is a Q1 journal paper on an autonomous indoor cleaning robot (Swachh Boudhik Yantra). It needs the user's 14 metrics plus 15 extras (A1–A15), measured in simulation and defensible to reviewers. "Defensible" means:
- valid data;
- metrics that are not circular;
- a pre-registered dev/test split;
- statistics with the episode as the unit;
- reporting failures as well as successes.

**Definition of done:** every non-held metric in `docs/METRICS_STATUS.md` reaches stage **Campaign**. That means it is measured on the test split with episode counts from `vacuum_eval.plan_sample_size`, its `aggregate.csv` contains cluster-bootstrap CIs, and every invalid or failed run is reported.

The metrics (definitions in `docs/specs/13_preregistration.md`):
1. coverage
2. steps per episode
3. collisions
4. % obstacle avoidance
5. responsiveness, measured as wall-clock controller latency
6. ATE
7. RPE
8. map completeness
9. avoidance trial success
10. navigation success
11. loop-closure precision and recall
12. path length ratio
13. method comparison: **ON HOLD**, the user's decision; do not implement
14. cleaning efficiency: secondary

## 2. Hard constraints and user decisions (do not change without asking the user)

| Decision | Detail |
|---|---|
| Global planner | Nav2 **SmacPlannerHybrid, DUBIN**, unchanged. The user refused changing it twice. Do not switch to 2D, Lattice, Reeds-Shepp or NavFn. |
| Method comparison (#13) | On hold. No baselines (modified A*, B-A*, GA+NN). A coverage planner was overruled by the council until a valid campaign exists. |
| Physics | No fudge-factor calibration. `wheel_separation_multiplier` stays 1.0. Odometry drift is *measured*. In-place rotation odom/GT yaw is 0.940–0.942 (stable), arcs 0.957–0.976, straight lines exact. |
| Swath width | 0.25 m (placeholder for the brush width). Cleaning efficiency is secondary. |
| Responsiveness | Wall-clock controller latency; deadline 0.5 s for command→motion and stop. |
| Subagents | Use **Sonnet** subagents (the user's standing instruction, usually low effort) with **non-overlapping file ownership** and precise tasks. Second-order subagents only Haiku/Sonnet. The main session orchestrates. Subagents must not start the simulator or run `colcon` while another agent or a sim run is active; only one simulation can run on this laptop at a time. |
| Communication | Concise replies. Give a recommendation, not a survey. Ask before destructive actions. Never ask for the sudo password (see §3). |
| Data leaving the machine | The claude-council plugin (`hex/claude-council`) is not installable here (`/plugin` unavailable). A local `llm-council` skill exists in `~/.claude/skills/llm-council` and was used Sonnet-only. Do not send project content to third-party AI providers without the user's explicit OK. |

## 3. Environment (verified)

- **Machine:** Windows laptop, WSL2 Ubuntu 24.04, i7-1185G7 with 8 threads, no usable GPU (software rendering; `--headless-rendering` segfaults).
- **Stack:** ROS 2 Jazzy, Gazebo Harmonic (gz-sim 8.15).
- **Repo:** `~/Swachh` (the Windows copy is stale). Workspace: `~/Swachh/Navigation/Simulation/vacuum_ws`.
- **Shell setup** (non-interactive shells need it explicitly):
  ```bash
  source /opt/ros/jazzy/setup.bash
  source ~/Swachh/Navigation/Simulation/vacuum_ws/install/setup.bash
  export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp CYCLONEDDS_URI=file://$HOME/Swachh/Navigation/cyclone_dds.xml ROS_DOMAIN_ID=0
  ```
- **Root without a password:** `wsl.exe -d Ubuntu -u root -e bash -c "<cmd>"`.
- **DDS buffers** (this was the root cause of every SLAM failure until 2026-10-21):
  - `/etc/sysctl.d/90-ros2-dds.conf` sets rmem/wmem to 32 MB.
  - `/etc/wsl.conf` `[boot] command` reapplies it at every WSL start.
  - `cyclone_dds.xml` has `SocketReceiveBufferSize min="16MB" max="32MB"`.
  - **Check after every WSL restart:** `cat /proc/sys/net/core/rmem_max` must be `33554432`. If it isn't, re-run the sysctl as root, or images will silently stop reaching RTAB-Map.
- **Build:** `colcon build --symlink-install`. `vacuum_eval` and config/launch files are symlinked. **`vacuum_exploration` installs copies**, so rebuild after editing it.
- **Python:** numpy, scipy, matplotlib, PIL, yaml, pytest and cv2 are available. pandas, evo, skimage and shapely are **not**; do not add them as dependencies.
- **Installed via apt on 2026-10-21:** `ros-jazzy-spatio-temporal-voxel-layer`.

### Gotchas that cost hours (do not repeat)
- **Never** `pkill -f` with a pattern that appears in your own command line. For example, `pkill -f 'gz sim'` inside a command that also contains `gz sim` kills the calling shell. Start processes with `setsid` and kill the process group (`kill -- -$PGID`), or use scripts.
- **Gazebo's `/stats` `real_time_factor` field is misleading.** It read 1.00 while the true sim/wall rate was 0.49. Measure RTF as d(sim_time)/d(wall) over 15–20 s; `rtf.csv` from the recorder does this.
- **Contact sensors** only publish for models that exist when the world loads. `sim.launch.py` therefore bakes the robot into the world at launch (`embed_robot:=true`, the default), in a unique `tempfile.mkdtemp` directory. Relative texture paths are rewritten to absolute paths during baking.
- **`ros2 topic hz` with a single subscriber proves nothing about DDS drops.** Use the episode validity keys (§4).
- **Harness gates:** G4 (TF map→odom) passes even when RTAB-Map processes nothing. G7 (`/rtabmap/info` alive) is the real check.
- **Cancelled tool calls** can leave stale `gz sim` or `ruby` processes. Check `pgrep -fa "gz sim|ruby"` before launching.

### Machine setup and preflight scripts
- `Navigation/Simulation/scripts/setup_machine.sh [--dry-run]` sets up a fresh WSL or native Ubuntu machine (apt, DDS sysctl, bashrc, build, tests).
- `Navigation/Simulation/scripts/preflight.sh` is a read-only check to run before every batch. See `Navigation/Simulation/scripts/README.md`.

## 4. Pipeline (what exists and how to run it)

| Component | Where | Notes |
|---|---|---|
| Simulation bring-up | `vacuum_bringup/launch/sim.launch.py` | Arguments: `world`, `spawn_*`, `headless`, `odom_mode` (`clean`/`eval`), `odom_noise`, `odom_noise_seed`, `embed_robot`, `gz_verbose`, `extra_bridge_config` |
| Ground truth | OdometryPublisher plugin in the URDF → `/ground_truth/odom_raw` → `vacuum_eval/ground_truth_node` → `/ground_truth/odom` (frame `world`) | Verified exact at spawn |
| Odometry noise (evaluation) | `vacuum_eval/odom_noise_node` (in the odometry path when `odom_mode:=eval`) | Persistent scale error plus heading random walk, seeded |
| Command path | Nav2 → `/cmd_vel_nav` → velocity_smoother → `/cmd_vel_smoothed` → `cmd_vel_relay_nav` → stamped `/diff_drive_controller/cmd_vel` | The controller only subscribes to the stamped topic |
| SLAM | RTAB-Map, `vacuum_slam/config/rtabmap.yaml` | STMSize 10, MinInliers 10, FeatureType 6 = detector, Force3DoF, grid band 0.03–0.30 m |
| Nav2 | `vacuum_nav2/config/nav2_params.yaml` | Polygon footprint 0.30×0.25 m, `consider_footprint` true, inflation 0.28/5, STVL obstacle layer on `/scan_from_depth` (decay 15 s local, 60 s global), band 0.03–0.30 m |
| Explorer | `vacuum_exploration/exploration_manager.py` | Goal snapping, bootstrap spin; guards added 2026-10-21: goal-at-robot, no-information-gain, `min_frontier_size_m` 0.5, robot position from TF map→base_footprint |
| Recorder | `vacuum_eval/recorder_node.py` | Writes all raw CSVs (`docs/specs/02` §2.4) plus `est_interp`, `wall_t`, `lc_tx/ty/tyaw` |
| Episode harness | `python3 -m vacuum_eval.run_episode` | Gates G1–G7; methods `frontier`, `scripted_goals`, `responsiveness`; `--localization {auto,slam,amcl,gt}`; `--nav-map {gt,slam}`; `--goal-list ...` |
| Offline metrics | `python3 -m vacuum_eval.compute_metrics <run_dir>` | Writes `summary.json`/`.csv`; status `ok`/`partial`/`failed`/`invalid` |
| Validity | `metrics/validity.py` | `invalid` if image drop >10%, RTAB-Map gap >5 s, or <0.5 updates per s (RTAB-Map rules are skipped for amcl/gt localization) |
| Diagnosis | `python3 -m vacuum_eval.diagnose <run_dir> --png out.png` | Explains why metrics are what they are: time split, goals, log failures, stuck spots |
| Batch | `python3 -m vacuum_eval.run_batch --matrix config/campaigns/<file>.yaml --split dev` (test needs `--split test --confirm-test-split`) | Writes `batch_manifest.json` with the campaign hash and git commit |
| Aggregation | `python3 -m vacuum_eval.aggregate --root ~/eval_runs/<exp> --out aggregate.csv` | Episode unit, cluster bootstrap, Holm |
| Sample size | `python3 -m vacuum_eval.plan_sample_size ...` | For example, p=0.6, 8 goals per episode, ICC 0.1, ±10 pp → 20 episodes |
| Worlds | `vacuum_gazebo/worlds/*.sdf` | 9 evaluation worlds + 8 `avoid_*` scenarios, distinct textures per wall (`symmetric_hall` repeats deliberately); registry in `vacuum_eval/config/worlds.yaml` and `worlds_scenarios.yaml` (with `split`) |
| Tests | `cd src/vacuum_eval && python3 -m pytest test -q -p no:cacheprovider` | 154 pass, including the oracle known-answer tests; `src/vacuum_exploration/test` has 7 |

Results live in `~/eval_runs/<experiment>/<world>/<method>/seed_<NNN>/`. Runs on the current pipeline are `pilot1` (valid) and `pilot2`. The `smoke*` and `tune*` runs predate the DDS fix and the metric fixes, so do not use them for results.

Typical wall time: true RTF is about 0.3–0.45, so 600 s of sim time takes about 25–35 min and a 20-minute-sim episode about 45 min.

## 5. Requirements still open (do these in order)

Each requirement must end with its result recorded in `docs/METRICS_STATUS.md`, any spec change logged with a date in the relevant spec, and pre-registration changes in `13_preregistration.md` §13.6.

**R1. Evaluate pilot 2.** Run dir: `~/eval_runs/pilot2/apartment/frontier/seed_002`. Log: `/tmp/claude-1002/-home-hrishikesh-Swachh/4b4a4437-3043-4377-b3a9-ab73bbb99673/scratchpad/pilot2.log` (it may be gone after a reboot; the run dir is what matters).
- If `summary.json` is missing, run `compute_metrics` on it. Then run `diagnose`.
- Acceptance:
  - `episode_valid` is true.
  - `rtabmap_updates` ≈ `episode_sim_sec`.
  - No goal loop: `n_goals` is at most a few dozen and `frontiers_skipped` appears in `/exploration/status`.
  - `ate_improvement_pct` > 0.
  - Compare against pilot 1 (`ate_fixed_rmse_m` 0.066, `coverage_explored_pct` 62.4, `map_completeness_pct` 45.4).
- Check that STVL did not create new collisions or planner failures. Its two risks: frustum clearing can wipe low obstacles under the scan slice, and a single scan slice means the height band does not really filter.

**R2. Verify the loop-closure transform direction.**
- `recorder_node` writes `lc_tx, lc_ty, lc_tyaw`, assuming RTAB-Map's Info `loop_closure_transform` maps ref (current) → loop (older), so pose_loop = pose_ref · T. That convention is unverified.
- On pilot 2 data, compare each accepted closure's transform with inv(GT_ref)·GT_loop and with its inverse.
- If the inverse matches, fix `metrics/loop_closure.py` and the doc. Acceptance: the correct convention gives errors of a few cm and degrees; the wrong one gives large errors.

**R3. Scripted navigation (dev world `apartment`).**
- Run: `run_episode --method scripted_goals --goal-list random20 --nav-map gt` three times, once each with `--localization gt`, `amcl` and `slam`, on seeds 1–2.
- The `--localization gt` route (plain `nav2.launch.py` + `map_server` lifecycle wrapper + `gt_localization_node`) has **never run live**. Expect to debug it.
- Acceptance: valid runs with `nav_success_gt_pct`, `path_length_ratio_mean`, `loc_error_mean_m` (AMCL), and a clear gt-versus-amcl-versus-slam difference. This separates navigation failures from localization error.

**R4. Responsiveness.**
- Run: `run_episode --method responsiveness --stack bare` and `--stack loaded`, dev world, seed 1.
- Acceptance: wall-clock `lat_cmd_motion_ms_*` and `lat_stop_ms_*` are present, `resp_definition` is `wall_clock_controller_latency`, and `wall_latency_s` is filled in `responsiveness_events.csv`.

**R5. Avoidance scenarios (dev split): `avoid_head_on`, `avoid_cluster`, `avoid_dynamic_cross`.**
- These have **never been launched**. The dynamic world needs `extra_bridge_config` (`gz_bridge_dynamic.yaml`) and `dynamic_mover`.
- Acceptance: `trial_success`, contact-sensor collisions counted where they happen (`collision_source: contact`), `avoidance_pct` with more than 1 encounter, and dynamic-obstacle ground truth in `dyn_obstacles.csv`.

**R6. Loop-closure world check (dev-safe).**
- `multi_room_loop` and `symmetric_hall` are *test* worlds; do not tune on them.
- Instead, check loop closures on a dev world with a revisit-rich path: apartment with the `loop_tour` goal list, or a longer 900 s exploration.
- Acceptance: closures accepted, and transform-based precision computed with R2 resolved.

**R7. Sample size and campaign sizing.**
- Run `plan_sample_size --from-root` on the dev runs (needs at least 3 seeds per configuration, so run a few more dev seeds if needed). Fix the episode counts.
- The current `final_exploration.yaml` is 6 worlds × 10 seeds × 2 noise levels = 120 episodes, about 44 h of wall time. Reduce or extend it based on the target CI widths.
- **Ask the user before committing to a multi-day campaign.**

**R8. Freeze and run the test campaign.**
- Before the first test run: update `13_preregistration.md` §13.6, commit the code (ask the user first; the repo has many CRLF-only diffs, so commit only touched files), and record the commit.
- Then run `run_batch --split test --confirm-test-split` for `final_exploration`, `final_navigation`, `final_avoidance` and `final_responsiveness`.
- Run `diagnose` after each batch of about 5 episodes. Rerun invalid episodes once with the same seed only for infrastructure faults, and report both attempts.

**R9. Aggregate and report.**
- Run `aggregate` per experiment, then fill `METRICS_STATUS.md` to stage Campaign, with a results table per metric: mean, cluster CI, n, n_invalid and n_failed.
- Report unfavourable results, invalid counts and deviations (pre-registration §13.5b).

## 6. Known open issues and risks

- **Loop closure:** only pilot 1 had accepted closures (2, both true under the loose definition). The transform truth test (R2) is unverified. With STMSize 10, closures need revisits more than about 10 nodes (≈10 s) apart.
- **Low simulation speed:** RTF 0.29–0.45. A camera reduction to 320×240 is deferred, because it changes the sensor; decide only if campaign wall time is prohibitive, and ask the user.
- **Nav2 success** on frontier goals was low before the 2026-10-21 fixes (planner "no valid path"). Re-assess on pilot 2 and R3. The planner itself must not change; costmap, STVL and footprint are allowed.
- **Axle offset:** the wheel axle is 8 cm behind `base_footprint`. In-place spins move the GT position about 0.10 m while odometry reports 0, so odometry rotates about the wrong point. Documented as measured error, not fixed.
- **Simulation-only evaluation** is a reviewer risk. Mitigations in place: noise injection, multiple worlds, a dev/test split, validity gates, and failure reporting. Real-robot or public-dataset validation is not planned; mention this in the paper's limitations.
- **Unit tests:** the original tests were written by the same agents as the code. The `test_oracle_*.py` known-answer tests are the independent check; extend them when changing a metric.

## 7. Other subsystems (not part of this work; carried over from the retired HANDOFF.md)

**Perception** (`Object Detection/Camera/vision`):
- Depth units mix metres and centimetres, with 10 cm rounding.
- `ARM:PICK` is not understood by the Arduino firmware.
- The stereo calibration is suspect (cx outside the image, large rectification angles).
- Detection runs on the unrectified frame while depth comes from the rectified one.
- The YOLO `_nms` transpose heuristic likely mishandles the standard `(84, 8400)` output.
- There are two detector worlds: COCO yolov8s versus a custom 8-class model.
- The HMI and the vision code compete for one serial port.
- The Pi host IP differs between files (10.0.0.1 versus 192.168.4.1).

**Hardware** (Arduino/HMI):
- No watchdog: motors keep running if the link dies.
- Blocking `delay`s.
- Peripherals are flags only.
- The HMI's `send_command` blocks the GTK thread.
- Battery level is simulated.
- Serial protocol: 115200 baud, `MOVE:*`, `SPEED:1..9`, `VACUUM|ARM|WIPER|UV:ON|OFF`, `AUTO`, `AI`, `ESTOP`, `RESET`; replies `ACK:`/`ERR:`, `STATUS:` every 1 s.

**Edge-vision benchmark paper** (`docs/PROJECT_CONTEXT.md`, `docs/README.md`):
- The "quantization gain" confounds backend with precision (ORT-CPU FP32 versus TRT-GPU FP16/INT8).
- INT8 is calibrated on random noise.
- Network transit is a constant RTT/2.
- The engine sizes reported are the ONNX sizes.
- `shapiro()` is actually D'Agostino.
- Model paths are inconsistent between files.

**Lab workstation docs** (`Navigation/Simulation/Documentation/software_stack.md`, `ros2_jazzy_final_verified.md`): these describe the team's HP Z4 workstation (Ubuntu 26.04). They may matter for the paper's Methods section if the final runs happen there. `Navigation/*.sh` scripts hardcode `/home/bmscecse/...` paths for that machine, so don't use them in WSL.
