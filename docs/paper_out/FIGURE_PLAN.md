# Figure plan for the simulation results

**Written for:** the paper authors, who will take the screenshots themselves.

Figures come in two kinds. **Generated** figures are made by scripts from the result files, so they are exact and reproducible. **Screenshots** need Gazebo or RViz running. Use generated figures wherever possible and screenshots only where a picture of the real simulator matters.

## A. Generated (no screenshot needed)

Files are in `docs/paper_out/figures/` (script: `docs/paper_out/make_figures.py`) and in each campaign's `report/figures/`.

| Figure | File | Use in paper |
|---|---|---|
| Six held-out test worlds, floor plans with reachable area | `figures/fig_test_worlds.png` | Section 7.1, test environments |
| Exploration paths over the floor plan, 3 worlds x 3 seeds, with the coverage reached | `figures/fig_exploration_trajectories.png` | Section 7.3. Shows the good office and multi-room runs and the two maze runs that never left the start |
| Navigation paths, 3 worlds x 4 seeds, with the ground-truth success rate | `figures/fig_navigation_trajectories.png` | Section 7.3 |
| Coverage over time | `~/eval_runs_victus/quick_exploration_noise/report/figures/coverage_vs_time.png` | Section 7.3 |
| Trajectory error (ATE) and relative error (RPE) box plots | same folder: `ate_box.png`, `rpe_box.png` | Section 7.3 |
| Collisions per episode | same folder: `collisions.png` | Section 7.3 |
| Navigation success by world | `~/eval_runs_victus/quick_navigation/report/figures/nav_success.png` | Section 7.3 |

## B. Screenshots to take (6 shots)

Use the same window size and zoom for all of them, and crop to the content. In a caption, say "illustrative run, not a test episode".

Source the environment first, in every terminal:

    source /opt/ros/jazzy/setup.bash
    source ~/Swachh/Navigation/Simulation/vacuum_ws/install/setup.bash

| # | Shot | How | What to frame |
|---|---|---|---|
| S1 | Robot model, close-up | `ros2 launch vacuum_bringup sim.launch.py world:=empty_room use_rviz:=false` | The robot in Gazebo from a 3/4 angle: the 0.30 x 0.25 m body, the two drive wheels, the front caster and the D435i on its mount. Section 3.2 or 7.1 |
| S2 | Test world, 3D view, one per world | `ros2 launch vacuum_bringup sim.launch.py world:=office use_rviz:=false`, then the same with `multi_room_loop`, `maze_dead_ends`, `two_rooms_door` | Top-down or high oblique view with the robot visible. The two avoidance worlds need `world_file:=<repo>/Navigation/Simulation/vacuum_ws/src/vacuum_gazebo/worlds/avoid_u_trap.sdf` (and `avoid_dynamic_sudden.sdf`). Optional if you use the generated floor plans |
| S3 | What the camera sees | With the office running: `ros2 run rqt_image_view rqt_image_view`, select `/camera/color/image_raw` (colour) and then `/camera/depth/image_rect_raw` (depth) | Colour and depth image side by side, plus a note that the simulated field of view is 69.4 degrees. Section 5.3 |
| S4 | Exploration in progress | `cd ~/Swachh/Navigation && ./start.sh explore office` (starts Gazebo, SLAM, Nav2, the explorer and RViz) | RViz after about 60 s: the partial map, the robot, frontier markers, the planned path and the local costmap. Section 5.2 |
| S5 | Finished map | The same run, once exploration reports it is finished | RViz with the complete occupancy grid. Section 7.3 |
| S6 | Costmap layers | The same run | RViz zoomed on the local costmap: obstacle cells from the depth scan and the inflation halo around them. Section 5.3 |

Stop everything between runs with `./start.sh stop`.

## C. Optional, harder to capture

- **Start-occupied failure:** run `./start.sh navigate office`, send goals until the planner refuses; the RViz view then shows the robot footprint touching an inflated cell. It is hard to catch on demand.
- **Dynamic obstacle sequence:** three frames of `avoid_dynamic_sudden` (box hidden, box emerging, robot reacting). This needs the scenario tooling and timing, so it is the least reliable shot.

## Notes

- The laptop runs the simulator on the CPU, so it will be slow. Screenshots do not need real-time speed.
- Windows screenshot shortcut: Win+Shift+S.
- A white or light RViz background prints better. In RViz: Global Options, Background Color.
