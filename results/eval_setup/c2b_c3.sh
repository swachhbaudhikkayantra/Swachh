#!/bin/bash
# Wait for the running wave of the (SIGSTOPped) 3-slot C2 batch, drop that scheduler, then C2 remainder + C3 at --parallel 2.
source ~/eval_setup/env.sh >/dev/null 2>&1
OLD=88081; T=~/eval_setup/timer.log
while pstree -ap $OLD 2>/dev/null | grep -q "run_episode"; do sleep 10; done
echo "C2_WAVE2_DONE $(date -Is) (no run_episode left under stopped scheduler $OLD)" >> $T
kill -9 $OLD 2>/dev/null; sleep 8
echo "NOTE: a C2_DONE line near here is the aborted --parallel 3 batch window closing, not campaign completion. Real markers: C2b_DONE, C3_DONE" >> $T
[ -f ~/eval_setup/gpu_held.pid ] && touch ~/eval_setup/gpu_release   # clear any stale guard hold on the removed scheduler
echo "C2b_START $(date -Is) parallel=2 (maze_dead_ends remainder)" >> $T
python3 -m vacuum_eval.run_batch --matrix config/campaigns/quick_exploration.yaml --split test --confirm-test-split --parallel 2 2>&1 | tee ~/eval_setup/C2b.log
echo "C2b_DONE $(date -Is)" >> $T
echo "C3_START $(date -Is) parallel=2" >> $T
python3 -m vacuum_eval.run_batch --matrix config/campaigns/quick_navigation.yaml --split test --confirm-test-split --parallel 2 2>&1 | tee ~/eval_setup/C3.log
echo "C3_DONE $(date -Is)" >> $T
