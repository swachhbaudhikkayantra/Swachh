# Autonomous loop protocol (user instruction, 2026-10-21 night)

The user is away (asleep) and gave these standing instructions. They apply until every metric is done or the user returns.

## Goal
**All metrics measured.** Every non-held row of `docs/METRICS_STATUS.md` must reach stage **Campaign**. Metric #13 (method comparison) stays ON HOLD. The full plan, constraints and requirements R1–R9 are in `docs/REQUIREMENTS.md`.

## Roles
- **Supervisor:** the main Claude Code session. It starts and resumes the orchestrator, reviews each phase report, and keeps the loop alive.
- **Orchestrator:** always an **Opus** agent. It plans each phase, owns the simulator (only one simulation at a time on this laptop), integrates results, and updates `docs/METRICS_STATUS.md`.
- **Implementation:** always **Sonnet** subagents, usually low effort. Each gets a precise task and an explicit EDIT-ONLY file list, and file ownership never overlaps. Implementation agents never start the simulator, never run `colcon` while a simulation runs, and never `pkill`.
- **Decisions:** any decision that is not purely mechanical goes to the **Sonnet-only LLM council**. The protocol is in `~/.claude/skills/llm-council/SKILL.md` and its `references/`: 5 advisors, 5 anonymised reviewers, and a chairman synthesis in the orchestrator. Every advisor and reviewer uses model sonnet. Save artifacts in `~/Swachh/council/<timestamp>/`. Previous council: `council/2026-10-21-185011/`.

## Long-running commands
- Any terminal command expected to exceed **2 minutes** must run in the background, with a **timer** to come back: either a background wait-until-done-or-deadline command, or the harness's own completion.
- Deadline = expected duration + buffer (about 25–50%).
- **Timers never kill anything.** At the deadline, the orchestrator inspects progress (trajectory.csv sim time, rtf.csv, events.csv, logs) and decides itself whether to let it continue or to stop it gracefully: SIGINT to the harness PID, never a pattern-based pkill that can match its own shell.
- **Expected durations:** a 600 s sim exploration episode takes about 35 min wall at true RTF 0.30; bring-up plus metrics takes about 5 min. Scale linearly with sim seconds, about 1 / RTF.

## Loop
1. Pick the next open requirement (R1–R9 in `docs/REQUIREMENTS.md`) and the metrics still not at their target stage (`docs/METRICS_STATUS.md`).
2. Fix anything broken via Sonnet subagents, then run the needed episodes yourself (background plus timer).
3. After each run, run `compute_metrics` and `diagnose`, and update `docs/METRICS_STATUS.md`.
4. **When a metric has values, verify it** with an independent Sonnet subagent, or the council if a judgment call is needed:
   1. **Accurate:** cross-check against raw data and the oracle tests; recompute key numbers independently.
   2. **Measured correctly:** no wrong method, no circular definition, consistent with `docs/specs/13_preregistration.md`.
   3. **Good or bad:** if a value is bad, find out why with `diagnose` and the logs. Decide via the council whether it's a real result to report or a fixable artefact. Fix artefacts and re-measure; real results are reported as they are.
5. Record every decision in `docs/specs/13_preregistration.md` §13.6 (if pre-registration is touched) or in `docs/specs/14_critique_and_council_plan.md`.
6. Repeat until every metric is at stage Campaign and has passed verification, then run R9 (aggregate and report).

## Safety rails (from the user's earlier decisions; not overridable by the council)
- **Planner:** Smac Hybrid DUBIN stays unchanged.
- **Physics:** no fudge factors.
- **Method comparison:** #13 stays on hold.
- **Data leaving the machine:** nothing goes to third-party AI providers.
- **Git:** no git commits or pushes. Record the state instead: each `batch_manifest.json` holds the commit plus a `git diff --stat` hash.
- **Destructive actions:** no deletions outside `~/eval_runs` scratch or `/tmp`, and no system changes beyond what `docs/REQUIREMENTS.md` documents.
- **Test split:** tuning happens only on the dev split. Once the first test-split run starts, configs are frozen. Any later change needs a council decision and a §13.6 change-log entry, plus a rerun of the affected test runs.
- **Wall-time budget:** a multi-day campaign is acceptable (the laptop runs unattended). Size it with `plan_sample_size`, and use the council if a configuration exceeds about 48 h.

## Reporting
- Keep `docs/METRICS_STATUS.md` current. It is what the user reads first on return.
- At the end of each phase, append a short dated entry to the log below: what was run, results, decisions, and what is next.

## Log
- 2026-10-21 ~19:45. Protocol written. Pilot 2 is running (harness PID 4049, expected completion about 20:00). The Opus orchestrator is started next.
- 2026-10-22 03:15 (supervisor). The first Opus orchestrator hung at 20:43 (silent 6.5 h while marked running) and was stopped. It had started R1 on pilot 2, which completed by 20:15, and found a candidate artefact: around t≈310–325 s, **odometry yaw jumps ~125° against ground truth and SLAM follows it**, right after chair_1 contacts at t≈273–295 s. Nothing was measured or recorded beyond that. Change of procedure to avoid long silent hangs: the orchestrator now works **one requirement per run** and hands back after each (log entry plus METRICS_STATUS update); the supervisor restarts it for the next one.
- 2026-10-22 ~03:40 (orchestrator, R1). Pilot 2 evaluated from existing data; no simulation was run (the user now executes all runs).
  - **Acceptance:** valid; 586 RTAB-Map updates in 600 s; 27 goals, with `frontiers_skipped` present; coverage 90.4 %; map completeness 74.8 %. ATE improvement **failed** (-3.8 %; ATE 3.10 m).
  - **Cause:** a real navigation failure, not a simulator artefact or a recording bug. chair_1 had decayed out of the 15 s local STVL, MPPI arced into it, and the BT ran ClearEntireCostmap plus a 90 deg Spin while the robot was pressed against it. The wheels slipped (232 vs 105 deg) and the odometry yaw error reached +113 deg. SLAM followed and never recovered. Before the contact, ATE was 0.119 m against odometry 0.256 m (+53 %).
  - **Council** `council/2026-10-22-031950/`: keep the episode valid and failed; diagnostic keys are a stratifier, not an exclusion; add a local static layer and BackUp before Spin; no torque limits; no tilt rule.
  - **Code:** new `metrics/contact_odom.py` with an oracle test (170 tests pass); `eval_defaults.yaml` gets `contact_odom_corrupt_deg`; local static layer in `nav2_params.yaml`; `explore.xml` reordered.
  - **Docs:** spec 01, 13 §13.6 and 14 (items 19-21) updated.
  - **Next:** the user runs the R1 confirmation episodes (seeds 2 and 1). The next requirement is R3, scripted navigation; nav success was 15.4 %.

- 2026-10-22 ~04:00 (supervisor). The user takes over execution. All remaining code is written and tested (173 vacuum_eval + 7 explorer tests pass): R1 fix (local static layer, BackUp before Spin, contact-odometry diagnostics), loop-closure direction verified on pilot 2 (`loop_to_ref`), parallel slots, lean mode, GPU option, setup/preflight scripts, report generator. Execution steps are in `docs/RUNBOOK.md`. The autonomous loop is paused.
