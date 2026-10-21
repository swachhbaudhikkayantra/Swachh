# Swachh Boudhik Yantra — Project Status

*Based on a read-through of the source code (nothing was executed). Where a claim comes from a doc rather than code, it is marked as such.*

---

## 1. Project Intent

Build an **autonomous indoor cleaning robot** that can:

1. **Map and navigate** an indoor space on its own (differential-drive base, RGB-D / stereo camera, SLAM, Nav2).
2. **Find and pick up small household objects / debris** using a camera, a YOLO detector and stereo depth, then hand coordinates to a pick-up arm.
3. **Clean**: vacuum, wiper and UV modules driven from a touchscreen HMI and an Arduino motor controller.
4. **Publish research**: the repo doubles as the experimental basis for a Q1 journal paper (edge-inference benchmarking of YOLOv8/YOLOv11 on a Jetson Orin Nano, local vs. wireless; SLAM / exploration metrics in simulation).

Development philosophy (from the docs): *simulation first*, then transfer to hardware.

Three subsystems:

| Subsystem | Location | Purpose |
|---|---|---|
| Manual hardware control | `Navigation/Manual mode/` | GTK4 HMI + Arduino firmware for the real robot |
| Perception | `Object Detection/` | Detection, stereo depth, Pi→GPU streaming, benchmarks |
| Autonomy in simulation | `Navigation/Simulation/vacuum_ws/` | ROS 2 Jazzy + Gazebo Harmonic: SLAM, Nav2, exploration, localization |

---

## 2. Done Fully

These work as designed, as far as the code shows.

### Manual hardware control
- **Arduino firmware** (`swacch_robot.ino`): serial protocol at 115200 baud with `ACK:`/`ERR:` replies and 1 s `STATUS:` reports; forward/backward/left/right (tank turn via relay direction + PWM); 9 speed levels; `ESTOP` / `RESET` latch that blocks further commands.
- **GTK4 HMI** (C++): movement buttons (press = move, release = stop), speed selector, peripheral toggles, E-stop/reset, 4-category logger, serial auto-detect and launch scripts.

### Robot model and simulation base
- **URDF/xacro** model: chassis, two drive wheels, caster, camera / arm / vacuum mounts, D435i frames, single source of truth for dimensions in `_properties.xacro`.
- **`ros2_control`** with `diff_drive_controller` and `joint_state_broadcaster` on Gazebo Harmonic.
- **Gazebo worlds**: empty room, apartment, office, corridor.
- **ROS↔Gazebo bridge** for `/clock`, colour image, depth image, camera info, point cloud.
- **`cmd_vel_relay`** (Twist → TwistStamped), keyboard teleop and steering GUI.
- **RTAB-Map RGB-D mapping** with 2D occupancy-grid export, plus `run_mapping.sh`, `save_map.sh`, `view_map.sh`, `start.sh`, `stop.sh`. (Stage 4A is reported complete in `overall_progress_report.md`.)

### Benchmark framework (for the paper)
- Headless Jetson benchmark (`cli_benchmark.py`): warm-up, multiple trials, tegrastats power / GPU / temperature capture, CSV + JSON output.
- Custom TensorRT wrapper (`trt_inference.py`) building FP16 / INT8 engines from ONNX.
- Pure-NumPy statistics library (`stats_utils.py`): t-based CI, bootstrap, Welch, Mann-Whitney, Cohen's d.
- Scenario A (local) and Scenario B (Pi → Wi-Fi → Jetson) both executed; results saved in `Object Detection/Metrics/`.
- Bidirectional TCP protocol with detection feedback to the Pi, and RTT ping-pong.

### Trained models
- Custom 8-class debris detector (YOLOv8, YOLOv11-seg, RF-DETR) trained and exported to ONNX / TensorRT, with Streamlit demo apps.

---

## 3. Done Partially

Present in code but incomplete or not working correctly yet.

### Perception → arm pipeline (largest gap)
- Detector + stereo depth + serial sender exist, but:
  - Depth values are in **metres** but labelled and handled as **cm**, then rounded to 0.1 (10 cm resolution).
  - Sends `ARM:PICK:...`, which the Arduino does not implement (replies `ERR:UNKNOWN_CMD`).
  - Stored stereo calibration looks questionable (principal point beyond image width, large rectification rotations).
  - Detection runs on the unrectified frame while depth is read from the rectified one.
  - `_nms()` is likely to fail on a standard `(1, 84, 8400)` YOLOv8 output; tests only cover small shapes.
  - Vision pipeline uses COCO classes, while the trained model is the 8-class debris model; the two are not unified.
- ZMQ Pi↔GPU distributed mode exists and runs, but the config disagrees on the Pi IP (`10.0.0.1` vs `192.168.4.1`).

### Autonomous exploration (Stage 4B)
- Frontier detector, goal scorer, FSM manager, visualizer and metrics logger are written, but:
  - Oscillation check effectively cancels every goal after 15 s (the 30 s timeout is never reached).
  - Frontier IDs are unstable, so blacklisting can hit the wrong frontier; a cancelled goal's late result can be applied to the next goal.
  - `retry_count`, `oscillation_distance` and the "adaptive tightening" are declared but unused.
  - `raise StopIteration` in a timer callback is not a safe shutdown path.
  - Pure-Python full-map loops will be slow on large maps.
  - Goals are sent to raw frontier centroids, with no snapping to a reachable free cell.

### Nav2 setup
- Smac Hybrid A* + MPPI, custom behaviour trees, costmaps from depth-to-laserscan are configured, but:
  - The velocity smoother's input and output are mapped to the **same topic** as the controller output (feedback loop; smoothing is bypassed).
  - Footprint (`robot_radius` 0.18 m) is smaller than the chassis circumradius (≈0.195 m), and the wheel pivot is offset 8 cm.
  - Smac Dubins with a 0.25 m turning radius is more restrictive than a diff-drive robot needs.

### Stage 5 localization (AMCL + monitors)
- Launch, AMCL config, `localization_monitor` and `recovery_monitor` exist, but:
  - A stationary robot is flagged LOST after 3 s (AMCL only publishes on motion).
  - Recovery spins with a blocking `sleep` inside a callback, the goal-cancel line is a no-op, and "3 attempts" cannot actually occur.
  - `cov_trace_lost` is effectively unused by the classifier.
- Not shown as validated end-to-end in this repo.

### SLAM evaluation
- `evaluate_trajectory.py` and `record_trajectory.py` exist, but the Gazebo ground-truth bridge only works in the world named `vacuum_world` (the empty room), not apartment/office/corridor; the script uses `--correct_scale` and expects `/rtabmap/odom`, which may not be published; `delete_db:=false` is ignored by the SLAM launch.

### Paper results (validity)
- Numbers exist, but:
  - "Quantization speed-up / efficiency" compares ONNX-Runtime **CPU FP32** against TensorRT **GPU** FP16/INT8, so backend and precision are mixed.
  - INT8 engines use random-noise calibration and have no accuracy (mAP) comparison.
  - "Net transit" is a single RTT/2 constant applied to every frame.
  - Engine sizes in the write-up (8.6 / 4.8 MB) do not match the CSV (11,983 KB for all precisions).
  - The normality test labelled "Shapiro–Wilk" is actually D'Agostino–Pearson.
  - YOLOv11-seg INT8 fails to build on TensorRT 10.3 (documented, skipped).
  - Model paths in the Streamlit apps / `cli_benchmark.py` do not match the repo layout (`Model weights/...`).

### Hardware control
- Peripherals (vacuum, arm, wiper, UV) are state flags only — no pins or drivers.
- No Arduino watchdog / heartbeat: the motors keep running if the link drops.
- HMI blocks the UI thread up to 500 ms per command; battery level is simulated.
- Auto mode (`AUTO:ON`) only sets a flag.

### Test suite
- Directory structure for ~15 test tiers exists; only unit, regression, safety, fault-injection, performance and one integration test have content. The vision and regression tests point to `Navigation/Camera/vision`, which does not exist (code is in `Object Detection/Camera/vision`), so they cannot import the detector.

### Documentation
- Docs overlap (`docs/` vs `Navigation/Simulation/Documentation/`), the top-level `README.md` is empty, and the docs disagree on hardware (Jetson vs RPi 5 on Humble vs RPi + Windows GPU) and OS / Python versions (docs: Ubuntu 26.04 / Python 3.14; code: `python3.12`).

---

## 4. Yet To Be Done

### Integration (nothing connects the three subsystems yet)
- **ROS motor bridge**: a node translating `cmd_vel` to Arduino commands (differential speed, not the current fixed-PWM `MOVE:*` strings), with encoder / odometry feedback.
- **Hardware ros2_control plugin** replacing `GazeboSimSystem` (planned as "Stage 10").
- **Vision as ROS 2 nodes**: publish detections / 3D target poses as ROS messages; convert `main.py` into a node.
- **Pick-and-place**: arm hardware driver, arm kinematics / inverse kinematics, grasp sequencing, and the Arduino `ARM:PICK` handler.
- **Cleaning behaviours**: floor-coverage planning for vacuuming, using the trained debris classes (including dust and the `floor` / `obstacle` classes), vacuum / wiper / UV actuation by the autonomy stack.
- **Docking and charging** (a test folder exists, no implementation).

### Real-robot perception and localization
- Redo stereo calibration and validate reprojection error; fix the rectification / unit handling.
- Real sensor setup on the robot (current real-robot docs list only two C270 webcams: no depth camera, LiDAR or IMU). Decide between stereo visual SLAM (RTAB-Map / ORB-SLAM3) and adding a depth sensor.
- Wheel encoders / IMU fusion (e.g. `robot_localization`) on hardware.
- Sim-to-real calibration of wheel radius, separation and the correction multipliers in `controllers.yaml`.

### Autonomy
- Fix the exploration, Nav2 and localization-monitor defects listed in section 3.
- Complete Stage 5 validation: save maps, AMCL + goal navigation experiments, localization-loss recovery that actually works.
- Dynamic-obstacle avoidance tests; hardware-level safety layer (collision monitor, bumper / cliff sensing, watchdog on cmd_vel).
- Larger-environment (e.g. warehouse) support — referenced in launch arguments but no world file exists.

### Safety
- Arduino-side watchdog / heartbeat and ramped stop on link loss.
- Make E-stop independent of the host (hardware cut-off).

### Research deliverables
- Re-run the benchmarks with a fair design: TensorRT FP32 vs FP16 vs INT8 on the same backend, plus ORT-CPU as a separate baseline.
- Proper INT8 calibration on real data and an accuracy comparison (mAP / precision / recall) for every precision.
- Per-frame network latency measurement (clock-synchronised) instead of the RTT/2 constant.
- Correct the statistics labels (D'Agostino–Pearson vs Shapiro–Wilk; plain vs bias-corrected bootstrap).
- SLAM / exploration experiments with working ground truth in all worlds; roadmap items in `q1_paper_test_roadmap.md`.
- Q1 paper writing.

### Engineering hygiene
- Repair test paths and fill the empty test tiers (integration, system, hardware, field, endurance).
- Consolidate the duplicated docs, write the root `README.md`, and pick one canonical hardware / software stack.
- Remove duplicated files (`graphify.py` exists twice) and hard-coded `python3.12` / user-specific paths (`/home/bmscecse/...`).
- Add CI to run the unit tests.
