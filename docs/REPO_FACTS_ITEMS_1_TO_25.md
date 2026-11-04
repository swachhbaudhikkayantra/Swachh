# Repository facts for sections 5.1, 5.2 and 7.3: answers to items 1 to 25

**Written for:** the paper's authors. This is the full evidence behind `PAPER_SECTIONS_FILL.md`.

**How it was produced:** six independent read-only checks of the repository, run on 2026-10-25. I re-checked the key claims myself: the RTAB-Map feature enum and defaults (installed header `rtabmap-0.23`), the Smac defaults (Nav2 Jazzy source), the freeze history in git, and the recovery behaviour trees.

**Conventions:**
- `SRC` = `Navigation/Simulation/vacuum_ws/src`.
- "Default" means the library default was left unchanged. "Tuned" means we changed it.
- Line numbers refer to the repository at commit `72377df`.

---

## A. Explorer (section 5.2)

### Item 1. Frontier utility function
`SRC/vacuum_exploration/vacuum_exploration/goal_selector.py`, `_compute_score`, lines 125-148:

```python
info_gain = math.log(1 + frontier.size)
obs_penalty = self._obstacle_penalty(cx, cy, grid) if occupancy_grid is not None else 0.0
return (self._w_info * info_gain - self._w_dist * dist - self._w_obs * obs_penalty)
```

`score = 1.0 * ln(1 + n_cells) - 1.5 * d - 0.8 * p`. Higher is better.

| Term | Weight | Computation |
|---|---|---|
| Information gain | 1.0 (`weight_info_gain`) | Natural log of (1 + frontier cell count). Unitless and not capped. The docstring says "normalised 0..1": it is not |
| Travel distance | 1.5 (`weight_distance`) | Straight-line distance (metres) from the map-frame robot pose to the centroid. It is not path length |
| Obstacle penalty | 0.8 (`weight_obstacle_penalty`) | `p = max(0, 1 - d_obs / 0.5)`, in [0, 1], where `d_obs` is the distance to the nearest cell with value above 50 inside a 0.5 m square window around the centroid. Zero if none |

**Runtime note:** the YAML weights sit under a `goal_selector:` key, but no node of that name runs, so they are never read. The manager uses identical code defaults (`exploration_manager.py:163-165`). The numbers are right, but the YAML block is dead configuration. The YAML comment saying the information term is `size(f)` is wrong.

### Item 2. Implementation steps (for pseudocode)
Detector (`frontier_detector.py`):
1. Every 0.5 s (2 Hz, line 101) take the latest `/rtabmap/map`.
2. Frontier cells: value 0 (free) with at least one 4-connected neighbour equal to -1 (unknown), rows and columns 1 to N-2 (lines 166-185).
3. Cluster by flood fill. `radius_cells = max(1, int(0.5 / resolution))`. The window is square (Chebyshev), not a circle (lines 187-215).
4. Drop clusters under 5 cells (default `min_frontier_size`, line 153).
5. Centroid is the mean row and column, plus 0.5, times resolution, plus the origin (lines 223-230). Publish `PoseArray` on `/frontiers/centroids`, with z carrying the cell count.

Manager (`exploration_manager.py`):
- **State machine** at 10 Hz (line 281): IDLE, WAITING_FOR_MAP, DETECT_FRONTIERS, SELECT_GOAL, SEND_GOAL, NAVIGATING, GOAL_REACHED or RECOVERING, then back, and finally FINISHED.
- **Length filter** (lines 296-311): frontier length = cells x map resolution. Drop if under 0.5 m.
- **Bootstrap** (lines 365-379): no map after 3.0 s makes the robot spin at 0.4 rad/s for 8.0 s.
- **Snap** (`_snap_goal`, lines 624-646): `clearance = distance_transform_edt(grid == 0) * res`. Keep cells with clearance of at least 0.30 m. Take the one nearest the centroid. If farther than 1.50 m, or none exists, blacklist with reason `no_snap`.
- **Goal at robot** (lines 433-442): snapped goal within 0.30 m of the robot is blacklisted (`goal_at_robot`).
- **Send** (lines 443-489): `NavigateToPose` in the `map` frame, orientation w = 1.0. Nav2 success leads to GOAL_REACHED. Abort or rejection blacklists (`nav2_failure`). Over 30 s blacklists (`timeout`). Over 15 s without progress blacklists (`oscillation`).
- **Progress tracking** (lines 313-333): the timer resets when the odometry position moves at least 0.30 m from a reference pose, or when angular speed is at least 0.05 rad/s (hardcoded). That is how in-place rotation is excluded.
- **Blacklist** (lines 576-622): matched by centroid within 0.50 m (code only, line 151). A repeat increments a failure count. Entries expire 60 s after the last failure.
- **No-information-gain rule** (lines 555-569): after a success, a frontier within 0.5 m that persists with fewer than 10 new free cells is blacklisted (`no_information_gain`).
- **Completion** (`_check_completion`, lines 530-553), evaluated when the frontier list is empty. All of: at least 5 consecutive empty cycles; free-cell history spanning at least 15.0 s with growth under 10; |odom linear.x| under 0.02 m/s.
- **Not implemented:** `retry_count` (3) is loaded but never used, and the "3 failures, tighten the filter" log message has no logic behind it.

### Item 3. Values confirmed

| Value | Confirmed | Source |
|---|---|---|
| Detection rate 2 Hz | Yes | `exploration_params.yaml:17`, `frontier_detector.py:68` |
| Cluster radius 0.5 m | Yes | `exploration_params.yaml:22` (square window of `int(0.5/res)` cells) |
| Minimum frontier length 0.5 m | Yes | `exploration_params.yaml:94` (in addition to the 5-cell detector filter) |
| Snap clearance 0.30 m | Yes | `exploration_manager.py:157` (code default only). Maximum snap distance 1.50 m (line 158) |
| Goal already reached 0.30 m | Yes | `min_goal_distance`, set in two places; the manager's use (snapped goal) is the one that matters |
| Goal timeout 30 s | Yes | `exploration_params.yaml:72` |
| Blacklist 60 s | Yes | `exploration_params.yaml:67` |
| No-progress: under 0.30 m in 15 s, rotation excluded | Yes | `oscillation_distance`, `oscillation_timeout_sec` (YAML 83-84); the 0.05 rad/s threshold is hardcoded |
| Completion: 5 empty cycles, under 10 cells over 15 s, stationary | Yes | `no_frontier_consecutive_checks`, `map_growth_threshold`, `map_growth_patience_sec`, `stationary_vel_threshold` |

### Item 4. Provenance and coverage planner
- **Authorship:** no trace of adaptation from explore_lite, nav2_wavefront_frontier_exploration or m-explore. No URL, attribution or licence note in code comments, `package.xml` (Apache-2.0, maintainer Hrishikesh-Prasad-R) or git log (only commits `38c1f30` and `127f608` touch it). Describe it as a custom implementation.
- **Naming:** the detector docstring says "Wavefront Frontier Detection", but it is a plain scan of all cells plus flood-fill clustering, not the algorithm of Keidar and Kaminka.
- **Coverage planner:** none exists. "Boustrophedon" appears only in evaluation tests, metric specs and future-work notes.

---

## B. RTAB-Map (section 5.1)

Source of defaults: the installed header `/opt/ros/jazzy/include/rtabmap-0.23/rtabmap/core/Parameters.h` (RTAB-Map 0.23.13). Config: `SRC/vacuum_slam/config/rtabmap.yaml` (`RT`), loaded by `slam.launch.py`.

### Item 5. Parameter set

| Parameter | Value | Line in RT | Default or tuned |
|---|---|---|---|
| Mode | `subscribe_depth` and `subscribe_rgb` true; `subscribe_rgbd`, scan, odom_info false | 32-37 | tuned (node-level) |
| Sync | `approx_sync` true, `approx_sync_max_interval` 0.05 s, queue 10 | 45-49 | tuned |
| Frames | `frame_id` base_footprint, `odom_frame_id` odom, `map_frame_id` map | 26-29 | tuned |
| `Reg/Force3DoF` | true | 120 | **tuned** (default false) |
| `RGBD/LinearUpdate` | 0.1 m | 92 | default |
| `RGBD/AngularUpdate` | 0.087 rad | 93 | **tuned** (default 0.1) |
| `Rtabmap/DetectionRate` | 1 Hz | 75 | default |
| `Kp/MaxFeatures` | 500 | 99 | default |
| `Kp/DetectorStrategy` and `Vis/FeatureType` | 6 = **GFTT/BRIEF** | 98, 119 | the header lists default 8 or 6 depending on build, so do not call it tuned |
| `Kp/MaxDepth`, `Kp/MinDepth` | 4.0, 0.1 | 100-101 | tuned |
| `Rtabmap/LoopThr` | 0.11 | 83 | default |
| `Vis/MinInliers` | 10 | 117 | **tuned** (default 20) |
| `Vis/InlierDistance` | 0.1 | 118 | default |
| `Mem/STMSize` | 10 | 66 | default |
| `Mem/RehearsalSimilarity` | 0.45 | 67 | tuned (default 0.6) |
| `Grid/CellSize` | 0.05 m | 107 | default |
| `Grid/3D` | false | 105 | tuned |
| `Grid/RayTracing` | true | 106 | tuned |
| `Grid/MaxObstacleHeight` | 0.30 | 108 | tuned (default 0, disabled) |
| `Grid/MinGroundHeight` | -0.1 | 109 | tuned (this is -0.1, not 0.03) |
| `Grid/MaxGroundHeight` | 0.03 | 110 | tuned |
| `Grid/NormalsSegmentation` | false | 112 | tuned (a height passthrough is used) |
| `RGBD/CreateOccupancyGrid` | true | 128 | tuned |
| `Icp/MaxTranslation`, `Icp/MaxRotation` | 0.1, 0.1 | 123-124 | tuned; ICP is not used (no lidar) |

**Correction:** the config comment "6 = ORB" is wrong. In the library, 2 = ORB, 6 = GFTT/BRIEF, 8 = GFTT/ORB. Write "GFTT corners with BRIEF descriptors".

**Tuned versus default, in one line:** only 3-DoF registration, 10 inliers, the 0.087 rad update, depth-feature limits and the grid settings differ from library defaults. The 0.10 m step, 1 Hz rate, 500 features, 0.11 threshold, memory size 10 and 5 cm grid are all defaults.

### Item 6. Odometry source
- **No visual-odometry node** is launched (no `rgbd_odometry`, `icp_odometry` or similar anywhere).
- RTAB-Map subscribes to `/odom` (`slam.launch.py:163`), `nav_msgs/Odometry`, frame odom to base_footprint.
- `Odom/Strategy`, `Odom/ResetCountdown` and `OdomF2M/MaxSize` are set in the file but have no effect, because they belong to odometry nodes that are not run.

### Item 7. Memory management
`Rtabmap/TimeThr` 0 and `Rtabmap/MemoryThr` 0 (both unlimited, defaults). `Mem/IncrementalMemory` true (default; the launch sets it, and the localisation variant sets false). `Mem/InitWMWithAllNodes` false. **`Mem/ThreadsHistory` does not exist in version 0.23.** The comment on `MemoryThr` says "MB"; the library defines it as a node count. Net effect: the working-memory to long-term-memory transfer is not active in these runs.

### Item 8. Proximity detection
`RGBD/ProximityBySpace` true (default). `RGBD/ProximityMaxGraphDepth` 0 (tuned, default 50). `RGBD/ProximityByTime` not set (default false). `RGBD/ProximityPathMaxNeighbors` not set (default 0).

### Item 9. Wheel odometry and noise
- **Source:** `gz_ros2_control` with a `diff_drive_controller` on the simulated joints (`_ros2_control.xacro`, `controllers.yaml`). Wheel separation 0.268, wheel radius 0.033, multipliers 1.0, `open_loop` false, `publish_rate` 30, `enable_odom_tf` true.
- **Noise node** `SRC/vacuum_eval/vacuum_eval/odom_noise_node.py`: subscribes to `/diff_drive_controller/odom`, publishes `/odom` and the odom to base_footprint transform. Active only with `odom_mode:=eval` (the campaign runs use it).
- **Model:** per episode, `b_lin = 1 + 0.02 * N(0,1)` and `b_ang = 1 + 0.03 * N(0,1)`. Per message, `d' = d * b_lin` and `dtheta' = dtheta * b_ang + 0.02 * sqrt(|d|) * e1 + 0.03 * sqrt(|dtheta|) * e2`. The noise seed is the episode seed plus 1000. The sigma values come from the node defaults.
- **Noise in the test campaigns:** on only in `quick_exploration.yaml` (`odom_noise: [1]`). Navigation, navigation-extra, avoidance and responsiveness are `[0]`.
- **Noise-off still exists:** yes (`odom_noise: [0]` in those campaigns; `final_exploration.yaml` has `[0, 1]`).
- **Legacy node:** `vacuum_controller/odometry_noise_node.py` publishes `/odom_noisy`, which nothing subscribes to.

### Item 10. Real robot wheel odometry
**NOT FOUND.** The Arduino sketch has no encoder code, and no encoder type, counts, radius or track width is documented. The paper text gives 6-inch hub motors, so a nominal radius of about 0.076 m can be derived, but track width and encoder resolution must come from the hardware team.

### Item 11. Topics and TF
- RTAB-Map publishes `/rtabmap/map` (OccupancyGrid), `/rtabmap/info`, `/rtabmap/mapData`, `/rtabmap/mapGraph`, `/rtabmap/mapPath`, `/rtabmap/grid_prob_map`, `/rtabmap/cloud_map`, and the map to odom transform. No pose topic is remapped; poses come from the map to base_footprint transform.
- **Nav2:** a topic relay copies `/rtabmap/map` to `/map` (`nav2.launch.py:63-73`). Both costmaps' static layers read `/map` (`nav2_params.yaml:273`, `:336`).
- **Explorer:** subscribes to `/rtabmap/map` (`frontier_detector.py:67`, `exploration_manager.py:260-261`) and uses the map to base_footprint transform.
- **Evaluation recorder:** `/rtabmap/info`, `/rtabmap/map`, `/odom`, `/ground_truth/odom`, plus the map to odom transform (`recorder_node.py:145-169, 267, 403`).

---

## C. Camera and robot model

### Item 12. Camera
| Item | Value | Source |
|---|---|---|
| Height above floor | 0.1805 m (camera_link centre); top about 0.193 m | `_properties.xacro:87, 119-120, 165-166` (derived: base 0.093 + mount 0.0625 + camera 0.025) |
| Tilt | 0 (none) | `_sensors.xacro:55-56` |
| Offset from base | 0.100 m forward, 0 m sideways | `_properties.xacro:116` |
| Resolution, frame rate | 640 x 480, 30 Hz (colour and depth) | `_properties.xacro:187-194`, `_gazebo.xacro:174-208` |
| Colour HFOV | 69.4 deg (1.2112 rad) | `_properties.xacro:190`, `_gazebo.xacro:172` |
| Depth HFOV (actual) | **69.4 deg.** One `rgbd_camera` sensor has a single field of view fed from the colour value. `d435i_depth_hfov` (86 deg) is defined but never used | `_gazebo.xacro:169, 172, 185-190` |
| Depth range | Sensor clip 0.105 to 10 m. The navigation scan is cut to 0.20 to 4.0 m, 5 rows | `_gazebo.xacro:178-189`, `nav2.launch.py:92-97`, `nav2_localization.launch.py:103-106` |
| Noise | Standard deviation 0.0: **noise off**. `camera.yaml` says "ideal" and its "realistic" values are never read | `_gazebo.xacro:199-203`, `camera.yaml:30, 72-75` |
| Real D435i mount | **NOT FOUND.** Only the C270 camera's mount (30 deg downward tilt, low height) is documented | |

`camera.yaml` (depth 86 deg) is not wired into the model, and the Nav2 STVL clearing frustum uses 86 deg (`nav2_params.yaml:305, 368`): this does not match the 69.4 deg sensor.

### Item 13. Robot model and limits
- **Footprint:** `[[0.15, 0.125], [0.15, -0.125], [-0.15, -0.125], [-0.15, 0.125]]`, 0.30 x 0.25 m, both costmaps (`nav2_params.yaml:263, 328`). `robot_radius` is not used. The header comment "circle, radius 0.18 m" (line 7) is stale.
- **Wheels:** radius 0.033 m; track 0.268 m; **axle 8 cm behind the base origin** (`wheel_joint_x = -0.080`); front ball caster, radius 0.018 m, at +0.132 m.
- **Mass:** chassis 2.0 kg, wheels 0.25 kg each, caster 0.05 kg, camera mount 0.05 kg, D435i 0.072 kg, arm mount 0.05 kg, vacuum mount 0.1 kg.
- **Body:** 0.30 x 0.25 x 0.10 m chassis, about 0.19 m overall with camera. The real robot is about 0.60 x 0.50 m and 50 kg: **the simulation is a scaled model.**
- **Limits:** the diff-drive plugin allows 0.5 m/s and 2.0 rad/s; Nav2 limits to 0.30 m/s and 1.0 rad/s (velocity smoother and MPPI), reverse -0.10 m/s in the smoother, acceleration 2.5 m/s^2 and 3.2 rad/s^2.

---

## D. Nav2 configuration

Both launch files use the same `nav2_params.yaml` (`P`). Defaults come from the Nav2 Jazzy sample parameter file and, for Smac, the Nav2 Jazzy source (`smac_planner_hybrid.cpp`). Installed versions: Nav2 packages 1.3.13, `spatio_temporal_voxel_layer` 2.5.5.

### Item 14. Costmaps
| Item | Global | Local |
|---|---|---|
| Size and window | Follows the static map | 4 x 4 m, rolling (`P:325-326`) |
| Resolution | 0.05 | 0.05 |
| Update / publish | 1 Hz / 1 Hz | 5 Hz / 2 Hz |
| Layers | static, STVL, inflation | static, STVL, inflation |
| Inflation | radius 0.28 m, cost scaling 5.0 | same |
| STVL decay | 60 s | 15 s |
| STVL voxel size | 0.05 | 0.05 |
| STVL obstacle height | 0.03 to 0.30 m | same |
| Depth to scan | `scan_height` 5 rows, range 0.20 to 4.00 m | same (`nav2.launch.py:90-94`) |

### Item 15. Smac Hybrid-A*
Plugin `SmacPlannerHybrid` (`P:166-201`).

| Parameter | Ours | Default |
|---|---|---|
| `motion_model_for_search` | DUBIN | DUBIN (default) |
| `minimum_turning_radius` | 0.25 m | 0.4 (**tuned**) |
| `tolerance` | 0.30 m | 0.25 (**tuned**) |
| `reverse_penalty` | 2.1 | 2.0 (**tuned**) |
| `retrospective_penalty` | 0.025 | 0.015 (**tuned**) |
| `max_planning_time` | 5.0 s | 5.0 |
| `allow_unknown` | true | true |
| `angle_quantization_bins` | 72 | 72 |
| `change_penalty`, `non_straight_penalty`, `cost_penalty` | 0.0, 1.2, 2.0 | same |
| Analytic expansion | ratio 3.5, max length 3.0 | same |

**Reason for Dubins:** NOT FOUND. Only config comments ("non-holonomic: Dubins curves") and notes that the choice is fixed by the user. The paper text gives a justification and marks it for the authors to confirm.

### Item 16. MPPI
2000 samples, 56 steps, `model_dt` 0.05 s (2.8 s horizon), `DiffDrive`, `vx_max` 0.30, `vx_min` 0.0, `wz_max` 1.0, `vx_std` 0.2, `wz_std` 0.4, temperature 0.3, gamma 0.015. Eight critics (all enabled): Constraint (4.0), Cost (3.81, `consider_footprint` true, tuned), Goal (5.0), GoalAngle (3.0), PathAlign (14.0, `trajectory_point_step` 3, tuned), PathFollow (5.0), PathAngle (2.0), PreferForward (15.0, tuned; default 5.0). Everything else is the sample default. Goal checker: `SimpleGoalChecker`, 0.30 m and 0.50 rad (tuned from 0.25 / 0.25).

### Item 17. Controller, smoother, versions
`controller_frequency` 20 Hz. Velocity smoother: 20 Hz, open loop, max velocity [0.30, 0, 1.0], min [-0.10, 0, -1.0], max accel [2.5, 0, 3.2], max decel [-2.5, 0, -3.2]. Progress checker: 0.5 m in 10 s. Versions: see the header of this section.

### Item 18. Behaviour trees
Two trees are used, and they differ:
- **`explore.xml`** (exploration stack, `nav2.launch.py:41`): replanning at 1 Hz. Per-goal recovery, one action per failure in rotation: clear local then global costmap; **BackUp 0.15 m at 0.08 m/s**; Spin 1.57 rad (90 deg); Wait 3 s. Top-level recovery: clear both costmaps, BackUp 0.20 m, Spin 1.57, Wait 5 s.
- **`navigate.xml`** (AMCL navigation stack, `nav2_localization.launch.py`): clear both costmaps, Spin 1.57, Wait 5 s. **No BackUp.** This is the tree the 12 navigation test episodes used.
- `navigate_v2.xml` and `amcl_params_v2.yaml` are an opt-in variant (`VACUUM_NAV_VARIANT=v2`), unused unless the variable is set. The default is v1.

### Item 19. Platform
ROS 2 Jazzy with Gazebo Harmonic (gz sim 8), Ubuntu 24.04.4 LTS on the test machine. Jetson Orin Nano: L4T R36.4 (JetPack 6.1), CUDA 12.6, TensorRT 10.3.0. The Jetson's ROS version is not documented (a calibration script sources Humble, which is only a hint).

---

## E. Evaluation consistency (affects section 7.3)

### Item 20. Ground-truth band
- **Corrected after tracing the call:** the config says `robot_body_z_hi: 0.30` (`eval_defaults.yaml:4`, recorded in run metadata), but nothing passes it to the rasteriser. `compute_metrics.py:90` calls `gt_grid.build(sdf, seed)` with the code defaults `ROBOT_BODY_Z_LO = 0.03`, `ROBOT_BODY_Z_HI = 0.25` (`gt_grid.py:14-15`), so the effective ground-truth band is **0.03 to 0.25 m**. RTAB-Map and the Nav2 layers use 0.03 to 0.30 m. Rebuilding the six test-world grids with both values gives **identical** occupancy, reachable and cleanable grids, so no result is affected.
- **Rasteriser:** parses the world SDF; boxes are oriented rectangles, cylinders are discs; cell-centre sampling at 0.05 m, margin 0.5 m; an object counts as an obstacle if its z-extent overlaps the band.

### Item 21. Strict success
`GOAL_TOL = 0.30` m and `GOAL_TOL_STRICT = 0.15` m (`metrics/navigation.py:14-15`). Navigation success counts a goal only if Nav2 reported success **and** the ground-truth position at that time is within the tolerance (position only, no yaw, ground truth not the localisation estimate). Nav2's own tolerance (0.30 m) is deliberately not reused, so the check is independent.

### Item 22. Host and real-time factor
- **Host:** `victus`, an HP Victus 15 (15-fb3185AX): AMD Ryzen 7 260 (8 cores / 16 threads), 24 GB RAM (about 22 GB usable), 1 TB SSD, RTX 5050 laptop GPU (8 GB, 60 W), driver 595.91, Ubuntu 24.04.4, kernel 7.0. CPU: AMD Ryzen 7 260, 8 cores / 16 threads (from the product listing for HP Victus 15-fb3185AX; `lscpu` not run), 24 GB RAM.
- **True real-time factor** (`rtf_true_mean`):

| Campaign | Min | Max | Mean | Parallel slots |
|---|---|---|---|---|
| Exploration (9) | 0.729 | 1.000 | 0.827 | office, multi_room_loop: 3 (0.729 to 0.753); maze: 2 (0.999 to 1.000) |
| Navigation (12) | 0.9995 | 1.0000 | 0.9998 | 2 |
| Avoidance (6) | 0.804 | 1.000 | 0.911 | 3 |
| Responsiveness (4) | 0.926 | 1.000 | 0.972 | 3 plus serial reruns |

### Item 23. Freeze
- **Freeze commit:** `92c7757`, 2026-10-25 17:54 IST ("Freeze for 4-hour test campaign").
- **After the freeze** only two commits touched the packages: `c88b151` (extra-seed campaign file and a pre-registration row) and `10b6b11` (the opt-in v2 files, plus 3 lines in `run_episode.py` and 10 in `nav2_localization.launch.py`). I confirmed zero diff after the freeze in `nav2_params.yaml`, `vacuum_slam`, `vacuum_exploration`, `navigate.xml` and `explore.xml`.
- **Run metadata:** the `git_commit` values in the 31 test runs are `92c7757` (13), `ee97680` (5), `c88b151` (4), `7c20be5` (4), `308c945` (2), `c822591` (2) and `b708c2b` (1). All are descendants of the freeze commit (results snapshots and docs). 18 of 31 are flagged `git_dirty`, which the log attributes to uncommitted result snapshots.
- **`nav_variant`** is not recorded in the test runs' metadata. That the default (v1) ran rests on the code default, the commit messages and the logs.
- Earlier 2026-10-22 changes (SLAM map as a static layer in the local costmap; BackUp before Spin in the exploration tree) are part of the frozen stack.

### Item 24. Test worlds
Sizes are wall centre-line spans; outer faces add 0.2 m (0.1 m in the avoid worlds). Floor areas come from the ground-truth grids (`_gt/*.npz`).

| World | Size (m) | Reachable / cleanable area (m^2) | Wall height | Obstacles | Textures | Lighting |
|---|---|---|---|---|---|---|
| office | 8.2 x 6.2 | 34.0 / 40.4 | 3.0 | 21 static models: 2 pillars, meeting table, 6 chairs, 4 desks, 4 monitors, 2 cabinets, whiteboard, plant | 4 distinct outer walls, floor texture | ambient 0.55, sun 0.85, two point lights, shadows |
| multi_room_loop | 7.4 x 7.4 | 39.1 / 47.0 | 3.0 | 14 static (13 boxes, 1 cylinder) | 4 distinct outer, interior walls reuse some | ambient 0.5, sun 0.7, no shadows |
| maze_dead_ends | 8.2 x 6.2 | 33.3 / 41.4 | 3.0 | none (walls only) | mostly distinct (one shared pair) | ambient 0.5, sun 0.7 |
| two_rooms_door | 8.4 x 4.2 | 28.1 / 31.6 | 3.0 | 2 (table, pot); 0.9 m door gap | mostly distinct (one shared pair) | ambient 0.5, sun 0.7 |
| avoid_u_trap | 6.0 x 4.0 | 20.8 / 23.6 | 1.0 | U-trap of 3 walls (**plain colour**, untextured) | 4 distinct outer walls | ambient 0.5, sun 0.8, shadows |
| avoid_dynamic_sudden | 6.0 x 4.0 | 21.3 / 23.7 | 1.0 | 1 moving box 0.4 x 0.4 x 0.5 m at 0.5 m/s, plus a hiding wall | 5 distinct walls | same as u_trap |

No world has plain-colour outer walls. No world has a ceiling. Furniture and obstacles are plain colour. The six sizes are not stated anywhere in the repository; they were computed from the SDF wall poses.

---

## F. Jetson evidence

### Item 25
RTAB-Map, the explorer and Nav2 on the Jetson: **NOT FOUND** (no logs, launch files, Dockerfiles, CPU or RAM figures; no commit mentions Jetson or Orin). Navigation is documented as simulation only. What did run on the Jetson: the YOLO detection benchmark (Scenario A direct camera, Scenario B wireless) and power monitoring; a calibration launcher script and the manual-mode HMI are labelled for it. The authors confirmed the Jetson Orin Nano is the robot's computer.

---

## Discrepancies found (repository contradicts itself or the draft)

1. The paper draft and config comments say ORB; the config uses GFTT/BRIEF.
2. The draft and `camera.yaml` say depth HFOV 86 or 87 degrees; the simulated sensor uses 69.4 degrees. The costmap clearing frustum uses 86 degrees.
3. The Nav2 file header says the footprint is a circle of 0.18 m; it is the 0.30 x 0.25 m rectangle.
4. The explorer YAML weights are never read; the information term is `ln(size)`, not `size`. `retry_count` and filter tightening are not implemented.
5. The recovery sequence differs between the two behaviour trees, and the navigation tree has no back-up.
6. `gt_grid.py` has a stale 0.25 m band top; the campaign uses 0.30 m.
7. Odometry noise was on only in the exploration campaign.
8. Memory thresholds are unlimited; `Mem/ThreadsHistory` does not exist in this version.
9. A repository note (`Navigation/Manual mode/claude_context.md`) says the project moved from the Jetson to a Raspberry Pi 5; the authors state the Jetson is the robot's computer.
10. Mixed parallelism: the first six exploration episodes ran at 0.73 to 0.75 real-time with three simulations in parallel.

## Not found
Real robot encoder and odometry details; real D435i mount; reason for Dubins; Jetson ROS version; any navigation run on the Jetson; a generated SDF for the sensors (only xacro sources exist; the 69.4 degree depth FOV follows from the xacro text, so confirm it with `ros2 topic echo /camera/depth/camera_info` if you want it beyond doubt).

## Needs a human
Confirm the Dubins rationale given in the paper text; supply the real robot's wheel track, encoder resolution and D435i mount; state the YOLOv8 and YOLOv11 training settings and the training GPU; decide whether to quote world sizes as centre-line spans or inner free spans.
