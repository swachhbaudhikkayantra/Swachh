# 02 — Run Harness, Recorder, Episodes, Batching, Statistics

Covers: #2 (steps per episode), A7 (stuck/timeouts), A11 (CPU/RAM), A12 (real-time factor), A13 (repeatability), A15 (noise robustness runs). Defines **every raw file** that other specs read, so this file is the single source of truth for raw-data schemas.

Depends on: 00, 01.

---

## 2.1 Episode definition (the unambiguous version)

| Symbol | Definition |
|---|---|
| `t0` | Sim time of the recorder's first `trajectory.csv` row. Used for `t_rel`. |
| `episode_start_t` | The first sim time at which a command row with `source = ctrl_stamped` (see §2.4 `cmd_vel.csv`) has `|vx| > 0.01` or `|wz| > 0.01`. If none occurs, the episode never started: `status: failed`, `end_reason: no_motion`. |
| `episode_end_t` | The earliest of the end conditions below, in sim time. |
| episode duration | `episode_end_t − episode_start_t` (key `episode_sim_sec`). |

**All episode metrics are computed over `[episode_start_t, episode_end_t]` only.** Bring-up time (SLAM and Nav2 start-up) is excluded; it is recorded separately as `bringup_sim_sec = episode_start_t − t0`.

End conditions and `end_reason` values (exact strings):

| `end_reason` | Condition | Counts as completed? |
|---|---|---|
| `finished` | `/exploration/finished` (Bool true) received (method `frontier`) | yes |
| `goals_done` | `/eval/done` (Bool true) received (scripted goal lists, spec 05) | yes |
| `timeout` | `episode_sim_sec ≥ episode_timeout_sim_sec` (default 1200 s, per-world override in `worlds.yaml`) | no (A7) |
| `stuck` | In the last 180 s of sim time the ground-truth position moved less than 0.30 m **and** the robot's `smoothed` command magnitude was not rotating-only (see rule) and no `finished`/`goals_done` | no (A7) |
| `crash` | Any monitored process exited (sim, slam, nav2, explore, recorder) | no, `status: failed` |
| `no_motion` | see above | no, `status: failed` |
| `aborted_by_user` | harness received SIGINT | no |

Stuck rule precisely: sample GT position every 1 s; `stuck` fires when `max over window of hypot(x−x_first, y−y_first) < 0.30 m` for a 180 s window **and** summed `|wz|·dt` over the window < 2π rad (so pure spinning recoveries for a few seconds do not hide a stuck robot, but a robot that only spins for 180 s is also stuck).

## 2.2 Counters for #2 "steps"

Reported per run, all over the episode window:

| Key | Definition |
|---|---|
| `n_cmd_ticks` | Number of rows in `cmd_vel.csv` with `source = ctrl_stamped` in the window (each command reaches the controller exactly once) |
| `n_goals` | Number of `goal_events` rows with `src=explore, event=started` (method `frontier`) or goals sent by `goal_sender` (scripted) |
| `n_recoveries` | See spec 05 (A6) |
| `episode_sim_sec` | duration |
| `distance_gt_m` | `Σ hypot(Δx, Δy)` over consecutive `trajectory.csv` rows' GT positions in the window (10 Hz sampling) |

"Average steps per episode" = mean over runs of each key above (aggregate step, §2.9). The primary headline is `n_goals`; `n_cmd_ticks` is reported alongside. Reason: a "step" in RL terminology maps to a control tick, in navigation terminology to a goal; both are stated explicitly.

## 2.3 Launch matrix (what gets started)

The harness starts these as separate OS process groups (`subprocess.Popen(..., start_new_session=True)`), each logging to `logs/<name>.log`:

| Name | Command (sourced env) | Notes |
|---|---|---|
| `explore_stack` | `ros2 launch vacuum_exploration exploration.launch.py environment:=<world> spawn_x:=<x> spawn_y:=<y> spawn_yaw:=<yaw> odom_mode:=eval headless:=<bool> use_rviz:=false database_path:=<run_dir>/rtabmap.db` | Starts Gazebo (T+0), RTAB-Map (T+12 s), Nav2 (T+20 s), exploration nodes (T+28 s). **Required change:** forward `spawn_*`, `odom_mode`, `headless`, `use_rviz`, `database_path` and `odom_noise*` args to `sim.launch.py`/`slam.launch.py`; `exploration.launch.py` currently only forwards `environment`. Grep its `IncludeLaunchDescription` blocks. Also remove `warehouse` from its choices (no such world). |
| `eval_stack` | `ros2 launch vacuum_eval eval_stack.launch.py ...` | `ground_truth_node`, `odom_noise_node` params (via `odom_mode:=eval` it is started by sim launch), `recorder_node` |
| `bag` | `ros2 bag record -o <run_dir>/bag --use-sim-time -s sqlite3 <topics>` | Topic list §2.5 |

For scripted-goal runs (spec 05) the method launch is `ros2 launch vacuum_nav2 nav2.launch.py ...` after `sim` and `slam` launches, plus `goal_sender`. The harness has one `method` abstraction: `launch_method(method_name) -> list[ProcessSpec]`; `frontier` is the only implemented one now, `scripted_goals` for nav tests, others are plug-ins (spec 11).

## 2.4 Raw files written by `recorder_node` (authoritative schemas)

Node: `vacuum_eval/recorder_node.py`. Parameters: `run_dir` (str, required), `sample_hz` (10.0), `map_snapshot_period_sec` (5.0), `robot_model_name` (`vacuum_robot`), `extra_models` (list, default []; each name N is read from `/ground_truth/model/N`, `nav_msgs/Odometry`). All timers use the node's sim clock except the resource/RTF timer, which uses a wall clock (`self.create_timer(1.0, cb, clock=Clock(clock_type=ClockType.SYSTEM_TIME))`). Opens all CSVs with line buffering and `flush()` every row, so a crash loses at most one row. Subscribes with QoS `reliable, volatile, depth 50` unless stated.

All CSVs start with columns `t, t_rel` (sim seconds absolute, and minus `t0`). Floats with 6 decimals.

### `trajectory.csv` — timer at `sample_hz` (10 Hz sim)

| Column | Source |
|---|---|
| `gt_x, gt_y, gt_yaw` | latest `/ground_truth/odom` pose (frame `world`); empty if older than 0.2 s sim |
| `gt_vx, gt_wz` | its twist |
| `odom_x, odom_y, odom_yaw` | latest `/odom` pose (frame `odom`, possibly noisy); empty if older than 0.2 s |
| `est_x, est_y, est_yaw` | TF lookup `map → base_footprint`, `Time()` (latest), 0.05 s timeout; empty on failure |
| `est_ok` | 1 if the TF lookup succeeded else 0 |

### `cmd_vel.csv` — every message
Columns `source, vx, vy, wz`. Sources and topics (exact):

| `source` | Topic | Type |
|---|---|---|
| `teleop` | `/cmd_vel` | `geometry_msgs/Twist` |
| `nav` | `/cmd_vel_nav` | `Twist` (exists after fix 01 §1.4) |
| `smoothed` | `/cmd_vel_smoothed` | `Twist` (Nav2 velocity smoother output; informational) |
| `ctrl_stamped` | `/diff_drive_controller/cmd_vel` | `geometry_msgs/TwistStamped` (use `.twist`) — **the only topic the controller consumes** (teleop and Nav2 both reach it through `cmd_vel_relay`/`cmd_vel_relay_nav`) |

### `goal_events.csv`
Columns `src, goal_seq, event, result, x, y, nav2_error_code, uuid`.
- Rows with `src=explore`: from `/exploration/goal_events` JSON (01 §1.5.5). `event` = `started` or `ended`; `result` as in the JSON; `x,y` = goal position; `uuid` empty.
- Rows with `src=nav2_status`: one row per **status transition** seen on `/navigate_to_pose/_action/status` (`action_msgs/GoalStatusArray`): `event` ∈ `accepted, executing, canceling, succeeded, canceled, aborted` (map status codes 1,2,3,4,5,6), `uuid` = 32-char lowercase hex of `goal_info.goal_id.uuid`, other columns empty.
- Rows with `src=scripted`: published by `goal_sender` on `/eval/goal_events` (same JSON schema as explore; spec 05).
- Rows with `src=behavior_spin`, `behavior_backup`, `behavior_wait`: status transitions on `/spin/_action/status`, `/backup/_action/status`, `/wait/_action/status` (same mapping and `uuid` rule as `nav2_status`). Required by spec 05 §5.5.

### `feedback.csv`
From `/navigate_to_pose/_action/feedback` (`nav2_msgs/action/NavigateToPose_FeedbackMessage`): `uuid, distance_remaining, number_of_recoveries, navigation_time_sec` (navigation_time converted `sec + nanosec·1e-9`).

### `plans.csv`
One row per `/plan` message (`nav_msgs/Path`, frame `map`): `plan_seq` (counter), `n_poses`, `length_m` (sum of segment lengths), `start_x, start_y, end_x, end_y`.

### `rates.csv` — spec 07 §7.5 (1 Hz of sim time; message counts per topic)
### `responsiveness_events.csv` — written by `responsiveness_test.py`, spec 07 §7.4

### `collisions_raw.csv` — spec 06 §6.3.  `loop_events.csv` — spec 08 §8.2.  `dyn_obstacles.csv` — spec 09 §9.6.

### `resources.csv` and `rtf.csv` — 1 Hz **wall** timer
- `rtf.csv`: `rtf = Δsim_time / Δwall_time` between consecutive wall ticks (sim time = last `/clock` stamp); columns `t, t_rel, wall_dt, sim_dt, rtf`.
- `resources.csv`: columns `cpu_total_pct` (`psutil.cpu_percent(interval=None)`; the first sample is discarded and written empty), `ram_used_mb` (system `virtual_memory().used / 2**20`), and for each group G in the table below `cpu_G_pct` (sum over group processes of `Process.cpu_percent(interval=None)`; this is % of **one** core, can exceed 100) and `rss_G_mb`. Processes are matched by substring in `' '.join(proc.cmdline())`; first matching group in table order wins.

| Group G | cmdline contains any of |
|---|---|
| `gz` | `gz sim`, `ruby` with `gz` , `gz-sim` |
| `rtabmap` | `rtabmap` |
| `nav2` | `controller_server`, `planner_server`, `bt_navigator`, `behavior_server`, `smoother_server`, `velocity_smoother`, `amcl`, `map_server`, `lifecycle_manager`, `collision_monitor` |
| `bridge` | `parameter_bridge`, `ros_gz_bridge`, `topic_tools` |
| `explore` | `exploration_manager`, `frontier_detector`, `frontier_visualizer`, `exploration_metrics` |
| `eval` | `vacuum_eval`, `recorder_node`, `ground_truth_node`, `odom_noise_node` |
| `other_ros` | `/opt/ros/jazzy` or `vacuum_ws/install` |

### `maps/` snapshots
Subscribe `/rtabmap/map` (`nav_msgs/OccupancyGrid`; QoS `reliable, transient_local, depth 1`). On a message, if `t − last_snapshot_t ≥ map_snapshot_period_sec`, write `maps/map_<t_rel as %08.2f>.npz` containing arrays/scalars: `data` (int8, shape `(height, width)`, row 0 = lowest y, values −1/0/100), `resolution`, `origin_x`, `origin_y`, `origin_yaw` (float64), `t`, `t_rel`. On `/eval/stop` write `maps/final_map.npz` (from the most recent map message) and `final_map.pgm` + `final_map.yaml` (map_server format: PGM P5, free=254, occupied=0, unknown=205, `image: final_map.pgm`, `resolution`, `origin: [ox, oy, 0]`, `negate: 0`, `occupied_thresh: 0.65`, `free_thresh: 0.25`; PGM rows top-to-bottom = flipped `data`).

### Other topics subscribed by the recorder
`/rtabmap/info` → `loop_events.csv`; contacts topic → `collisions_raw.csv`; `/eval/stop` (`std_msgs/Empty`) → finalize and exit; `/exploration/finished` and `/eval/done` → write `events.csv` row `finished_signal`.

### `events.csv` (recorder + harness, appended)
Columns `event, detail`. Events: `recorder_started, first_gt_sample, first_est_sample, episode_start, finished_signal, stuck_detected, timeout_reached, stop_received, recorder_stopped`.

## 2.5 Rosbag topics (recorded for debugging and re-analysis; images excluded)

`/clock /tf /tf_static /odom /diff_drive_controller/odom /ground_truth/odom_raw /ground_truth/odom /cmd_vel /cmd_vel_nav /cmd_vel_smoothed /diff_drive_controller/cmd_vel /rtabmap/map /rtabmap/info /rtabmap/mapGraph /exploration/status /exploration/goal_events /exploration/current_goal /exploration/finished /navigate_to_pose/_action/status /navigate_to_pose/_action/feedback /plan /local_plan /scan_from_depth /joint_states /vacuum_robot/contacts /eval/goal_events /eval/done`. (Topics that do not exist are skipped by `ros2 bag record` with a warning; log it.)

## 2.6 Harness: `run_episode.py`

CLI (`argparse`), all long options:
`--experiment SLUG --world {apartment,office,corridor,...} --method {frontier,scripted_goals} --seed N --odom-noise {0,1} --headless {0,1} --timeout-sim-sec 1200 --runs-root ~/eval_runs --force`.

Sequence (each step logs a line to `events.csv`):
1. **Preflight:** `pgrep -f "gz sim"` must return nothing (else exit 2 "stale simulator"); check `cat /proc/sys/net/core/rmem_max ≥ 4194304` (warn otherwise); check free disk ≥ 5 GB.
2. **Run dir:** create `…/seed_<NNN>/`; if `summary.json` exists with `status: ok` and not `--force`, skip.
3. **Spawn sampling (§2.7).** Write `run_meta.yaml`.
4. **Start** `bag`, `explore_stack` (or method equivalent). Environment: `ROS_DOMAIN_ID` must be unique per concurrent run (this harness runs one at a time: domain 0).
5. **Readiness gates** (wall-clock timeouts; poll with `ros2` CLI or an rclpy helper node): G1 `/clock` publishing and advancing; G2 `ros2 control list_controllers` shows `joint_state_broadcaster` and `diff_drive_controller` both `active`; G3 one message on `/ground_truth/odom`; G4 TF `map→base_footprint` resolves; G5 action server `navigate_to_pose` available; G6 one `/rtabmap/map` message. Each gate timeout 120 wall s (G4–G6 total budget 240 s). On failure: write `end_reason: crash`/`bringup_failed`, `status: failed`, clean up, return non-zero.
6. **Start** `eval_stack` (recorder) as soon as G1–G3 pass (so `t0` precedes episode start).
7. **Monitor loop** (wall 1 Hz): check processes alive; read the recorder's `events.csv`/`trajectory.csv` tail for end conditions in §2.1 (the harness evaluates `timeout`/`stuck` itself from `trajectory.csv`; the end signals `finished`/`goals_done` come from the recorder's `events.csv`). SIGINT → `aborted_by_user`.
8. **Stop:** publish `/eval/stop` (once, `ros2 topic pub --once`); wait up to 30 wall s for the recorder to log `recorder_stopped`; stop the bag (SIGINT, wait 20 s); SIGINT all process groups, wait 15 s, SIGKILL leftovers by process-group id; verify `pgrep -f "gz sim"` empty (else `pkill -9 -f "gz sim"` then continue).
9. **Compute:** `python3 -m vacuum_eval.compute_metrics <run_dir>`; the exit code decides `status`.
10. Print one line: `run_dir status end_reason episode_sim_sec`.

## 2.7 Spawn pose sampling (seeded)

`config/worlds.yaml` holds, per world: `sdf_file`, `world_name_in_sdf`, `timeout_sim_sec`, `spawn_candidates` (list of `[x, y]` in `world` frame, each verified collision-free: the circumscribed disc r=0.195 m + 0.10 m margin is inside free space, checked by `gt_grid` in test 12 §T-03), `reachable_seed` (an `[x, y]` known free cell used to flood-fill), `goal_lists` (spec 05). Rule: `rng = numpy.random.default_rng(seed)`; `idx = int(rng.integers(len(spawn_candidates)))`; `yaw = float(rng.uniform(-pi, pi))`; spawn = `(*spawn_candidates[idx], yaw)`. The noise RNG is `default_rng(seed + 1000)`. Seeds for the standard campaign: 1–10.

## 2.8 `compute_metrics` orchestration

`python3 -m vacuum_eval.compute_metrics <run_dir> [--only module,module]`:
1. `run = load_run(run_dir)`; determine `episode_start_t`, `episode_end_t` (§2.1) from `cmd_vel.csv` and `events.csv`; if `run_meta.end_reason` missing, derive it.
2. Run modules in this order, each returning a flat dict that is merged: `resources`, `coverage` (03+10), `trajectory` (04), `navigation` (05), `safety` (06), `responsiveness` (07), `loop_closure` (08), `counters` (§2.2).
3. A module exception is caught: its keys are set to `null`, a note `"<module>: <exception>"` is appended, `status` becomes `partial`.
4. Write `summary.json` and `summary.csv` (one header + one row, keys sorted alphabetically, `notes` joined with `|`).

Always present keys: `experiment, world, method, seed, odom_noise, spawn_x, spawn_y, spawn_yaw, status, end_reason, episode_sim_sec, bringup_sim_sec, wall_elapsed_sec, n_cmd_ticks, n_goals, distance_gt_m, notes`.

`resources` module outputs: `rtf_mean, rtf_p05` (5th percentile), `rtf_min`, `cpu_<G>_mean_pct`, `cpu_<G>_peak_pct`, `rss_<G>_peak_mb` for each group, `ram_used_peak_mb`; all over the episode window. (A11, A12.)

## 2.9 Aggregation and statistics: `aggregate.py`

`python3 -m vacuum_eval.aggregate --root ~/eval_runs/<experiment> --out aggregate.csv [--paired-by seed]`.
- Input: all `summary.csv` with `status ∈ {ok, partial}`; rows with `status: failed` are **counted and reported** (column `n_failed`) but excluded from means.
- Group key: `(world, method, odom_noise)`.
- For each numeric key: `n`, `mean`, `std` (ddof=1; empty if n<2), `median`, `min`, `max`, `ci95_halfwidth = scipy.stats.t.ppf(0.975, n−1) · std / sqrt(n)` (empty if n<2). Success-rate metrics (`nav_success_pct`, `avoid_trial_success_pct`, `lc_*`) additionally get a **pooled** value: `100·Σ successes / Σ attempts` using the count columns `nav_goals_succeeded`, `nav_goals_total`, etc., and a Wilson 95 % interval (z=1.96).
- Method comparison (when ≥2 methods share worlds and seeds): per metric, `scipy.stats.wilcoxon(a, b)` on seed-paired values (requires equal `n ≥ 6`), else `scipy.stats.mannwhitneyu(a, b, alternative="two-sided")`; report `p_value` and Cliff's delta. No multiple-comparison correction; report the number of tests.
- **Repeatability (A13):** reported as `std` and `cv = std / |mean|` per metric.
- **Noise robustness (A15):** run the identical seeds with `--odom-noise 0` and `--odom-noise 1`; aggregate emits `delta_<metric> = mean(noise=1) − mean(noise=0)` per world/method.

## 2.10 Standard campaign (default)

Worlds `apartment, office, corridor(sealed)`; method `frontier`; seeds 1–10; both `odom-noise 0` and `1` → 60 episodes. Estimated 10–20 min each; batch runner `run_batch.py --matrix campaign.yaml` loops sequentially, skipping finished runs, pausing 10 s between runs, and prints a progress table.

## 2.11 Acceptance

See `12_acceptance_tests.md` T-02x. In short: a 3-minute smoke episode (timeout 180 s) in the apartment must produce every file in §0.6 with non-empty `trajectory.csv` (≈1800 rows ±5 %), a final map, and a `summary.json` with `status` ok or partial and all always-present keys.

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-10-20 | Episode starts at first motion command, not at launch | SLAM/Nav2 bring-up varies run to run and is not part of the task |
| 2026-10-20 | Timers for rates use sim time; resource/RTF use wall time | Sim-time rates are exact (30 Hz); RTF is by definition sim/wall |
| 2026-10-20 | Metric math offline from raw files | Re-computable if a definition changes |

## Update 2026-10-21: episode-level statistics (2.9 amendment)

- Unit of analysis is the episode. Rows with `status` `invalid` or `failed` are excluded from statistics and reported as `n_invalid` / `n_failed`.
- Pooled rate metrics (`nav_goals_succeeded`, `trial_success`, `lc_n_true`, `resp_n_met`) get `pooled_pct` plus a cluster (episode-level) bootstrap 95 % CI `cluster_ci_lo`/`cluster_ci_hi` (percentile, B=5000, rng seed in `boot_seed`, `--seed`). Wilson columns are renamed `wilson_naive_lo_pct`/`_hi_pct` and ignore clustering of goals within episodes.
- Continuous metrics keep mean/std/t-CI and add percentile bootstrap `boot_ci_lo`/`boot_ci_hi` over episodes.
- Method comparisons keep Wilcoxon / Mann-Whitney and add Holm-Bonferroni `p_holm` across all comparisons in the run.
- `python3 -m vacuum_eval.plan_sample_size` gives episodes needed (design effect 1+(m-1)ICC; t-based for continuous; `--from-root RUNS --metric KEY` estimates p/sd/ICC) and a wall-time estimate (`--episode-wall-min`, default 45).

## 2026-10-22 addendum: parallel slots, lean episodes, GPU

- `run_episode --slot N` (default 0): ROS_DOMAIN_ID = 10+N (0 for slot 0), GZ_PARTITION=`vacuum_slotN`, ROS_LOCALHOST_ONLY=1. run_meta records slot, ros_domain_id, gz_partition. Preflight refuses only if a process with this slot's GZ_PARTITION exists in /proc/*/environ or `~/eval_runs/.slotN.lock` holds a live PID (stale lock replaced). Shutdown killpg's only this episode's process groups; last resort kills only gz processes carrying this slot's partition (no global pkill).
- `run_batch --parallel K` (or campaign `parallel: K`): K worker slots 0..K-1, each takes the next job; slot i first starts after i*60 s (`--stagger-sec`). Split enforcement and manifest unchanged. `--prebuild-gt` builds every matrix world's GT grid first. GT cache writes are atomic (temp + os.replace).
- `--lean {0,1}` (batch default 1, single run default 0; campaign `lean:`): adds `enable_visualizer:=false enable_legacy_metrics:=false enable_diagnostics:=false` (exploration) / `enable_diagnostics:=false` (sim) and drops /clock and /joint_states from the bag. Recorded as run_meta.lean.
- `--gpu {0,1}` (campaign `gpu:`): passes `render_gpu:=true`; recorded as run_meta.gpu. gpu=1 and gpu=0 results must not be pooled (aggregate grouping should include gpu).
