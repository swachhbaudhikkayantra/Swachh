# Fill-in text for `rp_draft_project_sby (2).pdf`

**Audience:** the authors of the Swachh Bauddhika Yantra paper (Veena N Hegde et al.).
**Contents:** text for the requested sections, ready to paste. Simulation-campaign results that don't exist yet are marked **[TBD: …]**. The last section lists the errors and inconsistencies found in the whole draft (20 pages).

Sources:
- the draft PDF itself;
- the repository implementation: `Navigation/Simulation/vacuum_ws` (RTAB-Map, Nav2 and explorer configuration) and `Object Detection/Camera/vision` (decision and serial logic);
- `docs/PROJECT_CONTEXT.md` (Jetson benchmarks);
- the simulation evaluation framework (`docs/specs/`, `docs/METRICS_STATUS.md`).

> **Key caveat before using sections 5 and 7.** All navigation results come from the **Gazebo simulation**. The simulated robot is a **0.30 × 0.25 m** differential-drive base carrying only a D435i. The physical robot in §3.2–3.3 is about **0.60 × 0.50 m and 50 kg**, and also carries a C270 webcam and a robotic arm. No navigation experiment has run on the physical robot yet. The text below says so explicitly; keep that wording, or a reviewer will flag it.

---

## 3.2 Robot Physical and System Specifications (description text)

*Place this paragraph above Table 1. Table 1 itself needs the corrections listed in §E1 before submission.*

The Swachh Bauddhika Yantra is built on a three-tier rectangular metal chassis, about 60 cm long and 50 cm wide. Locomotion is a rear-wheel differential drive using two 6-inch brushless DC (BLDC) hub motors, each driven by a 24 V sine-wave controller, with a passive 360° caster wheel at the front. The drive wheels carry about 20 kg each and the caster about 10 kg, for a total payload capacity of 50 kg. The robot is powered by a 24 V, 26 Ah lead-acid battery pack (two 12 V batteries in series), which gives about 2 h of operation per charge and is recharged from a 230 V, 50 Hz mains supply. DC–DC buck converters derive the regulated supply rails for the individual components.

High-level computation runs on an NVIDIA Jetson Orin Nano (JetPack 6.1: L4T R36.4, CUDA 12.6, TensorRT 10.3). Object detection has been benchmarked on this device (Section 6.3). The navigation stack was evaluated in simulation on a workstation and has not yet been deployed on the Jetson. Low-level actuation is delegated to an Arduino Uno microcontroller over a serial link. Perception relies only on cameras: an Intel RealSense D435i RGB-D camera for mapping, localisation and obstacle sensing, and a Logitech C270 RGB webcam for trash detection, both streaming at 30 FPS. Wheel encoders provide odometry. Table 1 summarises the physical and system specifications.

---

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

## 4.2 Dataset Accessibility (replacement text: "Reference: small set of images on GitHub")

A representative subset of the dataset, with sample images from every class, is publicly available at **https://github.com/manaswi-siripurapu/sby** so that readers can inspect the acquisition conditions (low camera height, 30° downward tilt, laboratory floor backgrounds). The complete annotated dataset of 873 images in YOLO and COCO formats is available from the corresponding author on reasonable request.

*If the GitHub repository should carry a fixed sample size, state it (for example "20 images per class"). [TBD: confirm what is uploaded.]*

---

## 4.4 Augmentation (table to add)

**The PPT you mentioned was not found** anywhere on this machine, under `~/Swachh` or `C:\Users\DELL\{Downloads,Desktop,Documents}`. The table below is therefore **reconstructed from the text of §4.4**. Compare it with the PPT table, and replace any values that differ.

**Table X. Data augmentation applied to the training set.** Each transform was applied independently with probability 0.5, and transforms could combine on one image.

| Augmentation | Parameter | Probability | Purpose (deployment condition simulated) |
|---|---|---|---|
| Horizontal flip | — | 0.5 | Left/right symmetry of objects relative to the robot |
| Vertical flip | — | 0.5 | Arbitrary object orientation on the floor |
| Random rotation | ±15° | 0.5 | Chassis tilt and camera-mount vibration |
| Random crop | [TBD: crop range from PPT] | 0.5 | Partially visible objects at the frame border |
| Brightness adjustment | ±30 % | 0.5 | Normal vs. low-light indoor environments |
| Contrast adjustment | ±30 % | 0.5 | Lighting and surface-reflectance variation |
| Motion blur | 5 × 5 kernel | 0.5 | Image degradation while the robot is moving |
| **Result** | Training set expanded 3× | — | Validation and test sets **not** augmented |

**Fix the count sentence before adding the table** (see §E3). "Expanded three times, which gave 2619 augmented images" doesn't match: 2619 = 3 × 873, the *whole* dataset, but augmentation was applied only to the 611 training images. 611 × 3 = 1,833 training images (or 2,444 if the 611 originals are kept alongside three augmented copies).

---

## 4.6 Figures 4 and 5 (to drop)

To **drop Figure 4** (YOLOv8s architecture) and **Figure 5** (RF-DETR architecture):
- Delete both figure environments and captions.
- In §4.6.1, delete the sentence *"The overall YOLOv8s architecture used in this work is shown in Fig. 4."*
- Figure 5 has no in-text reference, so nothing else changes.
- Renumber any later figures. Check the figure counter too: the extracted text shows Figure 1 and Figure 3 but no Figure 2 caption, so Figure 2 may exist only as an image without a caption. Confirm it.
- Optional replacement sentences so the architecture descriptions still point somewhere:
  - §4.6.1 end: *"A detailed architecture diagram of YOLOv8 is given in [ref 68]."*
  - §4.6.2 end: *"The full architecture is described in [ref 70]."*

---

## 5 Navigation and Path Planning

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

### 5.4 Decision Module

The Decision Module fuses the outputs of perception (trash and obstacle detection) and navigation (pose, map, current goal) with the operating mode. It produces one high-level action per decision cycle and sends it to the Arduino Uno as an ASCII command over the 115200-baud serial link (Section 3.4).

**Detection gating:** a detection becomes actionable only after the same class has been seen in **N consecutive frames** (N = 2 in the current configuration) with confidence of at least 0.55. The detector's own threshold is 0.50. This suppresses single-frame false positives.

**Target localisation:** the object's 3D position in the camera frame is obtained by sampling the depth map at the centre of its bounding box. It is sent with the class and confidence so the arm can plan the pick (command `ARM:PICK:<class>,<X>,<Y>,<Z>,<confidence>`). When nothing is actionable, `ARM:NO_TARGET` is sent.

**Fusion logic:** Table 5 maps (detected class, mode, obstacle flag) to an action:
- **Pickable trash** (bottle, plastic wrapper, paper, aluminium foil) in automatic mode pauses navigation and activates the robotic arm.
- **Dust classes** (cement dust, wooden dust) activate the vacuum and continue along the path. *(Rows missing from Table 5; see §E5.)*
- The **obstacle** class sets the obstacle flag and triggers replanning.
- The **floor** class is a background class, used for floor-state context. It doesn't trigger an action.

**Mode handling:**
- **Manual mode:** the Decision Module forwards only operator commands from the HMI.
- **Semi-automatic mode:** fusion runs only inside the operator-selected area and task type.
- **Automatic mode:** the full fusion loop runs, and exploration resumes after each action completes.

An emergency stop (HMI button or the spoken command "STOP") overrides every decision. It latches until it is explicitly reset.

**Revised Table 5 (suggested; adds the missing classes):**

| Detected class | Mode | is_obstacle | Action |
|---|---|---|---|
| bottle | Auto | No | Pause navigation; activate robotic arm (pick) |
| plastic (wrapper) | Auto | No | Pause navigation; activate robotic arm (pick) |
| paper | Auto | No | Pause navigation; activate robotic arm (pick) |
| aluminium foil | Auto | No | Pause navigation; activate robotic arm (pick) |
| cement dust | Auto | No | Activate vacuum; continue path |
| wooden dust | Auto | No | Activate vacuum; continue path |
| obstacle | Auto | Yes | Mark obstacle; replan path |
| floor | Any | No | No action (background class) |
| any | Manual | — | Execute operator command only |
| any | Any (E-stop) | — | Stop all actuators until reset |

*Implementation status, to state honestly or fix before submission:* the Arduino firmware in the repository does not yet implement the `ARM:PICK` command; it answers `ERR:UNKNOWN_CMD`. The vacuum action for dust classes, and the coupling of detection with Nav2 pausing, are not yet implemented in code. [TBD: confirm with the hardware team which parts are implemented.]

---

## 6.3 Edge Deployment Optimisation

All perception runs on board the **NVIDIA Jetson Orin Nano**:
- L4T R36.4 (JetPack 6.1), CUDA 12.6, TensorRT 10.3.0.
- **Robot:** the camera is connected directly to the Jetson (Scenario A).
- **Comparison configuration:** the camera stream is sent wirelessly from a Raspberry Pi (Scenario B).

To meet the real-time budget of 33 ms per frame (30 FPS), the trained detectors were exported to ONNX and compiled into TensorRT engines at reduced precision (FP16 and INT8). They were compared against an FP32 ONNX Runtime baseline on the CPU.

**Table X. On-device inference on the Jetson Orin Nano** (Scenario A, direct camera, 3 trials × 150 frames per model):

| Model | Precision / backend | Inference latency (ms, mean ± SD) | P95 (ms) | Throughput (FPS) | Power (W) | Efficiency (FPS/W) |
|---|---|---|---|---|---|---|
| YOLOv8 | FP32 / ONNX Runtime (CPU) | 187.56 ± 45.47 | 269.37 | 5.3 | 10.51 | 0.50 |
| YOLOv8 | FP16 / TensorRT (GPU) | 15.03 ± 2.81 | 18.24 | 66.5 | 9.18 | 7.24 |
| YOLOv8 | INT8 / TensorRT (GPU) | **12.89 ± 2.75** | **17.38** | **77.6** | **8.30** | **9.35** |
| YOLOv11 | FP32 / ONNX Runtime (CPU) | 186.38 ± 38.23 | 262.38 | 5.4 | 10.60 | 0.51 |
| YOLOv11 | FP16 / TensorRT (GPU) | 17.10 ± 2.68 | 23.35 | 58.5 | 9.20 | 6.36 |
| RF-DETR | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |

**Text:**

On the Jetson, both YOLO models meet the 33 ms budget only after TensorRT compilation. YOLOv8 at INT8 reaches 12.9 ms per frame (77.6 FPS) at 8.3 W, which leaves more than half of each 33 ms frame period for SLAM and planning, which share the same device. FP16 gives 66.5 FPS for YOLOv8 and 58.5 FPS for YOLOv11.

INT8 compilation of the YOLOv11 segmentation variant failed on TensorRT 10.3.0 because of missing INT8 kernels for its prototype mask head. Only FP16 is reported for YOLOv11.

When frames are streamed over Wi-Fi from the Raspberry Pi (Scenario B), network transit (about 6.6 ms) and JPEG decompression (5.2–8.8 ms) add about 15 ms per frame. That caps end-to-end throughput at about 31.7 FPS, even with INT8 inference. This supports the on-board design choice (Section 2.5).

**Wording caveats (these are critic findings; keep the claims within them):**
- The FP32 baseline runs on the **CPU** with ONNX Runtime, while the reduced-precision engines run on the **GPU** with TensorRT. The 12–15× speed-ups therefore mix backend and precision effects. Describe them as "TensorRT FP16/INT8 vs. a CPU FP32 baseline", not as "quantisation gains". If possible, add a TensorRT FP32 row. [TBD]
- The INT8 engine was calibrated with **random-noise inputs**, and its detection accuracy (mAP) was not measured. Report INT8 mAP on the test set before claiming INT8 for deployment. [TBD: re-calibrate with ~300 real training images and report mAP.]
- The engine sizes previously quoted (8.6 MB / 4.8 MB) do not match the benchmark CSV, which reports the ONNX size (about 11.98 MB) for every precision. Measure the `.engine` file sizes, or drop the size column. [TBD]

---

## 7 Experimental Results

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

### 7.3 SLAM Navigation Performance

*Replace the current Table 8 (lab, lab corridor, low-light area: real environments not tested yet) with the simulation table below. Or keep both, with the real-environment rows marked as future work.*

**Table 8. SLAM and exploration performance in simulated test environments** (mean ± SD over episodes; [95 % CI]):

| Environment | Reachable area (m²) | Coverage (%) | Map completeness (%) | ATE (m) | RPE (m/m) | Loop closures (accepted / precision %) | Tracking gaps (count) |
|---|---|---|---|---|---|---|---|
| office | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |
| multi_room_loop | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |
| maze_dead_ends | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |
| **Pooled** | — | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |

**Table 8b. Navigation performance** (20 random goals per episode):

| Environment | Goals | Nav success, GT-verified (%) | Strict success, ≤0.15 m (%) | Path-length ratio | Recoveries per goal |
|---|---|---|---|---|---|
| office | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |
| two_rooms_door | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |
| maze_dead_ends | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |
| **Pooled** | [TBD] | [TBD] [CI] | [TBD] | [TBD] | [TBD] |

**Text (fill in the numbers):**

Across [TBD] valid exploration episodes ([TBD] invalid, excluded and reported), the robot explored [TBD] % (95 % CI [TBD]) of the reachable floor area within [TBD] s. The resulting maps reached [TBD] % completeness against the ground-truth floor plans.

With injected odometry noise, the SLAM trajectory error (ATE [TBD] m) was [TBD] % lower than that of wheel odometry alone ([TBD] m). This shows that RTAB-Map's visual loop closures compensate odometry drift. [TBD] loop closures were accepted per episode on average; [TBD] % had a geometrically correct relative transform.

**Localisation ablation:** in development experiments, we ran the same navigation task with perfect (ground-truth) localisation, AMCL on a known map, and SLAM. Goal success was [TBD] / [TBD] / [TBD] %. That attributes [TBD]% of navigation failures to localisation and the rest to planning and control.

**Failure-mode finding (development, keep as qualitative evidence):** in one development episode the robot struck a chair that had decayed from the obstacle layer. The recovery behaviour then rotated the robot in place while it was in contact. The resulting wheel slip corrupted odometry heading by about 125°, RTAB-Map did not recover, and ATE grew from 0.12 m (before contact) to 3.1 m. Reordering the recovery behaviour (back up before rotating) and adding the SLAM map as a static layer to the local costmap addressed this. Episodes in which contact still corrupted odometry are flagged, and ATE is reported both with and without them: [TBD].

### 7.4 Obstacle Avoidance Performance

**Table X. Obstacle avoidance** (contact sensors on chassis and camera; encounter = robot within 0.5 m of an obstacle):

| Scenario | Trials / episodes | Collisions (total) | Collision-free encounters (%) | Trial success, goal reached with no contact (%) | Min. clearance (m) |
|---|---|---|---|---|---|
| avoid_u_trap (static, concave) | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |
| avoid_dynamic_sudden (moving obstacle) | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |
| Exploration episodes (cluttered test worlds) | [TBD] | [TBD] | [TBD] | — | [TBD] |
| **Pooled** | [TBD] | [TBD] | [TBD] [CI] | [TBD] [CI] | — |

**Text:**

In the static concave-trap scenario, the robot reached the goal without contact in [TBD] of [TBD] trials. In the dynamic scenario, an obstacle emerges from behind a wall into the robot's path at 0.5 m/s, and trial success was [TBD] %. Across all exploration and navigation episodes, [TBD] collisions occurred in [TBD] obstacle encounters, a collision-free encounter rate of [TBD] % (95 % CI [TBD]). The closest approach to an obstacle was [TBD] m.

Collisions concentrated in [TBD: e.g. rotations near furniture / obstacles inside the 0.2 m depth blind zone]. That points to the camera-only sensing limit discussed in Section 5.3.

**Responsiveness** (wall clock, real-time stack): command-to-motion latency was [TBD] ms (P95 [TBD] ms) and stop latency [TBD] ms (P95 [TBD] ms). [TBD] % of events met the 0.5 s deadline, unloaded vs. with the full SLAM and navigation stack running.

---

## 9 Conclusion and Future Work

This paper presented Swachh Bauddhika Yantra, an autonomous indoor cleaning robot that combines camera-only navigation, deep-learning trash detection and a robotic arm for waste collection on a single on-board edge computer.

**Trash detection:** a custom dataset of 873 images with 6,349 instance annotations across eight action-oriented classes supported three detectors. YOLOv8, YOLOv11 and RF-DETR reached mAP@0.5 of 92.09 %, 92.48 % and [TBD: RF-DETR value after the Table 6/7 check, §E4] on the test set. With TensorRT, YOLOv8 runs at 77.6 FPS (INT8) on the Jetson Orin Nano at 8.3 W, comfortably inside the 30 FPS real-time budget.

**Navigation:** RTAB-Map RGB-D SLAM, frontier exploration and the Nav2 Hybrid-A*/MPPI stack were evaluated in simulation with a pre-registered protocol, held-out test environments and validity checks.
- The robot explored [TBD] % of the reachable area.
- SLAM reduced trajectory error by [TBD] % relative to wheel odometry.
- [TBD] % of navigation goals were reached, verified against ground truth.
- [TBD] % of obstacle encounters were collision-free.

The evaluation also exposed two failure modes: contact-induced odometry corruption that SLAM couldn't recover from, and objects closer than the camera's 0.2 m minimum range. Both are reported, not hidden.

**Limitations:**
- **Simulation only:** navigation was evaluated in simulation, with a simulated base smaller than the physical robot.
- **Partial integration:** the decision-to-actuation chain (arm pick command, dust-to-vacuum action) is only partly implemented in firmware.
- **INT8 accuracy:** the INT8 model has not yet been evaluated for accuracy.
- **Camera blind zone:** camera-only sensing can't see obstacles inside 0.2 m.

**Future work:**
1. **Hardware validation:** port the navigation stack to the physical platform and repeat the experiments in real lab, corridor and low-light environments (Table 8).
2. **Model fidelity:** align the simulation model with the real robot's dimensions, drive geometry and camera placement, including the axle-to-base offset.
3. **Coverage planning:** add a dedicated coverage planner (e.g. boustrophedon) after exploration, so the robot cleans the whole floor and not just maps it, and compare against classical and learning-based planners.
4. **Recovery behaviour:** make recovery contact-aware, and add a low-cost bumper to cover the depth blind zone.
5. **INT8 calibration:** calibrate INT8 on real images, and report accuracy alongside latency for every deployed precision.
6. **Closing the loop:** complete the closed loop from detection through decision to arm pick and vacuum on the robot, and measure end-to-end task success and latency (Table 9).
7. **Dataset:** extend the dataset to more floor types, lighting conditions and trash categories.

---

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

## E. Errors and inconsistencies found in the draft (fix before submission)

**Critical (a reviewer will catch these):**

1. **Table 1 contradicts §3.3 and §3.4:**
   - *Locomotion* says "12 V DC Servo Motors", but §3.3 says **6-inch BLDC hub motors with 24 V sine-wave controllers**.
   - *Perception hardware* says "RGB Webcam × 2, 720p" and omits the D435i. The vision code uses two USB cameras as a stereo pair, so the two webcams may be right for object detection; the D435i (used for mapping) should be added to the table.
   - *Wheel weight* "20 Kgs" is the per-wheel **load capacity**, not a weight.
   - *Free wheel rotation* "360oC" should be **360°**.
   - *Chassis width* "1.5 ft" (45.7 cm) vs. 50 cm in §3.3. *Chassis length* "2 ft" (61 cm) vs. 60 cm. Use one unit system (SI) consistently.
   - *Chassis height* "3 fts" should be "3 ft".
   - *Maximum speed* "30 rpm" is a wheel rotation rate. Give a linear speed too: with 6-inch (0.152 m) wheels, 30 rpm ≈ 0.24 m/s.
   - *Number of rotation cycles 10* is unclear. Define or remove.
   - *Total robot weight 50 Kg* vs. "chassis 30 kg + payload 20 kg": clarify whether 50 kg is the robot's mass or its total capacity (§3.3 says total **load capacity** is 50 kg).
2. **DWA vs MPPI:** §3.8 says obstacle avoidance uses the Dynamic Window Approach, but the implemented local controller is **MPPI** (Nav2 `MPPIController`). Fix §3.8, or the paper describes a different system from the one evaluated.
3. **Simulation vs. physical robot:** the simulated robot is 0.30 × 0.25 m, the real one about 0.60 × 0.50 m. All navigation numbers must be labelled "simulation". The size difference must be stated as a limitation (this file does that). Ideally re-run with a model at the real dimensions.
4. **Table 6 vs Table 7 for RF-DETR are inconsistent:**
   - Table 6 gives mAP@0.5 = **93.23 %**, but the mean of RF-DETR's per-class AP in Table 7 is **82.61 %**. For YOLOv8 (92.09) and YOLOv11 (92.48) the two tables agree exactly.
   - RF-DETR precision and recall also don't match: Table 6 has 93.40 / 88.52, while the Table 7 macro averages are 92.02 / 89.62.
   - So either Table 6's RF-DETR row or Table 7's RF-DETR columns come from a different run. As printed, the claim that RF-DETR has the highest mAP is contradicted by its per-class APs, which are the lowest.
5. **Table 7, cement_dust, RF-DETR:** F1 = 90.91 is impossible for P = 87.22 and R = 85.37. 2PR/(P+R) = **86.29**. All other F1 values check out.
6. **Dataset counts:**
   - Table 2 totals **877** images. The text (§4.1, §4.3) says **873**, and the split 611 + 175 + 87 = 873. The per-class numbers in Table 2 do sum to 877, so one of them is wrong.
   - §4.4's "2619 augmented images" = 3 × 873 (the whole dataset), which contradicts "augmentation applied only to the training set" (611 images → 1,833 or 2,444).
7. **Class list:**
   - Table 2 lists 6 classes. §4.3 uses 8 (adds floor and obstacle) and mentions "four functional classes described above", which are never described.
   - §4.6.1 says YOLOv8s detects "debris, obstacles, hazards, and humans", with a YOLOv8-seg floor model every fifth frame. Neither appears in the dataset or results.
8. **Decision Table 5** has no rows for cement_dust, wooden_dust or floor. The dust classes are the reason the robot has a vacuum (see the revised table in §5.4). The `ARM:PICK` command used by the vision code isn't implemented in the Arduino firmware in the repository.

**Edge benchmarks (§6.3):**

9. **Confounded comparison:** the "quantisation gain" compares CPU FP32 with GPU INT8. **INT8 calibration** used random noise, and INT8 accuracy wasn't measured. **Engine sizes** (8.6 / 4.8 MB) don't match the CSV, which reports ONNX size for all precisions.
10. **Table 9 hardware mismatch:** "YOLOv11n inference (RTX-A6000)" is a workstation GPU, but the latency breakdown should be measured **on the Jetson Orin Nano**. Table 9 also lists "SSD-MobileNet", which is never trained in this paper. "R-DETR" should be **RF-DETR**.
11. **Table 6 FPS:** = 30 for all three models. That is the camera frame rate, not inference throughput. Report the measured inference FPS (e.g. YOLOv8 INT8 77.6 FPS on Jetson) or label the column "camera-limited FPS".
12. **Model variant naming:** Table 4 is titled "YOLOv11n Training Hyperparameters" but lists "YOLO variants". §4.6.2 compares "YOLOv8s and YOLOv11n". Tables 6 and 7 say "YOLOv8 / YOLOv11". Name the exact variants (n/s/m) consistently. Table 4 still has "tbf" for optimizer and augmentation.

**Text and structure:**

13. **Placeholders:**
    - The abstract is a placeholder ("Swacch Robot ..").
    - Keywords: only "Computer Vision".
    - Bracketed placeholders remain: [ADD CAMERA SPECS], [MENTION HERE THE VALUE AND HOW WE CALCULATE CHARGE], [INSERT LINK IMAGE], [INSERT FORMULA AS OF NOW], [MENTION SPECS HERE], [REQUIRES MORE INFO], [NEEDS EXPERIMENTAL IRL PROOF].
    - §3.5 has a dangling "Figure" with no number.
14. **Truncated sentences:**
    - §2.1: "The results show promising perforamcne with a" ends mid-sentence.
    - §2.1, ref 18: the sentence about costmaps ("The problem is that the costmaps with an 9.56 second difference…") is garbled.
15. **§2.5 "Summary of Gaps"** describes the proposed system, not the research gaps. Retitle it ("Design Principles of the Proposed System") or rewrite it as gaps. It also says no ranging sensors are used, but the D435i is an active stereo depth (ranging) camera. Reword to "no LiDAR or ultrasonic sensors".
16. **§3.8:**
    - "1080x720p" isn't a standard resolution. The C270 streams 1280 × 720; §3.4 also says 1280 × 720.
    - "D430i" (in §3.6 and §3.8) should be **D435i**.
    - "it initially runs tests on depth on Jetson…" is garbled.
17. **§3.9:** the last sentence "Table 1 summarizes…" is misplaced (it belongs in §3.2).
18. **§3.6:** "36% and 499% more accurate" (citing ref 67). Verify these numbers against Merzlyakov & Macenski (IROS 2021) before keeping them; "499 %" is unusual and needs the exact source table.
19. **§3.6 vs §5.1 duplication:** both describe RTAB-Map. Keep the justification in §3.6 and the configuration in §5.1 (as written above), or merge them.
20. **Spelling inconsistency:** "Swachh Bauddhika Yantra" (title, captions) vs "Swachh Boudhik Yantra" (§3.6) vs "Swacch" (abstract). Pick one.

**References:**

21. **Duplicate:** refs **2** and **62** are the same paper (Ramalingam et al., Sci. Reports 2022).
22. **Wrong citation:** ref **49** (a 4-DOF robotic arm paper) is cited in §2.3 for "hybrid deep learning model".
23. **Missing authors:** refs **68** and **69** have author "Unknown".
24. **Incomplete entry:** ref 4 (Jagtap et al.) has no venue or year.

**Found while verifying against the repository:**

25. **Table 1 / §3.2:** the simulated robot is 0.30 × 0.25 m and 2 kg, while Table 1 gives about 60 × 50 cm and 50 kg. Every navigation result must be labelled simulation-only.
26. **§3.8 / §3.6:** a D435i depth field of view is stated as about 87°, but the simulated camera used 69.4°.
27. **Config comments are stale:** the RTAB-Map file says feature type 6 is ORB (it is GFTT/BRIEF); the Nav2 file says the footprint is a 0.18 m circle (it is a rectangle); the explorer YAML says the information term is the frontier size (it is the log of the size) and its weights are never read. Don't cite these comments.
28. **Compute board:** the robot's computer is the Jetson Orin Nano (confirmed by the authors). One repository note (`Navigation/Manual mode/claude_context.md`) still says the project moved to a Raspberry Pi 5 and should be corrected.

**Typos (sample):** comprenehsive, Kallaman, utilities (→ utilises), theoretial guarentees, perforamcne, efficency, funtion, convering, Accesssibility, comparision, maping, alligns, efficeint, crutial, accesible, baude, decison.
