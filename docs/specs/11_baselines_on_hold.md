# 11 — Coverage Method Comparison (#13) — ON HOLD

**Status: ON HOLD by user decision (2026-10-20). Do not implement baselines.** This file only fixes the interface so that the harness built in spec 02 does not need to change when the user supplies definitions.

The user has not yet defined the methods "modified A*", "SLAM + B. A*" (B. A* may mean bidirectional or boustrophedon A*), "GA + neural net", "etc." Open questions to ask when un-parking:

1. Is each method a global *path planner* inside Nav2, or a *coverage* planner producing a sweep order/goal sequence?
2. For GA + NN: what does the network consume/produce (map → goal sequence? local steering)? Is it trained, and on what?
3. Are they run with SLAM (map built online) or on a known map?
4. What is "etc."?

## 11.1 Plug-in contract (harness side, already part of spec 02)

A method is a Python class in `vacuum_eval/methods/<name>.py`:
```
class Method:
    name: str                                 # directory name under ~/eval_runs/<exp>/<world>/<name>/
    def launch_specs(self, ctx) -> list[ProcessSpec]   # processes beyond the common sim/slam/eval stack
    def end_signal_topic(self) -> str                  # '/exploration/finished' | '/eval/done'
    def requires_map(self) -> str                      # 'slam' | 'gt' | 'none'
```
and publishes its goals/paths through the **same** Nav2 `NavigateToPose` interface (or documents why not), emitting `goal_events` in the JSON schema of spec 01 §1.5.5 on `/eval/goal_events` so that spec 05 metrics work unchanged. The `frontier` method is the reference implementation.

## 11.2 Fairness rules for the comparison (fix now, apply later)

Same worlds, spawn poses (same seeds), Nav2 controller and parameters, robot, sensors, odometry noise setting, timeout; only goal generation/path logic may differ. Report all metrics of specs 03–10 per method plus `aggregate.py` paired tests (spec 02 §2.9).

## 11.3 Metrics specific to coverage planners (to add when un-parked)

Coverage planners produce an intended path; add `plan_vs_executed_deviation_m` (mean distance between planned coverage path and GT trajectory). Everything else is already covered by `coverage_*`, `cleaning_efficiency`, `overlap_ratio`.
