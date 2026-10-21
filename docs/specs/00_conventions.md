# 00 — Conventions (applies to every other spec)

## 0.1 Environment facts (verified 2026-10-20 in Ubuntu WSL)

- ROS 2 Jazzy, Gazebo Harmonic (`gz sim` 8.15.0), Python 3.12.3. Workspace `~/Swachh/Navigation/Simulation/vacuum_ws`, build `colcon build --symlink-install`.
- Needed in every shell: `source /opt/ros/jazzy/setup.bash; source ~/Swachh/Navigation/Simulation/vacuum_ws/install/setup.bash; export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp CYCLONEDDS_URI=file://$HOME/Swachh/Navigation/cyclone_dds.xml ROS_DOMAIN_ID=0` (already in `~/.bashrc`; non-interactive shells must run it explicitly).
- `gz` is only on PATH after sourcing ROS (`/opt/ros/jazzy/opt/gz_tools_vendor/bin/gz`).
- CycloneDDS needed two fixes on this machine (done): `cyclone_dds.xml` uses `<SocketReceiveBufferSize min="0B" max="2MB"/>`, and the kernel limit was raised with `echo 26214400 > /proc/sys/net/core/rmem_max` as root (does **not** survive a WSL restart; re-run via `wsl.exe -d Ubuntu -u root -e bash -c "..."`).
- Python modules present: numpy, scipy, matplotlib, PIL, yaml, pytest. **Missing: pandas, evo, skimage.** Runtime and offline code in this project must use only the present ones plus the standard library (`csv`, `json`, `heapq`, `dataclasses`). No pandas anywhere.
- Never `pkill -f python3.12` or `pkill -f ros2` from a tool shell: the pattern matches the shell itself. Kill with `pkill -f "gz sim"; pkill -f parameter_bridge; ...` by specific process names, or by saved PIDs.
- **The real-time factor (RTF) is not constant**: it is ~1.0 but dips to 0.1–0.4 for seconds (rendering). Wall-clock rates are therefore unreliable. In sim time `/odom` = 30 Hz and the camera = 30 Hz exactly.

## 0.2 Time

1. Every node uses `use_sim_time:=true`. Every timestamp in every output file is **sim time in seconds** (float, from `/clock` or message stamps), named `t` or `*_t`. Never `time.time()` except in the single field `wall_elapsed_sec` of `summary.json`.
2. Latencies are differences of sim-time stamps. A latency measured across a real-time-factor dip is still valid in sim time; report RTF separately (A12).
3. `t=0` of an episode is the sim time at which the recorder logs its first row (`t0`). All CSVs store `t - t0` as `t_rel` **and** absolute `t`. Both columns are present in every time-stamped file.

## 0.3 Frames and coordinates

| Frame | Meaning | Origin / source |
|---|---|---|
| `world` | Gazebo world frame. **Ground truth lives here.** SDF obstacle coordinates are in this frame | Gazebo |
| `map` | SLAM (RTAB-Map) or AMCL map frame | Origin = robot pose at SLAM start (when SLAM starts at spawn, `map` ≡ spawn pose in `world`) |
| `odom` | Wheel odometry frame | `diff_drive_controller`, origin = spawn pose |
| `base_footprint` | Robot base on the floor. Chassis box 0.300 (x) × 0.250 (y) × 0.100 (z) m is **centred on base_footprint in x,y** (box spans z 0.043–0.143 m); wheel separation 0.268 m | URDF |

- All planar math is SE(2): `(x, y, yaw)`, yaw in radians wrapped to (−π, π], counter-clockwise positive, x forward.
- **World↔map relation:** `T_world_map = (spawn_x, spawn_y, spawn_yaw)` as given to `sim.launch.py` (SLAM starts at spawn, its map origin is the odom origin which is the spawn pose). This is an assumption that every run **must verify** (spec 04 §4.5 "alignment check").
- Robot footprint polygon for geometric tests: rectangle with corners `(±0.150, ±0.125)` m in `base_footprint`, plus the camera if it protrudes (read `_sensors.xacro`; if the camera extends beyond x=0.150 add its box). Inscribed radius `r_in = 0.125 m`, circumscribed radius `r_circ = 0.195 m`.

## 0.4 Units

metres, seconds, radians internally; degrees only in CSV columns whose name ends `_deg`; percentages are 0–100 floats in columns ending `_pct`; areas in m²; energy proxy in m²/s (∫v² dt with v in m/s).

## 0.5 New package `vacuum_eval`

Create `Navigation/Simulation/vacuum_ws/src/vacuum_eval/` as an **ament_python** package (`build_type ament_python`, depends on rclpy, geometry_msgs, nav_msgs, sensor_msgs, tf2_ros, action_msgs, nav2_msgs, rtabmap_msgs, ros_gz_interfaces, std_msgs, builtin_interfaces).

```
vacuum_eval/
  package.xml  setup.py  setup.cfg  resource/vacuum_eval
  vacuum_eval/
    __init__.py
    ground_truth_node.py      # spec 01
    odom_noise_node.py        # spec 01 (replaces use of vacuum_controller's noise node for evaluation)
    recorder_node.py          # spec 02
    goal_sender.py            # spec 05 (scripted goal lists)
    responsiveness_test.py    # spec 07
    metrics/
      __init__.py
      common.py               # se2 math, csv/json IO, run-dir loader
      gt_grid.py              # spec 03 (SDF -> grid)
      coverage.py             # spec 03 / 10
      trajectory.py           # spec 04
      navigation.py           # spec 05
      safety.py               # spec 06
      responsiveness.py       # spec 07
      loop_closure.py         # spec 08
      resources.py            # spec 02
    compute_metrics.py        # CLI: run_dir -> summary.json
    aggregate.py              # CLI: many run dirs -> aggregate.csv + stats (spec 02)
    run_episode.py            # CLI launcher/harness (spec 02)
  launch/
    eval_stack.launch.py      # ground truth + recorder (+ noise) (spec 02)
  config/
    eval_defaults.yaml        # all thresholds listed in specs
  test/
    test_*.py                 # pytest, see spec 12
```

- Executables are registered as `console_scripts` (`ros2 run vacuum_eval recorder_node`). Python files that are ROS nodes use the shebang `#!/usr/bin/env python3` (system Python is 3.12; the old `python3.12` shebang convention elsewhere in the repo is kept only in old packages).
- **All thresholds and constants named in the specs live in `config/eval_defaults.yaml`** and are copied into `run_meta.yaml` of every run. Code never hardcodes them.

## 0.6 Directory layout for results

```
~/eval_runs/<experiment>/<world>/<method>/seed_<NNN>/
  run_meta.yaml            # exact args, seed, git commit, thresholds, versions, start wall time
  trajectory.csv           # 10 Hz, spec 02 §2.4
  cmd_vel.csv              # every /cmd_vel-like command message, spec 02
  goal_events.csv          # spec 05
  plans.csv                # spec 05
  collisions_raw.csv       # spec 06
  loop_events.csv          # spec 08
  resources.csv            # 1 Hz, spec 02
  rtf.csv                  # 1 Hz real-time factor
  maps/map_<t_rel>.npz     # every 5 s (sim) snapshots of /rtabmap/map  (spec 03)
  maps/final_map.npz  maps/final_map.pgm  maps/final_map.yaml
  bag/                     # rosbag2 (sqlite3 or mcap), topics in spec 02
  logs/                    # launch stdout/stderr per process
  summary.json             # produced offline by compute_metrics
  summary.csv              # one row, same keys, for aggregation
```
`<experiment>` is a short slug (e.g. `phase1_baseline`), `<method>` is `frontier` for the current explorer, `<NNN>` is zero-padded 3 digits.

## 0.7 File formats

- CSV: UTF-8, `,` separator, header row, no index column, floats in plain decimal (no thousands separators), missing values as empty field, booleans as `0`/`1`, never pandas.
- `summary.json`: one flat JSON object (no nesting), keys exactly as in the metric tables, numeric values or `null` when not computable, plus string `status` in `{"ok","partial","failed"}` and `notes` (list of strings). A metric that could not be computed must be `null` with a reason in `notes`; never write 0 for "unknown".
- `run_meta.yaml` keys (all required): `experiment, world, world_name_in_sdf, method, seed, spawn_x, spawn_y, spawn_yaw, odom_noise (bool), odom_noise_params, git_commit, git_dirty (bool), config_snapshot (copy of eval_defaults.yaml), start_wall_iso, episode_timeout_sim_sec, swath_width_m, grid_resolution_m`.

## 0.8 Randomness / seeds

Gazebo physics is deterministic and has no seed. A `seed` (integer) controls only: (a) spawn pose sampling (spec 02 §3.3), (b) odometry-noise RNG (`numpy.random.default_rng(seed)`), (c) goal-list shuffling in scripted tests. The same seed with the same code must produce the same spawn pose and the same noise sequence; the whole run will still differ slightly due to timing.

## 0.9 Coding rules

- Match surrounding style in existing packages; keep comments sparse and factual.
- No metric logic inside live nodes beyond what a spec explicitly lists.
- Every `metrics/*.py` function is pure (arrays/dicts in, dict out) and unit-tested with synthetic data (spec 12).
- Do not edit the stale Windows copy. Do not `git add -A`; commit only files you touched, after the user asks.
- When a spec says "verify at runtime", paste the observed output into the file's *Verification notes* section.

## 0.10 Common helper contracts (in `metrics/common.py`)

```
wrap_angle(a: float) -> float                           # to (-pi, pi]
se2_compose(a, b) -> (x, y, yaw)                        # a ∘ b
se2_inverse(a) -> (x, y, yaw)
load_csv(path) -> dict[str, np.ndarray]                 # columns as float arrays (strings kept as object arrays)
write_json(path, obj) / read_json(path)
load_run(run_dir) -> Run                                # dataclass holding meta + every csv that exists
```
