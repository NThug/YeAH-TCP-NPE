#!/usr/bin/env python3
"""Reproducible H1 audit + tables + figures. Uses ONLY raw CSV/JSON/log.

Install plot dependency on Ubuntu: sudo apt install python3-matplotlib
Run from WSL: python3 scripts/analyze_H1.py
Output: results/summary/h1 and results/figures/h1
Source: H1 simulation 600s, ns-3.44, one run/setting.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda: file.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def read_one_csv(path: Path) -> dict:
    with path.open(newline='') as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1:
        raise ValueError(f'Expected exactly 1 row: {path}, got {len(rows)}')
    return rows[0]


def near(actual: float, expected: float, tol: float = 1e-8) -> bool:
    return math.isclose(actual, expected, rel_tol=1e-10, abs_tol=tol)


def need(cond: bool, message: str):
    if not cond:
        raise ValueError(message)


def write_csv(path: Path, rows: list[dict], columns: list[str]):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def audit_case(case: dict, root: Path, full_source: Path):
    case_id = case['id']
    params = case['params']
    folder = root / case_id
    status = json.loads((folder / 'status.json').read_text())
    saved_config = json.loads((folder / 'config.json').read_text())
    need(saved_config == case, f'{case_id}: config does not match manifest')
    need(status['status'] == 'PASS' and status['returncode'] == 0, f'{case_id}: not PASS')
    need(sha(folder / 'summary.csv') == status['summary_sha256'], f'{case_id}: summary sha mismatch')
    need(sha(folder / 'timeseries.csv') == status['timeseries_sha256'], f'{case_id}: series sha mismatch')
    s = read_one_csv(folder / 'summary.csv')
    mapping = {'tcp1': 'tcp1', 'tcp2': 'tcp2', 'flows': 'flows', 'capacity': 'capacity_mbps',
               'rtt1': 'rtt1_target_ms', 'rtt2': 'rtt2_target_ms', 'bufferRatio': 'buffer_ratio',
               'duration': 'duration_s', 'loss': 'loss_probability', 'seed': 'seed', 'run': 'run',
               'mss': 'mss_bytes', 'initialCwnd': 'initial_cwnd_segments',
               'initialSsthreshSegments': 'initial_ssthresh_segments',
               'flow2Start': 'flow2_start_s', 'flow2Stop': 'flow2_stop_s'}
    for key, col in mapping.items():
        a = s[col] if isinstance(params[key], str) else float(s[col])
        need(a == params[key], f'{case_id}: config mismatch at {col}: {a} != {params[key]}')
    target_buffer = max(1, math.floor(params['capacity'] * 1e6 * min(params['rtt1'], params['rtt2']) / 1000.0 / (8*1500) * params['bufferRatio']))
    need(int(s['buffer_packets']) == target_buffer, f'{case_id}: buffer mismatch')
    log = (folder / 'run.log').read_text()
    need('Saved ' in log and 'summary.csv and timeseries.csv' in log,
         f'{case_id}: log missing completion confirmation')
    for node_id, tcp_key in ((0, 'tcp1'), (1, 'tcp2')):
        tcp_class = {'yeah':'TcpYeah', 'reno':'TcpNewReno'}[params[tcp_key]]
        need(f'Node {node_id} SocketType=ns3::{tcp_class}' in log,
             f'{case_id}: Node {node_id} socket type not confirmed by run.log')

    final = None
    prev = None
    rows = []
    qsum, qmax = 0, 0
    last_rx2_change = None
    last_rx1_change = None
    monotone = ('rx1_bytes', 'rx2_bytes', 'wire_bytes', 'bottleneck_drops', 'other_drops', 'random_drops')
    with (folder / 'timeseries.csv').open(newline='') as f:
        for idx, record in enumerate(csv.DictReader(f)):
            t = float(record['time_s'])
            q = int(record['queue_packets'])
            need(near(t, idx / 100, 1e-7), f'{case_id}: invalid sample time at row {idx}')
            need(0 <= q <= target_buffer, f'{case_id}: queue limit violated at {t}s')
            if idx < int(params['duration'] * 100):
                qsum += q
                qmax = max(qmax, q)
            if prev:
                for field in monotone:
                    need(int(record[field]) >= int(prev[field]), f'{case_id}: {field} counter decreased at {t}s')
                if int(record['rx1_bytes']) > int(prev['rx1_bytes']):
                    last_rx1_change = t
                if int(record['rx2_bytes']) > int(prev['rx2_bytes']):
                    last_rx2_change = t
            # Keep 60,001 records (8 cases) in memory only for processing; do not edit raw files.
            rows.append(record)
            prev = record
            final = record
    need(len(rows) == int(params['duration'] * 100) + 1, f'{case_id}: wrong number of samples')
    n = len(rows) - 1
    need(int(s['queue_samples']) == n, f'{case_id}: queue sample count mismatch')
    need(near(qsum / n, float(s['queue_mean_packets'])), f'{case_id}: queue mean mismatch')
    need(qmax == int(s['queue_max_sampled']), f'{case_id}: queue max mismatch')
    for field in ('rx1_bytes','rx2_bytes','bottleneck_drops','other_drops','random_drops'):
        need(int(s[field]) == int(final[field]), f'{case_id}: {field} final counter mismatch')
    gp1 = int(final['rx1_bytes']) * 8 / params['duration'] / 1e6
    gp2 = int(final['rx2_bytes']) * 8 / params['duration'] / 1e6
    util = int(final['wire_bytes']) * 8 / params['duration'] / (params['capacity'] * 1e6)
    fair = (gp1 + gp2)**2 / (2 * (gp1*gp1 + gp2*gp2)) if gp1+gp2 else 0
    enqueued, overflow = int(s['queue_enqueued']), int(final['bottleneck_drops'])
    overflow_p = overflow / (enqueued + overflow) if (enqueued + overflow) else 0
    calculated = {'goodput1_mbps': gp1, 'goodput2_mbps': gp2, 'total_goodput_mbps': gp1+gp2,
                  'goodput_over_capacity': (gp1+gp2)/params['capacity'], 'wire_utilization': util,
                  'queue_mean_packets': qsum/n, 'queue_normalized': qsum/n/target_buffer,
                  'overflow_probability': overflow_p, 'jain_index': fair}
    for field, value in calculated.items():
        need(near(float(s[field]), value), f'{case_id}: discrepancy in {field}: {s[field]} vs {value}')

    report = {'id':case_id, 'group':case['group'], 'tcp1':params['tcp1'], 'tcp2':params['tcp2'],
              'rtt1_ms':params['rtt1'], 'rtt2_ms':params['rtt2'], 'duration_s':params['duration'],
              'capacity_mbps':params['capacity'], 'buffer_packets':target_buffer,
              'seed':params['seed'], 'run':params['run'],
              'flow2_start_s':params['flow2Start'], 'flow2_stop_s':params['flow2Stop'],
              'rx1_bytes':int(final['rx1_bytes']), 'rx2_bytes':int(final['rx2_bytes']),
              'goodput1_mbps':round(gp1,10), 'goodput2_mbps':round(gp2,10),
              'total_goodput_mbps':round(gp1+gp2,10),
              'goodput_over_capacity_pct':round((gp1+gp2)/params['capacity']*100,8),
              'wire_utilization_pct':round(util*100,8),
              'queue_mean_packets':round(qsum/n,10), 'queue_over_buffer_pct':round(qsum/n/target_buffer*100,8),
              'queue_max_sampled':qmax, 'queue_enqueued':enqueued,
              'overflow_drops':overflow, 'overflow_per_million_attempts':round(overflow_p*1e6,6),
              'random_drops':int(final['random_drops']), 'other_drops':int(final['other_drops']),
              'jain_whole_600s':round(fair,10),
              'flow2_last_rx_increase_s':last_rx2_change if last_rx2_change is not None else '',
              'wall_seconds':round(status['wall_seconds'],3),
              'summary_sha256':status['summary_sha256'], 'timeseries_sha256':status['timeseries_sha256']}
    return report, rows


def interval_stats(rows: list[dict], a: int, b: int) -> dict:
    left = rows[a * 100]
    right = rows[b * 100]
    dur = b-a
    x1 = (int(right['rx1_bytes'])-int(left['rx1_bytes'])) * 8 / dur / 1e6
    x2 = (int(right['rx2_bytes'])-int(left['rx2_bytes'])) * 8 / dur / 1e6
    mean_q = sum(int(r['queue_packets']) for r in rows[a*100:b*100]) / (dur * 100)
    return {'from_s':a, 'to_s':b, 'goodput1_mbps':round(x1,6),
            'goodput2_mbps':round(x2,6), 'total_goodput_mbps':round(x1+x2,6),
            'queue_mean_packets':round(mean_q,6)}


def sec_means(rows: list[dict], column: str) -> tuple[list[float], list[float]]:
    xs = list(range(600))
    ys = [sum(float(r[column]) for r in rows[s*100:(s+1)*100])/100 for s in xs]
    return xs, ys


def make_plots(data: dict, reports: dict, figs: Path):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError as e:
        raise SystemExit('Need matplotlib: sudo apt install python3-matplotlib') from e
    plt.rcParams.update({'font.size':10, 'figure.dpi':120, 'savefig.dpi':300})
    output_provenance = []
    def save(fig, name: str, case_ids: list[str], measure: str):
        for suffix in ('.png','.svg'):
            fig.savefig(figs/(name+suffix),dpi=300,bbox_inches='tight')
        plt.close(fig)
        output_provenance.append({'figure':name, 'case_ids':case_ids, 'measure':measure, 'source':'timeseries.csv or summary.csv in the specified case folders'})

    for case_id in ('t0-yeah-yeah','t0-yeah-reno'):
        rows = data[case_id]
        params = reports[case_id]
        x, v1 = sec_means(rows,'cwnd1_bytes')
        _, v2 = sec_means(rows,'cwnd2_bytes')
        fig, ax = plt.subplots(figsize=(10,4.6))
        ax.plot(x,[v/1448 for v in v1],label='Flow 1: YeAH')
        # After flow 2 stops, its last stored cwnd is repeated by the sampler.
        # Mask inactive samples for display only; raw data remains unchanged.
        # The last received-data timestamp is an observation, not proof of TCP close.
        last_rx = params['flow2_last_rx_increase_s']
        flow2_visible = [v/1448 if params['flow2_start_s'] <= sec <= last_rx else float('nan')
                         for sec,v in zip(x,v2)]
        ax.plot(x,flow2_visible,label='Flow 2: '+('YeAH' if params['tcp2']=='yeah' else 'NewReno'))
        ax.axvline(60,ls='--',alpha=.65,label='Flow 2 app start: 60s')
        ax.axvline(400,ls=':',alpha=.65,label='Flow 2 app stop: 400s')
        ax.set(xlabel='Simulation time (s)', ylabel='Congestion window (segments)',
               title=f'H1 / {case_id}: cwnd (mean over each 1s window)',xlim=(0,600))
        ax.grid(alpha=.22);ax.legend(fontsize=9);fig.tight_layout()
        save(fig,f'{case_id}_cwnd',[''+case_id], 'cwnd_bytes/1448, mean of 100 samples per second; flow 2 hidden outside observed RX activity')

        x,q=sec_means(rows,'queue_packets')
        fig,ax=plt.subplots(figsize=(10,4.3))
        ax.plot(x,[v/params['buffer_packets']*100 for v in q], label='Measured bottleneck FIFO queue')
        ax.axvline(60,ls='--',alpha=.65,label='Flow 2 app start: 60s')
        ax.axvline(400,ls=':',alpha=.65,label='Flow 2 app stop: 400s')
        ax.set(xlabel='Simulation time (s)', ylabel='Mean queue / buffer (%)',
               title=f'H1 / {case_id}: physical queue (1s average)',xlim=(0,600),ylim=(0,105))
        ax.grid(alpha=.22);ax.legend(fontsize=9);fig.tight_layout()
        save(fig,f'{case_id}_queue',[case_id], 'queue_packets/buffer_packets*100, mean of 100 samples per second')

    t1 = {rtt:{tcp:reports[f't1-{tcp}-rtt{rtt}'] for tcp in ('yeah','reno')} for rtt in (15,60,240)}
    for metric, ylabel, name in [
        ('queue_over_buffer_pct','Mean queue / buffer (%)','t1_rtt_queue'),
        ('wire_utilization_pct','Wire utilization (%)','t1_rtt_wire_utilization'),
        ('overflow_per_million_attempts','Overflow drops per million enqueue attempts','t1_rtt_overflow')]:
        fig,ax=plt.subplots(figsize=(8.5,4.5))
        for tcp,label in [('yeah','YeAH'),('reno','NewReno')]:
            vals=[t1[rtt][tcp][metric] for rtt in (15,60,240)]
            ax.plot([15,60,240],vals,marker='o',label=label)
        ax.set(xlabel='Nominal propagation RTT (ms)',ylabel=ylabel,
               title=f'H1 / T1: {ylabel} vs RTT (one run each)', xticks=[15,60,240])
        ax.grid(alpha=.22);ax.legend();fig.tight_layout()
        save(fig,name,[f't1-{tcp}-rtt{rtt}' for rtt in (15,60,240) for tcp in ('yeah','reno')],metric)
    return output_provenance


def main():
    cli=argparse.ArgumentParser()
    cli.add_argument('--project',type=Path,default=Path.home()/'projects/YeAH-TCP-NPE')
    args=cli.parse_args()
    project=args.project.expanduser().resolve()
    root=project/'results/raw/experiments/h1'
    need(root.is_dir(),'H1 input folder missing; do not run new simulations')
    manifest=json.loads((root/'manifest.json').read_text())
    need(manifest['batch']=='H1' and len(manifest['cases'])==8,'Incorrect H1 manifest')
    env=json.loads((root/'environment.json').read_text())
    need(env['version']=='3.44','Unexpected NS-3 version')
    need(env['git_status']=='','Recorded ns-3 git status not clean')
    source=project/'simulation/yeah-experiment.cc'
    need(source.is_file() and sha(source)==env['source_sha256'],'Simulation source SHA-256 does not match H1. Do not analyze mismatched source.')
    statuses=json.loads((root/'batch_status.json').read_text())
    need(len(statuses)==8,'Batch status is incomplete')
    status_by_id={x['id']:x for x in statuses}
    need(set(status_by_id)=={x['id'] for x in manifest['cases']},'Status and manifest cases differ')
    summary,series={},{}
    for case in manifest['cases']:
        case_id=case['id']
        need(json.loads((root/case_id/'status.json').read_text())==status_by_id[case_id],
             f'{case_id}: status mismatch')
        report,rows=audit_case(case,root,source)
        summary[case_id]=report
        series[case_id]=rows
        print('AUDIT PASS:',case_id, '60001 samples',flush=True)
    out=project/'results/summary/h1';figs=project/'results/figures/h1'
    out.mkdir(parents=True,exist_ok=True);figs.mkdir(parents=True,exist_ok=True)
    columns=list(next(iter(summary.values())).keys())
    write_csv(out/'h1_summary_verified.csv',list(summary.values()),columns)
    t0rows=[]
    for name in ('t0-yeah-yeah','t0-yeah-reno'):
        for a,b in ((0,60),(60,400),(400,600)):
            t0rows.append(dict(id=name,**interval_stats(series[name],a,b)))
    write_csv(out/'t0_windows.csv',t0rows,list(t0rows[0].keys()))
    t1rows=[summary[f't1-{tcp}-rtt{rtt}'] for rtt in (15,60,240) for tcp in ('yeah','reno')]
    write_csv(out/'t1_rtt_verified.csv',t1rows,columns)
    plot_sources=make_plots(series,summary,figs)
    (out/'h1_audit.json').write_text(json.dumps({
        'batch':'H1', 'status':'VALIDATED_FROM_SUBMITTED_ARTIFACTS',
        'ns3_version':env['version'], 'ns3_commit':env['commit'],
        'source_sha256':env['source_sha256'], 'executable_sha256_recorded':env['executable_sha256'],
        'note':'No independent simulator rerun. One seed/run (1/1) per case. T0 Jain over full 600s not suitable as active-flow fairness.',
        'files':[{'case_id':x['id'],'source_summary_sha256':x['summary_sha256'],
                  'source_timeseries_sha256':x['timeseries_sha256']} for x in summary.values()],
        'figures':plot_sources},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('VERIFIED H1: 8/8, source and hashes match, metrics recomputed')
    print('OUTPUT:',out)
    print('FIGURES:',figs)

if __name__=='__main__':
    main()
