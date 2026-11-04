# 13. Results, docs and the paper pipeline

This note covers `results/`, `progress/`, `council/`, `large_files/`, `docs/` (with `docs/specs/` and `docs/paper_out/`) and `CLAUDE.md`. It describes only what is in the repository. File dates are from the file system; "current" and "historical" are judged from each file's own header text and dates.

## 1. CLAUDE.md (repo root)

Instructions for a fresh Claude Code session on the remote GPU machine `victus`. It says the job is to run the simulation evaluation, not to write features. It names the 2026-10-25 session as a 4-hour budget (clock start 16:29:17 IST, deadline 20:29:17 IST), gives a reading order (`SESSION_STATE.md`, `FOUR_HOUR_PLAN.md`, `REMOTE_MACHINE.md`, handoff, eight-hour plan, `FAILURE_MODES.md`), and lists the non-negotiable rules:
- no changes to the planner, robot model, worlds or metric definitions;
- Phase A fixes only for things that crash;
- one same-seed rerun, and only for infrastructure faults;
- exclude only `status: invalid`;
- no push to GitHub without an explicit OK;
- ask before destructive actions.

It is the active rulebook for that campaign. Its "current session" banner is dated 2026-10-25, so it describes a finished run.

## 2. docs/ (top level)

| File | What it is for | Current or historical |
|---|---|---|
| `SESSION_STATE.md` | Live state file of the evaluation: phase, what is done, what to run next, how to resume. Top block (about 20:12 on 10-25) says the test campaign is done (31 episodes), freeze commit `92c7757`, and the navigation v2 dev A/B failed its rule, so v1 results stand. Older blocks (pause at 17:29:54, resume at 17:53) are kept below it. | Current as final state of the run; the lower blocks are history. |
| `FOUR_HOUR_PLAN.md` | List of differences from the 8-hour plan: clock, phases A2/A3 skipped, 10-minute fix box, campaign sizes cut (41 to 25 planned episodes), parallelism rule, limitations to state in the paper. | Current for the 4-hour run. |
| `EIGHT_HOUR_PLAN.md` | Phase-by-phase procedure (A dev check, B freeze, C campaigns, D reporting) with checks and a contingency table. Has a banner saying durations and sizes are overridden by `FOUR_HOUR_PLAN.md`. | Still the base procedure; sizes are superseded. |
| `ANTIGRAVITY_HANDOFF.md` | Handoff for an earlier agent (Antigravity) on the Ubuntu GPU workstation. Section 3 is the hard rules, section 4 is setup. `CLAUDE.md` still points to it. | Rules still referenced; the audience and machine description are earlier-than-victus (history). |
| `REMOTE_MACHINE.md` | Facts about `victus` (Tailscale host, user, GPU, tools, how to open RViz) and the owner's "After the run" clean-up. | Current for this machine. |
| `EXECUTION_LOG.md` | Append-only dated log (newest at the bottom) of everything done in the session: setup, phases, pause/resume, deviations, rtf figures, audits. | Current; it is the record of the run. |
| `EVALUATION_FINDINGS_2026-10-25.md` | What each metric really measures, known biases, failure modes, and candidate fixes for the next campaign. Built from the log, campaign reports, `RESULTS_SO_FAR.md` and 12 read-only subagent audits. States that nothing was fixed in the measured v1 system. | Current. `CLAUDE.md` says to read it before a new campaign. |
| `METRICS_AUDIT_2026-10-25.md` | Completeness audit of every metric (14 user metrics, #13 on hold, plus extras A1-A15) against the test-split results. No simulation was run for it. | Current (post-run audit). |
| `METRICS_STATUS.md` | Tracker of what has actually been measured, by stage (Code, Pilot, Campaign and so on). Called the single source of truth for measurement status. | Current. |
| `METRICS_TO_BE_MEASURED.md` | Definition of each metric: what and why, tiers. Its own header says its Status column is historical and `METRICS_STATUS.md` is the live one. | Definitions current; status column historical. |
| `FAILURE_MODES.md` | Playbook for bad or unmeasurable metrics. Explains the `health_<metric>` codes (and `_reasons`) written to `summary.json` and their precedence. | Current reference. |
| `REQUIREMENTS.md` | Early "read this first" file: environment, constraints, requirements R1-R9. Last updated 2026-10-21. | Historical (superseded by later plans, but constraints still described). |
| `AUTONOMOUS_LOOP.md` | Standing instructions from the user for an autonomous loop on the night of 2026-10-21 (goal: all non-held metrics measured). | Historical. |
| `RUNBOOK.md` | Exact step-by-step commands for the user to run each measurement by hand. | Historical (Oct 22; written before the automated 4-hour run). |
| `SESSION_CONTEXT.md` | "Start here in a fresh chat" context, state as of 2026-10-22 about 04:30. | Historical; `CLAUDE.md` still lists it for project background. |
| `PAPER_SECTIONS_FILL.md` | Paste-ready text for the draft PDF `rp_draft_project_sby (2).pdf`, with `[TBD]` where results were not yet available, plus a list of errors found in the 20-page draft. | Historical input; sections 3.7 and 5.1-5.3 are copied from it by `build_final.py`. |
| `REPO_FACTS_ITEMS_1_TO_25.md` | Evidence behind `PAPER_SECTIONS_FILL.md`: answers to 25 questions about sections 5.1, 5.2 and 7.3, from six read-only checks. | Supporting evidence. |
| `PAPER_SECTIONS_5_7_VERIFIED.md` | Verified text for sections 5.1-5.3 and 7.1 (setup for 7.3). `[TBD]` marks facts the repository cannot answer. | Intermediate; the same text appears in the later files. |
| `PAPER_SECTIONS_FINAL.md` | Final text for sections 3.7, 3.8, 5.1-5.4, 7.3 and 7.4, with the generated tables as an appendix. Generated by `paper_out/build_final.py`. | Current output (generated). |
| `PAPER_TXT_REVIEW.md` | Fix list from reviewing `paper.txt` (1,176 lines) against the repo and results. Written 2026-10-27. | Current review. |
| `PROJECT_CONTEXT.md` | Benchmark report for the Jetson Orin Nano edge vision work (target Q1 journal; dated September 2026). | Separate project context, not about the simulation evaluation. |
| `README.md` | Readme of the Jetson Orin Nano / Raspberry Pi YOLOv8 vs YOLOv11-seg benchmark. | Separate topic from the simulation evaluation. |
| `user_guide.md` | User guide for the robot software stack scripts (run the robot, control it in simulation, export maps). | General usage guide. |

## 3. docs/specs/

These are implementation specs, written 2026-10-22, saying exactly what to build, with names, formulas and thresholds. `README.md` is their index and links the companion docs. Files 00-12 are dated 10-22 and are historical design documents; the code was built from them. `13_preregistration.md` was edited on 10-25 and is current.

| File | Content |
|---|---|
| `README.md` | Index of the specs. |
| `00_conventions.md` | Environment facts (ROS 2 Jazzy, Gazebo Harmonic, Python 3.12), shell setup, shared conventions. |
| `01_prerequisites_and_fixes.md` | Fixes that must be done before numbers are trustworthy (problem, change, verify). |
| `02_run_harness.md` | Run harness, recorder, episodes, batching, statistics. Defines every raw file other specs read. |
| `03_ground_truth_grid_coverage.md` | Ground-truth grid, coverage, map completeness. |
| `04_trajectory_accuracy.md` | ATE, RPE, drift, localization error (numpy only). |
| `05_navigation_metrics.md` | Navigation success, path length ratio, latency, smoothness; the scripted-goals mode. |
| `06_safety_collisions_avoidance.md` | Collisions, obstacle avoidance, clearance. |
| `07_responsiveness.md` | Responsiveness percentage, events and deadlines. |
| `08_loop_closure.md` | Loop closure success rate. |
| `09_worlds.md` | Hand-written SDF worlds and scenarios, `worlds.yaml`. |
| `10_cleaning_efficiency.md` | Virtual cleaning from the ground-truth trajectory, swept-area coverage. |
| `11_baselines_on_hold.md` | Method comparison (#13), on hold; only fixes the interface. |
| `12_acceptance_tests.md` | Unit (U) and runtime (R) acceptance tests per spec. |
| `13_preregistration.md` | Frozen metric keys, units and rules; each experiment's `batch_manifest.json` records the commit and campaign SHA-256. Contains the pre-registration row for the 4-hour budget. |
| `14_critique_and_council_plan.md` | Combined plan from an independent critique and the Sonnet-only council of 2026-10-21. |

## 4. docs/paper_out/ (paper pipeline outputs)

| Item | Kind | Notes |
|---|---|---|
| `make_figures.py` | hand-written script | Builds the PNGs from raw run files. |
| `build_final.py`, `build_de.py`, `build_fixes.py` | hand-written scripts | Fill templates from `paper_values.json`. |
| `sections_template.md`, `sections_DE_template.tex`, `sections_fixes_template.tex` | hand-written templates | Contain `{{path\|fmt}}` tokens. |
| `paper_values.json`, `paper_tables.md` | generated | `paper_tables.md` header says "do not edit by hand". |
| `sections_D_E.tex`, `sections_fixes.tex` | generated | From the two `.tex` templates. |
| `figures/*.png`, `data/*.npz` | generated | 9 PNGs; two costmap `.npz` files. |
| `FIGURE_PLAN.md`, `FIGURE_CAPTIONS.md`, `PAPER_TXT_INSERTS.md` | hand-written (with AI help) | Plan, draft captions, and where to put the inserts in `paper.txt`. The plan says screenshots must be taken by the authors. The captions file also lists repository charts not to use as they are. |

The nine figures: `fig_test_worlds`, `fig_actual_vs_explored`, `fig_exploration_trajectories`, `fig_navigation_trajectories`, `fig_coverage_vs_time`, `fig_nav_success`, `fig_ate_points`, `fig_costmap_layers`, `fig_slam_map_office`.

## 5. Other folders

| Folder | Content | Status |
|---|---|---|
| `progress/` | 16 reports, `report_01_1552.md` to `report_16_2045.md`, written by the `*/30` cron of the observing session. Report 16 (20:45) says all work is complete and nothing is running. | Historical log. |
| `council/` | Two LLM-council runs. `2026-10-21-185011/` (`content.json`, `council-report.html`, `council-transcript.md`) and `2026-10-22-031950/` (adds `anonymized_responses.md`, `framed_question.md`). The second is about how to classify a collision episode that corrupted odometry and SLAM. | Historical decision records. |
| `large_files/` | `MANIFEST.md` plus `eval_runs/` (hard links to the originals in `~/eval_runs`). The manifest lists 107 files, 6.3 GB: rosbags `bag/*.db3`, `rtabmap.db` and other files over 5 MB, with sizes and truncated sha256. The user's note says they are kept on victus, not in GitHub, and `.gitignore` excludes the folder (commit `0651f9d`). | Data store, listing only. |

## 6. results/ layout

| Path | Content | Generated or hand-written |
|---|---|---|
| `INDEX.md` | Table of every episode folder: experiment, world, method, seed, status, valid, rtf, img_drop %, end_reason. | generated (20:45 on 10-25) |
| `RESULTS_SO_FAR.md` | Test-split (`quick_*`) means and ranges over valid episodes, health flags, per-episode rtf. | generated by `results_table.py` |
| `results_table.py`, `metrics_audit_table.py` | Scripts that produce the table above and the audit table. | hand-written |
| `eval_setup/` | Helper scripts and logs from `~/eval_setup` (`env.sh`, `navab.sh`, `snapshot_results.sh`, `wait_timer.sh`, `gpu_watch.sh`, `v2.diff`, `goal_tolerance.diff`, `DEADLINE`, `T0`, and others). | copied |
| `monitoring/` | `gpu_alert.txt` (the snapshot script also copies `timer.log` here). | copied |
| `runs/` | Light snapshot of `~/eval_runs`, copied by `snapshot_results.sh` with rsync (max file size 5 MB; no `bag/`, `*.db`, `*.db3`, `*.mcap`). | copied |

### Run directory layout

`results/runs/<campaign>/<world>/<method>/seed_N/`

A seed folder holds:
- `summary.json` (about 276 keys) and `summary.csv`;
- `run_meta.yaml`, `goals.yaml`, `gt_map.pgm`, `gt_map.yaml`;
- `trajectory.csv`, `cmd_vel.csv`, `events.csv`, `goal_events.csv`, `plans.csv`, `feedback.csv`;
- `collisions_raw.csv`, `loop_events.csv`, `rates.csv`, `resources.csv`, `rtf.csv`.

Exploration episodes also carry `maps/` (the `map_*.npz` and `final_map.npz` files). The sampled navigation `summary.json` has keys such as `ate_fixed_rmse_m`, `avoidance_pct`, `status`, `episode_valid` and `end_reason`; the sampled episode (`quick_navigation/office/scripted_goals_random20/seed_101`) had `status: ok`, valid, `end_reason: stuck`.

Campaign-level files sit beside the world folders:
- `aggregate.csv` (rows of kind `stat` per world/method/metric, with n, mean, bootstrap and cluster CIs);
- `batch_manifest.json` (campaign yaml path, its SHA-256, git commit, split `test`, timestamp);
- `report/` (`results.md`, `metrics_status_update.md`, `figures/*.png` such as `ate_box.png`, `nav_success.png`).

Other `runs/` entries:
- `_gt/<world>.npz`: ground-truth grids for 9 worlds (apartment, 4 avoid worlds, maze_dead_ends, multi_room_loop, office, two_rooms_door).
- `_failed_attempts/quick_responsiveness/`: first attempts that failed at bring-up (`bringup_failed`).
- `dev8h_*`, `dev_navab_v1/v2`, `diag_gt_localization`: Phase A dev checks and diagnostics on the apartment (and two avoid worlds). Per `INDEX.md` they are not pooled.

## 7. The 4-hour campaign (what was run)

Plan (FOUR_HOUR_PLAN): 25 test-split episodes (responsiveness 4, avoidance 6, exploration 9, navigation 6). Actual: 31 test episodes, with navigation extended by two seeds.

| Campaign folder | Worlds / method | Seeds | Episodes |
|---|---|---|---|
| `quick_responsiveness` | office; `responsiveness_bare` and `responsiveness_loaded` | 101, 102 | 4 (the 2 `bare` ones are `invalid`; the 2 `loaded` ones valid) |
| `quick_avoidance` | `avoid_u_trap`, `avoid_dynamic_sudden`; `scripted_goals_scenario` | 101-103 | 6 (all ok) |
| `quick_exploration_noise` | office, multi_room_loop, maze_dead_ends; `frontier` | 101-103 | 9 (all ok) |
| `quick_navigation` | office, maze_dead_ends, two_rooms_door; `scripted_goals_random20` | 101-104 | 12 (6 planned, seeds 103/104 added via `quick_navigation_extra.yaml`) |
| **Total** | | | **31** |

Notes:
- The exploration episodes are in `quick_exploration_noise`. The `quick_exploration` folder holds only a `batch_manifest.json`, with no episodes.
- Runs went in parallel (3 slots for avoidance and most exploration, 2 for the maze and navigation), so rtf differs by wave. `RESULTS_SO_FAR.md` gives the rtf range as 0.729-1.000 over the 31 episodes, with none below 0.7.
- In maze_dead_ends, seeds 101 and 103 never moved (0 goals) and ended `stuck`. The log says the exploration manager could not snap any frontier to a free cell and kept blacklisting them.
- Dropped or limited, per FOUR_HOUR_PLAN: A2 and A3 skipped, no noise-robustness comparison (A15), several worlds and goal types dropped, one machine with headless EGL rendering.
- Navigation v2 (opt-in `VACUUM_NAV_VARIANT=v2`) was tried only on dev seeds 1-2 (`dev_navab_v1`, `dev_navab_v2`); its pre-fixed rule failed, so there are no test-split v2 runs.
- The git status at the start of this session shows modified `results/runs/...` map files, i.e. the working tree differs from the last commit.

## 8. Pipeline: summary.json to paper tables and figures

```
~/eval_runs/<campaign>/.../seed_N/summary.json     (and trajectory.csv, gt grids, etc.)
        |  (snapshot_results.sh copies light files to results/runs/; paper scripts read the root --root, default ~/eval_runs_victus)
        v
vacuum_eval/paper_tables.py        (Navigation/Simulation/vacuum_ws/src/vacuum_eval/vacuum_eval/)
        |-- paper_values.json      (all numbers: exploration, navigation, avoidance, responsiveness,
        |                           census, crosscheck, rtf, plan latency, ...)
        |-- paper_tables.md        (rendered tables, via render_tables)
        v
templates with {{path|fmt}} tokens
        |  build_final.py   : sections_template.md        -> docs/PAPER_SECTIONS_FINAL.md
        |                     (3.7 and 5.1-5.3 copied from PAPER_SECTIONS_FILL.md; 3.8, 5.4, 7.3, 7.4 from the template)
        |  build_de.py      : sections_DE_template.tex    -> sections_D_E.tex
        |  build_fixes.py   : sections_fixes_template.tex -> sections_fixes.tex
        v
paper.txt (authors paste text; PAPER_TXT_INSERTS.md says where)

make_figures.py : raw run files (+ _gt/*.npz, and paper_values.json for fig_nav_success) -> figures/*.png
```

Details:
- `paper_tables.py` says no value is typed by hand. It reads each episode's `summary.json`, computes per-world and pooled statistics with numpy (the episode is the unit), takes CIs from the repository's own bootstrap helpers (same seed and B as the campaign reports; `paper_tables.md` states 5000 resamples, seed 12345), and cross-checks means against `aggregate.csv` (the `crosscheck` block). Usage from its docstring: `--root ~/eval_runs_victus --out ~/Swachh/docs/paper_out [--template T.md --filled F.md]`.
- The `fill` function replaces `{{path|fmt}}` tokens such as `{{exploration.pooled.coverage_explored_pct.mean|f1}}` using formats like `f1`, `f2`, `int`. The build scripts print `MISSING TOKENS` and exit with status 2 if a token has no value.
- `make_figures.py` hardcodes `ROOT = ~/eval_runs_victus/` and writes to `~/Swachh/docs/paper_out/figures/`. It reads `_gt/<world>.npz`, trajectory CSVs, SLAM map files, and (for `fig_nav_success`) `paper_values.json`. It draws six test worlds: office, multi_room_loop, maze_dead_ends, two_rooms_door, avoid_u_trap, avoid_dynamic_sudden. The costmap figure uses the `data/*.npz` files. I did not run the scripts, so I did not check that they currently run.
- `paper_tables.py`, the build scripts and `make_figures.py` use the paths `~/eval_runs_victus` and `~/Swachh/...`. The `eval_runs_victus` directory is not in this repository.

## 9. Generated versus hand-written (summary)

| Generated | Hand-written |
|---|---|
| `results/INDEX.md`, `results/RESULTS_SO_FAR.md`, all `results/runs/**` (copied or produced by the harness), `aggregate.csv`, `report/*` | `CLAUDE.md`, all `docs/*.md` except `PAPER_SECTIONS_FINAL.md`, `docs/specs/*` |
| `docs/PAPER_SECTIONS_FINAL.md` | `results/results_table.py`, `metrics_audit_table.py`, `eval_setup/*` scripts |
| `docs/paper_out/paper_values.json`, `paper_tables.md`, `sections_D_E.tex`, `sections_fixes.tex`, `figures/*.png`, `data/*.npz` | `docs/paper_out/` scripts, `*_template.*`, `FIGURE_*.md`, `PAPER_TXT_INSERTS.md` |
| `large_files/MANIFEST.md` (and the hard links) | `progress/*` (written by the observing session's cron), `council/*` (outputs of council runs) |

One-line summary: the 4-hour run produced 31 test episodes in `results/runs/<campaign>/<world>/<method>/seed_N/`; `paper_tables.py` turns their `summary.json` files into `paper_values.json` and `paper_tables.md`, template scripts fill the paper text from it, and `make_figures.py` draws the figures from the raw files.
