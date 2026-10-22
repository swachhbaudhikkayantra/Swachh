# RUNBOOK: exact commands to finish all measurements

**Audience:** the user, running every step by hand. All code is written; this file is execution only. Background is in `docs/REQUIREMENTS.md`. Status lives in `docs/METRICS_STATUS.md`.

Run the steps **in order, one simulation at a time** (unless a step says `--parallel`). After each step, give Claude the run folder path. It will verify the numbers (accuracy, method, whether they're bad) and update `METRICS_STATUS.md`.

## 0. Every new terminal

```bash
source /opt/ros/jazzy/setup.bash
source ~/Swachh/Navigation/Simulation/vacuum_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp CYCLONEDDS_URI=file://$HOME/Swachh/Navigation/cyclone_dds.xml ROS_DOMAIN_ID=0
cd ~/Swachh/Navigation/Simulation/vacuum_ws/src/vacuum_eval
bash ~/Swachh/Navigation/Simulation/scripts/preflight.sh     # every line must say PASS before you start
```

If `rmem_max` FAILs after a WSL restart, run this once:
`wsl.exe -d Ubuntu -u root -e sysctl -p /etc/sysctl.d/90-ros2-dds.conf`.
If preflight lists stray `gz sim` or `ruby` processes, close them with `kill <PID>` using the listed PIDs, then re-run preflight.

**Helper used after every episode.** Paste this once per terminal. `RUN` is the run folder the harness prints on its last line.

```bash
post() { python3 -m vacuum_eval.compute_metrics "$1" && python3 -m vacuum_eval.diagnose "$1" --png "$1/diagnose.png"; }
```

## 1. Optional speed check (about 5 min; do it once)

```bash
bash ~/Swachh/Navigation/Simulation/scripts/check_gpu_render.sh --gz ~/Swachh/Navigation/Simulation/vacuum_ws/install/vacuum_gazebo/share/vacuum_gazebo/worlds/apartment.sdf --secs 60
```

- If the verdict shows `d3d12 renderer active=yes` and a speed-up of 1.3× or more, add `--gpu 1` to **every** command below, from step 2 onward.
- Never mix runs with and without `--gpu` in one experiment; `aggregate` keeps them apart.
- If you decide on GPU, re-run step 2 with `--gpu 1` so the dev baseline matches.

## 2. R1 confirmation (2 episodes, about 40 min each)

```bash
python3 -m vacuum_eval.run_episode --experiment r1confirm --world apartment --method frontier --seed 2 --odom-noise 0 --headless 1 --timeout-sim-sec 600
post ~/eval_runs/r1confirm/apartment/frontier/seed_002
python3 -m vacuum_eval.run_episode --experiment r1confirm --world apartment --method frontier --seed 1 --odom-noise 0 --headless 1 --timeout-sim-sec 600
post ~/eval_runs/r1confirm/apartment/frontier/seed_001
```

Check in each `summary.json`:
- `episode_valid` is true.
- `odom_corrupted_by_contact` is 0.
- `ate_improvement_pct` > 0.
- `n_collisions` is low.

Also compare `nav_success_gt_pct` against pilot 2's 15.4 %.

**Stopping rule (fixed in advance):** if either run has `odom_corrupted_by_contact = 1`, or a Spin happened while the robot was touching something, stop and tell Claude. The next fix would be the axle offset or a contact-aware recovery.

## 3. R2 loop-closure direction (2 min, no simulation)

```bash
python3 -m vacuum_eval.check_lc_direction ~/eval_runs/r1confirm/apartment/frontier/seed_00*
```

Pilot 2 already showed that `loop_to_ref` is correct (0.032 m vs 0.699 m median error). This step re-confirms it on the new runs. The verdict should name `loop_to_ref`.

## 4. R3 scripted navigation (6 episodes, about 25 min each)

Ground-truth, AMCL and SLAM localization, each on seeds 1 and 2. The `gt` mode has never run live; if it fails at start-up, send Claude `logs/` from that run folder.

```bash
for loc in gt amcl slam; do for s in 1 2; do
  python3 -m vacuum_eval.run_episode --experiment r3nav --world apartment --method scripted_goals --goal-list random20 --nav-map gt --localization $loc --seed $s --odom-noise 0 --headless 1
done; done
for d in ~/eval_runs/r3nav/apartment/*/seed_*; do post $d; done
```

Look at `nav_success_gt_pct`, `path_length_ratio_mean` and `loc_error_mean_m` (AMCL). **gt vs amcl vs slam** shows how much of the navigation failure is localization and how much is the planner.

## 5. R4 responsiveness (2 episodes, about 10 min each)

```bash
python3 -m vacuum_eval.run_episode --experiment r4resp --world apartment --method responsiveness --stack bare   --seed 1 --headless 1
python3 -m vacuum_eval.run_episode --experiment r4resp --world apartment --method responsiveness --stack loaded --seed 1 --headless 1
for d in ~/eval_runs/r4resp/apartment/*/seed_001; do post $d; done
```

Check:
- `resp_definition` = `wall_clock_controller_latency`.
- `lat_cmd_motion_ms_mean` and `lat_stop_ms_mean` are present.
- `wall_latency_s` is filled in `responsiveness_events.csv`.

## 6. R5 avoidance scenarios, dev split (3 worlds × 3 trials, about 5–8 min each)

These worlds have never been launched. Run the first one alone and check it before looping.

```bash
python3 -m vacuum_eval.run_episode --experiment r5avoid --world avoid_head_on --method scripted_goals --goal-list scenario --nav-map gt --seed 1 --headless 1
post ~/eval_runs/r5avoid/avoid_head_on/scripted_goals*/seed_001
```

If that looks sane (`trial_success` present, `collision_source` = contact when contacts happen), run the rest:

```bash
for w in avoid_head_on avoid_cluster avoid_dynamic_cross; do for s in 1 2 3; do
  python3 -m vacuum_eval.run_episode --experiment r5avoid --world $w --method scripted_goals --goal-list scenario --nav-map gt --seed $s --headless 1
done; done
for d in ~/eval_runs/r5avoid/*/*/seed_*; do post $d; done
```

For `avoid_dynamic_cross`, check that `dyn_obstacles.csv` has rows; it tracks the moving box.

## 7. R6 loop closures on a dev world (1 episode, about 55 min)

```bash
python3 -m vacuum_eval.run_episode --experiment r6loop --world apartment --method frontier --seed 3 --odom-noise 1 --headless 1 --timeout-sim-sec 900
post ~/eval_runs/r6loop/apartment/frontier/seed_003
python3 -m vacuum_eval.check_lc_direction ~/eval_runs/r6loop/apartment/frontier/seed_003
```

Check `lc_n_accepted` > 0, `lc_precision_pct` and `lc_recall_pct`. **Open question for the council:** pilot 2's closures had a median rotation error of 5.2°, just above the 5° tolerance.

## 8. R7 size the campaign (no simulation)

Run a few more dev seeds first if needed (at least 3 per configuration), then:

```bash
python3 -m vacuum_eval.plan_sample_size --from-root ~/eval_runs/r1confirm --metric ate_fixed_rmse_m --metric-kind continuous --target-halfwidth 0.05
python3 -m vacuum_eval.plan_sample_size --from-root ~/eval_runs/r3nav --metric nav_success_gt_pct --metric-kind proportion --target-halfwidth 0.10
```

Give Claude the outputs. It sets the seed counts in `config/campaigns/final_*.yaml`, through a council decision if the campaign exceeds about 48 h.

## 9. R8 test-split campaign (the long part)

**After this starts, nothing may be tuned.** Before starting, tell Claude so it can freeze `docs/specs/13_preregistration.md`.

```bash
bash ~/Swachh/Navigation/Simulation/scripts/preflight.sh          # note the suggested --parallel value
python3 -m vacuum_eval.run_batch --matrix config/campaigns/final_exploration.yaml --prebuild-gt --dry-run
for c in final_exploration final_navigation final_avoidance final_responsiveness; do
  python3 -m vacuum_eval.run_batch --matrix config/campaigns/$c.yaml --split test --confirm-test-split --parallel 1 --lean 1
done
```

- **Parallel:** on this laptop keep `--parallel 1` unless the GPU check passed, then try 2. On a workstation (A6000), use the value `preflight.sh` suggests.
- **Interruptions are safe:** `run_batch` skips finished episodes, so re-run the same command to resume.
- **Every 5–10 episodes:** run `post` on the new folders and send Claude any with `status` ≠ ok.
- **Wall time:** about 40 min per 600 s episode at RTF 0.3. Expect several days on this laptop, or about 1 night on an A6000 workstation (set up with `scripts/setup_machine.sh`).

## 10. R9 aggregate and report

```bash
for e in final_exploration final_navigation final_avoidance final_responsiveness; do
  python3 -m vacuum_eval.aggregate --root ~/eval_runs/$e --out ~/eval_runs/$e/aggregate.csv
  python3 -m vacuum_eval.make_report --root ~/eval_runs/$e --out ~/eval_runs/$e/report
done
```

Results: `~/eval_runs/<exp>/report/results.md`, plus `figures/` and `metrics_status_update.md` (paste it into `docs/METRICS_STATUS.md`). Give Claude the four report folders for the final verification pass (council or an independent agent): accuracy, method, and whether each result is bad.

## 11. If a metric is bad or unmeasurable

Look at `health_<metric>` and `health_<metric>_reasons` in `summary.json` (statuses: OK, LOW_N, UNMEASURABLE, SUSPECT, BAD, NA; precedence UNMEASURABLE > SUSPECT > LOW_N > BAD > OK). Then follow `docs/FAILURE_MODES.md`:

1. Find the metric's table and the reason code; run the first diagnostic step listed there (usually `diagnose` on the episode folder).
2. Infrastructure fault (image drops, crashed node, missing map or bag): re-run that episode once with the same seed; both attempts are reported.
3. Everything else is reported as measured. Never re-run to improve a number. Health flags never exclude an episode.
4. Use the fallback key named in the table when one exists, next to the headline.
5. Unclear cause: send Claude the episode folder; it goes to the council or to you (FAILURE_MODES.md section 5).
