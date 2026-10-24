# HANDOFF FOR ANTIGRAVITY: run the Swachh simulation evaluation on the Ubuntu GPU workstation

**Audience:** the Antigravity agent working on the user's Ubuntu workstation with an NVIDIA GPU (A6000). It has no prior context.
**Prepared:** 2026-10-24, by the Claude Code session that built this system.
**Repo:** `https://github.com/swachhbaudhikkayantra/Swachh`, branch `main`. Everything you need is committed.

Read this whole file before running anything. Deeper references:
- `docs/RUNBOOK.md`: the commands.
- `docs/FAILURE_MODES.md`: what to do when a metric is bad.
- `docs/REQUIREMENTS.md` and `docs/SESSION_CONTEXT.md`: full background.
- `docs/specs/`: how each metric is computed.
- `docs/specs/13_preregistration.md`: the frozen definitions.

---

## 1. Your mission

Execute the remaining evaluation runs on this GPU machine, make sure every run is valid, record the results, and produce the final metric report for a Q1 journal paper about an autonomous cleaning robot.

**All code is written and unit-tested:** 181 `vacuum_eval` tests and 7 explorer tests pass. Your job is execution, plus small runtime fixes when something fails on this machine.

You are done when every metric in `docs/METRICS_STATUS.md` (except #13, which is on hold) has reached stage **Campaign**, and `docs/RUNBOOK.md` step 10 has produced `results.md`, figures and a status update.

## 2. Project in brief

- **Robot:** 0.30 × 0.25 m differential-drive cleaning robot; its only sensor is a simulated Intel RealSense D435i RGB-D camera.
- **Stack:** ROS 2 Jazzy, Gazebo Harmonic (gz sim 8), RTAB-Map SLAM (RGB-D + wheel odometry), Nav2 (global planner Smac Hybrid-A* DUBIN, MPPI controller, spatio-temporal voxel layer on a depth-derived scan), and a custom frontier explorer.
- **Evaluation system** (`Navigation/Simulation/vacuum_ws/src/vacuum_eval`):
  - ground truth from a Gazebo odometry plugin;
  - a recorder node that writes CSVs;
  - an episode harness with readiness gates G1–G7;
  - offline metric modules;
  - validity gates;
  - per-metric health flags;
  - a diagnosis tool;
  - statistics (episode-level cluster bootstrap, Holm correction);
  - a report generator.
- **The 14 metrics** (definitions in `docs/specs/13_preregistration.md`):
  1. coverage
  2. steps per episode
  3. collisions
  4. % obstacle avoidance
  5. responsiveness (wall-clock controller latency)
  6. ATE
  7. RPE
  8. map completeness
  9. avoidance trial success
  10. navigation success
  11. loop-closure precision and recall
  12. path length ratio
  13. method comparison: **ON HOLD**, do not implement
  14. cleaning efficiency (secondary)
  
  Plus 15 extras (A1–A15).
- **Results so far** came from a WSL laptop (software rendering, about 0.3× real time) and are **development only; do not pool them with your runs**:
  - The pipeline is valid: SLAM receives images and corrects drift (53% better ATE than odometry before the first collision).
  - Coverage reached 90%, map completeness 75%, and 181 loop closures were accepted.
  - Navigation success is low (15%).
  - A collision-induced odometry failure was found and a fix applied (§7). The fix is not yet confirmed by a run.

## 3. Hard rules (do not break; ask the user if a rule blocks you)

**Fixed decisions:**
- Do not change the **global planner** (Smac Hybrid DUBIN). The user has refused this twice.
- Do not implement metric **#13** (method comparison) or any baseline or coverage planner.
- **No physics fudge factors.** `wheel_separation_multiplier` stays 1.0, and odometry drift is measured, not tuned away.

**Thresholds and the test split:**
- Do not change metric definitions, tolerances or thresholds in `vacuum_eval/config/eval_defaults.yaml`, and do not change the dev/test split in `worlds.yaml`.
- **Dev vs test split:** tuning is allowed only on dev worlds and seeds (RUNBOOK steps 2–7). Once the **test-split campaign** (RUNBOOK step 9) starts, nothing may be changed. Any later change needs the user's approval, a row in `docs/specs/13_preregistration.md` §13.6, and a rerun of affected test runs.

**Runs and reruns:**
- **Never rerun an episode to get a better number.** Rerun once, with the same seed, only for an infrastructure fault (crashed node, image drops, missing map). Report both attempts.
- Health flags and "bad" numbers **never exclude** an episode. Only `status: invalid` is excluded from statistics, and it is still counted and reported.
- **Do not mix machines or rendering modes in one experiment:** never laptop with workstation runs, or `--gpu 1` with `--gpu 0`.

**Processes:**
- **Never use `pkill -f <pattern>`** where the pattern also appears in your own shell command; it kills your own shell. To stop a run, send SIGINT to the harness PID (`kill -INT <pid>`) or kill its process group.
- **Long jobs:** anything over about 2 minutes runs in the background (`nohup ... > log 2>&1 &`). Note the PID, poll the log and output files, and set yourself a deadline of expected time + 40%. **A deadline never auto-kills.** Inspect progress (§6) and then decide.

**Git and system:**
- Git: do not push or force-push without asking the user. Committing doc or status updates locally is fine.
- Nothing destructive outside `~/eval_runs` and `/tmp`. Ask before system changes beyond §4.

## 4. Machine setup (once)

```bash
git clone https://github.com/swachhbaudhikkayantra/Swachh.git ~/Swachh      # or: cd ~/Swachh && git pull
. /etc/os-release && echo "$PRETTY_NAME"; nvidia-smi; nproc; free -g; df -h ~
```

**Ubuntu version matters.** ROS 2 Jazzy binaries officially target **Ubuntu 24.04**. The project notes say this workstation may run **Ubuntu 26.04** with Python 3.14, which is unverified.
- **24.04:** follow the ROS Jazzy install guide (https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html) if `/opt/ros/jazzy` is missing, then run the setup script.
- **Newer Ubuntu, Jazzy already present:** try the setup script. If apt packages are missing (often `ros-jazzy-spatio-temporal-voxel-layer`, `ros-jazzy-rtabmap-ros` or `ros-jazzy-gz-ros2-control`), **stop and tell the user**. The recommended fallback is an **Ubuntu 24.04 Docker container with NVIDIA GPU passthrough** (nvidia-container-toolkit), with the repo mounted and the same setup run inside. Do not build large stacks from source without asking.

```bash
bash ~/Swachh/Navigation/Simulation/scripts/setup_machine.sh --dry-run    # read what it will do
bash ~/Swachh/Navigation/Simulation/scripts/setup_machine.sh              # apt (sudo prompts), DDS sysctl, ~/.bashrc, rosdep, build, tests
```

The setup script does five things:
- installs the needed apt packages;
- writes `/etc/sysctl.d/90-ros2-dds.conf` (socket buffers 32 MB) and applies it;
- adds the environment lines to `~/.bashrc`;
- runs `rosdep` and `colcon build --symlink-install`;
- runs the unit tests (they must pass).

**Socket buffers are critical.** With the default 208 KB buffers, camera images are silently dropped between processes, RTAB-Map stops updating, and "SLAM" results quietly become odometry results. This cost two days on the laptop. `preflight.sh` checks for it.

**Display or headless.**
- The robot's camera needs rendering. If you run inside the workstation's desktop session (`echo $DISPLAY` is non-empty), nothing extra is needed: the NVIDIA GPU renders natively.
- If you run over SSH with no display, set `export VACUUM_GZ_HEADLESS_RENDERING=1` in every terminal, before any run. That makes Gazebo use `--headless-rendering`, with EGL on NVIDIA.
- **Check it** with the first episode: gates G6 and G7 must pass, and `img_drop_pct` must be about 0.
- Leave `--gpu` at 0 on this machine. That flag is only for WSL's Intel D3D12 path; native NVIDIA needs nothing.

**Every new terminal:**
```bash
source /opt/ros/jazzy/setup.bash
source ~/Swachh/Navigation/Simulation/vacuum_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp CYCLONEDDS_URI=file://$HOME/Swachh/Navigation/cyclone_dds.xml ROS_DOMAIN_ID=0
# export VACUUM_GZ_HEADLESS_RENDERING=1     # only if there is no display (SSH)
cd ~/Swachh/Navigation/Simulation/vacuum_ws/src/vacuum_eval
bash ~/Swachh/Navigation/Simulation/scripts/preflight.sh        # every line PASS before starting; note the suggested --parallel
post() { python3 -m vacuum_eval.compute_metrics "$1" && python3 -m vacuum_eval.diagnose "$1" --png "$1/diagnose.png"; }
```

**Speed estimate (unmeasured):** with the GPU, the simulation should run near real time, capped at 1.0 by the world files (do not raise the cap; it would change results). So a 600 s episode takes about 11–15 min. Check the true rate in each run's `rtf.csv`, which computes sim-time / wall-time. **Do not trust Gazebo's `/stats` `real_time_factor` field;** it read 1.00 when the true rate was 0.3.

## 5. Execution plan (follow `docs/RUNBOOK.md` exactly; summary here)

Run steps in order. Use **one simulation at a time** until step 9.

| Step | What | Runs | Accept if |
|---|---|---|---|
| 2 | R1 confirmation: apartment, frontier, seeds 2 and 1, 600 s | 2 | `episode_valid` true, `odom_corrupted_by_contact`=0, `ate_improvement_pct`>0, few collisions. **Stopping rule (pre-registered):** if either run has the corruption flag, or a recovery Spin happened while in contact (compare "spin" lines in `logs/explore_stack.log` with `collisions_raw.csv` timestamps), **stop and report to the user**. Do not start inventing fixes |
| 3 | Loop-closure direction check (no simulation) | 0 | `check_lc_direction` names `loop_to_ref` (already the configured default) |
| 4 | R3 scripted navigation, apartment, `--localization gt`/`amcl`/`slam` × seeds 1–2 | 6 | Valid runs; compare `nav_success_gt_pct` across the 3 localization modes. **`gt` mode has never run live**; expect to debug the map_server start-up |
| 5 | R4 responsiveness, `--stack bare` and `loaded` | 2 | `resp_definition`=`wall_clock_controller_latency`, `lat_cmd_motion_ms_mean` present, `wall_latency_s` filled |
| 6 | R5 avoidance scenarios (dev): `avoid_head_on`, `avoid_cluster`, `avoid_dynamic_cross` × 3 | 9 | **Never launched before: run one alone first.** `trial_success` present, `collision_source`=contact when contacts happen, `dyn_obstacles.csv` filled for the dynamic world |
| 7 | R6 loop closures, apartment 900 s, odom noise on | 1 | `lc_n_accepted`>0, precision/recall computed |
| 8 | R7 campaign sizing (`plan_sample_size`, no simulation) | 0 | Give the user the outputs and the resulting wall-time estimate. **The user approves campaign size** before step 9 |
| 9 | R8 test-split campaign (`run_batch --split test --confirm-test-split`), all 4 `final_*.yaml` | many | Before starting: confirm with the user that `13_preregistration.md` is frozen. Use `--parallel` per preflight (start with 2, check each episode's `rtf_true_mean` stays near 1 and validity passes, then raise). `run_batch` resumes skipped/finished runs |
| 10 | R9 aggregate + `make_report` | 0 | `results.md`, figures, `metrics_status_update.md` |

**Parallel runs** (step 9 only): `run_batch --parallel K` gives each slot its own ROS domain and Gazebo partition. This has **never run live**. Start with K=2 on two cheap episodes and check:
- the two runs don't see each other's topics: each run's `trajectory.csv` must look like a single robot;
- both are valid.

Only then raise K.

## 6. Running long jobs and monitoring

```bash
nohup python3 -m vacuum_eval.run_episode --experiment r1confirm --world apartment --method frontier --seed 2 --odom-noise 0 --headless 1 --timeout-sim-sec 600 > ~/r1_s2.log 2>&1 &
echo $!          # harness PID; note it
```

**Progress, read-only:**
- `tail ~/r1_s2.log`: gate lines G1–G7, then the final line `<run_dir> <status> <end_reason> <sim_sec>`.
- `tail -1 <run_dir>/trajectory.csv`: the first column is sim time.
- `tail -3 <run_dir>/rtf.csv`: true real-time factor.
- `<run_dir>/events.csv`.
- `<run_dir>/logs/*.log`.

**To stop a run:** `kill -INT <harness PID>`. The harness saves data, computes metrics and cleans up only its own process groups.

**Before every launch:** `pgrep -fa "gz sim|ruby"` must be empty, unless a parallel batch is running.

## 7. Known issues and history (so you recognise them)

**Pilot-2 failure mode (the fix is applied; step 2 confirms it).**
- **The sequence:** a chair decayed out of the obstacle layer. MPPI drove into it. The recovery Spin rotated the robot while it was pressed against the chair, and the wheels slipped. Odometry yaw jumped about 125°, and RTAB-Map never recovered.
- **Fix:** the local costmap now has the SLAM map as a static layer, and the explore behaviour tree runs BackUp before Spin.
- **Diagnostic keys:** `odom_corrupted_by_contact`, `contact_odom_yaw_excess_deg`, `ate_*_pre_corrupt`.

**Other known items:**
- **Navigation success is low** (15%, many "no valid path"). This is likely the DUBIN planner in tight rooms; the planner is fixed by the user. Step 4 (gt vs amcl vs slam) separates localization from planning. Report it, do not "fix" the planner.
- **Axle offset:** the axle sits 8 cm behind `base_footprint`. This is a documented limitation; do not change the robot model.
- **Loop-closure rotation:** the median error is about 5.2° against a 5° tolerance, flagged `SUSPECT: LC_ROT_BIAS`. It is an open question for the user; do not change the tolerance.
- **Camera blind zone:** obstacles nearer than 0.2 m can't be seen (depth minimum range). Genuine; report it.
- **Collision source:** contact sensors work because the robot is baked into the world at launch (`embed_robot:=true`, the default). If `collision_source` says `geometry` while contacts clearly happened, check that the contact topics are bridged.
- **Pre-fix runs:** `smoke*`/`tune*` runs on the laptop predate the fixes. Never use them.

## 8. Verify every run (do this before moving on)

For each run folder:
1. Run `post <run_dir>`. That runs `compute_metrics` (writes `summary.json`) and `diagnose` (time split, goals, log failure counts, stuck spots, health table).
2. **Validity:** `episode_valid` true, `img_drop_pct` < 10, `rtabmap_max_gap_s` < 5, `rtf_true_mean` plausible. If not valid, check whether it's an infrastructure fault; if so, rerun once.
3. **Health:** read `health_<metric>` and `health_<metric>_reasons`:
   - OK, NA
   - LOW_N
   - UNMEASURABLE: NO_DATA, NO_EVENTS, INVALID_EPISODE, GT_MISSING, MAP_MISSING
   - SUSPECT: ODOM_CORRUPTED, FRAME_OFFSET, RANGE, NAV_GT_DIVERGENCE, LOW_RTF, LC_ROT_BIAS
   - BAD: BELOW_FLOOR
   
   For any non-OK status, follow that metric's table in `docs/FAILURE_MODES.md`: fix and rerun (artefact or bug), report (genuine result), fallback key, or ask the user.
4. **Spot-check accuracy:** recompute one headline number independently from the raw CSVs. For example, GT path length from `trajectory.csv` against `distance_gt_m`, or the collision count from `collisions_raw.csv`. Expect agreement within 2%.
5. **Update `docs/METRICS_STATUS.md`:** stage and value per metric. Append a dated entry to `docs/EXECUTION_LOG.md` (create it): runs, validity, key numbers, issues, decisions.

**Unit tests after any code fix:** `cd ~/Swachh/Navigation/Simulation/vacuum_ws/src/vacuum_eval && python3 -m pytest test -q -p no:cacheprovider` must stay fully green. Rebuild with `colcon build --symlink-install` after editing the `vacuum_exploration` package, which installs copies.

## 9. When something fails

**Steps:**
1. Read the harness log (which gate failed), then `<run_dir>/logs/*.log` and `<run_dir>/events.csv`.
2. **Bring-up gate failures:**
   - **G1 clock:** Gazebo didn't start (rendering or display).
   - **G2 controllers:** gz_ros2_control or the robot description.
   - **G3 GT odometry:** the bridge.
   - **G4 TF / G6 map / G7 RTAB-Map alive:** SLAM inputs. Check images and socket buffers.
   - **G5 Nav2.**
3. **Fixes:** keep them minimal and local, run the unit tests, and document them in `docs/EXECUTION_LOG.md` with the cause.
4. **Stop and ask the user if a fix would change the measured system:**
   - robot or sensor model, world geometry;
   - planner or controller choice, Nav2/RTAB-Map parameters;
   - metric definitions or thresholds;
   - or if it is a judgment call (for example "is this a real result or an artefact?").
   
   Before the test split, configuration tuning is allowed only on dev worlds, and only with the user's OK.

**Where things live:**
- launch: `vacuum_bringup/launch/sim.launch.py`, `vacuum_exploration/launch/exploration.launch.py`, `vacuum_nav2/launch/*.py`
- configs: `vacuum_nav2/config/nav2_params.yaml`, `vacuum_slam/config/rtabmap.yaml`, `vacuum_controller/config/controllers.yaml`, `vacuum_eval/config/*.yaml`
- harness: `vacuum_eval/vacuum_eval/run_episode.py` and `run_batch.py`
- metrics: `vacuum_eval/vacuum_eval/metrics/*.py`

## 10. What to report to the user

After each RUNBOOK step, report briefly:
- runs done and their validity;
- headline numbers with health status;
- anything that failed and how it was fixed;
- any decision needed from the user;
- wall time used, and the estimate for the rest.

At the end, report `~/eval_runs/<exp>/report/results.md` for each experiment, the updated `METRICS_STATUS.md`, and the list of every deviation from `13_preregistration.md`. Unflattering results are reported as measured; the paper reports failures too.
