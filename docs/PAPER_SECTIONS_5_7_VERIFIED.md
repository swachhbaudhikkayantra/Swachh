# Verified text for sections 5.1, 5.2, 5.3 and 7.1 (setup for 7.3)

**Written for:** the paper's authors, to paste into the draft.
Every value comes from the repository configs, code and run metadata. Library defaults were checked against the installed RTAB-Map 0.23 header and the Nav2 Jazzy source. `[TBD: ...]` marks facts the repository cannot answer. The same text is in `docs/PAPER_SECTIONS_FILL.md`; this file is the short version for sections 5 and 7.1.

### 5.1 Visual SLAM

*Verified against `vacuum_slam/config/rtabmap.yaml` and the RTAB-Map 0.23 library defaults. "Default" means the library default was left unchanged. §3.6 already justifies the choice of RTAB-Map, so this subsection covers configuration only.*

RTAB-Map runs in RGB-D mode. The D435i colour, depth and camera-info topics are synchronised approximately (0.05 s window), and wheel odometry (`/odom`) is the odometry input. **No visual-odometry node runs**, so visual registration is used only for loop closure and proximity links. Because the robot moves on a flat floor, registration is constrained to three degrees of freedom (x, y, yaw), which is a change from the library default.

**Keyframes and features:**
- A new node is added to the pose graph when the robot has moved 0.10 m (default) or turned 0.087 rad, about 5° (default 0.1 rad). The map is updated at 1 Hz (default).
- Each image yields up to 500 keypoints (default count), detected with **GFTT corners and BRIEF descriptors** (feature type 6). *The draft and the config comment say ORB; that is wrong for this configuration.* Features are used within 0.1–4.0 m depth.
- A loop-closure hypothesis is accepted when its likelihood exceeds 0.11 (default) and registration finds at least **10 inliers** (the default is 20, so this is a relaxed setting).
- Proximity detection by space is enabled (default). Detection by time and multi-neighbour detection are off.
- The 10 most recent nodes sit in short-term memory (default). **No time or memory limits are set** (both 0, unlimited), so no memory limit applies to the map. *Do not claim that memory management bounds the computation; whether older nodes were transferred was not checked.*

**Occupancy grid:** RTAB-Map projects the depth cloud into a 2D grid with 5 cm cells (default), with ray tracing on and 3D off. Points up to 0.03 m above the floor count as ground, and points between 0.03 m and 0.30 m count as obstacles. The Nav2 obstacle layers use the same 0.03–0.30 m band. The evaluation's ground-truth rasteriser counts objects between 0.03 m and 0.25 m (its code default; the 0.30 m value in the evaluation config is not passed to it). The ground-truth grids of all six test worlds are identical for both values, so the comparison is unaffected. The published grid is the static map for Nav2 and the input to frontier exploration.

**Odometry in simulation:**
- Wheel odometry comes from a `ros2_control` differential-drive controller on the simulated wheel joints (wheel radius 0.033 m, track 0.268 m, 30 Hz).
- In the **exploration** campaign, a noise node perturbs it. A persistent scale error is drawn once per episode (σ = 2 % linear, 3 % angular), and a heading random walk is added (0.02 rad per √m travelled, 0.03 rad per √rad turned). The noise seed is the episode seed plus 1000.
- **Navigation, avoidance and responsiveness ran without injected noise.**
- **Odometry kinematics (simulation and robot):** from the left and right wheel angular velocities ωL and ωR, the base moves at v = r·(ωL + ωR)/2 and turns at ω = r·(ωR − ωL)/L, where r is the wheel radius and L the track width. In the simulation r = 0.033 m and L = 0.268 m. On the physical robot the draft describes 6-inch hub motors, a nominal r of about 0.076 m. [TBD: the physical track width and the wheel-encoder resolution are not documented in the repository; the simulated values are used for all results here.]

**Settings changed from the library defaults** (all others in this section are defaults): 3-DoF registration, minimum inliers 10, angular update 0.087 rad, depth-feature limits, and the grid settings above.

### 5.2 Path Planning

*Verified against `vacuum_exploration` and `vacuum_nav2/config/nav2_params.yaml`. Library defaults were checked against the Nav2 Jazzy source (Smac) and the sample parameter file.*

Path planning works at two levels: **where to go next** (exploration goal selection) and **how to get there** (global planning and local control).

**Goal selection (frontier exploration).** The explorer is a custom implementation in this repository; no external source is recorded in the code, package metadata or git history. Its detector is labelled "wavefront" in the code but is a plain grid scan with flood-fill clustering.
1. **Detect.** At 2 Hz, find free cells (value 0) that have at least one unknown 4-neighbour. Cluster them by flood fill within a ±0.5 m window, and drop clusters under 5 cells. The centroid is the mean cell position.
2. **Filter.** The manager (10 Hz state machine) drops frontiers shorter than 0.5 m (cells × 0.05 m) and any frontier that is blacklisted.
3. **Score.** Each frontier gets `score = 1.0 · ln(1 + n_cells) − 1.5 · d − 0.8 · p`, where `n_cells` is the frontier size, `d` is the straight-line distance in metres from the robot to the centroid (not path length), and `p = max(0, 1 − d_obs / 0.5)` is an obstacle-proximity penalty in [0, 1] from the nearest occupied cell within 0.5 m of the centroid. The highest score wins.
4. **Snap.** The centroid lies on unknown space, so the goal is moved to the nearest free cell with at least 0.30 m clearance, searching up to 1.5 m away. If none exists, the frontier is blacklisted.
5. **Send.** A goal within 0.30 m of the robot is not sent. Otherwise it goes to Nav2 as a `NavigateToPose` goal.
6. **Monitor and blacklist.** A goal that fails, exceeds 30 s, or shows less than 0.30 m of displacement in 15 s (in-place rotation counts as activity) is cancelled and blacklisted for 60 s (matching radius 0.5 m). After a successful goal, a frontier within 0.5 m that persists while fewer than 10 free cells were added is blacklisted too.
7. **Finish.** Exploration ends when five consecutive detection cycles find no frontier, the free-cell count grew by under 10 over 15 s, and the robot is stationary (|v| < 0.02 m/s). If no map exists after 3 s, the robot spins at 0.4 rad/s for 8 s to bootstrap.

*Not implemented, so do not claim them:* retries (a retry-count parameter exists but is never used), adaptive tightening of the frontier filter, and any coverage planner (e.g. boustrophedon).

**Global planning:** Nav2 **Smac Hybrid-A\*** with the Dubins motion model (the library default) and 72 heading bins (default). Settings we changed: minimum turning radius 0.25 m (default 0.4), goal tolerance 0.30 m (default 0.25), reverse penalty 2.1 (default 2.0), retrospective penalty 0.025 (default 0.015), and the cost limit for analytic expansion 3.5 (default 200.0). The analytic-expansion ratio (3.5) and maximum length (3.0 m) are defaults. Unknown space is allowed (default) and planning is capped at 5 s (default). Dubins (forward-only, curvature-bounded) paths suit this robot for two reasons: the MPPI controller is configured forward-only (minimum forward speed 0), so planned paths should be drivable without reversing; and the camera looks only forward (69.4° in the simulation), so reversing would move the robot into space it cannot see. [Authors to confirm this rationale: the repository records no earlier reason.]
- **Global costmap:** follows the SLAM map, 5 cm resolution, 1 Hz; layers are the static map (RTAB-Map), the spatio-temporal voxel layer and inflation (radius 0.28 m, cost scaling 5.0). The robot footprint is the 0.30 × 0.25 m rectangle.
- **Local costmap:** 4 × 4 m rolling window, 5 Hz, the same three layers.

**Local control:** an **MPPI** controller at 20 Hz.
- It samples 2,000 trajectories over 2.8 s (56 steps of 0.05 s) with a differential-drive model, and scores them with eight critics: constraint, footprint cost, goal, goal angle, path align, path follow, path angle and prefer-forward.
- Velocity limits are 0 to 0.30 m/s (forward only) and 1.0 rad/s. A velocity smoother limits acceleration to 2.5 m/s² and 3.2 rad/s².
- Critic weights follow the Nav2 sample file except prefer-forward (15, sample 5), footprint-aware collision cost on, and path-align sampling step 3 (sample 4). Lateral-motion settings are zero, because the robot cannot move sideways.
- A goal counts as reached within 0.30 m and 0.5 rad.

### 5.3 Obstacle Detection and Avoidance

The robot detects obstacles **only with cameras**.

**Geometric channel (depth):**
- The depth image is converted into a planar scan from a band of 5 image rows, with range limited to 0.20–4.00 m.
- **Field of view:** the simulated D435i sees **69.4°** horizontally. The real D435i depth camera is wider (about 87° by the manufacturer's specification). The simulation gives depth the colour sensor's field of view, because Gazebo defines one field of view for both. State this as a simulation limitation.
- The scan marks obstacles in a **spatio-temporal voxel layer (STVL)**: voxel size 0.05 m, obstacle height 0.03–0.30 m. Within the camera's view it clears cells on every update; outside it, cells **decay** after 15 s (local costmap) or 60 s (global).
- Without decay, a forward-facing camera leaves "ghost" obstacles behind the robot that are never observed again. *The clearing frustum in the costmap configuration uses 86°, which doesn't match the 69.4° sensor; disclose it.*
- The SLAM map is a persistent static layer in both costmaps.
- **Simulated camera noise is off** (standard deviation 0), so depth is ideal in the simulation.

**Semantic channel (RGB):** the trash detector's *obstacle* class is used by the Decision Module (Section 5.4) and doesn't add obstacles to the costmap.

**Avoidance:**
- **Proactive:** the MPPI footprint cost critic penalises trajectories whose rectangular footprint enters inflated or lethal cells.
- **Reactive:** the global path is recomputed at 1 Hz, and a progress checker requires 0.5 m of movement every 10 s. Recoveries differ between the two stacks we evaluated:
  - **Exploration stack:** each failure triggers one recovery in rotation: clear the costmaps, then **back up 0.15 m** (at 0.08 m/s), then spin 90°, then wait 3 s. The top-level recovery uses a 0.20 m back-up and a 5 s wait. Backing up comes first on purpose, because rotating in place while touching an obstacle made the wheels slip and corrupted odometry heading in earlier tests.
  - **Navigation stack (AMCL):** clear the costmaps, spin 90°, wait 5 s. **There is no back-up step.** (An opt-in variant with a back-up exists in the repository; it was not adopted and was not used for any reported result.)

**Known sensing limits:**
- Obstacles closer than about 0.2 m are invisible to the scan.
- The five-row scan misses overhanging and very low obstacles.
- The camera sees only 69.4° ahead, so side and rear obstacles rely on decay and the static map.

These are reported as limitations. Section 7 shows how contact corrupts odometry in practice.

### 7.1 Experimental Setup

**Trash detection:**
- **Data and training:** the detectors were trained on the dataset of Section 4: 611 / 175 / 87 train / validation / test images, with augmentation only on the training split. Inputs were 640 × 640 for 100 epochs.
- **Metrics:** precision, recall, F1 and mAP@0.5 on the held-out test set. On-device timings were measured on the Jetson Orin Nano (Section 6.3).
- **RF-DETR** (from `training_config.json`): DINOv2 windowed-small encoder, 100 epochs, batch size 16, learning rate 1.0e-4 (encoder 1.5e-4), weight decay 4.8e-5, EMA decay 0.993, trained on the augmented dataset folder. [TBD: the YOLOv8 and YOLOv11 training settings (no training logs or configs are in the repository), and the training GPU (the saved config only shows a college PC path, not the GPU).]

**Navigation and SLAM (simulation only; nothing here ran on the physical robot or the Jetson):**

- **Simulator:** Gazebo Harmonic (gz-sim 8) with ROS 2 Jazzy on Ubuntu 24.04.
- **Simulated robot (a scaled model, not a copy of the physical robot):**
  - Differential-drive base 0.30 × 0.25 m, chassis 2 kg, wheel radius 0.033 m, track 0.268 m, with the axle 8 cm behind the base origin and a front ball caster. Navigation limits are 0.30 m/s and 1.0 rad/s.
  - Simulated D435i at 0.18 m above the floor, 0.10 m ahead of the base origin, with no tilt: 640 × 480 at 30 Hz, **69.4° horizontal field of view** for colour and depth, depth range 0.105–10 m (0.20–4.0 m in the scan used for navigation), and **no sensor noise**.
  - The physical robot is about 0.60 × 0.50 m and 50 kg.
  - Ground-truth pose comes from the simulator, and contact sensors on the chassis and camera count collisions.
- **Odometry noise:** on in the exploration campaign only (Section 5.1). The navigation, avoidance and responsiveness campaigns used noise-free wheel odometry.
- **Test worlds** (held out, frozen before any test run; all outer walls textured; dimensions are wall centre-line spans):

| World | Size (m) | Reachable / cleanable floor area (m²) | Contents |
|---|---|---|---|
| office | 8.2 × 6.2 | 34.0 / 40.4 | 21 furniture models (desks, chairs, table, cabinets, pillars, plant), two lights plus sun |
| multi_room_loop | 7.4 × 7.4 | 39.1 / 47.0 | interior walls forming a loop, 14 obstacles |
| maze_dead_ends | 8.2 × 6.2 | 33.3 / 41.4 | interior partitions with dead ends, walls only |
| two_rooms_door | 8.4 × 4.2 | 28.1 / 31.6 | two rooms joined by a 0.9 m door, 2 obstacles |
| avoid_u_trap | 6.0 × 4.0 | 20.8 / 23.6 | three-wall U-shaped trap (walls 1.0 m high, trap walls untextured) |
| avoid_dynamic_sudden | 6.0 × 4.0 | 21.3 / 23.7 | one 0.4 m box that emerges from behind a wall at 0.5 m/s |

  Development worlds (apartment, empty room, cluttered room and further avoidance scenarios) were used for tuning only, with disjoint seeds.
- **Campaigns** (what was actually run, on the test split):
  - **Exploration:** 3 worlds × seeds 101–103 = **9 episodes**, frontier explorer, 450 s of simulated time, odometry noise on.
  - **Navigation:** 3 worlds (office, two_rooms_door, maze_dead_ends) × seeds 101–104 = **12 episodes** (178 goals), up to 20 random goals each, 900 s cap, on a **ground-truth map with AMCL localisation**, no injected noise. *This campaign measures Nav2 + AMCL, not the RTAB-Map pipeline.*
  - **Avoidance:** 2 scenarios × seeds 101–103 = **6 episodes**.
  - **Responsiveness:** office, bare and loaded stack × seeds 101–102 = **4 episodes**; the two bare runs are invalid by design (the RTAB-Map validity gates don't apply to a stack without RTAB-Map).
- **Host:** an HP Victus 15 gaming laptop (15-fb3185AX) with an AMD Ryzen 7 260 CPU (8 cores, 16 threads), 24 GB RAM (about 22 GB usable) and an NVIDIA GeForce RTX 5050 laptop GPU (8 GB, 60 W), running Ubuntu 24.04. The measured real-time factor was 0.73–0.75 for six exploration episodes (three simulations in parallel), and 0.80–1.0 for avoidance and 0.99–1.0 for navigation and the maze runs. (CPU model taken from the laptop's product specification; confirm with `lscpu` if a reviewer asks.)
- **Episode validity:** an episode is *invalid* (excluded but reported) if more than 10 % of camera frames are dropped, RTAB-Map stalls for more than 5 s, or it updates less than 0.5 times per second. Every metric additionally carries a health flag (OK / low-n / suspect / unmeasurable). Flags never exclude data.
- **Statistics:** the episode is the statistical unit. Results are reported as means with 95 % CIs from an episode-level cluster bootstrap. Definitions, thresholds, the world split and the analysis plan were pre-registered before the test runs.
- **Deviations from the pre-registered plan (all logged):**
  - The campaign was reduced to fit a 4-hour budget: 41 planned episodes became 25, plus 6 extra navigation episodes (seeds 103–104) added later.
  - Two measurement fixes were made before any test run: the recorder's frame counting (it over-reported dropped frames), and the goal-start tolerance (a goal sent up to 1 s before the first motion command now counts).
  - The first six exploration episodes ran with three simulations in parallel and the rest with two.
  - The noise-off exploration condition was dropped, so noise robustness was not measured.
  - A second navigation variant was developed and failed its dev check, so no test runs used it.

**Metrics:**
- **Coverage:** explored free area / reachable free area.
- **Map completeness:** mean of free-space and wall recall against the ground-truth grid, without alignment search.
- **ATE / RPE:** absolute and relative trajectory error of the SLAM pose vs. ground truth, with no scale correction.
- **Loop-closure precision:** accepted closures whose relative transform matches ground truth within 0.10 m and 5°.
- **Loop-closure recall:** revisits that produced a closure.
- **Navigation success:** goals reported reached by Nav2 *and* within 0.30 m of the goal in ground truth.
- **Path-length ratio:** travelled length / shortest feasible path.
- **Collisions:** contact events.
- **Obstacle-avoidance rate:** encounters without contact.
- **Responsiveness:** wall-clock latency from command to motion and from command to stop.
- **Cleaning efficiency** (secondary): virtually swept area (0.25 m swath) / reachable area, divided by the overlap ratio.

## V. Verification log (six independent read-only checks of this file against the repository)

*Everything in sections 5.1–5.3 and 7.1 was re-derived from configuration files, code and run metadata, with library defaults checked against the installed RTAB-Map 0.23 header and the Nav2 Jazzy source. Corrections to the earlier draft of this file:*

| Earlier text | Correct |
|---|---|
| "500 ORB features" | GFTT corners with BRIEF descriptors (feature type 6). The config comment saying "ORB" is wrong |
| Depth field of view 87° | 69.4° in the simulation (Gazebo gives depth the colour sensor's field of view). The costmap clearing frustum uses 86°, an inconsistency |
| Back-up before rotating, in all recoveries | Only in the exploration behaviour tree. The AMCL navigation tree has no back-up (clear, spin 90°, wait 5 s) |
| Memory management bounds computation | No time or memory limits are set; the feature isn't active |
| Odometry noise on in test campaigns | On in exploration only; off in navigation, avoidance and responsiveness |
| Explorer weights "1.0, 1.5, 0.8" without terms | `1.0·ln(1+cells) − 1.5·distance − 0.8·obstacle penalty`; the YAML weights are never read, the code defaults are identical |
| Retry and adaptive filter tightening | Declared but unused; do not claim |
| Tuned values: keyframe 0.10 m, 1 Hz, 500 features, 0.11 threshold, memory 10, 5 cm grid | All library defaults. Tuned: 3-DoF, 10 inliers, 0.087 rad, depth limits, grid settings |
| Smac settings | Tuned: turning radius 0.25 (default 0.4), tolerance 0.30 (0.25), reverse penalty 2.1 (2.0), retrospective 0.025 (0.015). Dubins is the default |
| "Perception, mapping, planning run on the Jetson" | The Jetson is the robot's computer, but only detection was benchmarked on it; navigation ran in simulation only |
| Nav2 footprint "circle 0.18 m" (config comment) | 0.30 × 0.25 m rectangle |

**Confirmed:** the stack was frozen before the test runs (all test-run commits descend from the freeze commit, and after it only the opt-in v2 files changed); the 0.03–0.30 m height band is the same in RTAB-Map and Nav2 (the ground-truth rasteriser uses 0.03–0.25 m by code default, with identical grids for all six test worlds); 20 Hz MPPI with 2,000 samples and 2.8 s horizon; 1 Hz replanning; 0.5 m / 10 s progress checker; STVL decay of 15 s (local) and 60 s (global).

**Not in the repository (authors must supply):** the real robot's encoder and odometry formula; the real D435i mounting height and tilt; confirmation of the Dubins rationale given above; the Jetson's ROS version (JetPack 6.1 is stated); the YOLOv8 and YOLOv11 training settings and the training GPU. (Floor areas are now filled in from the ground-truth grids.)
