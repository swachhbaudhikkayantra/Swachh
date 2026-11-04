# 07. Nav2 navigation stack and the controller package

Scope: `Navigation/Simulation/vacuum_ws/src/vacuum_nav2` (parameters, behaviour trees, launch files) and `src/vacuum_controller` (ros2_control config, launch, Python nodes). Every value below was read from those files. Where a file contradicts itself or a comment, that is noted.

Jargon, briefly:
- **Nav2**: the ROS 2 navigation framework. It is a set of cooperating servers (planner, controller, behaviours, smoothers) coordinated by a behaviour tree.
- **Costmap**: a 2D grid where each cell holds a cost from "free" to "lethal obstacle". Planners and controllers use it to avoid collisions.
- **Behaviour tree (BT)**: a tree of small actions and conditions that decides what to do next (plan, follow, recover). Written in XML.
- **Lifecycle node**: a ROS 2 node with explicit states (unconfigured, inactive, active). The lifecycle manager brings them up in order.
- **diff drive**: differential drive, two powered wheels; the robot can go forward/back and turn but cannot slide sideways (non-holonomic).

---

## 1. High-level picture: how a goal becomes wheel motion

```
NavigateToPose goal (map frame)
        |
   bt_navigator  -- runs a behaviour tree (explore.xml / navigate.xml / navigate_v2.xml)
        |  at 1 Hz              |  continuous                 |  on failure
        v                       v                             v
 planner_server          controller_server             behavior_server
 SmacPlannerHybrid       MPPIController (20 Hz)        spin / backup / wait
 (Hybrid A*, DUBIN)             |                       (+ costmap clearing services)
        |                       |
  global_costmap          local_costmap
  (map frame, 1 Hz)       (odom frame, 4x4 m rolling, 5 Hz)
                                |
                  /cmd_vel_nav (Twist)   <- controller_server and behavior_server are both remapped to this
                                |
                       velocity_smoother (20 Hz, accel limits)
                                |
                  /cmd_vel_smoothed (Twist)
                                |
              cmd_vel_relay_nav (vacuum_controller): Twist -> TwistStamped
                                |
              /diff_drive_controller/cmd_vel (TwistStamped)
                                |
           diff_drive_controller (ros2_control, in Gazebo): own velocity and acceleration limits
                                |
                    left/right wheel joint velocities -> Gazebo physics
                                |
                  odom -> /diff_drive_controller/odom -> relay -> /odom -> back to Nav2
```

Steps in words:
1. A client sends a `NavigateToPose` action goal to `bt_navigator`.
2. The BT calls `ComputePathToPose` (planner server, plugin id `GridBased`, Smac Hybrid A*) at most once per second against the global costmap. The result goes into the blackboard variable `{path}`.
3. The BT calls `FollowPath` (controller server, plugin id `FollowPath`, MPPI). MPPI samples many short candidate trajectories each cycle (20 Hz), scores them with "critics" against the local costmap and the path, and outputs one velocity command.
4. That command goes to `/cmd_vel_nav`, is rate-limited by the velocity smoother, stamped by a relay, and then passed through the diff_drive_controller, which applies its own limits and converts to wheel speeds.
5. If planning or following fails, the BT runs recoveries: clear costmaps, back up, spin, wait, then retry.

Two launch files start Nav2:
- `nav2.launch.py` (exploration, "Stage 4B"): map comes from RTAB-Map (`/rtabmap/map` relayed to `/map`), RTAB-Map provides the map to odom transform, uses `explore.xml`.
- `nav2_localization.launch.py` (known map, "Stage 5"): map server plus AMCL (particle-filter localisation), uses `navigate.xml`, or `navigate_v2.xml` when the environment variable `VACUUM_NAV_VARIANT=v2`.

---

## 2. Launch files

### 2.1 `nav2.launch.py` (exploration)

| Node | Package / executable | Notes |
|---|---|---|
| `rtabmap_map_relay` | `topic_tools relay` | `/rtabmap/map` to `/map`, because the static layer reads `/map` |
| `depthimage_to_laserscan_node` | `depthimage_to_laserscan` | `scan_height` 5 rows, `scan_time` 0.033 s, `range_min` 0.20 m, `range_max` 4.00 m, `output_frame` `camera_link`. Remaps `depth` to `/camera/depth/image_rect_raw`, `depth_camera_info` to `/camera/depth/camera_info`, `scan` to `/scan_from_depth` |
| `bt_navigator` | `nav2_bt_navigator` | Overrides `default_nav_to_pose_bt_xml` with `behavior_trees/explore.xml` |
| `planner_server` | `nav2_planner` | |
| `controller_server` | `nav2_controller` | `cmd_vel` remapped to `/cmd_vel_nav` |
| `behavior_server` | `nav2_behaviors` | `cmd_vel` remapped to `/cmd_vel_nav` |
| `smoother_server` | `nav2_smoother` | |
| `velocity_smoother` | `nav2_velocity_smoother` | input `cmd_vel` remapped to `/cmd_vel_nav`, output `cmd_vel_smoothed` to `/cmd_vel_smoothed` |
| `lifecycle_manager` | `nav2_lifecycle_manager` | `autostart: True`; manages planner_server, controller_server, behavior_server, smoother_server, velocity_smoother, bt_navigator |

### 2.2 `nav2_localization.launch.py` (known map)

Staged start with `TimerAction` delays:

| Time | What starts |
|---|---|
| T+0 s | `depth_to_scan` (same parameters as above) |
| T+2 s | `map_server` (loads `map_path`, frame `map`, topic `/map`) |
| T+5 s | `amcl` (parameters from `amcl_params.yaml`, or `amcl_params_v2.yaml` for v2) |
| T+8 s | bt_navigator, planner_server, controller_server, behavior_server, smoother_server, velocity_smoother (same remaps as above) |
| T+12 s | `lifecycle_manager` (map_server, amcl, bt_navigator, planner_server, controller_server, behavior_server, smoother_server, velocity_smoother) |
| T+14 s | RViz2 (only if `use_rviz` true) |

Arguments: `map_path` (default `~/maps/stage5/apartment.yaml`), `environment` (default `apartment`, label only), `use_sim_time` (default true), `use_rviz` (default true). Variant switch: `VACUUM_NAV_VARIANT` must be `v1` (default) or `v2`, otherwise a `RuntimeError` is raised. v2 selects `amcl_params_v2.yaml` and `navigate_v2.xml`. The AMCL files are not covered here.

---

## 3. `nav2_params.yaml`, parameter by parameter

The header comment describes the robot as a circle of radius 0.18 m, max linear 0.30 m/s, max angular 1.0 rad/s. The costmaps, however, use a rectangular footprint (see 3.7). The circle statement is only a comment and is stale relative to the footprint parameters.

### 3.1 `bt_navigator`

| Parameter | Value | Meaning |
|---|---|---|
| `global_frame` | `map` | Frame for goals and plans |
| `robot_base_frame` | `base_footprint` | Robot frame |
| `odom_topic` | `/odom` | Odometry used by the navigator |
| `bt_loop_duration` | 10 | BT tick period in ms |
| `default_server_timeout` | 20 | ms to wait for an action server reply per tick |
| `wait_for_service_timeout` | 1000 | ms to wait for services at startup |
| `action_server_result_timeout` | 900.0 | s before an action result is considered timed out |
| `navigators` | `["navigate_to_pose"]` | Only this navigator loaded; `navigate_through_poses` is omitted to avoid a duplicate plugin registration crash on Jazzy (per the file comment) |
| `navigate_to_pose.plugin` | `nav2_bt_navigator::NavigateToPoseNavigator` | |
| `default_nav_to_pose_bt_xml` | `""` | Overridden at launch with the chosen BT file |
| `plugin_lib_names` | intentionally absent | Jazzy auto-registers BT plugins; listing them causes "already registered" crash |

### 3.2 `controller_server` (local control)

| Parameter | Value | Meaning |
|---|---|---|
| `controller_frequency` | 20.0 Hz | Rate of the control loop |
| `min_x_velocity_threshold` | 0.001 | Odometry speeds below this are treated as zero |
| `min_y_velocity_threshold` | 0.5 | Same for y (irrelevant for diff drive) |
| `min_theta_velocity_threshold` | 0.001 | Same for rotation |
| `failure_tolerance` | 0.3 | s the controller may keep failing to produce a valid command before the action fails |
| `odom_topic` | `/odom` | |
| `progress_checker_plugins` | `progress_checker` | |
| `goal_checker_plugins` | `general_goal_checker` | |
| `controller_plugins` | `FollowPath` | Plugin id the BT refers to via `controller_id` |

Progress checker (`nav2_controller::SimpleProgressChecker`): robot must move at least `required_movement_radius` = 0.5 m within `movement_time_allowance` = 10.0 s, otherwise FollowPath fails (triggering BT recovery).

Goal checker (`nav2_controller::SimpleGoalChecker`): `stateful: true` (once the position tolerance is met it stays met while rotating), `xy_goal_tolerance` = 0.30 m, `yaw_goal_tolerance` = 0.50 rad (about 28.6 degrees). Comment: generous for exploration.

### 3.3 MPPI controller (`FollowPath`)

**MPPI** (Model Predictive Path Integral) is a sampling-based controller. Each cycle it rolls out `batch_size` random control sequences over a time horizon, scores each trajectory with critics, and takes a weighted average of the best ones.

Core parameters:

| Parameter | Value | Meaning |
|---|---|---|
| `plugin` | `nav2_mppi_controller::MPPIController` | |
| `time_steps` | 56 | Steps per trajectory |
| `model_dt` | 0.05 s | Time per step; horizon = 56 x 0.05 = 2.8 s |
| `batch_size` | 2000 | Number of sampled trajectories per cycle |
| `iteration_count` | 1 | Optimisation iterations per cycle |
| `ax_max` / `ax_min` | 3.0 / -3.0 m/s^2 | Forward/backward acceleration bounds used inside the sampler |
| `ay_max` | 3.0 | Lateral accel (unused for diff drive) |
| `az_max` | 3.5 rad/s^2 | Angular acceleration bound |
| `vx_std` | 0.2 | Std dev of sampled linear velocity noise |
| `vy_std` | 0.0 | No lateral sampling (non-holonomic) |
| `wz_std` | 0.4 | Std dev of sampled angular velocity noise |
| `vx_max` | 0.30 m/s | Forward speed cap |
| `vx_min` | 0.0 | Forward only; the file comment says this prevents continuous reverse driving |
| `vy_max` | 0.0 | |
| `wz_max` | 1.0 rad/s | Rotation cap |
| `prune_distance` | 1.7 m | Only this much of the global path ahead of the robot is considered |
| `transform_tolerance` | 0.1 s | TF lookup tolerance |
| `temperature` | 0.3 | Selectivity of the weighted average (lower = more greedy toward best trajectories) |
| `gamma` | 0.015 | Discount-like term in the update that couples control smoothness to cost |
| `motion_model` | `DiffDrive` | Trajectories follow differential-drive kinematics |
| `visualize` | false | Do not publish trajectory markers |

Critics (each scores trajectories; enabled in this order): ConstraintCritic, CostCritic, GoalCritic, GoalAngleCritic, PathAlignCritic, PathFollowCritic, PathAngleCritic, PreferForwardCritic. All have `enabled: true` and `cost_power: 1`.

| Critic | `cost_weight` | Other parameters | What it does |
|---|---|---|---|
| ConstraintCritic | 4.0 | | Penalises trajectories that violate velocity constraints |
| GoalCritic | 5.0 | `threshold_to_consider` 1.4 m | Pulls trajectory ends toward the goal once within 1.4 m |
| GoalAngleCritic | 3.0 | `threshold_to_consider` 0.5 m | Aligns final heading with goal heading when within 0.5 m |
| PreferForwardCritic | 15.0 | `threshold_to_consider` 0.5 m | Penalises driving backward when within 0.5 m of goal region |
| PathAlignCritic | 14.0 | `max_path_occupancy_ratio` 0.05, `trajectory_point_step` 3, `threshold_to_consider` 0.5, `offset_from_furthest` 20, `use_path_orientations` false | Keeps the trajectory aligned with the path; samples every 3rd trajectory point |
| PathFollowCritic | 5.0 | `offset_from_furthest` 5, `threshold_to_consider` 1.4 | Pulls toward a point ahead on the path |
| PathAngleCritic | 2.0 | `offset_from_furthest` 4, `threshold_to_consider` 0.5, `max_angle_to_furthest` 1.0 rad, `forward_preference` true, `mode` 0 | Penalises heading away from the path direction (mode 0 = forward preference) |
| CostCritic | 3.81 | `critical_cost` 300.0, `consider_footprint` true, `collision_cost` 1000000.0, `near_goal_smoothing_factor` 0.1 | Penalises trajectories through high-cost costmap cells. `consider_footprint: true` checks the whole rectangular footprint; the inline comment says the previous centre-cell check clipped corners |

Highest weights: PreferForward (15), PathAlign (14), GoalCritic and PathFollow (5), so staying on the path and driving forward dominate.

### 3.4 `planner_server` (global planning, Smac Hybrid A*)

**Hybrid A\*** is A* search over (x, y, heading) with motion primitives that respect a minimum turning radius, so plans are drivable by a car-like or diff-drive robot. **DUBIN** primitives are forward-only arcs and straight lines (no reversing); the alternative `REEDS_SHEPP` would allow reversing.

| Parameter | Value | Meaning |
|---|---|---|
| `expected_planner_frequency` | 20.0 | Used by Nav2 only to warn if planning is slower than this |
| `planner_plugins` | `["GridBased"]` | Id referenced by the BT |
| `plugin` | `nav2_smac_planner::SmacPlannerHybrid` | |
| `downsample_costmap` | false | Search at full costmap resolution |
| `downsampling_factor` | 1 | |
| `tolerance` | 0.30 m | How far from the requested goal the plan may end |
| `allow_unknown` | true | Plans may pass through unknown cells; comment: critical for frontier exploration |
| `max_iterations` | 1000000 | Search expansion cap |
| `max_on_approach_iterations` | 1000 | Extra iterations allowed once within tolerance |
| `max_planning_time` | 5.0 s | Abort planning beyond this |
| `motion_model_for_search` | `DUBIN` | Forward-only curved primitives |
| `angle_quantization_bins` | 72 | Heading resolution (360/72 = 5 degrees per bin) |
| `analytic_expansion_ratio` | 3.5 | How often to try a direct Dubins connection to the goal |
| `analytic_expansion_max_length` | 3.0 m | Longest direct connection attempted |
| `analytic_expansion_max_cost` | 3.5 | Max cost allowed along analytic expansion |
| `analytic_expansion_max_cost_override` | false | Do not allow overriding that cost limit |
| `minimum_turning_radius` | 0.25 m | Tightest arc in the search; comment: tight turns for a small robot |
| `reverse_penalty` | 2.1 | Cost multiplier for reversing (inert with DUBIN, which does not reverse) |
| `change_penalty` | 0.0 | Penalty for changing turn direction |
| `non_straight_penalty` | 1.20 | Penalty for non-straight moves |
| `cost_penalty` | 2.0 | Weight on costmap cost |
| `retrospective_penalty` | 0.025 | Small penalty favouring later-in-path decisions |
| `lookup_table_size` | 20.0 m | Size of the precomputed heuristic table |
| `cache_obstacle_heuristic` | false | |
| `debug_visualizations` | false | |
| `use_quadratic_cost_penalty` | false | |
| `downsample_obstacle_heuristic` | true | Coarser obstacle heuristic for speed |
| `allow_primitive_interpolation` | false | |
| `smooth_path` | true | Run the planner's built-in smoother |
| `smoother.max_iterations` | 1000 | |
| `smoother.w_smooth` | 0.3 | Weight toward smoothness |
| `smoother.w_data` | 0.2 | Weight toward staying near original points |
| `smoother.tolerance` | 1e-10 | Convergence tolerance |
| `smoother.do_refinement` | true | |
| `smoother.refinement_num` | 2 | Refinement passes |

### 3.5 `behavior_server` (recovery behaviours)

| Parameter | Value | Meaning |
|---|---|---|
| `local_costmap_topic` | `local_costmap/costmap_raw` | |
| `global_costmap_topic` | `global_costmap/costmap_raw` | |
| `local_footprint_topic` | `local_costmap/published_footprint` | |
| `global_footprint_topic` | `global_costmap/published_footprint` | |
| `cycle_frequency` | 10.0 Hz | Behaviour loop rate |
| `behavior_plugins` | `spin`, `backup`, `wait` | Mapped to `nav2_behaviors::Spin`, `BackUp`, `Wait` |
| `local_frame` | `odom` | |
| `global_frame` | `map` | |
| `robot_base_frame` | `base_footprint` | |
| `transform_tolerance` | 0.1 s | |
| `simulate_ahead_time` | 2.0 s | Spin/backup check collisions this far ahead before moving |
| `max_rotational_vel` | 1.0 rad/s | Spin top speed |
| `min_rotational_vel` | 0.4 rad/s | Spin minimum speed |
| `rotational_acc_lim` | 3.2 rad/s^2 | Spin ramp: speed rises and falls at this rate |

Behaviours publish on `cmd_vel`, remapped to `/cmd_vel_nav`, so they also pass through the velocity smoother.

### 3.6 `smoother_server` and `velocity_smoother`

`smoother_server`: plugin `simple_smoother` (`nav2_smoother::SimpleSmoother`), `tolerance` 1e-10, `max_its` 1000, `do_refinement` true. The BTs in this package never call a smoother action, so it is loaded and activated but not used by the trees.

`velocity_smoother` (limits the rate of change of the command, an acceleration ramp):

| Parameter | Value | Meaning |
|---|---|---|
| `smoothing_frequency` | 20.0 Hz | Output rate |
| `scale_velocities` | false | Axes are clipped independently, not scaled together |
| `feedback` | `OPEN_LOOP` | Assumes the last command was achieved, does not read odometry for the ramp |
| `max_velocity` | [0.30, 0.0, 1.0] | [vx, vy, wz] |
| `min_velocity` | [-0.10, 0.0, -1.0] | Reverse is limited to 0.10 m/s |
| `max_accel` | [2.5, 0.0, 3.2] | Speed-up limits, m/s^2 and rad/s^2 |
| `max_decel` | [-2.5, 0.0, -3.2] | Slow-down limits |
| `odom_topic` | `/odom` | Only used in CLOSED_LOOP |
| `odom_duration` | 0.1 s | |
| `deadband_velocity` | [0.0, 0.0, 0.0] | No deadband |
| `velocity_timeout` | 1.0 s | If no new command arrives for this long, it ramps toward zero |

### 3.7 Costmaps

Both costmaps have a rectangular footprint `[[0.15, 0.125], [0.15, -0.125], [-0.15, -0.125], [-0.15, 0.125]]` (comment: chassis 0.30 x 0.25 m; half-length 0.15 m, half-width 0.125 m) and `resolution` 0.05 m per cell. Layers are applied in order: static, obstacle, inflation.

| Parameter | Global costmap | Local costmap |
|---|---|---|
| `update_frequency` | 1.0 Hz | 5.0 Hz |
| `publish_frequency` | 1.0 Hz | 2.0 Hz |
| `global_frame` | `map` | `odom` |
| `robot_base_frame` | `base_footprint` | `base_footprint` |
| `use_sim_time` | true | true |
| `rolling_window` | not set | true |
| `width` x `height` | not set (follows the map) | 4 m x 4 m |
| `track_unknown_space` | true (needed for frontier exploration) | false |
| `always_send_full_costmap` | true | true |

**Static layer** (`nav2_costmap_2d::StaticLayer`): copies the occupancy grid from `/map` into the costmap. `map_subscribe_transient_local: true` so it receives the latest map even if published before it started. In the local costmap a comment says it provides persistent memory of mapped obstacles outside the forward-only camera field of view and survives `ClearEntireCostmap` and STVL voxel decay.

**Obstacle layer** (`spatio_temporal_voxel_layer/SpatioTemporalVoxelLayer`, STVL): a 3D voxel layer where each marked voxel decays over time and the camera frustum (view cone) clears voxels it can see through.

| Parameter | Global | Local | Meaning |
|---|---|---|---|
| `voxel_decay` | 60.0 s | 15.0 s | Lifetime of a marked voxel |
| `decay_model` | 0 | 0 | Linear decay |
| `voxel_size` | 0.05 | 0.05 | m |
| `track_unknown_space` | false | false | |
| `mark_threshold` | 0 | 0 | |
| `update_footprint_enabled` | true | true | Clears under the robot footprint |
| `combination_method` | 1 | 1 | 1 = max (combine with layers below) |
| `publish_voxel_map` | false | false | |
| `transform_tolerance` | 0.2 | 0.2 | s |
| `observation_sources` | `depth_mark depth_clear` | same | Two sources on the same topic |

Source `depth_mark`: `data_type: LaserScan`, `topic: /scan_from_depth`, `marking: true`, `clearing: false`, `obstacle_range` 4.0 m, `min_obstacle_height` 0.03 m, `max_obstacle_height` 0.30 m (a height band of z 0.03 to 0.30 m), `inf_is_valid: false`, `filter: passthrough`.

Source `depth_clear`: `LaserScan`, same topic, `marking: false`, `clearing: true`, `min_z` 0.105, `max_z` 4.0, `vertical_fov_angle` 1.0 rad, `horizontal_fov_angle` 1.5010 rad (depth horizontal FOV from camera.yaml), `decay_acceleration` 0.0 (must be 0 for scans), `model_type` 0 (depth camera frustum).

**Inflation layer** (`nav2_costmap_2d::InflationLayer`): spreads cost outward from obstacles so the robot keeps clear. Both costmaps: `inflation_radius` 0.28 m, `cost_scaling_factor` 5.0 (cost decays exponentially with distance; higher means faster decay). The robot's half-width is 0.125 m and half-length 0.15 m, so 0.28 m extends well past the footprint edge.

### 3.8 Remaining sections

| Section | Content |
|---|---|
| `map_server` | `yaml_filename: ""` (set at launch), `frame_id: map`, `topic_name: /map` |
| `amcl` | Stub with `use_sim_time: true`; real values come from `amcl_params*.yaml` |
| `map_saver` | `save_map_timeout` 5.0, `free_thresh_default` 0.25, `occupied_thresh_default` 0.65, `map_subscribe_transient_local` true |
| `lifecycle_manager` | `autostart: true`; node list in the YAML is bt_navigator, planner_server, controller_server, behavior_server, smoother_server, velocity_smoother. Both launch files pass their own list, which overrides this |

Note: the YAML `lifecycle_manager.node_names` order differs from the launch files, but the launch files define their own `node_names` parameter directly.

---

## 4. Behaviour trees, node by node

All three use BT.CPP format 4 and top-level `RecoveryNode number_of_retries="6" name="NavigateRecovery"`.

Node types (standard Nav2):
- **RecoveryNode(n)**: runs child 1; if it fails, runs child 2 (the recovery) and then retries child 1, up to n times.
- **PipelineSequence**: runs children in order, but keeps re-ticking earlier children while later ones run (so replanning continues during path following).
- **RateController hz**: only ticks its child at the given rate.
- **ReactiveFallback**: tries children in order each tick; here `GoalUpdated` first means a new goal immediately interrupts recovery.
- **RoundRobin**: each time it is entered, runs the next child in the list, cycling.
- **Sequence**: all children must succeed in order.
- **Fallback** (used in v2): tries children in order until one succeeds.

### 4.1 `explore.xml` (tree `ExploreNavigate`, used by `nav2.launch.py`)

Header comment: Nav2's default structure plus a BackUp recovery, for escaping near-wall situations during frontier exploration. A dated note says BackUp was placed before Spin (2026-10-22) after a contact-slip event.

```
RecoveryNode NavigateRecovery (6 retries)
|- PipelineSequence NavigateWithReplanning
|  |- RateController 1.0 Hz
|  |  `- RecoveryNode ComputePathRecovery (1 retry)
|  |     |- ComputePathToPose goal={goal} path={path} planner_id=GridBased error_code_id={compute_path_error_code}
|  |     `- ClearEntireCostmap global_costmap/clear_entirely_global_costmap
|  `- RecoveryNode FollowPathRecovery (1 retry)
|     |- FollowPath path={path} controller_id=FollowPath error_code_id={follow_path_error_code}
|     `- ReactiveFallback FollowPathFallback
|        |- GoalUpdated
|        `- RoundRobin LocalRecoveryActions
|           |- Sequence ClearCostmaps: ClearEntireCostmap local, ClearEntireCostmap global
|           |- BackUp backup_dist=0.15 backup_speed=0.08 error_code_id={backup_error_code}
|           |- Spin spin_dist=1.57 error_code_id={spin_error_code}
|           `- Wait wait_duration=3.0
`- ReactiveFallback TopLevelFallback
   |- GoalUpdated
   `- RoundRobin TopLevelRecovery
      |- ClearEntireCostmap local
      |- ClearEntireCostmap global
      |- BackUp backup_dist=0.20 backup_speed=0.08
      |- Spin spin_dist=1.57
      `- Wait wait_duration=5.0
```

Reading it: each second the path is recomputed (if planning fails once, clear the global costmap and try again). Meanwhile FollowPath runs. If FollowPath fails, the local recovery rotates through clear costmaps, back up 0.15 m at 0.08 m/s, spin 1.57 rad (about 90 degrees), wait 3 s, then FollowPath is retried (1 retry). If the whole pipeline fails, the top-level recovery rotates through clearing, backing up 0.20 m, spinning, waiting 5 s, and the whole navigation is retried up to 6 times. A new goal at any time (`GoalUpdated`) aborts recovery.

The clear services used are `local_costmap/clear_entirely_local_costmap` and `global_costmap/clear_entirely_global_costmap`.

### 4.2 `navigate.xml` (tree `Navigate`, used by `nav2_localization.launch.py` for v1)

Same skeleton as explore.xml but with no BackUp anywhere. Differences:
- Local recovery (`LocalRecovery` RoundRobin): clear both costmaps (Sequence `ClearBothCostmaps`), Spin 1.57, Wait 5.0.
- Top-level `TopLevelRecovery`: clear local, clear global, Spin 1.57, Wait 5.0.
- Top-level retries 6, `ComputePathRecovery` 1 retry, `FollowPathRecovery` 1 retry, `RateController` 1.0 Hz, as in explore.xml.

The header comment's "Spin 90°" corresponds to `spin_dist="1.57"` (radians).

### 4.3 `navigate_v2.xml` (tree `Navigate`, used when `VACUUM_NAV_VARIANT=v2`)

Identical to navigate.xml except the top-level fallback. Header says: navigate.xml plus a START_OCCUPIED recovery. The `TopLevelFallback` ReactiveFallback contains `GoalUpdated` and then a `Fallback` named `TopLevelRecoverySelect` with two children:

1. `Sequence StartOccupiedRecovery`:
   - `AreErrorCodesPresent error_code={compute_path_error_code} error_codes_to_check="205"` (205 is START_OCCUPIED per the file comment: the planner refused because the start cell is occupied). Succeeds only if the last planner error was 205.
   - `BackUp backup_dist=0.15 backup_speed=0.05`
   - `Spin spin_dist=0.52` (about 30 degrees)
2. If the sequence fails (error code was not 205, or a step failed), `RoundRobin TopLevelRecovery` as in navigate.xml: clear local, clear global, Spin 1.57, Wait 5.0.

So in v2 a start-occupied failure triggers a small back-up and a small turn so the next plan starts from a free cell, whereas other failures use the generic recovery. (The inner RoundRobin is mis-indented in the XML, but it is a sibling of the Sequence inside the Fallback.)

---

## 5. `vacuum_controller` package

### 5.1 `config/controllers.yaml` (ros2_control)

Loaded by the Gazebo ros2_control plugin; kinematics must match the xacro (comment: wheel_separation 0.268 m, wheel_radius 0.033 m).

| Section / parameter | Value | Meaning |
|---|---|---|
| `controller_manager.update_rate` | 50 Hz | Control loop rate (comment: matches the Gazebo physics step) |
| controllers registered | `joint_state_broadcaster` (JointStateBroadcaster), `diff_drive_controller` (DiffDriveController) | |
| `joint_state_broadcaster.joints` | `left_wheel_joint`, `right_wheel_joint` | Published to `/joint_states` |
| `left_wheel_names` / `right_wheel_names` | `left_wheel_joint` / `right_wheel_joint` | |
| `wheel_separation` | 0.268 m | |
| `wheel_radius` | 0.033 m | |
| `wheel_separation_multiplier` | 1.0 | Comment: was 0.945, the fudge overshot (odom/GT yaw 0.947 to 1.06), slip is non-stationary so drift is measured instead |
| `left_wheel_radius_multiplier`, `right_wheel_radius_multiplier` | 1.0 | |
| `publish_rate` | 30.0 Hz | Odometry and TF rate |
| `odom_frame_id`, `base_frame_id` | `odom`, `base_footprint` | |
| `open_loop` | false | Odometry uses wheel feedback |
| `velocity_rolling_window_size` | 10 | Averaging window for measured velocity |
| `enable_odom_tf` | true | Publishes odom to base_footprint transform |
| `pose_covariance_diagonal` | [0.001, 0.001, 1e6, 1e6, 1e6, 0.001] | |
| `twist_covariance_diagonal` | [0.001, 0.001, 1e6, 1e6, 1e6, 0.01] | |
| `use_stamped_vel` | false | The yaml says Twist is accepted, but the relay below states Jazzy's controller needs stamped input, and the launch comment says it subscribes only to the stamped topic (verified 2026-10-20) |
| `cmd_vel_timeout` | 0.5 s | Robot stops if no command for this long (comment: was 1.5, masked a starved controller) |
| `linear.x` limits | velocity +/-0.5 m/s; acceleration +1.0, -1.0 m/s^2; jerk off | Enabled |
| `angular.z` limits | velocity +/-2.0 rad/s; acceleration +/-2.0 rad/s^2; jerk off | Enabled |

Acceleration ramp: the diff_drive_controller itself limits acceleration to 1.0 m/s^2 linear and 2.0 rad/s^2 angular. For Nav2 commands the velocity smoother (2.5 m/s^2, 3.2 rad/s^2) is looser than this, so the controller's limits are the binding ramp. For teleop commands, which bypass the smoother, the controller's ramp is the only one. Nav2's own caps (0.30 m/s, 1.0 rad/s) are below the controller's caps (0.5 m/s, 2.0 rad/s).

### 5.2 `launch/controllers.launch.py`

Arguments: `use_sim_time` (true), `enable_odom_noise` (false), `enable_diagnostics` (true), `enable_camera_diagnostics` (true), `odom_mode` (`clean`; `eval` is the alternative), `odom_noise` (false), `odom_noise_seed` (0). Note `enable_diagnostics` and `enable_camera_diagnostics` are declared but not used as conditions; the diagnostics nodes always start.

| Time | Node | Detail |
|---|---|---|
| T+2 s | `jsb_spawner` | spawns `joint_state_broadcaster --activate` |
| T+2 s | `ddc_spawner` | spawns `diff_drive_controller --activate`; in `eval` mode it adds `--param-file` `vacuum_eval/config/ddc_no_tf.yaml` (that yaml is not in this package) |
| T+12 s | `cmd_vel_relay` | default input `/cmd_vel` |
| T+12 s | `cmd_vel_relay_nav` | `input_topic: /cmd_vel_smoothed` |
| T+12 s | `odom_relay` | `topic_tools relay` `/diff_drive_controller/odom` to `/odom` (only when not eval) |
| T+12 s | `odom_noise_node` (package `vacuum_eval`) | only when `odom_mode=eval`, parameters `enable_noise`, `seed`. Publishes /odom and the odom TF in that mode |
| T+13 s | `odometry_noise_node.py` | `enable_noise` from `enable_odom_noise`, `linear_noise_std` 0.005, `angular_noise_std` 0.003, `rate_hz` 30.0 |
| T+13 s | `motion_diagnostics_node.py` | `cmd_vel_timeout_warn` 0.5, `publish_rate` 2.0 |
| T+15 s | `camera_diagnostics_node.py` | parameters loaded from `vacuum_gazebo/config/camera.yaml` |

Inconsistency in comments: the file's top docstring says the controllers are auto-loaded by gz_ros2_control and "explicit spawners would conflict", while the code does start spawners and the comment above them says explicit spawners are required. The code (spawners present) is what executes.

### 5.3 Python nodes

#### `cmd_vel_relay.py` (node `cmd_vel_relay`)
- Subscribes: `Twist` on the `input_topic` parameter (default `/cmd_vel`), QoS depth 10.
- Publishes: `TwistStamped` on `/diff_drive_controller/cmd_vel`, depth 10.
- Logic: on each message, copies it into a `TwistStamped` with `header.stamp` = node clock now (sim time when `use_sim_time`) and `frame_id` = `base_footprint`. No filtering, no scaling, no ramp.
- Two instances run: the default (teleop on `/cmd_vel`) and `cmd_vel_relay_nav` (Nav2 output on `/cmd_vel_smoothed`). Both publish to the same output topic, so there is no arbitration between them; whichever publishes last wins.

#### `odometry_noise_node.py` (node `odometry_noise_node`)
- Subscribes: `Odometry` on `/odom` (RELIABLE, VOLATILE, depth 10).
- Publishes: `Odometry` on `/odom_noisy` (same QoS).
- Parameters: `enable_noise` (false), `linear_noise_std` 0.005 m, `angular_noise_std` 0.003 rad, `rate_hz` 30.0. Note `rate_hz` is declared but never used; output is published once per input message.
- Logic: copies header, child frame and twist. If noise is off, the pose is passed through. If on, adds Gaussian noise `N(0, 0.005)` to x and y, extracts the yaw from the quaternion, adds `N(0, 0.003)` to the yaw, rebuilds a yaw-only quaternion (roll and pitch set to zero), and adds the variances to pose covariance entries [0], [7], [35]. The twist is not noised. This does not feed Nav2 (Nav2 uses `/odom`); it exists for comparing ideal and degraded odometry. Each call draws independent noise (not a random walk), so it is jitter rather than drift.

#### `motion_diagnostics_node.py` (node `motion_diagnostics_node`)
- Subscribes: `/cmd_vel` (Twist), `/odom` (Odometry), `/joint_states` (JointState), depth 10.
- Publishes: `/motion_diagnostics` (DiagnosticArray) every 1/`publish_rate` s (2 Hz).
- Statuses: `Vacuum/CommandVelocity` (WARN if no command yet, or if age of last `/cmd_vel` exceeds `cmd_vel_timeout_warn` = 0.5 s, incrementing a timeout counter each publish; otherwise OK; reports linear_x, angular_z), `Vacuum/Odometry` (position, yaw in degrees, velocities, plus absolute tracking error between last `/cmd_vel` and measured velocity), `Vacuum/WheelVelocities` (position and velocity of each joint whose name contains "wheel").
- Caveat from the code: it listens to `/cmd_vel` only, not `/cmd_vel_smoothed` or `/cmd_vel_nav`, so during Nav2 driving it will report a timeout warning and a stale tracking error.

#### `camera_diagnostics_node.py` (node `camera_diagnostics_node`)
- Subscribes: colour image `/camera/color/image_raw`, depth image `/camera/depth/image_rect_raw`, point cloud `/camera/depth/points` (topic names are parameters `topics.*`).
- Publishes: `/camera/diagnostics` (DiagnosticArray) at `diagnostics.publish_rate_hz` = 5.0 Hz.
- Parameter defaults: `min_fps_color` 25.0, `min_fps_depth` 25.0, `min_fps_points` 10.0, `max_latency_s` 0.10, `fps_window_s` 2.0 (the launch overrides these from `camera.yaml`, which was not read).
- Logic: an `FPSTracker` per stream keeps arrival timestamps (monotonic clock) in a rolling window; fps = count in window / window length. Latency = monotonic now minus the message's header stamp (best effort; with simulation time this compares different clocks, so latency values are only meaningful if the stamp and monotonic clock share a base). Each status is OK if fps >= minimum and latency <= `max_latency_s`, otherwise WARN. Also publishes `D435i/System` with CPU percent (psutil), process RSS RAM in MB, and uptime.

#### `teleop_arrows.py` (node `teleop_arrows`)
- Publishes `Twist` on `/cmd_vel`; reads the terminal keyboard (raw mode, 0.1 s select timeout).
- Defaults: linear 0.20 m/s, angular 0.80 rad/s.
- Keys: Up = (+linear, 0), Down = (-linear, 0), Left = (0, +angular), Right = (0, -angular), space or s = stop. `q`/`z` change linear speed by +/-0.02 (clamped to 0.02..1.0), `w`/`x` change angular speed by +/-0.05 (clamped to 0.05..2.0). Note the banner says "10%" but the code uses fixed steps. Esc or Ctrl+C quits and sends a zero command.
- Publishes only on a key event, no repeat timer and no software acceleration ramp. The 0.5 s `cmd_vel_timeout` in the controller stops the robot shortly after key presses cease; smooth acceleration comes from the diff_drive_controller limits.

#### `robot_steering_gui.py` (node `robot_steering_gui`, Tkinter)
- Publishes `Twist` on `/cmd_vel` from a 10 Hz timer (`CmdVelPublisher`), running in a background thread; the GUI runs in the main thread.
- D-pad buttons and arrow keys add/remove entries in an active-key set; a 100 ms loop computes velocity from the sliders: linear slider 0.05 to 1.0 (default 0.3, step 0.05), angular slider 0.1 to 2.0 (default 0.8, step 0.1). Forward = +linear, back = -linear, left = +angular, right = -angular; combos are summed per axis (opposite keys on the same axis: the later check wins in code). Space or the stop button clears keys and zeroes velocity. Releasing the last key calls stop. On window close it zeroes velocity.
- No acceleration ramp in the node; limits come from the diff_drive_controller. Since the timer republishes the stored velocity at 10 Hz, the command stays alive for the controller's 0.5 s timeout.

---

## 6. Where speed and acceleration are limited (summary)

| Stage | Linear speed | Angular speed | Linear accel | Angular accel |
|---|---|---|---|---|
| MPPI sampler | 0.0 to 0.30 m/s | +/-1.0 rad/s | +/-3.0 m/s^2 (`ax`) | 3.5 rad/s^2 (`az_max`) |
| Spin behaviour | none | 0.4 to 1.0 rad/s | none | 3.2 rad/s^2 |
| Velocity smoother | -0.10 to 0.30 m/s | +/-1.0 rad/s | +2.5 / -2.5 m/s^2 | +/-3.2 rad/s^2 |
| diff_drive_controller | +/-0.5 m/s | +/-2.0 rad/s | +/-1.0 m/s^2 | +/-2.0 rad/s^2 |
| Teleop arrows | default 0.20 (max 1.0) | default 0.80 (max 2.0) | none | none |
| Steering GUI | slider 0.05 to 1.0 | slider 0.1 to 2.0 | none | none |

Net effect for autonomous driving: forward speed is capped at 0.30 m/s by MPPI and the smoother, and the real acceleration ramp experienced by the wheels is set by the diff_drive_controller (1.0 m/s^2 linear, 2.0 rad/s^2 angular), which is tighter than the smoother's 2.5 and 3.2.

---

Summary: Nav2 turns a goal into wheel motion via a behaviour tree that replans with Smac Hybrid A* (DUBIN) at 1 Hz and follows with MPPI at 20 Hz on a 4 m local costmap, passes commands through the velocity smoother and a Twist-to-TwistStamped relay into the diff_drive_controller (the final 1.0 m/s^2 and 2.0 rad/s^2 ramp), and recovers with costmap clearing, back-up, spin and wait, while the Python nodes only relay, add optional noise, teleoperate and publish diagnostics.
