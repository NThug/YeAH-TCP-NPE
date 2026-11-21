#!/usr/bin/env python3
"""H4: random independent packet loss, NS-3.44; measured outputs only.

Partial reproduction of YeAH-TCP (2007) Figure 5: RTT1=RTT2=200ms,
bottleneck=500 Mbps, B=100% BDP=8333 packets; p in 1e-8..1e-4.
A single seeded 600-second run per TCP / loss level is exploratory,
not a statistical estimate nor an exact Linux-testbed reproduction.

Usage:
    python3 scripts/run_H4.py
    python3 scripts/run_H4.py --resume
"""
import argparse
import csv
import hashlib
import json
import math
import os
import shlex
import shutil
import subprocess
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path.home() / 'projects/YeAH-TCP-NPE'
NS3 = Path.home() / 'projects/ns-3.44'
OUT = PROJECT / 'results/raw/experiments/h4'
ARCHIVE = PROJECT.parent / 'step-H4-random-loss.tar.gz'
SOURCE = PROJECT / 'simulation/yeah-experiment.cc'
SCRATCH = NS3 / 'scratch/yeah-experiment.cc'
SCRIPT = PROJECT / 'scripts/run_H4.py'
EXE = NS3 / 'build/optimized/scratch/ns3.44-yeah-experiment-optimized'
COMMIT = '43dce6710b8df69685e3479c1d33a571dda714ea'
SOURCE_HASH = '460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969'
EXE_HASH = '91c1b8ddc4460d79f1d95855a7692dc67b6c29ae0e50f4bdae319ba6a3775590'
WORKERS = 3
DURATION = 600


def need(cond, message):
    if not cond:
        raise RuntimeError(message)


def digest(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def cmd(*args):
    return subprocess.check_output(args, cwd=NS3, text=True).strip()


def configs():
    # Figure 5: 200 ms, 500 Mbps, B = 100% of BDP = 8333 packets.
    # Four sampled loss probabilities from paper's 1e-8 to 1e-4 range.
    # The p values are simulation inputs, NEVER observed loss ratios.
    common = dict(flows=2, capacity=500, rtt1=200, rtt2=200,
                  bufferRatio=1, duration=DURATION, flow2Start=0,
                  flow2Stop=DURATION, seed=1, run=1, mss=1448,
                  initialCwnd=10, initialSsthreshSegments=0)
    result = []
    for p_text, p_value in [('1e-8', 1e-8), ('1e-6', 1e-6),
                            ('1e-5', 1e-5), ('1e-4', 1e-4)]:
        for tcp in ('yeah', 'reno'):
            result.append(dict(id=f't4-{tcp}-p{p_text}', group='T4',
                               params=dict(common, tcp1=tcp, tcp2=tcp,
                                           loss=p_value)))
    return result


def expected_buffer(p):
    bdp = p['capacity'] * 1e6 * min(p['rtt1'], p['rtt2']) / 1000.0 / (8 * 1500)
    return max(1, math.floor(bdp * p['bufferRatio']))


def close(a, b, eps=1e-7):
    return math.isclose(float(a), float(b), rel_tol=1e-8, abs_tol=eps)


def audit(case, folder):
    p = case['params']
    with (folder/'summary.csv').open(newline='') as f:
        rows = list(csv.DictReader(f))
    need(len(rows) == 1, 'summary.csv must contain one data row')
    s = rows[0]
    mapping = {'tcp1':'tcp1','tcp2':'tcp2','flows':'flows','capacity':'capacity_mbps',
               'rtt1':'rtt1_target_ms','rtt2':'rtt2_target_ms','bufferRatio':'buffer_ratio',
               'duration':'duration_s','loss':'loss_probability','seed':'seed','run':'run',
               'mss':'mss_bytes','initialCwnd':'initial_cwnd_segments',
               'initialSsthreshSegments':'initial_ssthresh_segments',
               'flow2Start':'flow2_start_s','flow2Stop':'flow2_stop_s'}
    for key, column in mapping.items():
        want, got = p[key], s[column]
        if isinstance(want, str):
            need(got == want, f'{column}: expected {want}, got {got}')
        else:
            need(close(float(got), want, eps=1e-9), f'{column}: expected {want}, got {got}')
    buf = expected_buffer(p)
    need(int(s['buffer_packets']) == buf, 'Buffer packets mismatch')

    cumulative = ('rx1_bytes','rx2_bytes','wire_bytes',
                  'bottleneck_drops','other_drops','random_drops')
    last = None
    count = qsum = qmax = 0
    with (folder/'timeseries.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            need(close(float(row['time_s']), count / 100, eps=1e-7), f'Bad time at row {count}')
            q = int(row['queue_packets'])
            need(0 <= q <= buf, f'Queue outside physical buffer at row {count}')
            if count < DURATION * 100:
                qsum += q
                qmax = max(qmax, q)
            if last is not None:
                need(all(int(row[k]) >= int(last[k]) for k in cumulative),
                     f'Decreasing counter at row {count}')
            last = row
            count += 1
    need(count == DURATION * 100 + 1, f'Expected {DURATION*100+1} samples, got {count}')
    need(last is not None, 'No timeseries rows')
    need(int(s['queue_samples']) == DURATION*100, 'Queue samples mismatch')
    need(close(float(s['queue_mean_packets']), qsum/(DURATION*100)), 'Queue mean mismatch')
    need(int(s['queue_max_sampled']) >= qmax, 'Queue maximum mismatch')
    for column, trace in [('rx1_bytes','rx1_bytes'),('rx2_bytes','rx2_bytes'),
                          ('bottleneck_drops','bottleneck_drops'),
                          ('other_drops','other_drops'),('random_drops','random_drops')]:
        need(int(s[column]) == int(last[trace]), f'{column} differs from final trace')
    g1 = int(last['rx1_bytes'])*8/(DURATION*1e6)
    g2 = int(last['rx2_bytes'])*8/(DURATION*1e6)
    tot = g1 + g2
    wire = int(last['wire_bytes'])*8/(DURATION*p['capacity']*1e6)
    jain = tot**2/(2*(g1*g1+g2*g2)) if tot > 0 else 0
    need(close(s['goodput1_mbps'],g1), 'Goodput 1 mismatch')
    need(close(s['goodput2_mbps'],g2), 'Goodput 2 mismatch')
    need(close(s['total_goodput_mbps'],tot), 'Total goodput mismatch')
    need(close(s['wire_utilization'],wire), 'Wire utilization mismatch')
    need(close(s['queue_normalized'],(qsum/(DURATION*100))/buf), 'Normalized queue mismatch')
    need(close(s['jain_index'],jain), 'Jain index mismatch')
    need(int(s['random_drops']) >= 0, 'Invalid random loss counter')
    need(int(s['random_drops']) <= int(s['wire_packets']), 'Random drops exceed wire packets')
    need(int(s['bottleneck_drops']) >= 0, 'Invalid queue drops')
    need(int(s['flows']) == 2, 'This test requires two flows')
    need(float(s['min_rtt1_ms']) >= float(p['rtt1'])-0.01, 'RTT1 below propagation target')
    need(float(s['min_rtt2_ms']) >= float(p['rtt2'])-0.01, 'RTT2 below propagation target')
    return dict(samples=count, buffer_packets=buf, random_drops=int(s['random_drops']),
                loss_configured=p['loss'],
                summary_sha256=digest(folder/'summary.csv'),
                timeseries_sha256=digest(folder/'timeseries.csv'),
                goodput_total_mbps=round(tot, 10),
                wire_utilization=round(wire, 10),
                normalized_mean_queue=round(qsum/(DURATION*100)/buf,10))


def run_one(case):
    folder = OUT / case['id']
    folder.mkdir()
    args = dict(case['params'], out=str(folder))
    invocation = shlex.join(['scratch/yeah-experiment']+[f'--{k}={v}' for k,v in args.items()])
    command = ['./ns3','run',invocation,'--no-build']
    (folder/'config.json').write_text(json.dumps(case, indent=2)+'\n')
    status = dict(id=case['id'], started_utc=utc(), command=command, source_sha256=SOURCE_HASH)
    print(f'START {case["id"]}',flush=True)
    began = time.perf_counter()
    try:
        with (folder/'run.log').open('w') as log:
            log.write(shlex.join(command)+'\n')
            log.flush()
            process = subprocess.run(command,cwd=NS3,stdout=log,stderr=subprocess.STDOUT)
            status['returncode'] = process.returncode
        need(process.returncode == 0, f'Simulator exited {process.returncode}')
        status.update(audit(case,folder))
        status['status'] = 'PASS'
    except Exception as e:
        status['status'] = 'FAIL'
        status['error'] = str(e)
    status['wall_seconds'] = round(time.perf_counter()-began,6)
    status['ended_utc'] = utc()
    (folder/'status.json').write_text(json.dumps(status,indent=2)+'\n')
    print(f'{status["status"]} {case["id"]} ({status["wall_seconds"]:.2f}s)',flush=True)
    return status


def environment_checks():
    need(SCRIPT.resolve()==Path(__file__).resolve(), 'Script must be in scripts/run_H4.py')
    need(cmd('git','rev-parse','HEAD')==COMMIT,'Incorrect ns-3 git commit')
    need(not cmd('git','status','--porcelain','--','src'), 'NS-3 src has uncommitted modifications')
    need(SOURCE.is_file() and SCRATCH.is_file() and EXE.is_file(),'Missing simulation source/scratch/executable')
    need(digest(SOURCE)==SOURCE_HASH and digest(SCRATCH)==SOURCE_HASH,'Source hash mismatch')
    need(digest(EXE)==EXE_HASH,'Optimized executable hash mismatch')
    cache = (NS3/'cmake-cache/CMakeCache.txt').read_text().splitlines()
    for line in ('CMAKE_BUILD_TYPE:STRING=release','NS3_ASSERT:BOOL=OFF',
                 'NS3_LOG:BOOL=OFF','NS3_NATIVE_OPTIMIZATIONS:BOOL=ON',
                 'NS3_OUTPUT_DIRECTORY:STRING=build/optimized'):
        need(line in cache, f'Unexpected CMake config: {line}')
    return dict(version=(NS3/'VERSION').read_text().strip(), commit=COMMIT,
                git_status=cmd('git','status','--short'),
                source_sha256=digest(SOURCE), executable_sha256=digest(EXE),
                python_script_sha256=digest(SCRIPT), profile='optimized',
                workers=WORKERS, recorded_utc=utc())


def restore_or_requeue(plan):
    done = []
    remaining = []
    for case in plan:
        folder = OUT/case['id']
        if not folder.exists():
            remaining.append(case)
            continue
        try:
            status = json.loads((folder/'status.json').read_text())
            need(status.get('status') == 'PASS', 'Previous status is not PASS')
            need(json.loads((folder/'config.json').read_text()) == case, 'Previous config differs')
            checked = audit(case,folder)
            need(all(status.get(k)==v for k,v in checked.items()), 'Previous hash/audit mismatch')
            print(f'SKIP VERIFIED {case["id"]}',flush=True)
            done.append(status)
        except Exception as e:
            history = OUT/'_interrupted'
            history.mkdir(exist_ok=True)
            destination = history / (case['id']+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
            shutil.move(str(folder),str(destination))
            print(f'PRESERVED INTERRUPTED {case["id"]} -> {destination.name}: {e}',flush=True)
            remaining.append(case)
    return done, remaining


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume',action='store_true',help='Skip verified cases, preserve and re-run interrupted attempts')
    a = parser.parse_args()
    need(not ARCHIVE.exists(), f'Existing archive must not be overwritten: {ARCHIVE}')
    if a.resume:
        need(OUT.is_dir(),'No H4 directory exists to resume')
    else:
        need(not OUT.exists(),'Existing H4 directory; use --resume instead of overwriting')
    env = environment_checks()
    plan = configs()
    if not a.resume:
        OUT.mkdir(parents=True)
        (OUT/'manifest.json').write_text(json.dumps(dict(batch='H4',purpose='Figure 5 random loss probability',
              duration=DURATION, workers=WORKERS, cases=plan),indent=2)+'\n')
        (OUT/'environment.json').write_text(json.dumps(env,indent=2)+'\n')
        prior, remaining = [], plan
    else:
        old_manifest = json.loads((OUT/'manifest.json').read_text())
        need(old_manifest.get('cases') == plan,'Manifest differs from current script')
        old_env = json.loads((OUT/'environment.json').read_text())
        need(old_env.get('source_sha256') == env['source_sha256'] and
             old_env.get('executable_sha256') == env['executable_sha256'], 'Environment differs from original run')
        prior, remaining = restore_or_requeue(plan)
    results = prior[:]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        future = [pool.submit(run_one,case) for case in remaining]
        for f in as_completed(future):
            results.append(f.result())
    results.sort(key=lambda v:v['id'])
    (OUT/'batch_status.json').write_text(json.dumps(results,indent=2)+'\n')
    with tarfile.open(ARCHIVE,'w:gz') as tar:
        for path in (OUT,SOURCE,SCRIPT):
            tar.add(path,arcname=str(path.relative_to(PROJECT)))
    ok = len(results)==len(plan) and all(r.get('status')=='PASS' for r in results)
    print(f'=== H4 {"COMPLETE" if ok else "HAS FAILURES"} ===',flush=True)
    print(f'Archive: {ARCHIVE}',flush=True)
    return 0 if ok else 1

if __name__=='__main__':
    raise SystemExit(main())
