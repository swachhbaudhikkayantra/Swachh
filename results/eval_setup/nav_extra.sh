#!/bin/bash
# Extra navigation seeds 103/104 (user request). Start only if ^C3_DONE appears before 19:45; cut scheduler at 19:50.
source ~/eval_setup/env.sh >/dev/null 2>&1
T=~/eval_setup/timer.log; GATE=$(date -d "today 19:45" +%s); CUT=$(date -d "today 19:50" +%s)
while ! grep -q "^C3_DONE" $T; do
  [ $(date +%s) -ge $GATE ] && { echo "NAV_EXTRA_SKIPPED $(date -Is) C3 not finished by 19:45" >> $T; exit 0; }
  sleep 10
done
[ $(date +%s) -ge $GATE ] && { echo "NAV_EXTRA_SKIPPED $(date -Is) C3_DONE after 19:45" >> $T; exit 0; }
echo "NAV_EXTRA_START $(date -Is) parallel=2 seeds 103,104 x 3 worlds (cut at 19:50)" >> $T
python3 -m vacuum_eval.run_batch --matrix config/campaigns/quick_navigation_extra.yaml --split test --confirm-test-split --parallel 2 2>&1 | tee ~/eval_setup/C3x.log &
sleep 3; BP=$(ps -eo pid,args | awk '$2 ~ /^python3/ && /run_batch.*quick_navigation_extra/ && !/awk/ {print $1}' | head -1)
while kill -0 $BP 2>/dev/null; do
  if [ $(date +%s) -ge $CUT ]; then
    kill -STOP $BP; echo "NAV_EXTRA_CUT $(date -Is) scheduler $BP SIGSTOPped at the 19:50 limit; waiting for running episodes" >> $T
    while pstree -ap $BP 2>/dev/null | grep -q run_episode; do sleep 10; done
    kill -9 $BP; break
  fi
  sleep 10
done
wait 2>/dev/null
echo "NAV_EXTRA_DONE $(date -Is)" >> $T
