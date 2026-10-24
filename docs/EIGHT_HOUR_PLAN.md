# EIGHT-HOUR PLAN: measure every metric in one 8-hour session on a GPU PC

**Audience:** the agent (or person) running the evaluation on a remote Ubuntu PC with an NVIDIA GPU (a friend's machine, RTX 50-series), reached over SSH.
**Prepared:** 2026-10-24, by the Claude Code session that built the system.
**Goal:** in **8 hours of wall-clock time after machine setup**, produce valid measurements of **all 13 active metrics** (metric #13, method comparison, is on hold) on the pre-registered **test split**, plus the final report. The reduced scope is shown in §2.

**Companion documents:**
- `docs/ANTIGRAVITY_HANDOFF.md`: hard rules, setup, verification and failure handling, all in more depth. Read §3 (rules) and §4 (setup) there **before starting the clock**.
- `docs/FAILURE_MODES.md`: what to do when a metric is bad or unmeasurable.
- `docs/RUNBOOK.md`: the full, non-reduced procedure. Its steps 2–10 are replaced by this plan for this session.
- `docs/SESSION_CONTEXT.md`: full project background.

---

## 0. The plan at a glance

| Clock | Phase | What | Wall time (2 parallel / serial) |
|---|---|---|---|
| T−setup | 0 | Machine setup, **not counted** (§1). Must be finished, with preflight all PASS, before T+0 | about 1–2 h, outside the 8 h |
| T+0:00 | A0 | Open the tmux session, preflight, environment | 10 min |
| T+0:10 | A | Dev check: every mode works on this machine (8 short episodes, serial) | about 1 h 50 min (includes 45 min fix budget) |
| T+2:00 | B | Freeze: pre-registration change, git record, GT prebuild, parallel smoke test | 15 min |
| T+2:15 | C | Test campaign: 41 episodes (responsiveness, avoidance, exploration, navigation) | **about 3 h 45 min** / about 6 h 40 min |
| T+6:00 | D | Aggregate, report, verify, update tracker | 45 min |
| T+6:45 | E | Buffer | 1 h 15 min |

**Serial fallback:** if 2 parallel episodes are not possible (§4, gate G-SPEED), the cuts in §7 keep the total under 8 h.

## 1. Before the clock starts (setup; not part of the 8 h)

Do all of this first. If any step fails, fix it before starting.

1. **Machine check:**
   ```bash
   . /etc/os-release && echo "$PRETTY_NAME"     # 24.04 recommended; other versions: see ANTIGRAVITY_HANDOFF §4
   nvidia-smi                                    # RTX 50-series needs driver >= 570
   nproc; free -g; df -h ~                       # >= 8 cores and 16 GB for --parallel 2; >= 30 GB free disk
   ```
2. **Repo:** `git clone https://github.com/swachhbaudhikkayantra/Swachh.git ~/Swachh`, or `cd ~/Swachh && git pull` (branch `main`).
3. **Setup script:** run `bash ~/Swachh/Navigation/Simulation/scripts/setup_machine.sh --dry-run`, then the same without `--dry-run`. It installs the apt packages, writes the DDS socket-buffer sysctl, adds `~/.bashrc` lines, runs rosdep, builds the workspace and runs the unit tests. **All tests must pass.** Last known count: 181 `vacuum_eval` tests plus 7 explorer tests.
4. **Power:** disable sleep and suspend (desktop power settings, or `sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target`, with the owner's consent).
5. **Display:** if no desktop session is logged in on the PC (pure SSH), every terminal must `export VACUUM_GZ_HEADLESS_RENDERING=1`. That makes Gazebo render the camera with EGL on the NVIDIA GPU.
6. **tmux:** `sudo apt install tmux` if missing. All long work runs inside `tmux new -s eval`, so a dropped SSH connection doesn't kill runs. Reattach with `tmux attach -t eval`.

## 2. Scope: what is measured, what is dropped

| Campaign file (`vacuum_eval/config/campaigns/`) | Design | Episodes | Metrics it provides |
|---|---|---|---|
| `quick_exploration.yaml` | office, multi_room_loop, maze_dead_ends × seeds 101–105; frontier explorer; **odometry noise on**; 450 s sim | 15 | 1 coverage, 2 steps, 3 collisions, 4 avoidance %, 6 ATE, 7 RPE, 8 map completeness, 11 loop closure, 14 cleaning efficiency, extras A1–A12 |
| `quick_navigation.yaml` | office, two_rooms_door, maze_dead_ends × `random20` goals × seeds 101–104; GT nav map; 900 s cap | 12 (about 240 goals) | 10 nav success, 12 path length ratio, 2 steps, 3/4 collisions and avoidance, A6–A9, A14 AMCL error |
| `quick_avoidance.yaml` | avoid_u_trap (static) + avoid_dynamic_sudden (moving obstacle) × seeds 101–105 | 10 | 9 avoidance trial success, 3 collisions, 4 avoidance %, A5 clearance |
| `quick_responsiveness.yaml` | office, `bare` + `loaded` stack × seeds 101–102 | 4 | 5 responsiveness (wall-clock controller latency) |
| **Total** | | **41** | **all 13 active metrics** |

All four files are written and pass `run_batch --dry-run --split test`.

**Dropped from the full pre-registered campaign (266 episodes, about 55 h):**
- **Noise-off condition:** A15 noise robustness is not measured. Every exploration run uses realistic odometry noise.
- **Worlds:** corridor and symmetric_hall are out of exploration; corridor and multi_room_loop are out of navigation. The `long_range` goal list is out.
- **Avoidance:** avoid_narrow_gap and avoid_dead_end are out.
- **Seeds:** 5 per configuration (4 for navigation) instead of 10. A13 repeatability is reported from those.
- **Dev requirement R6** (separate 900 s loop-closure run) is skipped. Loop closures are measured inside `quick_exploration`.
- **R7 sample-size planning** is skipped. Episode counts are set by the wall-time budget, and this is stated in the pre-registration.

**Statistical consequence:**
- **Per-world intervals are wide:** about ±15–20 percentage points on success rates.
- **Headline numbers** are therefore **pooled across worlds**, with episode-level cluster-bootstrap 95% CIs. Navigation pools about 240 goals (about ±8 pp).
- **Paper framing:** a focused evaluation, with the reduced scope stated as a limitation.

## 3. Rules that apply all session (short version; full list in ANTIGRAVITY_HANDOFF.md §3)

**Fixed decisions:**
- Do not change the global planner (Smac Hybrid DUBIN), the robot or sensor model, the world geometry, metric definitions, or thresholds (`eval_defaults.yaml`).
- No physics fudge factors.
- Do not implement method comparison (#13).

**Changes:**
- Allowed in Phase A only: minimal runtime fixes for things that **crash or fail to start**. Each fix needs the unit tests to pass and an entry in `docs/EXECUTION_LOG.md`.
- **After Phase B starts nothing may change.** Changing a parameter to get better numbers is never allowed.

**Reruns and exclusions:**
- **Rerun policy:** an episode is rerun **once, with the same seed, only for an infrastructure fault**: crashed node, image drops (`status: invalid`), missing map or bag. Both attempts are reported. Never rerun for a better number.
- **Nothing is excluded except `status: invalid`.** Health flags (BAD/SUSPECT/LOW_N/UNMEASURABLE) are diagnosis and reporting aids, never exclusions.

**Processes:**
- Never `pkill -f <pattern>` where the pattern is also in your own command line. Stop a run with `kill -INT <harness PID>`.
- Long jobs run in tmux. Monitor them (§8) at the times given. A timer or deadline never auto-kills anything.
- Do not push to GitHub without the user's OK. Local commits of docs and status are fine.

## 4. Phase A0 (T+0:00–0:10): session start

```bash
tmux new -s eval            # all later commands run inside this session (create more windows with Ctrl-b c)
source /opt/ros/jazzy/setup.bash
source ~/Swachh/Navigation/Simulation/vacuum_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp CYCLONEDDS_URI=file://$HOME/Swachh/Navigation/cyclone_dds.xml ROS_DOMAIN_ID=0
# export VACUUM_GZ_HEADLESS_RENDERING=1          # ONLY if no desktop session/display (SSH-only)
cd ~/Swachh/Navigation/Simulation/vacuum_ws/src/vacuum_eval
bash ~/Swachh/Navigation/Simulation/scripts/preflight.sh
post() { python3 -m vacuum_eval.compute_metrics "$1" && python3 -m vacuum_eval.diagnose "$1" --png "$1/diagnose.png"; }
date | tee -a ~/Swachh/docs/EXECUTION_LOG.md    # start time; create the log if absent
```

Preflight must show PASS for:
- `rmem_max=33554432`
- no stray gz/ruby processes
- disk ≥ 20 GB free
- ROS environment sourced
- RMW set to CycloneDDS
- workspace built
- CycloneDDS minimum buffer ≥ 16 MB
- renderer is NVIDIA, not llvmpipe

Write down the `--parallel` value it suggests.

## 5. Phase A (T+0:10–2:00): dev check, every mode once (serial, dev split)

All runs here use **dev worlds and dev seeds**, so they never touch the test split. Run them **one at a time**. After each one, run `post <run_dir>` and the listed checks; the run folder is printed on the harness's last line.

**Time budget:** about 65 min of episodes plus 45 min for fixes. **Per-failure time box: 20 min.** If a mode can't be fixed within 20 min, see §7, row "mode broken".

### A1 (T+0:10): R1 confirmation, seed 2, plus the speed benchmark (about 13 min)
```bash
python3 -m vacuum_eval.run_episode --experiment dev8h_r1 --world apartment --method frontier --seed 2 --odom-noise 0 --headless 1 --timeout-sim-sec 600
post ~/eval_runs/dev8h_r1/apartment/frontier/seed_002
```
**Checks** (`summary.json`):
- `episode_valid` true and `img_drop_pct` < 10.
- `rtabmap_updates` ≈ `episode_sim_sec`.
- `odom_corrupted_by_contact` = 0.
- `ate_improvement_pct` > 0.
- `n_goals` reasonable (≤ about 40).

**Gate G-SPEED** (read `rtf_true_mean`):
- **≥ 0.75:** the plan holds. Phase C uses `--parallel 2` if preflight suggested ≥ 2; otherwise use the serial variant (§7).
- **0.45–0.75:** serial variant (§7). Expect about 8 h total, with the buffer used.
- **< 0.45:** the GPU isn't being used. Check that preflight's renderer line says NVIDIA, and that `VACUUM_GZ_HEADLESS_RENDERING` is set when there's no display. Fix this before going on; it is the most likely cause of a blown schedule.

### A2 (T+0:25): R1 confirmation, seed 1 (about 13 min)
```bash
python3 -m vacuum_eval.run_episode --experiment dev8h_r1 --world apartment --method frontier --seed 1 --odom-noise 0 --headless 1 --timeout-sim-sec 600
post ~/eval_runs/dev8h_r1/apartment/frontier/seed_001
python3 -m vacuum_eval.check_lc_direction ~/eval_runs/dev8h_r1/apartment/frontier/seed_00*
```
**Checks:**
- Same as A1.
- `check_lc_direction` should name `loop_to_ref`, the configured default. If it is ambiguous only because the rotation median is just above 5° (seen before, flagged LC_ROT_BIAS), note it and continue.

**R1 stopping rule (pre-registered), time-boxed version.** If **either** run has `odom_corrupted_by_contact = 1`, or a recovery Spin happened while in contact: write it in the execution log, **notify the user, and continue the plan**. Don't attempt a fix inside the 8 h. In the campaign the issue is handled by the stratifier keys `odom_corrupted_by_contact` and `ate_*_pre_corrupt`, and reported as a limitation. To check for spin-in-contact, compare the times of "spin" lines in `logs/explore_stack.log` with `collisions_raw.csv`.

### A3 (T+0:40): navigation with ground-truth localization (about 15 min)
This mode has **never run live**. It uses plain Nav2, a map_server lifecycle wrapper serving the exported GT map, and `gt_localization_node`.
```bash
python3 -m vacuum_eval.run_episode --experiment dev8h_nav --world apartment --method scripted_goals --goal-list random20 --nav-map gt --localization gt --seed 1 --odom-noise 0 --headless 1 --timeout-sim-sec 900
post ~/eval_runs/dev8h_nav/apartment/scripted_goals*/seed_001
```
**Checks:**
- Bring-up gates pass (G5 Nav2, G4 TF, map server).
- `localization_mode` = gt in `run_meta.yaml`.
- `nav_goals_total` > 0.
- `nav_success_gt_pct` present.

**If it fails to start:** read `logs/*.log` for the map_server lifecycle or `gt_localization` errors. The time box applies.

### A4 (T+0:55): navigation with SLAM localization (about 15 min)
```bash
python3 -m vacuum_eval.run_episode --experiment dev8h_nav --world apartment --method scripted_goals --goal-list random20 --nav-map gt --localization slam --seed 1 --odom-noise 0 --headless 1 --timeout-sim-sec 900
post ~/eval_runs/dev8h_nav/apartment/scripted_goals*/seed_001
```
The run folder name may include the localization mode; use the path printed by the harness.

**Checks:** valid, with `nav_success_gt_pct` present.

**Record** the gt vs slam nav success in the log. This separates "planner fails" from "localization fails", which matters for interpreting the low (about 15%) nav success seen on the laptop.

### A5 (T+1:10): responsiveness, bare and loaded (about 11 min)
```bash
python3 -m vacuum_eval.run_episode --experiment dev8h_resp --world apartment --method responsiveness --stack bare   --seed 1 --headless 1
python3 -m vacuum_eval.run_episode --experiment dev8h_resp --world apartment --method responsiveness --stack loaded --seed 1 --headless 1
for d in ~/eval_runs/dev8h_resp/apartment/*/seed_001; do post "$d"; done
```
**Checks:**
- `resp_definition` = `wall_clock_controller_latency`.
- `lat_cmd_motion_ms_mean` and `lat_stop_ms_mean` present.
- `wall_latency_s` column filled in `responsiveness_events.csv`.
- `loaded` has never run live.

### A6 (T+1:20): avoidance, one static and one dynamic scenario (about 9 min)
These worlds have never been launched.
```bash
python3 -m vacuum_eval.run_episode --experiment dev8h_avoid --world avoid_head_on --method scripted_goals --goal-list scenario --nav-map gt --seed 1 --headless 1
python3 -m vacuum_eval.run_episode --experiment dev8h_avoid --world avoid_dynamic_cross --method scripted_goals --goal-list scenario --nav-map gt --seed 1 --headless 1
for d in ~/eval_runs/dev8h_avoid/*/*/seed_001; do post "$d"; done
```
**Checks:**
- `trial_success` present.
- `collision_source` = contact if contacts happened.
- `dyn_obstacles.csv` has rows for the dynamic world, meaning the box moved: positions change over time.
- The dynamic world needs the extra bridge (`gz_bridge_dynamic.yaml`) and `dynamic_mover`. The harness starts both automatically for worlds with dynamic obstacles.

### A7 (T+1:30–2:00): fix buffer and Phase A record
- Use any remaining time for fixes, each with unit tests passing (`python3 -m pytest test -q -p no:cacheprovider`) and an EXECUTION_LOG entry.
- **Write the Phase A summary** in `docs/EXECUTION_LOG.md`: each run's validity and key numbers, RTF, the parallel decision, and every fix with its cause.
- **Update `docs/METRICS_STATUS.md`** (stage "Valid run") for the metrics now measured on this machine.

## 6. Phase B (T+2:00–2:15): freeze

1. **Pre-registration change:** append to the change-log table in `docs/specs/13_preregistration.md` §13.6, with today's date:
   ```
   | <date> | 8-hour reduced test campaign (config/campaigns/quick_*.yaml) replaces final_*.yaml for this run: exploration 3 worlds (office, multi_room_loop, maze_dead_ends) x seeds 101-105, odom noise on, 450 s; navigation 3 worlds (office, two_rooms_door, maze_dead_ends) x random20 x seeds 101-104, 900 s; avoidance avoid_u_trap + avoid_dynamic_sudden x seeds 101-105; responsiveness office bare+loaded x seeds 101-102. Dropped: noise-off condition (A15 not measured), long_range goals, corridor/symmetric_hall/two_rooms_door from exploration, corridor/multi_room_loop from navigation, avoid_narrow_gap/avoid_dead_end, R6 dev loop run, R7 sample-size planning. Headline CIs pooled across worlds (cluster bootstrap); per-world CIs reported but wide. | Wall-time budget of 8 h on a single GPU PC; decided before any test-split run. |
   ```
   If the serial variant (§7) is used, add its cuts to the same row.
2. **Record the code state:** `cd ~/Swachh && git add -A && git commit -m "Freeze for 8-hour test campaign" && git rev-parse HEAD`, and write the hash in the execution log. Commit locally only; push only if the user agrees. `run_batch` also writes the git commit and the campaign hash into each experiment's `batch_manifest.json`.
3. **Prebuild ground-truth grids,** so parallel runs don't race:
   ```bash
   cd ~/Swachh/Navigation/Simulation/vacuum_ws/src/vacuum_eval
   for c in quick_exploration quick_navigation quick_avoidance quick_responsiveness; do
     python3 -m vacuum_eval.run_batch --matrix config/campaigns/$c.yaml --prebuild-gt --dry-run --split test --confirm-test-split
   done
   ```
4. **From here on, no config or code changes.**

## 7. Contingencies and decision table

| Situation | Decision |
|---|---|
| G-SPEED says serial, or only 1 slot is possible | **Serial variant:** before Phase B, edit `quick_navigation.yaml` seeds to `[101, 102, 103]` and `quick_exploration.yaml` seeds to `[101, 102, 103, 104]`. Log both in the §6 pre-registration row. Serial Phase C is then about 5 h 50 min. |
| A mode is broken and not fixable in 20 min (gt localization, avoidance worlds, loaded responsiveness) | Continue without that mode. Gt localization broken: run navigation with the default AMCL localization (campaign default). The gt-vs-slam comparison is lost; log it. Avoidance worlds broken: drop `quick_avoidance`. Metric 9 is UNMEASURABLE (reason: scenario worlds fail to start); metrics 3/4 still come from exploration/navigation. Loaded responsiveness broken: remove `loaded` from `quick_responsiveness.yaml` (log it); metric 5 from bare only. |
| `--parallel 2` smoke test fails in Phase C (§8, step C0) | Run everything with `--parallel 1` and switch to the serial variant if it wasn't already applied. That change is only allowed before Phase B, so if Phase B is already done, run the full files serially and use the buffer, cutting at the end (next row). |
| Behind schedule in Phase C | Never stop an episode midway. Let the running campaign finish its current episodes, then reduce the **last** campaign (`quick_navigation`) by stopping `run_batch` with Ctrl-C between episodes. The finished episodes count; the rest are reported as "not run (time budget)". Do not skip responsiveness or avoidance: they are cheap and are the only sources of metrics 5 and 9. |
| An episode is `status: invalid` | Rerun once with the same seed (`run_batch` with `--force` re-runs only that seed, or run that single `run_episode` command). If it is invalid again, report both and move on. |
| Many episodes invalid with image drops | Stop and check `rmem_max` (it may have reset) and the RTF. Fix, then rerun the invalid ones once. |
| R1 corruption recurs (A1/A2) | Continue (see A2). Report it; the stratifier keys handle it. |
| Ubuntu/ROS packages missing at setup | Not inside the 8 h. Resolve during setup (ANTIGRAVITY_HANDOFF §4; Docker 24.04 fallback) before T+0. |

## 8. Phase C (T+2:15–6:00): the test campaign

**Order: cheapest first, then the two big ones.** This proves parallel runs on short jobs, and secures metrics 5 and 9 early. Run each command in the tmux window, and monitor from a second window (Ctrl-b c).

**C0 (T+2:15): parallel smoke test and responsiveness** (4 episodes, about 12 min with 2 slots):
```bash
python3 -m vacuum_eval.run_batch --matrix config/campaigns/quick_responsiveness.yaml --split test --confirm-test-split --parallel 2
```
Use `--parallel 1` under the serial variant.

**Parallel check** after it finishes:
- Each run folder's `run_meta.yaml` shows a different `slot` / `ros_domain_id` / `gz_partition` for concurrent runs.
- Each `trajectory.csv` is one continuous robot path, with no jumps between two robots.
- All are `episode_valid`, and `rtf_true_mean` is ≥ 0.7.

If this fails, see §7, row "parallel smoke test fails".

**C1 (T+2:30): avoidance** (10 episodes, about 25 min with 2 slots):
```bash
python3 -m vacuum_eval.run_batch --matrix config/campaigns/quick_avoidance.yaml --split test --confirm-test-split --parallel 2
```

**C2 (T+2:55): exploration** (15 episodes, about 1 h 25 min with 2 slots):
```bash
python3 -m vacuum_eval.run_batch --matrix config/campaigns/quick_exploration.yaml --split test --confirm-test-split --parallel 2
```

**C3 (T+4:20): navigation** (12 episodes, about 1 h 40 min with 2 slots):
```bash
python3 -m vacuum_eval.run_batch --matrix config/campaigns/quick_navigation.yaml --split test --confirm-test-split --parallel 2
```

**Monitoring** (every 20 min, from the second tmux window, read-only):
```bash
ls ~/eval_runs/quick_*/*/*/seed_*/summary.json 2>/dev/null | wc -l      # finished episodes so far
for f in $(ls -t ~/eval_runs/quick_*/*/*/seed_*/summary.json | head -4); do python3 -c "import json,sys;d=json.load(open('$f'));print('$f'.split('eval_runs/')[1], d.get('status'), d.get('episode_valid'), round(d.get('rtf_true_mean') or 0,2), d.get('end_reason'))"; done
pgrep -fa "gz sim" | wc -l      # 2 while a parallel batch runs, 1 if serial
```

**Track time.** If C2 ends later than T+4:45, apply "behind schedule" (§7) to C3 from the start: launch C3 anyway, and stop `run_batch` between episodes at T+6:00.

`run_batch` runs `compute_metrics` for every episode automatically. Run `diagnose` only when an episode looks wrong: invalid, `end_reason` stuck/crash, or a SUSPECT or BAD health flag.

## 9. Phase D (T+6:00–6:45): aggregate, report, verify

```bash
cd ~/Swachh/Navigation/Simulation/vacuum_ws/src/vacuum_eval
for e in quick_responsiveness quick_avoidance quick_exploration quick_navigation; do
  python3 -m vacuum_eval.aggregate --root ~/eval_runs/$e --out ~/eval_runs/$e/aggregate.csv
  python3 -m vacuum_eval.make_report --root ~/eval_runs/$e --out ~/eval_runs/$e/report
done
```

**Verification** (do all of these before calling it done):
1. **Validity census:** count ok / partial / failed / invalid per campaign, from the `status` column in `summary.csv`. List every invalid episode and its rerun.
2. **Health census:** per metric, count OK, LOW_N, SUSPECT, BAD and UNMEASURABLE. The report's "Metric health" section has this. For each non-OK headline metric, apply `docs/FAILURE_MODES.md` and note the fallback key used.
3. **Independent spot-checks** (recompute from raw CSVs, expect agreement within 2%):
   - One exploration episode: GT path length from `trajectory.csv` against `distance_gt_m`.
   - One navigation episode: count goals with `result` = succeeded in `goal_events.csv` against `nav_goals_succeeded`.
   - One avoidance episode: distinct contact events in `collisions_raw.csv` (gap > 0.5 s) against `n_collisions`.
4. **Sanity checks:**
   - Coverage, completeness and success values lie in 0–100.
   - ATE is less than the room size.
   - `rtf_true_mean` is similar across episodes.
   - Concurrent parallel runs show no cross-talk.
5. **Update `docs/METRICS_STATUS.md`:** paste each report's `metrics_status_update.md`, and set stage **Campaign** for each metric measured on the test split. Add the date and the note "reduced 8-hour campaign".
6. **Execution log:** append the totals: episodes run, wall time per phase, deviations, fixes, decisions.

## 10. Phase E (T+6:45–8:00): buffer

Use it for:
- reruns of invalid episodes (§7);
- the end of C3 if it ran late;
- regenerating the report after reruns.

If there is time left and the user agrees, a cheap extra is the noise-off condition for exploration on 1 world × 3 seeds (`--odom-noise 0`), as a limited A15 noise-robustness check. Log it as an exploratory addition, outside the pre-registered plan.

## 11. Deliverables (hand these to the user)

1. `~/eval_runs/quick_{exploration,navigation,avoidance,responsiveness}/report/results.md`, plus `figures/` and `metrics_status_update.md`.
2. The updated `docs/METRICS_STATUS.md` and `docs/EXECUTION_LOG.md`.
3. The pre-registration change row (§6) and the freeze commit hash.
4. A short message to the user:
   - per metric: headline value with 95% CI and health status;
   - validity and health census;
   - the gt-vs-slam navigation comparison from Phase A;
   - whether the R1 corruption recurred;
   - every deviation, fix and dropped item.

   Unflattering results are reported as measured.
5. Archive the results (optional, with the user's OK): `tar czf ~/eval_quick_$(date +%F).tgz ~/eval_runs/quick_* ~/eval_runs/dev8h_*` for transfer back. The bags are large; to skip them add `--exclude='*/bag/*'`.

## 12. Background the runner should know

- **Validity gates:** a run is `invalid` (excluded but counted) if camera images drop more than 10%, RTAB-Map stalls more than 5 s, or it updates less than 0.5 times per second. These caught a silent failure that had turned all SLAM results into odometry results on the laptop.
- **Health codes** (in `summary.json`): OK, NA, LOW_N, UNMEASURABLE (NO_DATA, NO_EVENTS, INVALID_EPISODE, GT_MISSING, MAP_MISSING), SUSPECT (ODOM_CORRUPTED, FRAME_OFFSET, RANGE, NAV_GT_DIVERGENCE, LOW_RTF, LC_ROT_BIAS), BAD (BELOW_FLOOR).
- **Known results on the laptop** (dev only, not comparable):
  - coverage about 90%, map completeness about 75%;
  - SLAM 53% better ATE than odometry before the first collision;
  - 181 loop closures, about 44% precision with about 5.2° rotation bias;
  - nav success about 15% (many "no valid path"; the planner is fixed by the user's decision).
- **Known limitations:** the axle sits 8 cm behind `base_footprint`; obstacles closer than 0.2 m are invisible to the depth camera; RTAB-Map does not recover from heavily corrupted odometry. Report them; don't fix them in this session.
- **True real-time factor:** use `rtf.csv`, which divides sim time by wall time. Never use Gazebo's `/stats real_time_factor` field.
