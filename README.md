# Swachh Bauddhika Yantra (SBY)

An autonomous indoor cleaning robot: it explores and maps a room, plans paths around obstacles, detects trash with a camera, and (in the design) picks it up with an arm and vacuums the floor. This repository holds the robot's navigation stack and simulator, the object-detection code and models, the manual-control HMI and firmware, a simulation evaluation framework, and the research paper draft.

> **Read this first: what is real and what is not.**
> - **Simulation (measured):** SLAM, exploration, navigation and obstacle avoidance were evaluated in Gazebo only. Nothing from that campaign ran on the physical robot or the Jetson.
> - **Hardware (implemented):** manual driving through the Arduino firmware and GTK HMI. The firmware drives the two motors only; vacuum, arm, wiper and UV commands just set flags.
> - **Vision (prototype):** the checked-in pick pipeline uses two USB cameras as a stereo pair with a generic COCO YOLOv8s detector (7 classes). The custom 8-class detectors in the paper are benchmarked but not wired into that pipeline.
> - **Design only:** the decision/fusion module and the semi-automatic and automatic modes.

## Where to go

| I want to… | Read |
|---|---|
| Run something end to end | [docs/USER_MANUAL.md](docs/USER_MANUAL.md) |
| Read the whole project as one story | [explainer/00_the_story.md](explainer/00_the_story.md) |
| Understand how everything works, high level to low level | [explainer/README.md](explainer/README.md) |
| See the evaluation results and how they were produced | [docs/EVALUATION_FINDINGS_2026-10-25.md](docs/EVALUATION_FINDINGS_2026-10-25.md), [docs/METRICS_AUDIT_2026-10-25.md](docs/METRICS_AUDIT_2026-10-25.md) |
| See which metrics were measured | [docs/METRICS_STATUS.md](docs/METRICS_STATUS.md) |
| Rebuild the paper tables and figures | [docs/paper_out/](docs/paper_out/) (see the manual, section 7) |
| Read the paper draft | [paper.txt](paper.txt) (LaTeX source) |

## Repository layout

| Path | What it is |
|---|---|
| `Navigation/Simulation/vacuum_ws/` | ROS 2 workspace: robot model, Gazebo worlds, RTAB-Map SLAM, Nav2, frontier explorer, controllers, evaluation framework (`vacuum_eval`) |
| `Navigation/start.sh`, `stop.sh`, … | Launch helper scripts (some contain paths from another machine; see the manual) |
| `Navigation/Manual mode/` | Arduino firmware and GTK HMI for manual driving |
| `Navigation/tests/` | Mocked-ROS unit tests |
| `Object Detection/` | Detection benchmark scripts, model weights (YOLOv8, YOLOv11-seg, RF-DETR), and the camera/stereo pick pipeline |
| `docs/` | Plans, metric definitions and status, audits, specs, paper-section drafts |
| `explainer/` | Deep explanations of every part of the code |
| `results/` | Recorded evaluation runs |
| `paper.txt` | Research paper draft (LaTeX) |

## Latest results (simulation, reduced 4-hour test campaign)

31 test episodes in Gazebo: 9 exploration (odometry noise on), 12 navigation, 6 obstacle avoidance, 4 responsiveness (2 invalid by design). All values are script-computed from the run files and carry wide intervals because of the small number of seeds.

| Metric | Result |
|---|---|
| Explored floor coverage (exploration) | 61.4 % [18.5, 88.0]. Office 83.8, multi-room loop 86.3, maze 14.3 (in two of three maze runs the explorer sent no goal) |
| SLAM trajectory error (ATE) | 0.57 m [0.33, 0.86], 7 episodes. Wheel odometry alone: 2.54 m in the same episodes |
| Loop-closure precision | 35.2 % of 1051 accepted closures (a lower bound) |
| Navigation success | 29.2 % of 178 goals confirmed by ground truth (Nav2 itself reported 50.0 %) |
| Obstacle avoidance trials | 4 of 6 (static trap 3/3, sudden moving box 1/3) |
| Response to a velocity command | 166 ms to half speed, 260 ms to stop |

Why navigation success is low: the dominant failure is Nav2 refusing to plan because the AMCL pose put the robot's footprint inside a wall. This is a localisation set-up issue and not a measure of the RTAB-Map pipeline. Details and caveats are in `docs/EVALUATION_FINDINGS_2026-10-25.md`.

## Quick start (simulation)

Requires Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic, RTAB-Map and Nav2 (full list in the manual).

```bash
cd Navigation/Simulation/vacuum_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
ros2 launch vacuum_bringup sim.launch.py world:=office
```

The manual covers exploration, navigation, the evaluation harness, the detection tools and the hardware.

## Known issues

- `Navigation/run_mapping.sh` and `save_map.sh` hard-code paths from another machine and will not run as written; the manual gives direct commands.
- `Navigation/stop.sh` force-kills processes by pattern and deletes `~/.ros/rtabmap.db*`; do not use it during evaluation runs.
- `Navigation/graphify.py` sends workspace snippets to the Gemini API unless run with `--no-ai`.
- 41 of the 126 tests under `Navigation/tests` fail because they import `Navigation/Camera/vision/detector.py`, which now lives in `Object Detection/Camera/`.
- Config comments in `rtabmap.yaml` call feature type 6 "ORB"; in RTAB-Map 0.23 it is GFTT/BRIEF.
- Benchmark files record no hardware identifier, so the Jetson attribution of the latency numbers rests on the scripts and project notes.

More in the explainer files (each lists the doc-versus-code disagreements it found).

## Safety

The base is motor-driven and the firmware has no command timeout: the last motion command keeps running until `MOVE:STOP`, `ESTOP`, `RESET` or a power cycle. Test with the wheels off the ground first.

## Licence and citation

No licence file is present in the repository. Contact the authors before reuse.
