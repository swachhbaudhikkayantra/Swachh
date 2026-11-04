# Swachh Bauddhika Yantra (SBY)

An autonomous indoor cleaning robot. The design: it explores and maps a room, plans paths around obstacles, spots trash with a camera, picks it up with a small arm and vacuums the floor. This repository holds the robot's navigation stack and Gazebo simulator, the object-detection code and models, the Arduino firmware and touchscreen HMI for manual driving, a simulation evaluation framework, and the draft of the research paper.

This README should be enough for most purposes: what is here, what is real, how to run it, what the results are, and what to watch out for. For the full narrative see [explainer/00_the_story.md](explainer/00_the_story.md). For line-level detail see [explainer/README.md](explainer/README.md). For step-by-step commands see [docs/USER_MANUAL.md](docs/USER_MANUAL.md).

## Contents

1. [What is real and what is not](#1-what-is-real-and-what-is-not)
2. [How the system fits together](#2-how-the-system-fits-together)
3. [Repository layout](#3-repository-layout)
4. [Requirements](#4-requirements)
5. [Install and build](#5-install-and-build)
6. [Run the simulation](#6-run-the-simulation)
7. [Run the evaluation framework](#7-run-the-evaluation-framework)
8. [Results (simulation, 4-hour campaign)](#8-results-simulation-4-hour-campaign)
9. [Metrics that were and were not measured](#9-metrics-that-were-and-were-not-measured)
10. [Paper: tables and figures pipeline](#10-paper-tables-and-figures-pipeline)
11. [Object detection](#11-object-detection)
12. [Hardware: firmware and HMI](#12-hardware-firmware-and-hmi)
13. [Tests](#13-tests)
14. [Known issues and gotchas](#14-known-issues-and-gotchas)
15. [Limitations of the work](#15-limitations-of-the-work)
16. [Safety](#16-safety)
17. [Documentation map](#17-documentation-map)
18. [Rules for contributors](#18-rules-for-contributors)
19. [Licence](#19-licence)

---

## 1. What is real and what is not

Mixing these up is the easiest way to misread the project.

| Part | Status |
|---|---|
| Navigation, SLAM, exploration, obstacle avoidance | **Simulation only.** Evaluated in Gazebo. Nothing from this campaign ran on the physical robot or the Jetson |
| Manual driving (HMI plus Arduino firmware) | **Implemented** for hardware. The firmware really drives only the two motors |
| Vacuum, arm, wiper, UV commands | **Flags only.** The firmware accepts them but has no output pins behind them |
| `ARM:PICK ...` sent by the vision code | **Unsupported by the firmware**: it would be answered with `ERR:UNKNOWN_CMD` |
| Trash-detection models (YOLOv8, YOLOv11-seg, RF-DETR) | **Trained and benchmarked**, but not the ones used by the checked-in pick pipeline |
| Stereo pick pipeline in `Object Detection/Camera` | **Prototype**: two USB webcams as a stereo pair, a generic COCO YOLOv8s model limited to 7 classes, ONNX Runtime (no TensorRT engine) |
| Decision/fusion module, semi-automatic and automatic modes | **Design only** |
| End-to-end latency (camera to actuator) | **Never measured** |

## 2. How the system fits together

```
 Gazebo (physics, depth camera, wheels)
   │  gz_bridge: camera images, wheel commands, ground truth
   ▼
 ROS 2 Jazzy
   ├─ RTAB-Map ........ builds the map and the robot pose from camera + wheel odometry
   ├─ Frontier explorer picks the next goal at the edge of the known map
   ├─ Nav2 ............ Smac Hybrid (Dubins) global planner, MPPI local controller, costmaps,
   │                    behaviour tree with recoveries
   ├─ Velocity smoother → relay → diff-drive controller → wheels
   └─ vacuum_eval ..... evaluation harness: runs episodes, records ground truth, computes metrics
```

- **Mapping.** RTAB-Map with GFTT keypoints and BRIEF descriptors (up to 500 per image), map updated at 1 Hz, loop-closure threshold 0.11, 3-DoF (planar) estimation, wheel odometry only, 5 cm occupancy grid. Note the comment in `rtabmap.yaml` calls feature type 6 "ORB"; in RTAB-Map 0.23 it is GFTT/BRIEF.
- **Planning.** Global planner re-plans about once a second. The local controller runs about 20 Hz on a 4 m rolling local costmap. The costmaps use the real 0.30 × 0.25 m rectangular footprint (a header comment in `nav2_params.yaml` still says "circle of radius 0.18 m").
- **Exploration.** Frontier score = 1.0·ln(1 + cluster size) − 1.5·distance − 0.8·obstacle penalty. Goals stay at least 0.30 m from walls.
- **Simulated robot.** 0.30 × 0.25 m box, 2.8 kg, wheel radius 0.033 m, track 0.268 m, one forward 640×480 30 Hz RGB-D camera with a 69.4° field of view and no sensor noise. No lidar, no IMU. The physical robot is about 0.60 × 0.50 m.

Deeper: [01 System overview](explainer/01_system_overview.md), [04 Robot model and worlds](explainer/04_robot_model_and_worlds.md), [06 SLAM](explainer/06_slam_and_localization.md), [07 Nav2](explainer/07_nav2_and_controller.md), [08 Exploration](explainer/08_frontier_exploration.md), [14 Topics and data flow](explainer/14_topics_tf_and_dataflow.md).

## 3. Repository layout

| Path | What it is |
|---|---|
| `Navigation/Simulation/vacuum_ws/src/` | The ROS 2 workspace (packages below) |
| `Navigation/start.sh`, `stop.sh`, `run_mapping.sh`, `save_map.sh`, `view_map.sh`, `steer_gui.sh` | Convenience launchers (see Known issues) |
| `Navigation/Simulation/scripts/` | `setup_machine.sh` (installer), `preflight.sh` (read-only checks), `check_gpu_render.sh` |
| `Navigation/Manual mode/` | Arduino firmware and GTK4 HMI |
| `Navigation/tests/` | Mocked-ROS pytest suite |
| `Object Detection/` | Benchmark and demo apps, model weights, and `Camera/` (stereo pick pipeline) |
| `docs/` | Plans, metric definitions and status, audits, specs, the user manual, paper drafts |
| `docs/paper_out/` | Scripts that turn results into paper tables and figures, plus the generated figures |
| `explainer/` | Narrative and per-subsystem explanations |
| `results/` | Archived evaluation runs |
| `paper.txt` | The paper draft (LaTeX source) |
| `progress/`, `council/`, `large_files/` | Progress reports, decision notes, large local-only files (rosbags, databases; ignored by git) |

ROS 2 packages in `vacuum_ws/src/`:

| Package | Role |
|---|---|
| `vacuum_description` | Robot model (URDF/xacro), sensors, contact sensors |
| `vacuum_gazebo` | 18 worlds, Gazebo to ROS bridge configuration |
| `vacuum_bringup` | `sim.launch.py` and RViz launch |
| `vacuum_controller` | Drive controller configuration, velocity relays, teleop and diagnostics nodes |
| `vacuum_slam` | RTAB-Map launch and configuration, map saving |
| `vacuum_localization` | AMCL covariance monitor and recovery spin |
| `vacuum_nav2` | Nav2 parameters, behaviour trees, launch |
| `vacuum_exploration` | Frontier explorer |
| `vacuum_eval` | Evaluation harness, metrics, aggregation, report and paper tables |
| `vacuum_utils` | 12 check, record, benchmark and diagram scripts |
| `vacuum_interfaces` | Defines no custom messages, services or actions (the generation call is commented out) |

## 4. Requirements

| Item | Requirement |
|---|---|
| OS | Ubuntu 24.04 (ROS 2 Jazzy needs it) |
| ROS 2 | Jazzy (`ros-jazzy-desktop`, `ros-dev-tools`) |
| Simulator | Gazebo Harmonic (gz-sim 8.x) |
| Mapping and navigation | `rtabmap_ros`, Nav2 (with `SmacPlannerHybrid`), `ros-jazzy-spatio-temporal-voxel-layer` |
| Middleware | CycloneDDS (`rmw_cyclonedds_cpp`) with `Navigation/cyclone_dds.xml` |
| Python | 3.12 with numpy, scipy, matplotlib, PIL, yaml, pytest, cv2 |
| GPU | Optional. NVIDIA driver 570+ recommended; without a GPU Gazebo falls back to slow software rendering |
| Compute | The evaluation machine had 22 GB RAM and 16 threads. CPU is the limit: two parallel simulations run at near real time, three dropped the real-time factor to about 0.74 |
| Terminal | `ptyxis` is used by `start.sh`; use the direct `ros2 launch` commands without it |
| Extra DDS setting | Socket buffer `net.core.rmem_max` must be 33554432, or SLAM silently gets no images |

Detection and hardware need their own packages (section 11 and 12).

## 5. Install and build

```bash
cd ~/Swachh/Navigation/Simulation/scripts
./setup_machine.sh --dry-run      # review first
./setup_machine.sh                # apt packages, DDS buffers, ~/.bashrc, rosdep, build, tests
source ~/.bashrc
./preflight.sh                    # read-only; every line should say PASS
```

Or build by hand:

```bash
cd ~/Swachh/Navigation/Simulation/vacuum_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

In every new terminal:

```bash
source /opt/ros/jazzy/setup.bash
source ~/Swachh/Navigation/Simulation/vacuum_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp CYCLONEDDS_URI=file://$HOME/Swachh/Navigation/cyclone_dds.xml ROS_DOMAIN_ID=0
```

Over SSH (no display) also set `export VACUUM_GZ_HEADLESS_RENDERING=1`.

## 6. Run the simulation

### Direct commands (work anywhere)

```bash
# 1. Gazebo + robot + controllers
ros2 launch vacuum_bringup sim.launch.py world:=office
# 2. SLAM on top (second terminal)
ros2 launch vacuum_slam slam.launch.py environment:=office use_rviz:=false
# 3. Autonomous frontier exploration (full stack)
ros2 launch vacuum_exploration exploration.launch.py environment:=office
# 4. Navigation on a saved map (after running sim.launch.py use_sim_time:=true)
ros2 launch vacuum_nav2 nav2_localization.launch.py map_path:=$HOME/maps/stage5/office.yaml environment:=office
```

Useful `sim.launch.py` arguments: `world`, `world_file` (path to your own `.sdf`), `use_rviz`, `headless`, `use_sim_time`, `spawn_x`, `spawn_y`, `spawn_yaw`. Run `ros2 launch vacuum_bringup sim.launch.py --show-args` for all 19.

### Convenience launcher

```bash
cd ~/Swachh/Navigation
./start.sh                 # manual mode: simulation + teleop + steering GUI
./start.sh explore office  # autonomous exploration
./start.sh navigate office # needs a saved map at ~/maps/stage5/office.yaml
./start.sh steer           # steering GUI only
./start.sh stop
```

`start.sh` opens terminal windows with `ptyxis`. Some listed environment names (for example `apartment`, `warehouse`) may not have matching world files, so check the name exists first.

### Worlds

`apartment, cluttered_room, corridor, empty_room, empty_world, maze_dead_ends, multi_room_loop, office, symmetric_hall, two_rooms_door`, plus obstacle-avoidance scenarios (`avoid_u_trap`, `avoid_dynamic_sudden`, and others with the `avoid_` prefix). 7 are development worlds and 10 are held-out test worlds; the split is defined in `vacuum_eval/config/`.

### Save and view a map

While the simulation runs: use `save_map.sh` (see Known issues for its path problem) or call `ros2 run nav2_map_server map_saver_cli -f ~/maps/stage5/office` yourself. The [manual, section 4](docs/USER_MANUAL.md) has both versions.

## 7. Run the evaluation framework

The harness runs the robot in standardised episodes, records ground truth from the simulator, and computes the metrics.

```bash
cd ~/Swachh/Navigation/Simulation/vacuum_ws/src/vacuum_eval
bash ~/Swachh/Navigation/Simulation/scripts/preflight.sh

# one episode
python3 -m vacuum_eval.run_episode --experiment myrun --world office --method frontier \
    --seed 1 --odom-noise 1 --headless 1 --timeout-sim-sec 600

# a campaign (many episodes); finished ones are skipped, so you can resume
python3 -m vacuum_eval.run_batch --matrix config/campaigns/quick_navigation.yaml \
    --split test --confirm-test-split --parallel 2 --lean 1
```

- **Methods:** `frontier` (exploration), `scripted_goals` (navigation or avoidance scenarios), `responsiveness`.
- **Outputs:** `~/eval_runs/<experiment>/<world>/<method>/seed_NNN/` with `summary.json`, logs and maps. Aggregate with `vacuum_eval.aggregate`, make a report with `vacuum_eval.make_report`.
- **Rules built in:** validity gates exclude episodes that did not really run the stack (only `status: invalid` is excluded); health flags warn but never exclude; intervals use bootstrap resampling (worlds first, then seeds) and Wilson intervals for success rates; the test split is frozen, so nothing may be tuned after a test campaign starts.
- A batch of exploration with odometry noise on is stored under the experiment name plus `_noise` (for example `quick_exploration_noise`).
- Run long jobs inside `tmux`. Stop a run with `kill -INT <harness PID>`. Do not use `stop.sh` for evaluation runs.

Deeper: [09 Metrics](explainer/09_evaluation_metrics.md), [10 Harness](explainer/10_evaluation_harness.md), [docs/RUNBOOK.md](docs/RUNBOOK.md).

## 8. Results (simulation, 4-hour campaign)

The campaign was shortened to four hours: 31 test episodes (9 exploration with odometry noise, 12 navigation, 6 avoidance, 4 responsiveness of which 2 are invalid by design). Values are script-computed from the run files. Only 3 or 4 seeds per world, so intervals are wide. Real-time factor was 0.73 to 1.00.

| Metric | Result |
|---|---|
| Explored floor coverage | 61.4 % [18.5, 88.0] overall. Office 83.8, multi-room loop 86.3, maze 14.3 |
| Map completeness | 47.7 % [15.1, 70.6] (mean of free-floor recall and wall recall) |
| SLAM trajectory error (ATE) | 0.57 m [0.33, 0.86], 7 episodes; wheel odometry alone 2.54 m in the same episodes |
| Relative error (RPE, 1 m) | SLAM 0.25 m/m; wheel odometry 0.19 m/m (the 1 m window hides accumulated drift) |
| Odometry corrupted by contact | 4 of 9 exploration episodes |
| Loop-closure precision / recall | 35.2 % of 1051 accepted closures (lower bound) / 28.2 % |
| Navigation success | Nav2 reported 50.0 % of 178 goals; ground-truth verified 29.2 % (52 of 178). Per-episode mean 23.4 % [2.8, 46.7] |
| Navigation by world | two_rooms_door 48.8 %, office 20.7 %, maze 2.5 % |
| Path-length ratio (reached goals) | 1.21 |
| Obstacle avoidance trials | 4 of 6 (static U-trap 3/3, sudden moving box 1/3); minimum clearance 0.159 m |
| Response to a velocity command | 166 ms to half speed, 260 ms to stop (2 valid episodes) |
| AMCL position error | 0.318 m [0.183, 0.509]; maze 0.44–0.59 m |

Three results to interpret carefully:

1. **The maze coverage of 14.3 % is a stall, not a slow robot.** In two of three maze episodes the explorer found no goal that met its 0.30 m clearance rule, and the robot stayed near its start. The cause has not been fixed.
2. **Navigation success is low mainly because of localisation.** The dominant failure was Nav2 refusing to plan because the AMCL pose put the footprint inside a wall while the true position was in free space. A diagnostic on one development world (a single episode per setting, so indicative only) gave 6 of 19 goals with AMCL and 19 of 20 with ground-truth localisation. The navigation campaign tests Nav2 plus AMCL on a ground-truth map, not the RTAB-Map pipeline.
3. **The loop-closure precision is a lower bound**, because closures are matched to ground truth with a timing bias.

Full context: [docs/EVALUATION_FINDINGS_2026-10-25.md](docs/EVALUATION_FINDINGS_2026-10-25.md).

## 9. Metrics that were and were not measured

Of the 14 requested metrics and 15 extras (full status in [docs/METRICS_STATUS.md](docs/METRICS_STATUS.md) and [docs/METRICS_AUDIT_2026-10-25.md](docs/METRICS_AUDIT_2026-10-25.md)):

- **Measured with caveats:** coverage, steps, collisions, % obstacle avoidance, responsiveness, ATE, RPE, map completeness, avoidance success, navigation success, loop closure, path ratio, cleaning efficiency, and most extras (coverage-vs-time, overlap, missed area, distance and energy proxy, clearance, recoveries, path smoothness, odometry drift, CPU, real-time factor, repeatability, AMCL error).
- **Not measured:** #13 comparison of coverage methods (on hold by decision) and A15 noise robustness (the clean-sensor condition was dropped from the shortened plan).

Definitions follow the code, which differs from older documents in places: map completeness is the mean of free recall and wall recall (not an IoU); the ground-truth obstacle band is about 3 to 25 cm; the step-response test uses 50 % of the commanded step. Details are in [explainer 09](explainer/09_evaluation_metrics.md).

## 10. Paper: tables and figures pipeline

No number in the paper results is typed by hand.

```bash
cd ~/Swachh/Navigation/Simulation/vacuum_ws/src/vacuum_eval
PYTHONPATH=$PWD python3 -m vacuum_eval.paper_tables --root ~/eval_runs_victus --out ~/Swachh/docs/paper_out
cd ~/Swachh/docs/paper_out && python3 make_figures.py
```

- `paper_tables.py` reads each episode's `summary.json`, computes the statistics, cross-checks them against `aggregate.csv`, and writes `paper_values.json` and `paper_tables.md`.
- `make_figures.py` draws nine figures from the raw run data (floor plans, exploration and navigation paths, actual-versus-explored maps, coverage over time, navigation success, trajectory error, costmap layers, a SLAM map). It has no command-line flags; edit its `ROOT` and `OUT` constants if your data lives elsewhere.
- Both scripts overwrite the committed outputs in `docs/paper_out/`. They need `~/eval_runs_victus/` with a `_gt/` folder of ground-truth grids, which is not in the repository.
- `paper.txt` expects its images in an `images/` folder next to it; that folder is not in the repository. Copy the generated figures into it, together with the architecture and data-sample pictures.

Details: [explainer 13](explainer/13_results_docs_and_paper_pipeline.md).

## 11. Object detection

Folder `Object Detection/` (the folder name has a space; quote it).

```bash
cd "$HOME/Swachh/Object Detection"
pip install -r requirements.txt
bash run.sh                    # menu: live UI, benchmark UI, Pi camera sender, CLI benchmark
streamlit run app.py           # live detection UI
python3 cli_benchmark.py --frames 150 --runs 3 --warmup 10
```

- **Models.** Three detectors on a custom 8-class trash set: YOLOv8, YOLOv11-seg and RF-DETR. Weights are in `Model weights/`. In the paper RF-DETR has the best accuracy (mAP@0.5 0.9336 on the validation set) and the YOLO nano models are far smaller.
- **Latency.** The benchmark script measures 450 samples per model (10 warm-up frames, then 3 trials of 150 frames). TensorRT FP16 and INT8 took roughly 12 to 20 ms per frame (YOLOv11 FP16 17.1 ms, YOLOv8 INT8 12.9 ms) against about 190 ms for FP32 on the CPU. The FP32 and TensorRT rows differ in both precision and device, so they are not a pure precision comparison. INT8 engines were calibrated on random data, so INT8 accuracy is not meaningful. RF-DETR was never benchmarked for latency.
- **Hardware not recorded.** No result file states which machine produced the latencies; the Jetson Orin Nano attribution comes from the scripts and project notes.
- **Pick pipeline** (`Camera/`). Stereo disparity from two USB cameras, a COCO YOLOv8s detector on 7 classes, a serial `ARM:PICK` command, and a ZeroMQ mode that splits work between a Raspberry Pi and a GPU computer. The shipped calibration has a principal point (cx0 = 681.9) beyond the 640 px image width, which suggests it should be checked before trusting its distances.

Deeper: [11 Camera code](explainer/11_object_detection_camera.md), [12 Models and benchmarks](explainer/12_detection_models_and_benchmarks.md).

## 12. Hardware: firmware and HMI

Folder `Navigation/Manual mode/`.

```bash
cd "$HOME/Swachh/Navigation/Manual mode/hmi"
bash scripts/setup.sh      # one time; installs build tools, GTK4, arduino-cli; log out and in afterwards
bash scripts/run.sh        # builds if needed, detects the Arduino port, starts the HMI
```

- **Protocol.** 115200 baud, newline-terminated text: `MOVE:FORWARD`, `MOVE:LEFT`, `MOVE:STOP`, `SPEED:1` to `SPEED:9`, `ESTOP`, `RESET`, plus `VACUUM`, `ARM`, `WIPER`, `UV` on/off. The Arduino replies `ACK:<command>` and sends `STATUS:` lines.
- **What really acts.** Only the two motors (PWM pins 5 and 6, relay pins 7 and 8). Everything else sets a flag.
- **HMI.** GTK4 touchscreen app. Its battery level is simulated, and it does not synchronise its state from the Arduino's status lines.
- The firmware has no board-flashing script in the folder; upload `arduino/swacch_robot/swacch_robot.ino` with the Arduino IDE.

Deeper: [03 Manual mode and HMI](explainer/03_manual_mode_hmi.md).

## 13. Tests

```bash
# evaluation harness tests (27 test files)
cd ~/Swachh/Navigation/Simulation/vacuum_ws/src/vacuum_eval && python3 -m pytest test -q
# project-wide mocked-ROS suite
cd ~/Swachh/Navigation && python3 -m pytest
```

When the Navigation suite was run for the explainer, 126 tests were collected: 85 passed and 41 failed. All 41 failures are vision tests that import `Navigation/Camera/vision/detector.py`, which no longer exists because the camera code moved to `Object Detection/Camera/`. They are stale, not evidence of a runtime bug. The harness tests were not re-run for the explainer.

## 14. Known issues and gotchas

- `Navigation/run_mapping.sh` and `save_map.sh` hard-code paths from another machine (`/home/bmscecse/...` or `~/Swachh_Boudhik_Yantra`). They fail in a normal clone; use the direct commands in the manual.
- `Navigation/stop.sh` kills processes by pattern with `pkill -9 -f` and deletes `~/.ros/rtabmap.db*`. Do not use it during evaluation runs.
- `Navigation/graphify.py` sends scanned workspace snippets to the Gemini API unless run with `--no-ai`. Its default workspace resolves to your home directory, so always pass `--workspace`.
- Stale comments in configs: feature type "ORB" (it is GFTT/BRIEF), footprint "circle 0.18 m" (it is a rectangle), physics "1000 Hz" (the worlds run at 250 Hz).
- The 86° depth field of view in the robot config is never applied; only the colour camera's 69.4° is.
- The camera noise values in `camera.yaml` are not wired in; the simulated camera is noiseless.
- `vacuum_controller` diagnostics flags (`enable_diagnostics`, `enable_camera_diagnostics`) are declared but unused, so those nodes always start.
- `/camera/depth/points` is commented out of the bridge, but a few utility scripts expect it.
- In `recovery_monitor.py` the goal-cancel line is missing its call parentheses, so it does nothing.
- The explorer's `retry_count` is read but never used; a frontier is blacklisted after its first failure.
- YAML says the ground-truth obstacle band top is 0.30 m, but the code always uses 0.25 m.
- Documentation mentions both a Raspberry Pi 5 and a Jetson Orin Nano as the robot computer; the authors identify the Jetson.

## 15. Limitations of the work

- All navigation and SLAM results are from simulation, with a smaller robot (0.30 × 0.25 m against about 0.60 × 0.50 m), a noiseless camera and a 69.4° depth field of view. Nothing ran on the Jetson or the physical robot.
- The campaign was cut from eight to four hours: 3 or 4 seeds per world, 9 exploration episodes instead of 15, 178 navigation goals instead of about 240.
- Office and multi-room exploration ran three simulations at once on one machine, which lowers the real-time factor and inflates CPU readings.
- Odometry noise was injected only in the exploration campaign.
- Contact counts bursts more than 0.5 s apart, so one jam can be counted several times, and the wheels are not in the contact sensor.
- The end-to-end latency chain, noise robustness and a comparison of coverage methods were not evaluated.

## 16. Safety

The base is motor-driven and the firmware has **no command timeout and no heartbeat**: the last motion command keeps running until `MOVE:STOP`, `ESTOP`, `RESET` or a power cycle. The check that blocks movement while auto mode is on exists only in the HMI. Test with the wheels off the ground first, and keep the emergency stop within reach.

## 17. Documentation map

| Want | Read |
|---|---|
| The whole project as a story | [explainer/00_the_story.md](explainer/00_the_story.md) |
| Per-subsystem deep dives (14 files) | [explainer/README.md](explainer/README.md) |
| Exact run commands, troubleshooting | [docs/USER_MANUAL.md](docs/USER_MANUAL.md) |
| Evaluation procedure | [docs/RUNBOOK.md](docs/RUNBOOK.md), [docs/specs/](docs/specs/) |
| What each result means, biases, failure modes | [docs/EVALUATION_FINDINGS_2026-10-25.md](docs/EVALUATION_FINDINGS_2026-10-25.md), [docs/FAILURE_MODES.md](docs/FAILURE_MODES.md) |
| Metric definitions and status | [docs/METRICS_TO_BE_MEASURED.md](docs/METRICS_TO_BE_MEASURED.md), [docs/METRICS_STATUS.md](docs/METRICS_STATUS.md), [docs/METRICS_AUDIT_2026-10-25.md](docs/METRICS_AUDIT_2026-10-25.md) |
| Project background and requirements | [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md), [docs/SESSION_CONTEXT.md](docs/SESSION_CONTEXT.md), [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) |
| Paper drafts and figure notes | [docs/paper_out/](docs/paper_out/), [docs/PAPER_SECTIONS_FINAL.md](docs/PAPER_SECTIONS_FINAL.md), [paper.txt](paper.txt) |

## 18. Rules for contributors

From `CLAUDE.md` and the pre-registration, for anyone touching the evaluation:

- Do not change the planner, robot or sensor model, world geometry, metric definitions or thresholds to improve numbers, and do not tune after a test campaign starts.
- Rerun an episode once, with the same seed, only for infrastructure faults. Exclude only episodes marked `status: invalid`. Report unflattering results as measured.
- Run commands over two minutes in `tmux`. Never `pkill -f` a pattern that appears in your own command line; stop runs with `kill -INT <harness PID>`.
- Do not push to GitHub or send data to third-party services without the owner's explicit approval.

## 19. Licence

No licence file is present in the repository. Contact the authors before reuse.
