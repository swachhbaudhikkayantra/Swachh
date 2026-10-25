# Swachh: instructions for a fresh Claude Code session

You are on a **remote Ubuntu 24.04 GPU PC** (hostname `victus`, user `hrishikesh`, reached over SSH/Tailscale) with **no memory of earlier chats**. Your job is to **run the 8-hour simulation evaluation**, not to write new features.

> **CURRENT SESSION (2026-10-25): the budget is 4 hours, not 8.** The clock started at **16:29:17 IST**; the deadline is **20:29:17 IST**. Read **`docs/SESSION_STATE.md` first** (live state: phase, what is done, what to run next, how to resume) and **`docs/FOUR_HOUR_PLAN.md`** (the cuts relative to the 8-hour plan). Log everything in `docs/EXECUTION_LOG.md`, and progress reports go to `~/Swachh/progress/` from ONE cron job only (`*/30`, owned by the other observing session; the */20 job was deleted at the user's request). If you are a new session, do not create a second cron. Never wait more than 15 minutes without checking in; run a timed watcher (`~/eval_setup/wait_timer.sh`) whenever you wait. The watcher is passive (writes `~/eval_setup/wait_timer.txt`); arm a notifying waiter only when you actually go idle, and stop it if you are already back at work, so it never interrupts you mid-task.

## Read first, in this order
0. `docs/SESSION_STATE.md` and `docs/FOUR_HOUR_PLAN.md` (current state and overrides).
1. `docs/REMOTE_MACHINE.md`: this machine's facts and what is already set up.
2. `docs/ANTIGRAVITY_HANDOFF.md` §3 (hard rules) and §4 (setup).
3. `docs/EIGHT_HOUR_PLAN.md`: the phase-by-phase procedure and checks (durations and campaign sizes are overridden by `FOUR_HOUR_PLAN.md`).
4. `docs/FAILURE_MODES.md` when a metric is bad or unmeasurable; `docs/SESSION_CONTEXT.md` for project background.

## Non-negotiable rules (full list in the handoff §3)
- Do not change the Smac Hybrid DUBIN planner, robot/sensor model, world geometry, metric definitions or thresholds. No physics fudge factors. Metric #13 (method comparison) is on hold.
- Phase A may fix only things that crash or fail to start (log each in `docs/EXECUTION_LOG.md`, unit tests must pass). After Phase B starts, nothing changes. Never tune for better numbers.
- Rerun an episode once, same seed, only for infrastructure faults. Exclude only `status: invalid`. Report unflattering results as measured.
- Commands over 2 minutes run in tmux (`tmux new -s eval`). Timers never kill anything; inspect first and decide yourself. Never `pkill -f` a pattern that is in your own command line; stop runs with `kill -INT <harness PID>`.
- Do NOT push to GitHub or send data to third-party services without the user's explicit OK. Local commits are fine.
- Ask the user before destructive actions (deleting runs, rewriting history).
- Decisions between real alternatives: keep replies concise, give a recommendation.

## Start
Do setup and preflight (plan §1, §4), then tell the user when it is ready to start the clock. The user may be watching the desktop; see `docs/REMOTE_MACHINE.md` for how to open RViz.
