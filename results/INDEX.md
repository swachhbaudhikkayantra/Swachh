# Results index (auto-generated 2026-10-25 18:24)

Light snapshot of `~/eval_runs` (no bags, no rtabmap.db). Full data stays on victus. Test-split campaigns are `quick_*`; `dev8h_*` are Phase A dev checks (not pooled); `_failed_attempts` are attempt-1 infra failures.

| experiment | world | method/stack | seed | status | valid | rtf | img_drop % | end_reason |
|---|---|---|---|---|---|---|---|---|
| _failed_attempts | quick_responsiveness | office | seed_101 | failed | True |  |  | bringup_failed |
| _failed_attempts | quick_responsiveness | office | seed_102 | failed | True |  |  | bringup_failed |
| dev8h_avoid | avoid_dynamic_cross | scripted_goals_scenario | seed_001 | ok | True | 1.01 | 9.48 | goals_done |
| dev8h_avoid | avoid_head_on | scripted_goals_scenario | seed_001 | ok | True | 1.003 | 3.69 | goals_done |
| dev8h_avoid_fix | avoid_dynamic_cross | scripted_goals_scenario | seed_001 | ok | True | 1.0 | 0.0 | goals_done |
| dev8h_avoid_fix | avoid_head_on | scripted_goals_scenario | seed_001 | ok | True | 1.0 | 0.0 | goals_done |
| dev8h_nav | apartment | scripted_goals_random20 | seed_001 | invalid | False | 1.002 | 7.83 | goals_done |
| dev8h_nav_amcl | apartment | scripted_goals_random20 | seed_001 | ok | True | 1.002 | 8.04 | goals_done |
| dev8h_r1 | apartment | frontier | seed_002 | ok | True | 1.002 | 8.71 | stuck |
| dev8h_resp | apartment | responsiveness_bare | seed_001 | invalid | False | 1.0 | 78.03 | goals_done |
| dev8h_resp | apartment | responsiveness_loaded | seed_001 | invalid | False | 1.003 | 10.36 | goals_done |
| dev8h_resp_fix | apartment | responsiveness_bare | seed_001 | invalid | False | 1.0 | 0.0 | goals_done |
| dev8h_resp_fix | apartment | responsiveness_loaded | seed_001 | ok | True | 1.0 | 0.0 | goals_done |
| dev8h_resp_fix | apartment | responsiveness_loaded | seed_001_attempt1_failed | failed | True | 1.0 |  | bringup_failed |
| quick_avoidance | avoid_dynamic_sudden | scripted_goals_scenario | seed_101 | ok | True | 0.852 | 0.0 | goals_done |
| quick_avoidance | avoid_dynamic_sudden | scripted_goals_scenario | seed_102 | ok | True | 0.813 | 0.0 | goals_done |
| quick_avoidance | avoid_dynamic_sudden | scripted_goals_scenario | seed_103 | ok | True | 0.804 | 0.0 | goals_done |
| quick_avoidance | avoid_u_trap | scripted_goals_scenario | seed_101 | ok | True | 1.0 | 0.0 | goals_done |
| quick_avoidance | avoid_u_trap | scripted_goals_scenario | seed_102 | ok | True | 1.0 | 1.34 | goals_done |
| quick_avoidance | avoid_u_trap | scripted_goals_scenario | seed_103 | ok | True | 0.997 | 0.0 | goals_done |
| quick_responsiveness | office | responsiveness_bare | seed_101 | invalid | False | 1.0 | 0.0 | goals_done |
| quick_responsiveness | office | responsiveness_bare | seed_102 | invalid | False | 0.926 | 0.0 | goals_done |
| quick_responsiveness | office | responsiveness_loaded | seed_101 | ok | True | 0.963 | 0.0 | goals_done |
| quick_responsiveness | office | responsiveness_loaded | seed_102 | ok | True | 1.0 | 0.0 | goals_done |
