# 06 — Safety: Collisions, Obstacle Avoidance, Clearance

Covers: #3 total collisions, #4 % obstacle avoidance, #9 obstacle avoidance success rate (trial level), A5 clearance.
Depends on: 00, 01, 02 (raw files), 03 (GT grid; needs the `obs_id` addition in §6.5), 05 (scripted goals / scenarios), 09 (obstacle scenarios and dynamic obstacles).
Module: `vacuum_eval/metrics/safety.py`.

---

## 6.1 Physical situation (verified by reading, 2026-10-20)

- Robot collision geometry: `base_link` box 0.300 × 0.250 × 0.100 m centred at `base_footprint` height 0.093 m (spans z 0.043–0.143), camera body on top of a mount at x=+0.10; wheels (r=0.033) and a front caster are separate links. The chassis does not touch the floor, so a contact sensor on the chassis only fires on real obstacle hits.
- All four worlds already load `gz-sim-contact-system` (server side). The robot has **no** `<sensor type="contact">`, so nothing is reported today.
- Contacts with the wheels/caster on the ground plane are normal and must be ignored; do not attach sensors to wheels/caster.
- Depth-to-scan range_min is 0.20 m, so obstacles closer than ~0.2 m are invisible to Nav2: contact detection must not depend on the camera.

## 6.2 Contact sensors (robot description change)

File: `vacuum_description/urdf/_gazebo.xacro` (a `<gazebo reference="base_link">` block; sensors attach to the link that owns the collision).

1. **Discover exact collision names first** (URDF fixed joints are lumped, so names change): 
   ```
   xacro .../vacuum.urdf.xacro > $SCRATCH/v.urdf && gz sdf -p $SCRATCH/v.urdf | grep -n 'collision name'
   ```
   Expected (verify; paste into Verification notes): `base_link_collision` for the chassis and `base_link_fixed_joint_lump__camera_link_collision` (and possibly `..._camera_mount_link_collision`) for the camera parts, `..._caster_wheel_link_collision`, wheel collisions on the wheel links.
2. Add one contact sensor per **body collision** (chassis, camera, camera mount; **not** wheels, **not** caster):
   ```
   <gazebo reference="base_link">
     <sensor name="chassis_contact" type="contact">
       <always_on>true</always_on><update_rate>50</update_rate>
       <contact><collision>base_link_collision</collision></contact>
       <topic>/vacuum_robot/contacts/chassis</topic>
     </sensor>
     <sensor name="camera_contact" type="contact">
       <always_on>true</always_on><update_rate>50</update_rate>
       <contact><collision>base_link_fixed_joint_lump__camera_link_collision</collision></contact>
       <topic>/vacuum_robot/contacts/camera</topic>
     </sensor>
   </gazebo>
   ```
   (Use the exact names found in step 1; if the camera mount has its own collision add a third sensor on `/vacuum_robot/contacts/camera_mount`.) A contact sensor holds one `<collision>`; do not list several.
3. Bridge (append to `vacuum_gazebo/config/gz_bridge.yaml`, one block per topic, direction `GZ_TO_ROS`):
   `ros_topic_name: "/vacuum_robot/contacts/chassis"`, `gz_topic_name` the same, `ros_type_name: "ros_gz_interfaces/msg/Contacts"`, `gz_type_name: "gz.msgs.Contacts"`; repeat for `camera` (and `camera_mount`).
4. Recorder subscribes to these topics (`ros_gz_interfaces/msg/Contacts`, QoS reliable depth 50) and writes **one row per contact** into `collisions_raw.csv`.

## 6.3 `collisions_raw.csv` schema

`t, t_rel, sensor, own_entity, other_entity, other_model, px, py, pz`
- `sensor` = `chassis|camera|camera_mount`.
- `Contacts.contacts[k].collision1.name` / `collision2.name` are full names such as `vacuum_robot::base_link::base_link_collision` and `wall_north::link::col`. `own_entity` = the one whose first `::` token is `vacuum_robot`; `other_entity` = the other; `other_model` = first `::` token of `other_entity`.
- `px,py,pz` = first entry of `positions[]` (world frame).
- Rows with `other_model == "ground_plane"` are **dropped by the recorder** (and counted in `events.csv: ground_contacts_dropped` once at stop).

## 6.4 Collision events (#3)

Offline, from `collisions_raw.csv` rows in the episode window:
1. Group rows by `other_model`.
2. Within a group sort by `t`; start a new **event** whenever the gap to the previous row exceeds `collision_gap_s = 0.5` (sim). Both sensors (`chassis`, `camera`) are merged in the same group.
3. Event record: `other_model, t_start, t_end (last row), n_rows`.

Keys: `n_collisions` (**#3, number of events**), `n_collision_obstacles` (distinct `other_model`), `collision_contact_time_s` (Σ `t_end − t_start`), `collision_first_t_ep`, `collision_source` = `"contact"`.

If `collisions_raw.csv` is absent or the contact topics never published (checked via `events.csv: contact_topic_alive` = 0), compute the **geometric fallback** instead and set `collision_source = "geometry"`:
- for each `trajectory.csv` row, robot rectangle `0.30 × 0.25` at the GT pose; contact iff any `occ` cell centre of the GT grid lies inside the rectangle, or the rectangle overlaps a dynamic obstacle rectangle (§6.7);
- events formed with the same 0.5 s gap rule;
- always also computed as a **cross-check** `n_collisions_geom`; if `|n_collisions − n_collisions_geom| > 2`, add note `"contact vs geometry disagree: contact=N geom=M"`.

## 6.5 Clearance (A5) — required additions to the GT grid (spec 03)

`gt_grid` additionally outputs `obs_id` (int16 array, shape like `occ`; −1 for free cells, otherwise the index into `obs_names`) and `obs_names` (list of model names, in SDF order). A cell covered by several obstacles gets the lowest index. Boundary cells `B` (spec 03) carry their `obs_id`. `worlds.yaml` lists `wall_models` (regex, default `^wall_|^ceiling$`).

Clearance of the robot body to obstacle `k` at a trajectory row: the distance from the robot rectangle (`0.30 × 0.25`, centred on the GT pose, oriented by GT yaw) to the nearest boundary-cell centre of obstacle `k`, minus half a cell (`res/2 = 0.025 m`), floored at 0:
`d = hypot(max(|px| − 0.150, 0), max(|py| − 0.125, 0)) − 0.025` where `(px, py)` is the cell centre in the robot frame. Use `scipy.spatial.cKDTree` on boundary-cell centres with radius query 1.2 m around the GT position to limit work.
Dynamic obstacles (from `dyn_obstacles.csv`, size from `worlds.yaml: dynamic_obstacles`) use the same formula against the obstacle's oriented rectangle (distance rectangle-to-rectangle approximated by the robot-rectangle-to-obstacle-centre distance minus the obstacle half-extent along the line; exact method: sample the obstacle perimeter at 0.02 m).

Per row `clearance = min_k d_k` (cap at 1.0 m when no obstacle within 1.0 m). Keys: `min_clearance_m`, `mean_clearance_m`, `clearance_p05_m`, `time_below_020m_s` (rows with clearance < 0.20 m × 0.1 s), `time_below_010m_s`.

## 6.6 Encounters and % obstacle avoidance (#4)

- For each obstacle `k` (static models in `obs_names` and dynamic models), compute `d_k(t)` per row.
- An **encounter** with `k` is a maximal set of consecutive rows with `d_k < d_enc = 0.50 m`; encounters of the same `k` separated by less than 2.0 s are merged; encounters shorter than 0.5 s are discarded.
- An encounter is **collision-free** iff no collision event with `other_model == k` has `[t_start, t_end]` intersecting `[encounter_start, encounter_end + 0.5 s]`.
- `avoidance_pct = 100 · collision-free encounters / all encounters`, **excluding walls** (obstacles whose name matches `wall_models`); `avoidance_pct_all` includes walls. Counts: `n_encounters`, `n_encounters_free`, `n_encounters_all`, `n_encounters_free_all`.
- If there are 0 encounters, `avoidance_pct = null` with note `"no encounters"` (never 100).

## 6.7 Obstacle-avoidance trials (#9)

A **trial** = one episode in a scenario world (spec 09 §9.5 names the scenarios `avoid_head_on`, `avoid_narrow_gap`, `avoid_u_trap`, `avoid_cluster`, `avoid_dead_end`, `avoid_dynamic_cross`, `avoid_dynamic_sudden`), method `scripted_goals`, goal list `scenario` (a single start→goal pair defined in `worlds.yaml`), one seed per trial. Per run keys:

| Key | Definition |
|---|---|
| `trial_goal_reached` | 1 iff `nav_success_gt_pct` for the single goal is 100 (GT within 0.30 m at `t_end`) |
| `trial_collisions` | `n_collisions` |
| `trial_success` | `1` iff `trial_goal_reached = 1` and `n_collisions = 0` and `end_reason = goals_done` |
| `trial_time_s` | episode duration |

`avoid_trial_success_pct` (**#9**) is computed by `aggregate.py` as `100 · Σ trial_success / n_trials` per (scenario, method), with Wilson 95 % CI; `n_trials` ≥ 10 (seeds 1–10). Seeds vary the spawn pose by uniform offsets `±0.10 m` in x,y and `±0.2 rad` yaw around the scenario's nominal start (from `worlds.yaml`, `scenario.start`), and for dynamic scenarios the obstacle start delay `U(0, 2) s` (using `rng = default_rng(seed + 3000)`).

Difference to #4: #4 is per obstacle encounter in any run; #9 is per designed trial with a known obstacle in the way.

## 6.8 Dynamic obstacle logging

For worlds with dynamic obstacles (spec 09 §9.6) the recorder is started with `extra_models:=[dyn names]` and writes `dyn_obstacles.csv` (`name, x, y, yaw`) at 10 Hz from `/ground_truth/model/<name>`.

## 6.9 Function contract

```
compute_safety_metrics(run: Run, gt: GtGrid, worlds_cfg: dict) -> dict
collision_events(rows, gap_s=0.5) -> list[Event]
clearance_series(traj, gt, dyn) -> ndarray[N]            # §6.5
encounters(traj, gt, dyn, d_enc=0.5, merge_s=2.0, min_s=0.5) -> dict[obstacle_name, list[(t0,t1)]]
```

## 6.10 Verification notes

| Check | Expected | Observed |
|---|---|---|
| Robot idle on the floor: contacts topic silent | 0 rows | |
| Drive into `wall_north` at 0.2 m/s | ≥ 1 event with `other_model = wall_north`, within 0.5 s of GT hitting the wall | |
| Robot rolls over the `rug` (2 cm) | no chassis contact (rug is below chassis) ; wheel contacts not recorded | |
| `ros_gz_bridge` supports `gz.msgs.Contacts` → `ros_gz_interfaces/msg/Contacts` | yes (else write a small gz-transport Python bridge or poll `gz topic -e`) | |
| Contact count vs geometric count on a scripted wall hit | within ±1 | |
| Collision names found by `gz sdf -p` | pasted here | |

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-10-20 | Contact sensors on chassis/camera only; ground contacts dropped | Wheels/caster always touch the floor |
| 2026-10-20 | Encounters are per obstacle, walls excluded from the headline | Otherwise a robot circling in a 6×5 m room has one permanent wall encounter |
| 2026-10-20 | 0.5 s event gap, 0.5 m encounter distance | User asked for no ambiguity; values live in `eval_defaults.yaml` and can be changed globally |

## Decision 2026-10-21
- Per-row dt from the `t` column (clipped to [0, 1.0] s) replaces the fixed 0.1 s in `time_below_*`.
- Geometry fallback counts any row with clearance <= 0 as a contact (previously could report 0 collisions with min_clearance <= 0). When contact-sensor events exist they remain the source of truth; `geometric_collisions` is reported as a cross-check.
- Self-contacts (`other_model == 'vacuum_robot'` or starting with the robot model name, meta `robot_model`) are dropped from collisions_raw.csv.

## Decision 2026-10-21 (exact geometry)
- New `metrics/geometry.py`: exact signed distance (SAT + vertex distance; negative = overlap) between the 0.30 x 0.25 m robot rectangle and SDF boxes (with yaw), cylinders/spheres (discs) and dynamic-obstacle rectangles, using gt_grid's SDF parser.
- `min_clearance_m`, encounters and `geometric_collisions` now use these exact distances (SDF found via worlds.yaml `sdf_file`; else grid fallback, `geometry_source` = 'grid'). Grid-based values kept as `min_clearance_grid_m`, `geometric_collisions_grid`, `n_encounters_grid`. `max_penetration_m` added. Contact sensors remain the primary collision source.
