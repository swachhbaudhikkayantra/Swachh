# 14 — Combined plan: independent critique + LLM council (2026-10-21)

Sources: independent Opus critic report (findings a-j, alternatives) and the Sonnet-only LLM council (`council/2026-10-21-185011/`). This file is the single list agents work from. Status is updated by the orchestrator.

Governing decisions (council verdict):
- Order: transport -> physics freeze -> metric freeze -> pilot -> campaign. No campaign before a valid pilot.
- Smac Hybrid DUBIN global planner stays unchanged (user instruction). Motion model / planner swaps are out of scope.
- Physics is not tuned with fudge factors; odometry drift is measured. Measured with wheel_separation_multiplier 1.0 (2026-10-21): in-place rotation odom/GT yaw = 0.940-0.942 (stable over 3 repeats), arcs 0.957-0.976, straight lines exact.
- Responsiveness = wall-clock controller latency; cleaning efficiency = secondary, explicitly labelled, until a coverage planner exists; coverage denominator = reachable area; map completeness headline = unaligned.

| # | Item | Source | Status |
|---|---|---|---|
| 1 | Image transport: rmem/wmem 32 MB (persisted via /etc/wsl.conf boot), Cyclone SocketReceiveBufferSize min 16 MB | critic 3, council | DONE, RTAB-Map 17 updates / 0 no-data warnings (was 0-1) |
| 2 | Validity gates (image drop, RTAB-Map stall, RTF, config hash, status 'invalid', G7 rtabmap-alive) | critic 3/6, council blind spot 3 | DONE |
| 3 | Revert wheel_separation_multiplier 0.945 -> 1.0, cmd_vel_timeout 1.5 -> 0.5 | critic 1.2, 4 | DONE |
| 4 | consider_footprint true; one obstacle band 0.03-0.30 m in GT, RTAB-Map, Nav2 | critic 1.3, 2 | DONE |
| 5 | Reachable coverage denominator; unaligned completeness headline; GT success at Nav2-success time + 0.15 m strict; canceled = failure; real row dt; geometry fallback; self-contacts | critic 1.3/1.4/1.6, 2 | DONE |
| 6 | est pose looked up at GT stamp; wall-clock stamps; responsiveness redefined | critic 1.5, 2 | DONE |
| 7 | Known-answer oracle tests (found +20 % swept-area edge bias, fixed) | council blind spot 1 | DONE (113 tests pass) |
| 8 | RTAB-Map STMSize 10, MinInliers 10, FeatureType = detector, Force3DoF | critic 1.1 | DONE |
| 9 | Pilot: 600 s apartment episode through the full harness | council one-thing | RUNNING |
| 10 | Pre-registration + dev/test split of worlds and seeds; campaign files (long exploration episodes, many scripted goals per nav episode) | critic 7, council blind spot 2 | TODO (agent B) |
| 11 | Statistics: per-episode units, cluster bootstrap CIs, sample-size planner from target CI width | critic 1.7, council | TODO (agent A) |
| 12 | Localization ablation: navigation tests with GT localization vs AMCL vs SLAM | critic 5 | TODO (agent C) |
| 13 | Exact polygon collision test (robot rectangle vs SDF boxes/cylinders) replacing grid fallback; tighter loop-closure truth tolerances | critic 1.8, 5 | TODO (agent D) |
| 14 | Distinct textures per room/wall (avoid perceptual aliasing); per-run embedded world path (no shared /tmp file) | critic 1.1, 4 | TODO (agent E) |
| 15 | Costmap ghost obstacles outside 87 deg FOV: spatio-temporal voxel layer with decay (installed 2026-10-21) | critic 4/5 | TODO (agent F) |
| 16 | evo cross-check of ATE/RPE | critic 5 | DEFERRED (oracle tests cover ATE math) |
| 17 | Bag-replay end-to-end test from the pilot run | critic 8 | TODO after pilot |
| 18 | Consolidate docs (METRICS_TO_BE_MEASURED one-sentence definitions, spec README status) | council (Outsider) | TODO (orchestrator) |
| - | Coverage planner (boustrophedon / opennav_coverage), benchmark release | council Expansionist | OVERRULED for now, revisit after a valid campaign |
| - | Smac REEDS_SHEPP / Lattice | critic 5 | OUT OF SCOPE (user: planner unchanged) |
| - | Camera 320x240 for speed | critic 3 | DEFERRED, decide after pilot RTF |
