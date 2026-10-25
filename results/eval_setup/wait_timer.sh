#!/bin/bash
# usage: wait_timer.sh <label> <end-marker-in-timer.log> <deadline_min>
# HARD CAP 10 min per wait (user rule). Also shows GPU status (gpu_watch.sh) and exits early on a GPU alert.
label=$1; marker=$2; dl=$(( ${3:-10} * 60 )); [ $dl -gt 600 ] && dl=600; t0=$(date +%s)
a0=$(wc -l < ~/eval_setup/gpu_alert.txt 2>/dev/null || echo 0)
gpusum() {  # max temp / min headroom / flags over this wait window, from gpu.log
  awk -v s="$(date -d @$t0 +%T)" '$1>=s && $2 ~ /^(NORMAL|LOG|HOT|THROTTLE)$/ {split($3,a,"=");t=a[2]+0; if(t>mx)mx=t; split($4,b,"=");h=b[2]+0; if(mn==""||h<mn)mn=h; if($0~/thermal_flag=1/)th++; if($0~/powercap=Active/)pc++; if($2!="NORMAL")nn++}
       END{printf "GPU window: max %dC, min headroom %sC, thermal-flag samples %d, power-cap samples %d, non-NORMAL samples %d", mx, mn, th, pc, nn}' ~/eval_setup/gpu.log 2>/dev/null
}
while ! grep -q "$marker" ~/eval_setup/timer.log; do
  e=$(( $(date +%s) - t0 ))
  printf '%s elapsed %02d:%02d / cap %02d:00 (alert only, never kills) | %s | last: %s\n' "$label" $((e/60)) $((e%60)) $(( dl/60 )) "$(cat ~/eval_setup/gpu_status.txt 2>/dev/null | cut -c1-110)" "$(tmux capture-pane -t eval -p | grep -v '^$' | tail -1 | cut -c1-70)" > ~/eval_setup/wait_timer.txt
  if [ "$(wc -l < ~/eval_setup/gpu_alert.txt 2>/dev/null || echo 0)" -gt "$a0" ]; then echo "GPU ALERT during $label at $(date -Is):"; tail -n +$((a0+1)) ~/eval_setup/gpu_alert.txt; gpusum; echo; exit 4; fi
  if [ $e -ge $dl ]; then echo "10-MIN CHECK-IN for $label at $(date -Is) — inspect, do not auto-kill"; gpusum; echo; exit 3; fi
  sleep 15
done
echo "$label finished after $(( ($(date +%s)-t0)/60 )) min"; gpusum; echo
