# SESSION CONTEXT: start here in a fresh chat

**Audience:** a new Claude Code session continuing this project with no memory of earlier chats.
**State as of:** 2026-10-22, ~04:30.
**Instruction for the new session:** read this file, then the files in §3, before acting.

---

## 1. One-paragraph summary

Swachh Boudhik Yantra is an autonomous indoor cleaning robot (university team, Q1 journal paper). We built and debugged a complete **simulation evaluation system**: ROS 2 Jazzy, Gazebo Harmonic, RTAB-Map SLAM, Nav2, a custom frontier explorer, ground truth from Gazebo, a recorder, an episode harness, offline metric modules, validity gates, per-metric health flags, statistics and a report generator. It measures the user's 14 metrics plus 15 extras.

**All code is written and tested:** 181 `vacuum_eval` tests and 7 explorer tests pass. **What remains is execution**, which **the user runs themselves**, on an **Ubuntu GPU workstation (NVIDIA A6000)**, following `docs/RUNBOOK.md`. Claude's job now: help when a step fails (from logs), verify each run's numbers, update the tracker, and send judgment calls to the Sonnet-only council.

## 2. The user and how to work with them

**Working style and checks:**
- Wants verified, honest answers, a recommendation rather than a survey, and short replies.
- Gets frustrated by surface-level work and by unverified claims.
- Has repeatedly asked: "will the metrics be shit?", "how close are we?", "what's the worst case?" Answer with numbers and caveats.
- Check before every claim. Never report something as done unless it was run or tested.

**Delegation:**
- **The main session orchestrates.** Implementation goes to **Sonnet subagents** (`model: sonnet`, usually `effort: low`) with an explicit EDIT-ONLY file list and no overlapping files. Second-order subagents: only Haiku or Sonnet.
- **An Opus agent** is used only for orchestrator or independent-critic roles, when asked.
- **Decisions** (non-mechanical judgment calls) go to the **LLM council, Sonnet only**. It is a local skill at `~/.claude/skills/llm-council/SKILL.md`: 5 advisors, 5 anonymised reviewers, and the chairman synthesis done in the main session. Artifacts are saved in `~/Swachh/council/<timestamp>/`. The plugin `hex/claude-council` could not be installed (`/plugin` is unavailable here).

**Long-running work:**
- Any command over about 2 minutes runs in the background with a wait-only timer: expected time plus a 25–50% buffer.
- **Timers never kill.** Claude itself inspects progress and decides what to do.
- Agents can hang silently. One Opus orchestrator sat "running" for 6.5 h doing nothing, so use activity-watchdog timers.

**Execution and safety:**
- The user now runs all simulations. Agents must not launch simulations unless the user asks again.
- Never ask for the sudo password. On the laptop, root is available without a password via `wsl.exe -d Ubuntu -u root -e bash -c "..."`.
- Ask before destructive actions.
- No git commits or pushes unless the user says so (see §8).
- Nothing goes to third-party AI providers.
- Use they/them for the user.

**Fixed decisions (never change without the user):**
- Global planner stays **Smac Hybrid DUBIN**; the user said no twice.
- Metric **#13, method comparison** (modified A*, B-A*, GA+NN), is **on hold**.
- **No physics fudge factors**: `wheel_separation_multiplier` stays 1.0, and odometry drift is measured.
- Swath width is 0.25 m; responsiveness deadline is 0.5 s.

## 3. Documents (read in this order)

| File | What it is |
|---|---|
| `docs/SESSION_CONTEXT.md` | This file |
| `docs/RUNBOOK.md` | Exact commands for everything left to execute (steps 0–10), including §11 for when a metric is bad or unmeasurable |
| `docs/METRICS_STATUS.md` | Live tracker per metric. Stages: Code, then Valid run, then Campaign. Update it after every run |
| `docs/REQUIREMENTS.md` | Detailed requirements R1–R9, environment, gotchas, pipeline map, hardware/perception backlog |
| `docs/FAILURE_MODES.md` | Per-metric failure modes, detection (health codes), the decision (fix+rerun / report / fallback / council), paper wording |
| `docs/specs/13_preregistration.md` | Frozen final definitions, validity rules, dev/test split, statistics, change log §13.6 |
| `docs/specs/14_critique_and_council_plan.md` | Every critique and council item with its status (items 1–21) |
| `docs/specs/README.md` and `00`–`12` | Implementation specs, each with dated decision sections |
| `docs/AUTONOMOUS_LOOP.md` | The (now paused) autonomous protocol and its log |
| `docs/METRICS_TO_BE_MEASURED.md` | Original what/why of the metrics. Its status column is historical |
| `council/2026-10-21-185011/`, `council/2026-10-22-031950/` | Council reports (upstream decisions; pilot-2 yaw jump) |

**Memory:** `~/.claude/projects/-home-hrishikesh-Swachh/memory/` holds notes on the subagent orchestration preference and the project state.

## 4. Machines

- **Laptop (dev so far):**
  - Hardware and OS: Windows 11, WSL2 Ubuntu 24.04, i7-1185G7 with 8 threads, Intel Iris Xe. Gazebo uses software rendering (llvmpipe).
  - Speed: true real-time factor about 0.29–0.45, so a 600 s-sim episode takes about 35–40 min.
  - Repo: `~/Swachh`. Workspace: `~/Swachh/Navigation/Simulation/vacuum_ws`. Results: `~/eval_runs/<experiment>/<world>/<method>/seed_<NNN>/`.
  - DDS socket buffers are 32 MB: `/etc/sysctl.d/90-ros2-dds.conf` plus a `/etc/wsl.conf` `[boot]` command. Check `rmem_max == 33554432` after any WSL restart.
- **GPU workstation (where the campaign will run):**
  - Expected hardware and OS: HP Z4 with NVIDIA A6000. Per `Navigation/Simulation/Documentation/software_stack.md` it runs Ubuntu 26.04 with Python 3.14, which is **unverified** and not the official Jazzy platform (24.04).
  - Setup: `Navigation/Simulation/scripts/setup_machine.sh [--dry-run]`, then `preflight.sh`.
  - **GPU flag:** native NVIDIA needs no `--gpu` flag; `--gpu 1` is only for the WSL D3D12 path.
  - **Interpreter fix:** all `python3.12` interpreter references were changed to `python3` on 2026-10-22 so it runs on Python 3.14.
- **Shell setup on either machine:**
  ```bash
  source /opt/ros/jazzy/setup.bash
  source ~/Swachh/Navigation/Simulation/vacuum_ws/install/setup.bash
  export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp CYCLONEDDS_URI=file://$HOME/Swachh/Navigation/cyclone_dds.xml ROS_DOMAIN_ID=0
  ```

## 5. What exists (pipeline, very short; details in REQUIREMENTS §4)

**Simulation:**
- `sim.launch.py` bakes the robot into the world at launch (needed for contact sensors) and supports `headless`, `odom_mode eval` (noise node in the odometry path), `render_gpu` and `embed_robot`.
- Ground truth: a Gazebo OdometryPublisher plugin feeds `ground_truth_node`.
- Nav2: polygon footprint, STVL obstacle layer plus a static layer in the local costmap, and BackUp before Spin in `explore.xml`.
- RTAB-Map: STMSize 10, MinInliers 10, Force3DoF, obstacle band 0.03–0.30 m.
- Explorer: goal snapping, the guards goal-at-robot / no-gain / min frontier size 0.5 m, and robot position taken from TF map→base_footprint.
- Worlds: 9 evaluation worlds plus 8 `avoid_*` scenarios, distinct textures per wall (`symmetric_hall` repeats on purpose), dev/test split in `worlds.yaml`.

**Episode tooling:**
- `run_episode`: gates G1–G7; methods `frontier`, `scripted_goals`, `responsiveness`; flags `--localization {auto,slam,amcl,gt}`, `--slot`, `--lean`, `--gpu`.
- `run_batch`: `--parallel K`, `--split`, `--confirm-test-split`, `--prebuild-gt`.
- Other tools: `compute_metrics`, `diagnose`, `check_lc_direction`, `plan_sample_size`, `aggregate`, `make_report`.

**Per-run quality checks:**
- **Validity:** `invalid` if image drop >10%, RTAB-Map gap >5 s, or <0.5 updates/s. Invalid episodes are excluded and counted.
- **Health:** `health_<metric>` with reasons:
  - OK, NA
  - LOW_N
  - UNMEASURABLE: NO_DATA, NO_EVENTS, INVALID_EPISODE, GT_MISSING, MAP_MISSING
  - SUSPECT: ODOM_CORRUPTED, FRAME_OFFSET, RANGE, NAV_GT_DIVERGENCE, LOW_RTF, LC_ROT_BIAS
  - BAD: BELOW_FLOOR
  
  Health never excludes anything.

## 6. Results so far (dev world apartment, seed 2; single episodes)

| Metric | Before fixes (tune3, 150 s) | pilot1 (210 s) | pilot2 (600 s, all fixes up to R1) |
|---|---|---|---|
| Valid (SLAM receiving images) | no | yes | yes (586 RTAB-Map updates) |
| Coverage explored | 76.7 % | 62.4 % | **90.4 %** |
| Map completeness | 63 % | 45.4 % | **74.8 %** |
| Floor cleaned (secondary) | 12.8 % | 3.3 % | 30.4 % |
| ATE, SLAM vs odometry | 0.71 vs 0.71 (no correction) | 0.066 vs 0.113 | 3.10 vs 2.99 overall; **0.119 vs 0.256 before the first collision (+53 %)** |
| Loop closures accepted | 0 | 2 | **181**, precision 43.6 %, median error 0.032 m / 5.24° |
| Nav success (GT) | 25 % of 8 | invalid (goal-loop bug) | **15.4 % of 26** (209 "no valid path") |
| Collisions | 2 | 0 | 3 (contact sensors) |

**Pilot 2's yaw jump (R1, council decision):** a real navigation failure, not a simulator artefact. The chair had decayed out of the costmap, a recovery Spin happened while in contact, and the wheels slipped, so odometry yaw went 125° off and RTAB-Map never recovered.
- **Fix applied:** local-costmap static layer plus BackUp before Spin.
- **Diagnostic keys** (`odom_corrupted_by_contact`, `ate_*_pre_corrupt`): a stratifier, never an exclusion.
- **Status:** not yet confirmed by runs (RUNBOOK step 2, with a stopping rule fixed in advance).

**Metric counts:**
- Valid-run stage: 10 yes, 2 partial (5 responsiveness, 11 loop closure), 1 no (9 avoidance success).
- Campaign stage: **0 of 13**.

## 7. Bugs found the hard way (do not reintroduce)

**Transport and simulator:**
- **DDS image drops** (208 KB socket buffer) silently made every "SLAM" result equal to odometry for two days. Gate G7 and the validity rules now catch this.
- **Gazebo `/stats` `real_time_factor`** reads 1.00 while the true rate is about 0.3. Only use d(sim_time)/d(wall).
- **Contact sensors** don't publish for runtime-spawned models; hence the robot is baked into the world at launch.
- **Textures** silently failed to load when the world moved to /tmp; paths are now rewritten to absolute.
- **`ros_gz_bridge`** drops entity names in `Pose_V`, hence the OdometryPublisher plugin for ground truth.

**Topics and wiring:**
- **`depthimage_to_laserscan` on Jazzy** subscribes to `depth` / `depth_camera_info`.
- **`diff_drive_controller`** only accepts stamped `/diff_drive_controller/cmd_vel`.
- **RTAB-Map topic names:** its topics had to be remapped to `/rtabmap/*`.
- **Explorer frames:** the explorer used the odometry frame for the robot position against map-frame goals.
- **Goal loop:** a snapped goal at the robot's own position "succeeded" 340 times.

**Metric and config bugs:**
- **Loop-closure direction:** the transform direction was backwards. Pilot 2 showed `loop_to_ref` is correct; it is now the configured default.
- **Swept area:** it over-counted by 20% when swath edges fell on cell centres (found by the oracle tests).
- **Calibration fudge:** `wheel_separation_multiplier` 0.945 overshot and was reverted. In-place rotation slip is about 6% (odom/GT yaw 0.94); arcs 2–4%.

**Shell gotchas:**
- **Never** `pkill -f '<pattern>'` with a pattern that appears in your own command line.
- Use `setsid`, and kill the process group.

## 8. Git state

Nothing from 2026-10-20 to 2026-10-22 is committed:
- 13 obsolete docs are staged as deleted (`git rm`).
- Many files are modified or new.
- The repo also carries old CRLF→LF-only diffs.

Before moving to the GPU workstation, the code must get there. Offer to **commit only the touched files** (not the CRLF noise) for the user to pull, or tell them to `rsync` without `build/install/log`. **Commit only if the user says so.**

## 9. What to do next (in the new session)

1. **Code transfer:** if the user hasn't moved the code yet, help with it (§8). Then help with setup on the workstation (`setup_machine.sh --dry-run`, then `preflight.sh`). Expect apt package gaps on Ubuntu 26.04 (STVL, rtabmap, gz_ros2_control). The fallback is a 24.04 Docker container with NVIDIA passthrough.
2. **Each run folder the user sends:**
   1. Run `compute_metrics` if needed, then `diagnose`.
   2. Read `summary.json`: validity plus `health_*`.
   3. **Verify:** the numbers are accurate (spot-recompute from the raw CSVs), the method was right, and judge whether a bad value is a fixable artefact or a genuine result (FAILURE_MODES.md). Use an independent Sonnet subagent or the council for judgment calls.
   4. Update `METRICS_STATUS.md`, and log decisions in `specs/14` or `13_preregistration.md` §13.6.
3. **Never-run-live modes:** expect failures in ground-truth localization (`--localization gt` with the map_server lifecycle wrapper), the `avoid_*` worlds (including `dynamic_mover` and the extra bridge), loaded responsiveness, and parallel slots. Fix through Sonnet subagents from the logs.
4. **Open council items:**
   - Loop-closure rotation bias of about 5.2° against the 5° tolerance.
   - What to do if contact corruption recurs after R1 (axle offset / contact-aware recovery).
   - Campaign size if it exceeds about 48 h.
5. **Before the test-split campaign (RUNBOOK step 9):** freeze `13_preregistration.md` and record the commit. After that, no tuning.

## 10. Worst case (told to the user)

**Most likely problems:**
- Jazzy doesn't install cleanly on Ubuntu 26.04: 1–2 days, Docker fallback.
- Navigation success stays low because of the fixed DUBIN planner: report it honestly.
- Contact corruption recurs: about half a day of fixing, or report with and without.
- Never-run modes need fixes: 1–3 h each.
- Loop closures stay weak: report as low or unmeasurable, with the reason.

**Absolute worst:** about 1 extra week, and honest but unflattering navigation and SLAM numbers. Coverage, pre-collision ATE, map completeness, collisions and responsiveness should still hold.

**What the pipeline guards against:** it will not silently produce invalid numbers, because of the validity gates, the health flags and the oracle tests.
