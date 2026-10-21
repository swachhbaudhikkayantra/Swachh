# 01 — Prerequisites and Fixes

Nothing in specs 02–12 gives trustworthy numbers until this file is done. Each section: **Problem (evidence) → Change (exact) → Verify (command and expected result)**. Evidence marked *[run]* was observed by running on 2026-10-20; *[read]* comes from reading code only and must be reproduced first.

Order: 1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6 → 1.7 → 1.8 → 1.9.

---

## 1.1 Ground-truth pose (DONE 2026-10-20)

**Problem [run]:** `gz_bridge.yaml` bridged `/world/vacuum_world/pose/info`, valid only for `empty_world.sdf`. Parametrising the world name worked (`/world/apartment_world/pose/info` bridged) but **`ros_gz_bridge` drops entity names in `Pose_V` → `TFMessage`**: every `child_frame_id` is empty and every stamp is zero, so the robot cannot be identified.

**Change (implemented):**
1. Removed the `/ground_truth/poses` block from `vacuum_gazebo/config/gz_bridge.yaml`.
2. `vacuum_description/urdf/_gazebo.xacro`: model-level plugin `gz-sim-odometry-publisher-system` (`odom_frame world`, `robot_base_frame base_footprint`, `dimensions 2`, `odom_publish_frequency 30`, topic `/model/vacuum_robot/ground_truth_odom`).
3. `gz_bridge.yaml`: `/model/vacuum_robot/ground_truth_odom` (`gz.msgs.Odometry`) → `/ground_truth/odom_raw` (`nav_msgs/msg/Odometry`).
4. `sim.launch.py` starts `vacuum_eval/ground_truth_node` (§1.2).

**Verified [run]:** spawn at (1.5, −1.0, yaw 0.7) → first ground-truth sample `x=1.500 y=-1.000 yaw=0.700`, i.e. the plugin reports the **absolute world pose**; `/ground_truth/odom` rate = 29.3 Hz in sim time.

**Dynamic obstacles** (spec 09 §9.6) use the same plugin per model with topic `/model/<name>/ground_truth_odom`, bridged to `/ground_truth/model/<name>` (`nav_msgs/Odometry`).

## 1.2 `ground_truth_node` (implemented: `vacuum_eval/vacuum_eval/ground_truth_node.py`)

- Subscribes `/ground_truth/odom_raw` (`nav_msgs/Odometry`, reliable, depth 10).
- Publishes `/ground_truth/odom` (`nav_msgs/Odometry`): `header.stamp` = incoming stamp (node sim clock if zero), `header.frame_id = "world"`, `child_frame_id = "base_footprint"`, pose x, y, yaw (z = 0), twist from finite differences of consecutive samples **in the robot frame** (`vx = (dx·cos(yaw)+dy·sin(yaw))/dt`, `vy = (−dx·sin(yaw)+dy·cos(yaw))/dt`, `wz = wrap(dyaw)/dt`), skipping samples with `dt ≤ 1e-4`.
- Does not publish TF. Logs the first sample once; warns if no sample for > 2 s.

**Verification notes (observed 2026-10-20):** after driving an arc (cmd `vx=0.2, wz=0.3`), wheel odometry composed with the spawn pose differed from ground truth by 0.064 m and the **odometry yaw was 0.419 rad vs 0.537 rad true (22 % under-estimate)**. So `/odom` is not perfect during rotation even without injected noise (wheel slip / caster effects in the sim). Straight-line motion matched to 4 decimals. This is real odometry error that ATE (spec 04) will measure.

## 1.3 Evaluation odometry path with controllable noise (A15, #6, #7, #11)

**Problem [read]:** `vacuum_controller/odometry_noise_node` publishes `/odom_noisy` which nothing consumes; RTAB-Map reads TF `odom→base_footprint` from `diff_drive_controller` (`enable_odom_tf: true`) and `/odom` from `topic_tools relay`. Enabling that node changes nothing. *[run]* Without noise, straight-line `/odom` matches ground truth to 4 decimals, but rotation is under-reported by ~22 % (§1.2 note); translational drift is otherwise tiny, so controlled noise is needed to test SLAM drift correction.

**Design:** one odometry path with the noise node *in* the path.

1. New launch argument on `sim.launch.py` (and forwarded to `controllers.launch.py`): `odom_mode` ∈ `{clean, eval}`, default `clean` (current behaviour, nothing changes).
2. In `odom_mode:=eval`:
   - `ddc_spawner` gets `--param-file <vacuum_eval share>/config/ddc_no_tf.yaml` with content `diff_drive_controller: {ros__parameters: {enable_odom_tf: false}}` so the controller no longer publishes `odom→base_footprint`.
   - The `topic_tools relay` `/diff_drive_controller/odom → /odom` is **not** started.
   - `vacuum_eval/odom_noise_node` is started instead.
3. `odom_noise_node` (replaces `vacuum_controller/odometry_noise_node` for evaluation; do not edit the old one):
   - Subscribes `/diff_drive_controller/odom` (clean, 30 Hz).
   - Parameters (defaults in `eval_defaults.yaml`): `enable_noise` (bool, default false), `seed` (int, default 0), `sigma_scale_lin` = 0.02, `sigma_scale_ang` = 0.03 (persistent scale errors, drawn once per run), `sigma_rw_per_sqrt_m` = 0.02 rad/√m and `sigma_rw_per_sqrt_rad` = 0.03 rad/√rad (heading random walk), `publish_tf` (bool, default true).
   - **Why this model:** the first version put independent relative noise on every 30 Hz increment; *[run]* that produced no visible drift (0.362 vs 0.361 m over a 4 s drive) because independent errors average out. Real wheel odometry error is correlated: a persistent scale error plus a heading random walk.
   - State: noisy pose `(X, Y, Θ)` in the `odom` frame, initialised to the first clean pose. `rng = numpy.random.default_rng(seed)`; the first two draws `z0, z1` give `b_lin = 1 + sigma_scale_lin·z0`, `b_ang = 1 + sigma_scale_ang·z1`.
   - For each clean message compute the increment since the previous clean message **in the previous robot frame**: `(dx, dy, dθ)`, `d = hypot(dx, dy)`. Draw `e1, e2 ~ N(0,1)` (always, in this order, even if noise is off, so the sequence does not depend on the flag). If noise is enabled:
     - `dx' = dx·b_lin`, `dy' = dy·b_lin`
     - `dθ' = dθ·b_ang + sigma_rw_per_sqrt_m·sqrt(d)·e1 + sigma_rw_per_sqrt_rad·sqrt(|dθ|)·e2`
     else `dx'=dx, dy'=dy, dθ'=dθ`. Then `X += cos(Θ)·dx' − sin(Θ)·dy'`, `Y += sin(Θ)·dx' + cos(Θ)·dy'`, `Θ = wrap(Θ + dθ')`.
   - Publishes `/odom` (`nav_msgs/Odometry`, same header stamp, `frame_id odom`, `child_frame_id base_footprint`, noisy pose, twist copied from clean, covariance copied) and, if `publish_tf`, the transform `odom → base_footprint` with the noisy pose and the message stamp.
4. RTAB-Map, Nav2 and the exploration stack are unchanged: they already read `/odom` and TF `odom→base_footprint`.

**Verify:** (a) `odom_mode:=eval enable_noise:=false`: drive 1 m with teleop; `/odom` x equals `/diff_drive_controller/odom` x within 1e-6; `ros2 run tf2_ros tf2_echo odom base_footprint` shows exactly one publisher (`ros2 topic info /tf -v` lists `odom_noise_node` and no `diff_drive_controller` as the odom TF source). (b) `enable_noise:=true seed:=1`: the node logs `b_lin`, `b_ang` at start; drive a straight 2 m: odometry distance differs from ground truth by ≈ `(b_lin−1)·2 m`; the same seed gives the same `b_lin`, `b_ang` in the log on every launch.

## 1.4 Nav2 velocity path (DONE 2026-10-20)

**Problem [read + run]:** (1) `nav2.launch.py` / `nav2_localization.launch.py` remapped controller_server, behavior_server **and** both velocity_smoother ports to `/diff_drive_controller/cmd_vel_unstamped`: the smoother consumed its own output. (2) *[run]* **Nothing subscribes to `/diff_drive_controller/cmd_vel_unstamped`**: `diff_drive_controller` subscribes only to the stamped `/diff_drive_controller/cmd_vel` (`geometry_msgs/TwistStamped`; parameter `use_stamped_vel` is not set in the running controller). Nav2 commands therefore never moved the robot; teleop worked only because `cmd_vel_relay` stamps `/cmd_vel`.

**Change (implemented):**
- controller_server and behavior_server: `cmd_vel → /cmd_vel_nav`.
- velocity_smoother: input `cmd_vel → /cmd_vel_nav`, output `cmd_vel_smoothed → /cmd_vel_smoothed`.
- `vacuum_controller/cmd_vel_relay.py` gained parameter `input_topic` (default `/cmd_vel`); `controllers.launch.py` starts a second instance `cmd_vel_relay_nav` with `input_topic: /cmd_vel_smoothed`. Both publish stamped commands to `/diff_drive_controller/cmd_vel`.
- Same in `nav2_localization.launch.py`.

**Verify [run]:** `/cmd_vel_nav` has one subscriber (velocity_smoother) and publishers controller/behavior/exploration; `/diff_drive_controller/cmd_vel_unstamped` is no longer used; during a goal the robot moves (GT position changes).

## 1.5 Exploration manager fixes (affect #10, #2, #1)

All in `vacuum_exploration/vacuum_exploration/exploration_manager.py` (current line numbers from 2026-10-20; re-grep before editing).

1. **Oscillation detector (line ~221–233, `_odom_callback`).** Problem [read]: `_last_move_time` refreshes only if the robot moved > 0.05 m between two consecutive odom messages (≈1 cm at 30 Hz) so after `oscillation_timeout_sec` = 15 s every goal is cancelled. Change: keep a reference pose `(ref_x, ref_y, ref_t)`; on each odom message, if `hypot(x-ref_x, y-ref_y) >= oscillation_distance` (parameter, 0.30 m, currently unused) then set `ref = (x, y, t)` and `_last_move_time = t`. Reset the reference at the start of each goal. A goal is cancelled as "oscillation" only if `t - _last_move_time > oscillation_timeout_sec` (15 s) **and** the robot is not rotating in place (`|wz| < 0.05 rad/s` from `msg.twist.twist.angular.z`) — rotating recoveries must not trigger it.
2. **Stale result race (`_cancel_goal`, `get_result_async`).** Problem [read]: a result callback from a cancelled goal sets `_goal_result` later and is consumed by the next goal. Change: store the `goal_handle` (or its `goal_id.uuid` bytes) when the goal is sent; in the result callback ignore results whose uuid is not the current goal's; clear `_goal_result` when sending a new goal.
3. **Frontier identity for the blacklist.** Problem [read]: `Frontier.id` is the index in the list from `/frontiers/centroids`, unstable between cycles. Change: blacklist entries store the centroid `(x, y)` and a frontier is considered blacklisted if any entry is within `blacklist_radius` = 0.5 m (new parameter). Keep `id` only for logging.
4. **`raise StopIteration` in the FSM timer (line ~359).** Change: in FINISHED, publish the final status once, publish `/exploration/finished` (`std_msgs/Bool`, true, transient-local QoS depth 1), cancel the timer, and keep the node alive. (The harness, spec 02, ends the episode on this topic.)
5. **Goal events topic (needed by spec 05).** New publisher `/exploration/goal_events` (`std_msgs/String`, JSON, reliable, depth 50). One JSON object per goal **end**, keys exactly: `goal_seq` (int, 1-based), `t_sent`, `t_end` (sim seconds), `x`, `y` (goal position in `map`), `result` (one of `succeeded`, `nav_aborted`, `timeout`, `oscillation`, `canceled_by_manager`, `rejected`), `nav2_error_code` (int, 0 if unknown), `frontier_x`, `frontier_y`. Also publish one event at goal **start** with `result: "started"` and `t_end: null`. `goals_failed` continues to count every result except `succeeded`.
6. **Coverage figure in status.** Keep the existing `coverage_pct` (it is `free/(free+unknown)`) but rename the key in the JSON to `map_free_ratio_pct`, add the old key unchanged too for one release; the evaluation never uses either (spec 03). Vectorise the Python cell counting with numpy (`np.asarray(msg.data, dtype=np.int8)`), because it runs at 10 Hz on maps of tens of thousands of cells.
7. **Completion condition:** unchanged, but add parameter `max_episode_sim_sec` handled by the harness, not the manager.

**Verify:** run exploration in the apartment for 5 min. Expected: goals are no longer all cancelled at ~15 s (look at `/exploration/goal_events` `result` values and durations); `/exploration/status.goals_completed` increases; the robot drives to several distinct frontiers.

## 1.6 `slam.launch.py` `delete_db`

**Problem [read]:** mapping mode always passes `--delete_db_on_start`. **Change:** pass it only if `delete_db:=true` (default true, so default behaviour is unchanged). The harness always sets `database_path:=<run_dir>/rtabmap.db delete_db:=true`.

## 1.7 Metric-relevant simulation settings

1. Spawn is wall-clock timed (3 s timer). The harness must not rely on timers: it waits for readiness (spec 02 §3.5 readiness gates).
2. Add launch arg `headless` to `sim.launch.py`: when true, `gz_args` becomes `-r -s --headless-rendering <world>` (server only, no GUI). Verify the depth camera still produces images headless (`ros2 topic hz --use-sim-time /camera/depth/image_rect_raw` ≈ 30). If headless rendering is not available on this WSL, document it and keep GUI mode with `use_rviz:=false`.
3. `enable_odom_noise` launch arg already exists and refers to the old node; leave it, document that evaluation uses `odom_mode`.

## 1.8 Corridor world sealing and world-name uniqueness

See `09_worlds.md`. Required before any coverage/completeness number from the corridor.

## 1.9 Python tooling

`pip` is not required. `evo`/`pandas`/`skimage` are **not** used by the evaluation code. Optional cross-check only: `python3 -m venv --system-site-packages ~/venvs/eval && ~/venvs/eval/bin/pip install evo`. If pip is not installed, install `python3-venv python3-pip` as root via `wsl.exe -d Ubuntu -u root -e apt-get install -y python3-venv python3-pip`.

---

## Verification notes (fill during implementation)

| Item | Observed value | Date |
|---|---|---|
| `Pose_V` bridge keeps entity names | **No** (child_frame_id empty, stamp 0) → plugin used | 2026-10-20 |
| `/ground_truth/odom` rate (sim time) | 29.3 Hz | 2026-10-20 |
| Which cmd topic moves robot under Nav2 | | |
| Headless rendering works | | |

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-10-20 | Noise node replaces the odom relay and TF source in `odom_mode:=eval` instead of adding a second odom topic | RTAB-Map takes its odometry from TF; a parallel topic would not influence it |
| 2026-10-20 | Noise = persistent scale errors + heading random walk on increments | White noise on the pose or independent per-message noise gives no drift (tested); real wheel odometry error is correlated |
