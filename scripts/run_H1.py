#!/usr/bin/env python3
"""H1: T0 dynamics and T1 RTT anchors, ns-3.44 optimized, no TCP changes."""
import csv
import hashlib
import json
import math
import shlex
import subprocess
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path.home() / 'projects/YeAH-TCP-NPE'
NS3 = Path.home() / 'projects/ns-3.44'
OUT = PROJECT / 'results/raw/experiments/h1'
ARCHIVE = PROJECT.parent / 'step-H1-experiments.tar.gz'
SOURCE = PROJECT / 'simulation/yeah-experiment.cc'
SCRATCH = NS3 / 'scratch/yeah-experiment.cc'
EXE = NS3 / 'build/optimized/scratch/ns3.44-yeah-experiment-optimized'
COMMIT = '43dce6710b8df69685e3479c1d33a571dda714ea'
SOURCE_HASH = '460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969'
EXE_HASH = '91c1b8ddc4460d79f1d95855a7692dc67b6c29ae0e50f4bdae319ba6a3775590'
WORKERS = 3


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def cmd(*args):
    return subprocess.check_output(args, cwd=NS3, text=True).strip()


def now():
    return datetime.now(timezone.utc).isoformat()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def cases():
    common = dict(flows=2, capacity=500, bufferRatio=1, duration=600,
                  loss=0, seed=1, run=1, mss=1448, initialCwnd=10,
                  initialSsthreshSegments=0)
    result = []
    for tcp2 in ('yeah', 'reno'):
        result.append(dict(id=f't0-yeah-{tcp2}', group='T0',
                           params=dict(common, tcp1='yeah', tcp2=tcp2,
                                       rtt1=80, rtt2=80, flow2Start=60, flow2Stop=400)))
    for rtt in (15, 60, 240):
        for tcp in ('yeah', 'reno'):
            result.append(dict(id=f't1-{tcp}-rtt{rtt}', group='T1',
                               params=dict(common, tcp1=tcp, tcp2=tcp,
                                           rtt1=rtt, rtt2=rtt, flow2Start=0, flow2Stop=600)))
    return result


def validate(case, folder):
    with (folder / 'summary.csv').open(newline='') as f:
        rows = list(csv.DictReader(f))
    require(len(rows) == 1, 'Expected exactly one summary row')
    s = rows[0]
    p = case['params']
    mapping = {'tcp1':'tcp1','tcp2':'tcp2','flows':'flows','capacity':'capacity_mbps',
               'rtt1':'rtt1_target_ms','rtt2':'rtt2_target_ms','bufferRatio':'buffer_ratio',
               'duration':'duration_s','loss':'loss_probability','seed':'seed','run':'run',
               'mss':'mss_bytes','initialCwnd':'initial_cwnd_segments',
               'initialSsthreshSegments':'initial_ssthresh_segments',
               'flow2Start':'flow2_start_s','flow2Stop':'flow2_stop_s'}
    for key, column in mapping.items():
        expected = p[key]
        actual = s[column] if isinstance(expected, str) else float(s[column])
        require(actual == expected, f'Config mismatch: {column}={actual}, expected {expected}')
    buffer = max(1, math.floor(p['capacity'] * 1e6 * min(p['rtt1'], p['rtt2']) / 1000 / (8*1500) * p['bufferRatio']))
    require(int(s['buffer_packets']) == buffer, 'Buffer mismatch')
    count, last, qsum = 0, None, 0
    counters = ('rx1_bytes','rx2_bytes','wire_bytes','bottleneck_drops','other_drops','random_drops')
    with (folder / 'timeseries.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            require(abs(float(row['time_s']) - count/100) < 1e-7, f'Time mismatch at row {count}')
            q = int(row['queue_packets'])
            require(0 <= q <= buffer, f'Queue out of bounds at row {count}')
            if count < p['duration'] * 100:
                qsum += q
            if last:
                require(all(int(row[k]) >= int(last[k]) for k in counters), 'Counter decreased')
            last = row
            count += 1
    require(count == p['duration']*100+1, f'Expected 60001 samples, got {count}')
    require(int(s['queue_samples']) == count-1, 'Queue sample count mismatch')
    require(math.isclose(float(s['queue_mean_packets']), qsum/(count-1), abs_tol=1e-8), 'Queue mean mismatch')
    return {'samples': count, 'summary_sha256': sha(folder/'summary.csv'),
            'timeseries_sha256': sha(folder/'timeseries.csv')}


def run_case(case):
    folder = OUT / case['id']
    folder.mkdir()
    args = dict(case['params'], out=str(folder))
    invocation = shlex.join(['scratch/yeah-experiment'] + [f'--{k}={v}' for k,v in args.items()])
    command = ['./ns3', 'run', invocation, '--no-build']
    result = dict(id=case['id'], group=case['group'], started_utc=now(), command=command)
    (folder/'config.json').write_text(json.dumps(case, indent=2)+'\n')
    print(f"START {case['id']}", flush=True)
    start = time.perf_counter()
    try:
        with (folder/'run.log').open('w') as log:
            log.write(shlex.join(command)+'\n'); log.flush()
            proc = subprocess.run(command, cwd=NS3, stdout=log, stderr=subprocess.STDOUT)
            result['returncode'] = proc.returncode
        result['wall_seconds'] = round(time.perf_counter()-start, 6)
        require(proc.returncode == 0, f'NS-3 exit code {proc.returncode}')
        result.update(validate(case, folder))
        result['status'] = 'PASS'
    except Exception as e:
        result.setdefault('wall_seconds', round(time.perf_counter()-start, 6))
        result['status'], result['error'] = 'FAIL', str(e)
    result['ended_utc'] = now()
    (folder/'status.json').write_text(json.dumps(result, indent=2)+'\n')
    print(f"{result['status']} {case['id']} ({result['wall_seconds']:.2f} s)", flush=True)
    return result


def main():
    require(not OUT.exists() and not ARCHIVE.exists(), 'H1 output already exists; do not overwrite. Send existing logs for recovery.')
    require(cmd('git','rev-parse','HEAD') == COMMIT, 'Unexpected ns-3 commit')
    require(not cmd('git','status','--porcelain','--','src'), 'NS-3 source tree has changes')
    require(sha(SOURCE) == SOURCE_HASH and sha(SCRATCH) == SOURCE_HASH, 'Simulation source hash mismatch')
    require(sha(EXE) == EXE_HASH, 'Optimized executable hash mismatch')
    cache = (NS3/'cmake-cache/CMakeCache.txt').read_text().splitlines()
    expected_cache = ['CMAKE_BUILD_TYPE:STRING=release','NS3_ASSERT:BOOL=OFF','NS3_LOG:BOOL=OFF','NS3_NATIVE_OPTIMIZATIONS:BOOL=ON','NS3_OUTPUT_DIRECTORY:STRING=build/optimized']
    require(all(line in cache for line in expected_cache), 'Unexpected CMake profile')
    require(Path(__file__).resolve() == (PROJECT/'scripts/run_H1.py').resolve(), 'Place script in project/scripts/run_H1.py')
    OUT.mkdir(parents=True)
    plan = cases()
    (OUT/'manifest.json').write_text(json.dumps(dict(batch='H1', workers=WORKERS, cases=plan), indent=2)+'\n')
    (OUT/'environment.json').write_text(json.dumps(dict(version=(NS3/'VERSION').read_text().strip(), commit=COMMIT, git_status=cmd('git','status','--short'), source_sha256=sha(SOURCE), executable_sha256=sha(EXE), profile=expected_cache, workers=WORKERS, started_utc=now()), indent=2)+'\n')
    results = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(run_case,c) for c in plan]
        for f in as_completed(futures):
            results.append(f.result())
    results.sort(key=lambda r:r['id'])
    (OUT/'batch_status.json').write_text(json.dumps(results, indent=2)+'\n')
    with tarfile.open(ARCHIVE, 'x:gz') as tar:
        for path in (OUT, SOURCE, PROJECT/'scripts/run_H1.py'):
            tar.add(path, arcname=str(path.relative_to(PROJECT)))
    ok = all(r['status']=='PASS' for r in results) and len(results)==len(plan)
    print(f"=== H1 {'COMPLETE' if ok else 'HAS FAILURES'} ===", flush=True)
    print(f"Archive: {ARCHIVE}", flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
