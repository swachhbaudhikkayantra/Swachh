# 09 — Worlds and Scenarios

Covers the environments needed by the other specs: sealing the corridor, six new closed test worlds, obstacle/avoidance scenarios, dynamic obstacles, `worlds.yaml`. Depends on: 00.

All worlds are **hand-written SDF** (boxes/cylinders), never Fuel downloads, so that the ground-truth rasteriser (spec 03) can read them exactly.

---

## 9.1 SDF rules (so the rasteriser works)

1. One `<world name="X_world">` per file; `X_world` unique across all files (needed by the ground-truth bridge, spec 01 §1.1).
2. Allowed geometry on collisions: `box`, `cylinder` (vertical axis only), `sphere`, ground `plane`. No meshes, `<include>`, nested models, `polyline`, `capsule`, `ellipsoid`.
3. Poses: model/link/collision `<pose>x y z 0 0 yaw</pose>`; roll and pitch must be 0.
4. Every wall, obstacle and ceiling is its own `<model>` with `<static>true</static>` (except dynamic obstacles, §9.6). Wall models are named `wall_*`; the ceiling `ceiling`; furniture/obstacles any other name unique within the world.
5. The room must be **closed**: the connected free area from the spawn seed must not touch the grid border (spec 03 §3.2.7).
6. Ground plane: `plane` normal 0 0 1 (size at least 20×20), friction defaults. Include the standard `gz-sim-physics-system`, `user-commands`, `scene-broadcaster`, `sensors` (render engine `ogre2`), `contact-system` plugins exactly as the existing worlds do (copy `apartment.sdf` header).
7. Floor decals (rug, etc.) that the robot can drive over: height < 0.03 m (they are ignored by the rasteriser; collision allowed).
8. Obstacle height rule for being an obstacle: top above 0.03 m and bottom below 0.25 m (spec 03 §3.2.4). A table is therefore an obstacle if any part (leg or top) lies in that band.
9. Optional marker for human readers: `<!-- GT-SPAWN x y -->` comments next to candidate spawn points.

## 9.2 Corridor fix (blocks all corridor numbers)

`vacuum_gazebo/worlds/corridor.sdf`: its south wall has two ~1 m gaps (x≈−2.5 and x≈+2.0) that open to empty outside. Fix: add two filler wall models `wall_south_fill_1`, `wall_south_fill_2` (box, height 3.0, thickness 0.2) closing each gap flush with the neighbouring segments. Keep the lintels. Result: sealed 12.2 × 2.4 m corridor. Verify: `gt_grid --world corridor` does not raise `WorldNotSealed`; `A_clean_m2` ≈ interior area (≈ 12.0 × 2.2 = 26.4) minus obstacle footprints.
(Alternative the user may prefer: turn the gaps into real doors to two small rooms; then document it here and add the rooms to `worlds.yaml`. Default = fill.)

## 9.3 Existing worlds (reference)

| World key | File | `<world name>` | Approx. interior | Notes |
|---|---|---|---|---|
| `room` | `empty_world.sdf` | `vacuum_world` | unbounded plane | not usable for coverage (not sealed); used for bare control tests (spec 07) |
| `apartment` | `apartment.sdf` | `apartment_world` | 6.0 × 5.0 m (wall inner faces x∈[−3.0,3.0], y∈[−2.5,2.5]) | 21 models; rug 2 cm high |
| `office` | `office.sdf` | `office_world` | ≈ 8.0 × 6.0 m (walls at ±4.1/±3.1 centres, thickness per file) | pillars r=0.15, desks, chairs, cabinets |
| `corridor` | `corridor.sdf` | `corridor_world` | ≈ 12.0 × 2.2 m | needs §9.2 |

Add the new keys to `WORLD_MAP`/the `dynamic_world_default` expression in `sim.launch.py` and to `choices` in `slam.launch.py` / `exploration.launch.py` (and remove the non-existent `warehouse`, `large` entries or give them files).

## 9.4 New coverage / SLAM worlds

| Key | File | `<world name>` | Layout (exact enough to build) | Serves |
|---|---|---|---|---|
| `empty_room` | `empty_room.sdf` | `empty_room_world` | 6.0 × 6.0 m interior, 4 walls (thickness 0.2, height 3.0), nothing inside, spawn candidates at (±2, ±2), (0,0) | coverage upper bound (#1, #14, A1) |
| `cluttered_room` | `cluttered_room.sdf` | `cluttered_room_world` | 8.0 × 8.0 m interior; 14 boxes/cylinders (sizes 0.3–0.8 m) placed on a fixed list of coordinates stored in the SDF so that obstacle footprint ≈ 15 % of the interior and every free passage is ≥ 0.6 m wide | avoidance density (#3, #4) |
| `two_rooms_door` | `two_rooms_door.sdf` | `two_rooms_door_world` | two 4.0 × 4.0 m rooms side by side joined by a **0.9 m** wide, 0.2 m deep door opening in the shared wall | door traversal (#10, #12) |
| `multi_room_loop` | `multi_room_loop.sdf` | `multi_room_loop_world` | 4 rooms (each ≈ 3.5 × 3.5 m) arranged in a ring around a central block, connected by four 0.9 m doors so a closed loop of ≈ 14 m exists; 3–4 distinguishable objects (different box sizes) per room | loop closures (#11), drift (#6, #7) |
| `maze_dead_ends` | `maze_dead_ends.sdf` | `maze_dead_ends_world` | 8.0 × 6.0 m with wall partitions forming 1.0 m corridors and 3 dead ends | recovery/stuck (A6, A7) |
| `symmetric_hall` | `symmetric_hall.sdf` | `symmetric_hall_world` | 10.0 × 4.0 m hall with 4 identical pillar pairs equally spaced (point-symmetric) and no distinguishing features | perceptual aliasing (#11 precision, A10) |

Each file's header comment lists its dimensions, the obstacle coordinates, and the `reachable_seed` and `spawn_candidates` used in `worlds.yaml`.

## 9.5 Obstacle-avoidance scenario worlds (#9, trial level)

Small (≈ 6 × 4 m) closed worlds with one start and one goal and one designed difficulty. Files `avoid_<name>.sdf`, `<world name>` = `avoid_<name>_world`. Start `S` and goal `G` are stored in `worlds.yaml: scenario`. Distance S→G ≈ 4.0 m on the straight line.

| Scenario | Layout | Dynamic? |
|---|---|---|
| `avoid_head_on` | a 0.4 × 0.4 m box centred on the S–G line, 2.0 m from S | no |
| `avoid_narrow_gap` | two boxes forming a **0.60 m** gap on the S–G line (robot width 0.25 m, so 0.175 m clearance each side before inflation; Nav2 inflation radius 0.35 m — the gap is intentionally tight; also generate a variant with 0.80 m) | no |
| `avoid_u_trap` | a U-shaped obstacle (3 boxes, opening facing S) with G behind the U | no |
| `avoid_cluster` | 6 boxes/cylinders scattered with ≥ 0.6 m passages between S and G | no |
| `avoid_dead_end` | corridor branch that dead-ends, G beyond a second branch | no |
| `avoid_dynamic_cross` | a 0.4 × 0.4 × 0.5 m moving box crossing the S–G line at 0.25 m/s starting when the robot passes the midpoint ± seeded delay | yes (§9.6) |
| `avoid_dynamic_sudden` | the moving box starts hidden behind a wall segment and emerges into the robot's path at 0.5 m/s at the seeded delay | yes (§9.6) |

## 9.6 Dynamic obstacles

Gazebo actors are not physical (no collision). Use a **dynamic model + velocity control**:
- Model `dyn_box_N`, `<static>false</static>`, one link, mass 5 kg, box collision + visual, `<gravity>false</gravity>`, large friction-free sliding is not needed: 
- Plugin on the model: `<plugin filename="gz-sim-velocity-control-system" name="gz::sim::systems::VelocityControl"><topic>/model/dyn_box_N/cmd_vel</topic></plugin>` (topic is then a gz `Twist`).
- Bridge entries (static in `gz_bridge.yaml` or a per-world bridge) `/model/dyn_box_N/cmd_vel` ROS `geometry_msgs/msg/Twist` → gz `gz.msgs.Twist` (`ROS_TO_GZ`).
- `dynamic_mover.py` (vacuum_eval node): params `model` (`dyn_box_1`), `waypoints` (list of x,y in `world`), `speed`, `start_delay_s`, `start_trigger` (`time` or `robot_x_beyond:<x>`); it publishes a Twist (world-frame velocity towards the next waypoint, stopping within 0.05 m of the last) at 20 Hz of sim time, deterministic given the sim clock, and logs `events.csv: obstacle_start`.
- Ground truth of dynamic models: each carries the same `gz-sim-odometry-publisher-system` plugin (topic `/model/<name>/ground_truth_odom`, bridged to `/ground_truth/model/<name>`, `nav_msgs/Odometry`); sizes in `worlds.yaml: dynamic_obstacles: {dyn_box_1: {size: [0.4, 0.4]}}`.
- The GT grid ignores dynamic models (they are not static); spec 06 handles them from `dyn_obstacles.csv`.
Verify: the box really collides with the robot (a contact appears) and is pushed; if it does not push the robot, mass/friction need tuning — record the working values here.

## 9.7 `worlds.yaml` (in `vacuum_eval/config/`) — schema

```
worlds:
  apartment:
    sdf_file: <share>/vacuum_gazebo/worlds/apartment.sdf     # resolved via ament index at runtime
    world_name_in_sdf: apartment_world
    timeout_sim_sec: 1200
    reachable_seed: [0.0, 1.0]               # world frame; must be a free cell
    spawn_candidates: [[-2.0, -1.5], [2.0, 1.5], ...]   # verified free, r=0.195+0.10 m
    wall_models: "^wall_|^ceiling$"
    goal_lists:
      fixed: [[x, y, yaw], ...]
      loop_tour: [[x, y, yaw], ...]          # closed tour, only where meaningful
    scenario:                                # avoid_* worlds only
      start: [x, y, yaw]
      goal:  [x, y, yaw]
    dynamic_obstacles:
      dyn_box_1: {size: [0.4, 0.4], waypoints: [[x,y],[x,y]], speed: 0.25, start_delay_s: 0.0}
```
Every `spawn_candidate` and `fixed` goal is validated by test T-03x (free in `navigable`, in `a_reach`).

## 9.8 Verification notes

| Check | Expected | Observed |
|---|---|---|
| each world loads in Gazebo; `gz topic -l` shows `/world/<name>/pose/info` | yes | |
| each world sealed: `gt_grid` does not raise | yes | |
| `A_clean_m2` per world pasted | | |
| `avoid_*` start/goal reachable (A* on GT grid) | yes | |

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-10-20 | Fill the corridor gaps (default) | Fastest way to get a sealed region; doors can be added later |
| 2026-10-20 | Dynamic obstacles via VelocityControl, not actors | Actors have no collision physics |
