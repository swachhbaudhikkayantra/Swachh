# FOUR-HOUR PLAN: overrides `docs/EIGHT_HOUR_PLAN.md` for this session

**Decided by the user on 2026-10-25, before any test-split run.** The budget is **4 hours of wall-clock** (not 8) from the clock start. This file lists only what differs from `EIGHT_HOUR_PLAN.md`. Everything else in that plan, in `CLAUDE.md` and in `ANTIGRAVITY_HANDOFF.md` §3 still applies: no tuning after the freeze, same rerun rules (once, same seed, infrastructure faults only), exclude only `status: invalid`, no pushing to GitHub, no `pkill -f` on your own command line.

**Live state (clock, current phase, what to run next) is in `docs/SESSION_STATE.md`. Read it first if you are resuming.**

## Clock
- **T0 = 2026-10-25 16:29:17 IST** (user said "start the clock"). **Deadline = 20:29:17 IST.**
- Setup (15:50-16:29, including the renderer check) was outside the budget.
- Do not wait for planned times. Move to the next phase as soon as the previous one passes.

## Phase A (dev check): only A1, A4, A5, A6
| Run | Status in this session |
|---|---|
| A1 R1 confirmation seed 2 + speed gate | run |
| A2 R1 seed 1 + `check_lc_direction` | **SKIPPED** (limitation: R1-corruption/LC-direction not confirmed on a second seed) |
| A3 navigation with `--localization gt` | **SKIPPED** (limitation: gt-vs-slam navigation comparison not measured; navigation campaign uses the campaign default localization) |
| A4 navigation `--localization slam` | run |
| A5 responsiveness bare + loaded | run |
| A6 avoidance head_on + dynamic_cross | run |

- **No fix buffer.** Per-failure time box is **10 minutes** (was 20). If a mode cannot be fixed in 10 minutes, apply the contingency table (EIGHT_HOUR_PLAN §7) and move on.
- Only minimal fixes for things that crash or fail to start, with unit tests green and an `EXECUTION_LOG.md` entry.
- Gate G-SPEED (A1 `rtf_true_mean`): >= 0.75 plan holds; 0.45-0.75 serial variant; < 0.45 check the renderer. Renderer was confirmed NVIDIA at setup (see log).

## Phase B (freeze): campaign sizes cut
Edited **before any test-split run** (validated with `run_batch --dry-run --split test --confirm-test-split`, all pass):

| Campaign file | Was | Now | Episodes |
|---|---|---|---|
| `quick_responsiveness.yaml` | seeds 101-102 | unchanged (101-102) | 4 |
| `quick_avoidance.yaml` | seeds 101-105 | **101-103** | 6 |
| `quick_exploration.yaml` | seeds 101-105 | **101-103** | 9 |
| `quick_navigation.yaml` | seeds 101-104 | **101-102** | 6 (about 120 goals) |
| **Total** | 41 | | **25** |

- **Parallel:** if A1 shows `rtf_true_mean` > 0.7 with 2 slots, test `--parallel 3` in the Phase B smoke test (C0, `quick_responsiveness`) and use 3 if it passes (concurrent runs on different slots, one continuous robot path each, all `episode_valid`, `rtf_true_mean` >= 0.7). Otherwise use 2. If 2 slots are impossible, run serial and cut at the end per EIGHT_HOUR_PLAN §7.
- Preflight suggested 3; the machine has 22 GB RAM and a 60 W GPU, so 2 is the default.
- The pre-registration row (§13.6) and the freeze commit must list: the 4-hour budget, these seed cuts, dropped A2/A3, and everything the 8-hour row already lists. See the row in `docs/specs/13_preregistration.md`.
- After the freeze: no code or config changes.

## Phase C / D: order and overlap
Order unchanged: responsiveness (C0, smoke test) -> avoidance -> exploration -> navigation.
**Phase D overlaps Phase C:** run `aggregate` + `make_report` for each finished campaign while the next one is running (read-only on finished folders), so the end-of-run reporting is short. Spot-checks (EIGHT_HOUR_PLAN §9.3) and the `METRICS_STATUS.md` update can also be done as each campaign finishes.

Rough budget (2 slots): A about 50 min, B 15 min, C about 2 h (resp 12, avoid 15, explore 50, nav 50), D finishing about 20 min after the last episode. Tight against the 4 h: if behind schedule, EIGHT_HOUR_PLAN §7 "behind schedule" applies (stop `run_batch` between episodes in `quick_navigation`; never skip responsiveness or avoidance).

## Limitations to state in the paper / final report
1. 4-hour budget: 25 test-split episodes, fewer than the 8-hour plan (41) and far fewer than the full pre-registered campaign (266). Per-world intervals are very wide; headline numbers are pooled across worlds (episode-level cluster bootstrap).
2. A15 noise robustness not measured (every exploration run has odometry noise on).
3. A2 and A3 skipped: no second-seed R1 confirmation, no gt-vs-slam navigation comparison.
4. Everything the 8-hour plan already drops (corridor, symmetric_hall, long_range goals, avoid_narrow_gap, avoid_dead_end, R6, R7).
5. Single machine, laptop-class 60 W GPU, headless EGL rendering.

## Deliverables
Same as EIGHT_HOUR_PLAN §11, plus: this file, `docs/SESSION_STATE.md` and `docs/EXECUTION_LOG.md` kept current, and `~/Swachh/progress/report_NN_HHMM.md` every 30 minutes, written by a single `*/30` cron of an observer session (do not create a second cron).
