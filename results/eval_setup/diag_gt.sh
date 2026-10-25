#!/bin/bash
# DIAGNOSTIC (not test split): --localization gt on DEV world apartment, DEV seed 1. Starts after the extra navigation seeds finish.
source ~/eval_setup/env.sh >/dev/null 2>&1
T=~/eval_setup/timer.log
while ! grep -q "^NAV_EXTRA_DONE\|^NAV_EXTRA_SKIPPED" $T; do sleep 10; done
echo "DIAG_GT_START $(date -Is) apartment dev seed 1 --localization gt (diagnostic, 15 min box)" >> $T
python3 -m vacuum_eval.run_episode --experiment diag_gt_localization --world apartment --method scripted_goals --goal-list random20 --nav-map gt --localization gt --seed 1 --odom-noise 0 --headless 1 --timeout-sim-sec 900 2>&1 | tee ~/eval_setup/DIAG_GT.log
echo "DIAG_GT_DONE $(date -Is)" >> $T
