#!/usr/bin/env python3
"""Independent H2 audit + reproducible table/figure generator.

Input:  results/raw/experiments/h2/ (untouched NS-3 outputs)
Output: results/summary/h2/, results/figures/h2/
Run:    python3 scripts/analyze_H2.py
Plot dependency: sudo apt install python3-matplotlib

No experimental values are supplied or assigned inside this script. Every
measurement is recomputed from raw counters/queue samples in timeseries.csv.
The declared experiment matrix is verified against manifest.json.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

RATIOS = (0.125, 0.25, 0.5, 1.0)
TCPS = ('yeah', 'reno')
CUMULATIVE_FIELDS = ('rx1_bytes', 'rx2_bytes', 'wire_bytes',
                     'bottleneck_drops', 'other_drops', 'random_drops')
PARAM_COLUMNS = {
    'tcp1': 'tcp1', 'tcp2': 'tcp2', 'flows': 'flows', 'capacity': 'capacity_mbps',
    'rtt1': 'rtt1_target_ms', 'rtt2': 'rtt2_target_ms',
    'bufferRatio': 'buffer_ratio', 'duration': 'duration_s',
    'loss': 'loss_probability', 'seed': 'seed', 'run': 'run',
    'mss': 'mss_bytes', 'initialCwnd': 'initial_cwnd_segments',
    'initialSsthreshSegments': 'initial_ssthresh_segments',
    'flow2Start': 'flow2_start_s', 'flow2Stop': 'flow2_stop_s'
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def close(a, b, abs_tol=1e-7) -> bool:
    return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=abs_tol)


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def read_single_csv(path: Path):
    with path.open(newline='', encoding='utf-8') as stream:
        records = list(csv.DictReader(stream))
    require(len(records) == 1, f'{path} should have exactly 1 data row')
    return records[0]


def write_csv(path: Path, records: list[dict], fields: list[str]) -> None:
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(records)


def expected_buffer(parameters: dict) -> int:
    bdp = (parameters['capacity'] * 1e6 *
           min(parameters['rtt1'], parameters['rtt2']) / 1000 / (8 * 1500))
    return max(1, math.floor(bdp * parameters['bufferRatio']))


def interval(rows_by_second: dict, queue_sums: dict, a: int, b: int, buffer: int, capacity: float):
    left, right = rows_by_second[a], rows_by_second[b]
    seconds = b - a
    bytes1 = int(right['rx1_bytes']) - int(left['rx1_bytes'])
    bytes2 = int(right['rx2_bytes']) - int(left['rx2_bytes'])
    wire_bytes = int(right['wire_bytes']) - int(left['wire_bytes'])
    g1 = bytes1 * 8 / (seconds * 1e6)
    g2 = bytes2 * 8 / (seconds * 1e6)
    queue_total = sum(queue_sums[sec] for sec in range(a, b))
    return dict(from_s=a, to_s=b, goodput1_mbps=round(g1, 9),
                goodput2_mbps=round(g2, 9), total_goodput_mbps=round(g1+g2, 9),
                wire_utilization_pct=round(100 * wire_bytes * 8 / (seconds * capacity * 1e6), 8),
                queue_mean_packets=round(queue_total / (seconds * 100), 9),
                queue_over_buffer_pct=round(100 * queue_total / (seconds * 100 * buffer), 8))


def audit_case(root: Path, case: dict, status: dict):
    case_id = case['id']
    params = case['params']
    folder = root / case_id
    require(read_json(folder / 'config.json') == case, f'{case_id}: config differs from manifest')
    require(read_json(folder / 'status.json') == status, f'{case_id}: status differs from batch record')
    require(status.get('status') == 'PASS' and status.get('returncode') == 0,
            f'{case_id}: run was not successful')
    require(sha256(folder/'summary.csv') == status['summary_sha256'], f'{case_id}: summary hash differs')
    require(sha256(folder/'timeseries.csv') == status['timeseries_sha256'], f'{case_id}: timeseries hash differs')
    log = (folder/'run.log').read_text(encoding='utf-8')
    require('summary.csv and timeseries.csv' in log, f'{case_id}: run.log lacks successful completion')
    cls = {'yeah': 'TcpYeah', 'reno': 'TcpNewReno'}
    for node, tcp in enumerate((params['tcp1'], params['tcp2'])):
        require(f'Node {node} SocketType=ns3::{cls[tcp]}' in log,
                f'{case_id}: socket algorithm not confirmed in log')
    summary = read_single_csv(folder/'summary.csv')
    for key, col in PARAM_COLUMNS.items():
        got = summary[col]
        val = params[key]
        require(got == val if isinstance(val, str) else close(got, val, 1e-9),
                f'{case_id}: {col} differs from configured {key}')
    duration = params['duration']
    require(duration == 600, f'{case_id}: unexpected duration')
    buffer = expected_buffer(params)
    require(int(summary['buffer_packets']) == buffer, f'{case_id}: buffer differs from BDP formula')
    require(params['flows'] == 2 and params['loss'] == 0 and params['seed'] == 1 and params['run'] == 1,
            f'{case_id}: experimental common parameters differ')
    require(params['rtt1'] == params['rtt2'] == 80 and params['capacity'] == 500,
            f'{case_id}: RTT/bottleneck differ')

    qsum = 0
    qmax = 0
    count = 0
    last = None
    points = {}
    queue_sums = [0] * duration
    with (folder/'timeseries.csv').open(newline='', encoding='utf-8') as stream:
        for row in csv.DictReader(stream):
            t = float(row['time_s'])
            require(close(t, count / 100, 1e-7), f'{case_id}: invalid time at sample {count}')
            q = int(row['queue_packets'])
            require(0 <= q <= buffer, f'{case_id}: queue outside buffer at sample {count}')
            if count < duration * 100:
                qsum += q
                qmax = max(qmax, q)
                queue_sums[count // 100] += q
            if count % 100 == 0:
                points[count // 100] = row
            if last is not None:
                for name in CUMULATIVE_FIELDS:
                    require(int(row[name]) >= int(last[name]),
                            f'{case_id}: {name} decreased at sample {count}')
            last = row
            count += 1
    require(count == duration * 100 + 1, f'{case_id}: sample count {count} != 60001')
    require(set(points) == set(range(601)), f'{case_id}: missing 1-second boundary samples')
    require(int(summary['queue_samples']) == duration * 100, f'{case_id}: queue sample count differs')
    require(qmax == int(summary['queue_max_sampled']), f'{case_id}: queue max differs')
    qmean = qsum / (duration * 100)
    require(close(qmean, summary['queue_mean_packets']), f'{case_id}: queue mean differs')
    for name in ('rx1_bytes', 'rx2_bytes', 'bottleneck_drops', 'other_drops', 'random_drops'):
        require(int(summary[name]) == int(last[name]), f'{case_id}: counter {name} differs')
    require(int(last['random_drops']) == 0, f'{case_id}: unexpected random drops')
    g1 = int(last['rx1_bytes']) * 8 / duration / 1e6
    g2 = int(last['rx2_bytes']) * 8 / duration / 1e6
    total = g1 + g2
    util = int(last['wire_bytes']) * 8 / duration / (params['capacity']*1e6)
    queue_norm = qmean / buffer
    overflow = int(last['bottleneck_drops'])
    enqueued = int(summary['queue_enqueued'])
    pdrop = overflow/(enqueued + overflow) if overflow + enqueued else 0
    jain = total**2/(2*(g1*g1+g2*g2)) if total else 0
    recalc = dict(goodput1_mbps=g1, goodput2_mbps=g2, total_goodput_mbps=total,
                  goodput_over_capacity=total/params['capacity'], wire_utilization=util,
                  queue_mean_packets=qmean, queue_normalized=queue_norm,
                  overflow_probability=pdrop, jain_index=jain)
    for name, value in recalc.items():
        require(close(summary[name], value), f'{case_id}: {name} differs from independent calculation')
    require(status.get('samples') == count and status.get('buffer_packets') == buffer,
            f'{case_id}: sample/buffer status mismatch')
    require(close(status.get('goodput_total_mbps'), total), f'{case_id}: goodput status mismatch')
    require(close(status.get('wire_utilization'), util), f'{case_id}: wire status mismatch')
    require(close(status.get('normalized_mean_queue'), queue_norm), f'{case_id}: queue status mismatch')
    record = dict(id=case_id, tcp=params['tcp1'], buffer_ratio=params['bufferRatio'],
                  buffer_pct=100*params['bufferRatio'], buffer_packets=buffer,
                  duration_s=duration, seed=params['seed'], run=params['run'],
                  goodput1_mbps=round(g1,10), goodput2_mbps=round(g2,10),
                  total_goodput_mbps=round(total,10),
                  goodput_over_capacity_pct=round(total/params['capacity']*100,8),
                  wire_utilization_pct=round(util*100,8),
                  queue_mean_packets=round(qmean,9),
                  queue_over_buffer_pct=round(queue_norm*100,8),
                  queue_max_sampled=qmax,
                  bottleneck_drops=overflow,
                  overflow_per_million_attempts=round(pdrop*1e6,8),
                  random_drops=int(last['random_drops']),
                  other_drops=int(last['other_drops']),
                  jain_whole_600s=round(jain,10),
                  wall_seconds=round(float(status['wall_seconds']),6),
                  summary_sha256=status['summary_sha256'],
                  timeseries_sha256=status['timeseries_sha256'])
    windows=[]
    for a,b in ((0,120),(120,300),(300,600)):
        windows.append(dict(id=case_id,tcp=params['tcp1'],buffer_ratio=params['bufferRatio'],
                            **interval(points,queue_sums,a,b,buffer,params['capacity'])))
    return record, windows


def plot_figures(summary: dict, figures: Path):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError as err:
        raise SystemExit('matplotlib required: sudo apt install python3-matplotlib') from err
    plt.rcParams.update({'font.size':10,'figure.dpi':120,'savefig.dpi':300})
    fields = (
        ('total_goodput_mbps','Total application goodput (Mbps)','t2_buffer_goodput'),
        ('wire_utilization_pct','Wire utilization (%)','t2_buffer_wire_utilization'),
        ('queue_over_buffer_pct','Mean bottleneck queue / buffer (%)','t2_buffer_queue_normalized'),
        ('overflow_per_million_attempts','Overflow drops per million enqueue attempts','t2_buffer_overflow'),
        ('jain_whole_600s',"Jain's fairness index (0–1)",'t2_buffer_fairness'),
    )
    provenance=[]
    for column,y_label,name in fields:
        fig,ax=plt.subplots(figsize=(8,4.5))
        identifiers=[]
        for tcp,label in (('yeah','YeAH × 2'),('reno','NewReno × 2')):
            xs=[];ys=[]
            for beta in RATIOS:
                id_ = f't2-{tcp}-beta{str(beta).replace(".","p")}'
                identifiers.append(id_)
                xs.append(100*beta)
                ys.append(summary[id_][column])
            ax.plot(xs,ys,marker='o',linewidth=2,label=label)
        ax.set(xlabel='Buffer / nominal BDP (%)',ylabel=y_label,
               title=f'H2 / T2: {y_label} vs buffer size (one run per point)',
               xticks=[100*x for x in RATIOS])
        ax.grid(alpha=.24)
        ax.legend()
        if column=='jain_whole_600s':
            ax.set_ylim(.75,1.01)
        fig.tight_layout()
        for ext in ('.png','.svg'):
            fig.savefig(figures/(name+ext), dpi=300,bbox_inches='tight')
        plt.close(fig)
        provenance.append(dict(figure=name, field=column, case_ids=identifiers,
                               source='Verified H2 timeseries.csv and summary.csv (one seed/run per case)',
                               meaning='Full 600s measurement window'))
    return provenance


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--project', type=Path, default=Path.home()/'projects/YeAH-TCP-NPE')
    args=parser.parse_args()
    project=args.project.expanduser().resolve()
    root=project/'results/raw/experiments/h2'
    require(root.is_dir(),f'Missing H2 raw folder: {root}; no new NS-3 simulation is launched')
    env=read_json(root/'environment.json')
    manifest=read_json(root/'manifest.json')
    statuses=read_json(root/'batch_status.json')
    require(env['version']=='3.44' and env['git_status']=='', 'Unexpected recorded environment')
    require(env['profile']=='optimized', 'H2 should use optimized build')
    src=project/'simulation/yeah-experiment.cc'
    run_script=project/'scripts/run_H2.py'
    require(src.is_file() and sha256(src)==env['source_sha256'],
            'Simulation source not found / SHA-256 differs from H2 run')
    require(run_script.is_file() and sha256(run_script)==env['python_script_sha256'],
            'H2 runner not found / SHA-256 differs from H2 run')
    require(manifest['batch']=='H2' and len(manifest['cases'])==8, 'Unexpected H2 manifest')
    require(len(statuses)==8, 'Unexpected H2 batch status')
    ids={f't2-{tcp}-beta{str(beta).replace(".","p")}' for tcp in TCPS for beta in RATIOS}
    require({c['id'] for c in manifest['cases']}==ids, 'Unexpected IDs or missing H2 cases')
    require({s['id'] for s in statuses}==ids, 'Missing/duplicate H2 case statuses')
    status_by_id={s['id']:s for s in statuses}
    summary={}
    windows=[]
    for case in manifest['cases']:
        id_=case['id']
        p=case['params']
        require(p['tcp1']==p['tcp2'] and p['tcp1'] in TCPS,
                f'{id_}: unexpected TCP selection')
        require(close(p['bufferRatio'], next(beta for beta in RATIOS if str(beta).replace('.','p') in id_),1e-12),
                f'{id_}: ID/buffer ratio mismatch')
        item,partial=audit_case(root,case,status_by_id[id_])
        summary[id_]=item
        windows.extend(partial)
        print(f'AUDIT PASS: {id_} 60001 samples',flush=True)
    out=project/'results/summary/h2'
    plots=project/'results/figures/h2'
    out.mkdir(parents=True,exist_ok=True)
    plots.mkdir(parents=True,exist_ok=True)
    ordered=[summary[f't2-{tcp}-beta{str(beta).replace(".","p")}']
             for beta in RATIOS for tcp in TCPS]
    fields=list(ordered[0].keys())
    write_csv(out/'h2_summary_verified.csv',ordered,fields)
    write_csv(out/'t2_buffer_verified.csv',ordered,fields)
    write_csv(out/'t2_windows.csv',windows,list(windows[0].keys()))
    provenance=plot_figures(summary,plots)
    audit={
        'batch':'H2', 'status':'VALIDATED_FROM_SUBMITTED_ARTIFACTS',
        'ns3_version':env['version'],'ns3_commit':env['commit'],
        'source_sha256':env['source_sha256'],
        'runner_sha256':env['python_script_sha256'],
        'executable_sha256_recorded_not_locally_rechecked':env['executable_sha256'],
        'limitations': [
            'Only one seed/run per configuration (1/1); no confidence intervals.',
            'Validation of submitted original outputs, not an independent NS-3 simulation rerun.',
            'No SURGE cross traffic or Limited Slow Start; NS-3 implementation is not a full Linux testbed reproduction.',
            'The overflow rate uses bottleneck FIFO enqueue attempts, not end-to-end loss probability.',
            'All performance metrics use the full 600s interval including startup.'
        ],
        'cases':[{ 'id':x['id'], 'source_summary_sha256':x['summary_sha256'],
                   'source_timeseries_sha256':x['timeseries_sha256']} for x in ordered],
        'figures':provenance}
    (out/'h2_audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('VERIFIED H2: 8/8, source and hashes match, metrics recomputed')
    print('OUTPUT:',out)
    print('FIGURES:',plots)

if __name__=='__main__':
    main()
