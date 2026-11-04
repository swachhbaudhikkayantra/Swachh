# 08. Frontier exploration (package `vacuum_exploration`)

Everything below describes what the code in
`Navigation/Simulation/vacuum_ws/src/vacuum_exploration` does. Files read: `frontier_detector.py`, `goal_selector.py`, `exploration_manager.py`, `frontier_visualizer.py`, `exploration_metrics.py` (header only), `config/exploration_params.yaml`, `launch/exploration.launch.py`, `test/test_goal_selection_guard.py`, `setup.py`.

## 1. The idea in plain words

A frontier is the boundary between space the robot already knows is free and space it knows nothing about. If the robot drives to a frontier and looks, the map grows. Frontier exploration repeats this loop:

1. Look at the current SLAM map (`/rtabmap/map`) and find every frontier.
2. Group neighbouring frontier cells into candidate regions.
3. Score each candidate: bigger is better, nearer is better, being close to a wall is bad.
4. Move the goal onto a safe free cell near the best candidate and ask Nav2 to drive there.
5. If Nav2 fails, times out, or the robot stops making progress, blacklist that spot for a while and pick another.
6. Stop only when there have been no frontiers for several checks in a row, the map has stopped growing, and the robot is standing still.

Three ROS nodes do the work; a fourth (the visualizer) only draws markers, and a fifth (`exploration_metrics`) writes a legacy CSV.

| Node (executable) | Role |
|---|---|
| `frontier_detector` | Finds and clusters frontiers on the map, publishes centroids |
| `exploration_manager` | State machine; scores, snaps, sends goals, handles failures and termination. The scoring class `GoalSelector` (`goal_selector.py`) is a plain Python class imported by the manager, not a node |
| `frontier_visualizer` | RViz markers (goal arrow, trajectory, status text) |
| `exploration_metrics` | Legacy 1 Hz CSV and `metadata.yaml` (not part of the decision logic) |

## 2. Topics, actions and TF

| Name | Type | Direction | Used by |
|---|---|---|---|
| `/rtabmap/map` | `nav_msgs/OccupancyGrid` | in | detector (QoS reliable, volatile, depth 1; topic is the `map_topic` param), manager (same QoS, topic hardcoded) |
| `/frontiers/centroids` | `geometry_msgs/PoseArray` | detector -> manager | one pose per cluster: x, y = centroid, `position.z` = cluster size in cells (size is smuggled in z) |
| `/frontiers/markers` | `visualization_msgs/MarkerArray` | out | green spheres, scale `min(0.15 + 0.01*size, 0.40)`, lifetime 1 s |
| `/odom` | `nav_msgs/Odometry` | in | manager (speed, oscillation check), visualizer |
| TF `map` -> `base_footprint` | tf2 | in | manager robot position in map frame; falls back to `/odom` pose with a one-time warning if TF is missing |
| `navigate_to_pose` | Nav2 action `NavigateToPose` | manager is client | goal pose in frame `map`, orientation `w = 1.0` (yaw 0) |
| `/cmd_vel_nav` | `geometry_msgs/Twist` | manager out | only for the bootstrap spin |
| `/exploration/status` | `std_msgs/String` (JSON) | out | state, coverage, counters. Published every FSM tick (10 Hz) and, after FINISHED, at 1 Hz |
| `/exploration/goal_events` | `std_msgs/String` (JSON), reliable depth 50 | out | one `started` and one `ended` event per goal |
| `/exploration/current_goal` | `PoseStamped` | out | the snapped goal that was sent (RViz, visualizer) |
| `/exploration/selected_marker` | `MarkerArray` | out | red sphere (0.45 m) on the chosen frontier centroid, lifetime 5 s |
| `/exploration/finished` | `std_msgs/Bool`, transient-local, reliable, depth 1 | out | `True` once, when FINISHED is reached |
| `/exploration/goal_marker`, `/exploration/trajectory`, `/exploration/status_text` | markers | visualizer out | arrow, path history (max 2000 points), text overlay (4 Hz) |

Goal event JSON fields: `goal_seq`, `event` (`started`/`ended`), `t_sent`, `t_end`, `x`, `y` (snapped goal), `result`, `nav2_error_code`, `frontier_x`, `frontier_y`. The `result` for an ended event is one of `succeeded`, `rejected`, `nav_aborted`, `timeout`, `oscillation`.

## 3. Frontier detection (`frontier_detector.py`)

A timer fires at `publish_rate` (2 Hz). If no map has arrived yet it does nothing. Otherwise:

**Step 1, find frontier cells.** The grid is read as a flat int8 array. For every cell with `row` in `1..height-2` and `col` in `1..width-2` (the outer border is skipped) the cell is a frontier cell if its value is exactly `0` (free) and at least one of its 4 neighbours (up, down, left, right) has value `-1` (unknown). Occupied cells (non-zero values, including >0 probabilities) never count as frontier cells. The code is a pure Python double loop over the whole grid.

**Step 2, cluster (BFS).** `radius_cells = max(1, int(cluster_radius / resolution))`. Take any unvisited frontier cell as a seed. Breadth-first search: for each popped cell, every unvisited frontier cell inside the square window `[-radius_cells, +radius_cells]` in both row and column (a square, not a circle) joins the cluster and is queued. So two frontier cells end up in the same cluster if a chain of cells links them with every link at most `radius_cells` apart in each axis. At 0.05 m resolution, `radius_cells = 10`.

**Step 3, filter.** A cluster is dropped if it has fewer than `min_frontier_size` cells (5).

**Step 4, centroid.** The mean row and column of the cluster's cells, converted to world coordinates: `x = origin_x + (avg_col + 0.5) * res`, `y = origin_y + (avg_row + 0.5) * res`. Note the centroid is the average of all cells, so for a curved or long frontier it can lie off the frontier itself, possibly inside unknown or occupied space. This is why the manager later snaps the goal (section 5).

Each surviving cluster gets `id` = its index in the BFS cluster list (counted before filtering). The detector publishes `PoseArray` (frame `map`) and the markers.

## 4. How the manager receives frontiers (`_frontiers_callback`)

For each pose in `/frontiers/centroids`:

- size = `max(1, int(pose.position.z))` cells.
- If a map has been received, frontier length in metres = `size * resolution`. The frontier is dropped if that is below `min_frontier_size_m` (0.5). At 0.05 m resolution this means at least 10 cells (the unit test asserts 10 cells passes and 8 fails). This is a second, stricter filter on top of the detector's 5 cells. If no map has yet reached the manager, this filter is skipped.
- Surviving frontiers get fresh ids `0, 1, 2...` in list order. The manager's ids therefore differ from the detector's ids and change between messages (the code comments say so, and the blacklist is matched by position for that reason).

## 5. The state machine (`exploration_manager.py`)

The FSM timer runs at 10 Hz (every 0.10 s). All times use the node clock (`use_sim_time` is true in the launch file, so these are simulation seconds).

| State | What happens | Next |
|---|---|---|
| `IDLE` | logs, nothing else | `WAITING_FOR_MAP` |
| `WAITING_FOR_MAP` | Wait until the map has at least one free cell (value 0). Bootstrap spin if no map (see 5.1) | `DETECT_FRONTIERS` once a map with free cells exists |
| `DETECT_FRONTIERS` | First runs the no-information-gain check (5.7). If the frontier list is non-empty: reset the no-frontier counter, go on. Else increment the counter and test completion (section 8) | `SELECT_GOAL`, stay, or `FINISHED` |
| `SELECT_GOAL` | Score frontiers (section 6). If none eligible, log a warning | `SEND_GOAL`, or back to `DETECT_FRONTIERS` |
| `SEND_GOAL` | Snap, check distance, send to Nav2 (5.3) | `NAVIGATING` or back to `DETECT_FRONTIERS` |
| `NAVIGATING` | Watch result, timeout, oscillation (section 7) | `GOAL_REACHED` or `RECOVERING` |
| `GOAL_REACHED` | `goals_completed += 1`, clear current frontier | `DETECT_FRONTIERS` |
| `RECOVERING` | `goals_failed += 1`; logs a warning when the count is a multiple of 5 ("temporarily tightening frontier filter") but nothing is actually tightened; clear current frontier | `DETECT_FRONTIERS` |
| `FINISHED` | Logs the summary, publishes status and `/exploration/finished = True`, cancels the FSM timer, then keeps publishing status at 1 Hz | terminal |

Each tick starts by purging expired blacklist entries and ends by publishing `/exploration/status`.

### 5.1 Bootstrap spin

RTAB-Map publishes no map until the robot has moved (the code comment cites a check on 2026-10-20). Time is measured from the first tick in `WAITING_FOR_MAP`. If there is still no map with free cells, then while `3.0 s <= waited < 3.0 + 8.0 s` the manager publishes `Twist` with `angular.z = 0.4` rad/s on `/cmd_vel_nav` (every tick in that window). As soon as a map with free cells arrives the state moves on and the spin stops, whatever the elapsed time.

### 5.2 Getting from detection to a goal

The centroid of a frontier sits on the edge of unknown space and is often not plannable by Nav2 ("no valid path found", per the code comment). So the manager does not send the centroid. It sends a snapped point.

### 5.3 Goal snapping and clearance (`_snap_goal`) and the 0.30 m rules

There are two separate 0.30 m numbers; do not confuse them.

**Goal clearance (`goal_snap_clearance_m` = 0.30 m).** The latest map is reshaped to (height, width). "Free" means value exactly 0. A Euclidean distance transform gives, for every free cell, the distance in metres to the nearest non-free cell, where non-free means unknown (-1) or occupied. Candidate cells are those with that distance >= 0.30 m. If none exist, snapping fails. Otherwise the candidate nearest (straight-line, cell centre) to the frontier centroid is picked, provided it lies within `goal_snap_max_m` (1.50 m) of the centroid; otherwise snapping fails. Because unknown cells count as blocking, a goal can only be placed at least 0.30 m inside known free space.

**Snap failure** (`no_snap`): the frontier is blacklisted immediately and no goal is sent; the FSM returns to `DETECT_FRONTIERS`.

**Goal-at-robot rule (`min_goal_distance` = 0.30 m).** After snapping, if the snapped goal is less than 0.30 m (Euclidean, map frame) from the robot's map-frame position, no goal is sent. The frontier is blacklisted with reason `goal_at_robot` and `frontiers_skipped` is incremented. If the robot position is unknown the check passes (unit-tested).

The same `min_goal_distance` value (0.30) is also given to the `GoalSelector`, which skips frontiers whose raw centroid is closer than 0.30 m to the robot (section 6). Both come from the yaml (`goal_selector` and `exploration_manager` sections hold separate 0.30 entries; the manager reads its own entry for both uses).

If the Nav2 action server is not available within 5.0 s, the manager logs an error and returns to `DETECT_FRONTIERS` (no blacklisting).

### 5.4 Sending the goal

`NavigateToPose` goal in frame `map` at the snapped (x, y), z = 0, orientation `w = 1.0`. Sequence counters are incremented so late callbacks from older or cancelled goals are ignored (`_goal_seq`). A reply that arrives for an outdated goal and was accepted is cancelled. If Nav2 rejects the goal, the result is recorded as ABORTED with a "rejected" flag. On sending, the manager records the map's free-cell count (`_free_at_send`), the goal start time, resets the oscillation reference, increments `goals_sent` and publishes the `started` event.

## 6. Scoring formula (`goal_selector.py`)

`select_best` loops over all frontiers and keeps the highest score, skipping:

- frontiers whose id is in the blacklisted id set (section 7.4), and
- frontiers whose centroid is closer than `min_goal_distance` (0.30 m) to the robot.

If nothing survives it returns `None`, and the manager goes back to `DETECT_FRONTIERS`.

```
score(f) = w_info * ln(1 + size_cells)
         - w_dist * dist(robot, centroid)
         - w_obs  * obstacle_penalty(centroid)
```

Higher is better. Note the docstring in the file header says "size(f)", but the code uses the natural log of `1 + size`.

| Constant | Value | Where set | Meaning |
|---|---|---|---|
| `w_info` (`weight_info_gain`) | 1.0 | yaml, manager param | weight on `ln(1 + size)` |
| `w_dist` (`weight_distance`) | 1.5 | yaml | weight on straight-line distance in metres (not path length) |
| `w_obs` (`weight_obstacle_penalty`) | 0.8 | yaml | weight on the obstacle penalty |
| `min_goal_distance` | 0.30 m | yaml | selector skip radius |
| `obstacle_search_radius` | 0.50 m | `GoalSelector` constructor default (not in yaml, not passed by manager) | window for the penalty |

Distance uses the robot position from TF (`map`->`base_footprint`), or `(0, 0)` if neither TF nor odom is available.

**Obstacle penalty.** Convert the centroid to grid indices (`col = int((cx - ox)/res)`, `row = int((cy - oy)/res)`). Scan the square window of half-width `max(1, int(0.5 / res))` cells around it. An obstacle cell is one with value > 50. Take the smallest Euclidean distance `d` from the centroid cell to any obstacle cell in the window. If none: penalty 0. Otherwise `penalty = max(0, 1 - d / 0.5)`: 1 when touching, falling linearly to 0 at 0.5 m. Unknown cells are not obstacles here. If no map is available the penalty is 0.

The maximum possible penalty cost is `w_obs * 1 = 0.8`, small next to distance: every metre costs 1.5, and one doubling of cluster size adds only about `ln 2 = 0.69`.

## 7. Failure handling while navigating

### 7.1 Result handling
Each tick in `NAVIGATING`, if a result arrived:

- `STATUS_SUCCEEDED`: `succeeded` event, remember `(frontier x, y, free count at send, frontier message count)` for the gain check, go to `GOAL_REACHED`.
- Anything else (aborted, canceled, rejected): event `rejected` or `nav_aborted`, blacklist frontier (reason `nav2_failure`), go to `RECOVERING`.

### 7.2 Goal timeout
`elapsed = now - goal_start_time`. If `elapsed > goal_timeout` (30.0 s): cancel the goal, event `timeout`, blacklist (reason `timeout`), `RECOVERING`.

### 7.3 Oscillation / no-progress cancel
The odometry callback maintains `_osc_ref` (x, y, t) and `_last_move_time`:

- When the first odom message arrives, or after a new goal resets it to None, `_osc_ref` is set to the current pose.
- Whenever the robot is at least `oscillation_distance` (0.30 m) away from `_osc_ref`, `_osc_ref` is moved to the current pose and `_last_move_time` = now.
- Whenever the angular speed is >= 0.05 rad/s, `_last_move_time` = now (in-place rotation, e.g. Nav2 recoveries, counts as activity).
- `_last_move_time` is also set to now when a goal is sent and when the map first arrives.

In `NAVIGATING`, if `now - _last_move_time > oscillation_timeout_sec` (15.0 s): cancel goal, event `oscillation`, blacklist (reason `oscillation`), `RECOVERING`. The check uses `/odom` positions (odom frame), only as relative displacement, so odom drift against the map does not matter here. The timeout check comes before the oscillation check in the same tick.

### 7.4 Blacklist
Each entry stores centroid x, y, a failure count, last failure time and `expiry_sec` (60.0 s).

- Adding: if an existing entry lies within `blacklist_radius` (0.50 m, a code default not present in the yaml) of the frontier centroid, its failure count is incremented and its time refreshed; otherwise a new entry is added. Entries are matched by position because frontier ids are only list indices.
- Applying: in `SELECT_GOAL`, any current frontier whose centroid is within 0.50 m of any entry is excluded.
- Expiry: an entry is removed when `now - last_failure_time > 60.0 s`. Each refresh restarts the 60 s.
- `retry_count` (3) is declared and read into `_retry_count`, but nothing else uses it: a frontier is blacklisted after the first failure, not the third. Failure counts are only logged.
- Reasons used: `no_snap`, `goal_at_robot`, `nav2_failure`, `timeout`, `oscillation`, `no_information_gain`.

### 7.5 No-information-gain check
After a successful goal, in the next `DETECT_FRONTIERS` ticks, once a new frontier message has arrived, the manager checks (`no_information_gain`): is there still a current frontier within 0.50 m of the reached frontier's centroid, and did the map's free-cell count grow by fewer than `map_growth_threshold` (10) cells since the goal was sent? If both, the spot is blacklisted (reason `no_information_gain`, a synthetic frontier of size 1, `frontiers_skipped += 1`). If not, it keeps checking until two frontier messages have passed since success, then gives up on the check. If the frontier is gone, no blacklist (unit-tested).

## 8. Finish conditions

`_check_completion` is only evaluated in `DETECT_FRONTIERS` on a tick with an empty frontier list. All three must hold at once:

| # | Condition | Constants |
|---|---|---|
| 1 | `no_frontier_count >= no_frontier_consecutive_checks` | 5. The counter increments once per FSM tick (0.10 s) with an empty list, and resets to 0 when frontiers are present. So this is about 0.5 s of continuous emptiness, not 5 detector cycles (the detector runs at 2 Hz) |
| 2 | Map stable: the oldest and newest entries of the free-cell history (a deque of the last 60 map messages) span at least `map_growth_patience_sec` (15.0 s) and the free-cell growth across them is `< map_growth_threshold` (10 cells) | window needs >= 2 entries and >= 15 s span |
| 3 | `|odom linear.x| < stationary_vel_threshold` (0.02 m/s) | |

When true, state becomes `FINISHED`. The manager does not otherwise end exploration (there is no overall time limit in this package).

## 9. Parameters

Values in `config/exploration_params.yaml` unless the source column says "code default". Launch passes this yaml to the detector and manager (and metrics), with `use_sim_time: True`.

| Parameter | Node | Value | Source | Notes |
|---|---|---|---|---|
| `map_topic` | detector | `/rtabmap/map` | yaml | |
| `publish_rate` | detector | 2.0 Hz | yaml | |
| `cluster_radius` | detector | 0.50 m | yaml | -> 10 cells at 0.05 m |
| `min_frontier_size` | detector | 5 cells | yaml | |
| `weight_info_gain` | selector/manager | 1.0 | yaml (`goal_selector` section, but the manager reads its own declared values, see note) | |
| `weight_distance` | same | 1.5 | yaml | |
| `weight_obstacle_penalty` | same | 0.8 | yaml | |
| `min_goal_distance` | manager | 0.30 m | yaml (`exploration_manager` section) | |
| `goal_timeout` | manager | 30.0 s | yaml | |
| `retry_count` | manager | 3 | yaml | unused |
| `blacklist_expiry_sec` | manager | 60.0 s | yaml | |
| `no_frontier_consecutive_checks` | manager | 5 | yaml | |
| `map_growth_patience_sec` | manager | 15.0 s | yaml | |
| `map_growth_threshold` | manager | 10 cells | yaml | also used by the no-gain check |
| `stationary_vel_threshold` | manager | 0.02 m/s | yaml | |
| `oscillation_distance` | manager | 0.30 m | yaml | |
| `oscillation_timeout_sec` | manager | 15.0 s | yaml | |
| `min_frontier_size_m` | manager | 0.5 m | yaml | |
| `blacklist_radius` | manager | 0.50 m | code default only | |
| `goal_snap_clearance_m` | manager | 0.30 m | code default only | |
| `goal_snap_max_m` | manager | 1.50 m | code default only | |
| `bootstrap_wait_sec` | manager | 3.0 s | code default only | |
| `bootstrap_spin_sec` | manager | 8.0 s | code default only | |
| `bootstrap_spin_wz` | manager | 0.4 rad/s | code default only | |
| `obstacle_search_radius` | `GoalSelector` | 0.50 m | constructor default | not a ROS parameter |
| `output_base_dir`, `log_rate`, `nav2_config`, `exploration_config` | metrics | `~/bags/stage4b`, 1.0 Hz, ... | yaml | logging only |

Note on the weight/`min_goal_distance` yaml entries: the yaml has a `goal_selector:` block, but the launch file starts only nodes named `frontier_detector`, `exploration_manager`, `frontier_visualizer`, `exploration_metrics`. No node is named `goal_selector`, so that yaml block is not applied to any node by this launch file. The manager uses its own declared defaults for the weights and `min_goal_distance` (the `exploration_manager:` yaml block does contain `min_goal_distance: 0.30` but not the weights). The declared defaults equal the yaml values (1.0, 1.5, 0.8, 0.30), so behaviour is identical today.

Launch extras: `start_manager` (false runs the stack without the manager), `enable_visualizer`, `enable_legacy_metrics`, `environment` (one of apartment, office, room, corridor, empty_room, cluttered_room, two_rooms_door, multi_room_loop, maze_dead_ends, symmetric_hall), spawn pose, headless, odometry mode and noise arguments are passed through. Start-up order: simulation at T+0 s, RTAB-Map at T+12 s, Nav2 at T+20 s, exploration nodes and RViz at T+28 s.

## 10. Worked example

Assume map resolution 0.05 m, robot at (0, 0) in the map frame, all weights at defaults, no blacklist entries.

The detector finds three clusters (all at least 5 cells) and publishes them. The manager keeps those whose length >= 0.5 m, i.e. at least 10 cells:

| Frontier | Cells | Length | Centroid | Distance | Nearest obstacle to centroid | Penalty |
|---|---|---|---|---|---|---|
| A | 40 | 2.0 m | (2.0, 0.0) | 2.000 | none within 0.5 m | 0 |
| B | 100 | 5.0 m | (4.0, 0.0) | 4.000 | 0.25 m | `1 - 0.25/0.5 = 0.5` |
| C | 12 | 0.6 m | (1.0, 0.5) | 1.118 | none | 0 |
| D | 8 | 0.4 m | (0.8, 0.0) | 0.8 | - | dropped by the 0.5 m filter |

Scores (`1.0*ln(1+n) - 1.5*d - 0.8*pen`):

- A: `ln 41 = 3.714`; `3.714 - 3.000 - 0 = 0.714`
- B: `ln 101 = 4.615`; `4.615 - 6.000 - 0.4 = -1.785`
- C: `ln 13 = 2.565`; `2.565 - 1.677 - 0 = 0.888`

C wins even though it is the smallest, because it is the nearest. Snapping: build the clearance map; find the free cell with >= 0.30 m clearance nearest to (1.0, 0.5). Say that is (0.95, 0.40), 0.11 m away (under 1.5 m, so it is accepted). It is 1.03 m from the robot (over 0.30 m), so the goal is sent to Nav2.

Outcomes:

- Succeeds in 12 s: `succeeded` event, `goals_completed = 1`, back to detection. If a frontier is still within 0.5 m of C and the free-cell count grew by fewer than 10 cells since sending, C's location is blacklisted as `no_information_gain`.
- The robot moves less than 0.30 m and does not rotate for 15 s: `oscillation`, C blacklisted at (1.0, 0.5) for 60 s; any frontier within 0.5 m of that is skipped, so A is chosen next.
- Nav2 still driving at 30 s: `timeout`, same blacklist handling.

Finishing: suppose later the frontier list is empty. The counter reaches 5 after about 0.5 s of consecutive empty ticks. If the free cell count over the last 15 s or more changed by under 10 cells and the robot speed is below 0.02 m/s, the state goes to FINISHED and `/exploration/finished` is published True. If the robot is still moving or the map is still growing, the check fails and repeats on the following ticks.

## 11. Documented stall in maze_dead_ends (as documented only)

`docs/EVALUATION_FINDINGS_2026-10-25.md` section 4 records that in `maze_dead_ends`, seeds 101 and 103 never moved. The document attributes it to: the bootstrap spin stopping after about 0.8 rad when the first map arrived, leaving the robot facing a wall 0.5-0.75 m away with a first map of 0.5-0.7 m2; `_snap_goal` treating unknown cells as blocked so no cell reached the 0.30 m clearance and the only frontier was blacklisted; and no fallback existing, since `RECOVERING` only increments a counter, so the robot waited until the harness stuck rule fired at 180 s. The document classifies this as deterministic and spawn-pose dependent, not an infrastructure fault, and states it was not rerun. It also states the corridors (1.0-1.1 m wide) were not the cause.

**One-line summary:** the detector finds free-next-to-unknown cells and clusters them, the manager scores clusters by `ln(1+size) - 1.5*distance - 0.8*obstacle_penalty`, snaps the best onto a free cell with 0.30 m clearance, sends it to Nav2 with a 30 s timeout and 15 s no-progress cancel, blacklists failures for 60 s within 0.5 m, and finishes only when frontiers are absent, the map is stable for 15 s and the robot is still.
