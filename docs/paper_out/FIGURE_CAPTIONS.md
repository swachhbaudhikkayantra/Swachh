# Figure descriptions and draft captions

**Written for:** the paper authors. All figures below are produced by `docs/paper_out/make_figures.py` from the raw result files (deterministic code, no image generation). Numbers are not typed into captions: the figures and the generated tables carry them.

| File | What it shows | Where | Draft caption |
|---|---|---|---|
| `fig_test_worlds.png` | Floor plans of the six held-out test worlds. Dark = walls and obstacles, light blue = reachable floor | 7.1 | Held-out test environments. Dark cells are walls and obstacles; light cells are floor the robot can reach. Top row: office, multi-room loop, maze with dead ends. Bottom row: two rooms with a door, and the two obstacle-avoidance scenarios (U-shaped trap, box that emerges suddenly). |
| `fig_actual_vs_explored.png` | For each exploration world, the real floor plan (left) and the final SLAM map of each of the three seeds (right). Grey = unexplored | 7.3 | Actual floor plan (left) and the occupancy grid explored by the robot in each of three runs. Maps are placed using the starting pose only, so warped or rotated shapes show SLAM drift. In the maze the explorer sent no goal in two of three runs, so almost nothing was mapped. |
| `fig_exploration_trajectories.png` | Robot paths (colour = time, green dot = start) over the floor plan, 3 worlds x 3 seeds, with the coverage reached in each title | 7.3 | Ground-truth paths during exploration. Colour runs from early (dark) to late (yellow). The robot covers the office and multi-room loop but barely leaves its starting position in two maze runs. |
| `fig_navigation_trajectories.png` | Robot paths during the navigation test, 3 worlds x 4 seeds, with the ground-truth-verified success rate of each run in the title | 7.3 | Ground-truth paths during the navigation test (up to 20 goals per run). Titles give the share of goals reached according to ground truth. Runs in the maze end early because the robot is judged stuck. |
| `fig_coverage_vs_time.png` | Explored share of the reachable area over time, one line per episode, coloured by world | 7.3 | Exploration coverage over time. The office and multi-room runs rise quickly and level off; the maze runs end early. Each line is one episode, so no interval band is drawn. |
| `fig_nav_success.png` | Navigation success per world and pooled: bars for goals Nav2 reported reached and for goals confirmed by ground truth, with 95 percent bootstrap intervals | 7.3 | Navigation success pooled over goals. Light bars: Nav2's own report. Dark bars: goals where the robot was within 0.30 m of the goal according to ground truth. The gap shows that Nav2 often reports success while the robot is still short of the goal. |
| `fig_ate_points.png` | Trajectory error of each exploration episode. Hollow markers = odometry corrupted by contact | 7.3 | Absolute trajectory error of each exploration episode (episodes without a defined error are omitted). Hollow markers mark episodes in which contact with an obstacle corrupted the wheel odometry. |
| `fig_costmap_layers.png` | Three panels from one live headless run of the office world: the SLAM occupancy grid, the global costmap and the 4 x 4 m local costmap. Black = lethal obstacle, dark red = inscribed zone (robot cannot enter), orange = inflation, grey = unknown, green triangle = robot. The snapshot is chosen by a fixed rule (most obstacle and inflation cells in the local costmap, out of 21 snapshots) | 5.3 | Costmap layers during exploration of the office. Left: the SLAM occupancy grid used as the static layer. Middle: the global costmap, in which every wall cell is a lethal obstacle surrounded by an inscribed zone and a decaying inflation zone (radius 0.28 m). Right: the local costmap around the robot (a rolling 4 x 4 m window; it is kept in the odometry frame, so it can be offset slightly from the map frame). Illustrative run, not a test episode. |
| `fig_slam_map_office.png` | The occupancy grid RTAB-Map had built in a live run after about four minutes, office world | optional | Occupancy grid built by RTAB-Map during exploration of the office (illustrative run, partial map). Black = occupied, white = free, grey = unknown. |

## Do not use these repository charts as they are

| File | Problem | Use instead |
|---|---|---|
| `quick_navigation/report/figures/nav_success.png` | Plots Nav2-reported success only, which overstates the ground-truth-verified rate | `fig_nav_success.png` |
| `quick_exploration_noise/report/figures/coverage_vs_time.png` | Shades confidence bands below 0 percent (for three episodes per world) | `fig_coverage_vs_time.png` |
| `quick_exploration_noise/report/figures/ate_box.png` | Box plots of one to three points per world | `fig_ate_points.png` |

## Screenshots (taken by hand, see FIGURE_PLAN.md)

| Shot | What it shows | Draft caption |
|---|---|---|
| S1 | The simulated robot in Gazebo | The simulated robot: a 0.30 x 0.25 m differential-drive base with a front caster and a forward-looking RGB-D camera. |
| S2 | A test world in 3D | The office test environment in Gazebo. |
| S3 | Colour and depth image | Colour and depth images from the simulated camera (69.4 degree horizontal field of view). |
| S4 | RViz during exploration | Exploration in progress: partial occupancy grid, frontier markers, planned path and local costmap. |
| S5 | Finished map in RViz | Occupancy grid at the end of an exploration run. |
| S6 | Costmap close-up | Local costmap: obstacles from the depth scan and the inflation zone around them. |
