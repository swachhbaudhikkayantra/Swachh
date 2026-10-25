import json,glob,os,statistics as st,collections,datetime
R=os.path.expanduser('~/eval_runs')
M=[('coverage','coverage_explored_pct'),('completeness','map_completeness_pct'),('ATE m','ate_fixed_rmse_m'),('RPE m/1m','rpe_trans_rmse_m_1m'),
   ('LC prec %','lc_precision_pct'),('nav GT %','nav_success_gt_pct'),('collisions','n_collisions'),('path ratio','path_length_ratio_mean')]
def f(v): return '' if v is None else ('%.2f'%v if abs(v)<10 else '%.1f'%v)
groups=collections.OrderedDict()
for p in sorted(glob.glob(R+'/quick_*/*/*/seed_*/summary.json')):
    s=json.load(open(p)); c,w,m,sd=p[len(R)+1:].split('/')[:4]
    groups.setdefault((c,w,m),[]).append((sd,s))
out=[]
out.append('# Test-split results so far (auto-generated %s)\n'%datetime.datetime.now().strftime('%F %H:%M'))
out.append('Only `quick_*` (test split). Values: mean [min-max] over the *valid* episodes; invalid episodes are counted but excluded from statistics. Flags: counts of non-OK health statuses over all episodes of the group (L=LOW_N, S=SUSPECT, B=BAD, U=UNMEASURABLE; n= episodes in that status). Pooled CIs come from the final report; here n is tiny.\n')
hdr='| campaign | world / stack | n | valid | rtf_true_mean | '+' | '.join(a for a,_ in M)+' |'
out.append(hdr); out.append('|'+'---|'*(5+len(M)))
for (c,w,m),eps in groups.items():
    n=len(eps); val=[s for _,s in eps if s.get('episode_valid') and s.get('status')=='ok']
    rtf=[s['rtf_true_mean'] for _,s in eps if s.get('rtf_true_mean')]
    cells=[]
    for lab,k in M:
        vs=[s.get(k) for s in val if s.get(k) is not None]
        fl=collections.Counter(s.get('health_'+k) for _,s in eps if s.get('health_'+k) not in (None,'OK'))
        fs=' '.join('%s×%d'%({'LOW_N':'L','SUSPECT':'S','BAD':'B','UNMEASURABLE':'U','NA':'NA'}.get(a,a),b) for a,b in fl.items() if a!='NA')
        if vs: t='%s [%s-%s]'%(f(st.mean(vs)),f(min(vs)),f(max(vs)))
        else: t='–'
        cells.append(t+(' **'+fs+'**' if fs else ''))
    out.append('| %s | %s/%s | %d | %d | %s | %s |'%(c,w,m.replace('responsiveness_','').replace('scripted_goals_scenario','scen').replace('frontier','frontier'),n,len(val),'%.3f-%.3f'%(min(rtf),max(rtf)) if rtf else '',' | '.join(cells)))
low=[(c,w,m,sd,round(s['rtf_true_mean'],3)) for (c,w,m),eps in groups.items() for sd,s in eps if s.get('rtf_true_mean') and s['rtf_true_mean']<0.7]
allr=[s['rtf_true_mean'] for eps in groups.values() for _,s in eps if s.get('rtf_true_mean')]
out.append('\n**rtf_true_mean range over %d test episodes: %.3f-%.3f. Episodes below 0.7 (LOW_RTF, SUSPECT, not excluded): %s**\n'%(len(allr),min(allr),max(allr),low or 'none'))
out.append('## Per-episode rtf_true_mean and status\n\n| campaign | world/stack | seed | status | valid | rtf | img_drop % |\n|---|---|---|---|---|---|---|')
for (c,w,m),eps in groups.items():
    for sd,s in eps: out.append('| %s | %s/%s | %s | %s | %s | %s | %s |'%(c,w,m,sd,s.get('status'),s.get('episode_valid'),f(s.get('rtf_true_mean')),f(s.get('img_drop_pct'))))
out.append('\n## Avoidance and responsiveness specifics\n')
for (c,w,m),eps in groups.items():
    if c=='quick_avoidance':
        out.append('- %s: '%w+'; '.join('%s trial_success=%s coll=%s src=%s goals Nav2 %s/%s, GT-reached %s%%'%(sd.replace('seed_',''),s.get('trial_success'),s.get('n_collisions'),s.get('collision_source'),s.get('nav_goals_succeeded'),s.get('nav_goals_total'),s.get('nav_success_gt_pct')) for sd,s in eps))
    if c=='quick_responsiveness':
        out.append('- %s: '%m+'; '.join('%s %s cmd->motion %s ms, stop %s ms (health %s)'%(sd.replace('seed_',''),s.get('status'),f(s.get('lat_cmd_motion_ms_mean')),f(s.get('lat_stop_ms_mean')),s.get('health_resp_cmd_motion_ms_mean') or s.get('health_lat_cmd_motion_ms_mean')) for sd,s in eps))
print('\n'.join(out))
