#!/usr/bin/env python3
"""Independently audit real NS-3 H4 data and regenerate tables and figures.

Run from the existing YeAH-TCP-NPE project:
    python3 scripts/analyze_H4.py

Reads ONLY results/raw/experiments/h4/{manifest,environment,batch_status,...}.
Outputs results/summary/h4 and results/figures/h4.
No measured datapoints are hard-coded. Every plotted point comes from CSV.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
from pathlib import Path

PROJECT = Path.home() / 'projects/YeAH-TCP-NPE'
ROOT = PROJECT / 'results/raw/experiments/h4'
SOURCE = PROJECT / 'simulation/yeah-experiment.cc'
RUNNER = PROJECT / 'scripts/run_H4.py'
OUT = PROJECT / 'results/summary/h4'
FIG = PROJECT / 'results/figures/h4'
SOURCE_HASH = '460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969'
RUNNER_HASH = 'c77cb78d9ab921a4994e778586473a1bf587e4b4e9bba75d3faf1313f6138c74'
COMMIT = '43dce6710b8df69685e3479c1d33a571dda714ea'
PARAM_COLUMNS = {'tcp1':'tcp1','tcp2':'tcp2','flows':'flows','capacity':'capacity_mbps',
  'rtt1':'rtt1_target_ms','rtt2':'rtt2_target_ms','bufferRatio':'buffer_ratio',
  'duration':'duration_s','flow2Start':'flow2_start_s','flow2Stop':'flow2_stop_s',
  'seed':'seed','run':'run','mss':'mss_bytes','initialCwnd':'initial_cwnd_segments',
  'initialSsthreshSegments':'initial_ssthresh_segments','loss':'loss_probability'}
CUM = ('rx1_bytes','rx2_bytes','wire_bytes','bottleneck_drops','other_drops','random_drops')


def require(cond, msg):
    if not cond: raise ValueError(msg)


def close(a,b,abs_tol=1e-7):
    return math.isclose(float(a),float(b),rel_tol=1e-8,abs_tol=abs_tol)


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for buf in iter(lambda:f.read(2**20),b''):h.update(buf)
    return h.hexdigest()


def obj(path):return json.loads(path.read_text(encoding='utf-8'))


def get_summary(path):
    with path.open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
    require(len(rows)==1,f'{path}: expected exactly one row')
    return rows[0]


def write_csv(path,rows,fields):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader();w.writerows(rows)


def fairness(g1,g2):
    return (g1+g2)**2/(2*(g1*g1+g2*g2)) if (g1*g2 or g1+g2)>0 else 0.


def audit(case,status,env):
    name=case['id'];p=case['params'];folder=ROOT/name
    require(obj(folder/'config.json')==case,f'{name}: config differs from manifest')
    own=obj(folder/'status.json')
    require(own==status,f'{name}: status differs from batch status')
    require(status.get('status')=='PASS' and status.get('returncode')==0,f'{name}: not successful')
    require(status.get('source_sha256')==SOURCE_HASH,f'{name}: source hash in status mismatch')
    for f in ('summary','timeseries'):
        require(sha(folder/f'{f}.csv')==status[f'{f}_sha256'],f'{name}: CSV sha256 mismatch')
    summary=get_summary(folder/'summary.csv')
    for k,column in PARAM_COLUMNS.items():
        actual=summary[column];expected=p[k]
        if isinstance(expected,str):require(actual==expected,f'{name}: {k} mismatch')
        else: require(close(actual,expected,abs_tol=1e-12),f'{name}: {k} mismatch')
    buffer_expected=max(1,math.floor(p['capacity']*1e6*min(p['rtt1'],p['rtt2'])/1000/(8*1500)*p['bufferRatio']))
    require(int(summary['buffer_packets'])==buffer_expected,f'{name}: buffer packet count mismatch')
    require(close(summary['bdp_packets'],p['capacity']*1e6*min(p['rtt1'],p['rtt2'])/1000/(8*1500)), f'{name}: BDP mismatch')
    count=0; queue_sum=0; queue_max=0; prev=None;bounds={}
    with (folder/'timeseries.csv').open(newline='',encoding='utf-8') as f:
        for r in csv.DictReader(f):
            require(close(r['time_s'],count*0.01,abs_tol=1e-7),f'{name}: unexpected sample time at {count}')
            q=int(r['queue_packets']);require(0<=q<=buffer_expected,f'{name}: queue exceeds buffer at {count}')
            if count<60000:
                queue_sum+=q;queue_max=max(queue_max,q)
            if prev is not None:
                require(all(int(r[k])>=int(prev[k]) for k in CUM),f'{name}: nonmonotone counter at {count}')
            if count in (0,30000,60000):bounds[count//100]=dict(r)
            prev=r; count+=1
    require(count==60001,f'{name}: expected 60001 samples, got {count}')
    require(int(status['samples'])==count,f'{name}: status samples mismatch')
    require(int(summary['queue_samples'])==60000,f'{name}: queue sampling count mismatch')
    require(close(summary['queue_mean_packets'],queue_sum/60000),f'{name}: queue mean mismatch')
    require(close(summary['queue_normalized'],queue_sum/(60000*buffer_expected)),f'{name}: queue normalized mismatch')
    require(int(summary['queue_max_sampled'])==queue_max,f'{name}: queue max mismatch')
    for k in CUM:
        if k in summary:require(int(summary[k])==int(prev[k]),f'{name}: trace final {k} mismatch')
    g1=int(prev['rx1_bytes'])*8/600e6;g2=int(prev['rx2_bytes'])*8/600e6;total=g1+g2
    wire=int(prev['wire_bytes'])*8/(600*p['capacity']*1e6)
    j=fairness(g1,g2)
    accepted=int(summary['queue_enqueued']);overflow=int(summary['bottleneck_drops'])
    prob=overflow/(accepted+overflow) if accepted+overflow>0 else 0.
    independent={
      'goodput1_mbps':g1,'goodput2_mbps':g2,'total_goodput_mbps':total,
      'goodput_over_capacity':total/p['capacity'], 'wire_utilization':wire,
      'jain_index':j,'overflow_probability':prob}
    for k,v in independent.items():require(close(summary[k],v),f'{name}: independent {k} mismatch')
    require(int(summary['random_drops'])<=int(summary['wire_packets']),f'{name}: random drops > observed tx')
    require(int(summary['other_drops'])==0,f'{name}: other drops nonzero: review required')
    require(int(summary['max_wire_packet_bytes'])<=1502,f'{name}: unexpected packet size')
    require(float(summary['min_rtt1_ms'])>=p['rtt1']-0.01 and float(summary['min_rtt2_ms'])>=p['rtt2']-0.01,f'{name}: RTT below target')
    require(int(status['random_drops'])==int(summary['random_drops']), f'{name}: random drops status mismatch')
    require(close(status['goodput_total_mbps'],total), f'{name}: total status mismatch')
    require(close(status['wire_utilization'],wire),f'{name}: utilization status mismatch')
    require(close(status['normalized_mean_queue'],summary['queue_normalized']),f'{name}: queue status mismatch')
    win=[]
    for lo,hi in [(0,300),(300,600)]:
        a,b=bounds[lo],bounds[hi];dt=hi-lo
        x1=(int(b['rx1_bytes'])-int(a['rx1_bytes']))*8/(dt*1e6)
        x2=(int(b['rx2_bytes'])-int(a['rx2_bytes']))*8/(dt*1e6)
        v=(int(b['wire_bytes'])-int(a['wire_bytes']))*8/(dt*p['capacity']*1e6)
        win.append(dict(case_id=name,algorithm=p['tcp1'],loss_configured=p['loss'],start_s=lo,end_s=hi,
                        goodput1_mbps=round(x1,9),goodput2_mbps=round(x2,9),
                        total_goodput_mbps=round(x1+x2,9),wire_utilization_pct=round(v*100,7),
                        random_drops=int(b['random_drops'])-int(a['random_drops']),
                        bottleneck_drops=int(b['bottleneck_drops'])-int(a['bottleneck_drops'])))
    row=dict(case_id=name,algorithm='YeAH' if p['tcp1']=='yeah' else 'NewReno',
             loss_configured=p['loss'],seed=p['seed'],run=p['run'],duration_s=p['duration'],
             capacity_mbps=p['capacity'],rtt1_ms=p['rtt1'],rtt2_ms=p['rtt2'],buffer_packets=buffer_expected,
             goodput1_mbps=round(g1,9),goodput2_mbps=round(g2,9),total_goodput_mbps=round(total,9),
             goodput_over_capacity_pct=round(total/p['capacity']*100,7),wire_utilization_pct=round(wire*100,7),
             queue_mean_packets=round(queue_sum/60000,7),queue_over_buffer_pct=round(queue_sum/(60000*buffer_expected)*100,8),
             overflow_drops=overflow,overflow_probability=round(prob,12),
             random_drops=int(summary['random_drops']),wire_packets=int(summary['wire_packets']),
             random_drops_per_wire_packet=round(int(summary['random_drops'])/int(summary['wire_packets']),11),
             jain_index=round(j,10),wall_seconds=status['wall_seconds'],samples=count)
    audit_row=dict(case_id=name,status='AUDIT_PASS',samples=count,summary_sha256=sha(folder/'summary.csv'),
                   timeseries_sha256=sha(folder/'timeseries.csv'),source_sha256=status['source_sha256'],
                   algorithm=p['tcp1'],loss_configured=p['loss'])
    print(f'AUDIT PASS: {name} {count} samples')
    return row,win,audit_row


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    series=[('YeAH',sorted([x for x in rows if x['algorithm']=='YeAH'],key=lambda r:r['loss_configured'])),
            ('NewReno',sorted([x for x in rows if x['algorithm']=='NewReno'],key=lambda r:r['loss_configured']))]
    specs=[('t4_loss_wire_utilization','wire_utilization_pct','Wire utilization (%)',
            'Wire utilization vs configured random loss probability'),
           ('t4_loss_goodput','total_goodput_mbps','Total application goodput (Mbps)',
            'Goodput vs configured random loss probability'),
           ('t4_loss_queue_normalized','queue_over_buffer_pct','Mean queue / buffer (%)',
            'Normalized queue vs configured random loss probability'),
           ('t4_loss_random_drops','random_drops','Observed random packet drops (count)',
            'Random loss count by configured probability')]
    for stem,metric,ylabel,title in specs:
        fig,ax=plt.subplots(figsize=(8.2,4.9))
        for name,data in series:
            ax.plot([r['loss_configured'] for r in data],[r[metric] for r in data],
                    marker='o',markersize=6,linewidth=1.8,label=name)
        ax.set_xscale('log');ax.set_xticks(sorted(set(r['loss_configured'] for r in rows)))
        from matplotlib.ticker import LogFormatterMathtext
        ax.xaxis.set_major_formatter(LogFormatterMathtext())
        ax.set_xlim(5e-9,2e-4);ax.set_ylim(bottom=0)
        ax.set_xlabel('Configured random packet-loss probability p')
        ax.set_ylabel(ylabel);ax.set_title(title)
        ax.grid(alpha=.25);ax.legend()
        fig.text(.5,.01,'NS-3.44 · 500 Mbps · RTT 200/200 ms · 600 s · seed/run=1/1',ha='center',fontsize=9)
        fig.tight_layout(rect=(0,.035,1,1))
        fig.savefig(FIG/f'{stem}.png',dpi=300,bbox_inches='tight')
        fig.savefig(FIG/f'{stem}.svg',bbox_inches='tight')
        plt.close(fig)


def main():
    for path in (ROOT,SOURCE,RUNNER):require(path.exists(),f'Missing project input: {path}')
    manifest=obj(ROOT/'manifest.json');env=obj(ROOT/'environment.json');status_list=obj(ROOT/'batch_status.json')
    require(env['version']=='3.44' and env['commit']==COMMIT,'Wrong NS-3 version/commit')
    require(env['profile']=='optimized','Unexpected build profile')
    require(env['source_sha256']==SOURCE_HASH==sha(SOURCE),'Source hash differs from H1-H3')
    require(env['python_script_sha256']==RUNNER_HASH==sha(RUNNER),'Runner hash mismatch')
    require(manifest['batch']=='H4' and manifest['duration']==600, 'Incorrect manifest')
    cases=manifest['cases'];require(len(cases)==8,'Expected exactly 8 scenarios')
    cases_by_id={c['id']:c for c in cases};statuses={s['id']:s for s in status_list}
    require(len(cases_by_id)==len(statuses)==8 and set(statuses)==set(cases_by_id),'Case IDs missing/duplicated')
    expect_prob={1e-8,1e-6,1e-5,1e-4};actual_pairs=set()
    for c in cases:
        p=c['params'];actual_pairs.add((p['tcp1'],p['loss']))
        require(p['tcp1']==p['tcp2'] and p['tcp1'] in ('yeah','reno'),'Bad TCP pairing')
        require(p['rtt1']==p['rtt2']==200 and p['capacity']==500 and p['bufferRatio']==1,
                'Unexpected RTT/capacity/buffer')
        require(p['duration']==600 and p['flow2Start']==0 and p['flow2Stop']==600,
                'Unexpected start/stop/duration')
        require(p['mss']==1448 and p['seed']==p['run']==1 and p['flows']==2,
                'Unexpected MSS/seed/flow count')
        require(p['initialCwnd']==10 and p['initialSsthreshSegments']==0,'Unexpected TCP init')
    require(actual_pairs=={(a,p) for a in ('yeah','reno') for p in expect_prob},'Unexpected/missing case combinations')
    OUT.mkdir(parents=True,exist_ok=True);FIG.mkdir(parents=True,exist_ok=True)
    rows=[];windows=[];audits=[]
    for case in cases:
        r,w,a=audit(case,statuses[case['id']],env);rows.append(r);windows.extend(w);audits.append(a)
    rows.sort(key=lambda r:(r['loss_configured'],r['algorithm']))
    windows.sort(key=lambda r:(r['loss_configured'],r['algorithm'],r['start_s']))
    write_csv(OUT/'h4_summary_verified.csv',rows,list(rows[0]))
    comparison=[dict(loss_configured=p,algorithm=a,**{k:r[k] for k in (
      'total_goodput_mbps','goodput_over_capacity_pct','wire_utilization_pct','queue_over_buffer_pct',
      'overflow_drops','random_drops','jain_index')}) for p in sorted(expect_prob) for a in ('YeAH','NewReno')
      for r in rows if r['loss_configured']==p and r['algorithm']==a]
    write_csv(OUT/'t4_loss_comparison.csv',comparison,list(comparison[0]))
    write_csv(OUT/'t4_time_windows.csv',windows,list(windows[0]))
    (OUT/'h4_audit.json').write_text(json.dumps(dict(result='PASS',cases=audits,
     inputs=dict(ns3_version=env['version'],commit=env['commit'],source_sha256=SOURCE_HASH,
       runner_sha256=RUNNER_HASH, profile=env['profile']),
     cautions=['Single run per TCP/p; no confidence interval',
       'p is configured, not measured rate',
       'Random drops on receiving bottleneck device and queue overflow drops are distinct',
       'Configured p=1e-8 produced zero observed random drops in both cases',
       'Figure 5 physical Linux testbed is not identical to NS-3 implementation']),indent=2,ensure_ascii=False)+'\n')
    plot(rows)
    print('VERIFIED H4: 8/8, source and hashes match, metrics recomputed')
    print(f'OUTPUT: {OUT}')
    print(f'FIGURES: {FIG}')

if __name__=='__main__': main()
