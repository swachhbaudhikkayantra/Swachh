# 14. Topics, TF, Actions, Services, QoS and Data Flow (low-level reference)

Scope: `/home/hrishikesh/Swachh/Navigation/Simulation/vacuum_ws/src`. Only what is in the code. Anything not visible in the repo is marked "not found". Paths below are relative to that `src` directory. Standard Nav2 / RTAB-Map / ros2_control internals that are not written in this repo are labelled "package default (not in repo)".

Notation: `file:line`. "DDC" = `diff_drive_controller`, "JSB" = `joint_state_broadcaster`, "GZ" = Gazebo Harmonic.

---

## 1. Process layout (who is started by which launch file)

| Launch file | Starts | Cite |
|---|---|---|
| `vacuum_bringup/launch/sim.launch.py` | robot_state_publisher, Gazebo (via ros_gz_sim), `ros_gz_bridge` (main), `ros_gz_bridge_extra` (optional), `ground_truth_node`, optional runtime `create` spawner, controllers.launch.py, optional RViz | `sim.launch.py:196-206, 264-267, 294-311, 316-336, 341-373` |
| `vacuum_controller/launch/controllers.launch.py` | JSB spawner, DDC spawner (t=2 s), `cmd_vel_relay` (t=12 s), `cmd_vel_relay_nav` (t=12 s), `topic_tools relay` odom (clean mode only), `odom_noise_node` (eval mode only), `odometry_noise_node`, `motion_diagnostics_node`, `camera_diagnostics_node` | `controllers.launch.py:81-248` |
| `vacuum_slam/launch/slam.launch.py` | `rtabmap_slam/rtabmap` (3 variants: fresh DB, keep DB, localization), optional RViz | `slam.launch.py:142-259` |
| `vacuum_nav2/launch/nav2.launch.py` | `topic_tools relay` /rtabmap/map to /map, `depthimage_to_laserscan_node`, bt_navigator, planner_server, controller_server, behavior_server, smoother_server, velocity_smoother, lifecycle_manager | `nav2.launch.py:67-188` |
| `vacuum_nav2/launch/nav2_localization.launch.py` | AMCL + map_server + same Nav2 nodes (used only for `scripted_goals` with AMCL) | `nav2_localization.launch.py:96-211` (names only; internals not read in detail) |
| `vacuum_exploration/launch/exploration.launch.py` | includes sim (t=0), slam (t=12 s), nav2 (t=20 s), then frontier_detector, exploration_manager, frontier_visualizer, exploration_metrics, RViz (all t=28 s) | `exploration.launch.py:111-242` (timer periods at the `TimerAction` blocks; log text at the `log_start` block) |
| `vacuum_eval/launch/eval_stack.launch.py` | `recorder_node` | `eval_stack.launch.py:14-15` |
| `vacuum_localization/launch/localization_monitor.launch.py` | localization_monitor, recovery_monitor, localization_metrics (AMCL-side; not in the frontier path) | file header `localization_monitor.launch.py:3-10`; node internals below |

How the evaluation harness composes them (`vacuum_eval/vacuum_eval/run_episode.py`):
- Method `frontier`: one `exploration.launch.py` with `odom_mode:=eval` (`run_episode.py:451-457`).
- Method `scripted_goals`: `sim.launch.py` (`odom_mode:=eval`, `run_episode.py:376-380`) plus one of three localisation modes: `gt` (plain `nav2.launch.py` + `map_server` + `gt_localization_node`, `:464-475`), `slam` (`slam.launch.py` + `nav2.launch.py`, `:479-486`), or AMCL (`nav2_localization.launch.py`, `:490-492`). Then `goal_sender` and `dynamic_mover` as late processes (`:497-512`).
- Method `responsiveness`: sim (or loaded exploration stack with `start_manager:=false`) plus `responsiveness_test` (`:514-528`).
- The harness also starts `eval_stack.launch.py` (`:399`) and a `ros2 bag record` of `BAG_TOPICS` (`:31-36, :751`).

---

## 2. Gazebo to ROS bridge (`ros_gz_bridge parameter_bridge`)

Config: `vacuum_gazebo/config/gz_bridge.yaml` (main), `gz_bridge_dynamic.yaml` (extra, only if `extra_bridge_config` is set; `sim.launch.py:303-311`). QoS for bridge entries: not set in either yaml (not found); bridge defaults apply (package default, not in repo).

| ROS topic | GZ topic | ROS type | Direction | Cite |
|---|---|---|---|---|
| `/clock` | `/clock` | `rosgraph_msgs/msg/Clock` | GZ to ROS | `gz_bridge.yaml:29-33` |
| `/camera/color/image_raw` | `/camera/image_raw/image` | `sensor_msgs/msg/Image` | GZ to ROS | `gz_bridge.yaml:36-40` |
| `/camera/color/camera_info` | `/camera/image_raw/camera_info` | `sensor_msgs/msg/CameraInfo` | GZ to ROS | `gz_bridge.yaml:43-47` |
| `/camera/depth/image_rect_raw` | `/camera/image_raw/depth_image` | `sensor_msgs/msg/Image` | GZ to ROS | `gz_bridge.yaml:50-54` |
| `/camera/depth/camera_info` | `/camera/image_raw/camera_info` (same gz topic as color) | `sensor_msgs/msg/CameraInfo` | GZ to ROS | `gz_bridge.yaml:57-64` |
| `/camera/depth/points` | `/camera/image_raw/points` | `sensor_msgs/msg/PointCloud2` | DISABLED (commented out) | `gz_bridge.yaml:66-75` |
| `/ground_truth/odom_raw` | `/model/vacuum_robot/ground_truth_odom` | `nav_msgs/msg/Odometry` | GZ to ROS | `gz_bridge.yaml:83-87` |
| `/vacuum_robot/contacts/chassis` | same | `ros_gz_interfaces/msg/Contacts` | GZ to ROS | `gz_bridge.yaml:89-93` |
| `/vacuum_robot/contacts/camera_mount` | same | `ros_gz_interfaces/msg/Contacts` | GZ to ROS | `gz_bridge.yaml:95-99` |
| `/vacuum_robot/contacts/camera` | same | `ros_gz_interfaces/msg/Contacts` | GZ to ROS | `gz_bridge.yaml:101-105` |
| `/model/dyn_box_1/cmd_vel` | `/model/dyn_box_1/cmd_vel` | `geometry_msgs/msg/Twist` | ROS to GZ | `gz_bridge_dynamic.yaml:2-6` |
| `/ground_truth/model/dyn_box_1` | `/model/dyn_box_1/ground_truth_odom` | `nav_msgs/msg/Odometry` | GZ to ROS | `gz_bridge_dynamic.yaml:7-11` |

Notes:
- `gz_bridge.yaml:77-80` says a separate `gt_bridge` node in `sim.launch.py` publishes `/ground_truth/poses`. That node is not found in `sim.launch.py` (grep for `gt_bridge` and `ground_truth/poses` finds only that comment). Not found.
- There is no lidar or IMU bridged. The only perception sensor is the RGB-D camera (`vacuum_description/urdf/_gazebo.xacro` sensor `d435i`, type `rgbd_camera`, topic root `camera/image_raw`, `gz_frame_id` `camera_color_optical_frame`).
- GZ-side sources: rgbd camera rate `d435i_color_fps = 30`, `d435i_depth_fps = 30` (`_properties.xacro:189, 194`; `<update_rate>${d435i_color_fps}</update_rate>` in `_gazebo.xacro`); contact sensors `update_rate 50` (`_gazebo.xacro` sensors `chassis_contact`, `camera_mount_contact`, `camera_contact`); ground-truth `OdometryPublisher` `odom_publish_frequency 30`, `dimensions 2`, `odom_frame world`, `robot_base_frame base_footprint` (`_gazebo.xacro:121-129`).

---

## 3. Topic table (ROS 2)

"Rate" is only given where the code states it. Otherwise "not found".

### 3.1 Clock, sensors, ground truth

| Topic | Type | Publisher | Subscriber(s) | Rate | Cite |
|---|---|---|---|---|---|
| `/clock` | `rosgraph_msgs/Clock` | ros_gz_bridge | all nodes with `use_sim_time`; harness checks it (`run_episode.py:208-210`); bag (`:31`) | not found | `gz_bridge.yaml:29`; `sim.launch.py:101-103` |
| `/camera/color/image_raw` | `sensor_msgs/Image` | ros_gz_bridge | `rtabmap` (remap `rgb/image`); `camera_diagnostics_node`; `recorder_node` (BEST_EFFORT counter) | 30 fps (sensor `update_rate`) | `slam.launch.py:159`; `camera_diagnostics_node.py:130-132`; `recorder_node.py:172` |
| `/camera/color/camera_info` | `sensor_msgs/CameraInfo` | ros_gz_bridge | `rtabmap` (remap `rgb/camera_info`) | not found | `slam.launch.py:161` |
| `/camera/depth/image_rect_raw` | `sensor_msgs/Image` | ros_gz_bridge | `rtabmap` (remap `depth/image`); `depthimage_to_laserscan_node` (remap `depth`); `camera_diagnostics_node`; `recorder_node` | 30 fps | `slam.launch.py:160`; `nav2.launch.py:97`; `camera_diagnostics_node.py:134-136`; `recorder_node.py:171` |
| `/camera/depth/camera_info` | `sensor_msgs/CameraInfo` | ros_gz_bridge | `depthimage_to_laserscan_node` (remap `depth_camera_info`) | not found | `nav2.launch.py:98` |
| `/camera/depth/points` | `sensor_msgs/PointCloud2` | none (bridge entry commented out) | `camera_diagnostics_node` subscribes (`:138-140`) | n/a | `gz_bridge.yaml:66-75`; `camera.yaml:84` lists the topic name |
| `/scan_from_depth` | `sensor_msgs/LaserScan` | `depthimage_to_laserscan_node` | Nav2 STVL layers in global and local costmaps (`depth_mark`, `depth_clear`); `recorder_node` (BEST_EFFORT) | `scan_time` param 0.033 s | `nav2.launch.py:83-100`; `nav2_params.yaml:286-299, 349-362`; `recorder_node.py:173` |
| `/ground_truth/odom_raw` | `nav_msgs/Odometry` | ros_gz_bridge | `ground_truth_node` | 30 Hz (GZ plugin) | `gz_bridge.yaml:83`; `ground_truth_node.py:34` |
| `/ground_truth/odom` | `nav_msgs/Odometry` (frame `world`, child `base_footprint`) | `ground_truth_node` | `recorder_node`, `gt_localization_node`, `dynamic_mover`, `responsiveness_test` | follows input | `ground_truth_node.py:35, 66-69`; `recorder_node.py:146`; `gt_localization_node.py:50`; `dynamic_mover.py:49`; `responsiveness_test.py:57` |
| `/vacuum_robot/contacts/{chassis,camera_mount,camera}` | `ros_gz_interfaces/Contacts` | ros_gz_bridge | `recorder_node` | 50 Hz (GZ sensor) | `gz_bridge.yaml:89-105`; `recorder_node.py:166-168` |
| `/ground_truth/model/<m>` (e.g. `dyn_box_1`) | `nav_msgs/Odometry` | ros_gz_bridge_extra | `dynamic_mover`, `recorder_node` (extra models) | not found | `gz_bridge_dynamic.yaml:7-11`; `dynamic_mover.py:48`; `recorder_node.py:147-149` |
| `/model/<m>/cmd_vel` | `geometry_msgs/Twist` | `dynamic_mover` | ros_gz_bridge_extra (to GZ) | not found | `dynamic_mover.py:47`; `gz_bridge_dynamic.yaml:2-6` |

### 3.2 Drive chain and odometry

| Topic | Type | Publisher | Subscriber(s) | Rate | Cite |
|---|---|---|---|---|---|
| `/cmd_vel` | `geometry_msgs/Twist` | teleop nodes (`teleop_arrows.py:42`, `robot_steering_gui.py:36`); `responsiveness_test` (`:54`) | `cmd_vel_relay`; `motion_diagnostics_node` (`:58`); `recorder_node` (`:151`) | not found | `cmd_vel_relay.py:25-27` |
| `/cmd_vel_nav` | `geometry_msgs/Twist` | Nav2 `controller_server` and `behavior_server` (remap `cmd_vel`); also `exploration_manager` (bootstrap spin only) | Nav2 `velocity_smoother` (remap `cmd_vel`); `recorder_node` | controller 20 Hz | `nav2.launch.py:134, 144, 164`; `nav2_params.yaml:56`; `exploration_manager.py:274, 377` |
| `/cmd_vel_smoothed` | `geometry_msgs/Twist` | `velocity_smoother` | `cmd_vel_relay_nav` (param `input_topic`); `recorder_node` | smoothing 20 Hz | `nav2.launch.py:165`; `controllers.launch.py:141-153`; `nav2_params.yaml:239-240` |
| `/diff_drive_controller/cmd_vel` | `geometry_msgs/TwistStamped` | `cmd_vel_relay` and `cmd_vel_relay_nav` (frame_id `base_footprint`, stamp = node clock) | `diff_drive_controller` (stamped input; `use_stamped_vel: false` is set in yaml, see note); `recorder_node` | same as input | `cmd_vel_relay.py:28-37`; `controllers.yaml:103` |
| `/diff_drive_controller/cmd_vel_unstamped` | `geometry_msgs/Twist` | `recovery_monitor` | not found in repo (no subscriber code found) | not found | `recovery_monitor.py:72-73` |
| `/diff_drive_controller/odom` | `nav_msgs/Odometry` | `diff_drive_controller` | clean mode: `topic_tools relay` to `/odom`. Eval mode: `odom_noise_node` | `publish_rate: 30.0` | `controllers.yaml:73`; `controllers.launch.py:159-170`; `odom_noise_node.py:65-66` |
| `/odom` | `nav_msgs/Odometry` | clean: `topic_tools relay` (node `odom_relay`). Eval: `odom_noise_node` (RELIABLE depth 10) | `rtabmap` (remap `odom`); Nav2 `bt_navigator`, `controller_server`, `velocity_smoother` (`odom_topic`); `exploration_manager`; `frontier_visualizer`; `exploration_metrics`; `motion_diagnostics_node`; `odometry_noise_node` (sub); `localization_metrics`; `recorder_node` | 30 Hz (inherits DDC) | `slam.launch.py:163`; `nav2_params.yaml:33, 61, 247`; `odom_noise_node.py:62-63`; `exploration_manager.py:263`; `recorder_node.py:147` |
| `/odom_noisy` | `nav_msgs/Odometry` | `odometry_noise_node` (QoS profile built at `odometry_noise_node.py:57`) | none found | `rate_hz: 30.0` param | `odometry_noise_node.py:57-66`; `controllers.launch.py:194-210` |
| `/joint_states` | `sensor_msgs/JointState` | `joint_state_broadcaster` (joints `left_wheel_joint`, `right_wheel_joint`) | `robot_state_publisher` (implicit, package default, not in repo); `motion_diagnostics_node`; bag | not found | `controllers.yaml:39-44`; `motion_diagnostics_node.py:60` |
| `/robot_description` | `std_msgs/String` (latched) | `robot_state_publisher` | `ros_gz_sim create` when `embed_robot:=false` | n/a | `sim.launch.py:201-205, 323-330` |

Note on `use_stamped_vel`: `controllers.yaml:103` sets `use_stamped_vel: false` while `cmd_vel_relay.py:10-13` and `controllers.launch.py:136-138` state that the Jazzy DDC subscribes only to the stamped topic. Both are in the code. Which one the DDC honours at runtime is not determined from the repo.

Note on startup: `controllers.launch.py` header (lines 7-11) says the controllers are NOT spawned there, but spawner nodes `jsb_spawner` and `ddc_spawner` are created at `controllers.launch.py:81-117` and returned at `:259-260`. The inline comment at `:72-79` also says explicit spawners are required. The code spawns them.

### 3.3 SLAM, map, exploration

| Topic | Type | Publisher | Subscriber(s) | Rate | Cite |
|---|---|---|---|---|---|
| `/rtabmap/map` | `nav_msgs/OccupancyGrid` | `rtabmap` | `topic_tools relay` to `/map`; `frontier_detector` (param `map_topic`); `exploration_manager`; `exploration_metrics`; `recorder_node` (LATCHED) | `Rtabmap/DetectionRate 1` Hz | `slam.launch.py:166`; `exploration_params.yaml:16`; `nav2.launch.py:67-74`; `rtabmap.yaml:75` |
| `/map` | `nav_msgs/OccupancyGrid` | `topic_tools relay` (`rtabmap_map_relay`) in rtabmap mode; `map_server` in gt/AMCL modes | Nav2 StaticLayer in both costmaps (`map_topic: /map`, `map_subscribe_transient_local: true`) | follows source | `nav2.launch.py:67-74`; `nav2_params.yaml:263-273, 334-336, 380-384`; `run_episode.py:469, 532` |
| `/rtabmap/info` | `rtabmap_msgs/Info` | `rtabmap` | `recorder_node` | not found | `slam.launch.py:167`; `recorder_node.py:169` |
| `/rtabmap/mapData`, `/rtabmap/mapGraph`, `/rtabmap/mapPath`, `/rtabmap/grid_prob_map`, `/rtabmap/cloud_map` | rtabmap message types (per `slam.launch.py` docstring) | `rtabmap` | `mapGraph` is in the bag list (`run_episode.py:33`); others not found | not found | `slam.launch.py:168-172` |
| `/frontiers/centroids` | `geometry_msgs/PoseArray` | `frontier_detector` | `exploration_manager` | `publish_rate: 2.0` Hz | `frontier_detector.py:97-98`; `exploration_manager.py:262-263`; `exploration_params.yaml:17` |
| `/frontiers/markers` | `visualization_msgs/MarkerArray` | `frontier_detector` | RViz only (no code subscriber found) | 2 Hz | `frontier_detector.py:95-96` |
| `/exploration/status` | `std_msgs/String` | `exploration_manager` | `frontier_visualizer`; `exploration_metrics`; bag | FSM 10 Hz (publish cadence not found) | `exploration_manager.py:268`; `frontier_visualizer.py:48`; `exploration_metrics.py:109` |
| `/exploration/current_goal` | `geometry_msgs/PoseStamped` | `exploration_manager` | `frontier_visualizer`; bag | not found | `exploration_manager.py:269`; `frontier_visualizer.py:49` |
| `/exploration/selected_marker` | `visualization_msgs/MarkerArray` | `exploration_manager` | RViz only (not found in code) | not found | `exploration_manager.py:270` |
| `/exploration/goal_events` | `std_msgs/String` (JSON) | `exploration_manager`; QoS RELIABLE depth 50 | `recorder_node` (RELIABLE) | per goal | `exploration_manager.py:271-273`; `recorder_node.py:154` |
| `/exploration/finished` | `std_msgs/Bool` | `exploration_manager`; QoS depth 1, RELIABLE, TRANSIENT_LOCAL | `recorder_node` (LATCHED) | once | `exploration_manager.py:275-278`; `recorder_node.py:170` |
| `/exploration/goal_marker`, `/exploration/trajectory`, `/exploration/status_text` | `MarkerArray`, `Marker`, `Marker` | `frontier_visualizer` | RViz only | timer 0.25 s (4 Hz) | `frontier_visualizer.py:52-60` |

### 3.4 Evaluation

| Topic | Type | Publisher | Subscriber(s) | Rate | Cite |
|---|---|---|---|---|---|
| `/eval/goal_events` | `std_msgs/String` | `goal_sender` (RELIABLE depth 50) | `recorder_node` | per goal | `goal_sender.py:67`; `recorder_node.py:155` |
| `/eval/done` | `std_msgs/Bool` | `goal_sender`, `responsiveness_test` (QoS built at `goal_sender.py:68`, `responsiveness_test.py:55`; durability not read) | `recorder_node` (RELIABLE) | once | `recorder_node.py:171` area (`cs(Bool, '/eval/done' ...)`) |
| `/eval/stop` | `std_msgs/Empty` | harness via `ros2 topic pub --once` | `recorder_node` | once | `run_episode.py:614`; `recorder_node.py:169-170` |
| `/initialpose` | `PoseWithCovarianceStamped` | harness `ros2 topic pub -t 5 -r 2` (AMCL mode only) | AMCL (package default, not in repo) | 2 Hz x 5 | `run_episode.py:362-369` |
| `/tf` | `tf2_msgs/TFMessage` | see section 4 | `recorder_node` (RELIABLE, depth 100), all TF listeners | not found | `recorder_node.py:176-178` |

### 3.5 Diagnostics and localization (not in the frontier eval path)

| Topic | Type | Publisher | Subscriber(s) | Rate | Cite |
|---|---|---|---|---|---|
| `/camera/diagnostics` | `diagnostic_msgs/DiagnosticArray` | `camera_diagnostics_node` | none found | param `rate` (value not read) | `camera_diagnostics_node.py:142-145` |
| `/motion_diagnostics` | `DiagnosticArray` | `motion_diagnostics_node` | none found | `publish_rate: 2.0` | `motion_diagnostics_node.py:62-64`; `controllers.launch.py:223-227` |
| `/amcl_pose` | `PoseWithCovarianceStamped` | AMCL (package default) | `localization_monitor` (BEST_EFFORT depth 10); `localization_metrics` (BEST_EFFORT) | not found | `localization_monitor.py:84-90`; `localization_metrics.py:96-105` |
| `/particle_cloud` | `ParticleCloud` | AMCL (package default) | `localization_monitor` (if import available) | not found | `localization_monitor.py:93-95` |
| `/localization/status` | `std_msgs/String` | `localization_monitor` | `recovery_monitor`; `localization_metrics` | not found | `localization_monitor.py:98`; `recovery_monitor.py:68-69`; `localization_metrics.py:100` |
| `/localization/recovery_status` | `std_msgs/String` | `recovery_monitor` | `localization_metrics` | not found | `recovery_monitor.py:74-75`; `localization_metrics.py:102` |

### 3.6 Nav2 internal topics visible in repo config/code

`/plan` and `/local_plan` appear in the harness bag list (`run_episode.py:34`); `/plan` is subscribed by `recorder_node` as `nav_msgs/Path` (`recorder_node.py:163`). Publishers are Nav2 `planner_server` and `controller_server` (package default, not in repo). `local_costmap/costmap_raw`, `global_costmap/costmap_raw`, `local_costmap/published_footprint`, `global_costmap/published_footprint` are `behavior_server` topic params (`nav2_params.yaml:206-209`). Costmap update/publish rates: global 1.0/1.0 Hz (`:258-259`), local 5.0/2.0 Hz (`:319-320`).

---

## 4. TF tree

### 4.1 Frames and who publishes each transform

```
map
 └── odom                      [map -> odom]
      └── base_footprint       [odom -> base_footprint]
           └── base_link       [base_footprint_joint, fixed]
                ├── left_wheel_link   [left_wheel_joint, continuous]
                ├── right_wheel_link  [right_wheel_joint, continuous]
                ├── caster_wheel_link [caster_wheel_joint, fixed]
                └── camera_mount_link [placeholder bracket; joint not located in the files read]
                     └── camera_link  [camera_joint, fixed]
                          ├── camera_color_frame  [camera_color_joint, fixed]
                          │    └── camera_color_optical_frame [camera_color_optical_joint, fixed]
                          └── camera_depth_frame  [camera_depth_joint, fixed]
                               └── camera_depth_optical_frame [camera_depth_optical_joint, fixed]

world  (only used as header.frame_id of /ground_truth/odom; not part of the TF tree above)
```

| Transform | Publisher | Condition | Cite |
|---|---|---|---|
| `map -> odom` | `rtabmap` (`map_frame_id: map`, `odom_frame_id: odom`; the Nav2 launch docstring states RTAB-Map provides map to odom) | rtabmap modes (frontier method; scripted `slam`) | `rtabmap.yaml:26-28`; `nav2.launch.py:17-18` |
| `map -> odom` | `gt_localization_node` (composes map to odom from ground truth and odom to base_footprint, 30 Hz timer) | scripted `gt` mode only | `gt_localization_node.py:30-34, 49, 51, 68-76`; `run_episode.py:472-475` |
| `map -> odom` | AMCL (package default, not in repo) | scripted AMCL mode | `nav2_localization.launch.py:138` (node started); TF output not found in repo code |
| `odom -> base_footprint` | `diff_drive_controller` | clean odom mode (`enable_odom_tf: true`) | `controllers.yaml:75-76, 88` |
| `odom -> base_footprint` | `odom_noise_node` via `TransformBroadcaster` (`publish_tf` default True), DDC TF disabled via `ddc_no_tf.yaml` | `odom_mode:=eval` (what the harness uses) | `odom_noise_node.py:52, 64, 118-126`; `ddc_no_tf.yaml:5`; `controllers.launch.py:107-116`; `run_episode.py:377` |
| `base_footprint -> base_link`, wheel links, caster, camera chain | `robot_state_publisher` (`publish_frequency: 50.0`), driven by URDF and `/joint_states` | always | `sim.launch.py:196-206`; `_base.xacro:20-26`; `_macros.xacro:122-125, 172-175`; `_sensors.xacro:52-54, 88-91, 99-101, 119-122, 130-132` |

Header frame ids used elsewhere: `cmd_vel_relay` stamps `base_footprint` (`cmd_vel_relay.py:35`); `depthimage_to_laserscan` `output_frame: camera_link` (`nav2.launch.py:94`); costmap `global_frame` map / odom, `robot_base_frame` `base_footprint` (`nav2_params.yaml:260-261, 321-322`); rtabmap `frame_id: base_footprint` (`rtabmap.yaml:26`).

### 4.2 TF consumers in code

| Node | Use | Cite |
|---|---|---|
| `exploration_manager` | `lookup_transform('map','base_footprint')` | `exploration_manager.py:195-196, 342` |
| `gt_localization_node` | `lookup_transform('odom','base_footprint')` | `gt_localization_node.py:47-48, 62` |
| `recorder_node` | TF buffer with `spin_thread=True`, lookups at `:266` and `:275` (`map`,`base_footprint`) | `recorder_node.py:142-143, 266, 275` |
| `rtabmap` | `wait_for_transform 0.5`, `tf_delay 0.05`, `tf_tolerance 0.1` | `rtabmap.yaml:54-56` |
| Nav2 costmaps, MPPI, behaviors | `transform_tolerance` 0.1 / 0.2 | `nav2_params.yaml:96, 221, 285, 348` |
| Harness gate | `tf2_echo map base_footprint` | `run_episode.py:229` |

`/tf_static` is not published by any repo code; it comes from `robot_state_publisher` for fixed joints (package default, not in repo). It is in the bag list (`run_episode.py:31`).

---

## 5. Actions

| Action | Server | Client(s) | Cite |
|---|---|---|---|
| `navigate_to_pose` (`nav2_msgs/action/NavigateToPose`) | Nav2 `bt_navigator` (`NavigateToPoseNavigator`, `navigators: ["navigate_to_pose"]`) | `exploration_manager` (`ActionClient`, `wait_for_server(5.0)`, `send_goal_async`, `cancel_goal_async`); `goal_sender`; `recovery_monitor` (only if `_cancel_on_lost`) | `nav2_params.yaml:29-43`; `exploration_manager.py:219, 419, 688, 705, 730`; `goal_sender.py:70`; `recovery_monitor.py:78-80` |
| `navigate_to_pose/_action/status` and `/feedback` | bt_navigator | `recorder_node` | `recorder_node.py:157-162` |
| `compute_path_to_pose` | `planner_server` (plugin `GridBased` = `SmacPlannerHybrid`) | BT node `ComputePathToPose` | `explore.xml` (RecoveryNode "ComputePathRecovery" block); `nav2_params.yaml:163-168` |
| `follow_path` | `controller_server` (plugin `FollowPath` = MPPIController) | BT node `FollowPath` | `explore.xml` (RecoveryNode "FollowPathRecovery"); `nav2_params.yaml:62-79` |
| `spin`, `backup`, `wait` | `behavior_server` | BT nodes `Spin`, `BackUp`, `Wait` | `explore.xml` (recovery actions); `nav2_params.yaml:204-217`; status topics subscribed at `recorder_node.py:157-160` |
| ros2_control action/service names, `/diff_drive_controller` etc. | `controller_manager` | `spawner` CLI | `controllers.launch.py:81-117`; `run_episode.py:216` uses `ros2 control list_controllers` |

Action name-to-server mapping for the BT nodes uses package defaults; exact `server_name` attributes are in `explore.xml` but were not individually read beyond the node list.

## 6. Services

| Service | Server | Client | Cite |
|---|---|---|---|
| `global_costmap/clear_entirely_global_costmap` | `global_costmap` (package default) | BT `ClearEntireCostmap` | `explore.xml` (`service_name="global_costmap/clear_entirely_global_costmap"`) |
| `local_costmap/clear_entirely_local_costmap` | `local_costmap` (package default) | BT `ClearEntireCostmap` | `explore.xml` (`service_name="local_costmap/clear_entirely_local_costmap"`) |
| Lifecycle services (`configure`, `activate`) for nav2 nodes | each Nav2 node | `lifecycle_manager` (`autostart: True`, node list: planner_server, controller_server, behavior_server, smoother_server, velocity_smoother, bt_navigator) | `nav2.launch.py:171-188` |
| `/map_server` lifecycle (`ros2 lifecycle set`) | `nav2_map_server` | harness shell command (gt mode) | `run_episode.py:469-471` |
| controller_manager services | `controller_manager` | `spawner`, `ros2 control` | `controllers.launch.py:81-117`; `run_episode.py:216` |

No custom `create_service` or `create_client` calls were found in `vacuum_controller`, `vacuum_exploration`, `vacuum_localization`, or `vacuum_eval` Python nodes (grep on those patterns returned nothing). Custom message/service definitions in `vacuum_interfaces`: only `package.xml` exists there, so none are defined (not found).

---

## 7. QoS settings set in code

| Where | Topic | QoS | Cite |
|---|---|---|---|
| `ground_truth_node` sub | `/ground_truth/odom_raw` | RELIABLE, depth 10 | `ground_truth_node.py:33-34` |
| `ground_truth_node` pub | `/ground_truth/odom` | default, depth 10 | `:35` |
| `odom_noise_node` pub/sub | `/odom`, `/diff_drive_controller/odom` | RELIABLE, depth 10 | `odom_noise_node.py:62-66` |
| `odometry_noise_node` | `/odom` sub, `/odom_noisy` pub | custom `QoSProfile` (fields not read) | `odometry_noise_node.py:57-66` |
| `exploration_manager` map sub | `/rtabmap/map` | RELIABLE, VOLATILE, depth 1 | `exploration_manager.py:255-261` |
| `frontier_detector` map sub | map topic | RELIABLE, VOLATILE, depth 1 | `frontier_detector.py:82-92` |
| `exploration_metrics` map sub | `/rtabmap/map` | RELIABLE, TRANSIENT_LOCAL | `exploration_metrics.py:104-110` |
| `exploration_manager` pub | `/exploration/goal_events` | RELIABLE, depth 50 | `exploration_manager.py:271-273` |
| `exploration_manager` pub | `/exploration/finished` | RELIABLE, TRANSIENT_LOCAL, depth 1 | `exploration_manager.py:275-278` |
| `goal_sender` pub | `/eval/goal_events` | RELIABLE, depth 50 | `goal_sender.py:67` |
| `recorder_node` | RELIABLE depth 50 VOLATILE; BEST_EFFORT depth 50 (images, scan); LATCHED depth 1 RELIABLE TRANSIENT_LOCAL (`/rtabmap/map`, `/exploration/finished`); `/tf` RELIABLE depth 100 | `recorder_node.py:30-35, 146-178` |
| `localization_monitor` | `/amcl_pose`, `/particle_cloud` | BEST_EFFORT, depth 10 | `localization_monitor.py:84-95` |
| `localization_metrics` | `/amcl_pose` | BEST_EFFORT, depth 10 | `localization_metrics.py:96-105` |
| rtabmap image inputs | RGB, depth, camera_info | `qos_image: 2`, `qos_camera_info: 2` (comment: Best Effort / Volatile) | `rtabmap.yaml:39-40` |
| Nav2 StaticLayer | `/map` | `map_subscribe_transient_local: true` | `nav2_params.yaml:267` |
| Harness checks | `/rtabmap/map`, `/map` | `--qos-durability transient_local --qos-reliability reliable` | `run_episode.py:238-239, 532-533` |
| ros_gz_bridge | all entries | not set (not found) | `gz_bridge.yaml`, `gz_bridge_dynamic.yaml` |

All other publishers/subscribers in the survey use depth 10 with default reliability (`create_publisher(..., 10)` / `create_subscription(..., 10)`).

---

## 8. Parameter files per node

| Node | Parameter file(s) / inline params | Key content | Cite |
|---|---|---|---|
| `robot_state_publisher` | inline in `sim.launch.py` | `robot_description` (xacro), `use_sim_time`, `publish_frequency 50.0` | `sim.launch.py:201-205` |
| `ros_gz_bridge`, `ros_gz_bridge_extra` | `vacuum_gazebo/config/gz_bridge.yaml`, extra: `gz_bridge_dynamic.yaml` via `config_file` | bridge entries | `sim.launch.py:294-311` |
| `gz_ros2_control` plugin | `vacuum_controller/config/controllers.yaml` (referenced in URDF `<parameters>`) | see next rows | `_gazebo.xacro:113` |
| `controller_manager` | `controllers.yaml` | `update_rate: 50`; controllers JSB and DDC | `controllers.yaml:22-33` |
| `joint_state_broadcaster` | `controllers.yaml` | joints `left_wheel_joint`, `right_wheel_joint` | `controllers.yaml:39-44` |
| `diff_drive_controller` | `controllers.yaml`; in eval mode also `vacuum_eval/config/ddc_no_tf.yaml` | wheel_separation 0.268, wheel_radius 0.033, publish_rate 30, odom_frame `odom`, base_frame `base_footprint`, `enable_odom_tf` true (false in `ddc_no_tf.yaml`), `cmd_vel_timeout 0.5`, linear +-0.5 m/s, 1.0 m/s^2, angular +-2.0 rad/s, 2.0 rad/s^2 | `controllers.yaml:55-130`; `ddc_no_tf.yaml:3-5` |
| `cmd_vel_relay` / `cmd_vel_relay_nav` | inline: `use_sim_time`; second adds `input_topic: /cmd_vel_smoothed` | | `controllers.launch.py:132, 149-150`; `cmd_vel_relay.py:25` |
| `odom_relay` (`topic_tools relay`) | args `/diff_drive_controller/odom /odom`; `use_sim_time` | | `controllers.launch.py:162-170` |
| `odom_noise_node` | inline: `use_sim_time`, `enable_noise`, `seed`; defaults in code `sigma_scale_lin 0.02`, `sigma_scale_ang 0.03`, `sigma_rw_per_sqrt_m 0.02`, `sigma_rw_per_sqrt_rad 0.03`, `publish_tf True` | | `controllers.launch.py:182-186`; `odom_noise_node.py:46-52` |
| `odometry_noise_node` | inline: `enable_noise`, `linear_noise_std 0.005`, `angular_noise_std 0.003`, `rate_hz 30.0` | | `controllers.launch.py:202-208` |
| `motion_diagnostics_node` | inline: `cmd_vel_timeout_warn 0.5`, `publish_rate 2.0` | | `controllers.launch.py:223-227` |
| `camera_diagnostics_node` | `vacuum_gazebo/config/camera.yaml` | topics and frames sections | `controllers.launch.py:36-38, 242-245`; `camera.yaml:79-95` |
| `ground_truth_node` | inline: `use_sim_time` | | `sim.launch.py:367-373` |
| `rtabmap` | `vacuum_slam/config/rtabmap.yaml` + inline (`use_sim_time`, `database_path`, `Mem/IncrementalMemory`, ...) | `frame_id base_footprint`, `subscribe_depth/rgb true`, `approx_sync true`, `approx_sync_max_interval 0.05`, `Rtabmap/DetectionRate 1`, `Grid/CellSize 0.05`, `Reg/Force3DoF true`, others | `slam.launch.py:147-156`; `rtabmap.yaml:21-140` |
| `depthimage_to_laserscan_node` | inline | `scan_height 5`, `scan_time 0.033`, `range_min 0.20`, `range_max 4.00`, `output_frame camera_link` | `nav2.launch.py:88-95` |
| `bt_navigator`, `planner_server`, `controller_server`, `behavior_server`, `smoother_server`, `velocity_smoother`, `global_costmap`, `local_costmap`, `map_server`, `amcl` (stub), `map_saver`, `lifecycle_manager` | `vacuum_nav2/config/nav2_params.yaml`; `bt_navigator` also gets `default_nav_to_pose_bt_xml` = `behavior_trees/explore.xml` inline | SmacPlannerHybrid, MPPIController (20 Hz), STVL obstacle layers on `/scan_from_depth` | `nav2.launch.py:104-133`; `nav2_params.yaml` sections at `:29, 54, 163, 204, 228, 238, 255, 316, 380, 389, 395, 406` |
| `lifecycle_manager` (nav2.launch.py) | inline: `autostart True`, `node_names` list | | `nav2.launch.py:171-188` |
| `amcl` (scripted AMCL mode) | `vacuum_nav2/config/amcl_params.yaml`, `amcl_params_v2.yaml`; `map_server_params.yaml` | not read in detail | files present in `vacuum_nav2/config/` |
| `frontier_detector` | `vacuum_exploration/config/exploration_params.yaml` | `map_topic /rtabmap/map`, `publish_rate 2.0`, `cluster_radius 0.50`, `min_frontier_size 5` | `exploration_params.yaml:13-28`; `exploration.launch.py:164-170` |
| `exploration_manager` | `exploration_params.yaml` + inline `environment` | `goal_timeout 30.0`, `retry_count 3`, `blacklist_expiry_sec 60.0`, oscillation and no-frontier thresholds, goal-selector weights (1.0, 1.5, 0.8), `min_goal_distance 0.30` | `exploration_params.yaml:30-94`; `exploration.launch.py:175-186` |
| `exploration_metrics` | `exploration_params.yaml` (`metrics` section) + inline | `log_rate 1.0` | `exploration_params.yaml:96-110`; `exploration.launch.py:202-213` |
| `frontier_visualizer` | inline `use_sim_time` only | | `exploration.launch.py:190-197` |
| `recorder_node` | inline: `use_sim_time`, `run_dir`, optional `extra_models`; code default `sample_hz 10.0` | | `eval_stack.launch.py:11-15`; `recorder_node.py:83` |
| `goal_sender`, `dynamic_mover`, `responsiveness_test`, `gt_localization_node` | CLI `--ros-args -p` from the harness (`goals_file`, `t_world_map`; `model`, `waypoints`, `speed`, `start_delay_s`; `output_file`; `use_sim_time`); `gt_localization_node` declares `map_origin_x/y/yaw` default 0.0 | | `run_episode.py:466-528`; `gt_localization_node.py:44-45` |
| `localization_monitor`, `recovery_monitor`, `localization_metrics` | `vacuum_localization/config/localization_params.yaml` (file exists; load not verified in the launch file here) | | `vacuum_localization/config/localization_params.yaml` (33 lines) |

---

## 9. ASCII data-flow diagram (frontier exploration run)

```
                         GAZEBO HARMONIC (world SDF + embedded robot)
  +---------------------------------------------------------------------------+
  | rgbd_camera "d435i" 30 Hz  -> gz: camera/image_raw/{image,depth_image,    |
  |                                     camera_info}                          |
  | OdometryPublisher 30 Hz    -> gz: /model/vacuum_robot/ground_truth_odom   |
  | contact sensors 50 Hz      -> gz: /vacuum_robot/contacts/*                |
  | /clock                                                                    |
  | gz_ros2_control (GazeboSimSystem) <-> wheel joints (velocity cmd, pos/vel)|
  +---------+---------------------------------------------------^-------------+
            | GZ_TO_ROS                                         | joint velocity
            v                                                   | command / state
  +---------------------+                                       |
  |  ros_gz_bridge      |  (gz_bridge.yaml)                     |
  +--+--+--+--+--+------+                                       |
     |  |  |  |  |                                              |
     |  |  |  |  +--> /ground_truth/odom_raw --> ground_truth_node --> /ground_truth/odom
     |  |  |  |                                   (recorder, gt_localization, movers)
     |  |  |  +-----> /vacuum_robot/contacts/* --> recorder_node
     |  |  +--------> /clock --> every node (use_sim_time)
     |  |
     |  +-----------> /camera/depth/image_rect_raw ----+-------------------------+
     |                /camera/depth/camera_info -------+--> depthimage_to_laserscan
     |                                                  |        |
     +--------------> /camera/color/image_raw ----+     |        v
                      /camera/color/camera_info --+     |   /scan_from_depth
                                                  v     v        |
                                       +--------------------+    |
        /odom ------------------------>|      rtabmap       |    |
   (30 Hz, from odom path below)       | rgb+depth+odom     |    |
                                       | publishes map->odom|    |
                                       +----+---------------+    |
                                            | /rtabmap/map (1 Hz)|
              +-----------------------------+------+             |
              v                                    v             v
     topic_tools relay                     frontier_detector   Nav2 costmaps
     /rtabmap/map -> /map                  (2 Hz)              (STVL obstacle layer
              |                                 |               on /scan_from_depth;
              v                                 | /frontiers/   StaticLayer on /map)
     Nav2 StaticLayer (/map)                    |  centroids
                                                v
                                        exploration_manager (10 Hz FSM)
                                        TF map->base_footprint, /odom,
                                        /rtabmap/map
                                                |
                          NavigateToPose action | (send_goal_async / cancel)
                                                v
                  +-----------------------------------------------+
                  | Nav2: bt_navigator (explore.xml)              |
                  |   -> compute_path_to_pose: planner_server     |
                  |        (SmacPlannerHybrid)                    |
                  |   -> follow_path: controller_server (MPPI,    |
                  |        20 Hz)                                 |
                  |   -> spin/backup/wait: behavior_server        |
                  +-------------------+---------------------------+
                                      | /cmd_vel_nav (Twist)   (behavior_server too;
                                      v                         exploration_manager
                              velocity_smoother (20 Hz)         publishes a bootstrap
                                      | /cmd_vel_smoothed       spin here as well)
                                      v
                              cmd_vel_relay_nav
                              (Twist -> TwistStamped, frame base_footprint)
                                      | /diff_drive_controller/cmd_vel
                                      v
                              diff_drive_controller (ros2_control, 50 Hz CM)
                                      |  velocity commands to wheel joints  ------> (up to gz_ros2_control)
                                      |
                                      | /diff_drive_controller/odom (30 Hz)
                                      v
              eval mode (harness):  odom_noise_node -> /odom  + TF odom->base_footprint
              clean mode:           topic_tools relay -> /odom ; DDC publishes the TF itself
                                      |
                                      +--> rtabmap, Nav2 (odom_topic), exploration_manager,
                                           recorder_node

  Teleop path (manual, not used by the explorer): teleop_arrows / steering GUI
      -> /cmd_vel -> cmd_vel_relay -> /diff_drive_controller/cmd_vel

  Evaluation side channel (read-only observers):
      recorder_node subscribes /tf, /odom, /ground_truth/odom, /cmd_vel*, /plan,
      /navigate_to_pose/_action/*, /rtabmap/{map,info}, /exploration/*, /eval/*,
      contacts, camera and scan rate counters; writes CSV into run_dir.
      goal_sender (scripted_goals method) is a second NavigateToPose client.
```

---

## 10. Items not found or unresolved

- Bridge QoS overrides: not found in `gz_bridge.yaml` / `gz_bridge_dynamic.yaml`.
- `gt_bridge` / `/ground_truth/poses`: referenced in a comment (`gz_bridge.yaml:77-80`), no node found in `sim.launch.py`.
- Subscribers of `/odom_noisy`, `/camera/diagnostics`, `/motion_diagnostics`, `/diff_drive_controller/cmd_vel_unstamped`, `/frontiers/markers`, `/exploration/selected_marker`: none found in code (RViz configs were not inspected).
- Publish cadence of `/exploration/status` and `/exploration/current_goal`: not found in this survey.
- Joint that attaches `camera_mount_link` to `base_link`: not located in the files read (`_sensors.xacro:7-14` documents the chain).
- AMCL's TF/topic behaviour and the internals of `nav2_localization.launch.py`, `amcl_params*.yaml`: only names read.
- `localization_params.yaml` consumption by localization nodes: not verified.
- Which stamped/unstamped command interface the DDC actually subscribes to at runtime: conflicting comments/params in repo (see section 3.2 note).
- `controllers.launch.py` docstring (lines 7-11) contradicts the code that spawns JSB and DDC.

---

One-line summary: This file is the code-cited reference of every topic, TF transform, action, service, QoS setting and parameter file in the vacuum_ws sim, with an ASCII flow from Gazebo sensors through the bridge, RTAB-Map, Nav2, the explorer and the relay chain back to the diff-drive controller, and a list of items not found.
