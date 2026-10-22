# Council: 22 October 2026, 03:19

## Original question

R1 (evaluate pilot 2): around t=310-325 s odometry yaw jumps ~125 deg vs ground truth and SLAM follows it, after chair_1 contacts. Decide with evidence whether this is a simulation artefact, a real but rare event, or a recording bug; whether to add tilt/flip detection as a validity rule; and how to treat episodes with collisions that corrupt odometry.

## Framed question

**Decision.** A simulated indoor robot evaluation episode (pilot 2) shows a collision that corrupted wheel odometry and therefore SLAM. Decide (1) how the episode and similar future episodes are classified and reported, (2) which fixes, if any, to make to the navigation stack or the evaluation code before the next runs, and (3) whether to add any new validity rule (for example tilt/flip or "odometry corrupted by contact" detection).

**Facts (measured from the run's raw data).**
- Setup: Gazebo Harmonic + ROS 2 Jazzy, differential-drive robot (0.30 x 0.25 m rectangular chassis, wheel axle 8 cm behind `base_footprint`, so in-place spins rotate about a point Nav2 does not model), forward-only depth camera (scan slice, HFOV ~69 deg, min range 0.20 m). Nav2: Smac Hybrid DUBIN global planner (frozen by the user), MPPI controller using only the local costmap; local costmap = STVL voxel layer (decay 15 s) + inflation, no static layer; global costmap = static layer from SLAM map + STVL (decay 60 s). STVL replaced the plain ObstacleLayer between pilot 1 and pilot 2 to remove "ghost" obstacles outside the narrow FOV. Wheels use a velocity command interface with no effort (torque) limit. Ground-truth pose plugin is 2D (no roll/pitch/z).
- Episode: apartment world, frontier exploration, 600 s sim, valid by all existing gates (0 % image drop, 586 RTAB-Map updates, max gap 1.2 s). 27 goals (the earlier goal-loop bug is gone), but only 4/26 Nav2 goals succeeded (209 "no valid path" planner messages, 40 "start occupied").
- Collision: robot touched static box `chair_1` (0.45 x 0.45 x 0.9 m) twice: t = 285.3-290.4 s and 318.4-324.3 s (contact sensor). Contact z is always exactly the chassis bottom/top face (0.043 / 0.143 m): no climbing; GT velocities stay bounded (|v| <= 0.3 m/s, |w| <= 1.0 rad/s): no physics explosion. Odometry equals the integral of wheel joint angles (max 2.3 deg diff per 0.5 s): no recording bug.
- Mechanism of the second contact: the chair was behind/beside the robot and last seen by the camera ~28 s earlier, so it had decayed out of the 15 s local STVL; MPPI drove an arc into it. The global planner then said "start occupied", the BT ran a 90 deg Spin recovery while pressed against the chair; Spin's collision check uses the local costmap, which did not contain the chair. Wheels spun at the commanded rate, the chassis was blocked, wheels slipped. In 319-324 s the wheels integrated ~232 deg of yaw while the body turned ~105 deg: odometry yaw error jumped from -10 deg to +113 deg. Outside contact windows the net wheel-vs-GT yaw excess over the whole episode is 0.1 deg.
- SLAM (RTAB-Map, odometry-driven, Force3DoF) followed the odometry and never recovered (SLAM yaw error 117-123 deg until the end).
- Result: headline ATE 3.10 m (odometry 2.99 m), ATE improvement -3.8 %. Up to the second contact: SLAM ATE 0.123 m, odometry 0.276 m, improvement 55 %. Pilot 1 (210 s, old ObstacleLayer, no contacts) had ATE 0.066 m. Coverage explored 90.4 % (pilot 1 62.4 %), map completeness 74.8 % (45.4 %).

**Hard constraints (cannot be changed by this council).** The global planner stays Smac Hybrid DUBIN. No physics fudge factors (e.g. `wheel_separation_multiplier` stays 1.0; odometry drift is measured, not tuned away). Costmap, STVL, footprint, BT/recovery configuration may be changed, but only on the dev split (no test-split run has started yet). Pre-registration defines headline metrics; adding diagnostic keys is allowed, redefining headlines needs a logged deviation. Every invalid or failed episode must be reported. One simulation at a time; a 600 s episode costs ~35 min wall.

**Options on the table (not exhaustive).**
1. Report as a real failure; keep headline ATE as is; add diagnostic keys (e.g. contact-induced odometry slip in deg, ATE up to first contact, a flag `odom_corrupted_by_contact`).
2. Also fix the navigation stack so this collision mode is less likely: add the SLAM-map static layer to the local costmap, and/or lengthen local STVL decay, and/or revert the local costmap to ObstacleLayer, and/or block Spin recovery while the footprint is in collision (BackUp first). Then rerun one dev confirmation episode.
3. Add a validity rule that marks such episodes invalid (excluded from headline statistics but reported).
4. Add wheel effort/torque limits to the URDF so a blocked robot stalls rather than slips (is this physics fidelity or a fudge factor? The real motor torque is not known).
5. Switch the GT plugin to 3D and add a tilt/flip physics-sanity validity rule (none was seen here).

**Stakes.** This is a Q1 journal paper's evaluation. Treating a real navigation failure as invalid would bias results (reviewers call it cherry-picking); treating a simulator artefact as a real result would also be wrong. A stack change after the test split starts would force reruns of a ~44 h campaign. Contact-induced odometry corruption can turn one collision into a multi-metre ATE that dominates the ATE mean across episodes.

## Workspace context used

REQUIREMENTS.md §2 (planner frozen, no physics fudge, Sonnet subagents), 13_preregistration.md §13.3/§13.5b (no post-hoc exclusions; report failures), spec 01 STVL change log (2026-10-21).

---

## Round 1: Advisor responses (raw, de-anonymized)

### The Contrarian

You are asking the wrong question. This is not a classification problem, it is a stack-validity problem, and every option on the list has a hole.

Option 1 is the only honest one for this episode, but it is not enough. This is one collision, and 4/26 goals succeeded, with 209 "no valid path" and 40 "start occupied" messages. Pilot 2 is mostly a failing stack. The odometry corruption is a symptom. STVL decay of 15 s on a forward-only camera, with no static layer, means the robot is blind to everything it passed. That is a design defect you introduced between pilots, and the test split will hit it in every episode. A 3.10 m ATE from one slip tells you the metric is fragile. It does not tell you the robot is bad.

Option 3 is cherry-picking with a lab coat. "Odometry corrupted by contact" is triggered by the stack's own behavior. Once you exclude on it, any method that bumps things looks better, and reviewers will see that.

Option 4 is a fudge factor wearing a physics label. Unknown real motor torque means any limit you pick is a free parameter you will be asked to justify.

Option 5 is wasted effort. Nothing was seen, and the contact z values rule out tilt.

The unexamined risk is that you tune on one episode. "Fix then rerun one dev confirmation" is n=1, and a different seed will find a different collision mode. Do not confirm with one run. Run several dev episodes, and decide the stopping rule in advance.

Also, the Spin recovery fix is the clear win. Spinning against an obstacle that the local costmap cannot see is a plain bug, not a tuning choice. Fix that first.

Freeze the stack only after the dev episodes show collisions are rare. If you freeze at 4/26 goals, the paper's headline ATE will be noise from contact events.

### The First Principles Thinker

The question to ask is not "how do we classify this episode". It is "what is the ATE headline supposed to measure, and does this episode measure that?"

The headline is meant to show SLAM quality given a navigation stack. This episode shows a different thing. The nav stack caused an unobserved collision, and the collision then corrupted the odometry. The 3.10 m ATE therefore measures the nav stack's blindness to the chair, not SLAM. Both are real findings, but they are different findings.

Premise tests:
- "Real failure vs simulator artefact" is a false binary. The collision is a real nav failure. Wheel slip against a blocked chassis would also happen on a real robot. The unbounded slip is partly an artefact of having no torque limit, but real motors stall too, so the artefact is one of degree and not of kind.
- Option 3 (invalid) is wrong. No physics fault occurred: the contact z-values are clean, velocities are bounded, and the odometry is consistent. Excluding it is cherry-picking, and the pre-registration forbids it.
- Option 5 (3D GT) is wrong. No tilt or flip was observed, so it would fix a problem that does not exist.
- Option 4 (torque limit) is wrong. Real torque is unknown, so any value would be a fudge factor.

What to do:
1. Option 1. Keep the headline ATE and report the episode as a failure. Add diagnostic keys: ATE to first contact, contact slip in degrees, and `odom_corrupted_by_contact`. Treat the flag as a stratifier for reporting, never as an exclusion rule. Report the headline with and without flagged episodes, and use cluster-bootstrap CIs, so a single episode cannot dominate the mean.
2. Do the dev-split nav fix now, before any test run starts. The cause is a stack defect: a 15 s STVL decay plus a Spin recovery that checks only the local costmap. Block Spin while the footprint is in collision, and BackUp first. Lengthen the decay or add a persistent static layer. Then run one confirmation episode. The only cost of fixing now is one 35 min run. The cost of fixing after the test split starts is a ~44 h campaign rerun.
3. Disclose the stack change. Pilot 2 stays in the paper as the motivating failure.

The 4/26 goal success is the bigger signal. Check it before anything else, because it suggests the stack has deeper problems than this one chair.

### The Expansionist

You are asking a defensive question (classify, patch, exclude) when this episode is a gift: a free, measured, mechanistic failure case that most SLAM-evaluation papers never get.

1. Make the failure mode the paper's contribution. You already have a clean causal chain: STVL decay, then forgotten chair, then contact, then Spin recovery against the chair, then wheel slip (232 deg integrated vs 105 deg real), then 123 deg SLAM yaw error with no recovery. The pre-contact numbers (SLAM 0.123 m vs odometry 0.276 m, 55 % improvement) are a real result. The post-contact numbers (3.10 m) are a different real result. Report both as pre-registered diagnostic keys: ATE up to first contact, contact-induced slip in deg, and time-to-divergence. A "contact-corruption rate per episode" with cluster-bootstrap CIs is a headline-grade robustness metric that reviewers will remember. Option 1 is the floor, not the answer.

2. Do option 2 now, on the dev split, while it is free. It is the only fix that moves the whole project. Only 4/26 goals succeeded, with 209 "no valid path" and 40 "start occupied" messages, so the navigation stack is the bottleneck for every later metric. Fix the stack before the 44 h campaign and you get far more usable episodes per hour of wall time. Block Spin when the footprint is in collision and run BackUp first. Lengthen local STVL decay, or add a persistent static layer. A near-zero-cost bonus is to run the current and fixed stacks as a paired ablation, which turns one pilot into a "nav-stack robustness shapes SLAM validity" finding.

3. Skip options 3, 4 and 5. Excluding the episode hides your most interesting data. Torque limits are a fudge factor you cannot justify. A 3D GT plugin adds cost for a tilt problem that did not occur.

4. Build one reusable asset: an odom_corrupted_by_contact detector (wheel yaw minus GT yaw gap during contact windows). It becomes a general tool for the field.

### The Outsider

Reading this as a stranger, I think you are asking the wrong question. You are debating labels (valid/invalid, option 1 to 5) when the facts already show the problem is one specific hole in your own stack.

1. The robot hit a chair it could not see. Your costmap forgets obstacles after 15 s, and the chair was last seen 28 s earlier. Then the recovery behaviour (Spin) checked that same forgetful map and spun the robot while it was pressed against the chair. This is not a mysterious simulator artefact. It is a navigation bug, and it will recur in every episode. A fix that stops a robot from grinding into things is not tuning to the test, and you are allowed to make it because no test run has started. Block Spin while in collision and BackUp first. Add the static layer, or a longer decay, to the local costmap. Rerun one dev episode. Do this before the 44 h campaign, not after.

2. Do not mark the episode invalid (option 3). The robot really collided, so excluding it is cherry-picking by your own definition. Report it as a failure (option 1) and keep the headline ATE.

3. Your 4/26 goal success, 209 "no valid path" messages and 40 "start occupied" messages are a bigger red flag than the collision. One bad collision does not explain a navigation stack that mostly fails to plan. Check this first.

4. Skip options 3, 4 and 5. Adding torque limits means inventing a motor value you admit is unknown, which is a fudge factor. 3D ground truth is only worth it if you see a flip, and you saw none.

5. Jargon problems for a reader of the paper: "ATE", "STVL", "MPPI", "Smac Hybrid DUBIN", "Force3DoF" and "start occupied" are never defined. "Dev split" and "test split" are never explained for a robotics audience. A reviewer will also ask why a 600 s episode of one world is your unit of evidence.

### The Executor

Do option 1 plus a cheap slice of option 2, run on the dev split only. Skip 3, 4 and 5 entirely.

**Classification (Monday, about 2 hours, no sim time).** Pilot 2 stays a valid, failed episode. Headline ATE stays 3.10 m. Add three diagnostic keys computed from the existing raw data: `contact_odom_slip_deg` (232 vs 105 deg here), `ate_until_first_destructive_contact`, and `odom_corrupted_by_contact`. Use a hard-coded threshold, for example more than 15 deg of wheel-vs-GT yaw excess inside a contact window. Report the headline and the pre-contact numbers side by side. A "55 % improvement until the second contact" figure is a diagnostic, not a headline. If you exclude it from the headline, you are cherry-picking, and a Q1 reviewer will see it.

**Option 3 is a trap.** Your own facts say this is a real navigation failure. The stack drove into a chair it had forgotten. The slip is a symptom of that failure, not a simulator artefact. Invalidating it would also let the campaign hide every episode where the stack collides.

**Options 4 and 5.** Torque limits would be a guessed fudge factor with unknown real motor torque. A 3D ground-truth plugin and a tilt rule guard against something you saw zero of. Don't build them.

**Stack fix (do this before the test split, because a change afterwards forces a ~44 h rerun).** The root cause is the 15 s local STVL decay, which loses obstacles the robot has just driven past. Make two changes:
- Put a stack-level guard in the BT so Spin and Wait recoveries are not run while in contact. Use BackUp first, or a clear-costmap plus BackUp sequence. This addresses the 90 deg Spin that caused the 113 deg yaw jump.
- Lengthen local STVL decay (for example 15 s to 60 s, matching the global costmap), or add the SLAM static layer to the local costmap.

I can't tell which of these actually fixes it, so test them as two cheap experiments, not one bundle.

**Test.** Rerun this exact apartment world, seed and start, with the change, for about 35 min wall. If chair_1 isn't hit, proceed. The 209 "no valid path" messages and 4/26 goal success are the bigger problem. Spend an hour reading the "start occupied" cause (40 instances) before you launch the next episode. Those are probably inflation and footprint mismatch from the 0.08 m axle offset, and they'll eat more campaign time than the collision does.

**Then freeze the stack and log the deviations.**

---

## Anonymization map

Session timestamp: `1792639190` · permutation index: `110`

| Advisor | Letter shown to reviewers |
|---|---|
| Contrarian | D |
| First Principles Thinker | C |
| Expansionist | B |
| Outsider | E |
| Executor | A |

---

## Round 2: Peer reviews (reviewers saw only the anonymized A to E responses)

### Reviewer 1

1. Strongest: C. It reframes correctly (the headline ATE measures nav-stack blindness here, not SLAM), dissolves the "real vs artefact" binary, and gives the most defensible reporting design. It treats the flag as a stratifier, reports the headline with and without flagged episodes, and uses cluster-bootstrap CIs so one episode can't dominate the mean. It also says to disclose the stack change and keep pilot 2 in the paper.

2. Biggest blind spot: B. It treats the episode as a "gift" and proposes new headline-grade metrics. It never questions the 4/26 goal success as a validity or stack problem beyond a passing mention. It also ignores the pre-registration constraint on redefining headlines and the n=1 confirmation risk. D covers that risk, and B skips it.

3. Missed by all five:
- Nobody asked whether the contact threshold or flag definition should be pre-specified and logged before test runs, to avoid post-hoc tuning on this one episode.
- Nobody noted that the dev-fix changes the frozen stack, so pilot 1 and pilot 2 numbers aren't comparable. They also didn't point out that the STVL change made between pilots was itself an unlogged deviation.
- Nobody considered the planning mismatch from the 8 cm axle offset: Spin rotates about a point Nav2 doesn't model, so even a correct footprint check can clip obstacles. A footprint or recovery-radius fix addresses this directly.
- Nobody proposed a cheap offline replay or fault injection (e.g. a synthetic slip applied to the logged odometry) to test how sensitive ATE is to contact before spending 35 min runs.
- Nobody addressed that SLAM never recovers from corrupted odometry. That is an RTAB-Map loop-closure or odometry-reset question, and it affects every collision episode.

### Reviewer 2

1. Strongest: C. It reframes the question (what is the ATE headline supposed to measure?). It dissolves the "real failure vs artefact" binary, noting real motors also stall. It gives a concrete reporting rule: use the flag as a stratifier, never an exclusion, and report headline with and without flagged episodes using cluster-bootstrap CIs so one episode can't dominate the mean. It also requires disclosing the stack change and keeping pilot 2 in the paper.

2. Biggest blind spot: B. It treats the episode as a "gift" and proposes new headline-grade metrics. It never addresses the pre-registration constraint (redefining headlines needs a logged deviation). It never says how mean ATE stays robust to one 3 m outlier. It ignores the 40 "start occupied" messages as a possible footprint/axle-offset cause. It also suggests a paired ablation that costs 35 min per run, with no budget.

3. Missed by all five:
- Whether MPPI/Nav2 should be tuned for the 8 cm axle offset. Spin rotates about an unmodelled point, so the Spin collision check is wrong even with a perfect costmap.
- The fix is validated only by the same seed and world, which risks tuning to the dev set. D noticed n=1 but none suggested held-out dev worlds or seeds.
- No one proposed a robust headline estimator (median or trimmed mean) or pre-registered the stratification before the test split.
- None asked whether SLAM should reject odometry that is inconsistent with visual-loop evidence. That would be a SLAM-side failure to report, not only a nav one.

### Reviewer 3

1. Strongest: C. It reframes the question (what the headline ATE is meant to measure), dissolves the "real failure vs artefact" binary, and gives a concrete reporting rule: the flag is a stratifier and never an exclusion, headline reported with and without flagged episodes, cluster-bootstrap CIs so one episode can't dominate the mean. It also says to disclose the stack change and keep pilot 2 in the paper.

2. Biggest blind spot: B. It treats the failure as "a gift" and a paper contribution. It never addresses the n=1 confirmation weakness or the 4/26 goal-success problem as a gating item. It also proposes a "contact-corruption rate" headline-grade metric, which risks redefining headlines without logging the deviation the pre-registration requires. It never questions whether the proposed fixes work.

3. Missed by all five:
- A bump-triggered or contact-triggered recovery. This is the root cause, because the stack lacks any contact-aware behavior. A contact-sensor-driven (or odometry-vs-IMU slip) stop/BackUp trigger is a stack feature, not a physics fudge.
- Whether the fix should depend on the robot's blind rear and sides. Spin about an axle 8 cm behind `base_footprint` is a footprint/rotation-centre mismatch, which is a separate defect that the 40 "start occupied" messages may reflect.
- The ATE metric itself. Reporting per-segment or windowed ATE and relative pose error (RPE), which are robust to a single yaw jump, is a better answer than any flag.
- The need to pre-register the fix/freeze criteria (such as a collision-rate threshold) in the deviation log before touching the stack.

### Reviewer 4

1. Strongest: C. It reframes the question (what does the ATE headline measure?), rejects the real-failure vs artefact binary, and gives a concrete reporting rule: the flag is a stratifier, never an exclusion. It also adds cluster-bootstrap CIs so one episode cannot dominate the mean, requires disclosing the stack change, and flags the 4/26 goal success.

2. Biggest blind spot: B. It treats the episode as a gift and proposes new headline-grade metrics ("contact-corruption rate", time-to-divergence). It never addresses the pre-registration constraint that headlines can't be redefined without a logged deviation. It also never asks whether the single fix-and-rerun is enough evidence. It sells a paired ablation as a "bonus" without noting it needs more than n=1 episodes.

3. Missed by all five:
- The robot's rear-axle offset (axle 8 cm behind `base_footprint`) means Nav2 does not model the in-place-spin pivot. The footprint and collision checks are therefore likely wrong in exactly the spin case. A (briefly), and no one else, touched the offset, and only as a possible cause of "start occupied". No one connected it to Spin collision.
- The forward-only camera means the robot can't see its own rear and sides. A simple rear/side-aware fix (restrict spins, or a short-range persistent memory layer) is not discussed.
- The contact detector uses ground-truth contact. A real-world-valid odometry-corruption check should use only on-board signals (wheel vs IMU/SLAM yaw disagreement), or the paper's flag isn't deployable.
- No one proposes testing whether SLAM could have rejected the bad odometry (RTAB-Map loop-closure or covariance gating). SLAM "never recovered", which is itself a SLAM-evaluation finding.

### Reviewer 5

1. Strongest: C. It names the real issue (what the ATE headline is meant to measure) and rejects the "real vs artefact" binary with a concrete point: real motors stall too, so the artefact is one of degree. It also gives the best statistical safeguard: the flag is a stratifier, never an exclusion rule. It reports the headline with and without flagged episodes and uses cluster-bootstrap CIs so one episode can't dominate the mean. It also tells the user to disclose the stack change.

2. Biggest blind spot: E. It spends a point on jargon and has no safeguard against one collision dominating the ATE mean. It proposes no diagnostic keys, no `odom_corrupted_by_contact` flag, and no with/without reporting. That is most of option 1 and the paper's central stakes.

3. Missed by all five:
- Spin recovery cannot be fully fixed by blocking it only "while in contact". The chair was absent from the local costmap, so a contact signal is needed. Nobody proposes using Gazebo's contact sensor or odometry-vs-IMU/GT divergence at runtime as the trigger.
- The robot's wheel axle is 8 cm behind `base_footprint`, so in-place spins rotate about a point Nav2 does not model. The footprint and recovery geometry issue is unaddressed. Only A mentions it in passing, for "start occupied".
- No one flags that changing the stack (STVL decay, recovery BT) after seeing pilot 2 makes the dev/test split's tuning an explicit deviation to pre-register. They also don't ask for the pre-contact ATE to be pre-specified as a secondary metric before test runs.
- Nobody notes that RTAB-Map's SLAM could be given loop-closure or visual-odometry robustness. The SLAM never recovered from corrupted odometry.

---

## Chairman synthesis

### Where the council agrees

- **All five** (Contrarian, First Principles, Expansionist, Outsider, Executor): pilot 2 stays a **valid, failed** episode; the headline ATE (3.10 m) is kept; marking it invalid (option 3) is cherry-picking because the collision was caused by the stack itself.
- **All five** reject option 4 (wheel torque limits: the real motor torque is unknown, so any value is a guessed free parameter, i.e. a fudge factor) and option 5 (3D GT + tilt rule: contact z is pinned to the chassis faces, nothing tilted).
- **All five**: the root cause is a navigation-stack defect (local costmap forgets obstacles outside the forward-only FOV; Spin checks that same costmap), fixable now on the dev split before any test run.
- **Contrarian, First Principles, Outsider, Executor**: the 4/26 goal success with 209 "no valid path" is a bigger problem than the collision and must be investigated separately.

### Where the council clashes

- **Confirmation size.** The Contrarian wants several dev episodes with a stopping rule fixed in advance; First Principles, Outsider and Executor accept one confirmation run. Reasonable either way: one run tests the mechanism on the same seed, but n=1 cannot show the failure mode is rare.
- **How big to make the finding.** The Expansionist wants a headline-grade "contact-corruption rate" metric; First Principles and Executor keep it a diagnostic. A new headline after seeing data needs a logged deviation; a diagnostic does not.
- **Bundle or separate fixes.** The Executor wants decay-length and static-layer changes tested as separate experiments; the others bundle them.

### Blind spots the council caught

- **Axle offset (4 of 5 reviewers).** The wheel axle is 8 cm behind `base_footprint`, so Spin's own collision check simulates rotation about the wrong point; even a perfect costmap can be clipped during an in-place spin.
- **Pre-register before the test split (3 of 5).** The new keys, the 15 deg threshold and the "with and without flagged episodes" reporting rule must be written into the pre-registration before the first test run, not chosen afterwards.
- **SLAM never recovered (4 of 5).** RTAB-Map followed the corrupted odometry for 280 s with no correction; that is a SLAM-side result to report, not only a navigation one.

### The recommendation

Adopt option 1 plus a targeted option 2. Pilot 2 stays valid and failed with headline ATE 3.10 m; add diagnostic keys (contact-induced yaw excess, `odom_corrupted_by_contact`, ATE up to the first corrupting contact), pre-registered as secondary stratifiers that are never exclusions, with the ATE headline also reported with and without flagged episodes and as a median. On the stack, add the SLAM-map static layer to the local costmap and run BackUp before Spin; I overrule the Executor's separate decay experiment, because the behaviour tree runs ClearEntireCostmap on the local costmap before every Spin, so no STVL decay length could have kept the chair. I side with the Contrarian on n: confirm on two dev episodes (seed 2, as in pilot 2, plus seed 1) with a pre-declared stopping rule (no `odom_corrupted_by_contact` flag and no Spin while in contact in either run). The axle offset is documented as a limitation, not changed in R1.

### The one thing to do first

Run the seed-2 apartment frontier confirmation episode with the fixed stack and check `odom_corrupted_by_contact` and `n_collisions` in its summary.json.
