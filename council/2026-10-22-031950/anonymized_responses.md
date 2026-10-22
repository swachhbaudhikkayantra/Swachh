**Response A:**
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

**Response B:**
You are asking a defensive question (classify, patch, exclude) when this episode is a gift: a free, measured, mechanistic failure case that most SLAM-evaluation papers never get.

1. Make the failure mode the paper's contribution. You already have a clean causal chain: STVL decay, then forgotten chair, then contact, then Spin recovery against the chair, then wheel slip (232 deg integrated vs 105 deg real), then 123 deg SLAM yaw error with no recovery. The pre-contact numbers (SLAM 0.123 m vs odometry 0.276 m, 55 % improvement) are a real result. The post-contact numbers (3.10 m) are a different real result. Report both as pre-registered diagnostic keys: ATE up to first contact, contact-induced slip in deg, and time-to-divergence. A "contact-corruption rate per episode" with cluster-bootstrap CIs is a headline-grade robustness metric that reviewers will remember. Option 1 is the floor, not the answer.

2. Do option 2 now, on the dev split, while it is free. It is the only fix that moves the whole project. Only 4/26 goals succeeded, with 209 "no valid path" and 40 "start occupied" messages, so the navigation stack is the bottleneck for every later metric. Fix the stack before the 44 h campaign and you get far more usable episodes per hour of wall time. Block Spin when the footprint is in collision and run BackUp first. Lengthen local STVL decay, or add a persistent static layer. A near-zero-cost bonus is to run the current and fixed stacks as a paired ablation, which turns one pilot into a "nav-stack robustness shapes SLAM validity" finding.

3. Skip options 3, 4 and 5. Excluding the episode hides your most interesting data. Torque limits are a fudge factor you cannot justify. A 3D GT plugin adds cost for a tilt problem that did not occur.

4. Build one reusable asset: an odom_corrupted_by_contact detector (wheel yaw minus GT yaw gap during contact windows). It becomes a general tool for the field.

**Response C:**
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

**Response D:**
You are asking the wrong question. This is not a classification problem, it is a stack-validity problem, and every option on the list has a hole.

Option 1 is the only honest one for this episode, but it is not enough. This is one collision, and 4/26 goals succeeded, with 209 "no valid path" and 40 "start occupied" messages. Pilot 2 is mostly a failing stack. The odometry corruption is a symptom. STVL decay of 15 s on a forward-only camera, with no static layer, means the robot is blind to everything it passed. That is a design defect you introduced between pilots, and the test split will hit it in every episode. A 3.10 m ATE from one slip tells you the metric is fragile. It does not tell you the robot is bad.

Option 3 is cherry-picking with a lab coat. "Odometry corrupted by contact" is triggered by the stack's own behavior. Once you exclude on it, any method that bumps things looks better, and reviewers will see that.

Option 4 is a fudge factor wearing a physics label. Unknown real motor torque means any limit you pick is a free parameter you will be asked to justify.

Option 5 is wasted effort. Nothing was seen, and the contact z values rule out tilt.

The unexamined risk is that you tune on one episode. "Fix then rerun one dev confirmation" is n=1, and a different seed will find a different collision mode. Do not confirm with one run. Run several dev episodes, and decide the stopping rule in advance.

Also, the Spin recovery fix is the clear win. Spinning against an obstacle that the local costmap cannot see is a plain bug, not a tuning choice. Fix that first.

Freeze the stack only after the dev episodes show collisions are rare. If you freeze at 4/26 goals, the paper's headline ATE will be noise from contact events.

**Response E:**
Reading this as a stranger, I think you are asking the wrong question. You are debating labels (valid/invalid, option 1 to 5) when the facts already show the problem is one specific hole in your own stack.

1. The robot hit a chair it could not see. Your costmap forgets obstacles after 15 s, and the chair was last seen 28 s earlier. Then the recovery behaviour (Spin) checked that same forgetful map and spun the robot while it was pressed against the chair. This is not a mysterious simulator artefact. It is a navigation bug, and it will recur in every episode. A fix that stops a robot from grinding into things is not tuning to the test, and you are allowed to make it because no test run has started. Block Spin while in collision and BackUp first. Add the static layer, or a longer decay, to the local costmap. Rerun one dev episode. Do this before the 44 h campaign, not after.

2. Do not mark the episode invalid (option 3). The robot really collided, so excluding it is cherry-picking by your own definition. Report it as a failure (option 1) and keep the headline ATE.

3. Your 4/26 goal success, 209 "no valid path" messages and 40 "start occupied" messages are a bigger red flag than the collision. One bad collision does not explain a navigation stack that mostly fails to plan. Check this first.

4. Skip options 3, 4 and 5. Adding torque limits means inventing a motor value you admit is unknown, which is a fudge factor. 3D ground truth is only worth it if you see a flip, and you saw none.

5. Jargon problems for a reader of the paper: "ATE", "STVL", "MPPI", "Smac Hybrid DUBIN", "Force3DoF" and "start occupied" are never defined. "Dev split" and "test split" are never explained for a robotics audience. A reviewer will also ask why a 600 s episode of one world is your unit of evidence.
