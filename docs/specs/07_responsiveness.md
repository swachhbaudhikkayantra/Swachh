# 07 — Responsiveness (#5)

"% responsiveness of the system" = the share of timed reaction events that completed within their deadline. This file defines the events, how each latency is measured, the deadlines, and the percentage.
Depends on: 00, 01 (ground truth), 02 (`trajectory.csv`, `cmd_vel.csv`, `rates.csv`), 05 (goal events), 06/09 (dynamic obstacle scenario).
Module: `vacuum_eval/metrics/responsiveness.py`; node: `responsiveness_test.py`.

---

## 7.1 Why not reuse the existing latency code

`vacuum_controller` diagnostics subtract ROS (sim) stamps from a monotonic wall clock. Under the unstable real-time factor (spec 00 §0.1) that gives meaningless numbers. All latencies here are **sim-time differences** of events observed at message level.

## 7.2 Event types, measurement, deadlines

Deadlines are in `eval_defaults.yaml` (`deadline_*`). The user accepted 0.5 s as the general deadline; per-event values below are the proposed concrete settings (change them in one place if needed).

| Event id | Meaning | Start event `t_a` | Response event `t_b` | Deadline |
|---|---|---|---|---|
| `cmd_motion` | Motion command → robot moves | `responsiveness_test` publishes a step command from standstill (`/cmd_vel` Twist `vx=0.2`, `wz=0`; or `vx=0, wz=0.5` for the rotation variant) at sim time `t_a` (stamped with the node clock immediately before `publish`) | first `/ground_truth/odom` message after `t_a` with `gt_vx ≥ 0.10` (forward; 50 % of 0.2) or `|gt_wz| ≥ 0.25` (rotation; 50 % of 0.5) | 0.5 s |
| `stop` | Stop command → robot stops | step to `(0, 0)` published while moving at steady state (≥ 1.0 s after motion onset) | first GT message with `|gt_vx| ≤ 0.02 and |gt_wz| ≤ 0.05` | 0.5 s |
| `goal_motion` | Navigation goal accepted → robot moves | `goal_events` row `src ∈ {explore, scripted}, event=started` time | first `trajectory.csv` row after `t_a` with `|gt_vx| ≥ 0.05` or `|gt_wz| ≥ 0.10` (0.1 s resolution) | 2.0 s |
| `obstacle` | Obstacle enters danger zone → robot reacts | `t_a` from §7.3 | first `cmd_vel.csv` row (`source=ctrl_stamped`) after `t_a` with `vx ≤ 0.7·v_ref` or `|wz| ≥ 0.3`, where `v_ref` = mean `ctrl_stamped` `vx` over `[t_a − 1.0, t_a]`; if `v_ref < 0.05` the event is discarded | 1.0 s |

Latency `L = t_b − t_a` (sim seconds). An event that never gets a response within `3 × deadline` has `L = null` and counts as **missed** (not met).

## 7.3 Obstacle-appearance time `t_a` (from ground truth only)

For scenario `avoid_dynamic_sudden` and `avoid_dynamic_cross` (spec 09 §9.5/9.6), for each trajectory row: dynamic obstacle position `o` (from `dyn_obstacles.csv`), robot pose `(x, y, ψ)`.
`t_a` = the first row where **all** hold: (i) clearance from robot body to the obstacle (spec 06 §6.5) `≤ 1.5 m`, (ii) obstacle centre lies within the camera horizontal field of view: `|wrap(atan2(o.y − y, o.x − x) − ψ)| ≤ 0.6056 rad` (HFOV 1.2112 rad of the Gazebo `rgbd_camera`, `_properties.xacro`), (iii) the robot's `ctrl_stamped` command `vx ≥ 0.05` during the previous 1.0 s (robot is moving).
Exactly one `t_a` per run per dynamic obstacle (the first qualifying row).

## 7.4 The step-test node

`responsiveness_test.py` (ROS node, `use_sim_time:=true`):
- Parameters: `n_trials` = 10 per variant, `v_step` = 0.2, `wz_step` = 0.5, `settle_s` = 3.0, `run_s` = 1.5, `output_file` (`<run_dir>/responsiveness_events.csv`).
- Subscribes `/ground_truth/odom`. Publishes `/cmd_vel` (`Twist`).
- Sequence per trial (all times sim): wait until `|gt_vx| ≤ 0.02 and |gt_wz| ≤ 0.05` for `settle_s`; publish the step; wait for onset (or 3 × deadline); keep command for `run_s` (so steady state is reached); record `cmd_motion` row; publish zero; record `stop` row (response = first GT message satisfying the stop criterion; wait up to 3 × deadline); then the next trial. Variant order: `fwd`, `rot` alternating; forward trials alternate direction (`+0.2`, `−0.2`; onset threshold on `|gt_vx|`) so the robot oscillates about its start, travelled distance ≤ 0.3 m per trial.
- Output columns: `trial, variant (fwd|rot), event (cmd_motion|stop), t_a, t_b, latency_s` (empty `t_b/latency_s` if missed).
- At the end publishes `/eval/done` true.

Run modes (harness `--method responsiveness --stack {bare|loaded}`):
- `bare`: `sim.launch.py` + `odom_mode:=eval` only (+ eval stack). Measures the control chain `/cmd_vel → cmd_vel_relay → diff_drive_controller → Gazebo`.
- `loaded`: the full exploration stack running (RTAB-Map, Nav2, depth→scan, exploration nodes **not** sending goals: start `exploration.launch.py` with the manager disabled — add launch arg `start_manager:=false`). Measures the same chain while the CPU is busy.
Both use the `apartment` spawn at its seeded pose, 1 seed = 1 run of 10 + 10 trials; use seeds 1–10.

## 7.5 Topic-rate health (secondary, reported separately)

Recorder writes `rates.csv` every 1.0 s of **sim** time with columns `t, t_rel, n_odom, n_depth, n_color, n_cmd_nav, n_cmd_smoothed, n_tf_map_odom, n_scan, n_plan` = number of messages received on `/odom`, `/camera/depth/image_rect_raw`, `/camera/color/image_raw`, `/cmd_vel_nav`, `/diff_drive_controller/cmd_vel`, TF messages containing child `odom` with parent `map`, `/scan_from_depth`, `/plan` in the last sim second (message counts reset every second). Required rates (`eval_defaults.yaml: rate_floor`): `n_odom ≥ 27`, `n_depth ≥ 27`, `n_color ≥ 27` (90 % of 30 Hz), `n_cmd_nav ≥ 16` and `n_cmd_smoothed ≥ 16` **only while a goal is active** (80 % of 20 Hz), `n_tf_map_odom ≥ 1`, `n_scan ≥ 9` (30 Hz /3 minimum, depends on depth-to-scan rate; set after measuring). Key `topic_ok_pct_<name>` = percent of 1 s windows in the episode window meeting the floor. `topic_ok_pct_min` = the minimum over topics.
Not part of the headline percentage.

## 7.6 Keys

| Key | Definition |
|---|---|
| `resp_n_events` | total number of timed events of types `cmd_motion, stop, goal_motion, obstacle` in the run |
| `resp_n_met` | events with `L ≤ deadline` |
| **`responsiveness_pct`** | `100 · resp_n_met / resp_n_events` (null if 0 events) |
| `resp_cmd_pct`, `resp_stop_pct`, `resp_goal_pct`, `resp_obstacle_pct` | same per event type (null if none) |
| `lat_cmd_motion_ms_mean`, `_p95`; `lat_stop_ms_mean`, `_p95`; `lat_goal_motion_ms_mean`, `_p95`; `lat_obstacle_ms_mean`, `_p95` | statistics over events that got a response |
| `resp_stack` | `bare`, `loaded` or `episode` (events taken from a normal exploration/navigation run: only `goal_motion` and `obstacle`) |
| `topic_ok_pct_*`, `topic_ok_pct_min` | §7.5 |

In normal exploration/navigation runs only `goal_motion` (and `obstacle` if a dynamic scenario) events exist; the step-test events come from the dedicated `responsiveness` runs. The paper's headline `responsiveness_pct` uses the pooled events of `responsiveness` runs (`bare` and `loaded` reported separately) plus the `goal_motion` and `obstacle` events of navigation/avoidance runs, via `aggregate.py` pooling counts (`resp_n_met`, `resp_n_events`).

## 7.7 Verification notes

| Check | Expected | Observed |
|---|---|---|
| Rate of `/ground_truth/odom` (sim) | ≥ 30 Hz (gives ≤ 0.033 s latency resolution). If lower, record the real rate here and state the resulting resolution in the paper | |
| Typical `cmd_motion` latency bare | expected well below 0.5 s (cmd_vel_relay + 50 Hz controller + accel limit) | |
| `cmd_vel_timeout` 0.5 s in `controllers.yaml` does not truncate the 1.5 s command | test node republishes the step command at 10 Hz during `run_s` | |
| Acceleration limits delay the 50 % threshold | note measured effect | |

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-10-20 | Truth for motion onset = ground truth velocity, not `/odom` | Odometry is derived from the same controller and lags it |
| 2026-10-20 | Per-event deadlines 0.5/0.5/2.0/1.0 s | 0.5 s accepted by the user; navigation start involves planning so 0.5 s is unreachable; flagged for user review |
| 2026-10-20 | Topic-rate health reported separately from the headline % | Different nature (continuous health, not discrete reactions) |
