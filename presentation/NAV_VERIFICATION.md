# Navigation subsystem: verification of README and paper claims

Verified 2026-11-12 by reading code, configs and result files under `/home/hrishikesh/Swachh` (read-only). Numbers marked VERIFIED were recomputed by me from the per-episode `results/runs/quick_*/**/summary.json` files, not only copied from tables. Nothing was run in ROS/Gazebo.

Sources: README = `/home/hrishikesh/Swachh/README.md`; paper = `/home/hrishikesh/Swachh/my_paper.txt` (LaTeX, untracked in git; the README still calls it `paper.txt`, which was deleted). Verdicts: VERIFIED / MISMATCH / UNVERIFIABLE.

Bottom line: every navigation result number in the paper abstract, Tables 7-9 and the results text reproduces from the raw summary files, with two small exceptions (section C, "Mismatches"). The weak points are not arithmetic. They are (1) everything is simulation only, (2) the navigation campaign tests Nav2 + AMCL on a ground-truth map, not the RTAB-Map pipeline, (3) n is 3 to 4 seeds per world, and (4) several hardware sentences in the paper are not backed by anything in the repo (section B).

---

## A. Architecture as implemented

Workspace: `Navigation/Simulation/vacuum_ws/src/` (11 ROS 2 packages, list in README section 3; all present).

| Item | What the code/config says | Source |
|---|---|---|
| ROS 2 / simulator | ROS 2 Jazzy, Gazebo Harmonic, CycloneDDS | README s4; `Navigation/cyclone_dds.xml`; paper "ROS 2 (Jazzy)" (VERIFIED) |
| SLAM | RTAB-Map RGB-D (colour + depth), wheel odometry from `diff_drive_controller`, `Reg/Force3DoF=true` (x, y, yaw), 5 cm 2D grid, ray tracing on, grid obstacle band z 0.03 to 0.30 m, `Rtabmap/DetectionRate` 1 Hz, `Rtabmap/LoopThr` 0.11, `Kp/MaxFeatures` 500, `Kp/MaxDepth` 4.0, `Vis/MinInliers` 10, `Mem/STMSize` 10, `RGBD/LinearUpdate` 0.1 m, `AngularUpdate` 0.087 rad, `ProximityBySpace` on with depth 0, `Mem/RehearsalSimilarity` 0.45, no time/memory limits | `vacuum_slam/config/rtabmap.yaml`. Paper Table "RTAB-Map parameters" matches every row checked (VERIFIED) |
| Feature type | `Kp/DetectorStrategy 6` is labelled "ORB" in a comment; README says it is GFTT/BRIEF in RTAB-Map 0.23 (explainer 06). Paper does not name the detector | `rtabmap.yaml`; I did not re-check the RTAB-Map 0.23 enum (UNVERIFIABLE here) |
| Global planner | `nav2_smac_planner::SmacPlannerHybrid`, `motion_model_for_search: DUBIN`, `minimum_turning_radius 0.25`, `tolerance 0.30`, `allow_unknown true`, `max_planning_time 5.0`, `retrospective_penalty 0.025` | `vacuum_nav2/config/nav2_params.yaml:168-187` (VERIFIED vs paper Table "Explorer and Nav2") |
| Local controller | `nav2_mppi_controller::MPPIController`, DiffDrive, `controller_frequency 20`, `batch_size 2000`, `time_steps 56`, `model_dt 0.05` (2.8 s horizon), `vx_max 0.30`, `wz_max 1.0`; critics: Constraint, Cost (`consider_footprint: true`), Goal, GoalAngle, PathAlign (`trajectory_point_step 3`), PathFollow, PathAngle, PreferForward (weight 15) = the 8 terms in the paper | `nav2_params.yaml:56-160` (VERIFIED) |
| Goal checker | `xy_goal_tolerance 0.30`, `yaw_goal_tolerance 0.50` | `nav2_params.yaml:74-75` (VERIFIED) |
| Velocity smoother | max velocity [0.30, 0, 1.0], max accel [2.5, 0, 3.2] | `nav2_params.yaml:243-245` (VERIFIED) |
| Costmaps | Rectangular footprint 0.30 x 0.25 m, 5 cm resolution; global 1 Hz, local 4 x 4 m rolling at 5 Hz; static + spatio-temporal voxel layer (z 0.03 to 0.30) + inflation (radius 0.28, scaling 5.0) | `nav2_params.yaml:258-374` (VERIFIED) |
| Frontier exploration | Own node (`vacuum_exploration`, about 1770 lines). Frontier = free cell with an unknown 4-connected neighbour; BFS clustering, 0.5 m radius, min 5 cells, 2 Hz; score = 1.0 ln(1+size) - 1.5 dist - 0.8 obstacle_penalty (penalty in [0,1], 0.5 m radius); goal snapped to a free cell with 0.30 m clearance within 1.5 m; blacklist 60 s, radius 0.5 m; goal timeout 30 s; no-progress 0.30 m in 15 s; stop = 5 empty cycles + <10 new free cells in 15 s + speed <0.02 m/s; bootstrap spin 0.4 rad/s for 8 s if no map after 3 s | `goal_selector.py:46-47,125-150`, `frontier_detector.py:9-11,67-70,169-180`, `exploration_manager.py:142-169` (VERIFIED vs paper text, Algorithm 1 and Table) |
| Simulated robot | Box chassis 0.30 x 0.25 m, wheel radius 0.033 m, separation 0.268 m, one forward RGB-D camera (D435i model, colour HFOV 69.4 deg used for both, no noise: `gaussian_noise 0` in `_gazebo.xacro:128`), no lidar, no IMU. Mass: chassis 2.0 kg + wheels 2 x 0.25 + caster + mounts, about 2.8 kg (README figure is a sum I could not see stated in one place) | `vacuum_description/urdf/_properties.xacro:29-48`, `_gazebo.xacro` (VERIFIED, mass total UNVERIFIABLE as a single number) |
| Worlds | 18 `.sdf` files in `vacuum_gazebo/worlds/` (VERIFIED). Split in `vacuum_eval/config/worlds.yaml:11-13`: dev = 7 (apartment, empty_room, cluttered_room, avoid_head_on, avoid_cluster, avoid_narrow_gap_wide, avoid_dynamic_cross); test = 10 (office, corridor, two_rooms_door, multi_room_loop, maze_dead_ends, symmetric_hall, avoid_narrow_gap, avoid_u_trap, avoid_dead_end, avoid_dynamic_sudden) | README "7 dev, 10 test" VERIFIED. Only 3 exploration worlds, 3 navigation worlds, 2 avoidance scenarios were actually run on the test split |
| Localisation in navigation runs | Nav2 + AMCL on a ground-truth map (`--nav-map gt`); in exploration runs RTAB-Map provides map->odom | `docs/METRICS_STATUS.md` header; paper s7.3 (VERIFIED) |
| Odometry noise (exploration only) | scale error sigma 2 % linear / 3 % angular per episode, plus heading random walk 0.02 /sqrt(m), 0.03 /sqrt(rad) | `vacuum_controller/odometry_noise_node.py`; paper s5.1 (stated; coefficients not re-checked line by line) |
| Evaluation harness | `vacuum_eval`: `run_episode`, `run_batch`, `aggregate`, `make_report`, `paper_tables`; validity gates (only `status: invalid` excluded); bootstrap CIs over worlds then seeds, Wilson CIs for rates | README s7; `docs/paper_out/paper_tables.md` cross-check section reports 0 mismatches against `aggregate.csv` |

Stale comments in config (README s14, all consistent with what I saw): feature type "ORB", footprint "circle 0.18 m", physics "1000 Hz" (actual 250 Hz); explorer `retry_count` read but unused (VERIFIED: parameter declared at `exploration_manager.py:143,173`, blacklisting happens on first failure).

---

## B. Manual mode on hardware

Location: `Navigation/Manual mode/` (README, `claude_context.md`, `arduino/swacch_robot/swacch_robot.ino` 317 lines, `hmi/` C++ GTK4 about 1180 lines, `ros.sh`, `stats.sh`).

### What exists
- **Arduino firmware** (`swacch_robot.ino`): 115200 baud ASCII, newline-terminated, 64-byte buffer. Commands: `MOVE:FORWARD|BACKWARD|LEFT|RIGHT|STOP`, `SPEED:1..9` (PWM table 80 to 255, default level 5 = 168), `ESTOP`, `RESET`, `VACUUM|ARM|WIPER|UV :ON|OFF`, `AUTO:ON|OFF`, `AI:ON|OFF`. Replies `ACK:<cmd>`, `ERR:UNKNOWN_CMD:<cmd>`, `ERR:EMERGENCY_STOP_ACTIVE`, `ERR:CMD_TOO_LONG`, and `STATUS:...,SPD=..` every 1000 ms (`STATUS_INTERVAL`). Lines 18-30, 149-262. (VERIFIED)
- **Motor drive:** two motors, PWM pins 5 (left) and 6 (right), direction relays on pins 7 and 8. Differential steering by driving sides in opposite directions. Only these four pins are configured as outputs (`pinMode` at lines 268-271). (VERIFIED)
- **Peripherals:** vacuum, arm, wiper, UV, auto mode only set a boolean; "no dedicated pins — just track state for HMI" (comment at line ~230). So the vacuum/arm cannot be actuated by this firmware. (VERIFIED; matches README s1 and s12)
- **HMI** (`hmi/src/gui.cpp`, `callbacks.cpp`, `serial_comm.cpp`, `logger.cpp`): fullscreen GTK4 touchscreen app: Forward/Left/Right/STOP buttons, 9 speed buttons, EMERGENCY STOP and Reset, Vacuum/Arm/Wiper/UV toggles, Auto toggle (blocked while e-stop active; movement blocked while Auto is on, `callbacks.cpp:33`), battery label (simulated by a 5 s timer, `gui.cpp:306`, `callbacks.cpp:258`), a logger. Built with CMake; `scripts/setup.sh` installs GTK4/arduino-cli, `scripts/run.sh` detects the port and starts it. (VERIFIED)
- **Simulation-side manual driving:** `Navigation/steer_gui.sh` launches a Tkinter steering GUI (`vacuum_controller/robot_steering_gui.py`); `teleop_arrows.py` is an arrow-key teleop node; `start.sh` with no argument starts sim + teleop + GUI. These drive the Gazebo robot, not hardware. (VERIFIED by file existence and script text)

### Hardware as described (all from paper/docs; none verifiable from code)
- Paper s4 and Table "Specifications": Jetson Orin Nano (compute), Arduino Uno, two 6-inch BLDC hub motors with YL-12 24 V sine-wave controllers, front caster, 24 V 26 Ah lead-acid pack (about 2 h), D435i + two 720p webcams, robot about 0.61 x 0.46 x 0.91 m, 50 kg. Communication: USB-serial 115200 8N1 between Jetson and Arduino. Confirmed by the authors per `docs/REPO_FACTS_ITEMS_1_TO_25.md` (Jetson is the robot computer).
- `Navigation/Manual mode/claude_context.md` instead says Raspberry Pi 5 + Debian 13 + ROS 2 Humble in distrobox, two C270 webcams, "no depth cameras". This conflicts with the paper (Jetson, D435i). Treat as stale/other-session notes; README s14 flags the Pi/Jetson discrepancy.

### What is demonstrated vs not
| Claim | Verdict |
|---|---|
| Manual mode "implemented completely" (paper s4.6, abstract "hardware performs manual mode") | PARTLY VERIFIED: firmware + HMI exist and cover motion, speed, e-stop. No test log, video, photo or measurement of the physical robot driving exists in the repo (Navigation/tests/hardware and /field contain only `__init__.py`). The deck/poster files (`SBY_IEEE_Video_Deck.pptx`, `Sample-Poster.pptx`) may hold photos; I did not open them. UNVERIFIABLE as a demonstration |
| Serial protocol: 115200, newline-terminated ASCII, ACK per command, STATUS at 1 Hz | VERIFIED (`.ino:28-30,250-262`) |
| "8N1" frame | UNVERIFIABLE explicitly, but it is the Arduino `Serial.begin` default (VERIFIED by default, no explicit config line) |
| Arduino executes "moving forward 30 cm, turning right 15 deg" (paper s4.3) | MISMATCH: firmware has only continuous `MOVE:*` plus `SPEED`; no distance or angle commands exist |
| "Wheel encoders ... accurate rotational feedback" (paper s4.1) | UNVERIFIABLE/MISMATCH: no encoder code in the sketch (`REPO_FACTS` item: "NOT FOUND ... no encoder type, counts, radius"). Odometry in all results is simulated |
| Emergency stop in the HMI | VERIFIED (`ESTOP` -> motors off, peripherals cleared, motion blocked until `RESET`) |
| Audio input "STOP" from a microphone and speaker feedback (paper s4.1, s4.3) | UNVERIFIABLE: no audio code anywhere in `Navigation/` or `Object Detection/` (grep for microphone/audio/speaker/voice found nothing) |
| HMI shows continuous video feed, alerts (paper s4.6) | UNVERIFIABLE: `gui.cpp` has no camera/video widget; it shows status, battery (simulated), buttons |
| "At start-up the Jetson self-checks cameras, Arduino and wheel drivers" | UNVERIFIABLE (no such code found) |
| "Locomotion actuation: 12 V DC Servo Motors" in the spec table vs BLDC hub motors in the text | MISMATCH inside the paper (text and README/firmware: BLDC + PWM + relay) |
| Spec table "Wheel weight 20 kg", chassis 30 kg, total 50 kg, speed 30 rpm | UNVERIFIABLE (hardware facts, no source in repo) |
| Hardware safety: firmware has no command timeout/heartbeat; relay direction switching with motors running not guarded | VERIFIED as stated in README s16; HMI-only check blocks motion in Auto |
| HMI battery level | It is simulated, not measured (README s12 VERIFIED) |

Do not present: autonomous or semi-automatic operation on the robot, vacuum/arm actuation via this firmware, Jetson-run navigation, encoder odometry, voice stop.

---

## C. Results (all simulation, test split, frozen code commit 92c7757)

Campaign sizes (VERIFIED by counting `summary.json` files): exploration 9 (3 worlds x seeds 101-103, odometry noise on, 450 s sim cap, RTAB-Map + Nav2 + frontier), navigation 12 (3 worlds x seeds 101-104, up to 20 random goals, Nav2 + AMCL on GT map), avoidance 6 (2 scenarios x 3 seeds, Nav2 + AMCL), responsiveness 4 (2 valid, 2 bare-stack runs invalid by design). 29 of 31 valid. True real-time factor 0.729 to 1.000 (mean 0.929); exploration mean 0.827 (office and multi_room_loop ran three sims at once, RTF about 0.74).

Source for all: `docs/paper_out/paper_tables.md` and `paper_values.json` (cross-checked by that script against `aggregate.csv`, 0 mismatches), and my recomputation from `results/runs/quick_*/*/*/*/summary.json`. Brackets = 95 % bootstrap CI as the paper reports them (worlds then seeds for pooled rows). sd is from my recomputation (episode level).

### C1. Exploration + SLAM (9 episodes, RTAB-Map, odometry noise on)
| Metric | Reported | Recomputed (n, mean, sd) | Verdict |
|---|---|---|---|
| Reachable-floor coverage, pooled | 61.4 % [18.5, 88.0] | 9, 61.44, 37.5 | VERIFIED (README, abstract, paper) |
| by world | maze 14.3 [1.2, 39.9]; multi_room_loop 86.3 [82.6, 88.6]; office 83.8 [71.5, 91.6] | per-episode table in paper_tables.md: maze 1.8 / 39.9 / 1.2; multi 82.6 / 87.6 / 88.6; office 91.6 / 88.2 / 71.5 | VERIFIED |
| Map completeness (mean of free recall and wall recall) | 47.7 % [15.1, 70.6] | 9, 47.73, 29.6 | VERIFIED |
| ATE (SLAM, no scale correction) | 0.57 m [0.33, 0.86], n=7 | 7, 0.572, 0.296 | VERIFIED. Only 7 of 9 episodes have an ATE (2 maze episodes never moved) |
| ATE excluding contact-corrupted | 0.44 m (3 episodes); before first corruption 0.33 m (7) | paper_values `ate_uncorrupted` 0.437 (n=3), `ate_pre_corrupt` 0.332 (n=7) | VERIFIED |
| RPE over 1 m windows | 0.25 m/m [0.14, 0.44], n=7 | 7, 0.250, 0.197 | VERIFIED |
| Wheel-odometry-only ATE, same episodes | README: 2.54 m. Paper s7.3: "trajectory error of wheel odometry alone was not measured" | 7, 2.543, 0.985; SLAM ATE improvement vs odometry 72 % mean (`ate_improvement_pct`) | README VERIFIED; **paper sentence is MISMATCH/stale** (the value exists in the summaries). Caveat: odometry here has injected noise, so this is not a fair "SLAM vs real odometry" claim |
| Wheel-odometry RPE 1 m | README 0.19 | 7, 0.194 | VERIFIED. SLAM RPE (0.25) is worse than odometry (0.19) at the 1 m window; do not claim SLAM improves local accuracy |
| Odometry corrupted by contact | 4 of 9 | `odom_corrupted_by_contact` mean 0.444 over 9 | VERIFIED |
| Loop closure | 1051 accepted, 370 true = 35.2 % [17.9, 58.6]; recall 28.2 % [12.6, 40.9] | sums 1051 / 370; recall 28.2 | VERIFIED. Docs say precision is a lower bound (GT matched at message arrival; a time-shift diagnostic gives 52 to 77 %). Per-episode mean precision is 36.8 % [19.9, 94.3] (one maze episode at 94.3 % inflates the interval) |
| Episodes with no goal sent (maze 101, 103) | 2 of 9, stuck at 180 s | `end_reason` stuck, `episode_sim_sec` 180 | VERIFIED |
| Goals per episode | 15.2 [6.3, 21.0] | 9, 15.22, 8.9 | VERIFIED |
| Recoveries per episode | 81.9 [31, 116] | 9, 81.89, 49.2 | VERIFIED (paper says 70-80 % are instant costmap clears: from docs, not rechecked) |
| Time to 50 % explored | 67.7 s [39.8, 124.7], n=7 | 7, 67.67, 45.0 | VERIFIED |
| Time-averaged explored share | 52.9 % | 9, 52.87 | VERIFIED |
| Overlap ratio / missed area | 1.95 / 37.6 m2 | 1.946 / 37.61 | VERIFIED |
| Distance travelled (GT) | 44.2 m | 44.19 (sd 26.9) | VERIFIED |
| Energy proxy / odometry drift / cleaning efficiency | 23.2 m2/s / 8.6 % / 0.055 | 23.18 / 0.086 / 0.055 | VERIFIED. Cleaning efficiency is secondary: the explorer is not a cleaner |
| Collisions (contact bursts) per episode | 1.78 [0.4, 3.9] | 1.778 | VERIFIED; counts bursts more than 0.5 s apart, so one jam can count 3 to 7 times |
| SLAM update time | median 153 ms total (p95 440 ms), 3755 updates | `paper_values.json slam_update` | VERIFIED from file; not re-derived by me |
| Peak RTAB-Map RAM | about 1.6 GB mean (1.0 to 2.0 GB) | `paper_values.json memory` | VERIFIED from file. Measured on a 22 GB PC, not the 8 GB Jetson |

### C2. Navigation (12 episodes, Nav2 + AMCL on ground-truth map, no injected noise)
| Metric | Reported | Recomputed | Verdict |
|---|---|---|---|
| Goals issued | 178 (7 of 12 episodes ended early as "stuck"; 5 reached 20 goals or goals_done) | sum `nav_goals_total` = 178 | VERIFIED |
| Nav2-reported success | 50.0 % (89 of 178) | 89 | VERIFIED |
| Ground-truth verified, 0.30 m | 29.2 % (52 of 178), by goals CI [16.0, 40.0] | per-episode table: 1+0+0+0 + 0+3+5+4 + 10+8+8+13 = 52 | VERIFIED |
| Per-episode mean GT success | 23.4 % [2.8, 46.7] (README, paper) | 23.43 | VERIFIED. This CI uses the pre-registered worlds-then-seeds bootstrap; a plain episode bootstrap in `paper_values.json` gives [11.7, 35.4]. Pick one and say which |
| Strict 0.15 m | 9.0 % (16 of 178) [3.3, 14.1] | 16 | VERIFIED |
| By world (GT 0.30 m, by goals) | two_rooms_door 48.8 % (39/80); office 20.7 % (12/58); maze 2.5 % (1/40) | same | VERIFIED. Nav2-reported: 82.5 / 37.9 / 2.5 % |
| Path-length ratio (reached goals) | 1.21 [1.09, 1.27] (n=9 episodes) | `paper_values` 1.209 [1.157, 1.265] under episode bootstrap | VERIFIED (interval differs by bootstrap type) |
| Recoveries per episode | 147.6 [107, 184] | 147.58 | VERIFIED |
| Contact events per episode | 1.9 | 1.917 | VERIFIED |
| AMCL position error | 0.318 m [0.183, 0.509] | from `docs/METRICS_STATUS.md` A14; not re-derived | VERIFIED from docs only |
| Localisation diagnostic | AMCL 6 of 19 GT-verified; GT localisation 19 of 20 | `paper_tables.md` diagnostic table (apartment, dev world, seed 1, one episode per setting) | VERIFIED; indicative only (n=1, dev world) |
| Obstacle share passed without contact | exploration 98.4 %, navigation 93.2 %, avoidance 80.0 % | recomputed 98.36 / 93.15 / 80.0 | VERIFIED (small denominators; walls excluded) |
| RMS path curvature (navigation) | 3.01 1/m | 3.009 | VERIFIED |
| Time to first valid plan | "about 10 ms navigation, 30 ms exploration" | `paper_values plan_latency`: navigation median 8 ms (121 goals planned; 62 goals had no plan; mean 6.4 s) | Navigation VERIFIED as a median; exploration 30 ms UNVERIFIABLE by me (docs say 10-30 ms). It is "time to first successful plan", not planner compute time; do not present as planning latency |

### C3. Avoidance (6 episodes) and responsiveness
| Metric | Reported | Recomputed | Verdict |
|---|---|---|---|
| Trial success (goal reached, no contact) | 4 of 6 = 66.7 %, Wilson 95 % [30.0, 90.3]; u_trap 3/3, dynamic_sudden 1/3 | `trial_success` = [0,0,1,1,1,1] across the 6 summaries | VERIFIED. Docs' bootstrap CI is [16.7, 100]; paper uses Wilson, which is the appropriate choice |
| Goal reached | 5 of 6 | `trial_goal_reached` sum 5 | VERIFIED |
| Contact events | 1 total, 0.17 per episode | 1 | VERIFIED |
| Min clearance | 0.159 m; paper CI [0.076, 0.227] | mean 0.1586; `paper_tables.md` and `paper_values.json` give [0.084, 0.222] | **MISMATCH (minor):** the paper interval comes from the older `METRICS_AUDIT_2026-10-25.md` row; the script-computed interval is [0.084, 0.222]. The mean is right. Note one dynamic episode had clearance 0.0 (contact) |
| Responsiveness (loaded stack, n=2) | 166 ms to half speed [160, 172], p95 206; stop 260 ms [250, 270], p95 301; deadline 0.5 s | cmd 171.7 / 160.4 ms; stop 270.4 / 249.7 ms | VERIFIED. The two "bare" episodes are `invalid` by design (no RTAB-Map) and excluded. This is mostly the configured acceleration ramp plus about 45 ms of pipeline delay, i.e. a simulation controller latency, not hardware responsiveness |

### Mismatches and cautions to fix before presenting
1. Paper s7.3 says wheel-odometry-only ATE "was not measured": it was, 2.54 m (7 episodes, with injected noise). Update the sentence or do not use it.
2. Paper avoidance clearance CI [0.076, 0.227] should be [0.084, 0.222] to match the generated table.
3. Paper s4 hardware statements without a code/evidence basis: 30 cm / 15 deg commands, wheel encoders, microphone STOP, HMI video feed, start-up self-check (section B).
4. Paper spec table "12 V DC Servo Motors" contradicts "BLDC hub motors" in the text.
5. README says `paper.txt`; the file is `my_paper.txt` (untracked) and `paper.txt` is deleted in the working tree. `images/` folder referenced by the paper (architecture diagram, `hmi.jpg`) is not in the repo.
6. README s13 test counts (126 collected, 85 pass, 41 fail, vision tests stale) were not re-run by me: UNVERIFIABLE now. The 41 failures are described as stale imports, not runtime bugs.
7. Two intervals exist for the same quantity (navigation 23.4 % [2.8, 46.7] vs [11.7, 35.4]). Use the pre-registered one the paper uses and name the method.

---

## D. Known limitations, failure modes, what is left

Stated in docs/README and consistent with code and results:
- **Simulation only.** No navigation, SLAM or exploration run on the physical robot or on the Jetson. Simulated base is 0.30 x 0.25 m against about 0.60 x 0.50 m physical; camera is noiseless with 69.4 deg HFOV (86 deg configured but never applied, `_gazebo.xacro:172`; D435i is about 87 deg); textured walls may flatter loop closure. No lidar or IMU. Inflation, turning radius, clearance and speed limits are tuned for the small base.
- **Small samples.** 3 seeds per exploration world (9 episodes), 4 seeds per navigation world (12 episodes), 3 per avoidance scenario. The shortened 4-hour campaign cut exploration from 15 to 9 episodes and navigation from about 240 to 178 goals. Intervals are wide (coverage 18.5 to 88.0).
- **Navigation result is not the SLAM pipeline.** Nav2 + AMCL on a ground-truth map. Dominant failure: Nav2 error 205 "start occupied" (1242 planner lines): AMCL pose (error 0.318 m) puts the footprint inside an inflated wall while the true pose is free, and v1 has no recovery that moves the robot. About 36 % localisation-caused, about 60 % robot genuinely near a wall (`docs/EVALUATION_FINDINGS_2026-10-25.md` s3). A "nav v2" fix (BackUp + Spin + more AMCL particles) failed its pre-set A/B rule and was not adopted.
- **AMCL weaknesses** (audited): loose `sigma_hit`/`z_rand`, recovery disabled, 69.4 deg FOV, maze geometry, an unmodelled 8 cm axle offset.
- **Maze stall.** In 2 of 3 maze episodes the explorer never sent a goal: the bootstrap spin ended facing a wall, the first map was a 0.5 to 0.7 m2 sliver, and `_snap_goal` treats unknown cells as blocked so no goal met the 0.30 m clearance; no fallback exists, the robot waits until the 180 s stuck rule. Corridors are 1.0 to 1.1 m wide, so it is not a narrow-passage problem. Deterministic, not rerun, not fixed. (README s8 and paper wording differ slightly: the paper says "no navigation goals were issued", docs give the cause; both consistent.)
- **Contact-corrupted odometry** in 4 of 9 exploration episodes; RTAB-Map did not recover, so coverage/ATE are a full-pipeline estimate, not a best case.
- **Moving obstacles.** Sudden moving box avoided in only 1 of 3 trials.
- **Metric caveats:** collisions count contact bursts (one jam = 3 to 7); LC precision is a lower bound; "planning latency" is time to first successful plan; clearance is slightly optimistic (wheels protrude 1.8 cm); health flags are diagnostics, not exclusions; metric-9 pooled row empty in `make_report.py:35` (a reporting bug, value computed separately).
- **Not measured:** metric #13 (comparison of coverage methods, on hold by decision); A15 noise robustness (clean-sensor condition dropped); end-to-end latency camera-to-actuator; anything on hardware. Odometry noise was injected only in exploration.
- **Left to do (from paper conclusion and docs):** deploy and validate navigation on the physical robot; integrate navigation with trash detection (the decision/fusion module is design only); fix the maze stall; improve moving-obstacle avoidance; semi-automatic and automatic modes; hardware firmware outputs for vacuum/arm (flags only today); firmware command timeout/heartbeat; candidate fixes list in `docs/EVALUATION_FINDINGS_2026-10-25.md` s6 (AMCL tuning, depth FOV, START_OCCUPIED recovery, explorer stall fallback, recorder timestamps).
- **Reproducibility:** `paper_tables.py` and `make_figures.py` need `~/eval_runs_victus/` including `_gt/` ground-truth grids, which are not in the repo; raw rosbags/databases are local only (`large_files/`, git-ignored).

---

## E. Safe headline facts for slides (each verified)

1. Navigation stack: ROS 2 Jazzy + RTAB-Map (RGB-D + wheel odometry, 3-DoF, 5 cm grid) + Nav2 with Smac Hybrid-A* (Dubins, 0.25 m min turning radius) planner and MPPI controller (20 Hz, 2000 samples, 2.8 s horizon, 0.30 m/s) + a custom frontier explorer. Source: `nav2_params.yaml`, `rtabmap.yaml`, `exploration_manager.py`.
2. All navigation results are from Gazebo simulation on held-out test worlds (31 test episodes, 29 valid; 18 worlds exist, only 3 exploration + 3 navigation worlds + 2 avoidance scenarios used). Source: `results/runs/quick_*`, `worlds.yaml`.
3. Autonomous exploration covered 61.4 % [18.5, 88.0] of reachable floor on average (9 episodes, 3 worlds, odometry noise on); 86.3 % in multi_room_loop and 83.8 % in office. Source: `paper_tables.md` Table 8, recomputed.
4. Excluding the two maze episodes where no goal was issued, the 7 moving episodes averaged 78.8 % coverage (docs figure `EVALUATION_FINDINGS` s2; consistent with the per-episode values: (82.6+87.6+88.6+91.6+88.2+71.5+39.9)/7 = 78.5 using the table values, so say "about 79 %"). Present only together with fact 3.
5. SLAM trajectory error 0.57 m [0.33, 0.86] (ATE, 7 episodes); 0.33 m before the first contact-corrupted odometry event. Source: `paper_values.json`.
6. Half of the reachable area explored after 67.7 s on average (7 episodes); mean distance travelled 44.2 m; 15.2 goals per episode. Source: summaries, recomputed.
7. On a known map with AMCL localisation, 29.2 % of 178 random goals were reached within 0.30 m of ground truth (Nav2 itself claimed 50.0 %); when ground-truth localisation replaced AMCL on a development-world diagnostic, 19 of 20 goals were reached (one episode, indicative only). Path length averaged 1.21 times the shortest. Source: `paper_tables.md` Table 8b.
8. Obstacle avoidance: static U-trap 3 of 3 trials, suddenly moving box 1 of 3; 4 of 6 overall (Wilson 95 % interval 30 to 90 %); mean minimum clearance 0.159 m. Source: `paper_tables.md` Table 9.
9. Controller step response in simulation: 166 ms to half commanded speed, 260 ms to stop (2 valid episodes, deadline 0.5 s). Say "simulation".
10. Manual mode exists in hardware form: Arduino firmware (two-motor PWM + direction relays, 115200-baud ASCII protocol with ACK, 1 Hz status, emergency stop) plus a fullscreen GTK4 touchscreen HMI. Source: `swacch_robot.ino`, `hmi/src/`. Say it is implemented; do not claim a measured hardware test.
11. Evaluation integrity: pre-registered metrics, frozen code and test split, bootstrap and Wilson intervals, script-generated tables cross-checked against `aggregate.csv` with 0 mismatches over 1784 compared values (637 + 571 + 376 + 200). Source: `paper_tables.md` last section.
12. Honest scope statement that judges will respect: simulation only, small robot model, noiseless camera, 3 to 4 seeds per world; next step is hardware deployment and integration with the trash detector. Source: paper s7 final paragraph and conclusion.

Avoid on slides: "autonomous navigation on the robot", "SLAM improves accuracy over odometry" (RPE 1 m is worse), planning latency in ms without the caveat, any 100 % claim about avoidance, loop-closure precision as a quality figure (lower bound, 35 %).

---

## F. Ready-made figures for navigation

Paper-quality (generated from raw data by `docs/paper_out/make_figures.py`; captions in `docs/paper_out/FIGURE_CAPTIONS.md`), all in `/home/hrishikesh/Swachh/docs/paper_out/figures/`:
- `fig_actual_vs_explored.png`: true floor plan next to the RTAB-Map grid from each exploration seed (shows maze stall and drift). Best single exploration visual.
- `fig_exploration_trajectories.png`: robot paths (colour = time) over floor plans, 3 worlds x 3 seeds, coverage in titles.
- `fig_navigation_trajectories.png`: paths during navigation test, 3 worlds x 4 seeds, GT success per run.
- `fig_coverage_vs_time.png`: explored share vs time, one line per episode.
- `fig_nav_success.png`: Nav2-reported vs ground-truth success per world and pooled, with CIs (use this one, not the harness chart that shows Nav2-only).
- `fig_ate_points.png`: ATE per exploration episode; hollow markers = odometry corrupted by contact.
- `fig_costmap_layers.png`: SLAM grid, global costmap and 4 x 4 m local costmap from a live office run.
- `fig_slam_map_office.png`: RTAB-Map occupancy grid after about 4 min in office (partial map, illustrative).
- `fig_test_worlds.png`: floor plans of the held-out test worlds (caption says six worlds).

Per-run harness plots (use with care): `/home/hrishikesh/Swachh/results/runs/quick_exploration_noise/report/figures/{ate_box,rpe_box,collisions,coverage_vs_time,nav_success}.png`, `.../quick_navigation/report/figures/*.png`. `FIGURE_CAPTIONS.md` says not to use `nav_success.png` (overstates success), `coverage_vs_time.png` (bands below 0 %) or `ate_box.png` (1 to 3 points per box). Per-episode `missed_explored.png` exists in each exploration seed folder, e.g. `results/runs/quick_exploration_noise/office/frontier/seed_101/missed_explored.png` (area explored but not swept). Per-run map snapshots are `maps/map_*.npz` (data, not images).

Not in the repo as image files: the system architecture diagram (`images/SBY Architecture.drawio (3).png`), the robot/HMI photos (`hmi.jpg`, `hmi.jpeg`), and Gazebo/RViz screenshots S1-S6 (planned in `docs/paper_out/FIGURE_PLAN.md`, to be taken by hand). Possible sources for hardware photos and a diagram: `/home/hrishikesh/Swachh/SBY_IEEE_Video_Deck.pptx`, `Sample-Poster.pptx`, `Major Project Phase 2 PPT.pptx`, `Submitted Paper.pdf` (not opened). Diagram generators exist in `vacuum_utils` (12 check/record/benchmark/diagram scripts) but were not run.
