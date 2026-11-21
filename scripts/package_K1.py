#!/usr/bin/env python3
"""K1: create audited light and full source/data ZIPs without editing raw measurements."""
from __future__ import annotations
import csv
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

PROJECT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT.parent
SOURCE_HASH = '460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969'
EXPECTED_CASES = {'h1': 8, 'h2': 8, 'h3': 8, 'h4': 8}
REQUIRED_FILES = (
    'simulation/yeah-experiment.cc', 'README.md', 'refs/paper_table_I_2007.csv',
    'scripts/run_H1.py', 'scripts/run_H2.py', 'scripts/run_H3.py', 'scripts/run_H4.py',
    'scripts/analyze_H1.py', 'scripts/analyze_H2.py', 'scripts/analyze_H3.py', 'scripts/analyze_H4.py',
    'scripts/audit_I1.py', 'scripts/compare_I2.py', 'scripts/generate_report_J2_3.py',
    'scripts/finalize_report_J3.py', 'results/summary/i1/i1_master_summary.csv',
    'results/summary/i2/i2_table_I_comparison.csv',
)

def sha(p: Path):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

def require(expr, message):
    if not expr:
        raise RuntimeError(message)

def safe_file(path: Path):
    return path.is_file() and not any(n in ('__pycache__', '.git', '.venv') or n.endswith(':Zone.Identifier') or n.startswith('.~') for n in path.parts)

def gather():
    files = []
    dirs = ['simulation','scripts','refs','results/summary','results/figures']
    for folder in dirs:
        d = PROJECT / folder
        require(d.is_dir(), f'Missing directory: {d}')
        files += [p for p in d.rglob('*') if safe_file(p)]
    for rel in ('README.md','docs/I2_doi_chieu_paper_generated.md',
                'docs/I1_Ket_qua_kiem_toan.md','docs/Nhat_ky_thuc_nghiem_YeAH_TCP_v20.md',
                'tests/tcp-yeah-unit-test.log'):
        p = PROJECT / rel
        if p.is_file(): files.append(p)
    return sorted(set(files))

def verify_inputs():
    for name in REQUIRED_FILES:
        require((PROJECT/name).is_file(), f'Missing required file: {name}')
    require(sha(PROJECT/'simulation/yeah-experiment.cc') == SOURCE_HASH,
            'Source hash mismatch; do not package unverified code.')
    count = 0
    raw_files = []
    for batch, n in EXPECTED_CASES.items():
        batch_root = PROJECT/'results/raw/experiments'/batch
        require(batch_root.is_dir(), f'Missing batch: {batch}')
        manifest = batch_root/'manifest.json'
        env = batch_root/'environment.json'
        require(manifest.is_file() and env.is_file(), f'Missing batch records: {batch}')
        require(json.loads(env.read_text())['source_sha256']==SOURCE_HASH,
                f'Source mismatch in {batch} environment')
        raw_files += [p for p in batch_root.rglob('*') if safe_file(p)]
        completed = 0
        for statusfile in batch_root.glob('*/status.json'):
            data = json.loads(statusfile.read_text())
            if data.get('status')!='PASS' or data.get('returncode')!=0:
                raise RuntimeError(f'Unverified run: {statusfile}')
            folder = statusfile.parent
            for csv_name,hash_name in [('summary.csv','summary_sha256'),('timeseries.csv','timeseries_sha256')]:
                path = folder/csv_name
                require(path.is_file(), f'Missing CSV: {path}')
                require(sha(path)==data[hash_name],f'Raw CSV hash mismatch: {path}')
            require(data.get('samples')==60001,f'Unexpected trace sample count: {statusfile}')
            completed += 1
        require(completed==n,f'Expected {n} PASS runs in {batch}, found {completed}')
        count += completed
    with (PROJECT/'results/summary/i1/i1_master_summary.csv').open(newline='',encoding='utf-8') as f:
        require(len(list(csv.DictReader(f)))==32,'I1 master table does not have 32 records')
    figures = list((PROJECT/'results/figures').rglob('*'))
    assert_png = sum(p.is_file() and p.suffix=='.png' for p in figures)
    assert_svg = sum(p.is_file() and p.suffix=='.svg' for p in figures)
    require(assert_png>=20 and assert_svg>=20, f'Expected >=20 PNG/SVG; found {assert_png}/{assert_svg}')
    return count,sorted(set(raw_files))

def package(name, files):
    output = OUTPUT_DIR / name
    require(not output.exists(), f'File already exists; refusing overwrite: {output}')
    hashes = []
    with ZipFile(output,'w',compression=ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for src in files:
            arc = src.relative_to(PROJECT).as_posix()
            z.write(src,arc)
            hashes.append(f'{sha(src)}  {arc}')
        z.writestr('FILE_SHA256_MANIFEST.txt', '\n'.join(hashes)+'\n')
    with ZipFile(output) as z:
        require(z.testzip() is None,'ZIP verification failed')
        require(len(z.namelist())==len(files)+1,'ZIP count mismatch')
    print(f'CREATED: {output} ({output.stat().st_size/1024/1024:.2f} MiB, {len(files)} data files)')
    return output

def main():
    print('K1: checking project source, all 32 PASS cases, raw CSV hashes, tables, figures')
    runs, raw = verify_inputs()
    common = gather()
    # Lightweight delivery intentionally omits full timeseries, but includes each run's
    # summary/config/status, manifests and logs for traceability.
    light_raw = [p for p in raw if p.name!='timeseries.csv']
    p1 = package('YeAH_TCP_CODE_RESULTS.zip',sorted(set(common+light_raw)))
    p2 = package('YeAH_TCP_FULL_REPRO.zip',sorted(set(common+raw)))
    print(f'K1 VERIFIED: {runs}/32 PASS; source SHA256 {SOURCE_HASH}; full/raw ZIP integrity OK')
    print('LIGHTWEIGHT ZIP lacks timeseries.csv; full audits require the FULL_REPRO ZIP.')
    print('NEXT: fill cover information in Word, update TOC, export a separate PDF.')

if __name__=='__main__':
    main()
