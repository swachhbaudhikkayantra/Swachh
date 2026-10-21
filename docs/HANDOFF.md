# HANDOFF — Swachh Boudhik Yantra (read this first)

This file is the full context for a Claude Code session running **inside WSL Ubuntu** that is taking over from a previous session which ran on the Windows side. Read it completely before doing anything. Everything here was learned by reading the code and running setup commands; **nothing in the robot code has been executed yet**, so bug claims are from reading, not from runtime observation.

Companion file: `docs/PROJECT_STATUS.md` (intent / done / partial / to-do summary).

---

## 0. TL;DR

- Project: an autonomous indoor cleaning robot. Repo has 3 parts: manual hardware control (Arduino + GTK HMI), perception (YOLO + stereo depth + benchmarks for a Q1 paper), and a **ROS 2 Jazzy + Gazebo Harmonic simulation** (SLAM, Nav2, frontier exploration, AMCL).
- The user wants to **run the simulation in WSL**, then iterate: user asks for a change → you edit code → run it → read logs/topics → verify; the user watches the Gazebo/RViz windows (WSLg) and reports what they see.
- **Working copy = `~/Swachh` in Ubuntu (WSL).** The Windows copy at `/mnt/c/Users/DELL/Desktop/Swachh` is the original and is now **stale**; do not edit it.
- **State right now:** WSL + ROS Jazzy + all apt dependencies are **installed**. The workspace has **NOT been built yet**. Next action = `colcon build`, then first launch of the sim.

---

## 1. The user and how they like to work

- Windows 11 laptop. Linux user in WSL is `hrishikesh`; Windows user is `DELL`. They are building this for a university project / Q1 paper.
- Wants **comprehensive, verified** analysis, not surface-level reading ("don't read surface docs, go through the code properly"). Do not claim things you did not check; say what you did and did not verify.
- Wants the whole loop done by you: edit → build → run → check logs → report. They watch GUI windows and tell you what they see; where possible figure things out from logs/topics yourself.
- **Never ask them for their sudo password or put passwords in files.** See §2 for how to get root without it.
- They were frustrated about low disk space on C: (so everything heavy lives on D:). Don't install large things onto C:.
- Be concise in replies; give a recommendation instead of a survey of options.
- Destructive actions (deleting distros, files, force pushes): ask first unless they already clearly said to do it.

---

## 2. Environment (verified)

| Item | Value |
|---|---|
| Host | Windows 11 Pro, laptop named `Hrishikesh-Laptop` |
| WSL | WSL2, distro **`Ubuntu`** (24.04 LTS, Python 3.12.3), registered at **`D:\WSL\Ubuntu`** (`ext4.vhdx`) |
| Default user | `hrishikesh` (uid 1002, in `sudo` group). `/etc/wsl.conf` sets `[user] default=hrishikesh` |
| Disk | WSL virtual disk shows ~1 TB, ~9.6 GB used after installs. Real space is D: (≈136 GB free before install); C: had ≈30 GB free after cleanup |
| Other distro | `docker-desktop` (Docker Desktop's own WSL distro, still on `C:\Users\DELL\AppData\Local\Docker\wsl\main`, untouched) |
| ROS | **Jazzy** installed at `/opt/ros/jazzy` (desktop + gz, gz_ros2_control, ros2_control(ers), navigation2, nav2_bringup, rtabmap_ros, depthimage_to_laserscan, topic_tools, teleop_twist_keyboard, rmw_cyclonedds_cpp, colcon, rosdep, python3-psutil, python3-tk) |
| Repo (working copy) | `/home/hrishikesh/Swachh` (≈827 MB, incl. model weights) |
| Repo (stale original) | `/mnt/c/Users/DELL/Desktop/Swachh` |
| GUI | WSLg (Gazebo, RViz windows appear on the Windows desktop) |

### Getting root without a password
The user's Ubuntu password exists but **do not ask for it**. From inside WSL you can call the Windows `wsl.exe` through interop and start a root shell with no password:
```bash
wsl.exe -d Ubuntu -u root -e bash -c "apt-get install -y <pkg>"
```
(Windows interop is on by default. If it is disabled, ask the user to run the `apt` command themselves in an Ubuntu terminal and paste the result.) Use `sudo` only if the user types the password themselves.

### Leftover files on D: (safe to delete, ask first)
`D:\WSL\ubuntu-backup.tar` (stray, from a migration attempt, origin unclear), `D:\WSL\download\ubuntu-24.04-rootfs.tar.gz` (340 MB image used to create the distro), `D:\WSL\install_ros.sh`, `install_ros.log`, `check.sh`. From WSL these are under `/mnt/d/WSL/`.

### History of what was done to get here (so you don't redo it)
1. User had an older Ubuntu on C: (low disk). It was **unregistered/deleted** and a fresh Ubuntu 24.04 was imported to D: from the official WSL rootfs; user `hrishikesh` created; password set by the user.
2. Repo copied from Windows to `~/Swachh`; **CRLF→LF** normalised for text files (`.py .sh .xacro .yaml .xml .sdf .md .cpp .hpp .txt .ino .rviz`); `git config core.autocrlf input` set in that copy.
3. ROS Jazzy + all project dependencies installed via apt (log at `/mnt/d/WSL/install_ros.log`, ended with `INSTALL_DONE`).
4. VS Code is connected via the WSL extension (`Swachh [WSL: Ubuntu]`).

### Git state caveat
`git status` in `~/Swachh` shows **many files as modified**. That is only the CRLF→LF conversion (and `docs/PROJECT_STATUS.md`, `docs/HANDOFF.md` are new). **Do not blindly `git add -A`/commit.** Use `git diff --ignore-space-at-eol` / `-w` to see real changes. Branch `main`, has an `origin` remote. No commits have been made by the previous session. Large binaries are Git-LFS tracked (`.onnx .trt .pt .pth .engine .npz`).

---

## 3. Immediate next steps (do these first)

```bash
# 1. environment for every shell
cat >> ~/.bashrc <<'EOF'
source /opt/ros/jazzy/setup.bash
[ -f ~/Swachh/Navigation/Simulation/vacuum_ws/install/setup.bash ] && source ~/Swachh/Navigation/Simulation/vacuum_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file://$HOME/Swachh/Navigation/cyclone_dds.xml
export ROS_DOMAIN_ID=0
EOF
source ~/.bashrc

# 2. build
cd ~/Swachh/Navigation/Simulation/vacuum_ws
colcon build --symlink-install 2>&1 | tail -40
source install/setup.bash
```
`--symlink-install` means edits to Python nodes, launch files and YAML take effect **without rebuilding**; only new files or C++/CMake changes need `colcon build`.

```bash
# 3. first run (sim only)
ros2 launch vacuum_bringup sim.launch.py world:=apartment
# in a 2nd shell, ~15 s later:
ros2 control list_controllers     # joint_state_broadcaster + diff_drive_controller should be active
ros2 topic hz /odom               # ~30 Hz
ros2 topic hz /camera/depth/image_rect_raw
```
Things that may break the build/launch: a package missing from apt (re-check with `rosdep install --from-paths src --ignore-src -r -y`), Gazebo black/crashing window (`export LIBGL_ALWAYS_SOFTWARE=1`), slow real-time factor (run with `use_rviz:=false`).

Run long things (sim, exploration) **in the background with logs redirected to a file**, and poll the log; a single foreground command is limited to ~10 min.

---

## 4. How to run each stage (WSL — do NOT use start.sh)

`start.sh`, `run_mapping.sh`, `stop.sh`, `steer_gui.sh` hardcode `/home/bmscecse/...` paths and use `ptyxis` (a GNOME terminal that does not exist here). Launch directly:

| Stage | Commands |
|---|---|
| **4A manual mapping** | T1 `ros2 launch vacuum_bringup sim.launch.py world:=apartment` · T2 (after ~15 s) `ros2 launch vacuum_slam slam.launch.py environment:=apartment use_rviz:=false` · T3 `ros2 run vacuum_controller teleop_arrows.py` (or the steering GUI `robot_steering_gui.py`) |
| **4B autonomous exploration** | `rm -f ~/.ros/rtabmap.db*; ros2 launch vacuum_exploration exploration.launch.py environment:=apartment` (starts Gazebo T+0, RTAB-Map T+12 s, Nav2 T+20 s, exploration nodes + RViz T+28 s). Monitor: `ros2 topic echo /exploration/status`. Metrics land in `~/bags/stage4b/<env>/run_NN/metrics.csv` |
| **Save the map** | `mkdir -p ~/maps/stage5 && ros2 run nav2_map_server map_saver_cli -f ~/maps/stage5/apartment` (while exploration/SLAM is running; Nav2 relays `/rtabmap/map`→`/map`) |
| **5 AMCL navigation** | `ros2 launch vacuum_bringup sim.launch.py world:=apartment` then `ros2 launch vacuum_nav2 nav2_localization.launch.py map_path:=$HOME/maps/stage5/apartment.yaml`; in RViz use "2D Pose Estimate" first, then "Nav2 Goal" |
| Stop everything | `pkill -9 -f "gz sim"; pkill -9 -f ros; pkill -9 rviz2` |

World names accepted by `sim.launch.py`: `room` (=`empty_world.sdf`), `apartment`, `office`, `corridor`. `exploration.launch.py` also lists `warehouse` but no such world exists (falls back to the empty world), and `slam.launch.py` rejects `warehouse`.

### What you can verify yourself without seeing the GUI
- logs and `ros2 topic echo/hz`, `ros2 node list`, `ros2 control list_controllers`, `/exploration/status` (JSON: state, coverage_pct, goals completed/failed, frontiers remaining, blacklist count), `~/bags/.../metrics.csv`.
- Save the map and the camera image to PNG and open them with the image Read tool to "see" them: `map_saver_cli` produces a `.pgm`/`.yaml` (convert to PNG with `python3 -c "from PIL import Image; Image.open('x.pgm').save('x.png')"` if PIL is present, or ask the user to install `python3-pil`).
- Headless Gazebo is possible (`gz sim -s -r <world>`), so a fully non-GUI test is feasible when the user is not around.

---

## 5. Repository map

```
Swachh/
├── docs/                         PROJECT_CONTEXT.md (paper results), overall_progress_report.md, PROJECT_STATUS.md, HANDOFF.md (this), roadmaps…
├── Navigation/
│   ├── Manual mode/              real-hardware control
│   │   ├── arduino/swacch_robot/swacch_robot.ino   motor + peripheral firmware
│   │   └── hmi/                  GTK4 C++ touchscreen UI (src/, include/, scripts/)
│   ├── Simulation/vacuum_ws/src/ ROS 2 workspace (see below)
│   ├── tests/                    pytest suite (many empty tiers)
│   ├── start.sh run_mapping.sh save_map.sh view_map.sh stop.sh steer_gui.sh   (hardcoded paths, see above)
│   ├── cyclone_dds.xml           raises MaxAutoParticipantIndex to 200 (many nodes)
│   └── graphify.py               Gemini-API doc/graph generator (duplicate of vacuum_utils/scripts/graphify.py)
└── Object Detection/
    ├── Camera/vision/            stereo pipeline: main.py camera.py detector.py depth.py serial_comm.py config.yaml calib/ models/
    ├── Camera/network/           Pi↔GPU ZMQ link: rpi_publisher.py gpu_worker.py benchmark.py journal_benchmark.py network_config.yaml + rpi_setup/ gpu_setup/
    ├── Camera/streamlit_app/     demo app (custom 8-class model)
    ├── Model weights/            Yolov8 / Yolov11 / Rfdetr (.onnx, .trt, .pt) — Git LFS
    ├── Metrics/                  benchmark CSV/JSON results (scenario A and B)
    └── benchmark.py cli_benchmark.py trt_inference.py frame_protocol.py rpi_sender.py stats_utils.py app.py   Jetson benchmark suite
```

### ROS packages (`Navigation/Simulation/vacuum_ws/src/`)
| Package | Role |
|---|---|
| `vacuum_description` | xacro/URDF: `base_footprint`→`base_link` (chassis 0.30×0.25×0.10 m, z=0.093), 2 drive wheels (r=0.033, separation 0.268, axle x=−0.08), front caster, camera/arm/vacuum mount placeholders, D435i frames. All dimensions in `_properties.xacro` |
| `vacuum_gazebo` | worlds (`empty_world`=`vacuum_world`, `apartment_world`, `office_world`, `corridor_world`), `gz_bridge.yaml`, `camera.yaml` |
| `vacuum_controller` | `controllers.yaml` (diff_drive_controller, 50 Hz, odom 30 Hz), `cmd_vel_relay.py` (Twist→TwistStamped), `odometry_noise_node.py`, `motion_diagnostics_node.py`, `camera_diagnostics_node.py`, `teleop_arrows.py`, `robot_steering_gui.py` |
| `vacuum_bringup` | `sim.launch.py` master launch (robot_state_publisher, Gazebo, bridge, spawn at T+3 s, controllers), RViz config |
| `vacuum_slam` | RTAB-Map RGB-D + wheel odom (`rtabmap.yaml`, `slam.launch.py`, `map_saver.launch.py`) |
| `vacuum_nav2` | `nav2_params.yaml` (Smac Hybrid A* + MPPI, costmaps from `/scan_from_depth`), `amcl_params.yaml`, BTs `explore.xml`/`navigate.xml`, `nav2.launch.py` (Stage 4B), `nav2_localization.launch.py` (Stage 5) |
| `vacuum_exploration` | `frontier_detector.py`, `goal_selector.py` (library), `exploration_manager.py` (FSM), `frontier_visualizer.py`, `exploration_metrics.py`, `exploration_params.yaml`, `exploration.launch.py` |
| `vacuum_localization` | `localization_monitor.py`, `recovery_monitor.py`, `pose_quality.py`, `localization_metrics.py` |
| `vacuum_utils` | scripts: ATE/RPE (`evaluate_trajectory.py`, uses `evo`), `record_trajectory.py`, `benchmark_slam.py`, `benchmark_camera.py`, `collect_metrics.py`, `check_tf.py`, validate_*.sh |
| `vacuum_interfaces` | placeholder for custom msgs (no msgs defined) |

### Data flow (simulation)
```
Gazebo(gz_ros2_control) ──/joint_states,/tf(odom→base_footprint)──► diff_drive_controller
 teleop ─/cmd_vel─► cmd_vel_relay ─TwistStamped─► /diff_drive_controller/cmd_vel
 Nav2 controller/behavior/vel-smoother ─Twist─► /diff_drive_controller/cmd_vel_unstamped
 /diff_drive_controller/odom ─topic_tools relay─► /odom
 D435i (rgbd_camera) ─bridge─► /camera/color/image_raw, /camera/depth/image_rect_raw, camera_info, /camera/depth/points
 RTAB-Map(/odom + rgb + depth) ─► /rtabmap/map (OccupancyGrid) + map→odom TF
 nav2.launch relays /rtabmap/map → /map ; depthimage_to_laserscan → /scan_from_depth (Nav2 obstacle layer)
 frontier_detector(/rtabmap/map) ─/frontiers/centroids (PoseArray, z=size)─► exploration_manager ─NavigateToPose─► Nav2
 exploration_manager ─/exploration/status (JSON)─► exploration_metrics (CSV)
```
Launch timers: sim controllers spawn at T+2 s, helper nodes T+12–15 s; exploration launch staggers SLAM 12 s / Nav2 20 s / exploration 28 s. Hardcoded `prefix=['python3.12']` and `#!/usr/bin/env python3.12` shebangs (matches Ubuntu 24.04).

---

## 6. Known bugs found by code reading (NOT yet runtime-verified). Suggested fix order

### Priority A — will break the simulation's autonomy
1. **Velocity smoother feedback loop** — `vacuum_nav2/launch/nav2.launch.py` and `nav2_localization.launch.py`: controller_server, behavior_server **and** velocity_smoother's `cmd_vel` and `cmd_vel_smoothed` are all remapped to `/diff_drive_controller/cmd_vel_unstamped`. The smoother subscribes to and republishes the same topic (re-ingests its own output) and smoothing is bypassed. Fix: controller/behavior → `cmd_vel` (default, input of smoother), smoother input `cmd_vel`, output `cmd_vel_smoothed`→`/diff_drive_controller/cmd_vel_unstamped`; i.e. give the smoother a distinct input topic.
2. **Oscillation detector fires after 15 s on every goal** — `exploration_manager._odom_callback`: `_last_move_time` is only refreshed when the robot moves >0.05 m *between two consecutive odom messages* (~1 cm at 30 Hz × 0.3 m/s), so it almost never updates; after `oscillation_timeout_sec` (15 s) every goal is cancelled as "oscillation" (the 30 s `goal_timeout` is never reached). Fix: compare against a stored reference pose/time window (`oscillation_distance` param exists but is unused; 0.05 is hardcoded).
3. **Unstable frontier IDs for the blacklist** — `frontier_detector` assigns `id=idx` of the cluster list each cycle (cluster order comes from set iteration), and the manager re-enumerates poses each message, so blacklisted IDs map to different frontiers over time. `BlacklistEntry` stores centroids but never matches on them. Fix: blacklist by centroid proximity.
4. **Stale goal result race** — after `_cancel_goal()` the earlier `get_result_async` callback still fires later and sets `_goal_result=STATUS_CANCELED`, which can be consumed by the *next* goal in `NAVIGATING` and blacklist the wrong frontier. Fix: tag results with goal id/handle.
5. **`raise StopIteration` in the FSM timer callback** (FINISHED state): inside rclpy's coroutine-wrapped callback this likely becomes `RuntimeError`, not a clean exit. Cancel the timer / shut down properly instead.
6. **`slam.launch.py` ignores `delete_db`** — always passes `--delete_db_on_start` in mapping mode.
7. **Ground-truth bridge only valid for `vacuum_world`** — `gz_bridge.yaml` uses `/world/vacuum_world/pose/info`, but only `empty_world.sdf` is named `vacuum_world` (others: `apartment_world`, `office_world`, `corridor_world`). ATE ground truth is silently missing in the apartment etc. Fix: parametrize world name in the bridge/launch.

### Priority B — correctness / robustness
8. Frontier goal = raw cluster centroid; no snapping to nearest reachable free cell → many Nav2 rejections. `retry_count` and "adaptive threshold tightening" are declared/logged but not implemented.
9. Performance: `_find_frontier_cells` is a pure-Python double loop over every cell at 2 Hz; `_map_callback`/`_publish_status` count free/unknown cells with Python generators (status at 10 Hz). Vectorise with numpy.
10. `_check_completion`: `_no_frontier_count` increments each 10 Hz FSM tick (so "5 consecutive checks" = 0.5 s, not 5 detector cycles).
11. **Localization monitor false LOST** — `localization_monitor.py` flags LOST if no `/amcl_pose` for 3 s, but AMCL only publishes after motion (`update_min_d` 0.25 m) → stationary robot reported LOST. `recovery_monitor.py`: goal-cancel line `self._nav2_client._cancel_goal_async` is a no-op attribute access; the 360° spin is a blocking `time.sleep` loop inside a subscription callback (~12.6 s) and competes with Nav2 on `cmd_vel_unstamped`; retries (max 3) can't happen because recovery only triggers on a *transition* into LOST. `PoseQuality.classify` returns LOST at `>= cov_warning` so `cov_trace_lost` is effectively unused.
12. **Footprint**: Nav2 `robot_radius: 0.18` < chassis circumradius ≈0.195 m; wheel axle is 8 cm behind `base_footprint` centre, so front corner sweeps ≈0.26 m when rotating. Smac Hybrid Dubins with min radius 0.25 is more restrictive than needed for a differential-drive robot that can rotate in place; MPPI `vx_min: 0.0` forbids reversing.
13. `odometry_noise_node` publishes `/odom_noisy` but nothing consumes it (RTAB-Map uses `/odom`), so enabling noise has no effect on mapping; `rate_hz` param unused.
14. `evaluate_trajectory.py` treats wheel `/odom` as reference and expects `/rtabmap/odom` (may not exist when RTAB-Map uses external odom); uses `--correct_scale` which hides scale error.
15. `controllers.launch.py` comments contradict code (says controllers are auto-loaded and not spawned; code spawns them at T+2 s). `diff_drive_controller` limits (0.5 m/s, 2 rad/s) differ from Nav2 (0.3 m/s, 1 rad/s) — intentional but note it. `use_stamped_vel:false` in `controllers.yaml` vs. relay publishing TwistStamped — check against the installed Jazzy `diff_drive_controller` (Jazzy defaults to stamped; unstamped topic is `~/cmd_vel_unstamped`; `cmd_vel_timeout` was renamed `reference_timeout`). **Verify at runtime** that teleop and Nav2 both actually move the robot.
16. depth sensor HFOV: `_properties.xacro` defines separate colour (1.2112 rad) and depth (1.5010 rad) HFOV but the Gazebo `rgbd_camera` uses only the colour HFOV for both; also depthimage_to_laserscan uses the *colour* camera_info.

### Priority C — perception (`Object Detection/Camera/vision`)
17. **Depth unit bug**: calibration baseline = 0.1534 (metres) → `StereoDepth.compute()` returns X,Y,Z in **metres**, but HUD/serial/fallback treat them as **cm** (`fallback_depth` returns cm), and values are `round(.,1)` → **10 cm resolution**. Pick targets are unusable until fixed.
18. **Protocol mismatch**: `serial_comm.py` sends `ARM:PICK:<cls>,x,y,z,conf`; Arduino firmware only knows `ARM:ON/OFF` → replies `ERR:UNKNOWN_CMD`, so `send_pick()` always returns False. Also sent on every stable frame with no debounce/cooldown.
19. **Stereo calibration looks suspect** (`calib/stereo_calib.npz`, `calibration_values.yaml`): P1 principal point cx=681.9 on a 640-px image, fx=fy=1611 vs K≈1068/1083, rectification rotations ≈8–12°, large distortion (k1≈0.33, k2≈−0.34). Re-calibrate and check reprojection error before trusting depth.
20. Detection runs on the unrectified left frame, but depth is sampled from the rectified disparity map at the same (cx,cy) → coordinate mismatch.
21. **`detector._nms` transpose heuristic** (`ncols < nrows and ncols <= 6`) never transposes a real YOLOv8 output `(84, 8400)`/(12,8400) → likely garbage for the standard export. Unit tests only use `(N,85)`-style shapes. Verify with the real `models/yolov8s.onnx` output shape (not verified; `onnx` wasn't installed) and fix by transposing when `shape[0] < shape[1]`.
22. Two detector worlds: COCO `yolov8s` (7 whitelisted classes) in `vision/` vs. custom 8-class debris model (`aluminium_foil,bottle,cement_dust,floor,obstacle,paper,wooden_dust,wrapper`) in Streamlit/benchmarks. Decide which feeds the arm vs. the vacuum.
23. `HMI` and vision both want the same Arduino serial port (HMI default `/dev/ttyUSB0`, vision `/dev/ttyACM0`) — only one process can own it.
24. `network_config.yaml` Pi host `10.0.0.1` vs README `192.168.4.1`.

### Priority D — hardware safety (Arduino/HMI)
25. No watchdog/heartbeat in the firmware: motors keep running if the USB link/HMI dies mid-move. `delay(50)` blocks in move functions. Peripherals are state flags only (no pins). `AUTO` mode only sets a flag. HMI `send_command()` blocks the GTK main thread up to 500 ms and its ACK read can consume a `STATUS:` line instead of the ACK. Battery % is simulated.

### Priority E — paper validity (`Object Detection/*benchmark*`, `docs/PROJECT_CONTEXT.md`)
26. "Quantization gain" compares **ORT-CPU FP32** vs **TensorRT-GPU FP16/INT8** → backend and precision are confounded; add TensorRT-FP32 (and GPU ORT) baselines.
27. INT8 engines use **random-noise calibration** (`trt_inference._RandCalib`) and no mAP/accuracy comparison is reported.
28. Net transit = one RTT/2 constant from 20 pings applied to every frame (zero variance); `E2E FPS = 1000/mean(sum)` assumes serial stages.
29. Reported engine sizes in the write-up (8.6/4.8 MB) vs CSV `Size_KB` 11983.2 for FP32/FP16/INT8 alike (it reports the ONNX size).
30. `stats_utils.shapiro()` is actually D'Agostino–Pearson but labelled Shapiro–Wilk; "bias-corrected bootstrap" is a plain percentile bootstrap; `t_ppf` for df≥1e6 uses non-existent `math.erfinv`.
31. Model paths in `app.py`/`benchmark.py`/`cli_benchmark.py` use `yolov8/best_fp32.onnx` but the repo has `Model weights/Yolov8/...`; YOLOv11 INT8 path `best_int8 (1).onnx` vs `best_int8.onnx`. YOLOv11-seg INT8 fails on TRT 10.3.0 (documented, skipped). DMR for INT8 (47.1 %) > FP16 (41.3 %) despite lower mean E2E — worth checking.

---

## 7. Tests (`Navigation/tests`, `pytest.ini` markers per tier)

- Real content in: unit (`controllers`, `exploration/test_frontier_detector.py`, `navigation/test_pose_quality.py`, `vision/test_nms.py`, `vision/test_preprocess.py`), `regression/test_known_bugs.py`, `safety/test_velocity_limits.py`, `fault_injection`, `performance/test_nms_throughput.py`, `integration/ros_topics`. All other tiers are empty `__init__.py` stubs.
- **Vision tests are broken by the repo reorganisation**: they look for `Navigation/Camera/vision`, but the code is in `Object Detection/Camera/vision`. `conftest.py` mocks `cv2` and `rclpy`.
- `pytest` is not installed yet (`sudo`/root: `python3-pytest python3-yaml`), nothing was run. Safety tests read `nav2_params.yaml` directly (e.g. assert `vx_max <= 0.30`).

---

## 8. Hardware protocol reference (Arduino ↔ host)

115200 baud, `\n`-terminated. Replies `ACK:<cmd>` / `ERR:<reason>`; `STATUS:VAC=..,ARM=..,WPR=..,UV=..,AUTO=..,ESTOP=..,MOVE=..,SPD=..,PWM=..` every 1 s; `SWACCH:READY` on boot.
Commands: `MOVE:FORWARD|BACKWARD|LEFT|RIGHT|STOP`, `SPEED:1..9` (PWM 80,102,124,146,168,190,212,234,255), `VACUUM|ARM|WIPER|UV:ON|OFF`, `AUTO:ON|OFF`, `AI:ON|OFF`, `ESTOP` (latches, blocks commands), `RESET`.
Pins: left motor throttle D5 (PWM) + relay D7; right throttle D6 + relay D8; relay HIGH = forward. Tank turns by flipping one relay.
Not available in WSL without extra work (USB passthrough via `usbipd-win`). HMI build: `bash Navigation/Manual\ mode/hmi/scripts/setup.sh` then `run.sh` (GTK4, cmake).

---

## 9. What the previous session did NOT read / verify

Skimmed or unread: second half of `benchmark.py` (Streamlit UI), `network/benchmark.py`, `journal_benchmark.py` after line ~260, `frontier_visualizer.py`, `exploration_metrics.py` after line 150, `localization_metrics.py`, `teleop_arrows.py`, `robot_steering_gui.py`, most of `gui.cpp`/`logger.cpp`, `camera_diagnostics_node.py`, `vacuum_utils/scripts/*` (except `evaluate_trajectory.py`/`graphify.py` heads), SDF worlds (only world names), RViz configs, `slam` map_saver launch, `navigate.xml`, Pi setup scripts, `docs/*` roadmaps beyond headings. Nothing was run. `onnx`/`pytest` were not available to check model shapes or run tests.

---

## 10. Suggested plan for the next session

1. Build the workspace (§3), launch the sim, confirm controllers + `/odom` + camera topics + TF (`ros2 run tf2_tools view_frames` or `ros2 run vacuum_utils check_tf.py`).
2. Confirm that teleop and Nav2 commands actually move the robot (bug §6.15), then fix §6.1 (velocity smoother) and re-verify.
3. Run exploration; confirm the 15 s oscillation cancel (§6.2) from logs; fix §6.2–§6.5; re-run and compare coverage % / goals completed in `/exploration/status` and `metrics.csv`.
4. Fix §6.6, §6.7; produce a saved map and view it as a PNG.
5. Stage 5: AMCL navigation on the saved map; fix §6.11 monitor issues.
6. Then (separately, hardware side): §6.17–6.21 vision/arm fixes, Arduino `ARM:PICK` handler + watchdog, ROS↔Arduino bridge node.
7. Repair the test paths (§7), install pytest, make the suite runnable in Ubuntu.
8. Paper-side fixes (§6.26–6.31) when the user asks.

## 11. Open questions to ask the user when relevant

- Which world(s) should be the primary test environment (apartment is the default everywhere)?
- Should vision for the arm use the COCO model or the custom debris model?
- Does the user want fixes committed to git (note the CRLF-noise in `git status`; they may prefer a clean branch)?
- Is the Windows Desktop copy to be kept as a backup or synced back after changes?
