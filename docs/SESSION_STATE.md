# >>> CURRENT STATE 2026-10-25 ~20:12 IST (read this first) <<<
- **Test campaign DONE** (31 episodes, Phase D verified; reports in `~/eval_runs/quick_*/report/`, status in `METRICS_STATUS.md`, findings and audits in `EVALUATION_FINDINGS_2026-10-25.md`). Freeze commit 92c7757; results snapshots committed locally; nothing pushed.
- **Navigation v2 (user request 19:51):** opt-in variant (`VACUUM_NAV_VARIANT=v2`: START_OCCUPIED BackUp+Spin recovery BT + AMCL more particles/updates), commit 10b6b11; v1 default unchanged. Dev A/B on apartment dev seeds 1-2 (`dev_navab_v1`, `dev_navab_v2`, script `~/eval_setup/navab.sh`) judged by the pre-fixed rule in EXECUTION_LOG ("NAV v2 DEV A/B DECISION RULE"). Test seeds 105/106 only if the rule passes.
- Owner clean-up after the run: see "After the run" in REMOTE_MACHINE.md.

# >>> RESUMED 17:53 (was paused 17:29:54; see EXECUTION_LOG) <<<
_Deadline now in ~/eval_setup/DEADLINE. The resume checklist below is DONE (all OK). Open: two pre-freeze user decisions._

# (old pause block, kept for reference)
**The run is PAUSED since 2026-10-25 17:29:54 IST by the user** (the PC owner suspends the machine to transport it). **Do not start anything until the user says to continue.**
- Clock at pause: **1 h 00 m 37 s used, 2 h 59 m 23 s remaining** (see `~/eval_setup/PAUSED`). The 20:29:17 deadline below is VOID; on resume set the deadline = resume time + 10763 s (write it to `~/eval_setup/DEADLINE`, add a `RESUME` line to `~/eval_setup/timer.log`, update this file).
- State at pause: nothing running (no gz/ruby/harness/watchers). Phase A is finished. Recorder fix v2 is applied and verified (`dev8h_resp_fix`, `dev8h_avoid_fix`). **Phase B (freeze) has NOT started; no test-split episode has been run.** Repo has uncommitted edits (docs, 3 campaign yamls, `recorder_node.py`); nothing pushed.
- **Two decisions still pending from the user before the freeze:**
  1. Apply `goal_tolerance.diff` (2 lines in `metrics/navigation.py`, accept goals starting up to 1 s before the first motion command)? Without it metric 9 (`trial_success`) is UNMEASURABLE in every avoidance episode and each navigation episode loses its first goal. Recommended: yes (needs a pre-registration row). Diff: `~/eval_setup/goal_tolerance.diff` (also described in the 17:27 EXECUTION_LOG entry); the independent rate counter is `~/eval_setup/rate_probe.py`.
  2. Bare responsiveness stack is `invalid` only via the RTAB-Map rules. Recommended: keep as is (report excluded-invalid); alternative: exempt bare (gate change).
- **Resume checklist (after the PC is moved and back online):**
  1. `date` (clock sync), `uptime` (did it reboot?), `tailscale status`, `nvidia-smi` (driver up, RTX 5050 present), `sysctl net.core.rmem_max` (must be 33554432), `df -h ~`, `free -g`.
  2. `tmux ls`: if the `eval` session is gone (reboot), `tmux new -d -s eval`. All env comes from `source ~/eval_setup/env.sh`.
  3. Orphan check by name: `ps -eo comm | awk '$1=="gz"||$1=="ruby"' | wc -l` must be 0 (never `pkill -f`).
  4. Re-run preflight: `source ~/eval_setup/env.sh && bash ~/Swachh/Navigation/Simulation/scripts/preflight.sh` (all PASS; renderer: headless EGL NVIDIA, `nvidia-smi` shows gz memory during a run). If the machine moved networks, Tailscale/SSH may need the owner. Power/thermal differ: watch `rtf_true_mean` in the first episode.
  5. Set the new deadline (above), then get the two decisions, then Phase B per `docs/FOUR_HOUR_PLAN.md`: pre-reg rows, git commit (local) and hash into the log, GT grids already prebuilt (re-run is harmless), C0 smoke test (`--parallel 3`, fall back to 2), C1-C3, D.
- The progress-report cron is owned by another session; my session's jobs were deleted. A new session should not create one.

# SESSION STATE: live handoff for the 4-hour evaluation on `victus`

**If you are a new Claude session: read this file first, then `docs/FOUR_HOUR_PLAN.md`, `CLAUDE.md`, and the phase you are in (`docs/EIGHT_HOUR_PLAN.md`).** Update this file after every step (it is the source of truth for where the run is). Last updated: see the "Updated" line at the bottom.

## Clock
- **T0 = 2026-10-25 16:29:17 IST. Deadline = 20:29:17 IST** (4 h). Also in `~/eval_setup/T0` and `~/eval_setup/DEADLINE`; events in `~/eval_setup/timer.log`.
- Remaining time: `echo $(( ($(date -d "$(cat ~/eval_setup/DEADLINE)" +%s) - $(date +%s)) / 60 )) min`.

## Where things are
| What | Where |
|---|---|
| Repo | `~/Swachh` (git, branch `main`; **nothing pushed**; local commits OK) |
| Environment for any terminal | `source ~/eval_setup/env.sh` (sources ROS + workspace, sets CycloneDDS, `ROS_DOMAIN_ID=0`, **`VACUUM_GZ_HEADLESS_RENDERING=1`** because there is no display, cds to `vacuum_eval`, defines `post()`) |
| tmux | session `eval`; long jobs run in extra windows (`tmux ls`, `tmux list-windows -t eval`, `tmux attach -t eval`) |
| Run outputs | `~/eval_runs/<experiment>/<world>/<method>/seed_NNN/` (`summary.json`, `rtf.csv`, `diagnose.png`, `logs/`) |
| Harness logs | `~/eval_setup/*.log` (e.g. `A1.log`) |
| Progress reports | `~/Swachh/progress/report_NN_HHMM.md`, written by ONE `*/30` cron owned by another (observer) session. The */20 job of the main session was deleted at the user's request; a new session must NOT create a second cron. |
| Wait timer | `~/eval_setup/wait_timer.sh <label> <marker-in-timer.log> <minutes>`; **max 15 min per wait** (user rule, changed from 10 on 2026-10-25 16:5x): when you are not doing other work, only briefly check, report, and leave if the job is still running; never idle >15 min. The watcher itself is passive; start the notifying background waiter only when you go idle, and do not let it fire while you are already working (stop it, or simply do not arm it). Live counter: `~/eval_setup/wait_timer.txt` |
| Setup record | `docs/EXECUTION_LOG.md` (append dated entries) |

## Machine facts that matter
- RTX 5050 Laptop 8 GB (60 W cap), 16 threads, 22 GB RAM, Ubuntu 24.04. **Renderer confirmed NVIDIA** with headless EGL (gz holds GPU memory; idle RTF about 1.01). libEGL "Permission denied /dev/dri/renderD12x" warnings are harmless.
- Preflight: ALL PASS; it suggests `--parallel 3`, plan default is 2 (see FOUR_HOUR_PLAN "Parallel").
- Desktop session belongs to user `uzair`; our runs are headless. No live RViz unless `uzair` logs in as `hrishikesh`.
- ROS apt repo is over http (signed-by key), because packages.ros.org has a TLS name mismatch. Do not "fix" with `-k`.

## Phase status (update me)
| Phase | Run | Status | Result / run folder | Notes |
|---|---|---|---|---|
| Setup | | DONE 16:29 | see EXECUTION_LOG | 184+1skip / 7 tests pass, preflight PASS, NVIDIA confirmed |
| Plan edits | campaign seed cuts, docs, pre-reg row | DONE 16:33 | `config/campaigns/quick_*.yaml` (25 episodes), `13_preregistration.md` §13.6 row | all 4 campaigns pass `--dry-run --split test --confirm-test-split` |
| A1 | R1 confirmation seed 2 + speed gate | DONE 16:36 | `~/eval_runs/dev8h_r1/apartment/frontier/seed_002` | valid; rtf_true_mean 1.0016 (serial) => G-SPEED passes; img_drop 8.7%; **R1 corruption recurred** (odom_corrupted_by_contact=1, yaw excess 78.9 deg), logged, continue; ended `stuck` at 357 s |
| A2 | | SKIPPED by user decision | | limitation |
| A3 | | SKIPPED by user decision | | limitation |
| A4 | nav, `--localization slam`, seed 1 | DONE 16:45, INVALID (plan/harness mismatch: ran AMCL, labelled rtabmap, 0 RTAB-Map updates) | `~/eval_runs/dev8h_nav/apartment/scripted_goals_random20/seed_001` | see EXECUTION_LOG; no code change |
| A4b | nav, campaign config `--nav-map gt --localization auto` (=AMCL), seed 1, `dev8h_nav_amcl` | DONE 16:54, VALID | `~/eval_runs/dev8h_nav_amcl/apartment/scripted_goals_random20/seed_001` | 19 goals; Nav2 says 73.7% success, GT says 31.6% (SUSPECT NAV_GT_DIVERGENCE); 0 collisions; ATE 0.388 m (BAD floor 0.3); rtf 1.002 |
| A5 | responsiveness bare + loaded, seed 1 | RERUN DONE 17:22 after recorder fix (applied v2): `dev8h_resp_fix` | `~/eval_runs/dev8h_resp_fix/apartment/responsiveness_{bare,loaded}/seed_001` | img_drop 0.0 both; recorder count = independent 30 Hz. loaded VALID (attempt1 failed bring-up: controller switch timeout, kept as `seed_001_attempt1_failed`, rerun once OK). bare still INVALID only via RTAB-Map rules (no RTAB-Map in bare) -> USER DECISION |
| A6 | avoid_head_on + avoid_dynamic_cross | DONE; recheck on fixed recorder `dev8h_avoid_fix` 17:24 | `~/eval_runs/dev8h_avoid_fix/*/scripted_goals_scenario/seed_001` | valid; but goal starts before episode_start => trial_success UNMEASURABLE (NO_DATA) deterministically; candidate fix `goal_tolerance.diff` NOT applied -> USER DECISION |
| B | freeze: git commit, hash in log, GT prebuild, (parallel 3 test) | pending | | **Freeze = no code/config changes afterwards** |
| C0 | `quick_responsiveness` (smoke test) | pending | | |
| C1 | `quick_avoidance` | pending | | |
| C2 | `quick_exploration` | pending | | |
| C3 | `quick_navigation` | pending | | |
| D | aggregate + report + verify + METRICS_STATUS + final message | pending (overlaps C) | | |

## What to run next
A5 is running (bare then loaded in one tmux window). When `A5_DONE` is in `~/eval_setup/timer.log`: post both runs and check the A5 criteria (EIGHT_HOUR_PLAN A5). Then A6 (`avoid_head_on`, `avoid_dynamic_cross`, `--goal-list scenario --nav-map gt`, one at a time, per EIGHT_HOUR_PLAN A6), then Phase B (freeze: pre-reg row already written; commit; GT prebuild; C0 smoke test with `--parallel 3`, fall back to 2), then C0..C3, D. Launch each run in a tmux window (`tmux new-window -d -t eval -n <name> "bash --rcfile <(echo 'source ~/.bashrc; source ~/eval_setup/env.sh') -ic '<cmd> 2>&1 | tee ~/eval_setup/<name>.log; echo <name>_DONE \$(date -Is) >> ~/eval_setup/timer.log; sleep 86400'"`) and wait with a <=15 min capped loop on the DONE marker.

## Rules (short; full list in CLAUDE.md and ANTIGRAVITY_HANDOFF §3)
No changes to planner / robot / sensors / worlds / metrics / thresholds; no tuning; Phase A fixes only for crash-or-fail-to-start (10-min box, unit tests green, log in EXECUTION_LOG); after the freeze nothing changes; one same-seed rerun only for infrastructure faults; exclude only `status: invalid`; no push; never `pkill -f` a pattern in your own command (use `kill -INT <PID>`, or `ps -eo pid,args | grep "[p]attern"`); `pgrep -fa "gz sim|ruby"` must be empty before launching a non-parallel run; stop a run with `kill -INT <harness PID>` and confirm no orphan `gz sim` remains (a SIGINT to the launch alone left an orphan once).

## Open items / things the user wants reported
- The ROS repo http workaround; the `pkill -f` slip at 15:55 (harmless).
- Limitations list: see FOUR_HOUR_PLAN.
- After the run: tell the owner to `sudo rm /etc/sudoers.d/hrishikesh`, `sudo deluser hrishikesh sudo`, unmask the sleep targets, unshare the machine in Tailscale; offer to tar the results (plan §11.5). Check that nothing was installed that the owner should know about (ROS Jazzy + `ros-dev-tools` + the setup packages, `/etc/sysctl.d/90-ros2-dds.conf`, `/etc/apt/sources.list.d/ros2.list`).

Updated: 2026-10-25 17:27 IST. Recorder fix v2 APPLIED + verified. PENDING USER DECISIONS before freeze: (1) goal-start tolerance (metric 9), (2) bare responsiveness validity. Phase B not started. Remaining ~182 min.
