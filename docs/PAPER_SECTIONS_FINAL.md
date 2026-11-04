# Final text for sections 3.7, 3.8, 5.1 to 5.4, 7.3 and 7.4

**Written for:** the paper authors. Numbers in 7.3 and 7.4 are filled by a script from the raw result files (`vacuum_eval.paper_tables`, verified by two independent recomputations); nothing was calculated by hand. Every statement was then fact-checked sentence by sentence against the code, configs and logs by three independent read-only reviewers, and the corrections are applied. The generated tables are at the end. `[TBD: ...]` marks facts the repository cannot answer.

## 3.7 Navigation Strategy

The navigation strategy of Swachh Bauddhika Yantra is built on three requirements:
1. The robot must build its own map of an unknown indoor space, without a prior floor plan.
2. It must navigate safely using **only camera-based sensing**, with no LiDAR or ultrasonic sensors (Section 2.5).
3. All processing must run on board.

To satisfy these, the navigation stack is organised as a closed perception–planning–control loop on ROS 2 (Jazzy), with four cooperating components.

**(i) Mapping and localisation.** RTAB-Map (Section 3.6) fuses the RGB-D stream of the D435i with wheel odometry. It produces a 2D occupancy grid at 5 cm resolution and a globally corrected pose (the `map → odom` transform). Visual loop closures correct the drift that accumulates in wheel odometry.

**(ii) Exploration.** In autonomous mode the robot doesn't know where to clean first, so a **frontier-based exploration** module repeatedly selects the boundary between known-free and unknown space on the live occupancy grid as the next navigation goal. Exploration ends when no reachable frontier remains and the map stops growing.

**(iii) Global and local planning.** Each exploration goal goes to the Nav2 navigation framework:
- **Global path:** a Hybrid-A* planner (Smac Hybrid, Dubins motion model) computes a kinematically feasible path on the global costmap.
- **Local control:** a Model Predictive Path Integral (MPPI) controller follows that path at 20 Hz while respecting the robot's velocity limits and the local costmap.

**(iv) Obstacle handling and recovery.** Obstacles are sensed from the depth image, converted into a planar scan and stored in a spatio-temporal voxel layer. Obstacles that leave the camera's field of view therefore decay after a fixed time and don't block the robot indefinitely. When a path can't be computed or followed, a behaviour tree runs one recovery action per failure, in rotation: clear the costmaps, back up (exploration stack only), rotate in place 90°, wait. Then it replans.

The Decision Module (Section 5.4) sits above this loop. It can pre-empt navigation when the object detector reports trash: the robot stops and triggers the robotic arm or the vacuum, then resumes exploration.

The full stack was developed and evaluated in a Gazebo Harmonic simulation of the robot and its D435i camera (Section 7). Validating it on the physical platform is ongoing work.

---

## 3.8 Working Explanation of SBY

Swachh Bauddhika Yantra is designed around a three-stage cycle: Perceive, Process and Act. This keeps the robot in step with its surroundings while it executes its tasks. At start-up the robot is intended to check the Jetson, the Arduino link, the cameras and the wheel drivers before entering the cycle. [TBD: confirm that this start-up self-test is implemented; the repository does not show it.]

**Perceive stage.** This stage gathers data from three sources:
- an Intel RealSense D435i depth camera, used for mapping and navigation;
- the RGB cameras (Logitech C270) used for trash detection. The vision configuration in the repository reads 640 × 480 pixels at 10 fps, and the detector input is 640 × 640. [TBD: the draft states 1280 × 720 at 30 fps; confirm which applies, or cite the C270 datasheet for its rated mode.] [TBD: confirm the camera settings used for the reported detection results.] Object depth in the vision prototype comes from a calibrated pair of USB cameras (stereo disparity);
- the wheel drivers, which report the rotation of each wheel.

The distance travelled is computed from the wheel rotation. With N_L and N_R the encoder counts of the left and right wheels over one interval, CPR the counts per wheel revolution, r the wheel radius and L the track width:

    d_L = 2·π·r·N_L / CPR,    d_R = 2·π·r·N_R / CPR
    Δs = (d_L + d_R) / 2,     Δθ = (d_R − d_L) / L

The pose is accumulated from Δs and Δθ. In the simulation r = 0.033 m and L = 0.268 m. [TBD: the physical robot's counts per revolution and track width. The wheel-encoder interface is not documented in the repository; the Arduino firmware contains no encoder code.]

**Process stage.** The following modules are designed to run in parallel on the Jetson Orin Nano. Only object detection has been benchmarked on the Jetson (Section 6.3); the navigation modules were evaluated in simulation on a laptop (Section 7).
- **Mapping.** RTAB-Map builds a 2D occupancy grid from the depth camera and wheel odometry (Section 5.1).
- **Planning and navigation.** The Nav2 stack provides path planning (a Smac Hybrid-A* global planner, Section 5.2), path following (an MPPI controller) and obstacle avoidance with a camera-derived obstacle layer (Section 5.3).
- **Object detection.** A YOLO model takes the RGB stream and outputs bounding boxes (Section 4).
- **Decision.** The decision module turns a stable detection into a command for the Arduino Uno (Section 5.4). Fusing detections with navigation state, operating mode and obstacle information is the intended design and is not yet implemented.

**Act stage.** The Arduino Uno executes the command. This separates responsibilities and keeps the Jetson away from the actuator electronics. The commands are short text messages, for example `MOVE:FORWARD`, `MOVE:LEFT`, `MOVE:STOP`, `SPEED:<value>`, `VACUUM:ON`, `ARM:ON` and `ESTOP`. The firmware moves the robot until it receives a stop command, so distance and angle must be controlled by the Jetson from odometry.

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

## 5.4 Decision Module

The Decision Module converts perception output into commands for the Arduino Uno, which drives the actuators over a serial link at 115200 baud.

**What the vision prototype implements** (`Object Detection/Camera/vision`):
- **Detection gating.** The detector confidence threshold is 0.50. The same class must be the top detection in N = 2 consecutive frames, and the top detection's confidence must be at least 0.55 before a command is sent. This suppresses single-frame false positives.
- **Target position.** Depth comes from the disparity of a calibrated stereo pair of USB cameras. The median of the valid (positive) disparity values in an 11 × 11 pixel window at the centre of the bounding box is converted to X, Y and Z. When no stereo depth is available (no calibration, or no valid disparity in the window), Z is estimated from the bounding-box height assuming a 12 cm object, and X and Y are sent as `?`.
- **Command.** A stable detection produces `ARM:PICK:<class>,<X>,<Y>,<Z>,<confidence>`. A function for `ARM:NO_TARGET` exists, but the main loop never calls it, so nothing is sent when nothing is detected. Any stable detection among the configured classes triggers the command, regardless of operating mode.
- [TBD: the prototype's allowed classes are generic object classes used as stand-ins (bottle, cup and so on), and its model file is a generic detector rather than the trained eight-class model of Section 4. Confirm which model and classes the deployed system uses.]

**What the Arduino firmware implements:** movement (`MOVE:FORWARD`, `BACKWARD`, `LEFT`, `RIGHT`, `STOP`), `SPEED`, `VACUUM`, `ARM:ON`/`OFF`, `WIPER`, `UV`, `AUTO:ON`/`OFF`, `AI:ON`/`OFF` (acknowledged only) and an emergency stop. `ESTOP` switches all actuators off and refuses further commands (`ERR:EMERGENCY_STOP_ACTIVE`) until `RESET`. The firmware does not implement `ARM:PICK`; it answers `ERR:UNKNOWN_CMD:<command>`.

**Intended design (not implemented in the repository).** The full decision module is meant to fuse the detected class, the operating mode, an obstacle flag and the navigation state (pose, map, current goal) into one action per cycle, as in Table 5 below. In manual mode only operator commands would be forwarded; in semi-automatic mode fusion would run only in an operator-selected area; in automatic mode exploration would resume after each action. An emergency stop from the HMI or by voice would override every decision. The repository contains no HMI or voice-command code for this, so these behaviours are not evidenced.

**Table 5 (intended decision table; design only):**

| Detected class | Mode | is_obstacle | Action |
|---|---|---|---|
| bottle, plastic wrapper, paper, aluminium foil | Auto | No | Pause navigation; activate robotic arm (pick) |
| cement dust, wooden dust | Auto | No | Activate vacuum; continue path |
| obstacle | Auto | Yes | Mark obstacle; replan path |
| floor | Any | No | No action (background class) |
| any | Manual | n/a | Execute operator command only |
| any | Any (E-stop) | n/a | Stop all actuators until reset |

[TBD: confirm with the hardware team whether the arm firmware exists elsewhere, and whether the vacuum action for the dust classes and the pausing of Nav2 during a pick are implemented.]

## 7.3 SLAM and Navigation Performance

All results in this section come from the Gazebo simulation described in Section 7.1 and are on the held-out test worlds. The tables below are generated from the per-episode result files by a script, and are reproduced in the appendix.

**Exploration and SLAM.** Across 9 valid exploration episodes (three worlds, three seeds each), the robot explored 61.4 % of the reachable floor area on average (95 % bootstrap interval 18.5 to 88.0 %). The result depended strongly on the world: 86.3 % in multi_room_loop, 83.8 % in office and 14.3 % in maze_dead_ends. In the maze, the explorer sent no goal in 2 of 3 episodes, and the robot ended those episodes stuck near its start with only a small fraction of the area mapped. The cause was traced to the explorer (docs/EVALUATION_FINDINGS_2026-10-25.md, section 4): the start-up rotation stops once the first map arrives, leaving the robot facing a wall 0.5 to 0.75 m away with a very small first map; the goal-snapping step treats unknown cells as blocked, so no cell met the 0.30 m clearance requirement, the only frontier was blacklisted, and the explorer has no fallback.

The mean map completeness against the ground-truth grid was 47.7 % (interval 15.1 to 70.6 %). The SLAM trajectory error (absolute trajectory error against ground truth, no scale correction) was 0.57 m (interval 0.33 to 0.86 m, from 7 episodes with a defined value), and the relative error was 0.25 m per metre travelled.

**Contact corrupts odometry.** The robot's wheel odometry was corrupted by contact with obstacles in 4 of 9 exploration episodes: wheel slip during contact changed the heading estimate and RTAB-Map did not recover from it. Excluding those episodes, the trajectory error was 0.44 m (3 episodes). The error measured before the first corruption was 0.33 m. Odometry noise was injected in this campaign: a persistent per-episode scale error (standard deviations of 2 % linear and 3 % angular) plus random-walk drift that grows with the distance travelled and the angle turned.

**Loop closure.** A loop closure counts as correct when its relative transform matches ground truth within 0.10 m and 5°. By closures, 35.2 % of the 1051 accepted closures were correct; the mean of the per-episode precision was 36.8 % (interval 19.9 to 94.3 %, 7 episodes). Recall averaged 28.2 %, where a revisit is a return to within 0.30 m and 30° of an earlier pose at least 30 s later. The precision figure is a lower bound, because of a timing bias in matching closures to ground truth (docs/EVALUATION_FINDINGS_2026-10-25.md).

**Collisions.** The robot made 1.8 contact events per exploration episode on average. One continuous contact can count as several events.

**Navigation.** The navigation campaign measures Nav2 with AMCL localisation on a ground-truth map, not the RTAB-Map pipeline. Over 12 episodes and 178 goals, Nav2 reported 50.0 % of goals reached (89 of 178). Checked against ground truth (the robot within 0.30 m of the goal), 29.2 % were reached (52 of 178 goals, interval 16.0 to 40.0 %). Averaged over episodes, as in the pre-registered analysis, the ground-truth success rate was 23.4 % (interval 2.8 to 46.7 %, two-stage bootstrap over worlds then seeds). With the stricter 0.15 m threshold, 9.0 % of goals were reached. By world, ground-truth success was 48.8 % in two_rooms_door, 20.7 % in office and 2.5 % in maze_dead_ends. The mean path-length ratio of successful goals was 1.21, and 7 of 12 episodes ended because the robot was judged stuck before all goals were tried. The robot ran 148 recovery behaviours per episode on average.

**Why navigation succeeds so rarely.** The dominant planner failure was Nav2 error 205 (start occupied): the planner refused plans because the robot's estimated pose, which is always the planner's start, placed its footprint within the inscribed zone of a wall. In the two office episodes analysed, the estimate collided in almost every such event while the true pose almost never did. Across the analysed events, about a third were caused by localisation error and about 60 % by the robot genuinely having ended up within footprint range of a wall, where the stack has no recovery that moves it away (docs/EVALUATION_FINDINGS_2026-10-25.md and docs/EXECUTION_LOG.md; the shares count planner log lines, which include repeated retries from a few stuck poses per episode, so the events are not independent). A diagnostic on a development world supports a localisation contribution: with AMCL localisation, 6 of 19 goals were reached according to ground truth, whereas with ground-truth localisation 19 of 20 were reached with the same planner. This is one episode per setting and is evidence, not proof. A variant that backs up 0.15 m and spins on this error and uses more AMCL particles with tighter update thresholds was tested on one development world (apartment, two seeds, one episode per arm and seed). It did not meet its pre-fixed rule (the number of start-occupied failures fell only to 95 % of the baseline, against a required 60 % or less), so it was not run on the test worlds.

**Simulation conditions.** The measured real-time factor was 0.73 to 1.00 over all test episodes, and 0.73 to 1.00 in the exploration campaign; the lower values (0.73 to 0.75) are from the office and multi_room_loop exploration episodes, which ran three at a time on an 8-core, 16-thread laptop, while the maze episodes ran two at a time at about 1.0.

## 7.4 Obstacle Avoidance Performance

Avoidance was tested in two scenarios with 6 valid episodes in total (three seeds each). A trial counts as successful only if the robot reaches the goal without any contact.

- **avoid_u_trap** (a static U-shaped trap): 3 of 3 trials succeeded.
- **avoid_dynamic_sudden** (a box emerging from behind a wall at 0.5 m/s): 1 of 3 trials succeeded.
- **Pooled:** 4 of 6 trials (66.7 %, Wilson interval 30.0 to 90.3 %). The goal was reached in 5 of 6 trials, and 1 contact event(s) occurred in total.
- **Clearance.** The minimum distance to an obstacle averaged 0.159 m. This is slightly optimistic, because the wheels protrude about 2 cm beyond the footprint.

With three trials per scenario the intervals are wide, and the result shows only that the static trap was handled and the dynamic obstacle was not reliably avoided. During exploration and navigation, the robot also touched obstacles, which Section 7.3 reports.

**Responsiveness.** With the SLAM stack running and the explorer disabled, the wall-clock step-response time (from a velocity command until the robot reaches 50 % of the commanded velocity) was 166 ms on average (95th percentile 206 ms), and the corresponding stop response time was 260 ms (301 ms at the 95th percentile), from 2 episodes. Both are below 0.5 s. The step response mostly reflects the configured acceleration ramp plus about 45 ms of pipeline delay. The runs without the SLAM stack (2 episodes) are marked invalid by the validity rules, which require RTAB-Map updates; they are excluded by that rule, not because of a problem in the measurement.

---

## Appendix: generated tables

Means are over valid episodes (status ok or partial). Brackets are 95 percent bootstrap intervals over episodes (5000 resamples, seed 12345) from the repository helpers. "n" is the number of episodes with a value for that metric.

## Table 8. SLAM and exploration (exploration campaign)

| World | Valid / run | Reachable m2 | Coverage (%) | Map completeness (%) | ATE (m) | RPE (m per m) | Loop-closure precision (by closures) | Loop-closure precision (per-episode mean) | Loop-closure recall (%) | Collisions per ep. | Odometry corrupted by contact |
|---|---|---|---|---|---|---|---|---|---|---|---|
| maze_dead_ends | 3 / 3 | 33.3 | 14.3 [1.2, 39.9] (n=3) | 11.9 [1.7, 31.8] (n=3) | 0.76 (n=1) | 0.30 (n=1) | 94.3% [94.3, 94.3] (133 of 141), from 1 episodes | 94.3 (n=1) | 13.3 [0.0, 40.0] (n=3) | 0.7 [0.0, 2.0] (n=3) | 1 of 3 |
| multi_room_loop | 3 / 3 | 39.1 | 86.3 [82.6, 88.6] (n=3) | 65.4 [59.2, 68.9] (n=3) | 0.74 [0.40, 0.97] (n=3) | 0.35 [0.12, 0.67] (n=3) | 24.9% [8.7, 52.4] (112 of 450), from 3 episodes | 25.9 [8.7, 52.4] (n=3) | 30.3 [22.2, 40.0] (n=3) | 3.7 [0.0, 6.0] (n=3) | 2 of 3 |
| office | 3 / 3 | 34.0 | 83.8 [71.5, 91.6] (n=3) | 65.9 [45.9, 78.0] (n=3) | 0.35 [0.13, 0.51] (n=3) | 0.13 [0.11, 0.15] (n=3) | 27.2% [20.0, 38.8] (125 of 460), from 3 episodes | 28.5 [20.0, 38.8] (n=3) | 41.0 [38.5, 42.9] (n=3) | 1.0 [0.0, 2.0] (n=3) | 1 of 3 |
| pooled | 9 / 9 |  | 61.4 [18.5, 88.0] (n=9) | 47.7 [15.1, 70.6] (n=9) | 0.57 [0.33, 0.86] (n=7) | 0.25 [0.14, 0.44] (n=7) | 35.2% [17.9, 58.6] (370 of 1051), from 7 episodes | 36.8 [19.9, 94.3] (n=7) | 28.2 [12.6, 40.9] (n=9) | 1.8 [0.4, 3.9] (n=9) | 4 of 9 |

ATE with and without episodes whose odometry was corrupted by contact:

| World | ATE all valid (m) | ATE excluding corrupted (m) | ATE before first corruption (m) |
|---|---|---|---|
| maze_dead_ends | 0.76 (n=1) | n/a (n=0) | 0.17 (n=1) |
| multi_room_loop | 0.74 [0.40, 0.97] (n=3) | 0.40 (n=1) | 0.38 [0.14, 0.59] (n=3) |
| office | 0.35 [0.13, 0.51] (n=3) | 0.46 [0.40, 0.51] (n=2) | 0.34 [0.11, 0.51] (n=3) |
| pooled | 0.57 [0.33, 0.86] (n=7) | 0.44 [0.40, 0.51] (n=3) | 0.33 [0.17, 0.46] (n=7) |

Per-episode exploration detail:

| World | Seed | Goals sent | Coverage (%) | Ended | Collisions | Odometry corrupted | RTF |
|---|---|---|---|---|---|---|---|
| maze_dead_ends | 101 | 0 | 1.8 | stuck | 0 | 0 | 0.999 |
| maze_dead_ends | 102 | 18 | 39.9 | timeout | 2 | 1 | 1.000 |
| maze_dead_ends | 103 | 0 | 1.2 | stuck | 0 | 0 | 1.000 |
| multi_room_loop | 101 | 22 | 82.6 | timeout | 5 | 1 | 0.738 |
| multi_room_loop | 102 | 18 | 87.6 | timeout | 0 | 0 | 0.740 |
| multi_room_loop | 103 | 15 | 88.6 | timeout | 6 | 1 | 0.750 |
| office | 101 | 16 | 91.6 | timeout | 2 | 1 | 0.753 |
| office | 102 | 22 | 88.2 | timeout | 0 | 0 | 0.737 |
| office | 103 | 19 | 71.5 | timeout | 1 | 0 | 0.729 |

Episodes in which the explorer sent no goal: maze_dead_ends 2 of 3, multi_room_loop 0 of 3, office 0 of 3, pooled 2 of 9

## Table 8b. Navigation (Nav2 with AMCL on a ground-truth map)

Two definitions are shown. "By goals" pools all goals (successes divided by goals, 95 percent interval from an episode-level bootstrap). "Per-episode mean" is the unweighted mean of the per-episode percentages; its pooled row uses the pre-registered two-stage bootstrap (worlds, then seeds), as in the campaign reports.

| World | Valid / run | Goals | Nav2-reported (by goals) | GT-verified, 0.30 m (by goals) | GT-verified, 0.30 m (per-episode mean) | Strict 0.15 m (by goals) | Path-length ratio | Recoveries per ep. | Collisions per ep. | Ended stuck |
|---|---|---|---|---|---|---|---|---|---|---|
| maze_dead_ends | 4 / 4 | 40 | 2.5% [0.0, 8.3] (1 of 40) | 2.5% [0.0, 8.3] (1 of 40) | 2.8 [0.0, 8.3] (n=4) | 2.5% [0.0, 8.3] (1 of 40) | 1.09 (n=1) | 167.5 [136.5, 221.8] (n=4) | 3.0 [0.0, 6.0] (n=4) | 4 of 4 |
| office | 4 / 4 | 58 | 37.9% [26.1, 47.2] (22 of 58) | 20.7% [8.7, 25.0] (12 of 58) | 18.8 [6.2, 25.0] (n=4) | 1.7% [0.0, 5.0] (1 of 58) | 1.19 [1.15, 1.23] (n=4) | 167.2 [146.0, 188.5] (n=4) | 0.8 [0.0, 2.2] (n=4) | 3 of 4 |
| two_rooms_door | 4 / 4 | 80 | 82.5% [68.8, 95.0] (66 of 80) | 48.8% [40.0, 58.8] (39 of 80) | 48.8 [40.0, 58.8] (n=4) | 17.5% [12.5, 22.5] (14 of 80) | 1.26 [1.18, 1.34] (n=4) | 108.0 [65.0, 151.0] (n=4) | 2.0 [2.0, 2.0] (n=4) | 0 of 4 |
| pooled | 12 / 12 | 178 | 50.0% [28.1, 67.8] (89 of 178) | 29.2% [16.0, 40.0] (52 of 178) | 23.4 [2.8, 46.7] (n=12) | 9.0% [3.3, 14.1] (16 of 178) | 1.21 [1.09, 1.27] (n=9) | 147.6 [107.0, 183.6] (n=12) | 1.9 [0.5, 3.7] (n=12) | 7 of 12 |

Per-episode detail (goals, Nav2-reported successes, GT-verified successes, end reason):

| World | Seed | Goals | Nav2 success | GT-verified | Ended |
|---|---|---|---|---|---|
| maze_dead_ends | 101 | 9 | 1 | 1 | stuck |
| maze_dead_ends | 102 | 9 | 0 | 0 | stuck |
| maze_dead_ends | 103 | 8 | 0 | 0 | stuck |
| maze_dead_ends | 104 | 14 | 0 | 0 | stuck |
| office | 101 | 10 | 2 | 0 | stuck |
| office | 102 | 12 | 4 | 3 | stuck |
| office | 103 | 20 | 10 | 5 | goals_done |
| office | 104 | 16 | 6 | 4 | stuck |
| two_rooms_door | 101 | 20 | 16 | 10 | goals_done |
| two_rooms_door | 102 | 20 | 19 | 8 | goals_done |
| two_rooms_door | 103 | 20 | 12 | 8 | goals_done |
| two_rooms_door | 104 | 20 | 19 | 13 | goals_done |

Localisation diagnostic (development world apartment, seed 1; not part of the test results):

| Localisation | Goals | Nav2-reported successes | GT-verified successes | GT-verified (%) |
|---|---|---|---|---|
| amcl | 19 | 14 | 6 | 31.6 |
| gt_localization | 20 | 19 | 19 | 95.0 |

## Table 9. Obstacle avoidance

| Scenario | Valid / run | Trials reaching goal without contact | Goal reached | Contact events (total) | Minimum clearance (m) |
|---|---|---|---|---|---|
| avoid_dynamic_sudden | 3 / 3 | 33.3% (1 of 3), Wilson [6.1, 79.2] | 2 of 3 | 1 | 0.165 [0.000, 0.290] (n=3) |
| avoid_u_trap | 3 / 3 | 100.0% (3 of 3), Wilson [43.8, 100.0] | 3 of 3 | 0 | 0.152 [0.149, 0.156] (n=3) |
| pooled | 6 / 6 | 66.7% (4 of 6), Wilson [30.0, 90.3] | 5 of 6 | 1 | 0.159 [0.084, 0.222] (n=6) |

## Table 10. Responsiveness (wall-clock, office)

| Stack | Valid / run | Command to motion mean (ms) | Stop mean (ms) | Command P95 (ms) | Stop P95 (ms) |
|---|---|---|---|---|---|
| responsiveness_bare | 0 / 2 | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) |
| responsiveness_loaded | 2 / 2 | 166.1 [160.4, 171.7] (n=2) | 260.0 [249.7, 270.4] (n=2) | 205.7 [189.2, 222.2] (n=2) | 300.8 [285.4, 316.3] (n=2) |

## Real-time factor and validity

| Campaign | Episodes with RTF | Min | Max | Mean |
|---|---|---|---|---|
| exploration | 9 | 0.729 | 1.000 | 0.827 |
| navigation | 12 | 0.999 | 1.000 | 1.000 |
| avoidance | 6 | 0.804 | 1.000 | 0.911 |
| responsiveness | 4 | 0.926 | 1.000 | 0.972 |
| all | 31 | 0.729 | 1.000 | 0.929 |

| Campaign | Status counts |
|---|---|
| exploration | ok: 9 |
| navigation | ok: 12 |
| avoidance | ok: 6 |
| responsiveness | invalid: 2, ok: 2 |

## Cross-check against the repository aggregate.csv

- exploration: compared 637 per-world means; mismatches: 0
- navigation: compared 571 per-world means; mismatches: 0
- avoidance: compared 376 per-world means; mismatches: 0
- responsiveness: compared 200 per-world means; mismatches: 0
