# The story of Swachh Bauddhika Yantra

This is the whole project told as one story, from the idea down to the evidence. Read it top to bottom to understand what exists, what works and what does not. Wherever a part is interesting, a link takes you into the detailed explainer file for it. Nothing here needs those files, but all of it is explained deeper there.

A note on honesty: this project has real parts, simulated parts and designed-but-unbuilt parts. The story keeps them apart, because mixing them up is the easiest way to misread the work.

---

## 1. The idea

Cleaning a large indoor floor by hand is slow and uneven. *Swachh Bauddhika Yantra* ("clean intelligent machine", SBY) is a robot meant to do it alone. It should:

1. **Look around** and build a map of the room.
2. **Move safely** through it, avoiding furniture and people.
3. **Spot trash** with a camera.
4. **Pick it up** with a small arm and **vacuum** the floor.

Each of these is a field of its own, so the project is really four systems that have to cooperate: perception, mapping, navigation, and actuation. The next sections follow them in that order. For the one-page version of this idea, see the [system overview](01_system_overview.md).

## 2. The robot's body

The physical robot is a wheeled base of roughly 0.60 × 0.50 m. Two driven wheels push it along and a caster balances it. A computer (the authors describe an NVIDIA Jetson Orin Nano as the robot's brain) makes the decisions, and an Arduino sits between that computer and the motors. The Arduino listens to short text commands over a serial cable, such as "move forward" or "stop", and turns them into motor signals.

Here is the first thing worth knowing. **The firmware only really drives the two motors.** Commands for the vacuum, the arm, a wiper and a UV lamp are accepted, but they only flip a flag in memory; there is no output pin behind them. The arm's "pick" command that the vision code sends is not handled by the firmware at all and would be answered with an error. So the hardware that exists and moves is the driving base. The full details, including the serial protocol and a safety gap (the firmware has no command timeout, so the last move command keeps running until a stop), are in the [manual mode and HMI explainer](03_manual_mode_hmi.md).

A person can drive the robot with a small desktop control panel (the HMI). That is the one operating mode that is actually implemented. The design also describes semi-automatic and fully automatic modes in which a "decision module" combines what the camera sees with the map and chooses actions. That decision module is a design, not working code. This matters later, when we talk about what was and was not measured.

## 3. Why a simulator

Testing a robot that moves, maps and plans on real hardware is slow, risky for the hardware, and hard to repeat. So the navigation work was built and tested in a physics simulator: **Gazebo**, with the robot software running on **ROS 2** (a framework in which many small programs, called nodes, pass messages to each other).

The simulated robot is a simplified, smaller version of the real one: a box of 0.30 × 0.25 m and 2.8 kg, with two wheels and one forward-looking depth camera (it returns a colour picture plus a distance for every pixel). There is no lidar and no inertial sensor in the simulation, so everything the robot knows about its surroundings comes from that one camera and from counting wheel turns. The simulated world has 18 hand-built environments, grouped into development worlds used while building, and held-out test worlds used for the final scores. Every number, link and plugin of the model is in [robot model and worlds](04_robot_model_and_worlds.md).

Two honest limits of the simulator belong here. The simulated camera has no sensor noise, and its field of view is 69.4°, narrower than the physical camera's roughly 87°. An 86° depth value sits in the config files but is never applied; the code uses 69.4°.

## 4. How the simulation is started

One launch file brings the whole thing up in order: it loads the robot description, starts Gazebo with a chosen world, connects Gazebo to ROS through a "bridge" (so camera images and wheel commands cross between the two programs), starts the drive controller, and optionally opens the RViz viewer. After that, further launch files add mapping, navigation and exploration on top. The launch arguments and the helper scripts are described in [bringup, interfaces and utilities](05_bringup_interfaces_utils.md), and the convenience launchers (`start.sh` and friends), the setup and preflight checks, and the unit tests are in [navigation scripts and tests](02_navigation_scripts_and_tests.md).

If you want to see every message that flows between all these programs, which topic carries what, and which program publishes each coordinate transform, that is all collected in [topics, transforms and data flow](14_topics_tf_and_dataflow.md).

## 5. Seeing and mapping: SLAM

The robot starts in a room it has never seen. To move sensibly it must build a map and know where it is on that map at the same time. This is called SLAM, simultaneous localisation and mapping.

The project uses **RTAB-Map**. It watches the camera, picks out distinctive points in each image (the paper's configuration uses up to 500 per image, with the GFTT detector and BRIEF descriptors), and remembers what places look like. Two things come out:

- an **occupancy grid**, a top-down map where each small square is free, occupied or unknown; and
- **loop closures**: when the robot recognises a place it has seen before, it uses that to correct accumulated drift.

Between camera updates the robot estimates motion from its **wheel odometry**, which means counting wheel rotations. Odometry drifts, especially when a wheel slips, and a real lesson of the project is how much. In the test runs, noise was deliberately added to the odometry to make it realistic, and contact with obstacles corrupted it in 4 of 9 exploration runs.

A small gotcha: the comment in the config file says detector type 6 is "ORB". In the RTAB-Map version used it is actually GFTT/BRIEF, which is what the paper reports. Every RTAB-Map parameter, the map saving and loading, and the localisation monitor are covered in [SLAM and localisation](06_slam_and_localization.md).

## 6. Moving: Nav2

A map is only useful if the robot can use it. **Nav2** is the standard ROS navigation system, and here it works in two layers.

- A **global planner** (Smac Hybrid, using Dubins curves, which means paths that respect the fact that a wheeled robot cannot move sideways) finds a route from the robot to a goal across the map. It re-plans about once a second.
- A **local controller** (MPPI, which tries many short candidate motions each cycle and picks the best) follows that route while dodging things the global map did not know about. It runs about twenty times a second.

Both use **costmaps**: copies of the map where every obstacle is surrounded by a danger zone, so the robot keeps its distance from walls. If the robot gets stuck, a **behaviour tree** triggers recoveries such as clearing the costmap, backing up, spinning or waiting. Finally the speed commands pass through a velocity limiter and a drive controller that enforces gentle acceleration before they reach the wheels. All of these parameters, the three behaviour trees and the extra controller programs are in [Nav2 and controller](07_nav2_and_controller.md).

One more detail that confused people for a while: a header comment says the robot is a circle of radius 0.18 m, but the costmaps actually use the true 0.30 × 0.25 m rectangle.

## 7. Choosing where to go: frontier exploration

Nav2 needs a goal; it does not choose one. Exploring an unknown room needs a rule for "where next?". The project uses **frontier exploration**: a frontier is a boundary between known free space and unknown space. Going to a frontier reveals new map.

The explorer finds frontiers in the live map, groups them into clusters, and scores each one. Bigger frontiers score higher, being far away lowers the score, and being close to obstacles lowers it too. The best-scoring one becomes the next goal, with a safety rule that keeps the goal at least 0.3 m from walls. It cancels goals that take too long or make no progress, and it stops when no frontiers are left. A worked example with every constant is in [frontier exploration](08_frontier_exploration.md).

One failure from the tests is worth remembering: in two of the three runs in the maze world, the explorer found no goal that met its clearance rule, so the robot never left its starting spot.

## 8. Seeing trash: object detection

Separately from navigation, the project trained and compared three object detectors on a custom set of trash images with eight classes: YOLOv8, YOLOv11 (segmentation version) and RF-DETR. RF-DETR scored best on accuracy, while the small YOLO models are far lighter. A benchmark measured how long each takes per image: roughly 12 to 20 milliseconds with TensorRT on a GPU, compared with about 190 ms on a CPU. The method, the columns and the pitfalls are in [detection models and benchmarks](12_detection_models_and_benchmarks.md).

Be careful here, because the story has a twist. The detectors in the paper are **not** what the checked-in pick pipeline uses. That pipeline takes two ordinary USB cameras as a stereo pair, runs a generic COCO-trained YOLOv8s on seven everyday classes, estimates distance from the stereo disparity, and sends a pick command to the Arduino, which cannot act on it. There is also a network mode that splits the work between a small board and a GPU computer. The whole pipeline, the calibration and the Streamlit demo app are described in [the camera code explainer](11_object_detection_camera.md). Also note that the benchmark result files do not record which hardware produced them, so the "Jetson Orin Nano" label on the speed numbers comes from the scripts and project notes.

## 9. Measuring honestly: the evaluation framework

A robot that "seems to work" is not a result. The project therefore built an **evaluation framework** that runs the robot in the simulator in standardised **episodes** (one run from start to a finish condition), over several **seeds** (different random starts), in different **worlds**, and records everything: the robot's true position from the simulator, the map it built, contacts, timings and more.

Several rules keep it honest:

- An episode only counts if it passes **validity gates** (for example, the mapping system must actually have been running); invalid ones are excluded, and nothing else is.
- **Health flags** warn when a number is suspicious but never remove an episode.
- Intervals are computed by **bootstrap resampling** (and Wilson intervals for success rates), done first over worlds and then over seeds, so a few runs cannot masquerade as certainty.
- Nothing may be tuned after the test begins.

How the harness starts and stops episodes, the file layout of every run, and every command-line tool are described in [the evaluation harness](10_evaluation_harness.md). The definition of each metric, as it is actually coded, is in [the evaluation metrics](09_evaluation_metrics.md). Two things there are easy to get wrong: the map-completeness score is the average of free-floor recall and wall recall (not an intersection-over-union), and the ground-truth map treats a thin band of heights (about 3 to 25 cm) as obstacles.

## 10. What the numbers say

The final campaign was shortened to four hours, so it used 31 test episodes: 9 exploration, 12 navigation, 6 obstacle-avoidance and 4 responsiveness (two invalid by design). The intervals are wide because there were only three or four seeds per world.

- **Exploration.** On average the robot explored 61.4 % of the reachable floor (interval 18.5–88.0 %). In the office it reached 83.8 % and in the multi-room loop 86.3 %, but in the maze only 14.3 %, because of the stall described above.
- **Trajectory accuracy.** The SLAM position error was 0.57 m on average. For comparison, the wheel odometry alone, with the injected noise, had an average error of 2.54 m in the same episodes. So SLAM helped a lot with accumulated drift, even though over short stretches the two were similar.
- **Loop closures.** Only 35.2 % of the 1051 accepted closures were correct by the strict test, a lower bound because of how timing is matched to ground truth.
- **Navigation.** Nav2 reported 50.0 % of 178 goals reached, but when checked against the robot's true position only 29.2 % were. The dominant failure was Nav2 refusing to plan because the position estimate (AMCL) put the robot's footprint inside a wall while its true position was in free space. A diagnostic on one development world supports this: with the estimated position, 6 of 19 goals were reached, and with the true position 19 of 20. So the low number mostly reflects the localisation set-up, not the planner.
- **Obstacle avoidance.** 4 of 6 trials succeeded: 3 of 3 with a static U-shaped trap, but only 1 of 3 when a box suddenly started moving.
- **Responsiveness.** The robot reached half speed 166 ms after a command and stopped in 260 ms.

The full discussion of what each number really measures, the known biases and the failure modes is in the findings and audit documents listed in [results, docs and the paper pipeline](13_results_docs_and_paper_pipeline.md).

## 11. From numbers to paper

To keep the paper trustworthy, no number is typed by hand. A script reads every episode's summary file, computes the statistics, and writes a values file and tables. Another script draws the figures straight from the raw data. The paper's text then pulls from these. This pipeline, which files are generated and which are written by people, and a guide to every document in the `docs` folder are in the [same results and docs explainer](13_results_docs_and_paper_pipeline.md).

## 12. What is still missing

An honest ending lists the gaps:

- Nothing from the navigation and SLAM campaign ran on the physical robot or the Jetson.
- The camera-to-actuator latency chain was never measured.
- The decision and fusion logic, and the semi-automatic and automatic modes, are designs only.
- The arm and vacuum are not driven by the firmware.
- Noise robustness (clean versus noisy sensors) and comparison with other coverage methods were not evaluated.
- Some of the test scripts are stale after the camera code moved, and a few launch scripts contain paths from another machine.

If you want to run any of this yourself, the [user manual](../docs/USER_MANUAL.md) walks through it end to end. If you want the details behind any chapter above, use the table below.

---

## Map from story to files

| Chapter | Deep-dive file |
|---|---|
| 1–2 The idea, the robot, the modes | [01 System overview](01_system_overview.md), [03 Manual mode and HMI](03_manual_mode_hmi.md) |
| 3 The simulator | [04 Robot model and worlds](04_robot_model_and_worlds.md) |
| 4 Starting everything | [05 Bringup, interfaces, utilities](05_bringup_interfaces_utils.md), [02 Navigation scripts and tests](02_navigation_scripts_and_tests.md), [14 Topics, TF and data flow](14_topics_tf_and_dataflow.md) |
| 5 Mapping | [06 SLAM and localisation](06_slam_and_localization.md) |
| 6 Moving | [07 Nav2 and controller](07_nav2_and_controller.md) |
| 7 Exploring | [08 Frontier exploration](08_frontier_exploration.md) |
| 8 Trash detection | [11 Camera code](11_object_detection_camera.md), [12 Detection models and benchmarks](12_detection_models_and_benchmarks.md) |
| 9 Evaluation | [09 Evaluation metrics](09_evaluation_metrics.md), [10 Evaluation harness](10_evaluation_harness.md) |
| 10–11 Results and paper | [13 Results, docs and paper pipeline](13_results_docs_and_paper_pipeline.md) |
| Running it | [User manual](../docs/USER_MANUAL.md) |
