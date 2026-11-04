# 02. Navigation launcher scripts, setup scripts, documentation and tests

Scope: `/home/hrishikesh/Swachh/Navigation/` top-level files, `Navigation/Simulation/scripts/`, `Navigation/Simulation/Documentation/`, and `Navigation/tests/`.
Everything below is read from the files. Where behaviour depends on code outside the scope (launch files, node sources) this is said explicitly and not guessed.

---

## 1. High-level picture

Two separate families of tooling live here.

| Family | Files | Purpose |
|---|---|---|
| Interactive "operator" launchers (original Swachh Boudhik Yantra workflow) | `start.sh`, `stop.sh`, `run_mapping.sh`, `save_map.sh`, `view_map.sh`, `steer_gui.sh`, `cyclone_dds.xml` | Open Gazebo + SLAM + RViz in desktop terminal windows, drive the robot, explore, save a map, navigate on it. |
| Machine setup / pre-run checks (evaluation workflow) | `Simulation/scripts/setup_machine.sh`, `preflight.sh`, `check_gpu_render.sh`, `README.md` | Install packages, set DDS socket buffers, build the workspace, and check the machine before each batch of evaluation runs. |
| Support | `graphify.py`, `pytest.ini`, `tests/` | Architecture diagram generator; test-suite configuration and tests. |
| Reference docs | `Simulation/Documentation/*.md` | Three static markdown notes (not executed). |

### 1.1 What the launcher does end to end (`start.sh`)

`start.sh` is the single entry point. It takes a mode word as `$1` and opens one or two new `ptyxis` terminal windows, each of which sources ROS and runs a `ros2 launch` (or a sub-script).

| Mode | Command | End-to-end behaviour |
|---|---|---|
| manual (default, also any unrecognised word) | `./start.sh` | Window 1 runs `run_mapping.sh` (Gazebo, RTAB-Map, RViz2, rtabmap_viz, keyboard teleop). Waits 12 s. Window 2 runs `steer_gui.sh`. |
| explore | `./start.sh explore [env]` | Runs `stop.sh` quietly, deletes `~/.ros/rtabmap.db*`, opens one window running `ros2 launch vacuum_exploration exploration.launch.py environment:=<env>`. |
| navigate | `./start.sh navigate [env]` | Requires `~/maps/stage5/<env>.yaml`. Window 1 runs `vacuum_bringup sim.launch.py`. Waits 14 s. Window 2 runs `vacuum_nav2 nav2_localization.launch.py map_path:=... environment:=...`. |
| steer | `./start.sh steer` | Runs `steer_gui.sh` in the current terminal. |
| stop | `./start.sh stop` | Runs `stop.sh`. |

Default environment for `explore` and `navigate` is `apartment`. The header comment lists `apartment office room corridor warehouse`; the script itself does not validate the name.

Typical operator workflow implied by the printed hints: `./start.sh explore apartment`, then (while it still runs) `./save_map.sh apartment`, then `./stop.sh`, then `./start.sh navigate apartment`.

### 1.2 Environment assumptions common to the launchers

- Hardcoded paths that do not exist on this machine (`victus`, user `hrishikesh`): `/home/bmscecse/ros2_ws/install/setup.bash`, `/home/bmscecse/Swachh_Boudhik_Yantra/...`, `$HOME/Swachh_Boudhik_Yantra/...`. Checked: `/home/bmscecse` and `/home/hrishikesh/Swachh_Boudhik_Yantra` are absent here. See per-file notes for which scripts are affected.
- ROS 2 Jazzy at `/opt/ros/jazzy` (present here), Python 3.12 (`/usr/bin/python3.12` present here), the workspace install at `Navigation/Simulation/vacuum_ws/install` (present here).
- `ptyxis` (GNOME terminal) is not on `PATH` on this machine (`which ptyxis` printed nothing). `start.sh` modes `explore`, `navigate`, `manual` all depend on it.
- DDS: `rmw_cyclonedds_cpp`, `ROS_DOMAIN_ID=0`, `CYCLONEDDS_URI` pointing at `cyclone_dds.xml`.

---

## 2. Top-level files in `/home/hrishikesh/Swachh/Navigation/`

### 2.1 `start.sh`

- Shebang `#!/bin/bash`, `set -e`. `DIR` is the directory of the script (`cd "$(dirname "${BASH_SOURCE[0]}")" && pwd`), so it can be invoked from anywhere.
- Arguments: `$1` = mode (default `manual`), `$2` = environment (only for `explore`/`navigate`, default `apartment`).
- Prints a banner, then branches with `if [[ "$MODE" == ... ]]` blocks; each block ends with `exit`.

Line-level behaviour:

| Lines | Mode | Detail |
|---|---|---|
| 33-36 | `stop` | `bash "$DIR/stop.sh"; exit 0`. |
| 41-85 | `explore` | Line 47 `bash "$DIR/stop.sh" >/dev/null 2>&1 \|\| true`, line 48 `rm -rf ~/.ros/rtabmap.db*` (clears SLAM memory). Lines 55-71 open `ptyxis --new-window -- bash -c "..." &` in the background. Inside the window: `cd '$DIR'`; source `/opt/ros/jazzy/setup.bash`; source `/home/bmscecse/ros2_ws/install/setup.bash` only if it exists (`[ -f ... ] &&`); source `Simulation/vacuum_ws/install/setup.bash` (relative, unconditional); export `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`, `ROS_DOMAIN_ID=0`, `CYCLONEDDS_URI=file://'$DIR'/cyclone_dds.xml`; run `python3.12 /opt/ros/jazzy/bin/ros2 launch vacuum_exploration exploration.launch.py environment:=$ENV`; then `exec bash` to keep the window open. |
| 90-157 | `navigate` | `MAP_PATH="$HOME/maps/stage5/${ENV}.yaml"`. If the file is missing: prints instructions and `exit 1`. Otherwise window 1 launches `vacuum_bringup sim.launch.py use_sim_time:=true`; `sleep 14`; window 2 launches `vacuum_nav2 nav2_localization.launch.py map_path:=$MAP_PATH environment:=$ENV`. The banner text in window 2 tells the user to use RViz "2D Pose Estimate" and "Nav2 Goal". |
| 162-167 | `steer` | `bash "$DIR/steer_gui.sh"`. |
| 172-199 | manual (fallthrough) | Window 1: `cd '$DIR'; bash run_mapping.sh; exec bash`. `sleep 12`. Window 2: `bash steer_gui.sh; exec bash`. |

Tricky points:

- The `bash -c "..."` strings are double-quoted, so `$DIR`, `$ENV`, `$MAP_PATH` are expanded by the outer shell before the window starts; escaped `\\` at line 139 becomes a backslash line-continuation inside the inner command.
- Because of `set -e`, a failing command in the outer script (not inside the window) stops the launcher. The `explore` stop call is protected with `|| true`.
- The windows are started with `&`; the outer script does not track their PIDs, so they are only stopped by `stop.sh` pattern matching, by Ctrl+C in the window, or by closing it.
- Any mode word other than `stop`, `explore`, `navigate`, `steer` (including a typo) falls through to the manual mode.
- In the `navigate` banner (lines 129-130) the inner double quotes around "2D Pose Estimate" and "Nav2 Goal" sit inside a double-quoted `bash -c "..."` string. Whether this prints those words as intended was not tested; I did not run it.

Processes started: `ptyxis` windows; inside them `ros2 launch` (Python 3.12) with the launch files named above; or `run_mapping.sh`/`steer_gui.sh`.
Processes stopped: only via `stop.sh` (explore mode and `stop` mode).

### 2.2 `stop.sh`

- Purpose: "Emergency Stop & Clean". No arguments. No `set -e`.
- Runs `pkill -9 -f "<pattern>" 2>/dev/null || true` for each of these patterns, in order: `ros2 launch`, `gz sim`, `rtabmap`, `nav2`, `bt_navigator`, `planner_server`, `controller_server`, `behavior_server`, `smoother_server`, `velocity_smoother`, `exploration_manager`, `frontier_detector`, `frontier_visualizer`, `exploration_metrics`, `robot_state_publisher`, `parameter_bridge`, `rviz2`.
- Then `rm -rf ~/.ros/rtabmap.db*` (wipes the RTAB-Map database so the next run starts blank).
- Hazards, read directly from the code: `pkill -9 -f` matches against the full command line of any process, system-wide, for the current user. It uses SIGKILL (no graceful shutdown). It would also match any other process whose command line contains one of those words (for example an editor or shell command containing `rtabmap` or `nav2`). `CLAUDE.md` of the repo says never to `pkill -f` a pattern that is in your own command line and to stop evaluation runs with `kill -INT <harness PID>`; `stop.sh` does the opposite, so it is a manual-operator script, not part of the evaluation harness. (Whether the evaluation harness calls it was not checked here.)
- The variable `DIR` is computed but not used.

### 2.3 `run_mapping.sh`

- Purpose: Stage 4A teleoperated mapping in one terminal. Called by `start.sh` manual mode (`bash run_mapping.sh`). No arguments. `set -e` is on.
- Sequence:

| Step | Lines | Behaviour |
|---|---|---|
| 1 | 24 | `killall -9 gz sim server gz sim gui ruby parameter_bridge rtabmap rtabmap_viz rviz2 teleop_twist_keyboard \|\| true`, then `sleep 1`. `killall` treats every word as a separate process name (so `gz`, `sim`, `server`, `gui`, `ruby`, ... are each names to kill). |
| 2 | 29-36 | Sources `/opt/ros/jazzy/setup.bash`, `/home/bmscecse/ros2_ws/install/setup.bash` (unconditional here, so with `set -e` it aborts the script if the file is missing), and `/home/bmscecse/Swachh_Boudhik_Yantra/Simulation/vacuum_ws/install/setup.bash`. Exports `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`, `CYCLONEDDS_URI=file:///home/bmscecse/Swachh_Boudhik_Yantra/cyclone_dds.xml`, `LD_LIBRARY_PATH` (adds `/home/bmscecse/ros2_ws/install/lib`), `PATH` (adds `.../vacuum_ws/bin`). It does not export `ROS_DOMAIN_ID`. |
| 3 | 40-51 | `PIDS=()` array and a `cleanup()` function installed with `trap cleanup EXIT`. On exit it sends `kill` (SIGTERM) to each recorded PID that is alive, then `killall -9` on the same list of names (without `teleop_twist_keyboard`). |
| 4 | 55-57 | `python3.12 /opt/ros/jazzy/bin/ros2 launch vacuum_bringup sim.launch.py world:=apartment use_rviz:=false > /tmp/sim_launch.log 2>&1 &`; PID recorded. `sleep 10`. |
| 5 | 64-69 | `ros2 launch vacuum_slam slam.launch.py environment:=apartment use_rviz:=false > /tmp/slam_launch.log 2>&1 &`; `sleep 5`. |
| 6 | 73-76 | `ros2 run rviz2 rviz2 -d /home/bmscecse/Swachh_Boudhik_Yantra/Simulation/vacuum_ws/install/vacuum_bringup/share/vacuum_bringup/config/rviz_config.rviz > /tmp/rviz2.log`. |
| 7 | 80-86 | `ros2 run rtabmap_viz rtabmap_viz` with remaps `rgb/image:=/camera/color/image_raw`, `depth/image:=/camera/depth/image_rect_raw`, `rgb/camera_info:=/camera/color/camera_info`, `odom:=/odom`; log `/tmp/rtabmap_viz.log`. |
| 8 | 89 | Foreground: `python3.12 /home/bmscecse/Swachh_Boudhik_Yantra/Simulation/vacuum_ws/install/vacuum_controller/lib/vacuum_controller/teleop_arrows.py` (keyboard teleop). When it exits, the EXIT trap runs and tears everything down. |

- The world and SLAM environment are hardcoded to `apartment`. Logs go to `/tmp/*.log`.
- Because it has hardcoded `/home/bmscecse` paths, it cannot run unchanged on this machine (those directories do not exist here).

### 2.4 `save_map.sh`

- Usage: `./save_map.sh [env_name]`.
- With no argument: `OUTPUT_DIR=$HOME/maps/stage4`, `MAP_NAME=map`, `STAGE=4`. With an argument: `OUTPUT_DIR=$HOME/maps/stage5`, `MAP_NAME=<arg>`, `STAGE=5`.
- Sources ROS Jazzy, `/home/bmscecse/ros2_ws/install/setup.bash` (only if present), and `"$HOME/Swachh_Boudhik_Yantra/Simulation/vacuum_ws/install/setup.bash"` (unconditional; `set -e` aborts if missing). Exports `RMW_IMPLEMENTATION`, `ROS_DOMAIN_ID=0`, `CYCLONEDDS_URI="file://$HOME/Swachh_Boudhik_Yantra/cyclone_dds.xml"`.
- `mkdir -p "$OUTPUT_DIR"`, then `python3.12 /opt/ros/jazzy/bin/ros2 run nav2_map_server map_saver_cli -f "$OUTPUT_DIR/$MAP_NAME" --ros-args -p use_sim_time:=true`. This writes `<name>.pgm` and `<name>.yaml` from the map topic that must already be published (so SLAM must be running; the header warns that stopping RTAB-Map first gives an empty or missing map).
- Prints a box with the output paths and, for stage 5, the hint `./start.sh navigate $MAP_NAME`.
- Starts no long-lived processes and stops none.

### 2.5 `view_map.sh`

- No arguments. Runs `xdg-open ~/maps/stage4/map.pgm >/dev/null 2>&1 &` and prints "Done!". It only opens the stage-4 default map (it does not look at stage-5 maps).

### 2.6 `steer_gui.sh`

- Launches the Tkinter steering GUI. `SCRIPT_DIR` is auto-detected; `WS=$SCRIPT_DIR/Simulation/vacuum_ws`; `GUI=$WS/src/vacuum_controller/vacuum_controller/robot_steering_gui.py`.
- Sources `/opt/ros/jazzy/setup.bash` and `$WS/install/setup.bash`; exports `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`, `ROS_DOMAIN_ID=0`, and prepends `$WS/install/vacuum_controller/lib/python3.12/site-packages` to `PYTHONPATH`. Does not export `CYCLONEDDS_URI`.
- Runs `python3.12 "$GUI"` in the foreground. Unlike the other scripts it uses only relative-to-script paths, so it does not depend on `/home/bmscecse`. It needs a display (Tkinter). What topic the GUI publishes to is not in this scope.

### 2.7 `cyclone_dds.xml`

- CycloneDDS configuration. Contents: `Domain id="any"` -> `Discovery/MaxAutoParticipantIndex = 200`, and `Internal/SocketReceiveBufferSize min="16MB" max="32MB"`.
- The comment says the default `MaxAutoParticipantIndex` of 32 is too small for the many ROS nodes of the exploration/navigation stack, and that the buffer is raised for large point-cloud transfers.
- Used by pointing `CYCLONEDDS_URI` at it: `start.sh` (explore, navigate), `run_mapping.sh`, `save_map.sh`. `preflight.sh` checks the same file (see 3.2). `setup_machine.sh` writes `export CYCLONEDDS_URI=file://<repo>/Navigation/cyclone_dds.xml` into `~/.bashrc`.
- Note: the min buffer only helps if the kernel limit allows it; that is what the sysctl step in `setup_machine.sh` sets (32 MiB = 33554432).

### 2.8 `graphify.py`

- Shebang `#!/usr/bin/env python3.12`. Purpose: scan the ROS 2 workspace and generate architecture diagrams (Mermaid) and a report. Not part of the robot's run-time.
- Invocation: `python3.12 graphify.py [--workspace PATH] [--output DIR] [--model NAME] [--env FILE] [--no-ai]`.

| Argument | Default | Effect |
|---|---|---|
| `--workspace` | `''` -> `script_dir.parent.parent.parent` | `vacuum_ws` root. The default is `Path(__file__).resolve().parent.parent.parent`; the code comment assumed the script lived in `src/vacuum_utils/scripts/`. For this copy in `Navigation/` that resolves to `/home/hrishikesh` (derived by reading, not run), so pass `--workspace` explicitly.  |
| `--output` | `<workspace>/graphify_output` | Output directory. |
| `--model` | `gemini-2.0-flash` | Gemini model name. |
| `--env` | `<workspace>/.env` | Path to a `.env` file loaded with `python-dotenv`. |
| `--no-ai` | off | Static mode: no API call, no key needed. |

- Dependencies: `python-dotenv` and `requests`; each missing one prints an error and `sys.exit(1)` at import time (even for `--no-ai`).
- Classes and functions:
  - `GeminiClient` (POST to `https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent?key=<key>`, temperature 0.2, 8192 max tokens, 120 s timeout; HTTP 429 or any non-200 returns `''` so the caller falls back to static output). Note the API key is put in the URL query string.
  - `WorkspaceScanner` scans `<ws>/src` for `package.xml` (name, version, description, deps), `*.launch.py` (executables, `get_package_share_directory` packages), `.py` files containing `rclpy` (regex for `create_publisher`, `create_subscription`, `create_service` topic names; files with `test` in their path parts are skipped), `*.xacro`, `*.yaml`, plus a file tree capped at 250 lines.
  - `build_prompt(data)` builds the LLM prompt asking for sections `PACKAGE_GRAPH, DATAFLOW_GRAPH, TF_TREE, LAUNCH_SEQUENCE, CONTROLLER_ARCH, SUMMARY`. The prompt text is hardcoded to "Stage 4B" and names nine packages; it does not mention `vacuum_eval` or `vacuum_localization`.
  - `StaticGraphGenerator` with `INTERNAL_PKGS` (nine package names) and `generate_all`, `_package_graph`, `_dataflow_graph`, `_tf_tree`, `_launch_sequence`, `_controller_arch`, `_summary`. These produce the deterministic fallback. Any section missing from the Gemini reply is filled from this.
  - `parse_sections` splits the reply on lines matching `## [SECTION: NAME]`.
  - `write_reports` writes `workspace_graph.md`, one `<section>.mmd` per non-summary section, and `summary.md`.
- Data leaving the machine: in the default (non-`--no-ai`) mode the scanned file tree, package data, snippets of launch/node files and up to 1500 characters of every YAML are sent to the Gemini API. The repo `CLAUDE.md` forbids sending data to third-party services without the user's explicit OK, so use `--no-ai` unless approved. In non-`--no-ai` mode with no `GEMINI_API_KEY` it exits with `[ERROR] GEMINI_API_KEY not set.`.
- Output header says "Generated ... by graphify.py (Gemini 2.0 Flash)" regardless of mode (hardcoded in `write_reports`).
- Not run here; behaviour above is from reading the source.

### 2.9 `pytest.ini`

| Setting | Value |
|---|---|
| `testpaths` | `tests` |
| `python_files` / `python_classes` / `python_functions` | `test_*.py` / `Test*` / `test_*` |
| `addopts` | `-v --tb=short --strict-markers --durations=10` |
| `markers` | `unit, integration, system, performance, stress, endurance, regression, safety, security, fault_injection, simulation, hardware, field, acceptance` (with a one-line meaning each) |
| `filterwarnings` | `error::pytest.PytestUnknownMarkWarning` |

`--strict-markers` means any marker not in this list is an error. Run pytest from `/home/hrishikesh/Swachh/Navigation` so `pytest.ini` is picked up and `tests.conftest` is importable.

---

## 3. `Navigation/Simulation/scripts/`

### 3.1 `README.md`

Short description: works on the WSL2 laptop and on a native Ubuntu workstation (example given: HP Z4 with RTX A6000); ROS 2 Jazzy needs Ubuntu 24.04. Lists `setup_machine.sh [--dry-run] [--yes]` (idempotent installer) and `preflight.sh` (read-only checks). Fresh-machine recipe: `./setup_machine.sh --dry-run`, `./setup_machine.sh`, `wsl --shutdown` (WSL only), `source ~/.bashrc`, `./preflight.sh`. States that with an NVIDIA GPU Gazebo renders natively and `render_gpu` should stay false (WSL d3d12 only).

### 3.2 `preflight.sh`

- Read-only checks to run before every evaluation batch. "Never kills anything." No arguments. Exit code 1 if any `FAIL`, else 0.
- Paths derived from the script location: `SIM_DIR` = parent of the scripts dir, `REPO` = two levels above `SIM_DIR`, `WS=$SIM_DIR/vacuum_ws`.

| Check | Pass condition | Fail message / remedy printed |
|---|---|---|
| `rmem_max` | `/proc/sys/net/core/rmem_max` equals exactly `33554432` | `sudo sysctl -p /etc/sysctl.d/90-ros2-dds.conf` |
| Stray processes | `pgrep -fa "gz sim\|ruby"` (excluding pgrep and `preflight.sh` lines) is empty | lists the processes, does not kill them |
| Disk | `mkdir -p ~/eval_runs`; `df` free GB under it >= 20 | prints free GB |
| RAM | info only (`MemAvailable` in GB) | none |
| ROS env | `ROS_DISTRO` == `jazzy` | source `/opt/ros/jazzy/setup.bash` |
| RMW | `RMW_IMPLEMENTATION` == `rmw_cyclonedds_cpp` | prints actual value |
| Workspace built | `$WS/install/setup.bash` exists | `colcon build --symlink-install` |
| CycloneDDS config | file named by `CYCLONEDDS_URI` (with `file://` stripped; default `$REPO/Navigation/cyclone_dds.xml`) exists and a regex finds `SocketReceiveBufferSize ... min="NNMB"` with NN from 16 to 99 | prints config path and the URI |
| Suggested parallelism | info: `nproc`, GPU present (via `nvidia-smi -L`), `PAR = max(1, floor(nproc/6.5))`, `+1` when a GPU is present | none |
| Renderer | if `glxinfo` exists: FAIL when the renderer string contains `llvmpipe`; PASS with the string otherwise; info if empty; info if `glxinfo` not installed | `apt install mesa-utils` |

Tricky point: the stray-process check pattern `gz sim|ruby` could also match a shell whose command line contains those words; the script filters only `pgrep` and `preflight.sh`.

### 3.3 `setup_machine.sh`

- Usage: `setup_machine.sh [--dry-run] [--yes]` (`-y` also accepted). Unknown args print `unknown arg` and exit 2. Uses `sudo` unless run as root. In `--dry-run` the `run` helper prints `[dry-run] ...` instead of executing; `confirm` returns success automatically in dry-run or with `--yes`; otherwise it prompts `[y/N]`.
- Uses `set -u` but not `set -e`, so a failing step does not stop later steps.
- Steps (the script prints `=== [n] name ===`):

| # | Step | Behaviour |
|---|---|---|
| 1 | Detect platform | Detects WSL by `microsoft` in `/proc/version`; reads `/etc/os-release`; warns if `VERSION_ID` is not `24.04`; if `/opt/ros/jazzy` is missing prints the ROS apt repo link and aborts (exit 1) unless dry-run. |
| 2 | GPU | If `nvidia-smi` exists, prints name and driver and reminds to keep `render_gpu=false`; otherwise says llvmpipe software rendering will be used. |
| 3 | apt packages | Checks with `dpkg -s` a list of 21 packages (`ros-jazzy-desktop`, `ros-jazzy-ros-gz`, `ros-jazzy-gz-ros2-control`, `ros-jazzy-ros2-control`, `ros-jazzy-ros2-controllers`, `ros-jazzy-navigation2`, `ros-jazzy-nav2-bringup`, `ros-jazzy-rtabmap-ros`, `ros-jazzy-depthimage-to-laserscan`, `ros-jazzy-topic-tools`, `ros-jazzy-rmw-cyclonedds-cpp`, `ros-jazzy-spatio-temporal-voxel-layer`, `python3-psutil`, `python3-scipy`, `python3-matplotlib`, `python3-pil`, `python3-yaml`, `python3-pytest`, `mesa-utils`, `python3-colcon-common-extensions`, `python3-rosdep`); installs only the missing ones with `apt-get update` and `apt-get install -y` after confirmation. |
| 4 | DDS sysctl | Writes `/etc/sysctl.d/90-ros2-dds.conf` with `net.core.rmem_max`, `rmem_default`, `wmem_max`, `wmem_default` all `=33554432` (only if the content differs), then `sysctl -p` on it. On WSL adds `command = sysctl -p /etc/sysctl.d/90-ros2-dds.conf` under `[boot]` in `/etc/wsl.conf` (takes effect after `wsl --shutdown`). |
| 5 | `~/.bashrc` | Appends, if not already present as an exact line: `source /opt/ros/jazzy/setup.bash`; `[ -f $WS/install/setup.bash ] && source $WS/install/setup.bash`; `export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`; `export CYCLONEDDS_URI=file://$CYCLONE`. |
| 6 | rosdep | `rosdep init` if the default list is absent, `rosdep update`, and (with confirmation) `rosdep install --from-paths src --ignore-src -r -y` in `$WS`. |
| 7 | colcon build | `colcon build --symlink-install` in `$WS`. |
| 8 | vacuum_eval unit tests | `cd $WS/src/vacuum_eval && python3 -m pytest -q` (these are the evaluation package's own tests, not `Navigation/tests`). |

- Last line prints the next command: `<scripts dir>/preflight.sh`.

### 3.4 `check_gpu_render.sh`

- Usage: `check_gpu_render.sh [--gz WORLD.sdf] [--adapter NAME] [--secs N]` (`-h`/`--help` prints header lines 2-10). Unknown argument: exit 2. Defaults: adapter `Intel`, window 60 s. Header says "Starts nothing ROS-related. Only the gz process group it starts is killed."
- Purpose: check whether Mesa's d3d12 renderer (WSL2 GPU path) works and, optionally, whether it speeds up Gazebo.
- Flow:
  1. `renderer()` runs `glxinfo -B` (or `eglinfo`) with given environment and extracts the "OpenGL renderer" line; if neither tool is installed it prints an install hint. It is called twice: default environment (`A=1`, a harmless dummy variable), and with `GALLIUM_DRIVER=d3d12` plus `MESA_D3D12_DEFAULT_ADAPTER_NAME=<adapter>`.
  2. `D3D_ACTIVE=yes` when the d3d12 renderer string matches `d3d12`, `Intel`, `NVIDIA` or `AMD`, but is reset to `no` if it contains `llvmpipe`.
  3. Without `--gz`: prints `VERDICT: d3d12 renderer active=...` and exits 0.
  4. With `--gz WORLD`: checks the file exists and `gz` is on `PATH`, then `run_rtf()` twice (default env, then d3d12 env). `run_rtf` starts `setsid env <vars> gz sim -r -s --headless-rendering "$WORLD"` in the background, sleeps 15 s for loading, reads simulation time from `gz topic -e -n 1 -t /stats` (via an awk script that takes the `sim_time` block's `sec` and `nsec`), sleeps `SECS`, reads it again, kills the whole process group with `kill -- "-$pid"`, and computes true real-time factor = delta(sim time) / delta(wall time) with `date +%s.%N`. It prints `nan` if either sim-time reading is empty.
  5. Prints `VERDICT: true RTF default=... d3d12=... speedup=...x d3d12 renderer active=...`.
- It sleeps 3 s between the two gz runs. Total duration with `--gz` is roughly 2 x (15 + SECS) + 3 seconds.

---

## 4. `Navigation/Simulation/Documentation/`

Three static markdown files. None is executed or read by any script in this scope.

| File | What it contains |
|---|---|
| `d435i_custom_world_guide.md` | A how-to guide (ROS 2 Jazzy, Gazebo Harmonic) in four parts. Part 1: replace the TurtleBot3 LiDAR and camera with an Intel RealSense D435i (spec table; copy the TurtleBot3 waffle URDF into `~/robot_ws/src/my_robot/urdf`; delete the LiDAR block; add a `camera_link` plus an `rgbd_camera` and an `imu` sensor with noise; a `ros_gz_bridge` `parameter_bridge` launch file for `/camera/image`, `/camera/depth_image`, `/camera/camera_info`, `/camera/points`, `/camera/imu`; an `rtabmap_launch` command using depth only). Part 2: building custom Gazebo worlds (an SDF example room with four walls and two obstacles, loading via `ros_gz_sim gz_sim.launch.py`, GUI editing, Gazebo Fuel). Part 3: learning resources (YouTube channels, docs links, learning order). Part 4: command cheatsheet. It uses example paths such as `/home/bmscecse/my_world.world` and generic topic names; these are tutorial examples, not the topics the actual workspace uses (the scripts above use `/camera/color/image_raw` and `/camera/depth/image_rect_raw`). |
| `ros2_jazzy_final_verified.md` | A table of 42 ROS capabilities with installed/not-installed status and key packages, stamped "System: Ubuntu 26.04 (Resolute) \| Distro: ROS 2 Jazzy Jalisco \| Total packages: 409 \| Verified: 2026-07-14". Lists ORB-SLAM 3 as not installed, microROS and RealSense as manual, `rtabmap_rviz_plugins` as skipped because of a Qt6 conflict. Summary counts: 42 checked, 41 fully installed, 1 manual build, 2 optional. (Its arithmetic is as written in the file; the table above it marks ORB-SLAM 3 not installed and several items elsewhere as manual.) |
| `software_stack.md` | "Live-verified specifications" intended for a paper's methodology section: versions of OS (Ubuntu 26.04 LTS, kernel `7.0.0-22-generic`), ROS 2 Jazzy (`rclcpp` 28.1.18, `rclpy` 7.1.11), Cyclone DDS 0.11.0, Fast DDS 2.14.6, Gazebo Sim 8.11.0, `ros_gz_bridge` 1.0.22, RTAB-Map 0.23.7, `slam_toolbox` 2.8.5, Nav2 1.3.12 (Smac, Theta*, DWB, MPPI), `robot_localization` 3.8.3, RealSense 4.58.1, OpenCV 4.10.0, PCL 1.15.1, Boost 1.90.0, GCC 15.2.0, CMake 4.2.3, Python 3.14.4, `evo` 1.36.5, SciPy, Pandas, Matplotlib, Seaborn, NumPy. The file states it describes an "HP Z4 G5 Workstation". These values describe that other machine; this repo's current host is Ubuntu 24.04 (per the project `CLAUDE.md`), so they do not describe this machine. |

---

## 5. `Navigation/tests/`

### 5.1 Layout and what is real

The tree has 14 tier directories matching the markers in `pytest.ini`. Only some contain test files; the rest hold an empty `__init__.py` only.

| Directory | Contains tests? | Test files |
|---|---|---|
| `unit/controllers` | yes | `test_cmd_vel_relay.py`, `test_odometry_noise.py` |
| `unit/exploration` | yes | `test_frontier_detector.py` |
| `unit/navigation` | yes | `test_pose_quality.py` |
| `unit/vision` | yes | `test_nms.py`, `test_preprocess.py` |
| `unit/diagnostics`, `hmi`, `serial`, `slam`, `utils` | no (only `__init__.py`) | none |
| `integration/ros_topics` | yes | `test_topic_contract.py` |
| `integration/detector_to_arm`, `exploration`, `launch`, `nav2_to_controller`, `sensor_to_slam`, `slam_to_nav2`, `tf` | no | none |
| `safety` | yes | `test_velocity_limits.py` |
| `regression` | yes | `test_known_bugs.py` |
| `fault_injection` | yes | `test_corrupted_inputs.py` |
| `performance` | yes | `test_nms_throughput.py` |
| `acceptance`, `endurance`, `field`, `hardware`, `security`, `simulation`, `stress`, `system/*` | no | none |

Total collected: 126 tests (`pytest --collect-only`).

### 5.2 How to run

From `/home/hrishikesh/Swachh/Navigation` (the directory holding `pytest.ini`):

```
python3 -m pytest                       # whole suite
python3 -m pytest -m unit               # one marker
python3 -m pytest -m "safety or regression"
python3 -m pytest tests/safety/test_velocity_limits.py
```

No ROS installation or hardware is needed for most tests: `tests/conftest.py` provides stubs. Two groups need real files on disk: the vision-related tests need a `Camera/vision/detector.py` (see 5.4), and the safety tests need `Simulation/vacuum_ws/src/vacuum_nav2/config/nav2_params.yaml` (exists).

### 5.3 `tests/conftest.py` (shared stubs)

| Item | What it provides |
|---|---|
| `_mock_cv2()` | Fake `cv2` module: constants (`COLOR_BGR2GRAY=6`, `COLOR_BGR2RGB=4`, `INTER_LINEAR=1`, `BORDER_CONSTANT=0`, `CAP_*`), `cvtColor` (gray = first channel; 2-D to 3-channel stack), `resize` (returns zeros of the target size, not an actual resize), `copyMakeBorder` (fills padding with 114 for 3-channel), `VideoWriter_fourcc` returning 0, and `cv2.dnn.NMSBoxes`, a pure-Python greedy O(N^2) NMS taking boxes in xyxy. |
| `_mock_rclpy()` | Fake `rclpy`, `rclpy.node.Node` (parameter store, silent logger, clock, publisher that records messages), `rclpy.qos` with `QoSProfile` and policy enums, plus no-op `init`, `ok`, `spin`, `shutdown`. |
| `_mock_ros_msgs()` | Fake `geometry_msgs`, `nav_msgs`, `std_msgs`, `sensor_msgs`, `diagnostic_msgs`, `visualization_msgs`, `nav2_msgs` modules with minimal message classes. |
| fixture `mock_ros_env` | Injects all of the above (plus an empty `onnxruntime` module) into `sys.modules`, yields `(rclpy_stub, cv2_stub)`, and restores the previous modules afterwards. |
| fixture `make_flat_cov` | Factory returning a 36-element covariance list with `cov[0]=xx`, `cov[7]=yy`, `cov[35]=zz_rot`. |
| fixture `make_occupancy_grid` | Factory returning a fake grid class with `info` (width, height, resolution, origin) and `data`. |

Because the cv2 stub's `resize` returns zeros, any assertions in vision tests about pixel content run against this stub, not real OpenCV (unless real cv2 is imported first; the tests inject the stub explicitly).

### 5.4 Source modules the tests import (and a current problem)

| Test group | Module imported | Path built by the test |
|---|---|---|
| NMS / preprocess (unit/vision, regression, fault_injection, performance) | `detector` (`_nms`, `_preprocess`, `_letterbox`) | `Navigation/Camera/vision` (relative `..` joins from the test files). |
| Pose quality (unit/navigation, regression, fault_injection) | `pose_quality.PoseQuality` | `Navigation/Simulation/vacuum_ws/src/vacuum_localization/vacuum_localization` |
| Frontier detector (unit/exploration, integration, fault_injection) | `frontier_detector` | `Navigation/Simulation/vacuum_ws/src/vacuum_exploration/vacuum_exploration` |
| cmd-vel relay | `cmd_vel_relay` | `Navigation/Simulation/vacuum_ws/src/vacuum_controller/vacuum_controller` |
| Odometry noise | `odometry_noise_node` | `vacuum_controller` package (path built at lines 103-111 of the test file; the exact joins were not expanded here) |

Observed on this machine (I ran `python3 -m pytest -q` in `Navigation/`): **126 collected, 85 passed, 41 failed**. All 41 failures are the vision/detector-dependent tests; the 17 in `unit/vision/test_nms.py` show `ModuleNotFoundError: No module named 'detector'`. The directory `/home/hrishikesh/Swachh/Navigation/Camera` does not exist, so `detector.py` cannot be imported. Failure counts by file: `unit/vision/test_nms.py` 17, `unit/vision/test_preprocess.py` 10, `fault_injection/test_corrupted_inputs.py` 6, `performance/test_nms_throughput.py` 4, `regression/test_known_bugs.py` 4. Those that do not need `detector` (pose quality, frontier detector, relay, odometry noise, safety, topic contract, and the PoseQuality tests inside regression/fault_injection) pass. I only read the first error type for `test_nms.py`; I assume the other failing files fail for the same missing module, consistent with their code, but did not print each traceback.

### 5.5 Test files in detail

#### `unit/controllers/test_cmd_vel_relay.py` (marker `unit`, 11 tests)
Checks `CmdVelRelay` converts a `Twist` to a `TwistStamped` unchanged, using mocked rclpy and a fake publisher/clock.
- `TestCmdVelRelayPassthrough`: `test_linear_x_preserved`, `test_angular_z_preserved`, `test_all_six_velocity_components_preserved`, `test_zero_velocity_passthrough`, `test_negative_velocity_reverse`, `test_max_velocity_values`.
- `TestCmdVelRelayHeader`: `test_frame_id_is_base_footprint`, `test_stamp_is_not_none`, `test_stamp_has_sec_field`.
- `TestCmdVelRelayPublishCount`: `test_exactly_one_publish_per_callback`, `test_ten_rapid_callbacks_all_published`.

#### `unit/controllers/test_odometry_noise.py` (marker `unit`)
Checks `OdometryNoiseNode` in passthrough mode (`enable_noise=False`) and noisy mode.
- `TestPassthroughMode`: `test_position_x_unchanged`, `test_position_y_unchanged`, `test_position_z_unchanged`, `test_child_frame_id_preserved`, `test_header_preserved`, `test_publish_called_once`.
- `TestNoisyMode`: `test_position_x_differs_from_input`, `test_noise_within_3_sigma`, `test_zero_noise_std_output_equals_input`.
The module docstring also lists orientation-perturbation and large-value cases; no test with those names is present in the file, so those docstring items are not implemented as tests.

#### `unit/exploration/test_frontier_detector.py` (marker `unit`)
Tests the Wavefront Frontier Detection private methods of `FrontierDetector` without ROS.
- `TestFindFrontierCells`: `test_basic_free_adjacent_to_unknown_is_frontier`, `test_fully_occupied_returns_empty`, `test_fully_unknown_returns_empty`, `test_fully_free_returns_empty`, `test_border_cells_excluded`, `test_multiple_frontier_cells_detected`.
- `TestBfsCluster`: `test_single_connected_cluster`, `test_two_disconnected_clusters`, `test_single_cell_cluster`, `test_all_cells_visited`.
- `TestCellsToWorld`: `test_origin_zero_single_cell`, `test_nonzero_origin`, `test_centroid_of_two_cells`.
- `TestExtractFrontiers`: `test_known_grid_returns_frontiers`, `test_empty_data_returns_empty_list`, `test_all_occupied_returns_empty_list`, `test_all_unknown_returns_empty_list`, `test_min_size_filter_removes_small_clusters`, `test_frontier_has_valid_centroid_coordinates`, `test_frontier_ids_are_unique`.

#### `unit/navigation/test_pose_quality.py` (marker `unit`)
Tests `PoseQuality` (localization health from a 36-element covariance; trace = `cov[0] + cov[7]`, yaw variance = `cov[35]`).
- `TestClassify`: `test_good_when_trace_below_cov_good`, `test_good_just_below_threshold`, `test_warning_at_exact_good_threshold`, `test_warning_between_good_and_warning`, `test_warning_just_below_cov_warning`, `test_lost_at_exact_cov_warning`, `test_lost_above_warning`, `test_lost_far_above_threshold`, `test_all_zero_covariance_is_good`, `test_empty_covariance_is_lost`, `test_short_covariance_below_36_is_lost`.
- `TestTracePosition`: `test_correct_sum_of_cov_0_and_7`, `test_zero_trace`, `test_returns_inf_for_empty_list`, `test_returns_inf_for_short_list`.
- `TestYawVariance`: `test_returns_cov_35`, `test_returns_inf_for_empty`, `test_returns_inf_for_short_list`.
- `TestIsConvergedIsLost`: `test_is_converged_true_below_threshold`, `test_is_converged_false_at_threshold`, `test_is_lost_true_at_cov_lost`, `test_is_lost_false_below_cov_lost`.
Note: the file's docstring says "LOST when trace >= cov_lost" while a test named `test_lost_at_exact_cov_warning` implies LOST begins at `cov_warning`; the regression file builds `PoseQuality(cov_good=0.05, cov_warning=0.25, cov_lost=1.0)`. The real class was not in scope, so which boundary the code uses is not stated here beyond what the test names suggest.

#### `unit/vision/test_nms.py` (marker: no `pytestmark` found by grep; collected under unit directory) 
Tests `detector._nms(pred, conf_thr, iou_thr, allowed_ids)` with synthetic YOLO-style arrays of 85 columns (4 box + 1 objectness + 80 classes; class 39 is used in tests). Output is expected to have 6 columns.
- `TestNMSEmptyInput`: `test_empty_shape_0_85_returns_empty_array`, `test_empty_shape_85_0_transposed_returns_empty`, `test_empty_3d_shape_1_85_0`.
- `TestNMSSingleDetection`: `test_single_allowed_class_above_threshold`, `test_single_detection_below_threshold_filtered`, `test_single_disallowed_class_filtered`, `test_single_at_exact_confidence_threshold`.
- `TestNMSMultipleDetections`: `test_two_non_overlapping_both_survive`, `test_two_identical_bboxes_only_one_survives`, `test_high_conf_wins_over_low_conf_with_overlap`, `test_different_allowed_classes_both_survive`, `test_mixed_allowed_and_disallowed_classes`, `test_all_below_threshold_returns_empty`.
- `TestNMSOutputShape`: `test_output_columns_are_6`, `test_output_dtype_is_float32`, `test_xyxy_ordering_correct`, `test_3d_input_1_n_85_is_handled`.
Currently all 17 fail here (missing `detector`, see 5.4). Note: without `pytestmark`, `-m unit` will not select this file; I did not confirm that for the other vision file.

#### `unit/vision/test_preprocess.py` (marker `unit`)
Tests `_letterbox` and `_preprocess` from `detector.py`.
- `TestLetterbox`: `test_output_is_img_size_x_img_size`, `test_square_frame_ratio_is_1`, `test_wide_frame_ratio_less_than_1`, `test_tall_frame_ratio_less_than_1`, `test_1x1_frame_does_not_crash`.
- `TestPreprocess`: `test_output_tensor_shape`, `test_output_values_normalized_0_to_1`, `test_grayscale_2d_input_bw_mode`, `test_ratio_is_finite_and_nonzero`, `test_color_mode_does_not_crash`.
Currently all 10 fail here (missing `detector`).

#### `integration/ros_topics/test_topic_contract.py` (marker `integration`)
Mocked-ROS "topic contracts" by calling node callbacks directly.
- `TestCmdVelRelayTopicContract`: `test_output_topic_frame_id_is_base_footprint`, `test_linear_velocity_preserved_exactly`, `test_stamp_is_nonzero`.
- `TestFrontierCentroidEncodingContract`: `test_pose_z_encodes_cluster_size`, `test_frontier_ids_monotonically_assigned`, `test_centroid_in_correct_world_frame`.
The docstring also lists an `/odom_noisy` passthrough contract; no corresponding test class exists in this file.

#### `safety/test_velocity_limits.py` (marker `safety`)
Reads `Simulation/vacuum_ws/src/vacuum_nav2/config/nav2_params.yaml` (module-scoped fixture `nav2_params`) and asserts configured limits. Tests skip if a key is not found.
- `TestVelocityLimits`: `test_max_vel_x_within_safe_limit` (MPPI `controller_server.ros__parameters.FollowPath.vx_max`, else `velocity_smoother.max_velocity[0]`, must be <= 0.30), `test_max_vel_theta_within_safe_limit` (`velocity_smoother.max_velocity[2]` <= 1.5), `test_min_vel_x_not_too_large_in_reverse` (`velocity_smoother.min_velocity[0]` >= -0.30).
- `TestCostmapSafety`: `test_inflation_radius_positive` (`inflation_layer.inflation_radius` > 0 in local or global costmap), `test_costmap_resolution_fine_enough` (`resolution` <= 0.10 in each costmap found).
- `TestRecoveryBehaviors`: `test_recovery_behaviors_not_empty` (`behavior_server.ros__parameters.behavior_plugins` non-empty).
- `TestYAMLStructureIntegrity`: `test_nav2_params_file_exists`, `test_nav2_params_is_valid_yaml`, `test_nav2_params_has_controller_server`.
Caveats from the code: the module docstring says 0.26 m/s and 1.0 rad/s, but the actual thresholds in the assertions are 0.30 m/s and 1.5 rad/s; `AMCL_PARAMS_PATH` is defined but unused. Because of the `skip` branches, a renamed key makes a test skip, not fail. When run here: 17 of the `safety or regression or fault_injection or performance` selection failed (all detector-related) and 17 passed; I did not isolate the safety results separately from that count.

#### `regression/test_known_bugs.py` (marker `regression`)
Permanent guards for named bugs. Module-scoped autouse fixture injects the cv2 stub.
- `TestBug001NMSEmptyCrash`: `test_nms_empty_shape_0_85_does_not_crash` (result is an ndarray of shape (0, 6)), `test_nms_empty_shape_85_0_does_not_crash`, `test_nms_empty_3d_does_not_crash`.
- `TestBug002ExactThreshold`: `test_score_at_exact_threshold_is_rejected` (score equal to threshold must be filtered, strict `>`).
- `TestBug003PoseQualityBoundary`: `test_classify_at_exact_good_boundary_is_warning` (`PoseQuality(0.05, 0.25, 1.0)`, trace exactly 0.05 -> `"WARNING"`).
The first four need `detector` (fail here); BUG #003 passes.

#### `fault_injection/test_corrupted_inputs.py` (marker `fault_injection`)
Autouse fixture injects cv2/rclpy/message stubs. Checks nothing crashes on bad input.
- `TestNMSCorruptedInputs`: `test_nan_scores_do_not_crash`, `test_inf_scores_do_not_crash`, `test_negative_scores_filtered_out`, `test_all_zeros_pred_returns_empty`, `test_single_row_pred_no_crash`, `test_very_large_bbox_coordinates`.
- `TestPoseQualityCorruptedInputs`: `test_negative_covariance_does_not_crash`, `test_nan_covariance_does_not_crash`, `test_inf_covariance_returns_lost`, `test_single_element_covariance_returns_lost`.
- `TestFrontierDetectorCorruptedGrid`: `test_grid_with_boundary_values`, `test_1x1_grid_no_crash`, `test_empty_data_no_crash` (builds a `FrontierDetector` with `__new__` so no ROS init runs, setting `_cluster_radius=0.5`, `_min_size=2`).
The docstring lists more cases (None frame, YAML missing field) with no matching tests. The six NMS tests fail here (missing `detector`).

#### `performance/test_nms_throughput.py` (marker `performance`)
Timing checks with the pure-Python cv2 stub, so budgets are loose.
- `test_nms_100_detections_under_500ms` (average over 5 runs must be < 5000 ms despite the name), `test_nms_empty_input_is_near_instant` (< 5000 microseconds average over 1000 calls), `test_preprocess_640x480_under_10ms` (assert < 500 ms), `test_preprocess_1920x1080_under_50ms` (assert < 2000 ms).
Test names state tighter budgets than the assertions enforce. All four fail here (missing `detector`).

---

## 6. Gaps and unclear points

- `start.sh` modes `explore`, `navigate`, `manual` depend on `ptyxis`, which is not installed here; `run_mapping.sh` and `save_map.sh` depend on `/home/bmscecse/...` or `$HOME/Swachh_Boudhik_Yantra/...` that do not exist here. How the evaluation harness launches simulations (probably not via these scripts) is outside this scope.
- The launch files (`exploration.launch.py`, `sim.launch.py`, `slam.launch.py`, `nav2_localization.launch.py`) and node sources are outside this scope, so their arguments are only as passed by the scripts.
- `Navigation/Camera/vision/detector.py` is absent; the 41 failures listed in 5.4 follow from that.
- Some counts in my test-file headings above were taken from a quick grep; where a heading count disagrees with the names listed, the listed names are the reliable part.

**Summary:** `start.sh` opens ptyxis windows that run Gazebo/SLAM/Nav2 launch files (manual, explore, navigate, steer, stop modes) with companion save/view/stop/steer scripts and a DDS config, `Simulation/scripts` provides setup and preflight checks, `Documentation` holds three static notes, and `tests/` has 126 mocked-ROS tests (85 pass, 41 fail here because `Navigation/Camera/vision/detector.py` is missing).
