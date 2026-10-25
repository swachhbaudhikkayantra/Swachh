import json,glob,os,sys,collections,statistics as st
sys.path.insert(0,os.path.expanduser('~/Swachh/Navigation/Simulation/vacuum_ws/src/vacuum_eval'))
from vacuum_eval.make_report import pooled_cluster_ci
R=os.path.expanduser('~/eval_runs')
CAMP={'EXP':'quick_exploration_noise','NAV':'quick_navigation','AVO':'quick_avoidance','RES':'quick_responsiveness'}
def load(c):
    out=[]
    for f in sorted(glob.glob('%s/%s/*/*/seed_*/summary.json'%(R,CAMP[c]))):
        s=json.load(open(f)); p=f.split('/'); s.setdefault('world',p[-4]); s['_method']=p[-3]; s['_path']=f; out.append(s)
    return out
S={c:load(c) for c in CAMP}
# (id, name, campaign, key, health_key, scale, filter)
M=[('1','Coverage explored','EXP','coverage_explored_pct',None,1,None),
('2','Steps: goals / recoveries per episode','EXP','n_goals','n_goals',1,None),
('3','Total collisions per episode','EXP','n_collisions',None,1,None),
('3n','Total collisions per episode (navigation)','NAV','n_collisions',None,1,None),
('4','Obstacle avoidance %','EXP','avoidance_pct',None,1,None),
('4a','Obstacle avoidance % (avoidance scenarios)','AVO','avoidance_pct',None,1,None),
('5','Responsiveness: step cmd->motion latency (ms, loaded)','RES','lat_cmd_motion_ms_mean','responsiveness_pct',1,lambda s:s['_method']=='responsiveness_loaded'),
('5s','Responsiveness: stop latency (ms, loaded)','RES','lat_stop_ms_mean','responsiveness_pct',1,lambda s:s['_method']=='responsiveness_loaded'),
('6','ATE (SLAM, fixed frame)','EXP','ate_fixed_rmse_m',None,1,None),
('7','RPE (1 m)','EXP','rpe_trans_rmse_m_1m',None,1,None),
('8','Map completeness','EXP','map_completeness_pct',None,1,None),
('9','Avoidance trial success (% from trial_success)','AVO','trial_success',None,100,None),
('10','Navigation success, GT-verified','NAV','nav_success_gt_pct',None,1,None),
('11p','Loop-closure precision','EXP','lc_precision_pct',None,1,None),
('11r','Loop-closure recall','EXP','lc_recall_pct','lc_precision_pct',1,None),
('12','Path length ratio','NAV','path_length_ratio_mean',None,1,None),
('14','Cleaning efficiency','EXP','cleaning_efficiency',None,1,None),
('A1','Time to 50 % explored (s)','EXP','t_to_50_explored_s','coverage_explored_pct',1,None),
('A1b','Explored AUC','EXP','coverage_explored_auc','coverage_explored_pct',1,None),
('A2','Overlap ratio','EXP','overlap_ratio',None,1,None),
('A3','Missed area (m2)','EXP','missed_area_m2',None,1,None),
('A4','Distance GT (m)','EXP','distance_gt_m',None,1,None),
('A4e','Energy proxy (m2/s)','EXP','energy_proxy_m2ps',None,1,None),
('A5','Min clearance (m)','AVO','min_clearance_m',None,1,None),
('A6','Recoveries per episode','NAV','n_recoveries',None,1,None),
('A7','Stuck/timeout goals per episode','NAV','n_stuck_goals',None,1,None),
('A8','Planning latency (time to first plan, mean ms)','NAV','plan_latency_ms_mean',None,1,None),
('A9','Path smoothness (1/m)','NAV','smooth_curvature_rms_1pm',None,1,None),
('A10','Odometry drift ratio','EXP','odom_drift_ratio',None,1,None),
('A11','CPU total mean (%)','EXP','cpu_total_mean_pct',None,1,None),
('A12','True RTF (all test episodes)','ALL','rtf_true_mean',None,1,None),
('A14','AMCL localization error (m)','NAV','loc_error_mean_m',None,1,None)]
S['ALL']=S['EXP']+S['NAV']+S['AVO']+S['RES']
rows=[]
for mid,name,c,key,hk,sc,flt in M:
    eps=[s for s in S[c] if (flt is None or flt(s))]
    vals=[dict(s, **{key:(s[key]*sc if isinstance(s.get(key),(int,float)) else s.get(key))}) for s in eps]
    p=pooled_cluster_ci(vals,key)
    ndata=sum(1 for s in eps if isinstance(s.get(key),(int,float)))
    nvalid=sum(1 for s in eps if isinstance(s.get(key),(int,float)) and s.get('status')=='ok' and s.get('episode_valid'))
    h=collections.Counter(s.get('health_'+(hk or key)) for s in eps if s.get('health_'+(hk or key)) is not None)
    rows.append(dict(id=mid,name=name,campaign=CAMP.get(c,'all quick_*'),key=key,value=None if p is None else p,ndata=ndata,nvalid=nvalid,neps=len(eps),health=dict(h)))
json.dump(rows,open(os.path.dirname(os.path.abspath(__file__))+'/table.json','w'),indent=1,default=str)
for r in rows:
    v=r['value']
    vs='–' if v is None else ('%.4g [%.4g, %.4g]'%(v[0],v[1],v[2]) if isinstance(v,(tuple,list)) and len(v)>=3 else str(v))
    print('%-4s %-48s %-24s %-28s data %2d/%2d valid %2d  %s'%(r['id'],r['name'][:48],r['campaign'],vs,r['ndata'],r['neps'],r['nvalid'],r['health']))
