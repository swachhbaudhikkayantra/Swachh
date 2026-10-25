# Test-split results so far (auto-generated 2026-10-25 20:16)

Only `quick_*` (test split). Values: mean [min-max] over the *valid* episodes; invalid episodes are counted but excluded from statistics. Flags: counts of non-OK health statuses over all episodes of the group (L=LOW_N, S=SUSPECT, B=BAD, U=UNMEASURABLE; n= episodes in that status). Pooled CIs come from the final report; here n is tiny.

| campaign | world / stack | n | valid | rtf_true_mean | coverage | completeness | ATE m | RPE m/1m | LC prec % | nav GT % | collisions | path ratio |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| quick_avoidance | avoid_dynamic_sudden/scen | 3 | 3 | 0.804-0.852 | – **U×3** | – **U×3** | 0.20 [0.16-0.25] **S×1** | 0.25 [0.21-0.30] **S×1** | – **U×3** | 66.7 [0.00-100.0] **L×2 S×1** | 0.33 [0.00-1.00] | 2.02 [1.58-2.47] **L×3** |
| quick_avoidance | avoid_u_trap/scen | 3 | 3 | 0.997-1.000 | – **U×3** | – **U×3** | 0.07 [0.06-0.07] | 0.08 [0.07-0.08] | – **U×3** | 100.0 [100.0-100.0] **L×3** | 0.00 [0.00-0.00] | 1.08 [1.07-1.09] **L×3** |
| quick_exploration_noise | maze_dead_ends/frontier | 3 | 3 | 0.999-1.000 | 14.3 [1.17-39.9] **B×2 S×1** | 11.9 [1.69-31.8] **B×2 S×1** | 0.76 [0.76-0.76] **U×2 S×1** | 0.30 [0.30-0.30] **U×2 S×1** | 94.3 [94.3-94.3] **U×2** | 11.1 [11.1-11.1] **U×2 B×1** | 0.67 [0.00-2.00] | 1.05 [1.05-1.05] **U×2 L×1** |
| quick_exploration_noise | multi_room_loop/frontier | 3 | 3 | 0.738-0.750 | 86.3 [82.6-88.6] **S×3** | 65.4 [59.2-68.9] **S×3** | 0.74 [0.40-0.97] **S×3** | 0.35 [0.12-0.67] **S×2** | 25.9 [8.74-52.4] **B×2** | 8.96 [6.67-11.1] **B×3** | 3.67 [0.00-6.00] | 1.72 [1.32-2.07] **L×2** |
| quick_exploration_noise | office/frontier | 3 | 3 | 0.729-0.753 | 83.8 [71.5-91.6] **S×1** | 65.9 [45.9-78.0] **S×1 B×1** | 0.35 [0.13-0.51] **S×1 B×2** | 0.13 [0.11-0.15] **S×1** | 28.5 [20.0-38.8] **B×3** | 8.38 [5.26-13.6] **B×1 S×2** | 1.00 [0.00-2.00] | 1.49 [1.37-1.56] **L×1** |
| quick_navigation | maze_dead_ends/scripted_goals_random20 | 4 | 4 | 0.999-1.000 | – **U×4** | – **U×4** | 0.67 [0.54-0.96] **S×3 B×1** | 0.27 [0.10-0.62] **S×2** | – **U×4** | 2.78 [0.00-11.1] **B×4** | 3.00 [0.00-7.00] | 1.09 [1.09-1.09] **L×1 U×3** |
| quick_navigation | office/scripted_goals_random20 | 4 | 4 | 1.000-1.000 | – **U×4** | – **U×4** | 0.28 [0.23-0.32] **S×2** | 0.30 [0.24-0.38] | – **U×4** | 18.8 [0.00-25.0] **B×4** | 0.75 [0.00-3.00] | 1.19 [1.13-1.25] **L×2** |
| quick_navigation | two_rooms_door/scripted_goals_random20 | 4 | 4 | 1.000-1.000 | – **U×4** | – **U×4** | 0.20 [0.18-0.21] **S×3** | 0.23 [0.22-0.25] **S×2** | – **U×4** | 48.8 [40.0-65.0] **S×1 B×1** | 2.00 [2.00-2.00] | 1.26 [1.15-1.36] |
| quick_responsiveness | office/bare | 2 | 0 | 0.926-1.000 | – **U×2** | – **U×2** | – **U×2** | – **U×2** | – **U×2** | – **U×2** | – **U×2** | – **U×2** |
| quick_responsiveness | office/loaded | 2 | 2 | 0.963-1.000 | 54.1 [48.5-59.7] **B×2** | 38.3 [33.9-42.8] **B×2** | 0.11 [0.11-0.11] | 0.14 [0.14-0.14] | 76.3 [69.2-83.3] | – **U×2** | 0.00 [0.00-0.00] | – **U×2** |

**rtf_true_mean range over 31 test episodes: 0.729-1.000. Episodes below 0.7 (LOW_RTF, SUSPECT, not excluded): none**

## Per-episode rtf_true_mean and status

| campaign | world/stack | seed | status | valid | rtf | img_drop % |
|---|---|---|---|---|---|---|
| quick_avoidance | avoid_dynamic_sudden/scripted_goals_scenario | seed_101 | ok | True | 0.85 | 0.00 |
| quick_avoidance | avoid_dynamic_sudden/scripted_goals_scenario | seed_102 | ok | True | 0.81 | 0.00 |
| quick_avoidance | avoid_dynamic_sudden/scripted_goals_scenario | seed_103 | ok | True | 0.80 | 0.00 |
| quick_avoidance | avoid_u_trap/scripted_goals_scenario | seed_101 | ok | True | 1.00 | 0.00 |
| quick_avoidance | avoid_u_trap/scripted_goals_scenario | seed_102 | ok | True | 1.00 | 1.34 |
| quick_avoidance | avoid_u_trap/scripted_goals_scenario | seed_103 | ok | True | 1.00 | 0.00 |
| quick_exploration_noise | maze_dead_ends/frontier | seed_101 | ok | True | 1.00 | 0.00 |
| quick_exploration_noise | maze_dead_ends/frontier | seed_102 | ok | True | 1.00 | 0.00 |
| quick_exploration_noise | maze_dead_ends/frontier | seed_103 | ok | True | 1.00 | 0.00 |
| quick_exploration_noise | multi_room_loop/frontier | seed_101 | ok | True | 0.74 | 0.00 |
| quick_exploration_noise | multi_room_loop/frontier | seed_102 | ok | True | 0.74 | 0.00 |
| quick_exploration_noise | multi_room_loop/frontier | seed_103 | ok | True | 0.75 | 0.00 |
| quick_exploration_noise | office/frontier | seed_101 | ok | True | 0.75 | 0.00 |
| quick_exploration_noise | office/frontier | seed_102 | ok | True | 0.74 | 0.00 |
| quick_exploration_noise | office/frontier | seed_103 | ok | True | 0.73 | 0.00 |
| quick_navigation | maze_dead_ends/scripted_goals_random20 | seed_101 | ok | True | 1.00 | 0.00 |
| quick_navigation | maze_dead_ends/scripted_goals_random20 | seed_102 | ok | True | 1.00 | 0.00 |
| quick_navigation | maze_dead_ends/scripted_goals_random20 | seed_103 | ok | True | 1.00 | 0.00 |
| quick_navigation | maze_dead_ends/scripted_goals_random20 | seed_104 | ok | True | 1.00 | 0.00 |
| quick_navigation | office/scripted_goals_random20 | seed_101 | ok | True | 1.00 | 0.00 |
| quick_navigation | office/scripted_goals_random20 | seed_102 | ok | True | 1.00 | 0.00 |
| quick_navigation | office/scripted_goals_random20 | seed_103 | ok | True | 1.00 | 0.00 |
| quick_navigation | office/scripted_goals_random20 | seed_104 | ok | True | 1.00 | 0.00 |
| quick_navigation | two_rooms_door/scripted_goals_random20 | seed_101 | ok | True | 1.00 | 0.00 |
| quick_navigation | two_rooms_door/scripted_goals_random20 | seed_102 | ok | True | 1.00 | 0.00 |
| quick_navigation | two_rooms_door/scripted_goals_random20 | seed_103 | ok | True | 1.00 | 0.00 |
| quick_navigation | two_rooms_door/scripted_goals_random20 | seed_104 | ok | True | 1.00 | 0.00 |
| quick_responsiveness | office/responsiveness_bare | seed_101 | invalid | False | 1.00 | 0.00 |
| quick_responsiveness | office/responsiveness_bare | seed_102 | invalid | False | 0.93 | 0.00 |
| quick_responsiveness | office/responsiveness_loaded | seed_101 | ok | True | 0.96 | 0.00 |
| quick_responsiveness | office/responsiveness_loaded | seed_102 | ok | True | 1.00 | 0.00 |

## Avoidance and responsiveness specifics

- avoid_dynamic_sudden: 101 trial_success=0 coll=1 src=contact goals Nav2 1/1, GT-reached 100.0%; 102 trial_success=0 coll=0 src=geometry goals Nav2 1/1, GT-reached 0.0%; 103 trial_success=1 coll=0 src=geometry goals Nav2 1/1, GT-reached 100.0%
- avoid_u_trap: 101 trial_success=1 coll=0 src=geometry goals Nav2 1/1, GT-reached 100.0%; 102 trial_success=1 coll=0 src=geometry goals Nav2 1/1, GT-reached 100.0%; 103 trial_success=1 coll=0 src=geometry goals Nav2 1/1, GT-reached 100.0%
- responsiveness_bare: 101 invalid cmd->motion 162.5 ms, stop 248.2 ms (health None); 102 invalid cmd->motion 179.5 ms, stop 264.1 ms (health None)
- responsiveness_loaded: 101 ok cmd->motion 171.7 ms, stop 270.4 ms (health None); 102 ok cmd->motion 160.4 ms, stop 249.7 ms (health None)
