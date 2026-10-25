#!/bin/bash
# Snapshot all results so far into ~/Swachh/results/ (light files only: no bags, no rtabmap.db) and commit locally. Never pushes.
set -u
R=~/Swachh/results; mkdir -p $R/runs $R/monitoring
for e in $(ls ~/eval_runs | grep -E "^(quick_|dev8h_|dev_navab_|diag_|_failed|_gt)"); do
  [ -d ~/eval_runs/$e ] && rsync -a --prune-empty-dirs --max-size=5M \
    --exclude 'bag/' --exclude '*.db' --exclude '*.db3' --exclude '*.mcap' --exclude '*.bag' --exclude '.slot*.lock' \
    ~/eval_runs/$e/ $R/runs/$e/
done
python3 -I ~/eval_setup/results_table.py > $R/RESULTS_SO_FAR.md 2>/dev/null
rsync -a --max-size=5M --exclude "*.pid" --exclude "wait_timer.txt" ~/eval_setup/ $R/eval_setup/   # helper scripts + run logs
cp -f ~/eval_setup/timer.log $R/monitoring/timer.log 2>/dev/null
cp -f ~/eval_setup/gpu.log $R/monitoring/gpu.log 2>/dev/null
cp -f ~/eval_setup/gpu_alert.txt $R/monitoring/gpu_alert.txt 2>/dev/null
cp -f ~/eval_setup/C*.log $R/monitoring/ 2>/dev/null
python3 -I - <<'PY' > $R/INDEX.md
import json,glob,os,datetime
R=os.path.expanduser('~/Swachh/results/runs')
print('# Results index (auto-generated %s)\n' % datetime.datetime.now().strftime('%F %H:%M'))
print('Light snapshot of `~/eval_runs` (no bags, no rtabmap.db). Full data stays on victus. Test-split campaigns are `quick_*`; `dev8h_*` are Phase A dev checks (not pooled); `_failed_attempts` are attempt-1 infra failures.\n')
print('| experiment | world | method/stack | seed | status | valid | rtf | img_drop % | end_reason |\n|---|---|---|---|---|---|---|---|---|')
for f in sorted(glob.glob(R+'/*/*/*/seed_*/summary.json')+glob.glob(R+'/_failed_attempts/*/*/*/*/summary.json')):
    try: s=json.load(open(f))
    except Exception: continue
    p=f[len(R)+1:].split('/')[:-1]
    r=s.get('rtf_true_mean'); i=s.get('img_drop_pct')
    print('| %s | %s | %s | %s | %s | %s | %s | %s | %s |'%(p[0],p[-3] if p[0]=='_failed_attempts' else p[1],p[-2] if p[0]=='_failed_attempts' else p[2],p[-1],s.get('status'),s.get('episode_valid'),'' if r is None else round(r,3),'' if i is None else round(i,2),s.get('end_reason')))
PY
du -sh $R | tail -1 > $R/../results/.size 2>/dev/null; rm -f $R/../results/.size
cd ~/Swachh && git add results progress docs 2>/dev/null
if ! git diff --cached --quiet; then
  git -c user.name="Swachh eval (victus)" -c user.email="raghavendrap@rvce.edu.in" commit -q -m "${1:-Results snapshot $(date +%F\ %H:%M)}" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && echo "committed $(git rev-parse --short HEAD)"
else echo "nothing to commit"; fi
