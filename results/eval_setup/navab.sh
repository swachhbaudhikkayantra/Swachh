#!/bin/bash
# DEV A/B nav v1 vs v2: apartment, dev seeds 1 and 2; per seed v1 (slot 0) and v2 (slot 1) concurrently.
source ~/eval_setup/env.sh >/dev/null 2>&1
T=~/eval_setup/timer.log
echo "NAVAB_START $(date -Is) apartment dev seeds 1,2; v1 slot0 + v2 slot1 per seed" >> $T
for s in 1 2; do
  for v in v1 v2; do
    slot=$([ $v = v1 ] && echo 0 || echo 1)
    VACUUM_NAV_VARIANT=$v python3 -m vacuum_eval.run_episode --experiment dev_navab_$v --world apartment --method scripted_goals \
      --goal-list random20 --nav-map gt --localization auto --seed $s --odom-noise 0 --headless 1 --timeout-sim-sec 900 \
      --slot $slot > ~/eval_setup/NAVAB_${v}_s$s.log 2>&1 &
    sleep 20
  done
  wait
  echo "NAVAB_SEED${s}_DONE $(date -Is)" >> $T
done
echo "NAVAB_DONE $(date -Is)" >> $T
