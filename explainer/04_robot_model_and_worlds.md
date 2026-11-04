# 04. The simulated robot and the test worlds

Scope: `Navigation/Simulation/vacuum_ws/src/vacuum_description` (robot model), `vacuum_gazebo` (worlds, bridge config, spawn launch), plus the split and scenario definitions in `vacuum_eval/config/worlds.yaml` and `worlds_scenarios.yaml`. A few facts that live in other packages (`vacuum_controller/config/controllers.yaml`, `vacuum_bringup/launch/sim.launch.py`) are included because the robot model cannot be understood without them; they are marked.

All numbers below were read from the files. Where a file's own comment contradicts its values, both are given.

---

## 1. High-level picture

* The robot is a small differential-drive "vacuum" platform: a 0.30 x 0.25 x 0.10 m box chassis, two driven wheels, one passive front ball caster, an Intel RealSense D435i-style RGB-D camera on top, and two placeholder boxes (arm mount, vacuum module mount). There are no meshes; every link is a primitive box, cylinder or sphere. (`vacuum_description` contains only `urdf/*.xacro`, `CMakeLists.txt` and `package.xml`; there is no `meshes/` or `config/` directory.)
* The only exteroceptive sensor is the RGB-D camera. There is no lidar in the model. Three contact sensors report body collisions (used for the safety metrics), and an odometry-publisher plugin gives the true robot pose (ground truth for evaluation).
* Driving is done by `ros2_control` (`gz_ros2_control` plugin with a diff-drive controller), so `/cmd_vel`, `/odom`, `/tf` and `/joint_states` are native ROS 2 topics. `ros_gz_bridge` only carries the clock, camera data, ground truth and contacts.
* There are 18 world files. 10 are full-size "coverage / SLAM / navigation" environments (including the original `empty_world`), and 8 are small obstacle-avoidance scenario arenas. The evaluation splits them into a dev set (tuning allowed) and a frozen test set.

---

## 2. Robot model (URDF/xacro)

Entry file `urdf/vacuum.urdf.xacro` includes, in this order: `_properties`, `_materials`, `_macros`, `_base`, `_wheels`, `_ros2_control`, `_sensors`, `_gazebo`. All dimensions are defined once in `_properties.xacro`. Robot name: `vacuum_robot`. Frame convention: x forward, y left, z up.

### 2.1 Links and joints

| Link | Parent / joint (type) | Joint origin (xyz in parent frame, m) | Geometry | Mass (kg) |
|---|---|---|---|---|
| `base_footprint` | root | n/a | virtual, no geometry, no mass | 0 |
| `base_link` | `base_footprint` / `base_footprint_joint` (fixed) | 0, 0, 0.093 | box 0.300 x 0.250 x 0.100 (visual and collision) | 2.000 |
| `left_wheel_link` | `base_link` / `left_wheel_joint` (continuous, axis y) | -0.080, +0.134, -0.060 | cylinder r 0.033, length 0.018, rotated to lie along y | 0.250 |
| `right_wheel_link` | `base_link` / `right_wheel_joint` (continuous, axis y) | -0.080, -0.134, -0.060 | same as left | 0.250 |
| `caster_wheel_link` | `base_link` / `caster_wheel_joint` (fixed) | +0.132, 0, -0.075 | sphere r 0.018 | 0.050 |
| `camera_mount_link` | `base_link` / `camera_mount_joint` (fixed) | +0.100, 0, +0.0625 | box 0.025 x 0.090 x 0.025 | 0.050 |
| `camera_link` | `camera_mount_link` / `camera_joint` (fixed) | 0, 0, +0.025 | box 0.025 x 0.090 x 0.025 (D435i body) | 0.072 |
| `camera_color_frame` | `camera_link` / `camera_color_joint` (fixed) | 0, 0, 0 | massless frame | 0 |
| `camera_color_optical_frame` | `camera_color_frame` / `camera_color_optical_joint` (fixed) | 0, 0, 0; rpy -1.5707963, 0, -1.5707963 | massless frame | 0 |
| `camera_depth_frame` | `camera_link` / `camera_depth_joint` (fixed) | 0, 0, 0 | massless frame | 0 |
| `camera_depth_optical_frame` | `camera_depth_frame` / `camera_depth_optical_joint` (fixed) | 0, 0, 0; rpy -1.5707963, 0, -1.5707963 | massless frame | 0 |
| `arm_mount_link` | `base_link` / `arm_mount_joint` (fixed) | -0.050, 0, +0.060 | box 0.050 x 0.050 x 0.020 | 0.050 |
| `vacuum_mount_link` | `base_link` / `vacuum_mount_joint` (fixed) | +0.080, 0, -0.055 | box 0.060 x 0.060 x 0.010 | 0.100 |

Sum of the listed masses: 2.822 kg (computed from the table).

TF tree: `base_footprint -> base_link -> {left_wheel_link, right_wheel_link, caster_wheel_link, camera_mount_link -> camera_link -> {camera_color_frame -> camera_color_optical_frame, camera_depth_frame -> camera_depth_optical_frame}, arm_mount_link, vacuum_mount_link}`.

Notes on the numbers:

* Wheel centre height above ground = wheel radius = 0.033 m. `base_link` origin is 0.093 m above ground (chassis bottom clearance 0.043 m, per the xacro comment).
* Wheel separation is 0.268 m (`wheel_separation`); the joints sit at y = +/-0.134 (half of it). Because the chassis half-width is 0.125 m and the wheel thickness is 0.018 m, the wheel outer faces (0.143 m from the centreline) stick out beyond the chassis sides. This is derived from the numbers, not stated in the files.
* The drive axle is 0.080 m behind the `base_link` origin (`wheel_joint_x = -0.080`); the caster is at +0.132 m, near the front edge (chassis front face at +0.150).
* Overall top of the robot: `camera_link` centre is at 0.093 + 0.0625 + 0.025 = 0.1805 m above ground; with its half-height 0.0125 m the top is about 0.193 m (computed).
* The caster has a fixed joint (no swivel); free rolling is imitated by near-zero friction (see 2.4).
* The wheel joints carry `dynamics damping=0.01 friction=0.10`.
* Inertias are computed in `_macros.xacro` from the standard box, cylinder and sphere formulas. `base_link` uses the hand-computed values in `_properties.xacro` (Ixx 0.012083, Iyy 0.016667, Izz 0.025417).
* Visual materials (RViz): chassis light_grey, wheels dark_grey, caster white, camera mount and camera dark_grey, arm mount yellow, vacuum mount blue.

### 2.2 Camera (Intel RealSense D435i, simulated)

Defined in `_gazebo.xacro` as a Gazebo `rgbd_camera` sensor named `d435i`, attached to `camera_link`. Values come from `_properties.xacro` section 6 (comment: "Intel D435i datasheet v0.9").

| Parameter | Value |
|---|---|
| Sensor type | `rgbd_camera` (gz-sensors) |
| Colour resolution / format | 640 x 480, `R8G8B8` |
| Update rate | 30 Hz (`update_rate` = `d435i_color_fps`), `always_on` 1, `visualize` false |
| Horizontal FOV used by the sensor | 1.2112 rad (69.4 deg) |
| Clip planes | near 0.105 m, far 10.0 m (colour and depth) |
| Depth output | `<depth_camera><output>depths</output>`, same clip planes |
| Noise | gaussian, mean 0.0, stddev 0.0, i.e. noise is off |
| Gazebo topic root | `camera/image_raw` |
| `gz_frame_id` | `camera_color_optical_frame` |
| Colour/depth module offset | both co-located at `camera_link` centre (the xacro comment says the real colour module is 11.5 mm to the right; this is not modelled) |

Things that are defined but not wired in:

* `_properties.xacro` defines `d435i_depth_hfov = 1.5010` rad (86.0 deg) and depth width/height/fps, but the sensor block only uses `d435i_color_hfov`. A single `<horizontal_fov>` is set for the whole `rgbd_camera`. `camera.yaml` also lists depth hfov 86.0 deg but is not read by the Gazebo sensor. `docs/REPO_FACTS_ITEMS_1_TO_25.md` (Item 12) records the same conclusion: the sensor is 69.4 deg and the 86 deg value does not match it (the Nav2 STVL clearing frustum is configured with 86 deg there).
* The "realistic" noise values in `vacuum_gazebo/config/camera.yaml` (depth stddev 0.005, colour stddev 0.007) are only parameters of a diagnostics node's config; the URDF noise stays at 0.0 (also stated in REPO_FACTS Item 12).

### 2.3 Sensors that are not the camera

Three `contact` sensors are attached to `base_footprint` (the model is lumped, so collision names are the post-lumping names). Comment in the file: "body collisions only, not wheels/caster", spec 06 section 6.2.

| Sensor | Collision monitored | Gazebo topic | Rate |
|---|---|---|---|
| `chassis_contact` | `base_footprint_fixed_joint_lump__base_link_collision` | `/vacuum_robot/contacts/chassis` | 50 Hz |
| `camera_mount_contact` | `base_footprint_fixed_joint_lump__camera_mount_link_collision_2` | `/vacuum_robot/contacts/camera_mount` | 50 Hz |
| `camera_contact` | `base_footprint_fixed_joint_lump__camera_link_collision_3` | `/vacuum_robot/contacts/camera` | 50 Hz |

There is no IMU, lidar or wheel-encoder sensor element in the URDF; wheel position/velocity come from the `ros2_control` state interfaces.

### 2.4 Plugins and surface properties (`_gazebo.xacro`, `_ros2_control.xacro`)

| Item | Setting |
|---|---|
| `gz_ros2_control::GazeboSimROS2ControlPlugin` (`gz_ros2_control-system`) | loads `vacuum_controller/config/controllers.yaml` |
| `ros2_control` system `VacuumRobotHW` | hardware plugin `gz_ros2_control/GazeboSimSystem`; joints `left_wheel_joint`, `right_wheel_joint`, each with a velocity command interface (min -10.0, max +10.0 rad/s) and position and velocity state interfaces. The comment says "~0.33 m/s max (10 rad/s x 0.033 m)"; the controller's own speed limit is lower (see 2.5). |
| `gz::sim::systems::OdometryPublisher` (`gz-sim-odometry-publisher-system`) | frame `world`, robot base frame `base_footprint`, topic `/model/vacuum_robot/ground_truth_odom`, 30 Hz, 2 dimensions, gaussian_noise 0. File comment: it replaces the pose-vector bridge because that conversion drops entity names; it is read by `ground_truth_node`. |
| Drive wheel contact (both wheels) | `mu1` 200.0, `mu2` 100.0, `kp` 1.0e6, `kd` 1.0 |
| Caster contact | `mu1` 0.001, `mu2` 0.001, `kp` 1.0e6, `kd` 1.0 |
| Chassis and mounts | Gazebo material only; `selfCollide` false on every link that sets it |

The camera-mount, arm-mount and vacuum-mount links have collision boxes (via the `mount_placeholder` macro), as does `camera_link`.

### 2.5 Controller settings (outside the two scoped packages: `vacuum_controller/config/controllers.yaml`)

| Parameter | Value |
|---|---|
| `controller_manager.update_rate` | 50 Hz |
| `wheel_separation`, `wheel_radius` | 0.268 m, 0.033 m (must match the xacro) |
| Separation / radius multipliers | 1.0 (an earlier 0.945 separation multiplier was reverted, per the file comment) |
| `publish_rate` | 30 Hz; `odom_frame_id` `odom`; `base_frame_id` `base_footprint`; `enable_odom_tf` true; `open_loop` false |
| Velocity rolling window | 10 |
| `cmd_vel_timeout` | 0.5 s |
| Linear x limits | +/-0.5 m/s, acceleration +/-1.0 m/s^2 |
| Angular z limits | +/-2.0 rad/s, acceleration +/-2.0 rad/s^2 |
| Pose covariance diagonal | [0.001, 0.001, 1e6, 1e6, 1e6, 0.001] |
| Twist covariance diagonal | [0.001, 0.001, 1e6, 1e6, 1e6, 0.01] |

The comment in that file says the 50 Hz control rate "matches Gazebo physics step (1000 Hz / 20)". The world files actually use a 250 Hz physics step (section 4), so 5 physics steps fall in each control cycle. Nav2 applies lower limits than the controller (0.30 m/s, 1.0 rad/s according to REPO_FACTS Item 13); those are in the Nav2 package, not here.

### 2.6 Sim versus the physical robot (only what the docs state)

`docs/REPO_FACTS_ITEMS_1_TO_25.md` (Item 13) states that the real robot is about 0.60 x 0.50 m and 50 kg, and that "the simulation is a scaled model". It also states that the real D435i mount and the real robot's wheel track and encoder details were NOT FOUND in the repository (Items 10 and 12). The xacro comments describe the camera as a Gazebo stand-in for the hardware driver (`realsense2_camera`), with no URDF change needed on hardware. Nothing further is documented about sim-vs-real differences in the files read.

---

## 3. Gazebo to ROS bridge

Bridge file `vacuum_gazebo/config/gz_bridge.yaml`, started by `sim.launch.py` as a `ros_gz_bridge parameter_bridge` node (`ros_gz_bridge`). A second optional bridge node (`ros_gz_bridge_extra`) loads another YAML given by the launch argument `extra_bridge_config` (used for `gz_bridge_dynamic.yaml`).

### 3.1 Bridged topics

| ROS topic | Gazebo topic | ROS type | Gazebo type | Direction |
|---|---|---|---|---|
| `/clock` | `/clock` | `rosgraph_msgs/msg/Clock` | `gz.msgs.Clock` | GZ to ROS |
| `/camera/color/image_raw` | `/camera/image_raw/image` | `sensor_msgs/msg/Image` | `gz.msgs.Image` | GZ to ROS |
| `/camera/color/camera_info` | `/camera/image_raw/camera_info` | `sensor_msgs/msg/CameraInfo` | `gz.msgs.CameraInfo` | GZ to ROS |
| `/camera/depth/image_rect_raw` | `/camera/image_raw/depth_image` | `sensor_msgs/msg/Image` | `gz.msgs.Image` | GZ to ROS |
| `/camera/depth/camera_info` | `/camera/image_raw/camera_info` (same gz topic as colour) | `sensor_msgs/msg/CameraInfo` | `gz.msgs.CameraInfo` | GZ to ROS |
| `/ground_truth/odom_raw` | `/model/vacuum_robot/ground_truth_odom` | `nav_msgs/msg/Odometry` | `gz.msgs.Odometry` | GZ to ROS |
| `/vacuum_robot/contacts/chassis` | `/vacuum_robot/contacts/chassis` | `ros_gz_interfaces/msg/Contacts` | `gz.msgs.Contacts` | GZ to ROS |
| `/vacuum_robot/contacts/camera_mount` | `/vacuum_robot/contacts/camera_mount` | `ros_gz_interfaces/msg/Contacts` | `gz.msgs.Contacts` | GZ to ROS |
| `/vacuum_robot/contacts/camera` | `/vacuum_robot/contacts/camera` | `ros_gz_interfaces/msg/Contacts` | `gz.msgs.Contacts` | GZ to ROS |

Disabled (commented out): `/camera/depth/points` (`sensor_msgs/msg/PointCloud2` from `gz.msgs.PointCloudPacked`). The file's reason: a 640 x 480 cloud at 30 Hz costs a large share of CPU and nothing in the SLAM/Nav2/evaluation pipeline uses it; re-enable for visualisation.

`gz_bridge_dynamic.yaml` (dynamic-obstacle worlds only):

| ROS topic | Gazebo topic | ROS type | Gazebo type | Direction |
|---|---|---|---|---|
| `/model/dyn_box_1/cmd_vel` | `/model/dyn_box_1/cmd_vel` | `geometry_msgs/msg/Twist` | `gz.msgs.Twist` | ROS to GZ |
| `/ground_truth/model/dyn_box_1` | `/model/dyn_box_1/ground_truth_odom` | `nav_msgs/msg/Odometry` | `gz.msgs.Odometry` | GZ to ROS |

The ROS-to-Gazebo direction is used only for the moving obstacle. The robot's own `/cmd_vel` is not bridged (see 3.2).

### 3.2 Topics that are not bridged

* `/cmd_vel`, `/odom`, `/tf`, `/joint_states`: native ROS 2 topics from `diff_drive_controller` and `joint_state_broadcaster` (comment at top of `gz_bridge.yaml`).
* World ground-truth pose (`/ground_truth/poses`): not in the YAML because the Gazebo topic name contains the world name, which differs per world. `sim.launch.py` adds a separate `gt_bridge` node that reads the world name from the SDF (per the comment in `gz_bridge.yaml`).

### 3.3 Spawn and launch

`launch/spawn_robot.launch.py` (standalone): runs `robot_state_publisher` (xacro of `vacuum.urdf.xacro`, `use_sim_time` true by default) and `ros_gz_sim create` with name `vacuum_robot`, from topic `/robot_description`, at `spawn_x`, `spawn_y`, `spawn_z`, `spawn_yaw` (all default 0.0). The full stack is launched by `vacuum_bringup/launch/sim.launch.py` (outside scope); there Gazebo is started after a 3 s timer and the robot is spawned after a 3 s timer at z = 0.0, with a `headless` option (`-r -s`, optionally `--headless-rendering` when the environment variable `VACUUM_GZ_HEADLESS_RENDERING=1`) or GUI (`-r`). `sim.launch.py` bakes the robot into a temporary copy of the world SDF in a unique per-launch temp directory (spec 09 decision log).

`make_textures.py` (in `vacuum_gazebo/scripts`, not a launch file): deterministically (fixed seeds) generates `wall_00..15.png` (1024 px) and `floor_0..3.png` (2048 px) into `worlds/textures/`. The textures directory sits under `worlds/`, not directly under `vacuum_gazebo/`, and holds 22 files (these 20 plus the older `wall.png` and `floor.png`).

---

## 4. Physics and real-time settings

Identical in every one of the 18 world files (checked with an XML parse):

| Setting | Value |
|---|---|
| Physics engine | `ode` (`<physics name="default_physics" type="ode">`) |
| `max_step_size` | 0.004 s |
| `real_time_factor` | 1.0 |
| `real_time_update_rate` | 250 Hz |
| Gravity | 0 0 -9.81 (stated in `empty_world.sdf`) |
| World plugins | `Physics`, `SceneBroadcaster`, `Contact`, `UserCommands`, `Sensors` (render engine `ogre2`) |

Note: the header comment of `empty_world.sdf` says "step_size = 0.001 s -> 1000 Hz"; the actual values in the file are 0.004 s and 250 Hz. The controller YAML comment repeats the stale 1000 Hz figure.

The ground plane in `empty_world.sdf` has friction mu = mu2 = 1.0 (ODE and Bullet) and contact kp 1.0e6, kd 1.0. The other worlds contain no explicit `<mu>` setting (only one `<mu>1.0` occurrence was found across all world files). Plane size varies: 100 x 100 (`empty_world`), 30 x 30 (`cluttered_room`, `empty_room`, `maze_dead_ends`, `multi_room_loop`, `symmetric_hall`, `two_rooms_door`), 20 x 20 (the rest). Scene: ambient 0.4 0.4 0.4, shadows on, directional light `sun`.

Real time: the sim runs at whatever speed the host manages; the 1.0 factor is a target, not a guarantee. `docs/REPO_FACTS_ITEMS_1_TO_25.md` (Item 22 and a note) records that the first six exploration episodes ran at 0.73 to 0.75 real-time with three simulations in parallel; the harness measures a "true real-time factor". Sensor rates inside this: camera 30 Hz, contacts 50 Hz, ground-truth odometry 30 Hz, controller 50 Hz.

---

## 5. Worlds

### 5.1 Conventions (spec `docs/specs/09_worlds.md`)

All worlds are hand-written SDF using only boxes, cylinders (vertical axis), spheres and a ground plane, so the ground-truth rasteriser can read them exactly. Every wall/obstacle is its own static model; walls are named `wall_*`; the dynamic obstacle is the only non-static model. Rooms are closed. An object counts as an obstacle for coverage if its top is above 0.03 m and its bottom below 0.25 m (spec 03 section 3.2.4). Wall textures differ per wall to reduce visual perceptual aliasing, except in `symmetric_hall` (deliberately identical, to test aliasing). Interior sizes below are computed from the wall centre positions and thicknesses in the SDF files (inner face to inner face).

### 5.2 Split (from `vacuum_eval/config/worlds.yaml`)

The file's comment: dev = tuning allowed; test = frozen, run only via `run_batch.py --split test --confirm-test-split`. Dev holds the simplest/most familiar layouts (apartment is the tuning world); test holds the structurally hard layouts (loops, symmetry, dead ends, doors) and the hardest avoidance variants, "so tuning cannot overfit them".

| Split | Worlds | Seeds |
|---|---|---|
| dev | apartment, empty_room, cluttered_room, avoid_head_on, avoid_cluster, avoid_narrow_gap_wide, avoid_dynamic_cross | 1, 2, 3, 4, 5 |
| test | office, corridor, two_rooms_door, multi_room_loop, maze_dead_ends, symmetric_hall, avoid_narrow_gap, avoid_u_trap, avoid_dead_end, avoid_dynamic_sudden | 101 to 110 |

`empty_world` (key `room`, world name `vacuum_world`) is in neither split and has no entry in `worlds.yaml`; spec 09 section 9.3 says it is not usable for coverage (not sealed) and is used for bare control tests.

### 5.3 Coverage / SLAM / navigation worlds

Each has a `worlds.yaml` entry with `reachable_seed`, 8 to 10 `spawn_candidates` and a `fixed` goal list (6 goals); some also have a `loop_tour`. Timeout is in simulated seconds.

| World key (file) | World name | Split | Interior (computed) | Contents (from the SDF) | Purpose (spec 09) | Timeout (sim s) | Reachable seed |
|---|---|---|---|---|---|---|---|
| `room` (`empty_world.sdf`) | `vacuum_world` | none | unbounded 100 x 100 plane | ground plane only | bare control tests | n/a | n/a |
| `apartment` | `apartment_world` | dev | 6.0 x 5.0 m | 4 walls (height 3.0), ceiling (6.4 x 5.2 x 0.05 at z 3.0), sofa and back, coffee table, TV stand and TV, dining table with 2 chairs, bookshelf with 2 book rows, 2 plants (cylinder r 0.15 h 1.2 and sphere r 0.2), rug (visual only, 2 cm high), wall art | original familiar world; the tuning world | 1200 | (0, 1) |
| `empty_room` | `empty_room_world` | dev | 6.0 x 6.0 m | 4 walls (3.0 high), nothing inside | coverage upper bound | 900 | (0, 0) |
| `cluttered_room` | `cluttered_room_world` | dev | 8.0 x 8.0 m | 14 obstacles, all 0.5 m high: boxes (0.5 to 0.8 m sides) and cylinders (r 0.35 to 0.4) at fixed coordinates (x in -3, -1.5, 0, 1.5, 3; y in -3 to 3) | avoidance density | 1500 | (0, 0) |
| `office` | `office_world` | test | 8.0 x 6.0 m | 4 walls, 2 pillars (r 0.15, 3.0 high) at (+/-2.5, 1.5), meeting table 2.5 x 1.0 with 6 chairs, 4 desks with 4 monitors, 2 cabinets, whiteboard, plant | realistic furnished room | 1200 | (0, 0) |
| `corridor` | `corridor_world` | test | 12.0 x 2.0 m (spec text says about 12.0 x 2.2; the walls at y = +/-1.1 with thickness 0.2 give 2.0) | north wall, south wall in segments with door lintels (2.6 m high, 0.8 tall) and two filler walls closing the former gaps (spec 09 section 9.2), end walls, 2 extinguishers, 2 notice boards, bench, 2 bins | long featureless corridor | 900 | (0, 0) |
| `two_rooms_door` | `two_rooms_door_world` | test | two 4.0 x 4.0 m rooms (8.2 m total width with the shared wall) joined by a 0.9 m door in the 0.2 m shared wall | table_a (0.8 x 0.5 box) at (-2.5, 1.0), pot_b (cylinder r 0.25) at (2.5, -1.0) | door traversal | 1200 | (-2, 0) |
| `multi_room_loop` | `multi_room_loop_world` | test | 7.2 x 7.2 m, four rooms around a central block, four doors, a closed loop | outer walls, a central junction and 8 inner wall segments; 3 to 4 distinct small objects (0.5 m high) in each room | loop closure and drift | 1800 | (1.85, 1.85) |
| `maze_dead_ends` | `maze_dead_ends_world` | test | 8.0 x 6.0 m | 4 outer walls and 4 partition walls (7, 7, 6 plus 1, 7 m long) plus a fill block, forming serpentine passages with dead ends | stuck/recovery behaviour | 1800 | (0, 0) |
| `symmetric_hall` | `symmetric_hall_world` | test | 10.0 x 4.0 m | 4 outer walls, 8 identical pillars (r 0.25, 1.0 high) at x = -3.75, -1.25, 1.25, 3.75 and y = +/-0.9; identical wall and floor textures | perceptual aliasing | 1200 | (0, 0) |

Outer wall height is 3 m in all of these. The ceiling model exists only in `apartment` (the other files in this list have no ceiling model).

### 5.4 Obstacle-avoidance scenario worlds

From `worlds_scenarios.yaml` and the SDF files. All are closed arenas with 1.0 m high walls of 0.1 m thickness, inner size 6.0 m (x) by 4.0 m (y) (wall centres at x = +/-3.05 and y = +/-2.05). Each has one start, one goal and a 120 s (sim) timeout. They have no `worlds:` entry in `worlds.yaml`, so their split is only in the `splits` block.

| World | Split | Start / goal (x, y, yaw) | Added geometry | Intended difficulty |
|---|---|---|---|---|
| `avoid_head_on` | dev | (-2, 0, 0) to (2, 0, 0) | one box 0.4 x 0.4 x 1.0 at (0, 0) | single obstacle on the straight line |
| `avoid_cluster` | dev | (-2, 0, 0) to (2, 0, 0) | 6 obstacles: boxes 0.4 x 0.4, 0.5 x 0.5, 0.4 x 0.6 (1.0 high) and cylinders r 0.2 to 0.25 (0.6 high) | scattered obstacles |
| `avoid_narrow_gap_wide` | dev | (-2, 0, 0) to (2, 0, 0) | two walls 0.2 x 1.6 at y = +/-1.2 (gap spans y -0.4 to 0.4, i.e. 0.8 m) | tight gap, easier variant |
| `avoid_dynamic_cross` | dev | (-2, 0, 0) to (2, 0, 0) | dynamic box `dyn_box_1`, 0.4 x 0.4 x 0.5, starts (0, -1.6), moves to (0, 1.6) at 0.25 m/s | crossing moving obstacle |
| `avoid_narrow_gap` | test | (-2, 0, 0) to (2, 0, 0) | two walls 0.2 x 1.7 at y = +/-1.15 (gap spans y -0.3 to 0.3, i.e. 0.6 m) | tight gap |
| `avoid_u_trap` | test | (-2, 0, 0) to (2, 0, 0) | U shape: back wall 0.1 x 2.1 at x = 1.0; arms 1.1 x 0.1 at x = 0.5, y = +/-1.0; opens toward the start | goal behind a U |
| `avoid_dead_end` | test | (-2, -1.2, 0) to (1.2, 1.2, 0) | wall 3.0 x 0.1 at (-0.1, 0), short wall 0.6 x 0.1 at (-2.7, 0), pocket wall 0.1 x 2.0 at (-0.9, 1.0) | dead-end branch |
| `avoid_dynamic_sudden` | test | (-2, 0, 0) to (2, 0, 0) | `wall_hide` 0.1 x 1.2 at (-0.5, -1.0); `dyn_box_1` starts (0.6, -1.3), moves to (0.6, 1.3) at 0.5 m/s | sudden moving obstacle (spec: starts hidden behind a wall segment) |

The two narrow-gap clearances are computed from the wall positions. Spec 09 section 9.5 states the intent: the 0.60 m gap is "intentionally tight" against a 0.25 m wide robot and a Nav2 inflation radius (the spec says 0.35 m; REPO_FACTS Item 14 gives 0.28 m for the current configuration).

Dynamic obstacle model (both dynamic worlds): non-static, one link, mass 5 kg, inertia diagonal 0.1, gravity disabled, box collision and visual (red), plus two plugins: `gz::sim::systems::VelocityControl` on `/model/dyn_box_1/cmd_vel` and `OdometryPublisher` on `/model/dyn_box_1/ground_truth_odom` (30 Hz, 2D, no noise). The `dynamic_mover` node in `vacuum_eval` publishes the velocity command (spec 09 section 9.6) and uses waypoints, speed and `start_delay_s` (0.0 in both) from `worlds_scenarios.yaml`. The ground-truth grid ignores non-static models.

---

One-line summary: the robot is a 2.8 kg, 0.30 x 0.25 m diff-drive box (wheel r 0.033 m, track 0.268 m) with a 640 x 480, 30 Hz, 69.4 deg noiseless RGB-D camera, three 50 Hz contact sensors and a ground-truth odometry plugin, simulated in ODE at 0.004 s steps across 18 hand-built SDF worlds (7 dev, 10 test, plus the unused empty plane), bridged to ROS 2 by nine GZ-to-ROS topics plus two optional dynamic-obstacle topics.
