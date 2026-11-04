# Swachh Boudhik Yantra: User Manual

This manual takes you from a fresh clone to every part of the project: the Gazebo simulation, mapping, navigation, the evaluation harness, the paper tables and figures, the object-detection suite and the hardware HMI.

Conventions:
- `<repo>` is your clone, for example `~/Swachh`. All commands below assume `~/Swachh`; change it if you cloned elsewhere.
- A command marked **(unverified)** was read from a script or docstring but not run while writing this manual.
- Anything marked **KNOWN ISSUE** is a path or assumption in the repo that you may have to adjust.

Repo layout (top level):

| Folder | Content |
|---|---|
| `Navigation/` | Launch scripts (`start.sh`, `stop.sh`, `save_map.sh`, `view_map.sh`, `steer_gui.sh`, `run_mapping.sh`), the ROS 2 workspace `Simulation/vacuum_ws`, the pytest suite `tests/` |
| `Navigation/Simulation/vacuum_ws/src/` | ROS 2 packages: `vacuum_bringup`, `vacuum_controller`, `vacuum_description`, `vacuum_eval`, `vacuum_exploration`, `vacuum_gazebo`, `vacuum_interfaces`, `vacuum_localization`, `vacuum_nav2`, `vacuum_slam`, `vacuum_utils` |
| `Navigation/Manual mode/` | Arduino firmware and the GTK4 HMI (real hardware) |
| `Object Detection/` | YOLO / RF-DETR detection and benchmark suite |
| `docs/` | Plans, findings, failure modes, paper material (`docs/paper_out/`) |
| `results/` | Archived run folders and tables from the 2026-10-25 evaluation |

---

## 1. Prerequisites

### 1.1 Simulation and evaluation

| Item | Version / requirement | Source |
|---|---|---|
| OS | Ubuntu 24.04 (the evaluation machine runs 24.04.4 LTS). ROS 2 Jazzy needs 24.04; on other releases the apt packages may not exist | `docs/REMOTE_MACHINE.md`, `Navigation/Simulation/scripts/README.md` |
| ROS 2 | Jazzy (`/opt/ros/jazzy`), install `ros-jazzy-desktop` and `ros-dev-tools` | `setup_machine.sh`, `docs/REMOTE_MACHINE.md` |
| Gazebo | Harmonic (gz-sim 8.x; the project was tested with 8.15) | `docs/REQUIREMENTS.md` |
| SLAM | RTAB-Map (`rtabmap_ros` for Jazzy) | `docs/user_guide.md` |
| Navigation | Nav2 with `SmacPlannerHybrid` (DUBIN), `nav2_map_server` | `docs/REQUIREMENTS.md` |
| Extra apt package | `ros-jazzy-spatio-temporal-voxel-layer` | `docs/REQUIREMENTS.md` |
| Middleware | CycloneDDS (`rmw_cyclonedds_cpp`) with the repo file `Navigation/cyclone_dds.xml` | `start.sh` |
| Python | Python 3.12 (Ubuntu 24.04 default) with numpy, scipy, matplotlib, PIL, yaml, pytest, cv2. `pandas`, `evo`, `skimage`, `shapely` are NOT used; do not install them as dependencies | `docs/REQUIREMENTS.md` |
| Desktop terminal | `ptyxis` is used by `start.sh` to open windows (default terminal on newer Ubuntu/GNOME). **(unverified on a machine without it)** | `start.sh` |
| Steering GUI | Tkinter (`python3-tk`) **(unverified; the GUI file is a Tkinter program)** | `steer_gui.sh` |
| Image viewer | `xdg-open` (used by `view_map.sh`) | `view_map.sh` |
| GPU | Optional. An NVIDIA GPU with driver 570 or newer is recommended. The evaluation machine had an RTX 5050 laptop GPU (8 GB, driver 595.91). Without a GPU Gazebo falls back to software rendering (llvmpipe), which is slow but works | `docs/REMOTE_MACHINE.md`, `setup_machine.sh` |
| RAM / CPU | 22 GB RAM and 16 threads were used with `--parallel 2`. CPU, not GPU, is the limit; three parallel SLAM simulations ran at RTF 0.74 | `docs/REMOTE_MACHINE.md` |

Recommended way to install everything: the idempotent installer.

1. Review what it will do:
   ```bash
   cd ~/Swachh/Navigation/Simulation/scripts
   ./setup_machine.sh --dry-run
   ```
2. Run it (uses sudo and prompts; installs apt packages, DDS sysctl buffers, `~/.bashrc` exports, rosdep, builds the workspace and runs the `vacuum_eval` tests):
   ```bash
   ./setup_machine.sh
   ```
   It aborts if `/opt/ros/jazzy` is missing, so install ROS 2 Jazzy first (`ros-jazzy-desktop ros-dev-tools`).
3. Reload the shell and run the read-only preflight (exit 1 on any FAIL, never kills anything):
   ```bash
   source ~/.bashrc
   ./preflight.sh
   ```
   Run `preflight.sh` before every batch. It also prints a suggested `--parallel` value.

### 1.2 DDS buffers (important)

If SLAM silently receives no images, the cause is almost always too-small socket buffers.

```bash
cat /proc/sys/net/core/rmem_max
```
The value must be `33554432` (32 MB). `setup_machine.sh` writes `/etc/sysctl.d/90-ros2-dds.conf` to set this. To reapply without rebooting:
```bash
sudo sysctl -p /etc/sysctl.d/90-ros2-dds.conf
```
(WSL only: run `wsl --shutdown` from Windows once after setup so the boot hook applies.)

### 1.3 Environment for every new terminal

```bash
source /opt/ros/jazzy/setup.bash
source ~/Swachh/Navigation/Simulation/vacuum_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp CYCLONEDDS_URI=file://$HOME/Swachh/Navigation/cyclone_dds.xml ROS_DOMAIN_ID=0
```
`setup_machine.sh` adds equivalent lines to `~/.bashrc`.

### 1.4 Object detection and hardware (separate prerequisites)

See sections 9 and 10.

---

## 2. Build the workspace

1. Go to the workspace and source ROS:
   ```bash
   cd ~/Swachh/Navigation/Simulation/vacuum_ws
   source /opt/ros/jazzy/setup.bash
   ```
2. Install missing ROS dependencies (needs sudo; also done by `setup_machine.sh`):
   ```bash
   rosdep install --from-paths src --ignore-src -r -y
   ```
   If `rosdep` has never been used on this machine, run `sudo rosdep init` and `rosdep update` first.
3. Build:
   ```bash
   colcon build --symlink-install
   ```
4. Source the result:
   ```bash
   source install/setup.bash
   ```

Notes:
- `vacuum_eval`, config and launch files are symlinked, so edits take effect immediately.
- **`vacuum_exploration` installs copies**, so rebuild after editing it: `colcon build --symlink-install --packages-select vacuum_exploration`.
- Do not run `colcon build` while a simulation is running.

---

## 3. Run the simulation

Two ways: the `Navigation/start.sh` wrapper (opens separate terminal windows with `ptyxis`) or direct `ros2 launch` commands (works over SSH or without `ptyxis`).

### 3.1 `start.sh` modes

All run from `~/Swachh/Navigation`:
```bash
cd ~/Swachh/Navigation
```

| Command | What it does |
|---|---|
| `./start.sh` | Default `manual` mode. Opens one window running `run_mapping.sh` (Gazebo apartment world, RTAB-Map, RViz, rtabmap_viz, arrow-key teleop), waits 12 s, then opens the Tkinter steering GUI window |
| `./start.sh explore [env]` | Autonomous frontier exploration (Stage 4B). Stops previous instances, deletes `~/.ros/rtabmap.db*`, then launches `vacuum_exploration exploration.launch.py environment:=<env>`. Default `env` is `apartment` |
| `./start.sh navigate [env]` | AMCL localisation plus goal navigation (Stage 5). Needs a saved map at `~/maps/stage5/<env>.yaml`. Launches `vacuum_bringup sim.launch.py use_sim_time:=true`, waits 14 s, then `vacuum_nav2 nav2_localization.launch.py map_path:=... environment:=<env>` |
| `./start.sh steer` | Steering GUI only (attach to an already running session) |
| `./start.sh stop` | Same as `./stop.sh` (see section 12) |

Environment names listed in `start.sh`: `apartment office room corridor warehouse`. Only some of these have a matching `.sdf` in `vacuum_gazebo/worlds` (the shipped worlds are listed in section 3.3), so check the name exists before using it. **(unverified)**

**Explore, step by step**
1. `cd ~/Swachh/Navigation && ./start.sh explore apartment`
2. A new window opens and the robot drives itself. Do not use the keyboard.
3. Watch coverage from any sourced terminal: `ros2 topic echo /exploration/status`
4. Save the map while the simulation is still running (section 4).

**Navigate, step by step**
1. Make sure a map exists: `ls ~/maps/stage5/apartment.yaml` (create it by exploring and saving, section 4).
2. `./start.sh navigate apartment`
3. Wait about 30 s for RViz.
4. In RViz click **2D Pose Estimate** and place the arrow at the robot spawn pose.
5. Watch the green particle cloud converge.
6. Click **Nav2 Goal** and click a point on the map.
7. Monitor localisation: `ros2 topic echo /localization/status`

**KNOWN ISSUE (hard-coded paths).** `start.sh` sources `/home/bmscecse/ros2_ws/install/setup.bash` only if that file exists (harmless elsewhere). However `run_mapping.sh` (used by the default manual mode) and `save_map.sh` contain hard-coded paths `/home/bmscecse/Swachh_Boudhik_Yantra/...` or `$HOME/Swachh_Boudhik_Yantra/...`. On a clone at `~/Swachh` these do not exist. Either create a symlink so the old path resolves, or use the direct commands in 3.2 and 4.2:
```bash
ln -s ~/Swachh/Navigation ~/Swachh_Boudhik_Yantra
```
This also needs `Simulation/vacuum_ws` under it, which the symlink provides. `run_mapping.sh` additionally hard-codes `/home/bmscecse/...` (not `$HOME`), so for that script use the direct commands instead. **(unverified)**

### 3.2 Direct launch commands (no `ptyxis`)

Source the environment (section 1.3) first, then:

1. Simulation only (Gazebo + robot + controllers):
   ```bash
   ros2 launch vacuum_bringup sim.launch.py world:=apartment
   ```
   Useful documented arguments (from the `sim.launch.py` docstring): `use_rviz:=false`, `world_file:=/abs/path/custom.sdf`, `use_sim_time:=true`. Other declared arguments include `headless`, `spawn_x`, `spawn_y`, `spawn_yaw`, `odom_noise`, `render_gpu`; read the top of `Navigation/Simulation/vacuum_ws/src/vacuum_bringup/launch/sim.launch.py` for their meaning and defaults.
2. SLAM on top of a running simulation (second terminal):
   ```bash
   ros2 launch vacuum_slam slam.launch.py environment:=apartment use_rviz:=false
   ```
3. RViz alone (to watch a headless run):
   ```bash
   ros2 launch vacuum_bringup rviz.launch.py
   ```
4. Full autonomous exploration stack:
   ```bash
   ros2 launch vacuum_exploration exploration.launch.py environment:=apartment
   ```
5. Navigation on a saved map:
   ```bash
   ros2 launch vacuum_nav2 nav2_localization.launch.py map_path:=$HOME/maps/stage5/apartment.yaml environment:=apartment
   ```
   (Run `sim.launch.py use_sim_time:=true` first, as `start.sh navigate` does.)

`start.sh` runs these through `python3.12 /opt/ros/jazzy/bin/ros2 launch ...`; on Ubuntu 24.04 plain `ros2 launch` uses the same interpreter.

### 3.3 Worlds shipped in `vacuum_gazebo/worlds`

`apartment, cluttered_room, corridor, empty_room, empty_world, maze_dead_ends, multi_room_loop, office, symmetric_hall, two_rooms_door`, plus avoidance scenarios `avoid_cluster, avoid_dead_end, avoid_dynamic_cross, avoid_dynamic_sudden, avoid_head_on, avoid_narrow_gap, avoid_narrow_gap_wide, avoid_u_trap`.

### 3.4 Over SSH (no display)

There is no `DISPLAY`, so set headless rendering before launching:
```bash
export VACUUM_GZ_HEADLESS_RENDERING=1
```
View the run remotely by opening RViz on the machine's desktop (3.2 item 3), or inspect `diagnose.png` saved by the evaluation harness.

---

## 4. Save and view maps

### 4.1 With the scripts

RTAB-Map must still be running when you save. Stopping it first gives an empty or missing map.

| Command (from `~/Swachh/Navigation`) | Output |
|---|---|
| `./save_map.sh` | `~/maps/stage4/map.pgm` and `map.yaml` (Stage 4A default) |
| `./save_map.sh apartment` | `~/maps/stage5/apartment.pgm` and `.yaml` (the file `./start.sh navigate apartment` expects) |
| `./view_map.sh` | Opens `~/maps/stage4/map.pgm` with `xdg-open` |

`view_map.sh` only opens the stage-4 map. To view a stage-5 map: `xdg-open ~/maps/stage5/apartment.pgm`.

### 4.2 Without the script (works with any clone path)

Source the environment (1.3), then:
```bash
mkdir -p ~/maps/stage5
ros2 run nav2_map_server map_saver_cli -f ~/maps/stage5/apartment --ros-args -p use_sim_time:=true
```
This is exactly what `save_map.sh` runs, minus the hard-coded workspace paths.

### 4.3 Notes
- RTAB-Map keeps its database at `~/.ros/rtabmap.db`. `start.sh explore` and `stop.sh` delete it so every run starts from a blank map. Copy it elsewhere first if you want to keep it.
- Obstacles further than about 4 m from the depth camera may be missed; drive closer. Smooth, steady driving helps loop closures (`docs/user_guide.md`).

---

## 5. Manual steering

1. Start the stack in manual mode: `cd ~/Swachh/Navigation && ./start.sh`. A second window with the steering GUI opens after 12 s.
2. Drive with the GUI buttons. It does not need terminal focus.
3. To open only the GUI against an already running session: `./start.sh steer` (or `bash steer_gui.sh`). It uses `ROS_DOMAIN_ID=0` and `rmw_cyclonedds_cpp`.
4. Keyboard teleop: `run_mapping.sh` ends by running `teleop_arrows.py` in its terminal; click that terminal to focus it. The older teleop key map in `docs/user_guide.md` is: `U/I/O` forward-left/forward/forward-right, `J/K/L` rotate left/stop/rotate right, `M/,/.` reverse-left/reverse/reverse-right. Which key map your build uses depends on the teleop script. **(unverified)**
5. `cmd_vel_relay.py` timestamps the commands so the controllers accept them.
6. Do not use the keyboard during `explore`; the robot drives itself.

---

## 6. Run the evaluation harness

Package: `Navigation/Simulation/vacuum_ws/src/vacuum_eval`. Spec of what each metric means: `docs/specs/13_preregistration.md`, `docs/EVALUATION_FINDINGS_2026-10-25.md`.

### 6.1 Preparation

1. Environment (1.3) sourced.
2. Over SSH add: `export VACUUM_GZ_HEADLESS_RENDERING=1`.
3. Run from the package folder so `python3 -m vacuum_eval.<module>` resolves (it is also importable once the workspace is sourced):
   ```bash
   cd ~/Swachh/Navigation/Simulation/vacuum_ws/src/vacuum_eval
   bash ~/Swachh/Navigation/Simulation/scripts/preflight.sh
   ```
   Every line should say PASS. Only one simulation can run on a small machine at a time.
4. Commands that take longer than 2 minutes should run inside `tmux`: `tmux new -s eval`.

### 6.2 Single episode

```bash
python3 -m vacuum_eval.run_episode --experiment myrun --world office --method frontier --seed 1 --odom-noise 0 --headless 1 --timeout-sim-sec 600
```

All flags (from `--help`):

| Flag | Meaning |
|---|---|
| `--experiment NAME` (required) | Output folder name under the runs root |
| `--world W` (required) | A world from `config/worlds.yaml` / section 3.3 |
| `--method {frontier,scripted_goals,responsiveness}` | Exploration, scripted navigation goals, or responsiveness test |
| `--stack {bare,loaded}` | For the responsiveness method |
| `--nav-map {gt,slam}` | Map used by scripted navigation |
| `--localization {auto,slam,amcl,gt}` | Localisation source for `scripted_goals` (`auto` = slam for `--nav-map slam`, amcl for `gt`) |
| `--goal-list {fixed,random20,near_wall,long_range,scenario,loop_tour}` | Goals for `scripted_goals` (default `scenario` for `avoid_*` worlds, else `fixed`) |
| `--seed N` (required) | Random seed |
| `--odom-noise {0,1}` | Add odometry noise |
| `--headless {0,1}` | No GUI |
| `--timeout-sim-sec N` | Simulated-time cap (default from `worlds.yaml` or 1200) |
| `--runs-root DIR` | Output root (default `~/eval_runs`) |
| `--force` | Re-run even if the episode exists |
| `--slot N` | Parallel slot: `ROS_DOMAIN_ID=10+N` (0 for slot 0), `GZ_PARTITION=vacuum_slotN` |
| `--lean {0,1}` | 1 = disable optional nodes and trim the bag (batch passes 1) |
| `--gpu {0,1}` | 1 = `render_gpu:=true`; never pool with `--gpu 0` results |

Other examples taken from `docs/RUNBOOK.md`:
```bash
# scripted navigation with ground-truth map and AMCL
python3 -m vacuum_eval.run_episode --experiment r3nav --world apartment --method scripted_goals --goal-list random20 --nav-map gt --localization amcl --seed 1 --odom-noise 0 --headless 1
# responsiveness
python3 -m vacuum_eval.run_episode --experiment r4resp --world apartment --method responsiveness --stack bare --seed 1 --headless 1
# avoidance scenario
python3 -m vacuum_eval.run_episode --experiment r5avoid --world avoid_head_on --method scripted_goals --goal-list scenario --nav-map gt --seed 1 --headless 1
```

Output folder: `~/eval_runs/<experiment>/<world>/<method[_goal-list]>/seed_NNN/` (for example `~/eval_runs/r1confirm/apartment/frontier/seed_002`). The final line printed by the harness is the run folder.

After an episode, compute metrics and make a diagnostic picture:
```bash
RUN=~/eval_runs/myrun/office/frontier/seed_001
python3 -m vacuum_eval.compute_metrics $RUN
python3 -m vacuum_eval.diagnose $RUN --png $RUN/diagnose.png
```
(`compute_metrics` also accepts `--only <modules>` and `--gt-dir DIR`.)

### 6.3 Campaign (many episodes)

A campaign is a YAML matrix in `vacuum_eval/config/campaigns/`. Shipped files: `dev_tuning`, `quick_exploration`, `quick_navigation`, `quick_navigation_extra`, `quick_avoidance`, `quick_responsiveness`, and `final_exploration`, `final_navigation`, `final_avoidance`, `final_responsiveness`. A matrix names `experiment`, `split`, `worlds`, `methods`, `seeds`, `timeout_sim_sec`, `headless`, `lean`, `gpu`.

1. Dry run (prints the plan; with `--prebuild-gt` it builds all ground-truth grids and exits):
   ```bash
   python3 -m vacuum_eval.run_batch --matrix config/campaigns/quick_navigation.yaml --prebuild-gt --dry-run
   ```
2. Run (test split needs the confirmation flag):
   ```bash
   python3 -m vacuum_eval.run_batch --matrix config/campaigns/quick_navigation.yaml --split test --confirm-test-split --parallel 2 --lean 1
   ```
   Flags: `--force`, `--dry-run`, `--parallel K`, `--stagger-sec N`, `--lean {0,1}`, `--gpu {0,1}`, `--prebuild-gt`, `--split {dev,test}`, `--confirm-test-split`.
3. Interruptions are safe: finished episodes are skipped; run the same command to resume.
4. Use `--parallel 2` on a 16-thread machine; 3 slots lowered the real-time factor. Run `preflight.sh` for a suggestion.

Rules from the project (`CLAUDE.md`, `docs/specs/13_preregistration.md`): the test split is frozen; do not tune after a test campaign starts; report every episode.

### 6.4 Validity

An episode gets `status: invalid` (and is excluded from statistics, but listed and counted) if any of these hold:
- image drop above 10 % (`max_img_drop_pct`),
- an RTAB-Map update gap above 5 s (`max_rtabmap_gap_s`),
- RTAB-Map updates below 0.5 of the expected rate (`min_rtabmap_update_frac`).

Invalid episodes caused by infrastructure faults may be re-run once with the same seed; report both attempts. Statuses `ok` and `partial` count as valid (same rule as `aggregate`). Health flags (`health_<metric>`) never exclude an episode.

### 6.5 Where outputs go and how to read `summary.json`

Per-episode folder contents include `summary.json`, `summary.csv`, `trajectory.csv`, `coverage_curve.csv`, `collisions_raw.csv`, `goal_events.csv`, `loop_events.csv`, `plans.csv`, `rates.csv`, `resources.csv`, `rtf.csv`, `run_meta.yaml`, `maps/`, `missed_explored.png`, and `diagnose.png` (after step 6.2). The archived 2026-10-25 runs are under `~/Swachh/results/runs/`.

Read `summary.json` in this order:
1. **Validity:** `status`, `episode_valid`, `invalid_reasons`, `end_reason`, `img_drop_pct`, `rtabmap_max_gap_s`, `rtf_true_mean` (true real-time factor; Gazebo's own RTF display is misleading).
2. **Headline metrics:**

   | Metric | Key |
   |---|---|
   | Coverage | `coverage_explored_pct`, `coverage_cleaned_pct` (secondary) |
   | Steps | `n_goals`, `n_cmd_ticks`, `n_recoveries` |
   | Collisions | `n_collisions`, `collision_source` |
   | Obstacle avoidance | `avoidance_pct` |
   | Responsiveness | `responsiveness_pct`, `lat_cmd_motion_ms_mean`, `lat_stop_ms_mean` |
   | ATE / RPE | `ate_fixed_rmse_m`, `rpe_trans_rmse_m_1m` |
   | Map completeness | `map_completeness_pct` |
   | Avoidance trial | `trial_success` |
   | Navigation success | `nav_success_gt_pct` (and `nav_success_gt_strict_pct`) |
   | Loop closure | `lc_precision_pct`, `lc_recall_pct`, `lc_f1_pct` |
   | Path length ratio | `path_length_ratio_mean` |
   | Cleaning efficiency (secondary) | `cleaning_efficiency` |
3. **Health:** for each metric, `health_<metric>` is one of `OK`, `LOW_N`, `UNMEASURABLE`, `SUSPECT`, `BAD`, `NA`, with `health_<metric>_reasons`. Precedence: UNMEASURABLE > SUSPECT > LOW_N > BAD > OK. Also check `odom_corrupted_by_contact` (1 means a contact corrupted odometry; ATE is then inflated, use `ate_fixed_rmse_m_pre_corrupt` as a secondary).
4. Interpretation of each metric and known biases: `docs/EVALUATION_FINDINGS_2026-10-25.md`. Method comparison (metric 13) is on hold and not implemented.

### 6.6 Aggregate, report, sample size

Aggregate per-experiment statistics (cluster-bootstrap CIs, episode is the unit):
```bash
python3 -m vacuum_eval.aggregate --root ~/eval_runs/quick_navigation --out ~/eval_runs/quick_navigation/aggregate.csv
```
Other flags: `--paired-by`, `--seed` (default 12345), `--boot-B`.

Build the report (`results.md`, `figures/`, `metrics_status_update.md`):
```bash
python3 -m vacuum_eval.make_report --root ~/eval_runs/quick_navigation --out ~/eval_runs/quick_navigation/report
```
`--root` can be repeated for several campaigns.

Plan a sample size (no simulation needed):
```bash
python3 -m vacuum_eval.plan_sample_size --from-root ~/eval_runs/r1confirm --metric ate_fixed_rmse_m --metric-kind continuous --target-halfwidth 0.05
```

Check loop-closure direction on finished runs:
```bash
python3 -m vacuum_eval.check_lc_direction ~/eval_runs/r1confirm/apartment/frontier/seed_00*
```

---

## 7. Generate the paper tables and figures

Both read finished episode folders. No simulator is needed.

### 7.1 Tables

`paper_tables.py` computes every number in the paper's sections 7.3 and 7.4 from raw `summary.json` files (nothing typed by hand), cross-checks against `aggregate.csv`, and writes `paper_values.json` and `paper_tables.md`.

```bash
cd ~/Swachh/Navigation/Simulation/vacuum_ws/src/vacuum_eval
PYTHONPATH=$PWD python3 -m vacuum_eval.paper_tables --root ~/eval_runs_victus --out ~/Swachh/docs/paper_out
```
- `--root` must be a folder that holds the `quick_*` campaign folders (`quick_exploration_noise`, `quick_navigation`, `quick_avoidance`, `quick_responsiveness`) and `_gt/`. The archived copy of those runs inside this repo is `~/Swachh/results/runs/`, but it may lack `_gt/`; if the command reports missing `_gt`, copy the folder from the evaluation machine. **(unverified)**
- Optional: `--template T.md --filled F.md` fills `{{path|fmt}}` tokens in a text template from the computed values.
- Outputs in `docs/paper_out/`: `paper_values.json`, `paper_tables.md`.

### 7.2 Figures

`docs/paper_out/make_figures.py` has no command-line flags. It reads `ROOT = ~/eval_runs_victus/` and writes to `OUT = ~/Swachh/docs/paper_out/figures/`. Edit those two constants at the top of the file if your data lives elsewhere.
```bash
cd ~/Swachh/docs/paper_out
python3 make_figures.py
```
It needs numpy and matplotlib only, and `_gt/<world>.npz` grids under `ROOT`. The nine figures (`fig_test_worlds.png`, `fig_exploration_trajectories.png`, `fig_navigation_trajectories.png`, `fig_actual_vs_explored.png`, `fig_coverage_vs_time.png`, `fig_nav_success.png`, `fig_ate_points.png`, `fig_costmap_layers.png`, and so on) land in `docs/paper_out/figures/`. `fig_costmap_layers.png` uses `docs/paper_out/data/*.npz`. Captions: `docs/paper_out/FIGURE_CAPTIONS.md`.

Note: running either script overwrites the committed outputs in `docs/paper_out/`.

---

## 8. Run the unit tests

### 8.1 Evaluation harness tests (181 tests at the last record)

```bash
cd ~/Swachh/Navigation/Simulation/vacuum_ws/src/vacuum_eval
python3 -m pytest test -q -p no:cacheprovider
```
All must pass. These tests need no simulator.

### 8.2 Project-wide test tiers

`Navigation/pytest.ini` defines `testpaths = tests` and markers `unit, integration, system, performance, stress, endurance, regression, safety, security, fault_injection, simulation, hardware, field, acceptance`. `Navigation/tests/conftest.py` stubs heavy dependencies such as cv2.

```bash
cd ~/Swachh/Navigation
python3 -m pytest -m unit
```
Running the whole tree without `-m` also tries tiers that need Gazebo or hardware (`simulation`, `hardware`, `field`, `endurance`). Select markers explicitly, for example `-m "unit or integration"`. **(unverified: not run while writing this manual)**

The explorer package tests (7 at the last record) live in the `vacuum_exploration` package; run `colcon test --packages-select vacuum_exploration` from the workspace. **(unverified)**

---

## 9. Object detection

Folder: `~/Swachh/Object Detection` (note the space; quote the path). Target hardware is a Jetson Orin Nano; an ordinary PC works with ONNX Runtime.

### 9.1 Install

```bash
cd "$HOME/Swachh/Object Detection"
pip install -r requirements.txt
```
`requirements.txt`: `streamlit>=1.32.0`, `opencv-python>=4.8.0`, `onnxruntime>=1.17.0`, `numpy>=1.21.0`, `scipy>=1.8.0`, `psutil>=5.9.0`. For CUDA, remove `onnxruntime` and install `onnxruntime-gpu>=1.17.0` instead (marked optional in the file). On Ubuntu 24.04 you may need a virtual environment (`python3 -m venv`) because of the externally-managed-Python rule. **(unverified)**

### 9.2 Menu launcher

```bash
bash run.sh
```
It runs `pip install -r requirements.txt -q`, then asks:
1. Live Detection UI (`app.py`)
2. Scientific Benchmark UI (`benchmark.py`)
3. RPi Camera Sender (`rpi_sender.py`)
4. Terminal Benchmark CLI (`cli_benchmark.py`, the default): runs `python3 cli_benchmark.py --frames 150 --runs 3 --warmup 10 --interval 1000`

### 9.3 Individual programs

```bash
cd "$HOME/Swachh/Object Detection"
streamlit run app.py            # live detection UI
streamlit run benchmark.py      # scientific benchmark UI
streamlit run rpi_sender.py     # camera sender (run on the Raspberry Pi)
```

`cli_benchmark.py` (headless, YOLOv8 and YOLOv11 in FP32/FP16/INT8). Flags: `--frames` (default 150), `--runs` (3), `--warmup` (10), `--interval` (tegrastats ms, 1000), `--images PATH`, `--wireless`, `--port` (9876).
```bash
python3 cli_benchmark.py --frames 150 --runs 3 --warmup 10          # synthetic frames, direct
python3 cli_benchmark.py --images /path/to/images/                   # real images
python3 cli_benchmark.py --wireless --port 9876 --frames 150 --runs 3   # frames from the Pi
```
`tegrastats` readings need a Jetson.

### 9.4 Wireless setup (Raspberry Pi to Jetson)

1. On the Jetson start the receiver: `python3 cli_benchmark.py --wireless --port 9876 --frames 150 --runs 3` (or use the Benchmark UI).
2. On the Pi install `pip install streamlit opencv-python numpy` and copy `rpi_sender.py` together with `frame_protocol.py` into one folder (the sender imports it).
3. On the Pi run `streamlit run rpi_sender.py` and enter the Jetson's address and port in the UI.

### 9.5 Model weights and TensorRT

`Model weights/` contains:
- `Yolov8/`: `best.pt`, `yolov8n.pt`, ONNX `best_fp32/fp16/int8.onnx`, TensorRT `best_fp32_fp16.trt`, `best_fp32_int8.trt`
- `Yolov11/`: `yolo11n-seg.pt`, `best_fp32/fp16/int8.onnx`, `best_fp32_fp16.trt`
- `Rfdetr/`: `rfdetr_fp32/fp16/int8.onnx`, `hparams.yaml`, `training_config.json`

TensorRT notes (`trt_inference.py`):
- It builds engines from FP32 ONNX in FP16 or INT8 and caches them as `<model>_<precision>.trt` next to the ONNX file; an existing cached engine is loaded instead of rebuilt.
- It needs the `tensorrt` Python module, installed with JetPack (or `pip3 install tensorrt`). Without it the import raises `ImportError: TensorRT not found`.
- `.trt` engines are tied to the GPU and TensorRT version they were built with; rebuild them on a different device rather than copying them.
- `Object Detection/Metrics/` and `Camera/` hold supporting data. **(contents not inspected)**

---

## 10. Hardware / manual mode

Folder: `~/Swachh/Navigation/Manual mode`. Two parts: Arduino firmware that drives two BLDC motors and peripherals, and a GTK4 touchscreen HMI (Jetson Orin Nano) that talks to it over USB serial.

### 10.1 Arduino firmware

File: `Manual mode/arduino/swacch_robot/swacch_robot.ino`.
1. Open it in the Arduino IDE (or use `arduino-cli`, which `setup.sh` installs).
2. Select your board and port, then upload. The exact board type is not stated in the repo; check the sketch header. **(unverified)**
3. Serial settings: 115200 baud, newline-terminated commands.

Serial protocol (from the Manual mode README):
- Movement: `MOVE:FORWARD`, `MOVE:LEFT`, and so on.
- Peripherals: `VACUUM:ON`, `ARM:OFF`, and so on (vacuum, arm, wiper, UV).
- Speed: `SPEED:1` to `SPEED:9`.
- Safety: `ESTOP`, `RESET`.
- The Arduino replies `ACK:<command>` and sends periodic `STATUS:` lines.

### 10.2 HMI build and run

1. One-time setup (installs `build-essential cmake pkg-config libgtk-4-dev`, `arduino-cli`, and adds you to the `dialout` group; uses sudo):
   ```bash
   cd "$HOME/Swachh/Navigation/Manual mode/hmi"
   bash scripts/setup.sh
   ```
2. Log out and back in (or reboot) so the `dialout` group applies.
3. Plug in the Arduino by USB.
4. Build and run:
   ```bash
   bash scripts/run.sh
   ```
   `run.sh` builds with `cmake .. && make -j$(nproc)` in `hmi/build/` on first run if the binary `swacch_hmi` does not exist, auto-detects the first `/dev/ttyUSB*` or `/dev/ttyACM*`, and starts `build/swacch_hmi --port <port>`. With no Arduino it prints an error and falls back to `/dev/ttyUSB0` ("running without hardware").
5. To pick a port yourself after building:
   ```bash
   ./build/swacch_hmi --port /dev/ttyACM0
   ```
6. To rebuild after editing sources, delete `hmi/build/swacch_hmi` (or the `build` folder) and run `bash scripts/run.sh` again.

Safety: use the HMI's emergency stop (`ESTOP`) before approaching the robot, and send `RESET` to re-enable. Test with wheels off the ground first.

`Manual mode/ros.sh` enters a ROS 2 Humble distrobox (`distrobox enter ros-dev`); it is the author's personal container shortcut and is not needed for the simulation. `stats.sh` is not documented. **(unverified)**

---

## 11. Troubleshooting

Always start with the episode's `summary.json` (`status`, `end_reason`, `episode_valid`, `img_drop_pct`, `rtf_true_mean`, `odom_corrupted_by_contact`) and the `diagnose` output. Full per-metric tables are in `docs/FAILURE_MODES.md`.

### 11.1 Environment and start-up

| Symptom | Cause and fix |
|---|---|
| SLAM gets no images, RTAB-Map idle, or image drops | DDS socket buffers too small. `cat /proc/sys/net/core/rmem_max` must print `33554432`; if not, `sudo sysctl -p /etc/sysctl.d/90-ros2-dds.conf` |
| `ros2` nodes cannot see each other after changing Wi-Fi or network | Stale ROS daemon. Run `ros2 daemon stop` (for the right `ROS_DOMAIN_ID`), then relaunch |
| `start.sh` fails with `ptyxis: command not found` | Install `ptyxis` or launch with the direct commands in 3.2 |
| `run_mapping.sh` or `save_map.sh` cannot find `Swachh_Boudhik_Yantra/...` | Hard-coded old paths. Use the symlink workaround or direct commands (3.1, 4.2) |
| `navigate` says "Map not found: ~/maps/stage5/<env>.yaml" | Run `./start.sh explore <env>` then `./save_map.sh <env>` |
| Saved map empty | RTAB-Map was stopped before saving. Save while the simulation and SLAM are running |
| Gazebo fails to start over SSH / no display | `export VACUUM_GZ_HEADLESS_RENDERING=1` |
| Renderer shows llvmpipe (software rendering) with an NVIDIA GPU present | Same variable as above; check `nvidia-smi` for the `gz` process. `preflight.sh` reports the renderer only when a display exists |
| Stray `gz sim` or `ruby` processes make preflight FAIL | `kill <PID>` of the listed processes, re-run preflight |
| Edits to `vacuum_exploration` have no effect | That package installs copies; rebuild it with colcon |
| Contact sensors give no collisions | The robot must be baked into the world at launch (default `embed_robot:=true` in `sim.launch.py`); do not disable it |
| Real-time factor looks fine but runs are slow | Gazebo's own RTF is misleading; read `rtf_true_mean` in `summary.json` |
| Machine overloaded, episodes invalid | Use `--parallel 2` (not 3) on a 16-thread machine; keep RViz closed during campaigns |
| Gazebo `/dev/dri` warnings from libEGL | Harmless when NVIDIA EGL works |

### 11.2 Bad or unmeasurable metrics (`docs/FAILURE_MODES.md`)

Health codes: `OK`; `LOW_N:<count>/<min>`; `NA`. UNMEASURABLE: `NO_DATA`, `NO_EVENTS`, `INVALID_EPISODE`, `GT_MISSING`, `MAP_MISSING`. SUSPECT: `ODOM_CORRUPTED`, `FRAME_OFFSET`, `RANGE`, `NAV_GT_DIVERGENCE`, `LOW_RTF`, `LC_ROT_BIAS`. BAD: `BELOW_FLOOR:<value><op><floor>`.

Floors (diagnosis triggers, never exclusions): navigation success 50 %, coverage 70 %, map completeness 60 %, ATE above 0.30 m, loop-closure precision 50 %, avoidance 80 %. Minimum n: goals 5, encounters 3, accepted loop closures 5, revisits 3, responsiveness events 10.

| Situation | What to do |
|---|---|
| `INVALID_EPISODE` (image drops, RTAB-Map gap) | Infrastructure fault: re-run once with the same seed (`--force`), report both attempts |
| `ODOM_CORRUPTED`, ATE very high | Contact corrupted odometry (a Spin while touching something). Report the headline; also report `ate_fixed_rmse_m_pre_corrupt` and results with and without corrupted episodes |
| `GT_MISSING` / `MAP_MISSING` | Rebuild ground-truth grids offline (`run_batch ... --prebuild-gt --dry-run`) or check the map-save step |
| `LOW_RTF` | Simulation too slow; report as a load result, flag in the text |
| Goal loop (very large `n_goals`) | A bug if it recurs: fix and re-run only if infrastructure; otherwise report |
| Smac DUBIN "no valid path" in tight rooms | Genuine planner limit; the planner is fixed by project decision. Report as measured |
| `NAV_GT_DIVERGENCE` | Compare `nav_success_gt_strict_pct` with `nav_success_gt_pct`; run scripted `gt`, `amcl` and `slam` localisation to separate causes |
| `LC_ROT_BIAS` / wrong loop-closure direction | Run `python3 -m vacuum_eval.check_lc_direction <run>`; the verdict should name `loop_to_ref` |
| Low loop-closure precision in `symmetric_hall` | Expected (the world measures perceptual aliasing); report |

Decision rules: FIX+RERUN only for infrastructure faults, same seed, once. Everything else is reported as measured; never re-run to improve a number. Do not change the planner, robot or sensor model, world geometry, metric definitions or thresholds after a test campaign starts.

### 11.3 Known limitations to cite, not fix
- The wheel axle sits about 8 cm behind `base_footprint`, so in-place spins move the ground-truth pose while odometry reports zero.
- The depth camera has a blind zone below about 0.20 m.
- Effective depth HFOV is 69.4 degrees.
See `docs/FAILURE_MODES.md` and `docs/EVALUATION_FINDINGS_2026-10-25.md`.

---

## 12. Stopping everything safely

### 12.1 Normal stop
1. If you want the map, save it first (section 4) while the simulation is running.
2. In the window running the launch, press `Ctrl+C` once and wait for it to exit.
3. Run the stop script to catch leftovers:
   ```bash
   cd ~/Swachh/Navigation
   ./stop.sh
   ```
   (`./start.sh stop` does the same.) It force-kills (`pkill -9`) processes whose command lines match `ros2 launch`, `gz sim`, `rtabmap`, `nav2`, `bt_navigator`, `planner_server`, `controller_server`, `behavior_server`, `smoother_server`, `velocity_smoother`, `exploration_manager`, `frontier_detector`, `frontier_visualizer`, `exploration_metrics`, `robot_state_publisher`, `parameter_bridge` and `rviz2`, then **deletes `~/.ros/rtabmap.db*`**. Save or copy the database first if you need it.
4. Confirm nothing remains: `pgrep -a "gz|ruby|rtabmap|ros2"`.

### 12.2 Stopping an evaluation run (do not use `stop.sh`)
`stop.sh` is for the manual stack and is too blunt for a running campaign: it kills processes system-wide. For the harness:
1. Find the harness process: `pgrep -af "vacuum_eval.run_episode|vacuum_eval.run_batch"`.
2. Interrupt it gracefully so it can clean up: `kill -INT <harness PID>`.
3. Check for leftovers with `bash ~/Swachh/Navigation/Simulation/scripts/preflight.sh`; it lists stray `gz sim` / `ruby` processes without killing them. Kill listed PIDs one by one with `kill <PID>`.
4. Resume a batch later by re-running the same `run_batch` command; finished episodes are skipped.
5. Never run `pkill -f '<pattern>'` with a pattern that appears in your own command line; it will kill your own shell.

### 12.3 Hardware
1. Send `ESTOP` from the HMI first, then close the HMI.
2. Unplug USB only after the motors are stopped and power is off.

---

One-line summary: this manual covers prerequisites, build, simulation modes, mapping, steering, the evaluation harness, paper tables and figures, tests, object detection, hardware, troubleshooting and safe shutdown, with unverified commands and the hard-coded-path issues in `run_mapping.sh` and `save_map.sh` flagged.
