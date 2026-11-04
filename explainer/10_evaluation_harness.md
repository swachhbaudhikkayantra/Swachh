# 10. The evaluation harness (`vacuum_eval`, without `metrics/`)

Package: `/home/hrishikesh/Swachh/Navigation/Simulation/vacuum_ws/src/vacuum_eval/`
(ROS 2 `ament_python` package, version 0.1.0, license Apache-2.0).
The `vacuum_eval/metrics/` sub-package (the metric formulas) is documented elsewhere. This file covers everything else: the code that starts and stops simulated episodes, records raw data, turns it into a per-episode summary, aggregates many episodes, and builds reports. Where this file needs a fact from `metrics/` (validity rules, health flags) it states only what those modules do when called by the harness.

---

## 1. The big picture

### 1.1 Vocabulary

| Term | Meaning in the code |
|---|---|
| **Episode** | One simulation run of one (world, method, seed, noise setting). Run by `run_episode.py`. Its output is one *run directory*. |
| **Method** | `frontier` (autonomous exploration stack), `scripted_goals` (Nav2 is sent a fixed or generated goal list by `goal_sender`), or `responsiveness` (step-response test of the velocity command path). |
| **Campaign** | A YAML "matrix" file in `config/campaigns/`. `run_batch.py` expands it into the cross product worlds x methods x seeds x odom_noise (x method-specific variants) and runs the episodes. |
| **Slot** | A concurrency lane. Slot N gets its own ROS domain and Gazebo partition so several episodes can run side by side. |
| **Seed** | Integer given per episode. It drives spawn choice, generated goal lists, scenario jitter and odometry noise (Section 4.3). |
| **Validity gate** | A rule in `metrics/validity.py` that marks a finished episode `invalid` (image drops, RTAB-Map stalls). |
| **Health flag** | A per-metric label (`OK`, `LOW_N`, `UNMEASURABLE`, `SUSPECT`, `BAD`, `NA`) from `metrics/health.py`. Written into `summary.json`. Never an exclusion. |
| **Bring-up gate** | A liveness check (G1..G7) that the harness waits on before the episode is allowed to start. |

### 1.2 Data flow

```
campaign YAML --run_batch.py--> N x (python -m vacuum_eval.run_episode ...)  (K slots)
   run_episode.py:  write run_meta.yaml, goals.yaml, gt_map.*   (before launch)
                    start: bag, simulator/stack, bring-up gates, eval_stack (recorder_node), late nodes
                    monitor (1 Hz) -> end_reason
                    shutdown (clean stop of recorder, bag, all processes)
                    compute_metrics.compute()  -> summary.json + summary.csv
   aggregate.py     many summary.csv -> aggregate.csv
   make_report.py   summaries + aggregate.csv -> results.md, metrics_status_update.md, figures/*.png
   paper_tables.py  summary.json of the 4 quick_* campaigns -> paper_values.json, paper_tables.md (+ filled template)
```

### 1.3 Episode lifecycle in one paragraph

`run_batch` builds a command line per episode. `run_episode` computes the spawn pose and goal list from the seed, writes `run_meta.yaml`, starts a `ros2 bag record`, starts the method's launch files as child processes (each in its own session, log to `logs/<name>.log`), waits for gates G1..G3 (clock, controllers, ground-truth odometry), starts the evaluation stack (which contains `recorder_node`), waits for the method's gates (TF, Nav2 action server, map, ...), starts the "late" nodes (goal sender, dynamic obstacle movers, responsiveness test), then polls once per second until an end condition occurs. It then stops the recorder (which writes the final map), stops everything, and calls `compute_metrics.compute()` to write `summary.json` / `summary.csv`.

---

## 2. Concepts in detail

### 2.1 Episode window

The sim-time window used by every metric is decided offline in `compute_metrics.determine_episode`:

* **Start** = time of the first `cmd_vel.csv` row whose `source` is `ctrl_stamped` (the stamped command that reaches `diff_drive_controller`) with `|vx| > 0.01` or `|wz| > 0.01` (`MOTION_EPS = 0.01`). If there is none, the run has `no_motion`.
* **End** = the earliest of:
  * the first `finished_signal` event after the start (`goals_done` if the detail contains "done"/"goals" or the method is `scripted_goals`, otherwise `finished`);
  * `start + episode_timeout_sim_sec` (`timeout`);
  * the "stuck" rule firing (`stuck`);
  * the last trajectory row (`trajectory_end`, which is then relabelled from `run_meta.yaml`'s `end_reason` if that is a harness reason / `timeout` / `stuck`, else `crash`).
* If `run_meta.yaml` carries a harness reason (`crash`, `aborted_by_user`, `bringup_failed`), that reason is used and the end time is clamped to the last trajectory row.
* **Stuck rule** (`find_stuck`): ground truth is resampled every 1 s from the start. It fires when the robot stays within 0.30 m (`STUCK_DIST_M`) of its position at the start of a 180 s window (`STUCK_WINDOW_S`). Rotation in place does not prevent it.

The harness (`monitor`) uses the same helpers live, so the live end condition and the offline end condition agree.

### 2.2 Status values in `summary.json`

| `status` | Set when |
|---|---|
| `ok` | End reason is not a failure reason and no metric module raised. |
| `partial` | At least one metric module raised an exception; its keys are set to `None` and the error is appended to `notes`. |
| `failed` | `end_reason` is `no_motion`, `crash` or `bringup_failed` (`FAILED_REASONS`). |
| `invalid` | An episode that had a start, ran the `validity` module and got `episode_valid == False`, and whose status was `ok` or `partial`. |

`aborted_by_user` is a harness reason but is not in `FAILED_REASONS`, so it does not by itself make the status `failed`.
Statistics (`aggregate.py`, `make_report.py`, `paper_tables.py`) use only `ok` and `partial` episodes. `failed` and `invalid` are counted and listed but excluded.

### 2.3 How an episode becomes `invalid` (validity gates)

Computed in `metrics/validity.compute_validity` during `compute_metrics.compute`. Thresholds come from `config/eval_defaults.yaml` block `validity:`:

| Key | Value | Rule |
|---|---|---|
| `camera_hz` | 30.0 | Expected depth frame rate. |
| `max_img_drop_pct` | 10.0 | Invalid if `img_drop_pct > 10`. `img_drop_pct = 100 * (1 - sum(n_depth in window) / (30 * duration))`, clamped to 0..100. The count `n_depth` comes from `rates.csv`. |
| `max_rtabmap_gap_s` | 5.0 | Invalid if the largest gap between consecutive `loop_events.csv` rows in the window exceeds 5 s. |
| `min_rtabmap_update_frac` | 0.5 | Invalid if the number of RTAB-Map updates in the window is below `0.5 * duration_s`. |

The two RTAB-Map rules apply only if `loop_events.csv` exists and `localization_mode` in `run_meta.yaml` is not `amcl` or `gt`. Invalid reasons are stored in `invalid_reasons` and appended to `notes` as `episode invalid: ...`. `run_episode.finish` also prints a `VALIDITY: VALID/INVALID/UNKNOWN ...` line. `validity` also records `rtf_true_mean` (mean of `rtf.csv`'s `rtf` column) and a `config_hash` (12 hex chars of the config snapshot plus three config files).

Separately, the *live* harness can end an episode early with `end_reason` `stuck`, `timeout`, `crash`, `bringup_failed`, `aborted_by_user`. Those are not "invalid"; `crash` / `bringup_failed` / `no_motion` give status `failed`.

### 2.4 Health flags

Computed last in `compute_metrics.compute` by `metrics/health.compute_health`, using the `health:` block of `config/eval_defaults.yaml` (the frozen copy in `run_meta.yaml`'s `config_snapshot` is preferred when it contains a `health` block). One flag per metric is written as `health_<metric>` plus `health_<metric>_reasons`, plus counters `health_n_ok`, `health_n_bad`, `health_n_suspect`, `health_n_unmeasurable`.

Precedence: `UNMEASURABLE` > `SUSPECT` > `LOW_N` > `BAD` > `OK`; `NA` = metric not applicable (for example `trial_success` outside `avoid*` worlds, `responsiveness_pct` for the `frontier` method). The metrics covered are `coverage_explored_pct, n_goals, n_collisions, avoidance_pct, responsiveness_pct, ate_fixed_rmse_m, rpe_trans_rmse_m_1m, map_completeness_pct, trial_success, nav_success_gt_pct, lc_precision_pct, lc_recall_pct, path_length_ratio_mean, cleaning_efficiency`.

Thresholds in `eval_defaults.yaml`:

| Block | Key | Value | Effect |
|---|---|---|---|
| `min_n` | `goals` | 5 | `LOW_N` if 0 < event count < this |
| | `encounters` | 3 | |
| | `lc_accepted` | 5 | |
| | `lc_revisits` | 3 | |
| | `resp_events` | 10 | |
| `floors` (BAD if below; `ate_fixed_rmse_m` BAD if above) | `nav_success_gt_pct` | 50 | |
| | `coverage_explored_pct` | 70 | |
| | `map_completeness_pct` | 60 | |
| | `ate_fixed_rmse_m` | 0.30 | upper floor |
| | `lc_precision_pct` | 50 | |
| | `avoidance_pct` | 80 | |
| `suspect` | `nav_gt_divergence_pp` | 30 | `SUSPECT` if Nav2-reported success exceeds GT success by more than this |
| | `min_rtf` | 0.15 | `SUSPECT` (LOW_RTF) if `rtf_true_mean` below |
| | `frame_offset_m` | 0.10 | start offset above this marks frame-sensitive metrics `SUSPECT` |
| | `map_align_shift_m` | 0.20 | map alignment shift above this, same effect |

Other reasons seen in `health.py`: `INVALID_EPISODE`, `GT_MISSING`, `MAP_MISSING`, `NO_EVENTS`, `NO_DATA` (all `UNMEASURABLE`); `ODOM_CORRUPTED`, `FRAME_OFFSET`, `RANGE`, `NAV_GT_DIVERGENCE`, `LOW_RTF`, `LC_ROT_BIAS` (`SUSPECT`); `LOW_N:n/min`; `BELOW_FLOOR:...` (`BAD`). The floors are described in the config as pre-registered diagnosis triggers, never exclusion criteria.

### 2.5 Seeds

All derived from the integer `--seed` (the numbers below are what the code does):

| Purpose | Derivation |
|---|---|
| Spawn pose, worlds with `spawn_candidates` | `rng = default_rng(seed)`; pick a candidate index, then yaw ~ U(-pi, pi) (`sample_spawn`). Worlds without candidates spawn at (0, 0, 0) and a note is written. |
| Scenario worlds (`goal_list == scenario`) | `rng = default_rng(seed + 3000)`: spawn = scenario start + U(+-0.10) in x, y and U(+-0.2) in yaw, then one U(0, 2) start delay per dynamic obstacle (`scenario_draws`). |
| Generated goal lists (`random20`, `near_wall`, `long_range`) | `generate_goal_lists(gt, seed + 2000, ...)` from `metrics/navigation.py`. |
| Odometry noise | `odom_noise_seed:=seed + 1000` (also stored as `noise_seed` in `run_meta.yaml`). |
| Bootstrap statistics | Fixed `12345` and `B = 5000` in `aggregate.py` (`--seed`, `--boot-B` can change); `make_report.pooled_cluster_ci` uses `B = 2000`, seed 12345. |

Dev/test seed pools (from `config/worlds.yaml`): dev `1..5`; test `101..110`.

### 2.6 Dev / test split

`config/worlds.yaml` defines `splits.dev`, `splits.test` and `seeds.dev/test`. `run_batch.check_split` refuses a campaign if any world or seed is outside the declared split or inside the other one, and refuses the `test` split without `--confirm-test-split`. A campaign YAML declares its split with `split:`; `--split` on the command line must agree.

* dev worlds: `apartment, empty_room, cluttered_room, avoid_head_on, avoid_cluster, avoid_narrow_gap_wide, avoid_dynamic_cross`
* test worlds: `office, corridor, two_rooms_door, multi_room_loop, maze_dead_ends, symmetric_hall, avoid_narrow_gap, avoid_u_trap, avoid_dead_end, avoid_dynamic_sudden`

### 2.7 Concurrency slots

`--slot N` (given to `run_episode`; `run_batch --parallel K` assigns slots 0..K-1):

| Resource | Slot 0 | Slot N > 0 |
|---|---|---|
| `ROS_DOMAIN_ID` | 0 | 10 + N |
| `GZ_PARTITION` | `vacuum_slot0` | `vacuum_slotN` |
| lock file | `<runs_root>/.slot0.lock` | `<runs_root>/.slotN.lock` |

Every child process also gets `ROS_LOCALHOST_ONLY=1`, `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`, and `CYCLONEDDS_URI=file://$HOME/Swachh/Navigation/cyclone_dds.xml`.
`preflight` returns 2 (episode not started) if a process whose environment holds this slot's `GZ_PARTITION` and whose command line contains `gz` is still running, if the slot lock is held by a live PID (a stale lock with a dead PID is replaced), or if the free space on `runs_root` is under 5 GiB. It only warns if `net.core.rmem_max < 4194304`.
`run_batch.run_jobs` runs jobs on K worker threads, one per slot; each takes the next job from a shared queue; slot `i` delays its first start by `i * stagger` seconds (default 60) so the simulators do not start at once. With K = 1 jobs run in-process, serially, with `pause_sec` (default 10) between episodes.

---

## 3. Command-line entry points

`setup.py` registers these console scripts (all `vacuum_eval.<module>:main`): `ground_truth_node, odom_noise_node, recorder_node, run_episode, compute_metrics, run_batch, goal_sender, responsiveness_test, dynamic_mover, gt_localization_node`. `aggregate`, `make_report`, `paper_tables`, `diagnose`, `check_lc_direction`, `plan_sample_size` are not console scripts; run them as `python3 -m vacuum_eval.<name>`.

### 3.1 `run_batch` (the campaign runner)

`python3 -m vacuum_eval.run_batch --matrix config/campaigns/<file>.yaml [options]`

| Argument | Default | Meaning |
|---|---|---|
| `--matrix` (required) | | Campaign YAML. |
| `--force` | off | Re-run episodes even if finished; also passes `--force` to each episode. |
| `--dry-run` | off | Print each combination as `dry` or `skipped`; start nothing; no manifest written. |
| `--parallel K` | matrix key `parallel`, else 1 | Number of slots. |
| `--stagger-sec` | 60 | Delay between first starts of slots. |
| `--lean 0/1` | matrix `lean`, else 1 | Passed to episodes (disable optional nodes, trim the bag). |
| `--gpu 0/1` | matrix `gpu`, else 0 | Passed to episodes (`render_gpu:=true`). Results with gpu=1 must not be pooled with gpu=0. |
| `--prebuild-gt` | off | Build all worlds' GT grids first (with `--dry-run`: build and exit). |
| `--split dev/test` | matrix `split` | Enforce split (Section 2.6). |
| `--confirm-test-split` | off | Required for the test split. |

Behaviour:
* Return code 2 on a split error.
* Writes `<runs_root>/<experiment>/batch_manifest.json` (campaign path, SHA-256 of the campaign file, git commit, split, time) unless `--dry-run`.
* Combinations = `worlds x methods x seeds x odom_noise`, times *variants* from `variants()`: for `scripted_goals`, `nav_maps` x `goal_lists`; for `responsiveness`, `stacks`; otherwise one.
* The run directory is **not** keyed on noise. So when `odom_noise` is 1 the experiment slug gets a `_noise` suffix (`quick_exploration` with noise 1 is stored under `quick_exploration_noise`).
* An episode is skipped if its `summary.json` exists with `"status": "ok"` (unless `--force`). Note that `partial`, `invalid` and `failed` episodes are therefore re-run on the next invocation.
* Return code of each episode is printed but does not stop the batch; `main` returns 0.

Campaign YAML keys: `experiment, split, worlds, methods, seeds, odom_noise, nav_maps, goal_lists, stacks, timeout_sim_sec, headless, lean, gpu, parallel, runs_root (default ~/eval_runs), pause_sec (default 10)`.

### 3.2 `run_episode` (one episode)

`python3 -m vacuum_eval.run_episode --experiment E --world W --seed S [options]`

| Argument | Default | Meaning |
|---|---|---|
| `--experiment` (required), `--world` (required), `--seed` (required, int) | | Name the run directory. |
| `--method` | `frontier` | `frontier`, `scripted_goals`, `responsiveness`. |
| `--stack` | `bare` | `bare` or `loaded` (responsiveness only). |
| `--nav-map` | `gt` | `gt` or `slam` (scripted_goals). |
| `--localization` | `auto` | `auto`, `slam`, `amcl`, `gt`. `auto` = AMCL if nav-map is gt, else RTAB-Map. `amcl` and `gt` require `--nav-map gt`. |
| `--goal-list` | none | `fixed, random20, near_wall, long_range, scenario, loop_tour`. Default: `scenario` for worlds with a `scenario` entry, else `fixed`. |
| `--odom-noise` | 0 | 0/1. |
| `--headless` | 1 | 0/1. |
| `--timeout-sim-sec` | worlds.yaml `timeout_sim_sec`, else 1200 | Sim-time cap after episode start. |
| `--runs-root` | `~/eval_runs` | Output root. |
| `--force` | off | Re-run even if `summary.json` says `ok`. |
| `--slot` | 0 | Concurrency slot. |
| `--lean` | 0 | 1 = adds `enable_diagnostics:=false` (sim) or `enable_visualizer:=false enable_legacy_metrics:=false enable_diagnostics:=false` (exploration), and drops `/clock` and `/joint_states` from the bag. |
| `--gpu` | 0 | 1 = `render_gpu:=true`. |

Return codes: 0 if `status` is `ok` or `partial`, 1 otherwise, 2 if preflight refused, `SystemExit` for invalid localization combinations.

### 3.3 `compute_metrics` (offline, one run directory)

`python3 -m vacuum_eval.compute_metrics RUN_DIR [--only mod1,mod2] [--gt-dir DIR]`
Recomputes `summary.json` and `summary.csv` from the raw files. Module order: `resources, coverage, trajectory, contact_odom, navigation, safety, responsiveness, loop_closure, validity, counters`, then `health` (last, because it needs the merged dictionary). `--only` restricts modules (health runs only if `health` is listed or `--only` is absent). Returns 3 if status is `failed`, else 0.
The GT grid is cached at `<gt-dir>/<world>.npz` (default `~/eval_runs/_gt`), built from `worlds.yaml` (`sdf_file`, `reachable_seed`) when missing, written atomically (temp file plus `os.replace`) so concurrent builders never expose a partial file.
Always-present summary keys: `experiment, world, method, seed, odom_noise, spawn_x, spawn_y, spawn_yaw, status, end_reason, episode_sim_sec, bringup_sim_sec, wall_elapsed_sec, n_cmd_ticks, n_goals, distance_gt_m, notes`.
`summary.csv` has one header row and one data row with keys sorted alphabetically; `notes` is joined with `|`; None and non-finite become empty; booleans become 0/1.

### 3.4 `aggregate`

`python3 -m vacuum_eval.aggregate --root DIR --out aggregate.csv [--paired-by seed] [--seed 12345] [--boot-B 5000]`
Finds every `summary.csv` under `--root` (recursive), reads `gpu` / `lean` from `run_meta.yaml` if missing, and writes rows of these kinds (column `kind`):

| `kind` | Content |
|---|---|
| `stat` | Per (world, method, odom_noise, gpu, lean) group and per numeric column: n, mean, std, median, min, max, 95 % t-interval half-width, coefficient of variation, percentile-bootstrap CI of the mean, `n_failed`, `n_invalid`. Uses `ok`/`partial` rows only. |
| `pooled` | For pairs (`nav_goals_succeeded`/`nav_goals_total`, `trial_success`/1, `lc_n_true`/`lc_n_accepted`, `resp_n_met`/`resp_n_events`): pooled percentage, episode-level cluster-bootstrap CI (`cluster_ci_lo/hi`), and a naive Wilson interval with a note that it ignores clustering of goals inside episodes. |
| `compare` | For two methods in the same world, noise, gpu, lean: Mann-Whitney U two-sided, or Wilcoxon signed-rank when `--paired-by` is given and both sides have equal n >= 6; Cliff's delta; Holm-adjusted p over all tests (`p_holm`, `n_tests`). |
| `noise_delta` | Mean with noise 1 minus mean with noise 0 for each metric (`delta_<metric>`). |

Groups with different `gpu` or `lean` are never pooled or compared (covered by tests). Method comparison output is produced only when a group has two methods; the project notes call method comparison "on hold" in `CLAUDE.md`.

### 3.5 `make_report`

`python3 -m vacuum_eval.make_report --root DIR [--root DIR ...] --out OUTDIR`
Per root it loads summaries and uses `<root>/aggregate.csv` if present (otherwise builds and writes it). Writes into `OUTDIR`:
* `results.md`: tables for the core metrics (`CORE`, 17 rows keyed to the pre-registration numbers) and additional metrics (`EXTRAS`, A1..A14), pooled-rate tables, noise on/off tables, Holm-adjusted method comparisons, figure links, a "Metric health" table (counts per status, top reasons, fallback metrics to report when a metric is UNMEASURABLE / LOW_N / SUSPECT), and "Reported regardless of outcome" (status counts per experiment/world/noise, list of invalid/failed episodes, contents of any `deviations.md` found in the roots).
* `metrics_status_update.md`: headline value per metric with a world-cluster bootstrap CI (resample worlds, then seeds).
* `figures/`: `coverage_vs_time.png`, `ate_box.png`, `rpe_box.png`, `collisions.png`, `nav_success.png` (as produced by `make_figures`/`fig_*`).
Rows with fewer than `MIN_N = 3` valid episodes are marked insufficient data.

### 3.6 `paper_tables`

`PYTHONPATH=<src>/vacuum_eval python3 -m vacuum_eval.paper_tables --root DIR --out OUTDIR [--template T.md --filled F.md]`
Reads `summary.json` files from `<root>/{quick_exploration_noise, quick_navigation, quick_avoidance, quick_responsiveness}/<world>/<variant>/seed_NNN/` and `<root>/_gt/<world>.npz`. Computes per-world and pooled statistics with the repository's own bootstrap helpers (same seed 12345 and B as `aggregate`), plan-latency from `goal_events`/`plans`, RTAB-Map update times parsed from logs, memory, etc. Writes `paper_values.json` and `paper_tables.md` (including a cross-check of its means against each campaign's `aggregate.csv`, listing mismatches). With `--template`, replaces `{{path|fmt}}` tokens (`f0..f9`, `int`) from the computed values and writes `--filled`. Exit code: 1 if any cross-check mismatch, 2 if template tokens are missing (`{{MISSING:path}}` is left in the output), otherwise 0. It counts only `ok`/`partial` episodes. It does not compute anything by hand-typed values.

### 3.7 Small utilities

| Module | Usage | What it does |
|---|---|---|
| `diagnose` | `python3 -m vacuum_eval.diagnose RUN_DIR [--png out.png]` | Read-only explanation of a run: time moving / rotating / stationary, each goal's outcome and duration, counts of planner/controller/TF failure messages found in `logs/*.log`, localization-versus-navigation numbers from `summary.json`, stuck spots (>= 8 s within 0.15 m), a ranked list of likely causes, and the health table. `--png` draws the trajectory (colour = speed), stuck spots and goals. |
| `check_lc_direction` | `python3 -m vacuum_eval.check_lc_direction RUN_DIR [RUN_DIR ...]` | Compares the logged RTAB-Map loop-closure transform against ground truth under two conventions (`ref_to_loop`, `loop_to_ref`). Exit 0 if exactly one convention has median translation error < 0.10 m and rotation < 5 deg; exit 2 if ambiguous or no data. Prints the line to put in `eval_defaults.yaml` (`lc_transform_convention`). |
| `plan_sample_size` | `python3 -m vacuum_eval.plan_sample_size --metric-kind proportion --p P --goals-per-episode M --icc R --target-halfwidth H` (or `--metric-kind continuous --sd SD ...`, or `--from-root RUNS --metric KEY`; `--episode-wall-min`, default 45) | Number of episodes for a target CI half-width: design effect `1 + (M-1)*ICC` for clustered proportions, or iterative t-interval for continuous metrics; ICC estimated by one-way ANOVA. Prints the wall-time estimate. |

---

## 4. Episode mechanics (low level)

### 4.1 Run directory layout

`<runs_root>/<experiment>/<world>/<method_dir>/seed_<NNN>/` where `<method_dir>` is `frontier`; `scripted_goals[_<goal_list>][_slam]`; or `responsiveness_<stack>`.

| File / folder | Written by | Content |
|---|---|---|
| `run_meta.yaml` | `run_episode.write_meta`, updated by `finish` | experiment, world, method, seed, spawn pose, odom noise flag and parameters, `noise_seed`, git commit and dirty flag, full `config_snapshot` of `eval_defaults.yaml`, start wall time, timeout, headless, slot, ROS domain, GZ partition, lean, gpu, gz and python versions, `run_notes`; method extras (`goal_list, nav_map, localization_mode, nav_variant, t_world_map, dynamic_obstacles` / `stack`); after the run `end_reason`, `wall_elapsed_sec`. |
| `events.csv` | harness and recorder (shared, appended) | Columns `t, t_rel, event, detail`: `harness_started`, `gate_ok`/`gate_failed`, `amcl_initial_pose_sent`, `recorder_started`, `first_gt_sample`, `first_est_sample`, `episode_start`, `finished_signal`, `rtabmap_stalled`, `stuck_detected`, `timeout_reached`, `process_exited`, `harness_error`, `stopping`, `stop_received`, `contact_publishers`, `contact_topic_alive`, `ground_contacts_dropped`, `final_map_missing`/`final_map_error`, `recorder_stopped`. |
| `trajectory.csv` | recorder, 10 Hz | `gt_x gt_y gt_yaw gt_vx gt_wz`, `odom_*`, `est_x est_y est_yaw est_ok est_interp` (pose of `base_footprint` in `map` from TF), `wall_t`. |
| `cmd_vel.csv` | recorder | `source` (`teleop`, `nav`, `smoothed`, `ctrl_stamped`), `vx vy wz`, `wall_t`. |
| `goal_events.csv` | recorder | `src` (`explore`, `scripted`, `nav2_status`, `behavior_spin/backup/wait`), `goal_seq`, `event`, `result`, `x y`, `nav2_error_code`, `uuid`. |
| `feedback.csv`, `plans.csv` | recorder | Nav2 feedback (distance remaining, recoveries, navigation time); every `/plan` (length, start, end). |
| `rates.csv` | recorder, 1 Hz | Per-second message counts: `n_odom n_depth n_color n_cmd_nav n_cmd_smoothed n_tf_map_odom n_scan n_plan`. |
| `collisions_raw.csv` | recorder | Contacts from chassis, camera and camera_mount sensors (ground-plane contacts are dropped and counted). |
| `loop_events.csv` | recorder, per `/rtabmap/info` | `ref_id, loop_closure_id, proximity_detection_id`, GT pose, estimated pose, loop-closure transform. |
| `dyn_obstacles.csv` | recorder (only if dynamic models given) | Pose and velocity of each dynamic model. |
| `rtf.csv` | recorder, 1 Hz wall timer | `wall_dt, sim_dt, rtf`. |
| `resources.csv` | recorder, 1 Hz | Total CPU/RAM and CPU/RSS per process group (`gz, rtabmap, nav2, bridge, explore, eval, other_ros`). |
| `responsiveness_events.csv` | `responsiveness_test` | Section 4.5. |
| `maps/map_<t_rel>.npz` | recorder | `/rtabmap/map` snapshot every `map_snapshot_period_sec` (5 s sim time). |
| `maps/final_map.{npz,pgm,yaml}` | recorder on stop | Last map received. |
| `goals.yaml` | `run_episode` (scripted_goals) | The goal list `[{x,y,yaw}, ...]`. |
| `gt_map.pgm` / `gt_map.yaml` | `run_episode` (scripted_goals with `--nav-map gt`) | Ground-truth occupancy map for Nav2's map server. |
| `bag/` | `ros2 bag record` | sqlite3 bag of the topics in `BAG_TOPICS`. |
| `rtabmap.db` | exploration/SLAM launch | RTAB-Map database (frontier, loaded stack, slam). |
| `logs/<name>.log` | `Proc` | stdout/stderr of each child (`bag, sim, nav2, map_server, gt_localization, slam, explore_stack, eval_stack, goal_sender, dynamic_mover_<name>, responsiveness_test`). |
| `summary.json`, `summary.csv` | `compute_metrics.write_summary` | Section 3.3. |

Campaign-level: `<runs_root>/<experiment>/batch_manifest.json`, `<runs_root>/.slotN.lock`, `<runs_root>/_gt/<world>.npz`.

### 4.2 Starting an episode (in order)

1. `run_one`: set the slot environment, `preflight`, acquire slot lock (released in `finally`).
2. If `summary.json` has `status: ok` and no `--force`: print "skip (finished)" and return 0.
3. Choose spawn (Section 2.5); resolve the SDF (`resolve_sdf`, for non-frontier methods); set the timeout; for `scripted_goals` write `goals.yaml` and, for `--nav-map gt`, export `gt_map.*` (the GT grid is built from the SDF if not cached). For generated lists the GT grid is needed.
4. `write_meta` then event `harness_started`; `method_plan` builds the process plan.
5. Start the bag recorder, then each stack process, sleeping until its `delay_s` after the first stack process.
6. Gates (each waits up to its budget polling every 2 s, logging `gate_ok` or `gate_failed`):

| Gate | Check | Budget |
|---|---|---|
| G1_clock | `/clock` seconds increase over 3 s | 120 s |
| G2_controllers | `joint_state_broadcaster` and `diff_drive_controller` both active | 120 s |
| G3_gt_odom | one message on `/ground_truth/odom` | 120 s |
| (then `eval_stack` is started) | | |
| G4_tf | `tf2_echo map base_footprint` shows a translation | up to 120 s each, within a 240 s shared budget |
| G5_nav | `/navigate_to_pose` action exists | |
| G6_map | one `/rtabmap/map` message | |
| G6_map_server | one `/map` message | |
| G7_rtabmap_alive | >= 3 `/rtabmap/info` messages in 30 s (added automatically when G6_map is used) | |
| initialpose | not a check: publishes `/initialpose` for AMCL | |

7. If any gate fails: `end_reason = bringup_failed`. Otherwise start the "late" processes (goal sender, dynamic movers, responsiveness test), then `monitor`.

Process plans (`method_plan`):

| Method | Stack processes | Gates | Late processes |
|---|---|---|---|
| `frontier` | `ros2 launch vacuum_exploration exploration.launch.py` (with spawn, odom_mode eval, database path, noise args) | G4, G5, G6 (+G7) | none |
| `scripted_goals`, localization `amcl` (default for gt map) | `sim` (`vacuum_bringup sim.launch.py`), `nav2` (`nav2_localization.launch.py` with `map_path`, delay 12 s) | G5, initialpose, G4, G6_map_server | `goal_sender` |
| `scripted_goals`, localization `gt` | `sim`, `nav2` (12 s), `map_server` (14 s), `gt_localization_node` (12 s) | G5, G4, G6_map_server | `goal_sender` |
| `scripted_goals`, `--nav-map slam` | `sim`, `slam` (`vacuum_slam slam.launch.py`, 12 s), `nav2` (20 s) | G4, G5, G6 (+G7) | `goal_sender` |
| any scripted world with `dynamic_obstacles` | as above, simulator gets an extra bridge config | | plus one `dynamic_mover` per obstacle |
| `responsiveness` `bare` | `sim` only | none | `responsiveness_test` |
| `responsiveness` `loaded` | exploration stack with `start_manager:=false` | G4, G5, G6 (+G7) | `responsiveness_test` |

Every command runs through `bash -c "<ROS env>; exec <cmd>"` in a new session so it can be signalled as a process group.

### 4.3 Monitoring and ending an episode

`monitor` polls every 1 s and returns the first of:

| `end_reason` | Condition |
|---|---|
| `aborted_by_user` | SIGINT received by the harness (a handler is installed during monitoring), or `KeyboardInterrupt`. Stop an episode or batch with `kill -INT <harness PID>`. |
| `crash` | A critical process (the stack, `eval_stack`) has exited. Late processes are non-critical. |
| `goals_done` / `finished` | A `finished_signal` row in `events.csv` (from `/eval/done` or `/exploration/finished`). `goals_done` if the detail contains "done". |
| `timeout` | Latest trajectory time minus episode start >= `timeout_sim_sec`. |
| `stuck` | `find_stuck` fires (Section 2.1). |
| `bringup_failed` | A gate failed or the harness raised an exception. |

Side effect: if `loop_events.csv` stops growing for 20 s, an `rtabmap_stalled` event is written (informational; the validity rule is applied offline).

### 4.4 Stopping (`shutdown`) and finishing

1. Publish `std_msgs/Empty` once on `/eval/stop`; wait up to 30 s for the `recorder_stopped` event. The recorder writes the final map, contact diagnostics and closes its files.
2. SIGINT the bag recorder, wait up to 20 s.
3. SIGINT every process group (stack, late, eval stack, bag) and wait up to 15 s in total.
4. SIGKILL every process group.
5. Last resort: SIGKILL any process whose environment has this slot's `GZ_PARTITION` and whose command line contains `gz`.
6. `finish`: store `end_reason` and `wall_elapsed_sec` in `run_meta.yaml`, run `compute_metrics.compute`, write `summary.json` / `summary.csv`, print status and the `VALIDITY:` line. An invalid result changes `status` to `invalid` inside `compute` (Section 2.3).

### 4.5 Nodes the harness starts

| Node (console script) | Role |
|---|---|
| `recorder_node` (via `launch/eval_stack.launch.py`; args `run_dir`, optional `extra_models`; sets `use_sim_time`) | Writes the raw CSVs above. Parameters: `run_dir` (required), `sample_hz` 10, `map_snapshot_period_sec` 5, `robot_model_name` `vacuum_robot`, `extra_models`. Uses a 2-thread executor and puts the sampling timer in its own callback group (the code comment says the TF lookups otherwise stalled the other subscriptions and under-counted the 30 Hz image topics). The first non-zero `ctrl_stamped` command writes `episode_start`. `/eval/stop` triggers finalisation. |
| `ground_truth_node` | Republishes `/ground_truth/odom_raw` as `/ground_truth/odom` (frame `world`, child `base_footprint`) with twist from finite differences. |
| `odom_noise_node` | Sits between `/diff_drive_controller/odom` and `/odom` plus the `odom -> base_footprint` TF. With noise on: persistent scale errors `b_lin = 1 + 0.02*N(0,1)`, `b_ang = 1 + 0.03*N(0,1)` drawn once, plus per-message random-walk heading noise proportional to `sqrt(distance)` and `sqrt(angle)` (0.02 and 0.03). With noise off the output equals the input. The random draws are always consumed. |
| `gt_localization_node` | Publishes TF `map -> odom` from ground truth (`T_map_world * T_world_base * inv(T_odom_base)`), 30 Hz; used by `--localization gt`. |
| `goal_sender` | Sends `NavigateToPose` goals from `goals_file`, one at a time, converting world coordinates to map coordinates with `t_world_map`. Parameters: `goal_timeout_sim_sec` 120, `inter_goal_wait_sec` 1. Publishes JSON on `/eval/goal_events` (`started`, `ended` with result `succeeded`, `nav_aborted`, `canceled`, `timeout`, `rejected`) and latches `/eval/done` true after the last goal. |
| `dynamic_mover` | Drives a Gazebo model between waypoints through `/model/<name>/cmd_vel` at `speed`, after `start_delay_s` (harness passes the world's `start_delay_s` plus the seeded random delay). Optional trigger `robot_x_beyond:<x>`. |
| `responsiveness_test` | Parameters `n_trials` 10, `v_step` 0.2, `wz_step` 0.5, `settle_s` 3, `run_s` 1.5, `output_file`. Waits for the robot to be still (|vx| <= 0.02, |wz| <= 0.05) for `settle_s`, publishes a forward or rotate step on `/cmd_vel`, records sim-time and wall-time latency until the ground-truth speed reaches half the step (`cmd_motion`), holds for `run_s`, then publishes zero and records latency to stillness (`stop`). Trials alternate forward (direction alternates +/-) and rotate; a missed response after 1.5 s (3 x 0.5 s deadline) is recorded with an empty latency. Writes `responsiveness_events.csv` (`trial, variant, event, t_a, t_b, latency_s, wall_t_a, wall_t_b, wall_latency_s`) and latches `/eval/done`. |

---

## 5. Configuration files (`config/`)

| File | Content |
|---|---|
| `eval_defaults.yaml` | All thresholds: grid resolution 0.05 m, robot body z band 0.03..0.30 m, inscribed radius 0.125 m, grid margin 0.50 m, swath width 0.25 m, collision gap 0.5 s, contact-odometry corruption 15 deg, encounter distance 0.50 m, response deadlines (cmd motion 0.5 s, stop 0.5 s, goal motion 2.0 s, obstacle 1.0 s), loop-closure tolerances (position 0.30 m, yaw 30 deg, min time gap 30 s, registration 0.10 m / 5 deg, transform convention `loop_to_ref`), `episode_timeout_sim_sec` 1200, `odom_noise` sigmas (0.02, 0.03, 0.02, 0.03), `validity` (Section 2.3) and `health` (Section 2.4). A copy is frozen into each `run_meta.yaml`. |
| `worlds.yaml` | `splits`, `seeds`, and for 9 worlds (`apartment, office, corridor, empty_room, cluttered_room, two_rooms_door, multi_room_loop, maze_dead_ends, symmetric_hall`): `split`, `sdf_file`, `world_name_in_sdf`, `timeout_sim_sec`, `reachable_seed`, `spawn_candidates`, `wall_models`, `goal_lists` (`fixed` in all nine; `loop_tour` in six). `random20`, `near_wall`, `long_range` lists are generated, not stored. |
| `worlds_scenarios.yaml` | Eight avoidance worlds (`avoid_head_on, avoid_narrow_gap, avoid_narrow_gap_wide, avoid_u_trap, avoid_cluster, avoid_dead_end, avoid_dynamic_cross, avoid_dynamic_sudden`): `sdf_file`, `world_name_in_sdf`, `timeout_sim_sec` 120, `reachable_seed`, `scenario.start/goal`, and for the two dynamic ones `dynamic_obstacles` (size, waypoints, speed, start delay). Merged into the worlds map by `compute_metrics.load_worlds_cfg`. |
| `ddc_no_tf.yaml` | `diff_drive_controller.ros__parameters.enable_odom_tf: false`; loaded when `odom_mode:=eval` so that `odom_noise_node` publishes the odom TF. |
| `campaigns/*.yaml` | The ten campaign matrices below. |

### Campaigns

| File | Experiment | Split | Worlds | Method (variant) | Seeds | Noise | Timeout (sim s) | Other |
|---|---|---|---|---|---|---|---|---|
| `dev_tuning.yaml` | dev_tuning | dev | apartment, empty_room, cluttered_room | frontier, scripted_goals (fixed list) | 1-5 | 0 | 300 | |
| `quick_exploration.yaml` | quick_exploration | test | office, multi_room_loop, maze_dead_ends | frontier | 101-103 | 1 | 450 | lean 1, gpu 0 |
| `quick_navigation.yaml` | quick_navigation | test | office, two_rooms_door, maze_dead_ends | scripted_goals, nav_map gt, goal_list random20 | 101, 102 | 0 | 900 | lean 1, gpu 0 |
| `quick_navigation_extra.yaml` | quick_navigation | test | same | same | 103, 104 | 0 | 900 | same experiment name so results pool with `quick_navigation` |
| `quick_avoidance.yaml` | quick_avoidance | test | avoid_u_trap, avoid_dynamic_sudden | scripted_goals, goal_list scenario | 101-103 | 0 | 300 | lean 1, gpu 0 |
| `quick_responsiveness.yaml` | quick_responsiveness | test | office | responsiveness, stacks bare + loaded | 101, 102 | 0 | 300 | lean 1, gpu 0 |
| `final_exploration.yaml` | final_exploration | test | office, corridor, two_rooms_door, multi_room_loop, maze_dead_ends, symmetric_hall | frontier | 101-110 | 0 and 1 | 600 | |
| `final_navigation.yaml` | final_navigation | test | office, corridor, two_rooms_door, multi_room_loop, maze_dead_ends | scripted_goals, nav_map gt, goal_lists random20 + long_range | 101-110 | 0 | 1200 | |
| `final_avoidance.yaml` | final_avoidance | test | avoid_narrow_gap, avoid_u_trap, avoid_dead_end, avoid_dynamic_sudden | scripted_goals, nav_map gt | 101-110 | 0 | 300 | |
| `final_responsiveness.yaml` | final_responsiveness | test | office | responsiveness, stacks bare + loaded | 101-103 | 0 | 300 | |

Notes: the `quick_*` seed lists carry comments saying they were cut for the four-hour plan, and `quick_navigation_extra` was added at the user's request (comments in the files). Because noise-on episodes get a `_noise` slug, `quick_exploration` with noise 1 lands in `quick_exploration_noise`, which is the folder `paper_tables.py` reads.

### Packaging

`setup.py` installs `config/eval_defaults.yaml, ddc_no_tf.yaml, worlds.yaml, worlds_scenarios.yaml` and `launch/eval_stack.launch.py` into the package share directory (campaign YAMLs are not installed; run them by path). `package.xml` (format 3) declares exec dependencies `rclpy, geometry_msgs, nav_msgs, std_msgs, tf2_msgs, tf2_ros`, test dependency `python3-pytest`, build type `ament_python`. `setup.cfg` only sets the script install directory to `lib/vacuum_eval`. Several modules also import packages not listed in `package.xml` (`numpy, scipy, yaml, psutil, matplotlib`, `nav2_msgs`, `ros_gz_interfaces`, `rtabmap_msgs`, `action_msgs`); this is a fact about the imports, not a statement that they are missing from the machine.

---

## 6. Unit tests (`test/`, 27 files)

Run them with pytest from the package directory, with `vacuum_eval` importable (installed workspace, or `PYTHONPATH=<this package directory>`):

```
cd /home/hrishikesh/Swachh/Navigation/Simulation/vacuum_ws/src/vacuum_eval
python3 -m pytest test            # whole suite
python3 -m pytest test/test_run_batch.py -q   # one file
```

(There is no pytest configuration file in the package; `python3-pytest` is the declared test dependency. `test_worlds_yaml.py` and `test_run_batch.py` read the SDF world files of the sibling `vacuum_gazebo` package. `goal_sender.py` and `dynamic_mover.py`, imported by `test_nodes_import.py`, import `rclpy`, so that file needs a ROS Python environment. No test starts a simulator. This section was not verified by actually running the suite.)

| File | What it tests |
|---|---|
| `test_aggregate.py` | Wilson interval, group stats and the CLI, method comparison and noise delta, Holm adjustment against a hand value, cluster bootstrap coverage, exclusion of invalid episodes and key sets, `gpu`/`lean` groups not pooled or compared. |
| `test_check_lc_direction.py` | `closure_errors` / `verdict` pick the right convention (both directions), ambiguous or empty data gives no winner, `--help` exits 0. |
| `test_compute_metrics.py` | Episode start and counters, `no_motion`, finished signal, timeout, stuck (static and spinning), not stuck when moving, summary files and always-present keys, a failing module sets keys to None and status `partial`. |
| `test_coverage.py` | Swept-area coverage oracles: straight line, same path twice, rotation in place, boustrophedon, incremental computation, coverage from a trajectory, reachable-area headline keys. |
| `test_geometry.py` | Box/disc clearance geometry: touching, gap, overlap, corner gap, 45-degree box, crossing, disc, vectorised, obstacle loading from SDF. |
| `test_gt_grid.py` | Ground-truth grid from SDF: room area, rug not an obstacle, not-sealed rooms, unsupported shapes, link/collision pose composition, save/load/export determinism, CLI, map alignment against an exact map, missing final map, shifted and half-unknown maps, spawn transform. |
| `test_gt_localization.py` | `compose_map_to_odom` for identity, odometry offset (translation, rotation) and map origin shift/rotation. |
| `test_health.py` | Health classification: OK and counts, NA, LOW_N, UNMEASURABLE, SUSPECT, BAD, and precedence. |
| `test_loop_closure.py` | True/false closures, revisit without closure, helpers and proximity, tight vs loose tolerance, yaw tolerance default, registration-based correctness, transform convention parameter, error medians (and null without columns). |
| `test_make_report.py` | `make_report` builds `results.md` etc. from a synthetic root, and handles an empty root. |
| `test_navigation.py` | Navigation success counts, corridor shortest path, wall detour and path-length ratio, goal inside obstacle skipped, energy proxy, curvature, goal-list determinism, canceled counted as failure and truncated goals excluded, GT success tolerances. |
| `test_nodes_import.py` | Pure helpers of `goal_sender` (`world_to_map`) and `dynamic_mover` (`velocity_towards`, `parse_trigger`, step logic). |
| `test_oracle_contact_odom.py` | Known-answer oracle for contact-odometry slip: slip detected, no collisions, contact without slip, contact outside the episode ignored. |
| `test_oracle_gt_grid_swept.py` | Known-answer oracles for GT grid area (rug, overhead), wall gap not sealed, swept area for a straight line, quarter arc and repeated line. |
| `test_oracle_loop_closure.py` | Known-answer precision/recall for the loop-closure module, yaw tolerance and default tolerances. |
| `test_oracle_trajectory.py` | Hand-computed oracles for ATE (translation offset, rotation, aligned vs Kabsch with noise), RPE (scale error, heading drift on a circle) and a replay of a real run's distance and odometry ATE. |
| `test_paper_tables.py` | `paper_tables` helpers on synthetic data: integral and fractional GT success counts, pooled rate values, contributing-episode counting, missing values, mean/SD, template fill and missing tokens. |
| `test_parallel_slots.py` | `slot_env` values, lock behaviour, partition scan of `/proc`, lean bag topics, `run_jobs` slot assignment, atomic GT cache write. |
| `test_plan_sample_size.py` | Hand-checked proportion and continuous sample sizes, CLI output, ICC estimate. |
| `test_resources.py` | Resource metrics inside the episode window, and missing resource files. |
| `test_responsiveness.py` | Latency met and goal-motion, missing and late responses, response-start rule with field of view, obstacle response latency, rate-floor gap, wall-clock latency primary and its fallback note. |
| `test_run_batch.py` | Cross-split campaign refused, test split needs `--confirm-test-split`, every campaign YAML in `config/campaigns/` is valid (split check, world SDF exists, known method, dry run returns 0), at least five campaigns present. |
| `test_run_episode_plan.py` | Pure planning code of `run_episode`: command lines for frontier (noise flags), scripted gt/slam, dynamic obstacles (bridge and mover), responsiveness; meta extras; scenario draws deterministic and bounded; goal selection and YAML; generated goals deterministic; GT map export call; initial-pose command and directory names; localization `gt` plan. |
| `test_safety.py` | Collision/encounter logic: event grouping, wall clearance, collision-free and contact encounters, no-encounter null, geometry fallback with dynamic obstacles, self-contact filtered, exact geometry used vs grid, SDF path resolution, config matches SDF world name. |
| `test_trajectory.py` | ATE/RPE on identical, offset and drifting trajectories, spawn transform, insufficient motion, synthetic noise odometry, rigid alignment recovery, RPE function with gaps, AMCL keys. |
| `test_validity.py` | Valid run, image drop, RTAB-Map stall, drop clamping and mean depth rate. |
| `test_worlds_yaml.py` | T-035: every spawn candidate and goal in `worlds.yaml` is free and reachable according to the GT rasteriser (one test per world), and the dev/test splits are disjoint and complete. |

---

## 7. Quick recipes (what the code supports)

```
# list what a campaign would run, without starting anything
python3 -m vacuum_eval.run_batch --matrix config/campaigns/quick_navigation.yaml --dry-run --confirm-test-split

# run it on two slots (tmux recommended for long runs)
python3 -m vacuum_eval.run_batch --matrix config/campaigns/quick_navigation.yaml --parallel 2 --confirm-test-split

# one episode by hand
python3 -m vacuum_eval.run_episode --experiment demo --world office --method frontier --seed 101 --odom-noise 1

# recompute a summary after changing nothing but the code of a metric
python3 -m vacuum_eval.compute_metrics ~/eval_runs/demo/office/frontier/seed_101

# aggregate and report
python3 -m vacuum_eval.aggregate --root ~/eval_runs/quick_navigation --out ~/eval_runs/quick_navigation/aggregate.csv
python3 -m vacuum_eval.make_report --root ~/eval_runs/quick_navigation --out ~/report_nav

# stop a running episode or batch cleanly (do not pkill by pattern)
kill -INT <harness PID>
```

---

**One-line summary:** `vacuum_eval` turns a campaign YAML into seeded, slot-isolated simulation episodes (bring-up gates, recorder, monitored stop), writes a fixed run-directory of raw CSVs, computes `summary.json` with validity gating and health flags, and aggregates/reports them, all covered by 27 pytest files that never launch a simulator.
