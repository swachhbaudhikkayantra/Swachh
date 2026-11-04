# 05. Bring-up, interfaces and utility scripts

Scope: three ROS 2 packages under `/home/hrishikesh/Swachh/Navigation/Simulation/vacuum_ws/src/`:

| Package | Path | Role |
|---|---|---|
| `vacuum_bringup` | `vacuum_bringup/` | Launch files and the RViz config that start the whole simulation |
| `vacuum_interfaces` | `vacuum_interfaces/` | Reserved for custom msg/srv/action types (currently defines none) |
| `vacuum_utils` | `vacuum_utils/scripts/` | 12 standalone check, record, benchmark and documentation scripts |

This file only describes what the code does. Where a script's docstring disagrees with its code, both are noted.

---

## 1. High level: how the simulation starts

One command starts the simulation:

```
ros2 launch vacuum_bringup sim.launch.py [arguments]
```

`sim.launch.py` does not contain the controller logic. It starts the robot model, Gazebo, the bridges and the ground-truth node itself, then includes `controllers.launch.py` from the `vacuum_controller` package. RViz is started last, optionally.

The nodes below are listed in the order of the final `LaunchDescription` in `sim.launch.py`. Several have internal delays, so the order of listing is not always the order they come up.

| # | Action | Delay | What comes up |
|---|---|---|---|
| 0 | `AppendEnvironmentVariable` | none | Adds `vacuum_gazebo/worlds` to `GZ_SIM_RESOURCE_PATH` so world textures are found |
| 1 | `robot_state_publisher` | none | Expands `vacuum_description/urdf/vacuum.urdf.xacro`, publishes `/robot_description` and TF at `publish_frequency` 50.0 |
| 2 | Gazebo (`ros_gz_sim` `gz_sim.launch.py`) | `TimerAction` 3.0 s | Gazebo Harmonic with the (optionally baked) world; `on_exit_shutdown: true` |
| 3 | `extra_bridge` (`ros_gz_bridge parameter_bridge`, name `ros_gz_bridge_extra`) | none | Only if `extra_bridge_config` is non-empty |
| 4 | `ros_gz_bridge` (`parameter_bridge`) | none | Bridges the topics in `vacuum_gazebo/config/gz_bridge.yaml` |
| 5 | `ground_truth_node` (package `vacuum_eval`) | none | Turns `/ground_truth/odom_raw` into `/ground_truth/odom` |
| 6 | `spawn_vacuum_robot` (`ros_gz_sim create`) | `TimerAction` 3.0 s | Only when `embed_robot` is not `true` |
| 7 | `controllers` (include of `vacuum_controller/launch/controllers.launch.py`) | internal timers | Controller spawners, relays, odometry and diagnostic nodes (section 2.3) |
| 8 | `rviz2` | none | Only if `use_rviz` is true |

### 1.1 Timeline with default arguments

Default arguments: `embed_robot:=true`, `odom_mode:=clean`, `use_rviz:=true`. Times are launch time, taken from the `TimerAction` periods in the launch files.

| Time | Event |
|---|---|
| t = 0 s | `robot_state_publisher`, both bridges, `ground_truth_node` and `rviz2` start. The controllers include is also active; its timers start counting from here. |
| t = 2 s | `jsb_spawner` and `ddc_spawner` (the `controller_manager` `spawner`) run, loading and activating `joint_state_broadcaster` and `diff_drive_controller` |
| t = 3 s | The Gazebo action fires: the world is baked with the robot, then Gazebo starts. The `spawn_vacuum_robot` timer also fires but its node is skipped because `embed_robot` is `true`. |
| t = 12 s | `cmd_vel_relay`, `cmd_vel_relay_nav`, `odom_relay` start (in eval mode, `odom_noise_node` replaces `odom_relay`) |
| t = 13 s | `odometry_noise_node`, `motion_diagnostics_node` |
| t = 15 s | `camera_diagnostics_node` |

Two caveats come from the code itself:

- The controller spawners are timed from launch start (2 s), while Gazebo is started at 3 s. The comments in `sim.launch.py` and the docstring of `controllers.launch.py` describe other timings (5 s / 6 s / 10 s, and a claim that gz_ros2_control auto-loads controllers). Those comments do not match the `TimerAction` values in the code, which are the ones used above.
- `enable_diagnostics` and `enable_camera_diagnostics` are declared and forwarded to `controllers.launch.py`, but `controllers.launch.py` declares them without any node using them as a condition. Its diagnostic nodes start regardless.

### 1.2 What the world baking does (`embed_robot:=true`, the default)

`_launch_gazebo` in `sim.launch.py` runs at the 3 s mark and does the following:

1. Creates a unique temp directory (`tempfile.mkdtemp(prefix='vacuum_world_')`).
2. Runs `xacro` on `vacuum_description/urdf/vacuum.urdf.xacro`, writes `vacuum_robot.urdf` there, converts it with `gz sdf -p`.
3. Takes the first `model` from that SDF, names it `vacuum_robot`, replaces its pose with `spawn_x spawn_y 0 0 0 spawn_yaw`, and appends it to the `<world>` element of the chosen world file.
4. Rewrites relative texture paths (`albedo_map`, `normal_map`, `roughness_map`, `metalness_map`) to absolute paths.
5. Writes `<worldname>_with_robot.sdf` in the temp directory and passes it to Gazebo.

The code comment gives the reason: Gazebo only creates contact-sensor publishers for models that exist when the world loads, so a runtime-spawned robot never publishes contacts. With `embed_robot:=false` the world is used as-is and the `ros_gz_sim create` node spawns the robot from `/robot_description` at `-z 0.0`.

---

## 2. Package `vacuum_bringup`

Files:

```
vacuum_bringup/CMakeLists.txt
vacuum_bringup/package.xml
vacuum_bringup/launch/sim.launch.py
vacuum_bringup/launch/rviz.launch.py
vacuum_bringup/config/rviz_config.rviz
```

`CMakeLists.txt` is an `ament_cmake` package that only installs the `launch/` and `config/` directories to `share/vacuum_bringup/`. `package.xml` dependencies: `vacuum_description`, `vacuum_gazebo`, `robot_state_publisher`, `ros_gz_sim`, `ros_gz_bridge`, `rviz2`, `xacro`, and exec dependency `vacuum_eval`. It does not list `vacuum_controller` even though `sim.launch.py` calls `get_package_share_directory('vacuum_controller')`.

### 2.1 `launch/sim.launch.py` (master launch file)

Launch arguments (in the order declared):

| Argument | Default | Meaning in code |
|---|---|---|
| `use_sim_time` | `true` | Passed to robot_state_publisher, ground_truth_node, rviz2 and the controllers include |
| `use_rviz` | `true` | `IfCondition` on the `rviz2` node |
| `world` | `room` | Shorthand for a world file (table below). Ignored if `world_file` is given. |
| `world_file` | computed from `world` | Absolute path of the SDF. The default is a `PythonExpression` that maps `world` to a file in `vacuum_gazebo/worlds`. |
| `headless` | `false` | `true` starts Gazebo with `-r -s` (server only, no GUI); otherwise `-r` |
| `gz_verbose` | empty | Extra flags added to `gz_args`, e.g. `-v 4` |
| `embed_robot` | `true` | See section 1.2 |
| `spawn_x`, `spawn_y`, `spawn_yaw` | `0.0` | Robot start pose, used in the baked pose or the `create` node (`-x`, `-y`, `-Y`) |
| `enable_odom_noise` | `false` | Forwarded to `controllers.launch.py`; enables `odometry_noise_node` noise |
| `enable_diagnostics` | `true` | Forwarded (see caveat in 1.1) |
| `odom_mode` | `clean` | `clean` or `eval`; forwarded (section 2.3) |
| `odom_noise` | `false` | Forwarded; in eval mode controls the `odom_noise_node` `enable_noise` parameter |
| `odom_noise_seed` | `0` | Forwarded; the `seed` parameter of `odom_noise_node` |
| `extra_bridge_config` | empty | Path to a second `parameter_bridge` config file (docstring example: `gz_bridge_dynamic.yaml`) |
| `enable_camera_diagnostics` | `true` | Forwarded (see caveat in 1.1) |
| `render_gpu` | `false` | `true` wraps the Gazebo include in a scoped `GroupAction` that sets `GALLIUM_DRIVER=d3d12` |
| `gpu_adapter` | `Intel` | With `render_gpu:=true`, sets `MESA_D3D12_DEFAULT_ADAPTER_NAME` unless empty |

Also read from the environment: `VACUUM_GZ_HEADLESS_RENDERING`. When it equals `1` and `headless:=true`, Gazebo gets `-r -s --headless-rendering`. The code comment says it is off by default because it segfaults on WSL.

World shorthands (`WORLD_MAP`, all in `vacuum_gazebo/worlds/`):

| `world:=` | File |
|---|---|
| `room` | `empty_world.sdf` |
| `apartment` | `apartment.sdf` |
| `office` | `office.sdf` |
| `corridor` | `corridor.sdf` |
| `empty_room` | `empty_room.sdf` |
| `cluttered_room` | `cluttered_room.sdf` |
| `two_rooms_door` | `two_rooms_door.sdf` |
| `multi_room_loop` | `multi_room_loop.sdf` |
| `maze_dead_ends` | `maze_dead_ends.sdf` |
| `symmetric_hall` | `symmetric_hall.sdf` |
| anything else | `empty_world.sdf` |

Nodes and includes:

| Name | Package / executable | Parameters / arguments | Condition |
|---|---|---|---|
| `robot_state_publisher` | `robot_state_publisher` / `robot_state_publisher` | `robot_description` (xacro output wrapped in `ParameterValue(value_type=str)`), `use_sim_time`, `publish_frequency` 50.0 | always |
| Gazebo include | `ros_gz_sim` `launch/gz_sim.launch.py` | `gz_args` built from headless, `gz_verbose`, world path; `on_exit_shutdown: true` | always, after 3 s |
| `ros_gz_bridge` | `ros_gz_bridge` / `parameter_bridge` | `config_file` = `vacuum_gazebo/config/gz_bridge.yaml` | always |
| `ros_gz_bridge_extra` | `ros_gz_bridge` / `parameter_bridge` | `config_file` = `extra_bridge_config` | `extra_bridge_config != ''` |
| `ground_truth_node` | `vacuum_eval` / `ground_truth_node` | `use_sim_time` | always |
| `spawn_vacuum_robot` | `ros_gz_sim` / `create` | `-name vacuum_robot -topic /robot_description -x -y -z 0.0 -Y` | `embed_robot` is not `true`; delayed 3 s |
| controllers include | `vacuum_controller` `launch/controllers.launch.py` | forwards `use_sim_time`, `enable_odom_noise`, `enable_diagnostics`, `enable_camera_diagnostics`, `odom_mode`, `odom_noise`, `odom_noise_seed` | always |
| `rviz2` | `rviz2` / `rviz2` | `-d <vacuum_bringup>/config/rviz_config.rviz`, `use_sim_time` | `use_rviz` |

Bridged topics in `vacuum_gazebo/config/gz_bridge.yaml` (ROS topic <- Gazebo topic), as the file stands:

| ROS topic | Gazebo topic |
|---|---|
| `/clock` | `/clock` |
| `/camera/color/image_raw` | `/camera/image_raw/image` |
| `/camera/color/camera_info` | `/camera/image_raw/camera_info` |
| `/camera/depth/image_rect_raw` | `/camera/image_raw/depth_image` |
| `/camera/depth/camera_info` | `/camera/image_raw/camera_info` |
| `/ground_truth/odom_raw` | `/model/vacuum_robot/ground_truth_odom` |
| `/vacuum_robot/contacts/chassis` | same name |
| `/vacuum_robot/contacts/camera_mount` | same name |
| `/vacuum_robot/contacts/camera` | same name |

The `/camera/depth/points` entry is commented out in that file, although the docstring of `sim.launch.py` says 5 camera topics are bridged.

Usage examples (from the docstring):

```
ros2 launch vacuum_bringup sim.launch.py
ros2 launch vacuum_bringup sim.launch.py world:=apartment
ros2 launch vacuum_bringup sim.launch.py world:=office use_rviz:=false
ros2 launch vacuum_bringup sim.launch.py world_file:=/abs/path/custom.sdf
```

### 2.2 `launch/rviz.launch.py` (RViz only)

Starts one `rviz2` node with `-d <vacuum_bringup>/config/rviz_config.rviz` and `use_sim_time`. The simulation must already be running.

| Argument | Default |
|---|---|
| `use_sim_time` | `true` |

Usage: `ros2 launch vacuum_bringup rviz.launch.py`

### 2.3 Included file: `vacuum_controller/launch/controllers.launch.py`

This file is outside the scope folders, but `sim.launch.py` includes it, so what it starts is listed here. All entries are `TimerAction`s.

| Time | Node name | Package / executable | Notes |
|---|---|---|---|
| 2 s | `jsb_spawner` | `controller_manager` / `spawner` | arguments `joint_state_broadcaster --activate` |
| 2 s | `ddc_spawner` | `controller_manager` / `spawner` | `diff_drive_controller --activate`. In `odom_mode:=eval`, adds `--param-file vacuum_eval/config/ddc_no_tf.yaml`. |
| 12 s | `cmd_vel_relay` | `vacuum_controller` / `cmd_vel_relay.py` | default input topic |
| 12 s | `cmd_vel_relay_nav` | `vacuum_controller` / `cmd_vel_relay.py` | parameter `input_topic: /cmd_vel_smoothed` |
| 12 s | `odom_relay` | `topic_tools` / `relay` | `/diff_drive_controller/odom` to `/odom`; only when `odom_mode` is not `eval` |
| 12 s | `odom_noise_node` | `vacuum_eval` / `odom_noise_node` | only when `odom_mode == eval`; parameters `enable_noise`, `seed` |
| 13 s | `odometry_noise_node` | `vacuum_controller` / `odometry_noise_node.py` | `enable_noise`, `linear_noise_std` 0.005, `angular_noise_std` 0.003, `rate_hz` 30.0 |
| 13 s | `motion_diagnostics_node` | `vacuum_controller` / `motion_diagnostics_node.py` | `cmd_vel_timeout_warn` 0.5, `publish_rate` 2.0 |
| 15 s | `camera_diagnostics_node` | `vacuum_controller` / `camera_diagnostics_node.py` | parameters from `vacuum_gazebo/config/camera.yaml` |

### 2.4 `config/rviz_config.rviz`

Loaded by both `sim.launch.py` (when `use_rviz` is true) and `rviz.launch.py`. Key content:

| Item | Setting |
|---|---|
| Fixed Frame | `odom` |
| Displays | `Grid` (rviz_default_plugins/Grid), `RobotModel` (description topic `/robot_description`, visual enabled, collision disabled), `TF`, `Odometry` (topic `/odom`, shape Arrow) |
| Tools | Interact, MoveCamera, Select, FocusCamera, Measure, SetInitialPose (topic `/initialpose`), SetGoal (topic `/goal_pose`) |
| View | Orbit (rviz_default_plugins), target frame `<Fixed Frame>` |

---

## 3. Package `vacuum_interfaces`

The package defines no messages, services or actions. Directory contents: only `CMakeLists.txt` and `package.xml`; there are no `msg/`, `srv/` or `action/` folders.

| Item | Detail |
|---|---|
| `CMakeLists.txt` | Calls `find_package` for `ament_cmake`, `rosidl_default_generators`, `std_msgs`, `geometry_msgs`. The `rosidl_generate_interfaces(...)` call is commented out, with the comment "Stage 1: No custom interfaces defined yet". |
| Commented-out example names | `msg/VacuumStatus.msg`, `srv/SetMode.srv`, `action/NavigateToGoal.action` (with `DEPENDENCIES std_msgs geometry_msgs`). These files do not exist. |
| `package.xml` | Version 0.1.0, Apache-2.0, `member_of_group` `rosidl_interface_packages`, depends on `std_msgs` and `geometry_msgs`. Description states it is intentionally minimal and that types will be added as subsystems are implemented. |

So there are no field tables to give: the rest of the system uses standard types only. The utility scripts below use `geometry_msgs/Twist`, `nav_msgs/Odometry`, `sensor_msgs/*`, `tf2_msgs/TFMessage`, `nav_msgs/OccupancyGrid` and `rtabmap_msgs/Info`.

---

## 4. Package `vacuum_utils`

All scripts live in `vacuum_utils/scripts/`. `CMakeLists.txt` installs all 12 with `install(PROGRAMS ...)` to `lib/vacuum_utils`, so they can be run with `ros2 run vacuum_utils <script>`. `package.xml` depends on `rclpy`, `tf2_ros`, `tf2_py`, `sensor_msgs`, `nav_msgs`, `xacro`.

Summary:

| Script | Needs running sim? | Output |
|---|---|---|
| `drive_robot.py` | yes | publishes `/cmd_vel` |
| `check_tf.py` | yes | console report, exit code |
| `collect_metrics.py` | yes | CSV + console |
| `validate_urdf.sh` | no | console, exit code |
| `validate_controllers.sh` | yes | console, exit code |
| `validate_camera.sh` | yes | console, exit code |
| `record_trajectory.py` | yes | drives robot, console drift report, optional rosbag |
| `record_stage4.sh` | yes (SLAM running) | zstd-compressed rosbag |
| `benchmark_camera.py` | yes | CSV + console |
| `benchmark_slam.py` | yes (SLAM running) | CSV + console |
| `evaluate_trajectory.py` | no (reads a bag, needs `evo`) | text, zip, PDF, CSV |
| `graphify.py` | no | Markdown and Mermaid files |

### 4.1 `drive_robot.py`

- Purpose: node `auto_driver` that drives a fixed open-loop pattern for mapping runs.
- Arguments: none.
- Publishes: `geometry_msgs/Twist` on `/cmd_vel` at about 10 Hz (0.1 s sleep).
- Sequence: waits 2 s; then 3 laps of 4 sides. Each side is forward at `linear.x = 0.15` for 6 s, stop 0.5 s, turn at `angular.z = 0.3` for 5.23 s (commented as about 90 degrees), stop 0.5 s. Then a final spiral for 15 s at `linear.x = 0.12`, `angular.z = 0.25`. It ends with a zero Twist. On Ctrl+C it sends a zero Twist.
- Timing uses wall-clock `time.time()`, not sim time.
- Usage: `python3 drive_robot.py` or `ros2 run vacuum_utils drive_robot.py`.

### 4.2 `check_tf.py`

- Purpose: checks that the expected TF frames exist (Stage 1 tree). Node name `vacuum_tf_checker`.
- Arguments: `--timeout` (float, default 10.0 s, wait for `odom` to `base_footprint`). Unknown arguments are passed to rclpy.
- Expected parent to child pairs: `odom`>`base_footprint`, `base_footprint`>`base_link`, and from `base_link`: `left_wheel_link`, `right_wheel_link`, `caster_wheel_link`, `camera_mount_link`, `arm_mount_link`, `vacuum_mount_link`.
- Output: a table with a pass/fail mark, translation x/y/z for each edge, the list of all frames in the TF buffer, and an overall verdict.
- Exit code: 0 if all pass, 1 otherwise (including timeout).
- Usage: `ros2 run vacuum_utils check_tf.py --timeout 10`.

### 4.3 `collect_metrics.py`

- Purpose: Stage 1 system metrics logger. Node `vacuum_metrics_collector`.
- Arguments: `--duration` (int, default 60 s); `--output` (default `~/paper_ws/results/stage1/metrics_<YYYYmmdd_HHMMSS>.csv`).
- Subscribes: `/tf` (`TFMessage`), `/odom` (`Odometry`), `/joint_states` (`JointState`).
- Every 1 s it records `time_s, cpu_pct, ram_mb, ram_pct, tf_hz, odom_hz, joint_hz`. The Hz values are the number of messages received in the last 1 s. CPU and RAM use `psutil`; if it is missing they are -1.0.
- Output: the CSV (parent directory created if needed) and a printed table and mean/max summary at the end.

### 4.4 `validate_urdf.sh`

- Purpose: validates the robot description without running the simulation.
- Argument: optional path to a `.xacro` file as `$1`; otherwise it uses `vacuum_description/urdf/vacuum.urdf.xacro` found through `ros2 pkg prefix`.
- Steps: (1) `xacro` expansion to a temp file; (2) `check_urdf`; (3) counts `<link ` and `<joint ` lines and lists up to 20 names found in `name="..."` attributes.
- Sources `/opt/ros/jazzy/setup.bash` and the workspace `install/setup.bash` if present. Removes its temp dir on success.
- Exit codes: 0 pass, 1 xacro missing or expansion failed, 2 `check_urdf` failed.

### 4.5 `validate_controllers.sh`

- Purpose: Stage 2 check that the controllers and topics are alive.
- Argument: `$1` is used directly as the timeout in seconds (default 20). The docstring example `--timeout 30` would set the timeout to the literal string `--timeout`, which the arithmetic comparison would not treat as a number; only a plain number works.
- Steps: waits for service `/controller_manager/list_controllers`; runs `ros2 control list_controllers`; checks that `joint_state_broadcaster` and `diff_drive_controller` appear with "active"; runs `ros2 topic hz --once` on `/joint_states` and `/odom` (printed only; failures there do not change the result); prints a summary.
- Exit codes: 0 all good, 1 controller_manager not found, 2 a controller is missing or not active. The documented exit code 3 is not produced by the code.

### 4.6 `validate_camera.sh`

- Purpose: Stage 3 check of the simulated D435i camera.
- Argument: `--quick` skips the three FPS tests.
- Tests: T1 topics exist (`/camera/color/image_raw`, `/camera/color/camera_info`, `/camera/depth/image_rect_raw`, `/camera/depth/camera_info`, `/camera/depth/points`, `/camera/diagnostics`); T2 color `camera_info` has `width: 640` and `height: 480`; T3 RGB at least 25 Hz; T4 depth at least 25 Hz; T5 `/camera/depth/points` at least 10 Hz; T6 frames `camera_link`, `camera_color_frame`, `camera_color_optical_frame`, `camera_depth_frame`, `camera_depth_optical_frame` reachable from `base_link` (or found in `/tf_static`); T7 `frame_id` `camera_color_optical_frame` in the image header; T8 `/camera/diagnostics` message contains "D435i"; T9 one message within 2.5 s on the three image/points topics.
- Exit code: the number of failed checks (0 = all passed).
- Note: the bridge file currently has the `/camera/depth/points` bridge commented out, so T1, T5 and T9 depend on that topic being published some other way.

### 4.7 `record_trajectory.py`

- Purpose: executes a canned motion test and prints odometry displacement; optionally records a bag. Node `trajectory_executor`.
- Arguments:

| Argument | Default | Meaning |
|---|---|---|
| `--trajectory` | `forward` | `forward`, `reverse`, `rotate`, `square`, `circle`, `figure8` |
| `--duration` | 30.0 | seconds, for `circle` and `figure8` |
| `--distance` | 1.0 | metres, for `forward` and `reverse` |
| `--linear` | 0.2 | m/s |
| `--angular` | 0.5 | rad/s |
| `--bag` | empty | if set, starts `ros2 bag record -o <path> /cmd_vel /odom /tf /joint_states /motion_diagnostics` |

- Motions: forward/reverse drive for `distance / linear` seconds; rotate turns for `2*pi / angular` seconds; square does four sides of 1 m and 90 degree left turns with 0.3 s pauses; circle holds `linear` and `angular` for `duration`; figure8 runs `duration/2` with negative angular then `duration/2` with positive angular.
- Timing is open-loop and wall-clock; `/odom` is only used to wait for the first message (10 s timeout) and for the final report.
- Subscribes `/odom`, publishes `/cmd_vel`.
- Output: prints final displacement dx/dy, linear drift in metres and heading drift in degrees (final minus start yaw, not wrapped).

### 4.8 `record_stage4.sh`

- Purpose: records a rosbag of SLAM-relevant topics.
- Arguments: `$1` environment label (default `room`), `$2` duration in seconds (default 0 = until Ctrl+C).
- Output: bag at `bags/stage4_manual_mapping/<env>/slam_<env>_<YYYYmmdd_HHMMSS>`, relative to the current directory. Storage `sqlite3`, `--compression-mode file`, `--compression-format zstd`.
- Topics (20, each given with `-e`): `/camera/color/image_raw`, `/camera/color/camera_info`, `/camera/depth/image_rect_raw`, `/camera/depth/camera_info`, `/camera/depth/points`, `/odom`, `/tf`, `/tf_static`, `/joint_states`, `/cmd_vel`, `/robot_description`, `/rtabmap/map`, `/rtabmap/cloud_map`, `/rtabmap/odom`, `/rtabmap/info`, `/rtabmap/mapData`, `/rtabmap/mapGraph`, `/camera/diagnostics`, `/diagnostics`, `/clock`.
- Note: the `-e` flag of `ros2 bag record` takes a regular expression, so the topic names are used as regexes.
- At the end it prints the replay command (`ros2 bag play ... --clock`) and the `evaluate_trajectory.py` command.

### 4.9 `benchmark_camera.py`

- Purpose: timed performance benchmark of the camera pipeline. Node `benchmark_camera_node`.
- Arguments: `--duration` (int, default 60), `--warmup` (int, default 5), `--output` (default `bags/stage3/benchmark_<timestamp>.csv`), `--noise-mode` (`ideal` or `realistic`, default `ideal`; for `realistic` it only appends `_realistic` to the CSV file name).
- Subscribes: `/camera/color/image_raw` (Image), `/camera/depth/image_rect_raw` (Image), `/camera/depth/points` (PointCloud2).
- Every 0.5 s after warmup it takes a snapshot: FPS over a 2 s window, latency (`time.monotonic()` minus the message header stamp, in ms), process CPU% and process RSS memory via `psutil`, plus cumulative frame counts.
- CSV columns: `timestamp_s, color_fps, depth_fps, points_fps, color_latency_ms, depth_latency_ms, points_latency_ms, cpu_pct, ram_mb, color_frames, depth_frames, points_frames`.
- Pass criteria compared against the mean of each column: color FPS >= 25, depth FPS >= 25, points FPS >= 10, color latency <= 100 ms, depth latency <= 100 ms, CPU <= 85 %.
- Exit code: 0 if all pass, otherwise 1. Exits with an error if `rclpy` or `psutil` is missing.

### 4.10 `benchmark_slam.py`

- Purpose: RTAB-Map performance benchmark. Node `benchmark_slam_node`. Publishes nothing.
- Arguments: `--duration` (int, default 300), `--warmup` (int, default 10), `--environment` (default `room`, used in the file name), `--output` (directory, default `bags/stage4_manual_mapping`).
- Subscribes: `/rtabmap/info` (`rtabmap_msgs/Info`, only if the package imports), `/rtabmap/map` (`OccupancyGrid`), `/odom` (`Odometry`).
- From `Info` it reads `nodes_count` (as keyframes), `loop_closure_id` (as loop closures), `database_memory_used` (as DB size), and `time_ms` or `processing_time_ms` (as update time), each guarded by `hasattr`. Map area is the count of cells with value >= 0 times resolution squared. Trajectory length is the summed step distance of `/odom`.
- Output: `<output>/slam_benchmark_<environment>_<YYYYmmdd_HHMMSS>.csv` with columns `timestamp_s, keyframes, loop_closures, db_size_mb, map_area_m2, trajectory_m, rtabmap_update_ms, cpu_pct, ram_mb`, one row per second after warmup, and a console summary.
- Pass criteria: mean update time <= 2000 ms, mean CPU <= 85 %, final loop closures >= 1, DB growth <= 10 MB/min. The CPU and RAM figures are for the benchmark process itself (`psutil.cpu_percent`, `Process().memory_info()`), not for the whole system.
- Exit code 0 if all four pass, else 1.

### 4.11 `evaluate_trajectory.py`

- Purpose: computes ATE and RPE between a reference and an estimated odometry topic in a rosbag by calling the `evo` tools. It does not use ROS at run time.
- Requires: `evo_ape` on the PATH (checked), otherwise exits with an install hint.
- Arguments: `--bag` (required, bag path), `--ref-topic` (default `/odom`), `--est-topic` (default `/rtabmap/odom`), `--environment` (default `room`), `--output-dir` (default `bags/stage4_manual_mapping/<environment>`).
- Commands run: `evo_ape bag2 <bag> <ref> <est> --align --correct_scale -p --plot_mode xy --save_results ate_results.zip --save_plot trajectory_plot.pdf`, and `evo_rpe bag2 <bag> <ref> <est> --delta 1 --delta_unit m --align --save_results rpe_results.zip`.
- Outputs in the output directory: `ate_result.txt`, `rpe_result.txt`, `ate_results.zip`, `rpe_results.zip`, `trajectory_plot.pdf`, `metrics_summary.csv` (columns `metric, value, unit, environment, timestamp`, metrics rmse/mean/median/std/min/max, parsed from the `evo` text output).
- Criteria in the printed summary: ATE RMSE <= 0.30 m, RPE RMSE <= 0.05 m. The script itself does not set an exit code from them.
- Docstring versus code: the docstring lists `.png` plots (`ate_error_plot.png`, `rpe_error_plot.png`) and a `--live` mode; the code writes only `trajectory_plot.pdf` and has no `--live` option. It also says the reference is wheel odometry, which is the default reference only because `--ref-topic` defaults to `/odom`.

### 4.12 `graphify.py`

- Purpose: scans the workspace and produces architecture diagrams (Mermaid) and a summary.
- Arguments: `--workspace` (default: three levels above the script, i.e. the workspace root), `--output` (default `<workspace>/graphify_output`), `--model` (default `gemini-2.0-flash`), `--env` (default `<workspace>/.env`), `--no-ai` (static mode).
- Scanner: reads every `package.xml`, `*.launch.py` (regex for `executable=` and `get_package_share_directory`), every `.py` file using `rclpy` (regex for `create_publisher`, `create_subscription`, `create_service`), `*.xacro` includes, `*.yaml` (first 1500 characters) and a file tree of 250 entries.
- Without `--no-ai`: it needs `GEMINI_API_KEY` (from the environment or the `.env` file), builds a prompt from the scan and sends it over HTTPS to `https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent`. This sends source snippets of the workspace to a third-party service. On HTTP 429 or other errors it falls back to static generation. `--no-ai` makes no network call.
- Static generator sections: `PACKAGE_GRAPH`, `DATAFLOW_GRAPH`, `TF_TREE`, `LAUNCH_SEQUENCE`, `CONTROLLER_ARCH`, `SUMMARY`. Any section missing from the AI answer is filled from the static generator. The static `LAUNCH_SEQUENCE` text is hard-coded and describes an `exploration.launch.py` flow (`./start.sh explore apartment`, SLAM at T+12 s, Nav2 at T+20 s, exploration nodes at T+28 s); it is not generated from the launch files here.
- Outputs in the output directory: `workspace_graph.md`, `summary.md`, and one `<section>.mmd` per diagram section (lower-case name, e.g. `package_graph.mmd`).

---

## 5. Observations to keep in mind

- `vacuum_interfaces` is an empty placeholder; nothing depends on custom message types.
- Several script docstrings and launch comments disagree with the code (timings in `sim.launch.py` and `controllers.launch.py`, `--timeout` in `validate_controllers.sh`, plots and `--live` in `evaluate_trajectory.py`). The behaviour above follows the code.
- `/camera/depth/points` is commented out in `gz_bridge.yaml`, while three utility scripts expect it.
- Only `graphify.py` without `--no-ai` sends data off the machine.

One-line summary: `sim.launch.py` starts robot_state_publisher, a robot-baked Gazebo world, the bridges, ground truth, the controller include and RViz; `vacuum_interfaces` defines no custom types; `vacuum_utils` is 12 check, record, benchmark and diagram scripts.
