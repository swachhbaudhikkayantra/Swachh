# Content facts (single source of truth for deck + poster)

Every number on the deck and poster must come from this file. Source keys:
**P** = Submitted Paper (my_paper.txt, identical numbers to the PDF), **V** = NAV_VERIFICATION.md (code/results check),
**P2** = Major Project Phase 2 PPT, **VD** = SBY_IEEE_Video_Deck.

## Project identity
- Paper title (P): Design and Development of Navigation System and Trash Detection for Swachh Bauddhika Yantra. Submitted to IEEE Access.
- Phase 2 title (P2 slide 1, reused verbatim as deck slide 1): Design and Development of Precision Motion Control with Obstacle Avoidance and Trash Detection for Swachh Bauddhika Yantra.
- CSE team (P2): Sanjana Srinivas 1BM23CS301, Shashank U 1BM23CS314, Siripurapu Manaswi 1BM23CS331, Hrishikesh R Prasad 1BM23CS367. Guide Dr. Umadevi V (CSE); co-guide Dr. Veena N Hegde (ECE).
- ECE team (P2/P): Shreesha S, Rajat C Athani, Raviteja M, Preetham N. Multidisciplinary CSE + ECE.
- Support (P): Faculty Research Program Scheme (FRPS) Scheme 3, BMSCE. Acknowledged: Anand Iyer (Innovative Consulting Inc, ISA-ACARD), Vishwajeet Gokhale (CEO, Tantradnya, Pune).
- SDG 11 Sustainable Cities and Communities (P2).
- Dataset public: github.com/manaswi-siripurapu/swachh-bauddhika-yantra (full set on request) (P).

## Problem and gap (P, P2)
- Manual cleaning of large indoor spaces: labour-heavy, slow, inconsistent; workers may handle hazardous waste (P2).
- Existing robots vacuum/mop; no end-to-end system combining object detection, motion control and obstacle avoidance (P).
- Gaps (P): (1) DL trash detection in cleaning robots relies on external processing; (2) onboard DL detection not integrated with autonomous navigation.

## Vision / full scope (P)
- SBY = indoor cleaning robot: navigate, detect + classify trash, pick it with a 6-DOF arm, vacuum dust. Three modes: manual, semi-automatic, automatic.
- Architecture: Interface layer (HMI, mic, speaker) → Sensor layer (RGB cams, D435i, wheel encoders) → Processing layer on Jetson Orin Nano (Object detection; Visual SLAM: mapping, localisation, path planning, navigation, obstacle avoidance; Decision module = orchestrator) → Actuator layer (Arduino Uno → actuators). Actuator-agnostic.
- Decision fusion (P Table): bottle / plastic wrapper / paper / foil → activate robotic arm; obstacle → replan path.

## Hardware prototype (P Table 1 + text)
- 3-rack metal chassis ~0.61 × 0.46 × 0.91 m; total 50 kg; payload 20 kg; arm payload 0.5 kg; max speed 30 rpm.
- Two 6-inch BLDC hub motors (rear) with YL 12, 24 V sine-wave controllers; front free caster.
- 24 V 26 Ah battery, ~2 h runtime, 230 V 50 Hz charging; DC-DC buck converters.
- Jetson Orin Nano (8 GB) + Arduino Uno; Logitech C270 + Intel RealSense D435i, 1280×720 at 30 fps over USB.
- Racks: top HMI; middle Jetson, Arduino, relay, vacuum with suction pipe; bottom two lead-acid batteries; arm at front.
- Arm: 6-DOF, 3D-printed PLA+, MG996R (main joints) + MG90S (wrist, gripper), ≤ 500 g.

## Manual mode on hardware (P + V, code-verified only)
- DONE: prototype performs manual mode (P abstract, conclusion; photos P Fig 2, P2 slides 22-23).
- HMI: fullscreen GTK4 (C++) touchscreen: Forward / Left / Right / STOP, 9 speed levels, EMERGENCY STOP + Reset, toggles for Vacuum / Arm / Wiper / UV, Auto toggle (V).
- Link: Jetson ↔ Arduino serial 115200 baud, newline-terminated ASCII commands (e.g. SPEED:8; MOVE:FORWARD), ACK per command, STATUS every 1 s (P + V).
- Firmware: MOVE:FORWARD/BACKWARD/LEFT/RIGHT/STOP, SPEED:1..9 → PWM 80..255, ESTOP / RESET; 2 PWM motor outputs + 2 direction relays (V). ESTOP halts motors and blocks motion until RESET (P + V).
- Single execution path for manual and autonomous commands; safety-first e-stop (P).
- NOT done (V): vacuum/arm/wiper/UV are state flags only (no actuation pins); battery level on HMI simulated; no hardware test log; voice "STOP", wheel encoders, distance/angle commands, HMI video feed, start-up self-check = described in paper but not in code → present as designed / to do.

## Subsystem 1: Navigation (P §VI, verified V)
- ROS 2 Jazzy, Nav2, Gazebo simulator. Closed loop: RTAB-Map → frontier explorer → Smac Hybrid-A* → MPPI.
- RTAB-Map: RGB-D + wheel odometry, 3-DoF registration, 2D grid 5 cm cells, ground ≤ 0.03 m, obstacles 0.03–0.30 m, 1 Hz map update, loop closure via bag-of-words. Chosen: open source, odometry-independent, memory management suits 8 GB Jetson; most accurate indoors vs ORB-SLAM3/OpenVSLAM on TUM RGB-D in [merzlyakov2021].
- Frontier explorer (custom, 2 Hz): frontier = free cell with unknown 4-neighbour; flood-fill clusters in 0.5 m window, ≥ 5 cells, ≥ 0.5 m; score S = 1.0 ln(1+n) − 1.5 d − 0.8 p; snap to free cell with 0.30 m clearance within 1.5 m; cancel on Nav2 failure, 30 s, or < 0.30 m in 15 s; blacklist 60 s; stop after 5 empty cycles + < 10 new free cells in 15 s + stationary.
- Smac Hybrid-A*: Dubins, forward-only, min turning radius 0.25 m, goal tolerance 0.30 m, unknown traversable, 5 s cap.
- Costmaps: global 5 cm, RTAB-Map grid + spatio-temporal voxel layer + inflation 0.28 m (scaling 5); local 4×4 m rolling at 5 Hz; footprint 0.30×0.25 m.
- MPPI: 20 Hz, 2000 samples, 56 × 0.05 s = 2.8 s horizon, 8 critics, ≤ 0.30 m/s, 1.0 rad/s; smoother 2.5 m/s², 3.2 rad/s².

### Evaluation design (P §VII, V)
- Held-out Gazebo test worlds. Exploration: 9 episodes (3 worlds × 3 seeds) with wheel-odometry noise (2 % / 3 % scale, heading random walk). Navigation: 12 episodes (3 worlds × 4 seeds), ≤ 20 random goals, 178 goals, AMCL on ground-truth map. Avoidance: 2 scenarios × 3 seeds. Ground-truth checks instead of Nav2's own report; bootstrap / Wilson 95 % intervals.
- Integrity (V): frozen code + test split, script-generated tables cross-checked, 0 mismatches over 1,784 values.

### Results (all simulation)
- Exploration coverage of reachable floor: 61.4 % [18.5, 88.0] pooled; multi_room_loop 86.3 %, office 83.8 %, maze_dead_ends 14.3 % (2 of 3 maze runs issued no goal: 1.2 %, 1.8 %).
- Map completeness 47.7 % [15.1, 70.6]: maze 11.9, multi-room 65.4, office 65.9.
- ATE 0.57 m [0.33, 0.86]; RPE 0.25 m/m. Contact-induced wheel slip corrupted heading in 4 of 9 episodes; ATE 0.33 m before first corruption (7 ep.).
- Efficiency: 15.2 goals/episode; half the reachable area explored in 67.7 s (7 ep.); 44.2 m travelled; 98.4 % of obstacle encounters passed without contact in exploration.
- Navigation: Nav2 reported 50.0 %; ground truth within 0.30 m 29.2 % (52 / 178); within 0.15 m 9.0 %. Per world (GT 0.30): two_rooms_door 48.8 %, office 20.7 %, maze 2.5 %. Path ratio 1.21. AMCL error 0.318 m.
- Diagnostic (1 episode/setting, indicative): AMCL 6 / 19 goals vs ground-truth pose 19 / 20 → localisation, not planner, limits success.
- Avoidance: 4 / 6 (static U-trap 3/3, sudden moving box 1/3); 95 % Wilson 30.0–90.3 %; min clearance 0.159 m.
- Responsiveness: 166 ms to 50 % commanded velocity; 260 ms to stop (deadline 0.5 s); ~10 ms to first plan (navigation).

## Subsystem 2: Trash detection (P §V, §VII)
- Custom dataset: 877 images; 6 waste classes (aluminium foil 175, bottle 210, cement dust 68, paper 210, wooden dust 63, wrapper 151); 6,349 annotations over 8 labels (+ floor, obstacle). Obstacle 3,517 vs wooden dust 162 (~21.7× imbalance).
- Why custom: TrashNet/ImageNet classes and eye-level, high-end-camera images didn't match. Camera 1280×720, mounted low, tilted 30° down so the arm can reach. 10 man-hours, 2 people.
- Instance segmentation polygons in Roboflow, 2 annotators, no auto-labelling. Classes defined by the cleaning action they need.
- Split 70:20:10 → 611 / 175 / 91. Albumentations on train only (flips, ±15° rotation, crop, perspective, brightness/contrast ±30 %, motion blur; p = 0.5).
- Random search (5 trials × 20 epochs) instead of 450-trial grid (> 6 GPU-days). Trained on RTX A6000.
- Models: YOLOv8n 3.01 M / 6.23 MB / 0.36 h; YOLOv11n-seg 2.84 M / 5.98 MB / 0.95 h; RF-DETR Medium 33.3 M / 133.02 MB / 3.61 h (~22× larger).
- Validation (175 images): mAP@0.5 0.9271 / 0.9302 / 0.9336; mAP@0.5:0.95 0.8195 / 0.8208 / 0.8387 (EMA 0.8432); precision 0.9347 / 0.9132 / 0.9271; recall 0.8995 / 0.9197 / 0.8935.
- Per-class (test): foil best 96.5–98.9 % AP; dust weakest (cement dust RF-DETR 64.6 %, wooden dust RF-DETR 74.8 %).
- Jetson Orin Nano FP16: end-to-end 76.4 / 79.3 / 41.4 FPS; latency 13.35 / 12.61 / 24.23 ms; board power 12.66 / 12.90 / 14.85 W; 6.05 / 6.15 / 2.79 FPS/W; peak RAM 244 / 341 / 323 MB. GPU-only 252 / 201 / 72 FPS.
- Recommendation: YOLOv11n-seg best edge balance; RF-DETR suits a GPU base station.

## Done vs left (P conclusion + V)
- DONE: hardware prototype + manual mode via HMI; navigation stack built and evaluated in Gazebo; custom dataset; 3 detectors trained, benchmarked on Jetson Orin Nano; paper submitted to IEEE Access; dataset published.
- LEFT (P future work): deploy + validate navigation on the physical robot (re-tune inflation, turning radius, clearance, speed for 0.60×0.50 m base; real D435i FOV ~87° vs 69.4° sim); integrate navigation + detection (Decision module); fix maze runs with no goal; avoid suddenly moving obstacles; complete semi-automatic + automatic modes; detectors on the robot itself; arm/vacuum actuation through the controller; wheel encoders on hardware.

## Deck outline (superseded: see CHECKLIST.md round 3 for the current 13-slide outline)
1 Title (Phase 2 slide 1 verbatim) · 2 Problem · 3 Vision + scope & status board · 4 Architecture · 5 Prototype hardware · 6 Manual mode on hardware · 7 Navigation pipeline · 8 Frontier explorer · 9 How we evaluate (sim) · 10 Exploration results · 11 Navigation, avoidance, responsiveness · 12 Dataset · 13 Models + training · 14 Accuracy · 15 Jetson edge deployment · 16 Done vs left roadmap · 17 Sim-to-real gap / lessons · 18 Contributions & impact · 19 Thank you
