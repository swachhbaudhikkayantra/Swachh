# Swachh demo: scripts and methodology

Run everything from this folder: `cd ~/Swachh/demo`. Each script sets up ROS, the workspace and the DDS
settings itself. Default world is `office`. **Press Ctrl+C once: the script stops everything it started
(Gazebo, ROS nodes, RViz, harness, windows) and exits. It takes about 3-25 s; extra Ctrl+C presses are ignored
while it cleans up.** You do not need a second terminal. `./stop.sh` exists only for the case where a terminal
was closed or killed and left programs behind.
Run only one simulation at a time: a script refuses to start while anything from an earlier run is still running,
and lists what it found.

Do the demo on `victus` (RTX 5050). On the WSL2 laptop without a GPU the simulator ran at about a quarter of
real time, and RViz's map display raised a shader error (see Troubleshooting).

## What each demo shows, and the command

| # | You want to show | Command | Window(s) |
|---|---|---|---|
| 1 | **Manual mode**: you steer the robot | `./manual.sh` (simulation) / `./hmi.sh` (real robot) | Gazebo, RViz, steering buttons, arrow keys in the terminal |
| 2 | **Robot moves, live map updates**, e.g. spins | `./spin.sh` (spins on the spot) or `./explore.sh` (drives itself) | Gazebo + RViz live map, camera, robot trail |
| 3 | **Completed map of a previous run** | `./oldmap.sh [office\|multi_room_loop\|maze_dead_ends]` | RViz finished map + picture of floor plan vs maps |
| 4 | **Obstacle avoidance** | `./avoid.sh [scenario] [seed]` | Gazebo + RViz (costmap halo, planned path) |
| 5 | **Several worlds** | `./tour.sh` (all, one after another) or `./world.sh <name>` | Gazebo |

Helpers: `./status.sh` (live explorer status, second terminal), `./savemap.sh [world]` (save the live map to
`~/maps/stage5/`), `./navigate.sh [world]` (Nav2 + AMCL on a saved map), `./steer.sh` (steering buttons only),
`./stop.sh` (leftover cleanup only).

Worlds for `world.sh` / `tour.sh`: apartment office corridor empty_room cluttered_room two_rooms_door
multi_room_loop maze_dead_ends symmetric_hall, and the avoidance worlds avoid_u_trap avoid_dynamic_sudden
avoid_dead_end avoid_narrow_gap avoid_narrow_gap_wide avoid_head_on avoid_cluster avoid_dynamic_cross.
Exploration, spin and manual modes accept only the first nine.

Suggested order (about 12 minutes): `tour.sh 15 office multi_room_loop maze_dead_ends avoid_u_trap` (worlds) ->
`manual.sh` (steer, map grows) -> `spin.sh` (map from a turn) -> `oldmap.sh` (finished map) -> `avoid.sh`.
`explore.sh` replaces `spin.sh` if you prefer a fully autonomous run.

## How to read the RViz window (`demo.rviz`)

| What you see | Meaning |
|---|---|
| White / black / grey area | Live map from RTAB-Map: free floor / wall / unknown |
| Green arrows | Where the robot has been (SLAM odometry) |
| Green spheres, red sphere | All frontiers (edges of the known map), the one chosen as the next goal |
| Yellow arrow, magenta line | The Nav2 goal and the planned path |
| Blue line | Explorer path history (also the archived run's path in `oldmap.sh`) |
| Coloured halo around obstacles | Local costmap: obstacles plus inflation the controller keeps away from |
| Small image panel | What the robot's camera sees |

## Demo 1: manual mode

**Run:** `./manual.sh` (or `./manual.sh apartment`).
**Method:** starts Gazebo, RTAB-Map SLAM, RViz and a Tk steering window. The arrow keys (this terminal) and the
steering buttons both publish velocity commands on `/cmd_vel`; a relay timestamps them and the diff-drive
controller turns the wheels. Click the terminal for keys: arrows drive and spin, space/s stops, q/z and w/x change
speed, Esc quits.
**Show:** drive into a new area and the map grows there; drive back and it stays. Drive slowly: SLAM corrects
drift when it recognises a place it has seen (loop closure).
**Say:** the real robot has the same idea: the touchscreen HMI sends text commands (`MOVE:FORWARD`, `SPEED:1..9`,
`ESTOP`) over USB serial at 115200 baud to the Arduino, which drives the two motors. Run it with `./hmi.sh`.
Only the motors are really wired; vacuum, arm, wiper and UV buttons only set flags. The firmware has no command
timeout, so wheels off the ground for the first test and the e-stop within reach.
Optional 3D loop-closure viewer: `./manual.sh office --viz`.

## Demo 2: robot moves, map updates live

**Run:** `./spin.sh [world] [turns] [rad/s]` (default `office 1 0.5`).
**Method:** starts Gazebo, SLAM and RViz, waits for the first map, then publishes a rotation command until the
wheel odometry says the robot has turned the requested angle. It prints the known map cells before, every 3 s
during, and after the turn. The stack then stays up so you can keep talking, steer with `./steer.sh`, or save
the map with `./savemap.sh`.
**Show:** the printed line, e.g. `turned 180 deg | map known N cells`, rising while the grey area in RViz turns
white. The robot sees only a 69.4 degree wedge ahead (one forward camera), so the map is a fan at first and
fills as it turns.
**Say:** the map comes from one RGB-D camera plus wheel odometry, no lidar. RTAB-Map updates the map about once
a second. In `./explore.sh` the robot decides where to go by itself: every frontier is scored
`S = 1.0 ln(1+n) - 1.5 d - 0.8 p` (n frontier size, d distance, p obstacle penalty), the best becomes the goal,
Smac Hybrid-A* plans a path and MPPI follows it at 20 Hz. Do not touch the keyboard during `explore.sh`.
Note: odometry is clean in the live demo; the paper's exploration runs injected odometry noise.

## Demo 3: the completed map of a previous run

**Run:** `./oldmap.sh` (office, seed 101), `./oldmap.sh multi_room_loop` (seed 103), `./oldmap.sh maze_dead_ends`
(seed 102). Pick another seed with `SEED=102 ./oldmap.sh office`.
**Method:** no simulation. It reads the archived run in
`results/runs/quick_exploration_noise/<world>/frontier/seed_N/` (2026-10-25 campaign, odometry noise on),
publishes its final map and path to RViz, and opens the paper's figure (true floor plan next to the three
explored maps) cropped to that world. The line it prints gives coverage, completeness and trajectory error.
**Numbers:** office seed 101 coverage 91.6%, completeness 73.8%. Pooled over nine runs the paper reports 61.4%
(office 83.8%, multi-room loop 86.3%, maze 14.3%).
**Say:** warped walls are SLAM drift (maps are placed using the start pose only, so drift shows). The maze row
is the honest failure: in two of three runs the explorer never moved because it found no goal with 0.30 m
clearance. It is not fixed.

## Demo 4: obstacle avoidance

**Run:** `./avoid.sh` (static U-trap, seed 101) or `./avoid.sh avoid_dynamic_sudden 102` (moving box).
**Method:** runs one scripted scenario through the evaluation harness with the Gazebo GUI on: the robot drives
from (-2,0) to the goal at (2,0) using Nav2 on a ground-truth map. RViz opens beside it showing the local
costmap and planned path. Success means the goal is reached with no contact. The result is printed at the end and
written to `~/eval_runs/demo_<time>/` (its own name, not mixed with the evaluation runs; this is a demo run, not
evaluation data).
**Numbers:** 4 of 6 trials overall. Static U-trap 3 of 3. Sudden moving box 1 of 3. Mean minimum clearance
0.159 m (slightly optimistic: the wheels stick out 1.8 cm past the footprint).
**Say:** the static case is handled; the robot does not reliably avoid a suddenly moving obstacle. Only three
trials per scenario, so the intervals are wide.

## Demo 5: several worlds

**Run:** `./tour.sh [seconds] [world ...]`, e.g. `./tour.sh 20 office multi_room_loop maze_dead_ends avoid_u_trap`.
Each world opens in Gazebo for that long; press Enter to skip ahead; Ctrl+C ends. Or open one:
`./world.sh multi_room_loop`.
**Say:** 18 hand-built worlds; seven are development worlds used while building (apartment, empty_room,
cluttered_room and four avoidance scenarios) and the held-out test worlds were frozen before the test
campaign. Each world has deliberately distinct, loud wall and floor textures with marker shapes, so SLAM has
visual features and does not confuse places (anti perceptual aliasing). `symmetric_hall` is the exception: it is
identical everywhere on purpose, to test exactly that. The moving box in `avoid_dynamic_*` only moves under
`./avoid.sh`.
Worlds in the paper's results: office, multi_room_loop, maze_dead_ends (exploration); office, two_rooms_door,
maze_dead_ends (navigation); avoid_u_trap, avoid_dynamic_sudden (avoidance).

## Also available: navigation on a saved map

`./explore.sh` then, while it runs, `./savemap.sh`; stop; `./navigate.sh`. In RViz click **2D Pose Estimate** at the
spawn point and **Nav2 Goal** to send goals. Say: navigation success was 29.2% (52 of 178 goals, ground-truth
checked) mainly because AMCL's pose often put the footprint inside a wall; with perfect pose 19 of 20 goals were
reached (one development-world episode, indicative only). Do not use `Navigation/start.sh navigate`: it starts the
empty world. A partial `~/maps/stage5/office.*` already exists from testing; re-save after a full run.

## Honest limits to state

- Navigation and SLAM results are from simulation only. Nothing ran on the physical robot or the Jetson.
- Only the drive motors are wired on the real robot; the arm and vacuum are not implemented. Semi-automatic and
  automatic modes are design only.
- The simulated robot is smaller than the real one (0.30 x 0.25 m vs about 0.60 x 0.50 m), has a noiseless
  camera and a 69.4 degree field of view.
- Three or four seeds per world, so the intervals are wide.
- The textured walls make loop closure easier than in a plain real building.
- The explorer's own `coverage_pct` in `/exploration/status` is not real coverage; `status.sh` does not show it.

## What has and has not been tested (honest status)

Tested on the WSL2 laptop earlier: `world.sh`, `explore.sh` (explorer ran), `status.sh`, `savemap.sh`,
`navigate.sh` (office world, AMCL, Nav2), `manual.sh` start-up (before the new RViz config), `stop.sh`.
Tested since: `oldmap.sh` publishes the map and path and opens its picture window; RViz subscribed to it.
**Not tested after being written or changed:** `demo.rviz` rendering, `spin.sh`, `tour.sh`, `avoid.sh`
(the harness with `--headless 0`), `manual.sh` with the new RViz config and real keyboard, `hmi.sh`, `steer.sh`.
Run each once on `victus` before presenting.

## Troubleshooting

- **RViz map not showing / `indexed_8bit_image.vert` shader error** (seen on the WSL2 laptop's software
  renderer, not on `victus`): use `./manual.sh office --viz` for the rtabmap_viz window, or save the map
  (`./savemap.sh`) and open the `.pgm`. `./oldmap.sh` also shows the picture window, which does not need
  RViz's map shader.
- **Nothing happens / SLAM gets no images:** `cat /proc/sys/net/core/rmem_max` must be 33554432
  (`sudo sysctl -w net.core.rmem_max=33554432`). Each script warns if it is too small.
- **No window over SSH:** the scripts switch Gazebo to headless rendering when there is no display; RViz and the
  steering window are skipped.
- **A script says something from an earlier run is still running:** `./stop.sh` (it escalates polite stop, terminate,
  kill). It refuses to touch anything while an evaluation campaign (`run_batch`) is active.
- **Logs** of background parts: `~/.cache/swachh_demo/*.log` (sim, slam, rviz, steer_gui, publisher, figure).
- **Spawn somewhere else:** `SPAWN_X=1 SPAWN_Y=2 ./explore.sh office`.
