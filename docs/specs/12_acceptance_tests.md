# 12 — Acceptance Tests

A spec is implemented only when its tests here pass and the "Observed" column is filled. Two kinds: **U** = pytest unit test with synthetic data (no simulator, runs in seconds, lives in `vacuum_eval/test/`), **R** = runtime test in the simulator (manual or harness-driven). Run unit tests with `cd ~/Swachh/Navigation/Simulation/vacuum_ws/src/vacuum_eval && python3 -m pytest test -q`.

Synthetic test data helpers live in `test/synth.py`: `make_run(...)` builds an in-memory `Run` (meta + arrays) so metric functions are tested without files; `make_world(boxes=[...])` writes a tiny SDF to a tmp dir.

---

## 12.1 Prerequisites (spec 01)

| ID | Kind | Procedure | Expected | Observed |
|---|---|---|---|---|
| T-010 | R | Launch apartment with spawn (1.5, −1.0, 0.7); `ros2 topic echo /ground_truth/odom --once` | `frame_id: world`, x=1.5, y=−1.0, yaw 0.7 | **PASS 2026-10-20** (x=1.500 y=−1.000 yaw=0.700) |
| T-011 | R | Repeat T-010 in `office` and `corridor` | same | |
| T-012 | R | Drive 1 m forward; compare `/ground_truth/odom` x with `/odom` x (clean mode, spawn at origin) | difference < 0.02 m | |
| T-013 | R | `odom_mode:=eval enable_noise:=false`: `/odom` equals `/diff_drive_controller/odom` within 1e-6; one TF publisher for `odom→base_footprint` | yes | |
| T-014 | R | `odom_mode:=eval enable_noise:=true seed:=1`, drive a square 4× | non-zero end error ≈ `sigma_lin`×path (order of magnitude); rerun same seed → same first 5 noise draws | |
| T-015 | R | Nav2 up, send a goal: `ros2 topic info /diff_drive_controller/cmd_vel_unstamped -v` | exactly one publisher (`velocity_smoother`) | |
| T-016 | R | Exploration 5 min apartment | goals not all cancelled at ~15 s; `goals_completed ≥ 3`; `/exploration/goal_events` has started/ended pairs | |
| T-017 | U | Oscillation logic with a recorded odom sequence: robot moving 0.3 m/s straight | never flagged; stationary for 16 s → flagged; rotating in place 16 s → not flagged | |
| T-018 | R | `slam.launch.py delete_db:=false` keeps existing DB | yes | |

## 12.2 Harness and recorder (spec 02)

| ID | Kind | Procedure | Expected | Observed |
|---|---|---|---|---|
| T-020 | R | Smoke episode: `run_episode.py --experiment smoke --world apartment --method frontier --seed 1 --timeout-sim-sec 180` | exit 0; files from spec 00 §0.6 exist; `trajectory.csv` ≈ 10·(episode+bringup) rows ±5 %; `maps/final_map.pgm` loads in `PIL`; `summary.json` has all always-present keys | |
| T-021 | U | `compute_metrics` on a synthetic run dir | `summary.json` written; module exception injected → `status: partial`, keys null, note present | |
| T-022 | R | Kill the Gazebo process mid-run | harness ends with `end_reason: crash`, no leftover processes (`pgrep -f "gz sim"` empty) | |
| T-023 | U | Episode start detection | motion at t=40 s → `episode_start_t = 40` ± 0.1; no motion → `no_motion` | |
| T-024 | U | Stuck rule | GT static for 180 s → `stuck`; GT spinning in place for 180 s (sum |wz|dt ≥ 2π) → `stuck`; GT moving 0.5 m in window → not stuck | |
| T-025 | R | Same seed twice → same spawn pose; different seeds → different (over 10 seeds ≥ 2 distinct candidates) | yes | |
| T-026 | R | `rtf.csv` average over a 3-min run | mean ≈ 1.0 (record), min recorded | |
| T-027 | U | `aggregate.py` on 3 synthetic summaries | mean/std/CI equal numpy reference; Wilson interval for 8/10 = [0.490, 0.943] ±0.002 | |

## 12.3 Ground-truth grid, coverage, completeness (spec 03, 10)

| ID | Kind | Procedure | Expected | Observed |
|---|---|---|---|---|
| T-030 | U | Synthetic SDF: 6×6 m interior, walls 0.2 thick, one 1×1 m box | `A_clean_m2 = 36 − 1 = 35.0` ± 1 cell perimeter error (≤ 0.4 m²) | |
| T-031 | U | Box with z range 0–0.02 (rug) | not in `occ` | |
| T-032 | U | Wall gap → `WorldNotSealed` | raised | |
| T-033 | U | Unsupported geometry (mesh) → `UnsupportedSdf` | raised | |
| T-034 | U | Map = exact GT (build an OccupancyGrid from GT) | `coverage_explored_pct = 100`, `map_completeness_pct ≥ 99` | |
| T-035 | R | `worlds.yaml` validation script | every `spawn_candidate`/`fixed` goal is in `a_reach`; start/goal of `avoid_*` reachable | |
| T-036 | U | Map shifted by 0.15 m | fixed completeness lower than aligned; aligned search recovers `map_align_dx_m ≈ ±0.15` | |
| T-037 | U | Half the map unknown | coverage ≈ 50 % | |
| T-100 | U | Straight GT path 4.0 m, W=0.25 | `swept_area_m2 = 1.0` ± 5 % | |
| T-101 | U | Same path twice | `overlap_ratio ≈ 2.0` on strip | |
| T-102 | U | Rotation in place 360° | swept ≈ 0.049 m² ± 10 % | |
| T-103 | U | Boustrophedon over `empty_room` synthetic poses | coverage ≈ 100 %, overlap ≈ 1.0 | |
| T-104 | U | Incremental curve equals from-scratch at 5 sample times | exact | |

## 12.4 Trajectory (spec 04)

| ID | Kind | Procedure | Expected | Observed |
|---|---|---|---|---|
| T-040 | U | est = gt | ATE=0, RPE=0 (≤1e-9) | |
| T-041 | U | est = gt + (0.5, 0) translation in `map`/`world` offset case (`t_world_map = (0,0,0)`) | `ate_fixed = 0.5`, `ate_aligned ≈ 0` | |
| T-042 | U | est yaw drift 1 °/m on a straight line | `rpe_rot_rmse_deg_1m ≈ 1.0` ± 3 % | |
| T-043 | U | `t_world_map = spawn` transform used (est in map frame near origin, spawn (2,1,90°)) | fixed ATE 0 when est = T_spawn⁻¹∘gt | |
| T-044 | U | < 2 m motion | keys null + note | |
| T-045 | U | optional: compare with `evo_ape tum --align` if `evo` installed | match 1e-3 m | |
| T-046 | R | 2-min drive with noise on: `ate_odom_fixed_rmse_m > 0`, `ate_improvement_pct` finite | yes | |

## 12.5 Navigation (spec 05)

| ID | Kind | Procedure | Expected | Observed |
|---|---|---|---|---|
| T-050 | U | Synthetic goal events (5 succeeded, 2 aborted, 1 timeout, 1 canceled, 1 unfinished) | `nav_success_pct = 5/8·100 = 62.5`, `nav_goals_canceled = 1` | |
| T-051 | U | Shortest path in empty 5 m corridor | Euclid ± 0.01 m | |
| T-052 | U | Goal behind wall segment | shortest > Euclid, ratio ≥ 0.97 for a perfect follower | |
| T-053 | U | Goal in obstacle → skipped, counted in `ratio_skipped` | yes | |
| T-054 | U | Energy proxy: constant vx=0.2 for 10 s | `Σ(vL²+vR²)dt = 2·0.04·10 = 0.8` | |
| T-055 | U | Curvature of circle radius 1 m (v=0.2, wz=0.2) | `smooth_curvature_rms_1pm = 1.0` | |
| T-056 | R | `scripted_goals` with `fixed` list in `empty_room` with GT map | `nav_success_pct = 100`, ratio in [1.0, 1.4] | |
| T-057 | R | `random20` generation determinism | same seed → identical `goals.yaml` | |

## 12.6 Safety (spec 06)

| ID | Kind | Procedure | Expected | Observed |
|---|---|---|---|---|
| T-060 | R | Idle 60 s | 0 contact rows | |
| T-061 | R | Drive into `wall_north` | ≥1 event, `other_model: wall_north`; `n_collisions_geom` within ±1 | |
| T-062 | U | Event grouping: rows at t=1.0,1.2,1.4 then 3.0 | 2 events | |
| T-063 | U | Clearance of robot rectangle 0.2 m from a wall | 0.2 ± 0.03 | |
| T-064 | U | Encounter logic: path passes 0.3 m from a box without contact | 1 encounter, collision-free → `avoidance_pct = 100` | |
| T-065 | U | Same with a contact row | `avoidance_pct = 0` | |
| T-066 | U | No obstacle within 0.5 m | `avoidance_pct = null` | |
| T-067 | R | `avoid_head_on` 10 seeds | `trial_success` recorded for each; aggregate computes rate + Wilson CI | |
| T-068 | R | Dynamic box collides with robot (forced) | contact event with `dyn_box_1` | |

## 12.7 Responsiveness (spec 07)

| ID | Kind | Procedure | Expected | Observed |
|---|---|---|---|---|
| T-070 | U | Synthetic GT: onset 0.3 s after command | latency 0.3 → met | |
| T-071 | U | Missing response → `L=null`, counted missed | yes | |
| T-072 | U | Obstacle `t_a` rule on synthetic geometry (obstacle in FOV at 1.4 m vs behind robot) | only in-FOV qualifies | |
| T-073 | R | `bare` run 10+10 trials | ≥ 18 of 20 events have latency values; stats printed | |
| T-074 | R | `loaded` run | latencies ≥ `bare` median (record) | |
| T-075 | U | `rates.csv` floor logic with a gap of 3 s without `/odom` | 3 windows flagged | |

## 12.8 Loop closure (spec 08)

| ID | Kind | Procedure | Expected | Observed |
|---|---|---|---|---|
| T-080 | U | Nodes on a circle, closure between node 1 and node 10 which are 0.2 m apart in GT | precision 100 %, recall 100 % (one revisit episode) | |
| T-081 | U | Closure between two nodes 3 m apart | false closure, precision 0 % | |
| T-082 | U | Revisit with no closure | recall 0 % | |
| T-083 | R | `multi_room_loop` loop tour with noise | ≥ 1 accepted closure; counts printed | |

## 12.9 Worlds (spec 09)

| ID | Kind | Procedure | Expected | Observed |
|---|---|---|---|---|
| T-090 | R | Load each world headless 10 s | no errors in log; pose/info topic present | |
| T-091 | U | Rasterise each world | sealed, areas pasted | |
| T-092 | R | Dynamic mover timeline | box starts at `start_delay_s`, follows waypoints, stops at end | |

## 12.10 End-to-end acceptance (done = all green)

1. `run_episode.py` apartment/frontier/seed 1, 10 min timeout, noise 0 → `summary.json` with non-null: `coverage_explored_pct, coverage_cleaned_pct, map_completeness_pct, nav_success_pct, path_length_ratio_mean, ate_fixed_rmse_m, n_collisions, avoidance_pct (or null with note), cleaning_efficiency, rtf_mean`.
2. Same with `--odom-noise 1`: `ate_odom_fixed_rmse_m` larger than in (1).
3. A 3-seed batch → `aggregate.csv` has mean/std/CI for every key.
4. Two reruns of `compute_metrics` on the same run dir → byte-identical `summary.json`.
5. `docs/METRICS_TO_BE_MEASURED.md` statuses updated to reflect what is now `Exists`.
