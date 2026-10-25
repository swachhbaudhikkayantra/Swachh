#!/bin/bash
# GPU thermal guard (user rule, 2026-10-25). Logs every 10 s; applies the table:
#   <80 C NORMAL | 80-85 LOG (keep going) | >85 C or headroom<=5 C to slowdown -> HOT
#   thermal slowdown flag set, or newest episode rtf_true_mean < 0.7 -> THROTTLE / RTF_LOW
# HOT / THROTTLE / RTF_LOW: SIGSTOP the run_batch scheduler ONLY (running episodes finish, no new ones start).
# Release (SIGCONT) when temp < 75 C and no thermal flag. RTF_LOW needs a manual release: touch ~/eval_setup/gpu_release
# Never kills anything. Outputs: gpu.log (history), gpu_status.txt (latest), gpu_alert.txt (alerts, wakes wait_timer.sh).
D=~/eval_setup; LOG=$D/gpu.log; ST=$D/gpu_status.txt; AL=$D/gpu_alert.txt; HELD=$D/gpu_held.pid
mark=$(date +%s); seen=$D/.gpu_seen_summaries; : > $seen
alert() { echo "$(date -Is) $*" | tee -a $AL >> $LOG; }
batch_pids() { ps -eo pid,args | awk '$2 ~ /^python3/ && /-m vacuum_eval\.run_batch/ && !/awk/ {print $1}'; }
while true; do
  q=$(nvidia-smi --query-gpu=temperature.gpu,power.draw,clocks.sm,clocks_throttle_reasons.hw_thermal_slowdown,clocks_throttle_reasons.sw_thermal_slowdown,clocks_throttle_reasons.sw_power_cap --format=csv,noheader,nounits 2>/dev/null)
  IFS=',' read -r temp pwr clk hwt swt cap <<< "$q"; temp=${temp// /}; hwt=${hwt// /}; swt=${swt// /}; cap=${cap// /}
  head=$(nvidia-smi -q -d TEMPERATURE 2>/dev/null | awk -F: '/GPU T.Limit Temp/ && !/Shutdown|Slowdown|Max/ {gsub(/[^0-9-]/,"",$2); print $2; exit}')
  thermal=0; [ "$hwt" = "Active" ] || [ "$swt" = "Active" ] && thermal=1
  lvl=NORMAL
  [ "${temp:-0}" -ge 80 ] && lvl=LOG
  { [ "${temp:-0}" -gt 85 ] || { [ -n "$head" ] && [ "$head" -le 5 ]; }; } && lvl=HOT
  [ $thermal = 1 ] && lvl=THROTTLE
  # newest finished episodes: rtf check
  rtfmsg=""
  for f in $(find ~/eval_runs/quick_* -name summary.json -newermt "@$mark" 2>/dev/null); do
    grep -qxF "$f" $seen && continue; echo "$f" >> $seen
    r=$(python3 -c "import json;d=json.load(open('$f'));print(d.get('rtf_true_mean') or '')" 2>/dev/null)
    if [ -n "$r" ] && python3 -c "import sys;sys.exit(0 if float('$r')<0.7 else 1)"; then rtfmsg="RTF_LOW $r in ${f#*eval_runs/}"; fi
  done
  printf '%s %s temp=%sC head=%sC pwr=%sW sm=%sMHz thermal_flag=%s powercap=%s held=%s\n' "$(date +%T)" $lvl "$temp" "${head:-?}" "$pwr" "$clk" $thermal $cap "$([ -f $HELD ] && echo yes || echo no)" | tee $ST >> $LOG
  if [ -n "$rtfmsg" ]; then alert "$rtfmsg -> holding scheduler (manual release: touch $D/gpu_release)"; touch $D/.gpu_rtf_hold; fi
  if { [ $lvl = HOT ] || [ $lvl = THROTTLE ] || [ -f $D/.gpu_rtf_hold ]; } && [ ! -f $HELD ]; then
    pids=$(batch_pids); echo "$pids" > $HELD
    for p in $pids; do kill -STOP $p 2>/dev/null; done
    alert "HOLD ($lvl temp=${temp}C head=${head:-?}C) run_batch pid(s) [${pids//$'\n'/ }] SIGSTOPped: running episodes finish, no new ones start; release below 75C. Also: drop --parallel 3 -> 2 on restart."
  fi
  if [ -f $HELD ]; then
    rel=0
    if [ -f $D/.gpu_rtf_hold ]; then [ -f $D/gpu_release ] && rel=1; else [ "${temp:-99}" -lt 75 ] && [ $thermal = 0 ] && rel=1; fi
    if [ $rel = 1 ]; then
      for p in $(cat $HELD); do kill -CONT $p 2>/dev/null; done
      rm -f $HELD $D/.gpu_rtf_hold $D/gpu_release; alert "RELEASE temp=${temp}C: run_batch SIGCONT"
    fi
  fi
  sleep 10
done
