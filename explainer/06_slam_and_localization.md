# 06. SLAM and Localization (`vacuum_slam`, `vacuum_localization`)

Source files covered (all under `Navigation/Simulation/vacuum_ws/src/`):

- `vacuum_slam/config/rtabmap.yaml`, `launch/slam.launch.py`, `launch/map_saver.launch.py`, `config/slam_rviz.rviz` (RViz layout only), `package.xml`, `CMakeLists.txt`
- `vacuum_localization/config/localization_params.yaml`, `launch/localization_monitor.launch.py`, and the Python files `localization_monitor.py`, `recovery_monitor.py`, `localization_metrics.py`, `pose_quality.py`, plus `setup.py`

Terms used below: SLAM = Simultaneous Localization And Mapping (build a map while working out where the robot is in it). Localization = work out the robot pose inside an already-known map. TF = ROS's tree of coordinate-frame transforms. Odometry = a running estimate of robot motion, here from the wheels.

---

## 1. The big picture

| Question | Answer in this repo |
|---|---|
| What builds the map? | RTAB-Map (a graph-based SLAM library), run as the `rtabmap_slam/rtabmap` node, launched by `vacuum_slam`. |
| What sensors does it use? | RGB image + depth image + camera info from the simulated D435i camera, plus wheel odometry on `/odom`. No lidar (`subscribe_scan: false`). |
| What does it output? | A 2D occupancy grid on `/rtabmap/map` (for Nav2 and the frontier explorer), a 3D point cloud, graph/info topics, the `map -> odom` TF, and an SQLite database file. |
| What localizes the robot on a saved map? | Two options exist. (a) RTAB-Map itself in `localization:=true` mode. (b) AMCL (Adaptive Monte Carlo Localization, a particle filter that matches range scans to a saved 2D map), which is part of Nav2, not of these two packages. |
| What does `vacuum_localization` do? | It does not localize. It only watches AMCL's output, classifies quality (GOOD / WARNING / LOST), triggers a spin recovery, and logs a CSV. |
| Where is odometry noise injected? | Not in these packages. It is in `vacuum_eval/odom_noise_node.py` (see section 8). |

Data flow in short: Gazebo sim -> clean wheel odometry -> (optional noise node) -> `/odom` -> RTAB-Map (with camera) -> `/rtabmap/map` + `map->odom` TF. For navigation on a saved map, `nav2_map_server` loads a PGM/YAML map and AMCL provides the pose, and `vacuum_localization` monitors AMCL.

---

## 2. `vacuum_slam` package

Packaging: `CMakeLists.txt` only installs `config/` (and presumably launch) into the package share directory; `package.xml` depends on `rtabmap_ros`, `ros2launch`, `launch_ros`, `rviz2`, `teleop_twist_keyboard`, `ros2bag`, `rosbag2_transport`, `nav2_map_server`. It has no Python or C++ node of its own: it is configuration plus launch files.

### 2.1 `slam.launch.py`

Prerequisite (stated in the file): `ros2 launch vacuum_bringup sim.launch.py` must already be running.

**Launch arguments**

| Argument | Default | Meaning |
|---|---|---|
| `use_sim_time` | `true` | Use the Gazebo simulated clock. |
| `use_rviz` | `true` | Also start RViz2 with `config/slam_rviz.rviz`. |
| `environment` | `room` | Label only (choices: room, office, apartment, corridor, large, empty_room, cluttered_room, two_rooms_door, multi_room_loop, maze_dead_ends, symmetric_hall). Used for logging/naming. |
| `database_path` | `~/.ros/rtabmap.db` (expanded) | Where RTAB-Map's SQLite map database lives. |
| `delete_db` | `true` | Wipe the DB at start (fresh map). |
| `localization` | `false` | If true, run localization-only mode. |

**Three mutually exclusive RTAB-Map nodes** (all named `rtabmap`, all load `rtabmap.yaml`, selected by `IfCondition`):

| Variant | Condition | Extra settings |
|---|---|---|
| Mapping, fresh DB | `delete_db == true` and `localization == false` | Passes `--delete_db_on_start`; `Mem/IncrementalMemory=true`; `Rtabmap/StartNewMapOnLoopClosure=false` |
| Mapping, keep DB | `delete_db == false` and `localization == false` | Same as above but no delete flag (continues an existing DB) |
| Localization | `localization == true` | `Mem/IncrementalMemory=false` (no new keyframes added) and `Mem/InitWMWithAllNodes=true` (load all saved nodes into working memory) |

Note: a launch-time parameter dictionary overrides values from the YAML file.

**Topic remappings (identical in all three variants)**

| RTAB-Map input name | Real topic |
|---|---|
| `rgb/image` | `/camera/color/image_raw` |
| `depth/image` | `/camera/depth/image_rect_raw` |
| `rgb/camera_info` | `/camera/color/camera_info` |
| `odom` | `/odom` |

| RTAB-Map output name | Real topic | Type (from launch docstring) |
|---|---|---|
| `map` | `/rtabmap/map` | nav_msgs/OccupancyGrid (2D map for Nav2) |
| `info` | `/rtabmap/info` | rtabmap_msgs/Info (keyframes, loop closures) |
| `mapData` | `/rtabmap/mapData` | rtabmap_msgs/MapData (full graph) |
| `mapGraph` | `/rtabmap/mapGraph` | graph |
| `mapPath` | `/rtabmap/mapPath` | path |
| `grid_prob_map` | `/rtabmap/grid_prob_map` | probabilistic grid |
| `cloud_map` | `/rtabmap/cloud_map` | sensor_msgs/PointCloud2 (3D map) |

The comment in the file explains the reason for the explicit remaps: the node runs without a namespace, but the rest of the stack (frontier detector, Nav2 relay, RViz, evaluation) expects `/rtabmap/*` names. The docstring also lists `/rtabmap/odom`, but no remap for it appears in the launch.

**TF provided:** per the `rtabmap.yaml` comment, RTAB-Map publishes `map -> odom`. The `odom -> base_footprint` transform comes from the odometry source (the controller, or the noise node in eval mode).

**Also launched:** `rviz2` node `rviz2_slam` with `slam_rviz.rviz`, when `use_rviz` is true.

### 2.2 `map_saver.launch.py`

Runs `nav2_map_server/map_saver_cli` (node name `map_saver`) with `-f <output_dir>/<map_name>`. It subscribes to the live `/rtabmap/map` topic (the file notes that RTAB-Map must be publishing) and writes:

- `<output_dir>/<map_name>.pgm` (greyscale occupancy image)
- `<output_dir>/<map_name>.yaml` (map metadata, e.g. resolution/origin, for Nav2)

| Argument | Default |
|---|---|
| `map_name` | `map` |
| `output_dir` | `~/maps/stage4` |
| `use_sim_time` | `true` |

The docstring claims it can also work "from saved database — RTAB-Map NOT running", but the node it launches only reads a topic; it does not open the `.db`. Treat the live-topic path as the one that is actually implemented.

### 2.3 How the map is saved and loaded

| Artifact | Created by | Loaded by |
|---|---|---|
| `~/.ros/rtabmap.db` (or `database_path`) | RTAB-Map continuously (SQLite: keyframes, features, graph, grid) | `slam.launch.py localization:=true delete_db:=false` (RTAB-Map reloads it; `Mem/InitWMWithAllNodes=true`) |
| `<name>.pgm` + `<name>.yaml` | `map_saver.launch.py` | Nav2's `nav2_map_server` (`ros2 run nav2_map_server map_server --ros-args -p map:=<path>/<name>.yaml`, per the docstring); AMCL then localizes against it |

---

## 3. `rtabmap.yaml`: every parameter

Top-level structure: `rtabmap: ros__parameters:` (matches node name `rtabmap`). Keys written in the `Group/Name` style (e.g. `Kp/MaxFeatures`) are native RTAB-Map parameters and are given as strings. "Keyframe" here means a saved node in the map graph (an image + depth + pose snapshot).

### 3.1 Frames

| Parameter | Value | Meaning |
|---|---|---|
| `frame_id` | `base_footprint` | Robot base frame on the ground plane. |
| `odom_frame_id` | `odom` | Odometry frame (file comment says published by the diff-drive controller). |
| `map_frame_id` | `map` | Map frame; RTAB-Map publishes `map -> odom`. |
| `sensor_transform` | `""` | Empty: use TF to find the camera frame. |

### 3.2 Inputs and synchronisation

| Parameter | Value | Meaning |
|---|---|---|
| `subscribe_depth` | `true` | Use a depth image. |
| `subscribe_rgb` | `true` | Use a colour image. |
| `subscribe_rgbd` | `false` | Not using the combined RGBD message. |
| `subscribe_scan` | `false` | No lidar scan. |
| `subscribe_scan_cloud` | `false` | No lidar cloud. |
| `subscribe_odom_info` | `false` | No odometry-info topic. |
| `qos_image` | `2` | Best Effort / Volatile (drops old buffered frames). QoS = DDS delivery policy. |
| `qos_camera_info` | `2` | Same, for camera info. |
| `approx_sync` | `true` | Match RGB and depth by approximately equal timestamps (needed because the Gazebo bridge adds jitter). |
| `approx_sync_max_interval` | `0.05` s | Largest allowed timestamp gap between RGB and depth. |
| `queue_size` | `10` | Message queue length per input. |
| `wait_for_transform` | `0.5` s | How long to wait for a TF before giving up (default was 0.2 s per the comment). |
| `tf_delay` | `0.05` s | Delay before querying TF. |
| `tf_tolerance` | `0.1` s | Time tolerance for TF lookups. |
| `database_path` | `~/.ros/rtabmap.db` | Default DB; launch overrides it with its own argument. |

### 3.3 Memory management

RTAB-Map keeps recent keyframes in short-term memory (STM, not eligible for loop-closure matching) and older ones in working/long-term memory.

| Parameter | Value | Meaning |
|---|---|---|
| `Mem/STMSize` | `"10"` | Keyframes held in STM. Comment: 30 hid most of a 50-node episode from loop detection, so it was reduced. |
| `Mem/RehearsalSimilarity` | `"0.45"` | Similarity above which a new keyframe is merged into the previous one ("rehearsal"). |
| `Mem/BadSignaturesIgnored` | `"false"` | Keep poor-quality keyframes. |
| `Mem/InitWMWithAllNodes` | `"false"` | Do not preload the whole DB into working memory (overridden to true in localization mode). |
| `Mem/IncrementalMemory` | `"true"` | Keep adding keyframes (overridden to false in localization mode). |

### 3.4 Update rate

| Parameter | Value | Meaning |
|---|---|---|
| `Rtabmap/DetectionRate` | `"1"` Hz | Map update rate: one processing step per second. |
| `Rtabmap/TimeThr` | `"0"` ms | No per-update time limit. |
| `Rtabmap/MemoryThr` | `"0"` MB | No memory limit. |

### 3.5 Loop closure

A loop closure is RTAB-Map recognising a previously visited place and adding a graph constraint that corrects drift.

| Parameter | Value | Meaning |
|---|---|---|
| `Rtabmap/LoopThr` | `"0.11"` | Hypothesis probability needed to accept a closure. Lower = more closures but more false ones. |
| `Rtabmap/LoopRatio` | `"0"` | 0 = no extra ratio test; accept anything above `LoopThr`. |
| `RGBD/LoopClosureReextractFeatures` | `"false"` | Do not re-extract features when verifying a closure. |
| `RGBD/ProximityBySpace` | `"true"` | Also look for matches among spatially nearby nodes (not just appearance). |
| `RGBD/ProximityMaxGraphDepth` | `"0"` | Graph-depth limit for proximity search (0 as set). |
| `Rtabmap/StartNewMapOnLoopClosure` | `"false"` | Do not start a new map session on closure. |
| `Rtabmap/SaveWMState` | `"false"` | Do not save working-memory state. |

### 3.6 Keyframe creation thresholds

| Parameter | Value | Meaning |
|---|---|---|
| `RGBD/LinearUpdate` | `"0.1"` m | Minimum translation before a new keyframe. |
| `RGBD/AngularUpdate` | `"0.087"` rad (about 5 deg) | Minimum rotation before a new keyframe. |

### 3.7 Features (keypoints)

| Parameter | Value | Meaning |
|---|---|---|
| `Kp/DetectorStrategy` | `"6"` | Keypoint detector for loop closure. The comment in the YAML file says 6=ORB, but that comment is wrong: in RTAB-Map 0.23 the value 6 is GFTT/BRIEF (Good Features To Track keypoints described with BRIEF binary descriptors), which is what the paper reports. Treat the YAML comment as a documentation error. |
| `Kp/MaxFeatures` | `"500"` | Maximum keypoints per image. |
| `Kp/MaxDepth` | `"4.0"` m | Ignore features farther than this. |
| `Kp/MinDepth` | `"0.1"` m | Ignore features closer than this. |
| `Vis/FeatureType` | `"6"` | Feature type for visual registration. Comment: must equal `Kp/DetectorStrategy`; a mismatch disabled `Mem/UseOdomFeatures`. |
| `Vis/MinInliers` | `"10"` | Minimum matched features (RANSAC inliers, matches consistent with one motion) for a valid transform. |
| `Vis/InlierDistance` | `"0.1"` m | Maximum error for a match to count as inlier. |

### 3.8 Planar (3-DoF) constraint

| Parameter | Value | Meaning |
|---|---|---|
| `Reg/Force3DoF` | `"true"` | Registration is forced to 3 degrees of freedom: x, y, yaw only (planar robot). Roll, pitch, z are fixed. |

### 3.9 Occupancy grid (2D map for Nav2)

| Parameter | Value | Meaning |
|---|---|---|
| `RGBD/CreateOccupancyGrid` | `"true"` | Build and publish the grid on `/rtabmap/map`. |
| `Grid/3D` | `"false"` | 2D grid only. |
| `Grid/RayTracing` | `"true"` | Mark free space by casting rays from the sensor. |
| `Grid/CellSize` | `"0.05"` m | 5 cm cells. |
| `Grid/MaxObstacleHeight` | `"0.30"` m | Points above this are ignored (was 2.0; now the robot body band). |
| `Grid/MinGroundHeight` | `"-0.1"` m | Points below this are ignored. |
| `Grid/MaxGroundHeight` | `"0.03"` m | Points below this are floor (was 0.15; floor is flat in sim). |
| `Grid/FlatObstacleDetected` | `"true"` | Treat flat horizontal surfaces as obstacles. |
| `Grid/NormalsSegmentation` | `"false"` | Use height thresholds, not surface normals, to find the floor. |

### 3.10 ICP and odometry keys

| Parameter | Value | Meaning |
|---|---|---|
| `Icp/MaxTranslation` | `"0.1"` | ICP (point-cloud alignment) translation limit. File says ICP is disabled (no lidar). |
| `Icp/MaxRotation` | `"0.1"` | ICP rotation limit. |
| `Odom/Strategy` | `"0"` | 0 = Frame-to-Map, 1 = Frame-to-Frame (RTAB-Map's own visual odometry). |
| `Odom/ResetCountdown` | `"1"` | Reset visual odometry after 1 lost frame. |
| `OdomF2M/MaxSize` | `"1000"` | Max points in the local odometry map. |

The launch files start only the `rtabmap` node, with `/odom` remapped in from wheel odometry. The `Odom/*` and `OdomF2M/*` keys describe RTAB-Map's separate visual-odometry node, which is not launched here; they are in the YAML (commented "Odometry noise tolerance") but wheel odometry is the primary source ("visual is cross-check only", per the file's comment). Treat them as inert for this launch.

---

## 4. `vacuum_localization` package

Three ROS 2 nodes and one helper module, registered in `setup.py` as console scripts (`localization_monitor`, `recovery_monitor`, `localization_metrics`), launched together by `localization_monitor.launch.py`. All run with `use_sim_time: True` and read `config/localization_params.yaml`.

Launch arguments: `environment` (default `apartment`, passed to the metrics node) and `map_file` (default empty, recorded as metadata only).

### 4.1 Parameters (`localization_params.yaml`)

| Node | Parameter | Value | Meaning |
|---|---|---|---|
| `localization_monitor` | `cov_trace_good` | 0.05 | Position covariance trace below this = GOOD. |
| | `cov_trace_warning` | 0.25 | Above this = WARNING upper bound. |
| | `cov_trace_lost` | 1.00 | Documented as LOST threshold. |
| | `pose_timeout_sec` | 3.0 | No `/amcl_pose` for this long = LOST. |
| | `publish_rate` | 10.0 Hz | `/localization/status` rate. |
| `recovery_monitor` | `max_recovery_attempts` | 3 | Attempts before ABORT. |
| | `spin_angle_rad` | 6.28 | One full turn. |
| | `recovery_wait_sec` | 2.0 | Declared in YAML, but the code never reads it (the node only declares `max_recovery_attempts`, `spin_angle_rad`, `recovery_wait_sec`, `cancel_goal_on_lost`; `recovery_wait_sec` is stored in `_wait_sec` and unused). |
| | `cancel_goal_on_lost` | true | Try to cancel the active Nav2 goal. |
| `localization_metrics` | `output_base_dir` | `~/bags/stage5` | Output root. |
| | `log_rate` | 1.0 Hz | CSV rows per second. |
| | `environment` | `apartment` | Subfolder name. |
| | `map_file` | `""` | Set at runtime. |

Covariance trace here = x variance + y variance, taken from indices 0 and 7 of the 36-element covariance matrix in AMCL's pose message (`pose_quality.py`). Yaw variance is index 35.

### 4.2 `pose_quality.py` (not a node)

Class `PoseQuality(cov_good=0.05, cov_warning=0.25, cov_lost=1.00)` with `trace_position`, `trace_full` (sum of 6x6 diagonal), `yaw_variance`, `classify`, `is_converged`, `is_lost`, `summary`. `classify` returns GOOD if trace < good, WARNING if < warning, otherwise LOST. So in code the effective LOST boundary is `cov_trace_warning` (0.25), not `cov_trace_lost` (1.00); the `cov_lost` value is only used by `is_lost()`, which the nodes do not call. If the covariance list is shorter than 36 elements, trace returns infinity.

### 4.3 `localization_monitor` node

| Direction | Topic | Type | QoS |
|---|---|---|---|
| Subscribes | `/amcl_pose` | geometry_msgs/PoseWithCovarianceStamped | Best effort, depth 10 |
| Subscribes | `/particle_cloud` | nav2_msgs/ParticleCloud (only if importable) | Best effort, depth 10 |
| Publishes | `/localization/status` | std_msgs/String (JSON) | reliable, depth 10 |

TF: none. State machine: starts `INITIALIZING`; the first `/amcl_pose` moves it to `GOOD`; after that a 10 Hz timer sets `LOST` if time since last pose (`time.monotonic`, wall time) exceeds `pose_timeout_sec`, otherwise it classifies the latest covariance. Published JSON keys: `state`, `cov_trace`, `yaw_variance`, `particle_count`, `elapsed_since_update_sec`. It logs a warning (WARNING) or error (LOST) every tick while not GOOD.

### 4.4 `recovery_monitor` node

| Direction | Topic | Type |
|---|---|---|
| Subscribes | `/localization/status` | std_msgs/String |
| Publishes | `/localization/recovery_status` | std_msgs/String (JSON: `result`, `attempt`, `max_attempts`) |
| Publishes | `/diff_drive_controller/cmd_vel_unstamped` | geometry_msgs/Twist |
| Action client | `navigate_to_pose` | nav2_msgs/NavigateToPose (only if `cancel_goal_on_lost` and nav2_msgs import) |

Behaviour: on a new transition into LOST (and not already recovering) it starts a recovery. If `recovery_count >= max_recovery_attempts` it publishes `ABORT`. Otherwise it publishes `ATTEMPT_n`, sends a zero Twist, and spins at 0.5 rad/s for `6.28 / 0.5 = 12.56` s by publishing Twist at 10 Hz inside a blocking `time.sleep` loop (the file says the open-loop spin is a deliberate simplification). When status returns to GOOD while recovering it resets the counter and publishes `SUCCESS`. Code caveats visible in the file: the goal-cancel line is `self._nav2_client._cancel_goal_async` with no call parentheses, so it does nothing (the comment even says "noop if no goal"); and because the spin blocks the callback, the node cannot process new status messages during it. The recovery trigger fires only on a transition into LOST, so repeated attempts require leaving and re-entering LOST.

### 4.5 `localization_metrics` node

| Direction | Topic | Type |
|---|---|---|
| Subscribes | `/localization/status` | String |
| Subscribes | `/localization/recovery_status` | String (counts messages whose `result` starts with `ATTEMPT`) |
| Subscribes | `/amcl_pose` | PoseWithCovarianceStamped (best effort) |
| Subscribes | `/odom` | nav_msgs/Odometry (accumulates travelled distance from consecutive positions) |
| Publishes | none | |

TF: none. Writes `<output_base_dir>/<environment>/run_NN/localization.csv` (next run number auto-chosen), `metadata.yaml` (written at start with `complete: False`, rewritten on shutdown with `complete: True`; includes git commit looked up in `~/Swachh_Boudhik_Yantra`, which differs from this repo's path, so it will likely show `unknown`), and the docstring mentions a `summary.txt` that the code does not write. CSV columns: `timestamp_sec, loc_state, cov_trace, yaw_variance, particle_count, goals_sent, goals_succeeded, goals_failed, distance_m, recoveries, cpu_pct, ram_mb, elapsed_sec`. The three goal columns are always written as 0 ("goals logged by external nav node"). CPU and RAM use `psutil` if installed.

---

## 5. AMCL and the saved map

AMCL itself is configured in the Nav2 package (`vacuum_nav2`, e.g. `config/amcl_params_v2.yaml` and `map_server_params.yaml`), outside the scope of these two packages. What these packages contribute: `map_saver.launch.py` produces the PGM/YAML map that Nav2's map server loads, and `vacuum_localization` consumes AMCL's `/amcl_pose` and `/particle_cloud`. AMCL publishes the `map -> odom` TF in that setup (standard Nav2 behaviour; not shown in these files).

---

## 6. Wheel odometry and RTAB-Map

- RTAB-Map reads `/odom` as its motion prior and fuses camera constraints on top. It does not run its own odometry here.
- Planar restriction: `Reg/Force3DoF: true`.
- If odometry is corrupted (see below), RTAB-Map follows it: `docs/FAILURE_MODES.md` lists "RTAB-Map follows bad odometry, never recovers (item 21)".

---

## 7. Failure modes (from `docs/FAILURE_MODES.md`) that touch these packages

| Failure mode | Detected by / symptom | Decision in the doc |
|---|---|---|
| Episode invalid: DDS image drops > 10 % or RTAB-Map gap | `UNMEASURABLE:INVALID_EPISODE`; check `img_drop_pct`, `rtabmap_max_gap_s` | Fix and rerun once, same seed, report both |
| Contact-induced odometry corruption (pilot2: ATE 3.10 m vs 0.119 m before contact) | `SUSPECT:ODOM_CORRUPTED`, `odom_corrupted_by_contact` | Report headline; fallback key `ate_fixed_rmse_m_pre_corrupt`; report with and without, plus median |
| Axle 8 cm behind `base_footprint` (item 20) | No automatic flag; in-place spins move ground truth about 0.10 m while odometry reports 0 | Report as a documented limitation in every paper-table footnote |
| RTAB-Map follows bad odometry, never recovers (item 21) | `SUSPECT:ODOM_CORRUPTED` + persistent SLAM yaw error | Report as a SLAM finding |
| SLAM never started / too few poses | `UNMEASURABLE:NO_DATA` | Fix and rerun if infra, else report |
| No saved map | `UNMEASURABLE:MAP_MISSING` | Fix and rerun if the save failed |
| Textureless walls: no features, sparse map | `BELOW_FLOOR` map completeness < 60 | Report (genuine perception limit) |
| Map yaw-rotated after corrupted odometry | Unaligned completeness drops | Fall back to the aligned key, report both |
| RTAB-Map never accepts a closure | `UNMEASURABLE:NO_EVENTS` (precision), `LOW_N` | Report as not measurable; recall 0 % if revisits exist |
| Textureless walls / `symmetric_hall` aliasing: wrong closures | precision < 50 | Report (that environment is meant to measure this) |
| Direction/convention error in loop-closure truth (fixed 2026-10-22, `loop_to_ref`) | `SUSPECT:LC_ROT_BIAS` | Offline recompute from bag |
| Corrupted odometry makes closure transforms wrong | `SUSPECT:ODOM_CORRUPTED` | Report with and without |
| LC precision bad with rotation errors 7-15 deg (2026-10-25) | Ground truth taken at Info arrival (lag 0.1-0.4 s) | Report as lower bound; offline recompute |
| AMCL planner start in wall inscribed zone ("Start occupied", error 205) | About 36 % localization error | Report as measured; check with `--localization gt`; candidates: START_OCCUPIED recovery, AMCL likelihood settings |
| AMCL stuck 0.5 m / 10 deg off for minutes (maze) | Loose sigma_hit/z_rand, recovery off, 69 deg field of view, flat walls | Report; candidate AMCL settings |
| Goal reached by ground truth but not by controller estimate | `SUSPECT:NAV_GT_DIVERGENCE` | Report both keys; localization ablation separates causes |
| AMCL scripted run not done | `loc_error_mean_m` UNMEASURABLE:NO_DATA | Run R3, else report not measured |
| MPPI "control loop missed" with 3 sims on 16 threads | CPU oversubscribed | Use `--parallel 2` for SLAM workloads |

Related config observations in `rtabmap.yaml`: `Mem/STMSize` was lowered to 10 because 30 hid most of a 50-node episode; `Vis/FeatureType` must match `Kp/DetectorStrategy` or `Mem/UseOdomFeatures` is disabled.

---

## 8. Odometry noise injection (outside these packages)

Neither package injects noise. The relevant node is `vacuum_eval/vacuum_eval/odom_noise_node.py` (read only for its header). With `sim.launch.py odom_mode:=eval`, it sits between `/diff_drive_controller/odom` (clean) and `/odom` plus the `odom -> base_footprint` TF, so RTAB-Map and Nav2 see one odometry source. With `enable_noise:=false` output equals input. Noise is applied to motion increments and is correlated over time: per run, a persistent distance scale `b_lin = 1 + sigma_scale_lin * N(0,1)` and rotation scale `b_ang = 1 + sigma_scale_ang * N(0,1)`; per message, distance `d' = d * b_lin` and rotation `dtheta' = dtheta * b_ang + sigma_rw_per_sqrt_m * sqrt(|d|) * e1 + sigma_rw_per_sqrt_rad * sqrt(|dtheta|) * e2` (random walk growing with distance and turning). The RTAB-Map YAML comment "handle the Gaussian noise we inject in Stage 2" refers to the same idea. No EKF (extended Kalman filter, a state-fusion filter) appears in either package.

---

## 9. Typical command sequence (from the launch docstrings)

1. `ros2 launch vacuum_bringup sim.launch.py`
2. `ros2 launch vacuum_slam slam.launch.py` (add `environment:=office`, `use_rviz:=false` as needed)
3. Drive: `ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args --remap cmd_vel:=/cmd_vel`
4. Save: `ros2 launch vacuum_slam map_saver.launch.py map_name:=office output_dir:=/path/to/maps`
5. Re-localize with RTAB-Map: `ros2 launch vacuum_slam slam.launch.py localization:=true delete_db:=false`
6. Monitor AMCL: `ros2 launch vacuum_localization localization_monitor.launch.py environment:=office`

---

Summary: `vacuum_slam` runs RTAB-Map (GFTT/BRIEF features, 500 keypoints, 1 Hz updates, LoopThr 0.11, 3-DoF, 5 cm 2D grid) on RGB-D plus wheel odometry and exports PGM/YAML maps, while `vacuum_localization` only monitors AMCL covariance (GOOD/WARNING/LOST), spins to recover, and logs a CSV; odometry noise lives in `vacuum_eval`, not here.
