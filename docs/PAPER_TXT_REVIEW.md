# Review of paper.txt against the repository, the run results and the earlier draft

**Written for:** the paper authors, as a fix list before submission.

**How it was checked.** `paper.txt` (1,176 lines) was read in full. Three independent read-only reviewers then checked lines 48-450, lines 452-655 plus 879-1072, and lines 658-846 plus 1074-1131 against the repository, the raw result files and the earlier PDF draft. All arithmetic was done in code. **V** marks a finding I re-verified myself from raw files after the reviewers reported it; **R** marks a finding taken from a reviewer's evidence. Line numbers are `paper.txt` lines.

**Verification.** An independent adversarial critic then recomputed every number in the new sections and re-checked 15 of the items below; its corrections are applied, and its extra findings are in section 7.

**Replacement text** for the navigation results is in `docs/paper_out/sections_fixes.tex`, and the new sections D and E are in `docs/paper_out/sections_D_E.tex`. Every number in both files is filled by script from `docs/paper_out/paper_values.json`.

---

## 1. Wrong or inconsistent claims (fix these first)

| # | Line | Problem | Evidence | By |
|---|---|---|---|---|
| 1 | 967, 996-1017 | The RF-DETR per-class table is labelled "AP@0.5 at the final epoch", but the values are **AP@0.5:0.95**. Their mean is 0.81597, identical to the epoch-99 mAP@0.5:0.95 (0.81597). A true per-class AP@0.5 would average 0.9195 | `Object Detection/Metrics/rfdetr_metrics.csv`, epoch 99 | V |
| 2 | 972, 983-987 | The RF-DETR headline numbers are **maxima over epochs chosen on the validation set**, each from a different epoch (mAP@0.5 0.9336 at epoch 16, EMA 0.9323 at epoch 14, mAP@0.5:0.95 0.8387 at epoch 12 and EMA 0.8432 at epoch 14, mAP@0.75 0.8795 at epoch 12), while precision 0.9271 and recall 0.8935 are from epoch 99. At epoch 99 mAP@0.5 is **0.9195 (below the 0.92 the text claims for every model)**. State which checkpoint is reported, or report the final epoch | same csv | V |
| 3 | 916-918, 983-987, 1037-1068 | The same models have **different numbers in three tables**. YOLOv8n mAP@0.5 is 0.9209 (edge-acc, "validation"), 0.9271 (overall, "validation, 175 images") and 92.09 (per-class, "Test Set"). The per-class YOLO AP means equal the edge-acc values, so the "Test Set" table is probably the validation split mislabelled. The RF-DETR per-class mean is 82.61, 10 points below its quoted mAP@0.5 | reviewer arithmetic; RF-DETR mean V | R, V |
| 4 | 1048 | RF-DETR cement_dust F1 is printed as 90.91. From P = 87.22 and R = 85.37 it is **86.29**. All other F1 cells agree within 0.1 | recomputed in code | V |
| 5 | 882-948 | The edge section is **not a Jetson result**. It uses an unnamed "test machine" (the comment says hostname DESKTOP-SU3OTED) with peak CPU of 1209.8%, and INT8 is slower than FP32 there. The Jetson benchmark in `docs/PROJECT_CONTEXT.md` shows the opposite: YOLOv8 INT8 TensorRT 12.89 ms and 77.6 FPS, against 187.56 ms on the CPU, and the YOLOv11-seg INT8 build fails. The section also recommends YOLOv11n-seg for the edge although no INT8 engine exists for it on the Jetson. Name the platform and runtime of every row, or replace the section with the Jetson results | `docs/PROJECT_CONTEXT.md`, `Object Detection/Metrics/benchmark_results.csv` | R |
| 6 | 1100 | "We did not measure the trajectory error of wheel odometry alone" is **wrong**. Over the same 7 episodes the odometry-only error averaged **2.54 m** against 0.57 m for SLAM, a mean reduction of 72% (per-episode 14% to 94%), including all four contact-corrupted episodes. The baseline contains the injected noise. Use F1 in `sections_fixes.tex` | `ate_odom_fixed_rmse_m`, `ate_improvement_pct` in the exploration summaries | V |
| 7 | 1079 | "The cause of this behaviour has not yet been identified" is outdated. It was diagnosed: the start-up spin stops when the first map arrives, the robot faces a wall, the goal-snap step treats unknown cells as blocked, the only frontier is blacklisted, and there is no fallback. Use F2 | `docs/EVALUATION_FINDINGS_2026-10-25.md` section 4 | R |
| 8 | 1127 | "The AMCL pose placed the footprint inside an obstacle while the true pose was in free space" holds for the office episodes analysed, not in general. Over 1242 events, 36% were localisation error, 60% had the robot genuinely near a wall, and 4% were unexplained. The last sentence ("localisation set-up more than the planner") needs the same softening. Use F3 | `docs/EXECUTION_LOG.md` (verifier entry), findings section 3 | R |
| 9 | 684 | "The same height range is used by ... the ground-truth rasteriser" is wrong: the rasteriser uses 0.03 to 0.25 m (code default; the 0.30 m config value is never passed). Rebuilding all six test grids with both limits gives identical grids, so no result changes. Use F4 | `gt_grid.py:14-15`, `compute_metrics.py:90` | V |
| 10 | 501 vs 497 | "Expanded the training set three times, which gave 2619 images": 611 x 3 = 1833, while 2619 = 873 x 3, the whole dataset. This contradicts "augmentation only after the split" | arithmetic | R |
| 11 | 484 | The class table totals **877** images, against 873 in the text and the 611/175/87 split. It lists 6 classes, while the rest of the paper uses 8. The "four functional classes described above" (line 497) are never described. The table spec `{\|c\|c\|c\|}` has three columns for two | arithmetic | R |
| 12 | 896 vs 965 | YOLOv11n-seg input is 576 in the table but 560 in the text (the benchmark csv says 576). Epochs are 100 in the table but 60 with early stopping in the text. RF-DETR epochs are 100 in the table and 99 in the text (the csv is 0-indexed: epochs 0 to 99 are 100 epochs). Line 963 adds perspective warping, which the Augmentation subsection (501-504) does not list | training_config.json, csv | R |
| 13 | 285 | New error: the track width is written **0.286** m (the model is 0.268, as in line 668), and the symbol is "s" while the equations use L | URDF `_properties.xacro:48` | R |
| 14 | 146 vs 665-678 | The architecture describes a "Visual Odometry sub-module" estimating the robot's position. Section 5.1 says wheel odometry is the sole odometry source and no visual odometry node runs | `slam.launch.py`, `rtabmap.yaml` | R |
| 15 | 57 | "Omnidirectional mobility" contradicts the differential drive (two rear hub motors and a caster) described elsewhere and used by MPPI | line 188, `nav2_params.yaml` | R |
| 16 | 309 | Obstacle avoidance still "utilises the Dynamic Window Approach", while lines 263 and 780 say MPPI | `nav2_params.yaml` | R |
| 17 | 144, 208, 288 | The camera is 1280 x 720 at 30 fps in two places and "1080x720p" in a third. The vision configuration reads 640 x 480 at 10 fps. The vision code builds depth from a stereo pair of two USB cameras, not from a D435i | `vision/config.yaml`, `depth.py`, `calib.sh` | R |
| 18 | 318 | "Moving forward by 30 cm, turning right by 15 degrees" does not match the firmware, which has only continuous `MOVE:*` commands, `SPEED`, and peripheral toggles. "Mopper" has no firmware command | `swacch_robot.ino` | R |
| 19 | 248, 273 | "D430i" (should be D435i), repeated | | R |
| 20 | 265 | Recovery is described as a "fixed order (clear costmaps, backup, rotate, wait)". It is one action per failure in rotation, and the navigation tree used for the 12 navigation episodes has **no back-up** | `behavior_trees/*.xml` | R |

## 2. Omissions that a reviewer will notice

| # | Line | Missing | Fix |
|---|---|---|---|
| 21 | 782-818 | The planning table omits tuned Smac settings: **analytic-expansion cost limit 3.5 (default 200.0)** and **reverse penalty 2.1 (default 2.0; inactive with the forward-only Dubins model, so list it as inactive or leave it out)**, both confirmed against the Nav2 Jazzy source. One reviewer also listed `non_straight_penalty` and `analytic_expansion_max_length` as tuned, based on header-file struct defaults. The node declares defaults of 1.2 and 3.0, which our values equal, so **do not add those two** | add two rows |
| 22 | 685-714 | The RTAB-Map table omits `Kp/DetectorStrategy` 6 (GFTT/BRIEF) | add a row |
| 23 | 1090-1094 | Maze ATE 0.76 and RPE 0.30 come from **one episode**, and the pooled 0.57 m is a 7-episode mean (two maze episodes have no value). Maze loop-closure precision (94.3%) is also one episode | state n in the table note |
| 24 | 1081-1124 | Interval methods are not stated. Per-world intervals use 3 or 4 episodes, and pooled ones use a world-then-seed bootstrap with three clusters. The goal-pooled rate uses an episode bootstrap. Use F6 | add a sentence |
| 25 | 1106 | Seeds 103 and 104 of the navigation campaign were added after the freeze, at the user's request, once the office results of seeds 101 and 102 had been analysed (the extra episodes started after all 101 and 102 episodes had finished). 184 goals were sent; 6 unfinished goals are **excluded** from the 178-goal denominator (counting them as failures would give 28.3% instead of 29.2%). The recorder fix and the goal-start tolerance are not mentioned. Use F5 | add a paragraph |
| 26 | 1130 | The commented-out limitations paragraph holds the key caveats (simulation only, base smaller than the real robot, no sensor noise, shortened campaign, load effects). **Restore it** | un-comment |
| 27 | 960-967 | There is no setup description for the simulation (robot model, worlds, camera, validity rules, statistics, host). The earlier text for it is in `docs/PAPER_SECTIONS_5_7_VERIFIED.md` section 7.1 | add |
| 28 | 830-845 | Table 5 and the Decision section do not say that the firmware lacks `ARM:PICK` and that the vision prototype uses a generic detector. Section 3 says the module "fuses" all outputs | add an implementation-status note |

## 3. Unsupported statements

| Line | Statement | Status |
|---|---|---|
| 996 | Dust classes are "easy to confuse with one another" and have "diffuse, texture-defined" boundaries | no confusion data shown |
| 992 | RF-DETR is "more conservative" | an interpretation; YOLOv8n has higher precision and recall |
| 996 | Foil, floor, wrapper and bottle are detected well because of "reflective properties" | no evidence |
| 235-240 | Return-to-charge routine, spoken "STOP" and a web interface | not found in the repository |
| 1100 | "RTAB-Map did not recover" from corrupted odometry | supported only for a development run; in the test data the SLAM error was still below the odometry error in all four corrupted episodes |
| 944 | Latency standard deviations "1.6 to 6.4 ms" | the table gives 1.56 to 6.45 |
| 965 | "Single RTX A6000" | no GPU is recorded in the repository (the training config shows a Windows path) |

## 4. LaTeX and structure problems (all unchanged from the draft unless marked)

- Lines 292-298: the outer `itemize` is never closed.
- Lines 300-314: "The Mapping module is" is truncated and followed by repeated paragraphs, one of which still has `[REQUIRES MORE INFO]`. The sentence "i.e a simple instruction" is unfinished (new).
- Lines 188-193 and 196-201: the mechanical description appears twice, and its "- Bottom rack" lines are literal hyphens, not a list.
- Lines 239, 240, 206, 238: a dangling "Figure" (new) and the placeholders `[ADD CAMERA SPECS]`, `[MENTION HERE THE VALUE ...]` and `[INSERT LINK & IMAGE]`.
- Line 343: the sentence introducing Table `tab:specs` is stranded at the end of Operating Modes.
- Line 73: "The results show promising perforamcne with a" ends mid-sentence. Lines 36-46 still have the abstract and keyword placeholders.
- Table 1 (lines 165-182) keeps the draft's inconsistencies: payload 20 kg against a 50 kg capacity in the text, "wheel weight 20 kg", "12 V DC Servo Motors" against 6-inch BLDC hub motors, "360oC", "3 fts", 1.5 ft (45.7 cm) against 50 cm, "Number of rotation cycles 10", and RGB webcams that omit the D435i.
- The figure files `SBY ARCHI.png`, `Flowchart.jpeg` and the dataset sample images could not be checked.

## 5. Checked and correct

- **Result tables.** Every cell of both result tables (`tab:slam_results`, `tab:nav_results`, about 70 cells with intervals) and every number in the prose of 1079-1106 match the computed values and the raw episode files. The explorer parameters, the utility function and the algorithm match the code, the Nav2 and RTAB-Map values match the configs, and the tuned or default labels in both parameter tables are right for the rows that exist.
- **Arithmetic elsewhere.** The 6,349 annotations, the 21.7 factor, the 611/175/87 split, the 450-trial grid and its six days, FPS = 1000 / latency, the 21 to 22 times size ratio, the 3 to 4 times latency ratio, and the 90%, 85% and 7% reductions are all correct.
- **Serial protocol.** 115200 baud, 8N1, newline-terminated ASCII, acknowledgement per command and a 1 Hz status message match the firmware.

## 6. Differences from the text I wrote earlier

The paper adopted my wording for 5.1, 5.2 and the navigation results, and then **did not adopt** these corrections: the 3.8 rewrite (firmware commands, camera, stereo depth, the decision module as design intent), the maze cause, the start-occupied shares, the odometry comparison, the GT-band fix, and the Smac settings (reverse penalty, analytic-expansion cost). These are the items in sections 1 and 2 above.

## 7. Further discrepancies found by the critic (not in the tables above)

| Line | Problem |
|---|---|
| 737, 745 | The robot "rotates at 0.4 rad/s for 8 s". The code stops the spin as soon as a map with free cells arrives (about 0.8 rad). This contradicts the maze explanation, so use F7 |
| 780 | Only the smoother limits (2.5 m/s^2, 3.2 rad/s^2) are given; the tighter diff-drive controller limits (1.0 m/s^2, 2.0 rad/s^2) are the ones behind the 166 and 260 ms responses |
| 265, 720, 777 | The voxel layer's clearing frustum is configured at 86 degrees while the simulated depth camera has 69.4 degrees, so cells in the unseen side wedges are cleared |
| 684 | The Nav2 obstacle source is a five-row scan at about 0.18 m camera height, so the 0.03 to 0.30 m band is nominal (see F4) |
| 246 vs 681, 720 | Section 3 says memory transfer to long-term memory matters on the Jetson; Section 5 says no transfer occurs and nothing ran on the Jetson. Line 120 ("all navigation executed locally, ensuring low latency") is unsupported |
| 580, 597, 602, 611 | YOLOv8s is described and drawn as the deployed model, but all results and the Jetson benchmark are YOLOv8n (the vision configuration loads a YOLOv8s file) |
| 587 | YOLOv8 is given an objectness term, which it does not have (it is anchor-free, as lines 582 and 589-595 say) |
| 1106 | "178 goals in total": 184 were sent (see item 25) |
| 916-918 vs 983-986 | Beyond item 3: precision, recall and mAP@0.5:0.95 differ for every model; the edge table's RF-DETR mAP@0.5 (0.9323) is the EMA maximum at epoch 14, the overall table's (0.9336) is the regular maximum at epoch 16; the edge table's RF-DETR F1 (0.9075) does not match its own precision and recall (0.9089) |
| 820 | Implies the evaluation threshold is 0.15 m; the primary ground-truth check uses 0.30 m, so the 50.0% against 29.2% gap is not a tolerance effect |
| 611 vs 944, 948 | RF-DETR "targets the same real-time operating point as YOLOv8s and YOLOv11n", but the results show it 3 to 4 times slower |
| 668 | "Update rate of 30 Hz" is the odometry publish rate; the controller update rate is 50 Hz |
| 1077 | "Two experiments were performed": with sections D and E there are four campaigns |
| avoidance interval | The avoidance success rate has two intervals in the project files: Wilson 30.0 to 90.3% (used in section D) and a cluster bootstrap 16.7 to 100% (in the audit). State which one is used. The navigation planning-latency median in the findings (10 ms) is a different definition from the 8 ms in section D (goals that received a plan) |

## 8. Cautions about the new sections D and E

- The memory figure is a host-wide sum over concurrent simulations, so section E says it could not be isolated.
- The planning-latency distribution has censored goals (62 never got a plan); section D reports counts for all 184 goals.
- The obstacle-response value of 16 ms in seed 103 is an artefact of the trigger rule; section D says so.
- The Jetson benchmark ran on stored frames with ONNX Runtime and the TensorRT provider, without a camera; the L4T release is documented but the JetPack version is not.
- Delete the old subsection headings and the placeholder table (paper.txt lines 1133-1155) when inserting sections D and E, or the label `tab:latency` is defined twice.
