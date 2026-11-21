#!/usr/bin/env python3
"""Audit actual H3 NS-3.44 outputs and recreate H3 tables and figures.

Input: results/raw/experiments/h3/ (never modified)
Output: results/summary/h3/ and results/figures/h3/
Command: python3 scripts/analyze_H3.py

No hard-coded measured data. Experimental parameters are checked, not inferred.
Comparison windows [0,300] and [300,600] are derived from cumulative sink bytes.
Each point is one run (seed=1, run=1): no statistical uncertainty inferred.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

PROJECT = Path.home() / 'projects/YeAH-TCP-NPE'
ROOT = PROJECT / 'results/raw/experiments/h3'
SOURCE = PROJECT / 'simulation/yeah-experiment.cc'
RUNNER = PROJECT / 'scripts/run_H3.py'
SUMMARY_DIR = PROJECT / 'results/summary/h3'
FIGURES_DIR = PROJECT / 'results/figures/h3'
CUM_FIELDS = ('rx1_bytes','rx2_bytes','wire_bytes','bottleneck_drops','other_drops','random_drops')
PARAM_COLS = {'tcp1':'tcp1','tcp2':'tcp2','flows':'flows','capacity':'capacity_mbps',
              'rtt1':'rtt1_target_ms','rtt2':'rtt2_target_ms','bufferRatio':'buffer_ratio',
              'duration':'duration_s','loss':'loss_probability','flow2Start':'flow2_start_s',
              'flow2Stop':'flow2_stop_s','seed':'seed','run':'run','mss':'mss_bytes',
              'initialCwnd':'initial_cwnd_segments',
              'initialSsthreshSegments':'initial_ssthresh_segments'}


def require(ok: bool, why: str) -> None:
    if not ok:
        raise ValueError(why)


def near(actual, expected, *, eps=1e-7) -> bool:
    return math.isclose(float(actual),float(expected),rel_tol=1e-9,abs_tol=eps)


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def load_summary(path: Path):
    with path.open(newline='',encoding='utf-8') as f:
        rows=list(csv.DictReader(f))
    require(len(rows)==1,f'{path}: expected one row')
    return rows[0]


def put_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def fairness(a: float,b: float)->float:
    return (a+b)**2/(2*(a*a+b*b)) if a+b>0 else 0.


def interval(boundaries: dict, a: int, b:int, capacity:float)->dict:
    left,right=boundaries[a],boundaries[b]
    seconds=b-a
    x1=(int(right['rx1_bytes'])-int(left['rx1_bytes']))*8/(seconds*1e6)
    x2=(int(right['rx2_bytes'])-int(left['rx2_bytes']))*8/(seconds*1e6)
    wire=(int(right['wire_bytes'])-int(left['wire_bytes']))*8/(seconds*capacity*1e6)
    return dict(start_s=a,end_s=b,goodput1_mbps=round(x1,9),goodput2_mbps=round(x2,9),
                goodput_total_mbps=round(x1+x2,9),jain_index=round(fairness(x1,x2),10),
                wire_utilization_pct=round(wire*100,8))


def audit_one(case:dict, batch:dict, environment:dict):
    case_id=case['id']
    params=case['params']
    folder=ROOT/case_id
    status=load_json(folder/'status.json')
    require(status==batch, f'{case_id}: status.json differs from batch_status.json')
    require(status.get('status')=='PASS' and status.get('returncode')==0,
            f'{case_id}: simulation did not finish successfully')
    require(load_json(folder/'config.json')==case,f'{case_id}: config differs from manifest')
    require(status.get('source_sha256')==environment['source_sha256'],f'{case_id}: source hash differs')
    require(sha256(folder/'summary.csv')==status['summary_sha256'],f'{case_id}: summary hash mismatch')
    require(sha256(folder/'timeseries.csv')==status['timeseries_sha256'],f'{case_id}: trace hash mismatch')
    log=(folder/'run.log').read_text(encoding='utf-8')
    require('summary.csv and timeseries.csv' in log,f'{case_id}: missing completed run message')
    for i,tcp in enumerate((params['tcp1'],params['tcp2'])):
        name={'yeah':'TcpYeah','reno':'TcpNewReno'}[tcp]
        require(f'Node {i} SocketType=ns3::{name}' in log,
                f'{case_id}: {name} not confirmed in log')
    s=load_summary(folder/'summary.csv')
    for key,col in PARAM_COLS.items():
        want=params[key]
        require(s[col]==want if isinstance(want,str) else near(s[col],want,eps=1e-9),
                f'{case_id}: {col} differs from manifest')
    require(params['rtt1']==25 and params['rtt2'] in (25,50,75,100),f'{case_id}: RTT matrix differs')
    require(params['tcp1']==params['tcp2'] and params['tcp1'] in ('yeah','reno'),f'{case_id}: TCP matrix differs')
    require(params['duration']==600 and params['flows']==2 and params['capacity']==500,
            f'{case_id}: duration, flows or bottleneck differs')
    require(params['bufferRatio']==1 and params['loss']==0 and params['flow2Start']==0 and params['flow2Stop']==600,
            f'{case_id}: buffer, loss or application timing differs')
    require(params['mss']==1448 and params['seed']==1 and params['run']==1,
            f'{case_id}: MSS or RNG differs')
    require(params['initialCwnd']==10 and params['initialSsthreshSegments']==0,
            f'{case_id}: initial window differs')
    expected_buffer=math.floor(500e6*0.025/(8*1500))
    buffer=int(s['buffer_packets'])
    require(buffer==expected_buffer==1041,f'{case_id}: buffer mismatch')
    qsum=qmax=0
    row_count=0
    last=prev=None
    boundaries={}
    with (folder/'timeseries.csv').open(newline='',encoding='utf-8') as f:
        for row in csv.DictReader(f):
            require(near(row['time_s'],row_count/100,eps=1e-8),
                    f'{case_id}: time mismatch at sample {row_count}')
            q=int(row['queue_packets'])
            require(0<=q<=buffer,f'{case_id}: queue out of range at {row_count}')
            if row_count<60000:
                qsum+=q
                qmax=max(qmax,q)
            if row_count in (0,30000,60000):
                boundaries[row_count//100]=row
            if prev is not None:
                for col in CUM_FIELDS:
                    require(int(row[col])>=int(prev[col]),
                            f'{case_id}: decreasing {col} at {row_count}')
            prev=row
            last=row
            row_count+=1
    require(row_count==60001,f'{case_id}: expected 60001 samples, got {row_count}')
    require(set(boundaries)=={0,300,600},f'{case_id}: incomplete window boundaries')
    require(status['samples']==row_count,f'{case_id}: status samples mismatch')
    require(int(s['queue_samples'])==60000,f'{case_id}: summary queue sample count mismatch')
    require(int(s['queue_max_sampled'])==qmax,f'{case_id}: queue max mismatch')
    qmean=qsum/60000
    g1=int(last['rx1_bytes'])*8/(600*1e6)
    g2=int(last['rx2_bytes'])*8/(600*1e6)
    g=g1+g2
    util=int(last['wire_bytes'])*8/(600*500e6)
    drops=int(last['bottleneck_drops'])
    enqueued=int(s['queue_enqueued'])
    pdrop=drops/(drops+enqueued) if drops+enqueued else 0
    computed={'goodput1_mbps':g1,'goodput2_mbps':g2,'total_goodput_mbps':g,
              'goodput_over_capacity':g/500,'wire_utilization':util,
              'queue_mean_packets':qmean,'queue_normalized':qmean/buffer,
              'overflow_probability':pdrop,'jain_index':fairness(g1,g2)}
    for k,v in computed.items():
        require(near(s[k],v),f'{case_id}: {k} fails recomputation')
    for col in ('rx1_bytes','rx2_bytes','bottleneck_drops','other_drops','random_drops'):
        require(int(s[col])==int(last[col]),f'{case_id}: {col} final trace mismatch')
    require(int(s['other_drops'])==0 and int(s['random_drops'])==0,
            f'{case_id}: unexpected non-overflow drops')
    require(near(status['goodput_total_mbps'],g) and near(status['wire_utilization'],util)
            and near(status['normalized_mean_queue'],qmean/buffer),
            f'{case_id}: status computed values mismatch')
    require(status['buffer_packets']==buffer,f'{case_id}: buffer in status differs')
    require(float(s['min_rtt1_ms'])>=25-0.01 and
            float(s['min_rtt2_ms'])>=params['rtt2']-0.01,
            f'{case_id}: min measured RTT below target')
    ratio=int(params['rtt2']/params['rtt1'])
    rec={'id':case_id,'tcp':params['tcp1'],'rtt1_ms':params['rtt1'],
         'rtt2_ms':params['rtt2'],'rtt_ratio':ratio,'duration_s':600,
         'buffer_packets':buffer,'seed':1,'run':1,
         'goodput1_mbps':round(g1,10),'goodput2_mbps':round(g2,10),
         'total_goodput_mbps':round(g,10),'jain_whole_600s':round(fairness(g1,g2),10),
         'wire_utilization_pct':round(util*100,8),
         'queue_mean_packets':round(qmean,9),
         'queue_over_buffer_pct':round(qmean/buffer*100,8),
         'overflow_drops':drops,
         'overflow_per_million_attempts':round(pdrop*1e6,8),
         'wall_seconds':round(float(status['wall_seconds']),6),
         'summary_sha256':status['summary_sha256'],
         'timeseries_sha256':status['timeseries_sha256']}
    windows=[]
    for a,b in ((0,300),(300,600)):
        windows.append({'id':case_id,'tcp':params['tcp1'],'rtt_ratio':ratio,
                        **interval(boundaries,a,b,500)})
    return rec,windows


def draw(summary:list[dict],windows:list[dict]):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    FIGURES_DIR.mkdir(parents=True,exist_ok=True)
    data={(r['tcp'],r['rtt_ratio']):r for r in summary}
    win={(r['tcp'],r['rtt_ratio'],r['start_s']):r for r in windows}
    ratios=[1,2,3,4]

    def save(fig,name):
        fig.tight_layout()
        fig.savefig(FIGURES_DIR/(name+'.png'),dpi=300,bbox_inches='tight')
        fig.savefig(FIGURES_DIR/(name+'.svg'),bbox_inches='tight')
        plt.close(fig)

    fig,ax=plt.subplots(figsize=(7.2,4.4))
    for algo,label in (('yeah','YeAH'),('reno','NewReno')):
        ax.plot(ratios,[data[(algo,x)]['jain_whole_600s'] for x in ratios],marker='o',label=label)
    ax.set(xlabel='RTT2 / RTT1',ylabel="Jain's fairness index",title='H3: Fairness across RTT ratios (0-600 s)',ylim=(0.5,1.02))
    ax.set_xticks(ratios)
    ax.grid(alpha=0.25)
    ax.legend()
    save(fig,'t3_rtt_ratio_fairness_0_600')

    fig,ax=plt.subplots(figsize=(7.2,4.4))
    for algo,label in (('yeah','YeAH'),('reno','NewReno')):
        ax.plot(ratios,[win[(algo,x,300)]['jain_index'] for x in ratios],marker='o',label=label)
    ax.set(xlabel='RTT2 / RTT1',ylabel="Jain's fairness index",title='H3: Fairness in 300-600 s window',ylim=(0.5,1.02))
    ax.set_xticks(ratios)
    ax.grid(alpha=0.25)
    ax.legend()
    save(fig,'t3_rtt_ratio_fairness_300_600')

    fig,ax=plt.subplots(figsize=(7.2,4.5))
    for algo in ('yeah','reno'):
        for i in (1,2):
            ax.plot(ratios,[data[(algo,x)][f'goodput{i}_mbps'] for x in ratios],marker='o',
                    label=f'{"YeAH" if algo=="yeah" else "NewReno"} flow {i}')
    ax.set(xlabel='RTT2 / RTT1',ylabel='Application goodput (Mbps)',
           title='H3: Per-flow goodput (0-600 s)',ylim=(0,500))
    ax.set_xticks(ratios)
    ax.grid(alpha=0.25)
    ax.legend(ncol=2)
    save(fig,'t3_rtt_ratio_per_flow_goodput')

    fig,ax=plt.subplots(figsize=(7.2,4.4))
    for algo,label in (('yeah','YeAH'),('reno','NewReno')):
        ax.plot(ratios,[data[(algo,x)]['queue_over_buffer_pct'] for x in ratios],marker='o',label=label)
    ax.set(xlabel='RTT2 / RTT1',ylabel='Mean queue / buffer (%)',
           title='H3: Normalized bottleneck queue (0-600 s)',ylim=(0,100))
    ax.set_xticks(ratios)
    ax.grid(alpha=0.25)
    ax.legend()
    save(fig,'t3_rtt_ratio_queue')


def main():
    require(ROOT.is_dir(),f'Missing raw H3 folder: {ROOT}')
    manifest=load_json(ROOT/'manifest.json')
    environment=load_json(ROOT/'environment.json')
    batch_list=load_json(ROOT/'batch_status.json')
    require(manifest['batch']=='H3' and manifest['duration']==600 and len(manifest['cases'])==8,
            'H3 manifest invalid')
    require(environment['version']=='3.44' and
            environment['commit']=='43dce6710b8df69685e3479c1d33a571dda714ea'
            and environment['profile']=='optimized', 'Environment differs')
    require(sha256(SOURCE)==environment['source_sha256'], 'Simulation source SHA256 mismatch')
    require(sha256(RUNNER)==environment['python_script_sha256'], 'H3 runner SHA256 mismatch')
    batch={s['id']:s for s in batch_list}
    ids={c['id'] for c in manifest['cases']}
    require(len(ids)==8 and set(batch)==ids,'Status/manifest IDs not 8 unique entries')
    require(ids=={f't3-{tcp}-ratio{ratio}' for tcp in ('reno','yeah') for ratio in range(1,5)},
            'Unexpected experiment matrix')
    results=[]
    windows=[]
    audits=[]
    for case in manifest['cases']:
        rec,parts=audit_one(case,batch[case['id']],environment)
        results.append(rec)
        windows.extend(parts)
        audits.append({'id':case['id'],'status':'PASS','samples':60001,
                       'summary_sha256':rec['summary_sha256'],
                       'timeseries_sha256':rec['timeseries_sha256'],
                       'jain_whole_600s':rec['jain_whole_600s']})
        print(f'AUDIT PASS: {case["id"]} 60001 samples',flush=True)
    results.sort(key=lambda x:(x['rtt_ratio'],x['tcp']))
    windows.sort(key=lambda x:(x['rtt_ratio'],x['tcp'],x['start_s']))
    SUMMARY_DIR.mkdir(parents=True,exist_ok=True)
    put_csv(SUMMARY_DIR/'h3_summary_verified.csv',results,list(results[0]))
    put_csv(SUMMARY_DIR/'t3_fairness_windows.csv',windows,list(windows[0]))
    rows=[]
    for ratio in (1,2,3,4):
        yeah=next(r for r in results if r['tcp']=='yeah' and r['rtt_ratio']==ratio)
        reno=next(r for r in results if r['tcp']=='reno' and r['rtt_ratio']==ratio)
        rows.append({'rtt_ratio':ratio,'rtt1_ms':25,'rtt2_ms':ratio*25,
                     'jain_yeah_600s':yeah['jain_whole_600s'],
                     'jain_reno_600s':reno['jain_whole_600s'],
                     'jain_difference_yeah_minus_reno':round(yeah['jain_whole_600s']-reno['jain_whole_600s'],10)})
    put_csv(SUMMARY_DIR/'t3_fairness_comparison.csv',rows,list(rows[0]))
    (SUMMARY_DIR/'h3_audit.json').write_text(json.dumps({'batch':'H3','status':'PASS',
        'source_sha256':environment['source_sha256'],
        'runner_sha256':environment['python_script_sha256'],
        'environment':{'version':environment['version'],'commit':environment['commit'],
                       'profile':environment['profile']},
        'cases':audits},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    draw(results,windows)
    print('VERIFIED H3: 8/8, source and hashes match, metrics recomputed')
    print('OUTPUT:',SUMMARY_DIR)
    print('FIGURES:',FIGURES_DIR)


if __name__=='__main__':
    main()
