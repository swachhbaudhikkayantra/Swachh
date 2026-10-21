# 08 — Loop Closure Success Rate (#11)

Depends on: 00, 01 (§1.3 noise path, otherwise loop closures are meaningless: perfect odometry never needs them), 02 (`loop_events.csv`, `trajectory.csv`), 09 (a world with real revisits and a symmetric world for false positives).
Module: `vacuum_eval/metrics/loop_closure.py`. Recorder part: subscription to `/rtabmap/info`.

---

## 8.1 What RTAB-Map publishes (verified 2026-10-20 by `ros2 interface show rtabmap_msgs/msg/Info`)

`rtabmap_msgs/msg/Info` has `int32 ref_id` (id of the node just added/processed), `int32 loop_closure_id` (id of the node it closed a loop with; 0 if none), `int32 proximity_detection_id` (node id for a proximity link; 0 if none), `string[] stats_keys` / `float32[] stats_values` (generic statistics). It has **no** loop-count field. The existing `benchmark_slam.py` stored `loop_closure_id` as a count — a bug; do not reuse it.
Topic `/rtabmap/info`, published by the `rtabmap` node once per processed map update (detection rate: `Rtabmap/DetectionRate` in `vacuum_slam/config/rtabmap.yaml`, currently 1 Hz). **Verify at runtime** that it publishes (`ros2 topic hz --use-sim-time /rtabmap/info`); if `publish_stats` or a similar parameter is required, set it in `slam.launch.py` and log the change.

## 8.2 Raw file `loop_events.csv`

One row per `/rtabmap/info` message: `t, t_rel, ref_id, loop_closure_id, proximity_detection_id, gt_x, gt_y, gt_yaw, est_x, est_y, est_yaw`.
- `gt_*`: latest `/ground_truth/odom` pose in `world`, sampled when the message arrives (must be ≤ 0.2 s old else empty).
- `est_*`: the robot pose in `map` from TF `map→base_footprint` at arrival (empty on failure) — informational.
RTAB-Map also adds nodes at its own rate; `ref_id` identifies each one. A node's GT pose is the `gt_*` of the **first row** where that `ref_id` appears (`node_gt[ref_id]`).

## 8.3 Definitions

Constants (`eval_defaults.yaml`): `lc_pos_tol_m = 1.0`, `lc_yaw_tol_deg = 60`, `lc_min_time_gap_s = 30`.

- **Accepted closure:** a row with `loop_closure_id > 0`. It links node `a = ref_id` to node `b = loop_closure_id`. Closures with `proximity_detection_id > 0` and `loop_closure_id = 0` are *proximity links* (odometry-adjacent), counted separately as `n_proximity_links`, never as loop closures.
- **True closure** (correct): both `node_gt[a]` and `node_gt[b]` exist and `hypot(Δx, Δy) ≤ 1.0 m` **and** `|wrap(Δyaw)| ≤ 60°`.
- **False closure:** accepted but not true.
- **Revisit** (ground-truth event): a maximal set of consecutive nodes (ordered by first appearance) whose GT pose is within the tolerances of some earlier node's GT pose that appeared at least 30 s earlier. Compute: for each node `n` (in order), `revisit(n)` = exists node `m` with `t_first[m] ≤ t_first[n] − 30 s` and pose within tolerance. Consecutive nodes with `revisit = true` form one **revisit episode**; episodes separated by ≥ 1 node with `revisit = false` are distinct. Only nodes with `t_first ≥ episode_start_t` and `≤ episode_end_t` are considered.
- A revisit episode is **detected** if at least one **true closure** has its `ref_id` in the episode's node set.

## 8.4 Keys

| Key | Definition |
|---|---|
| `lc_n_info_msgs` | number of rows in the window |
| `lc_n_nodes` | distinct `ref_id` in the window |
| `lc_n_accepted` | number of accepted closures (rows with `loop_closure_id > 0`; a repeated identical `(a,b)` pair counts once) |
| `lc_n_true`, `lc_n_false` | as defined |
| `lc_n_revisits` | number of revisit episodes |
| `lc_n_revisits_detected` | episodes detected |
| `lc_precision_pct` | `100 · lc_n_true / lc_n_accepted` (null if no accepted closures; never 100 by default) |
| `lc_recall_pct` | `100 · lc_n_revisits_detected / lc_n_revisits` (null if no revisits) |
| `lc_f1_pct` | harmonic mean of the two (null if either null) |
| `n_proximity_links` | count |
| `lc_per_100m` | `100 · lc_n_accepted / distance_gt_m` |

**#11 "loop closure success rate"** is reported as the pair `lc_precision_pct` and `lc_recall_pct`; the single headline number used in summary tables is `lc_recall_pct` ("of the places the robot came back to, how many were recognised") with precision always shown beside it. If the user prefers one number, use `lc_f1_pct`.

## 8.5 Experimental conditions

- Compare `--odom-noise 1` (loop closures matter) with `0`. With perfect odometry few or no closures are expected; this is not an error.
- Worlds: `multi_room_loop` (spec 09 §9.4, designed with loops and revisits) for recall; `symmetric_hall` for precision (false positives).
- The exploration trajectory rarely revisits places deliberately. For a controlled test use `scripted_goals` with the goal list `loop_tour` from `worlds.yaml` (drives a closed tour twice, returning to the start pose within 0.3 m) so that revisit episodes are guaranteed.

## 8.6 Function contract

```
compute_loop_closure_metrics(run: Run) -> dict
node_poses(rows) -> dict[ref_id, (t_first, gt_x, gt_y, gt_yaw)]
revisit_episodes(nodes, pos_tol, yaw_tol, min_gap_s) -> list[set[ref_id]]
```

## 8.7 Verification notes

| Check | Expected | Observed |
|---|---|---|
| Info topic name and rate | `/rtabmap/info`, ≈1 Hz sim | |
| Drive a loop twice in `multi_room_loop` with noise: `lc_n_accepted ≥ 1` | yes | |
| Same drive with clean odometry | few/no closures; keys valid | |
| Synthetic unit test: nodes 1..10 on a circle, closures given | exact precision/recall | |

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-10-20 | Ground-truth poses at node creation decide correctness | RTAB-Map's own post-hoc optimised poses are what is being evaluated |
| 2026-10-20 | Headline = recall, precision always reported | User's wording "success rate"; precision exposes false positives that corrupt maps |

| 2026-10-21 | Truth tolerances tightened to 0.30 m / 30 deg (was 1.0 m / 60 deg) | Loose values make precision ~100% by construction in a 6x5 m flat; old tolerances still reported as `lc_n_true_loose`, `lc_n_false_loose`, `lc_precision_loose_pct` |

| 2026-10-21 | Correctness redefined: accepted closure is TRUE if RTAB-Map's `loop_closure_transform` (recorded as `lc_tx, lc_ty, lc_tyaw`, appended to `loop_events.csv`) matches the GT relative SE(2) transform inv(P_ref)*P_loop within `lc_reg_trans_tol_m` = 0.10 m and `lc_reg_rot_tol_deg` = 5 deg | A correct visual closure can link views ~1 m apart; what matters is registration accuracy. Convention: RTAB-Map Link ref->loop, pose_loop = pose_ref * T (ref = current node, loop = matched older node); not verified against live data. Old runs without the columns fall back to position tolerance (note emitted). Position results kept as `lc_precision_samepose_pct` (0.30 m/30 deg) and `lc_precision_loose_pct` (1.0 m/60 deg). Recall: revisits stay position-based (GT within 1.0 m/60 deg of a node >= `lc_min_time_gap_s` older), i.e. places where a closure was possible, independent of registration accuracy |
