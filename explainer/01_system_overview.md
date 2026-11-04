# 01. System overview: Swachh Bauddhika Yantra (SBY)

Audience: a new engineer or student with no prior context.
Rule used while writing: every claim comes from `paper.txt`, `docs/PROJECT_CONTEXT.md`, `docs/SESSION_CONTEXT.md`, `docs/REQUIREMENTS.md`, `docs/REPO_FACTS_ITEMS_1_TO_25.md`, or the code. Where the repo says nothing, this file says "not documented". Where docs and code disagree, the code was checked and the disagreement is noted.

Spelling note: the repo uses "Swachh Bauddhika Yantra" (paper), "Swachh Boudhik Yantra" (docs, code READMEs) and "SBY" for the same project.

---

## 1. What the robot is for

SBY is an autonomous indoor cleaning robot built by a university team. It is meant to:

- find and map the room it is in (no prior floor plan),
- drive around safely,
- spot trash with a camera and neural-network detector,
- pick trash up with a robotic arm (up to 0.5 kg payload) and vacuum dust and small debris.

The project has a paper target (a Q1 journal) with three kinds of work behind it:

1. a trash-detection model study (YOLOv8n, YOLOv11n-seg, RF-DETR on an 8-class custom dataset),
2. an edge-computing benchmark of detection on the Jetson (local vs wireless),
3. a simulation study of mapping, exploration and navigation (ROS 2 + Gazebo).

The real robot prototype does manual driving and has detection code; the autonomous navigation was evaluated only in simulation (see section 7).

---

## 2. Hardware

### 2.1 Robot specifications (from paper Table "Physical and System Specifications")

| Item | Value |
|---|---|
| Body | Metal chassis, 3 levels, about 0.60 m long x 0.50 m wide (the spec table lists 0.61 x 0.46 x 0.91 m high) |
| Total weight | 50 kg (the table lists chassis 30 kg and wheels 20 kg) |
| Payload | 20 kg; arm payload 0.5 kg |
| Drive | Two 6-inch (about 15.2 cm) brushless DC hub motors at the rear, one per side, with YL 12 / 24 V sine-wave controllers; one free caster wheel at the front centre |
| Max speed | 30 rpm |
| Power | 24 V, 26 Ah rechargeable battery (two lead-acid batteries), about 2 h runtime, charged from 230 V / 50 Hz mains; DC-DC buck converters step down for each component |
| Racks | Bottom: batteries and the arm base area at the front. Middle: Jetson, Arduino, relays, vacuum cleaner. Top: HMI touchscreen |

Inconsistency to know about: the paper table says "Locomotion actuation: 12 V DC Servo Motors", while the paper text and the Arduino firmware describe BLDC hub motors with relay direction control. The text and firmware are the more detailed sources. Also, the wheel track and encoder resolution of the real robot are "NOT FOUND" (REPO_FACTS item 10).

### 2.2 Compute

| Device | Role | Source |
|---|---|---|
| NVIDIA Jetson Orin Nano (8 GB; benchmark setup L4T R36.4, CUDA 12.6, TensorRT 10.3.0) | Onboard "brain": perception, mapping, decisions, runs the HMI | paper, PROJECT_CONTEXT |
| Arduino (paper says Uno) | Low-level actuator control; isolates the Jetson from motors and relays | paper, `.ino` firmware |
| Raspberry Pi (RPi) | Used as a wireless camera sender in the "Scenario B" benchmark (RPi -> Wi-Fi -> Jetson). `Object Detection/Camera/network/README.md` also describes an RPi 5 -> Windows GPU machine pipeline | PROJECT_CONTEXT, code |

Caveat from REPO_FACTS: a note in `Navigation/Manual mode/claude_context.md` says the project moved from the Jetson to a Raspberry Pi 5; the authors state the Jetson is the robot's computer. The Jetson's ROS version is not documented.

### 2.3 Sensors

| Sensor | Use | Notes |
|---|---|---|
| Logitech C270 HD webcam | Trash detection | Paper: 30 fps. The code (`vision/config.yaml`) opens two cameras at 640x480, 10 fps |
| Intel RealSense D435i depth camera | Intended input to RTAB-Map SLAM | Paper says both cameras stream 30 fps over USB-A. How the real D435i is mounted: not documented |
| Wheel encoders | Wheel odometry | The paper says they are used, but the Arduino sketch has no encoder code and no encoder specs are documented |
| Microphone and speaker | Voice "STOP" command and audio feedback | Mentioned in the paper; implementation not found in the folders checked |

Deployed-prototype caveat: the vision code in `Object Detection/Camera/vision` uses two USB webcams as a stereo pair (StereoSGBM disparity to depth) and a generic COCO YOLOv8s model, not the custom 8-class model and not the D435i. See section 7.

### 2.4 Actuators

| Actuator | Detail |
|---|---|
| Wheels | Two BLDC hub motors; the Arduino turns commands into PWM throttle plus relay direction switching |
| Vacuum cleaner | Switched on/off by the Arduino (paper); in the firmware it is only a state flag (see below) |
| Robotic arm | 6-DOF, 3D-printed PLA+; MG996R servos on main joints, MG90S on wrist and gripper; parallel-jaw gripper |
| Other (listed in firmware/HMI) | Wiper/spray and UV; also flag-only in the firmware |

Firmware facts (`Navigation/Manual mode/arduino/swacch_robot/swacch_robot.ino`): the VACUUM, ARM, WIPER and UV commands only set state flags ("no dedicated pins, just track state for HMI"). Only the motors have real output. `AUTO:ON/OFF` only sets a flag, and `AI:ON/OFF` is acknowledged and does nothing.

### 2.5 Jetson <-> Arduino link

- Serial, 115200 baud, 8N1, newline-terminated ASCII (paper; matches README and firmware).
- Commands: `MOVE:FORWARD/...`, `SPEED:1..9`, `VACUUM|ARM|WIPER|UV:ON|OFF`, `AUTO`, `AI`, `ESTOP`, `RESET`.
- Replies: `ACK:<cmd>` or `ERR:...`, plus `STATUS:` once per second.
- Known weaknesses (REQUIREMENTS section 7): no watchdog (motors keep running if the link dies), blocking `delay`s, battery level is simulated.

---

## 3. Software subsystems

| Subsystem | What it does | Main technology | Status |
|---|---|---|---|
| Perception (trash detection) | Finds trash in camera images; with stereo, estimates distance | YOLOv8 / YOLOv11-seg / RF-DETR (training study); YOLOv8s + TensorRT on Jetson (deployed code) | Trained and benchmarked; see caveats |
| SLAM | Builds a 2D occupancy map and the robot pose | RTAB-Map (RGB-D), ROS 2 Jazzy | Simulation |
| Exploration | Picks the next frontier (known-free next to unknown) as a goal | Custom Python node (`vacuum_exploration`) | Simulation |
| Navigation | Global path + local control + recovery behaviours | Nav2: Smac Hybrid-A* planner (Dubins), MPPI controller, behaviour trees | Simulation |
| Decision / modes | Fuses perception and navigation into one high-level action | Described in the paper | Design-only (section 6) |
| HMI | Touchscreen GUI for manual control, status, e-stop | GTK4, C++ | Real, manual mode only |
| Evaluation framework | Runs episodes, records data, computes metrics | `vacuum_eval` | Simulation only (not part of the robot) |

### 3.1 Perception

- Dataset: custom, 8 classes: aluminium foil, bottle, cement dust, floor, obstacle, paper, wooden dust, wrapper. Models trained on an NVIDIA RTX A6000 (paper).
- Edge benchmark (PROJECT_CONTEXT): YOLOv8 and YOLOv11-seg on the Jetson, FP32 (ONNX Runtime CPU), FP16 and INT8 (TensorRT). Scenario A runs locally; Scenario B streams from an RPi over Wi-Fi. YOLOv11-seg INT8 failed to build on TensorRT 10.3.0.
- Deployed vision code (`Object Detection/Camera/vision/`): captures two cameras, runs YOLOv8s, filters to 7 COCO classes (bottle, cup, remote, cell phone, book, scissors, toothbrush), computes depth by stereo, and sends `ARM:PICK` to the Arduino after the object appears in 2 consecutive frames at confidence of at least 0.50.

### 3.2 SLAM (RTAB-Map)

Takes colour and depth images plus wheel odometry and outputs a 2D occupancy grid (5 cm cells) and the `map` -> `odom` transform. The map feeds Nav2 costmaps and the explorer. In the simulation, no visual-odometry node runs; RTAB-Map uses wheel odometry from the simulated diff-drive controller (REPO_FACTS items 5, 6). Feature type is GFTT/BRIEF (the config comment saying "ORB" is wrong).

### 3.3 Exploration

A custom node pair: `frontier_detector` (2 Hz scan of the map for free cells next to unknown cells, clustered) and `exploration_manager` (state machine that scores frontiers, snaps goals to safe cells, sends a Nav2 goal, blacklists failures, and declares completion when no frontiers remain and the map stops growing). Score = `1.0*ln(1+cells) - 1.5*distance - 0.8*obstacle_penalty`. No coverage planner exists (no boustrophedon sweep); that word appears only in tests and future-work notes.

### 3.4 Navigation (Nav2)

- Global planner: Smac Hybrid-A*, Dubins motion model, minimum turning radius 0.25 m. This is a fixed project decision.
- Local controller: MPPI at 20 Hz, limited to 0.30 m/s and 1.0 rad/s in the sim configuration.
- Costmaps: static layer from the SLAM map plus a spatio-temporal voxel layer fed by a "scan" made from the depth image.
- Recovery: behaviour trees (clear costmaps, back up, spin, wait). Two trees exist: `explore.xml` (has BackUp) and `navigate.xml` (no BackUp).

### 3.5 HMI

A GTK4 C++ touchscreen app (`Navigation/Manual mode/hmi`) that sends the serial commands above. The paper also describes live video, detection overlays, preset arm sequences and an audio "STOP" input. The README shows the HMI source and the Arduino firmware; whether every paper feature exists in the code was not checked in detail.

---

## 4. How the pieces connect (data flow)

Target architecture from the paper (four layers) with what the code actually does annotated.

```
 INTERFACE LAYER             SENSOR LAYER
 +--------------------+     +-------------------------------------------+
 | HMI touchscreen    |     | C270 webcam(s)   D435i depth   Encoders    |
 | Microphone/Speaker |     +-----+---------------+-------------+-------+
 +----------+---------+           |               |             |
            |                     v               v             v
            |           PROCESSING LAYER  (Jetson Orin Nano)
            |           +----------------+   +---------------------------+
            |           | Object         |   | Visual SLAM (RTAB-Map)    |
            |           | Detection      |   |  -> occupancy grid + pose |
            |           | (YOLO etc.)    |   +-------------+-------------+
            |           +-------+--------+                 |
            |                   |            +-------------v-------------+
            |                   |            | Frontier explorer -> Nav2 |
            |                   |            | (Smac Hybrid-A*, MPPI)    |
            |                   |            +-------------+-------------+
            |                   v                          v
            |           +--------------------------------------------+
            +---------->|  DECISION MODULE ("orchestrator")  [design]|
                        |  fuses detection + navigation -> 1 action  |
                        +----------------------+---------------------+
                                               | ASCII over serial
                                               | 115200 8N1
                        ACTUATOR LAYER         v
                        +--------------------------------------------+
                        | Arduino: parses cmd, PWM + relays          |
                        +----+-----------+-----------+---------------+
                             v           v           v
                         Hub motors    Vacuum    Robotic arm (+wiper, UV)
```

What is wired together in practice:

| Link | Real or not |
|---|---|
| HMI -> Arduino (manual driving, flags) | Real (code in `Navigation/Manual mode`) |
| Cameras -> detector -> depth -> `ARM:PICK` to Arduino | Code exists in `Object Detection/Camera/vision`, but firmware does not understand `ARM:PICK` |
| Sensors -> RTAB-Map -> explorer -> Nav2 | Runs in the ROS 2 / Gazebo simulation only; its output goes to the simulated diff-drive controller, not to the Arduino |
| Detection + navigation -> Decision -> Arduino | Not implemented as a working module (design-only) |

Simulation command path (REQUIREMENTS section 4): Nav2 -> `/cmd_vel_nav` -> velocity smoother -> `/cmd_vel_smoothed` -> relay -> stamped `/diff_drive_controller/cmd_vel`.

---

## 5. Operating modes (paper, "Operating Modes")

| Mode | Operator's role | Implementation status |
|---|---|---|
| Manual | Full control of speed, direction, vacuuming and spot cleaning through the HMI; sees video, warnings and status | The paper states this mode "has been implemented completely" |
| Semi-automatic | Chooses the area, cleaning type and duration; the robot cleans autonomously inside it | Described only; no implementation found |
| Automatic | Robot maps, finds dirty areas, decides vacuum vs mop and cleans with no operator input | Described only. The navigation part (exploration + Nav2) exists in simulation; the cleaning/decision part does not |

Safety (paper): an emergency stop from the HMI or the spoken word "STOP" halts execution until explicitly reset. The firmware handles `ESTOP`/`RESET` and rejects commands while stopped. The microphone path is not documented in the code checked.

---

## 6. Real hardware vs simulation vs design-only

| Capability | Real hardware | Simulation | Design-only |
|---|---|---|---|
| Hub-motor driving via HMI + Arduino (manual mode) | Yes | | |
| Vacuum / arm / wiper / UV switching | Flags only in firmware (no dedicated pins) | | Physical actuation not shown in the firmware |
| Trash detection YOLO benchmarks on Jetson | Yes (latency, FPS, power) | | |
| Stereo-camera depth + `ARM:PICK` sender | Code exists | | |
| Arm motion for picking | | | Servo control sequence is only a commented-out outline in the paper |
| RTAB-Map SLAM, frontier exploration, Nav2 navigation | Not documented on the robot or Jetson (REPO_FACTS item 25: "NOT FOUND") | Yes, ROS 2 Jazzy + Gazebo Harmonic, with a smaller scaled robot model | |
| Decision module (fusion of detection + navigation) | | | Yes |
| Semi-automatic and automatic modes | | Navigation portion only | Yes |
| Voice STOP, return-to-charge | | | Mentioned in paper (return-to-charge is commented out); not found in code |
| Method comparison with other planners (metric 13) | | | On hold by user decision |

Simulated robot vs real robot: the simulation uses a scaled model (0.30 x 0.25 m footprint, camera at 0.18 m) while the real robot is about 0.60 x 0.50 m and 50 kg. The simulated camera is a D435i-like RGB-D sensor with zero noise.

---

## 7. Known caveats (read before trusting any claim)

1. Deployed prototype vs paper: the checked-in vision code uses two USB webcams as a stereo pair and a generic COCO YOLOv8s model with 7 allowed classes, not the custom 8-class model and not the D435i. The paper's trained models (YOLOv8n, YOLOv11n-seg, RF-DETR) are a separate study.
2. Fusion / mode logic is design-only. Nothing in the repo implements the Decision module or the semi-automatic and automatic modes. The explorer only knows about frontiers; it never receives trash detections.
3. `ARM:PICK` is unsupported by the Arduino firmware. The vision sender emits `ARM:PICK:<cls>,<X>,<Y>,<Z>,<conf>` but the firmware only handles `ARM:ON` and `ARM:OFF`; anything else returns `ERR:UNKNOWN_CMD`. Even those two only toggle a flag.
4. Other perception issues recorded in REQUIREMENTS section 7: mixed metre/centimetre depth units, suspect stereo calibration (cx outside the image), detection on the unrectified frame but depth from the rectified one, a likely wrong NMS transpose heuristic for the standard `(84, 8400)` output, HMI and vision both wanting one serial port, and inconsistent RPi IPs (10.0.0.1 vs 192.168.4.1).
5. Edge benchmark: "quantization gain" confounds backend and precision (ORT-CPU FP32 vs TensorRT FP16/INT8); INT8 was calibrated on random noise (REQUIREMENTS section 7).
6. Navigation is simulation only, and the paper's wheel-odometry equations use the simulated wheel parameters. The Jetson was never shown running RTAB-Map, the explorer or Nav2.
7. Simulation results in the paper come from a frozen stack (freeze commit `92c7757`, 2026-10-25). Fixed decisions: Smac Hybrid DUBIN planner stays; no physics fudge factors; metric 13 is on hold.
8. Odometry noise in the simulation is a custom node (`odom_noise_node`), active only with `odom_mode:=eval`.

---

## 8. Map of the repo

| Folder | Subsystem | What is in it |
|---|---|---|
| `paper.txt` | Paper | LaTeX draft (Methodology, Navigation, Results) |
| `Object Detection/` (top level: `app.py`, `benchmark.py`, `trt_inference.py`, `rpi_sender.py`, `frame_protocol.py`) | Perception / edge benchmark | Local vs wireless YOLO benchmarking on Jetson |
| `Object Detection/Camera/vision/` | Perception (deployed code) | Camera capture, YOLOv8s TensorRT, stereo depth, serial sender, calibration |
| `Object Detection/Camera/network/` | Perception (distributed) | RPi publisher and GPU worker over ZMQ |
| `Object Detection/Camera/streamlit_app/` | Perception demo | Streamlit app with a custom YOLOv8 model (`new_yolov8_best.*`) |
| `Object Detection/Model weights/`, `Metrics/` | Perception | Weights and benchmark outputs |
| `Navigation/Manual mode/` | HMI + Arduino | `hmi/` (GTK4 C++), `arduino/swacch_robot/swacch_robot.ino` firmware |
| `Navigation/*.sh` | Helper scripts | Contain hardcoded paths for the lab workstation (`/home/bmscecse/...`) per REQUIREMENTS |
| `Navigation/Simulation/vacuum_ws/src/` | Simulation workspace (ROS 2 Jazzy) | See next table |
| `Navigation/Simulation/scripts/` | Machine setup | `setup_machine.sh`, `preflight.sh` |
| `Navigation/Simulation/Documentation/` | Lab workstation docs | Software stack notes |
| `docs/` | Documentation | Plans, specs (`docs/specs`), metric tracker, findings, run state |
| `results/` | Evaluation output | Run folders, indexes, metric tables |
| `explainer/` | This explainer series | You are here |
| `council/`, `progress/` | Process records | LLM-council notes and periodic progress reports |
| `large_files/` | Large local data | Ignored by git; kept on the machine `victus` only |

ROS 2 packages inside `Navigation/Simulation/vacuum_ws/src/`:

| Package | Role |
|---|---|
| `vacuum_description` | Robot model (URDF/xacro): chassis, wheels, camera, sensors |
| `vacuum_gazebo` | Gazebo worlds (evaluation worlds and `avoid_*` scenarios) and bridge config |
| `vacuum_bringup` | Launch files that start the simulation (`sim.launch.py`) |
| `vacuum_controller` | Command relay (`cmd_vel_relay`), teleop, diagnostics, a legacy odometry-noise node |
| `vacuum_slam` | RTAB-Map launch and config (`rtabmap.yaml`) |
| `vacuum_nav2` | Nav2 parameters, launch files, behaviour trees (`explore.xml`, `navigate.xml`) |
| `vacuum_exploration` | Frontier detector, goal selector, exploration manager |
| `vacuum_localization` | Localization monitoring and pose-quality / recovery monitors |
| `vacuum_eval` | Episode harness, recorder, ground truth, noise node, metrics, statistics and report tooling |
| `vacuum_interfaces`, `vacuum_utils` | Shared message definitions and utility scripts |

---

## 9. Where to go next

- Navigation and evaluation details: `docs/REPO_FACTS_ITEMS_1_TO_25.md` (parameters with line numbers), `docs/SESSION_STATE.md`, `docs/EVALUATION_FINDINGS_2026-10-25.md`.
- Hardware and benchmark numbers: `docs/PROJECT_CONTEXT.md`.
- Metric definitions and rules: `docs/specs/13_preregistration.md`.

---

One-line summary: this file gives a plain-English tour of SBY, covering purpose, hardware, subsystems, data flow, modes, real vs simulated vs design-only status, key caveats, and a folder-to-subsystem map of the repo.
