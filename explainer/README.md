# Explainer: how everything in this repository works

Each file explains one part, starting with the big picture and ending in line-level detail. They were written by reading the code, and where documents and code disagree, the explainer follows the code and says so. Items marked "not found" or "unverified" were not confirmed.

**New here? Read [00 The story](00_the_story.md) first**: the whole project as one narrative, with a link into the detailed file for every chapter. Then read what you need.

| # | File | Covers |
|---|---|---|
| 01 | [System overview](01_system_overview.md) | Purpose, hardware, subsystems, data flow, operating modes, real vs simulated vs design-only |
| 02 | [Navigation scripts and tests](02_navigation_scripts_and_tests.md) | `start.sh` and the other launchers, setup/preflight scripts, the unit tests and their results |
| 03 | [Manual mode and HMI](03_manual_mode_hmi.md) | Arduino firmware, serial protocol, GTK HMI, safety behaviour |
| 04 | [Robot model and worlds](04_robot_model_and_worlds.md) | URDF, sensors, plugins, bridge, physics, the 18 Gazebo worlds |
| 05 | [Bringup, interfaces, utilities](05_bringup_interfaces_utils.md) | Launch files and arguments, `vacuum_interfaces`, the 12 utility scripts |
| 06 | [SLAM and localisation](06_slam_and_localization.md) | RTAB-Map parameters, map saving, AMCL monitoring, odometry noise |
| 07 | [Nav2 and controller](07_nav2_and_controller.md) | Planner, MPPI, costmaps, behaviour trees, velocity limits |
| 08 | [Frontier exploration](08_frontier_exploration.md) | Frontier detection, scoring, goal rules, finish conditions |
| 09 | [Evaluation metrics](09_evaluation_metrics.md) | Every metric (#1–14, A1–15): formula as coded, caveats |
| 10 | [Evaluation harness](10_evaluation_harness.md) | Episodes, campaigns, validity gates, health flags, CLIs, run layout |
| 11 | [Object detection: camera code](11_object_detection_camera.md) | Stereo pick pipeline, ZMQ protocol, Streamlit app |
| 12 | [Detection models and benchmarks](12_detection_models_and_benchmarks.md) | YOLOv8 / YOLOv11-seg / RF-DETR, latency benchmark method and results |
| 13 | [Results, docs and paper pipeline](13_results_docs_and_paper_pipeline.md) | Every doc, results layout, the summary.json → paper tables/figures pipeline |
| 14 | [Topics, TF and data flow](14_topics_tf_and_dataflow.md) | Every ROS topic, transform, action, service and parameter file |

Related: [docs/USER_MANUAL.md](../docs/USER_MANUAL.md) (how to run everything).

## Things the explainers found that differ from older documents

- Map completeness (#8) is coded as the mean of free-cell recall and wall-cell recall, not as an IoU (file 09).
- The 86° depth field of view in the robot config is never applied; only the colour camera's 69.4° is (file 04).
- The deployed pick pipeline uses a COCO YOLOv8s model with ONNX Runtime, not TensorRT and not the custom detectors (file 11).
- `vacuum_interfaces` defines no custom messages, services or actions (file 05).
- Several comments in configs are stale (feature type "ORB", footprint "circle 0.18 m", 1000 Hz physics); the code values are in the files above.

## Caveat on reliability

Fourteen separate writers produced these files from the code, and a few claims were spot-checked (firmware pins, feature type). The rest were not independently verified. When something matters for a result, check the cited source file.
