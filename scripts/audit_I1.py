#!/usr/bin/env python3
"""Read-only H1-H4 raw and summary audit; derive a 32-case master table.

Inputs (never modified):
  simulation/yeah-experiment.cc
  scripts/run_H*.py
  results/raw/experiments/h1..h4/{manifest,environment,batch_status,CASE/...}
  results/summary/h1..h4/h*_summary_verified.csv
  results/figures/h1..h4/ (existence/count only)
Output: results/summary/i1/i1_master_summary.csv, i1_audit.json

IMPORTANT: No invented measurements. All numeric rows are recomputed directly
from raw per-case summary.csv and every row of timeseries.csv.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

EXPECTED_COMMIT = "43dce6710b8df69685e3479c1d33a571dda714ea"
EXPECTED_SOURCE_HASH = "460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969"
EXPECTED_CASES = {
    "h1": {"t0-yeah-yeah", "t0-yeah-reno"} | {f"t1-{tcp}-rtt{rtt}" for tcp in ("yeah", "reno") for rtt in (15, 60, 240)},
    "h2": {f"t2-{tcp}-beta{beta}" for tcp in ("yeah", "reno") for beta in ("0p125", "0p25", "0p5", "1p0")},
    "h3": {f"t3-{tcp}-ratio{ratio}" for tcp in ("yeah", "reno") for ratio in range(1, 5)},
    "h4": {f"t4-{tcp}-p{p}" for tcp in ("yeah", "reno") for p in ("1e-8", "1e-6", "1e-5", "1e-4")},
}
FIGURES = {"h1": 7, "h2": 5, "h3": 4, "h4": 4}
CUMULATIVE = ("rx1_bytes", "rx2_bytes", "wire_bytes", "bottleneck_drops", "other_drops", "random_drops")
MASTER_COLS = ("batch", "id", "tcp1", "tcp2", "duration_s", "capacity_mbps", "rtt1_ms", "rtt2_ms", "buffer_ratio", "buffer_packets", "configured_random_loss", "seed", "run", "flow2_start_s", "flow2_stop_s", "rx1_bytes", "rx2_bytes", "goodput1_mbps", "goodput2_mbps", "total_goodput_mbps", "goodput_over_capacity_pct", "wire_utilization_pct", "queue_mean_packets", "queue_over_buffer_pct", "overflow_drops", "overflow_probability", "random_drops", "jain_whole_duration", "sample_count", "source_sha256", "summary_sha256", "timeseries_sha256", "fairness_interpretation")


def require(cond, message):
    if not cond: raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(2**20), b""):
            h.update(block)
    return h.hexdigest()


def near(a, b, absolute=1e-5):
    return math.isclose(float(a), float(b), rel_tol=1e-8, abs_tol=absolute)


def read_single_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    require(len(rows) == 1, f"Expected one summary row: {path}")
    return rows[0]


def trace_metrics(path, duration, buffer):
    rows = 0
    last = None
    queue_sum = 0
    max_queue = 0
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        require(set(CUMULATIVE).issubset(set(reader.fieldnames or [])), f"Missing trace counters: {path}")
        for row in reader:
            time = float(row["time_s"])
            require(abs(time - rows / 100) < 1e-7, f"Incorrect time/sample #{rows}: {path}")
            q = int(row["queue_packets"])
            require(0 <= q <= buffer, f"Queue exceeds buffer: {path} sample {rows}")
            if rows < duration * 100:
                queue_sum += q
                max_queue = max(q, max_queue)
            if last is not None:
                for key in CUMULATIVE:
                    require(int(row[key]) >= int(last[key]), f"Non-monotone {key}: {path}")
            last = row
            rows += 1
    require(rows == duration * 100 + 1, f"Incorrect trace sample count: {path}")
    return rows, last, queue_sum / (duration * 100), max_queue


def audit(project):
    source = project / "simulation/yeah-experiment.cc"
    require(source.is_file() and sha(source) == EXPECTED_SOURCE_HASH, "Simulation source hash differs; stop and investigate")
    master = []
    group_reports = {}
    all_hashes = set()
    for group in ("h1", "h2", "h3", "h4"):
        raw = project / "results/raw/experiments" / group
        require(raw.is_dir(), f"Missing raw group {group}")
        env = read_json(raw / "environment.json")
        manifest = read_json(raw / "manifest.json")
        batch = read_json(raw / "batch_status.json")
        require(env["version"] == "3.44" and env["commit"] == EXPECTED_COMMIT, f"Incorrect ns-3 version: {group}")
        require(env["source_sha256"] == EXPECTED_SOURCE_HASH and env["git_status"] == "", f"Source/status changed: {group}")
        if env.get("python_script_sha256"):
            runner = project / "scripts" / f"run_{group.upper()}.py"
            require(sha(runner) == env["python_script_sha256"], f"Runner mismatch: {group}")
        require(manifest.get("batch") == group.upper(), f"Incorrect manifest group: {group}")
        cases = manifest["cases"]
        case_ids = [case["id"] for case in cases]
        require(len(case_ids) == 8 and set(case_ids) == EXPECTED_CASES[group], f"Case list differs: {group}")
        batch_status = {rec["id"]: rec for rec in batch}
        require(set(batch_status) == EXPECTED_CASES[group], f"Batch status incomplete: {group}")
        verified_path = project / f"results/summary/{group}/{group}_summary_verified.csv"
        with verified_path.open(newline="", encoding="utf-8") as file:
            verified_list = list(csv.DictReader(file))
        key = "case_id" if group == "h4" else "id"
        verified = {row[key]: row for row in verified_list}
        require(len(verified_list) == 8 and set(verified) == EXPECTED_CASES[group], f"Verified summary incomplete: {group}")
        png = list((project / f"results/figures/{group}").glob("*.png"))
        svg = list((project / f"results/figures/{group}").glob("*.svg"))
        require(len(png) == len(svg) == FIGURES[group], f"Figure file counts differ: {group}: {len(png)} PNG / {len(svg)} SVG")
        for case in cases:
            id_ = case["id"]
            folder = raw / id_
            status = read_json(folder / "status.json")
            require(status == batch_status[id_] and status["status"] == "PASS" and status["returncode"] == 0, f"Case status mismatch: {id_}")
            summary_file = folder / "summary.csv"
            trace_file = folder / "timeseries.csv"
            require(sha(summary_file) == status["summary_sha256"] and sha(trace_file) == status["timeseries_sha256"], f"File hash mismatch: {id_}")
            all_hashes.add(status["summary_sha256"])
            all_hashes.add(status["timeseries_sha256"])
            s = read_single_csv(summary_file)
            duration = int(float(s["duration_s"]))
            capacity = float(s["capacity_mbps"])
            buffer = int(s["buffer_packets"])
            require(duration == 600 and capacity == 500 and int(s["flows"]) == 2, f"Unexpected common config: {id_}")
            require(int(s["seed"]) == int(s["run"]) == 1 and int(s["mss_bytes"]) == 1448, f"Seed/MSS differs: {id_}")
            require(int(s["initial_cwnd_segments"]) == 10 and int(s["initial_ssthresh_segments"]) == 0, f"TCP initial settings differ: {id_}")
            require(near(s["rtt1_target_ms"], case["params"]["rtt1"]) and near(s["rtt2_target_ms"], case["params"]["rtt2"]), f"RTT mismatch: {id_}")
            require(near(s["buffer_ratio"], case["params"]["bufferRatio"]) and near(s["loss_probability"], case["params"]["loss"], absolute=1e-12), f"Buffer/loss mismatch: {id_}")
            require(s["tcp1"] == case["params"]["tcp1"] and s["tcp2"] == case["params"]["tcp2"], f"TCP pair mismatch: {id_}")
            require(near(s["flow2_start_s"], case["params"]["flow2Start"]) and near(s["flow2_stop_s"], case["params"]["flow2Stop"]), f"Flow timing mismatch: {id_}")
            count, end, qmean, qmax = trace_metrics(trace_file, duration, buffer)
            require(int(s["queue_samples"]) == duration * 100, f"Queue sample count differs: {id_}")
            require(near(qmean, s["queue_mean_packets"], absolute=1e-6) and int(s["queue_max_sampled"]) == qmax, f"Queue computation differs: {id_}")
            for col in CUMULATIVE:
                dest_col = "rx1_bytes" if col == "rx1_bytes" else "rx2_bytes" if col == "rx2_bytes" else col
                if dest_col in s:
                    require(int(s[dest_col]) == int(end[col]), f"Final counter mismatch: {id_}/{col}")
            gp1 = int(end["rx1_bytes"]) * 8 / duration / 1e6
            gp2 = int(end["rx2_bytes"]) * 8 / duration / 1e6
            goodput = gp1 + gp2
            wire = int(end["wire_bytes"]) * 8 / duration / capacity / 1e6
            jain = (gp1 + gp2) ** 2 / (2 * (gp1**2 + gp2**2)) if goodput else 0
            checks = {"goodput1_mbps": gp1, "goodput2_mbps": gp2, "total_goodput_mbps": goodput,
                "goodput_over_capacity": goodput / capacity, "wire_utilization": wire,
                "queue_mean_packets": qmean, "queue_normalized": qmean / buffer,
                "jain_index": jain}
            for col, calc in checks.items():
                require(near(s[col], calc), f"Independent {col} mismatch: {id_}")
            accepted = int(s["queue_enqueued"])
            overflow = int(s["bottleneck_drops"])
            overflow_p = overflow / (accepted + overflow) if accepted + overflow else 0
            require(near(s["overflow_probability"], overflow_p, absolute=1e-9), f"Overflow formula differs: {id_}")
            row = verified[id_]
            for col, calc in {
                "total_goodput_mbps": goodput,
                "wire_utilization_pct": 100 * wire,
                "queue_mean_packets": qmean,
                "queue_over_buffer_pct": 100 * qmean / buffer,
                "goodput_over_capacity_pct": 100 * goodput / capacity,
            }.items():
                if col in row:
                    require(near(row[col], calc), f"Verified {col} differs from raw: {id_}")
            drop_key = "bottleneck_drops" if group == "h2" else "overflow_drops"
            require(int(row[drop_key]) == overflow, f"Verified overflow count mismatch: {id_}")
            require(row["summary_sha256"] == status["summary_sha256"] if "summary_sha256" in row else True, f"Verified summary SHA differs: {id_}")
            require(row["timeseries_sha256"] == status["timeseries_sha256"] if "timeseries_sha256" in row else True, f"Verified trace SHA differs: {id_}")
            note = "Dynamic flow (do not interpret Jain over 600 s as active-flow fairness)" if group == "h1" and id_.startswith("t0-") else "Two continuous flows; one seed/run only"
            master.append({
                "batch": group.upper(), "id": id_, "tcp1": s["tcp1"], "tcp2": s["tcp2"],
                "duration_s": duration, "capacity_mbps": capacity, "rtt1_ms": s["rtt1_target_ms"], "rtt2_ms": s["rtt2_target_ms"],
                "buffer_ratio": s["buffer_ratio"], "buffer_packets": buffer, "configured_random_loss": s["loss_probability"],
                "seed": s["seed"], "run": s["run"], "flow2_start_s": s["flow2_start_s"], "flow2_stop_s": s["flow2_stop_s"],
                "rx1_bytes": end["rx1_bytes"], "rx2_bytes": end["rx2_bytes"],
                "goodput1_mbps": f"{gp1:.10f}", "goodput2_mbps": f"{gp2:.10f}", "total_goodput_mbps": f"{goodput:.10f}",
                "goodput_over_capacity_pct": f"{100 * goodput / capacity:.8f}", "wire_utilization_pct": f"{100 * wire:.8f}",
                "queue_mean_packets": f"{qmean:.10f}", "queue_over_buffer_pct": f"{100 * qmean / buffer:.8f}",
                "overflow_drops": overflow, "overflow_probability": f"{overflow_p:.12f}",
                "random_drops": s["random_drops"], "jain_whole_duration": f"{jain:.10f}", "sample_count": count,
                "source_sha256": EXPECTED_SOURCE_HASH, "summary_sha256": status["summary_sha256"], "timeseries_sha256": status["timeseries_sha256"],
                "fairness_interpretation": note
            })
            print("AUDIT PASS", id_, "60001 samples", flush=True)
        group_reports[group] = {"cases": 8, "all_status": "PASS", "figures_png": len(png), "figures_svg": len(svg)}
    require(len(master) == 32 and len(all_hashes) == 64, "Duplicates or missing raw CSV hashes")
    out = project / "results/summary/i1"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "i1_master_summary.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=MASTER_COLS)
        writer.writeheader()
        writer.writerows(master)
    report = {"status": "VALIDATED_FROM_RAW_DATA", "cases": len(master), "files_sha256_checked": len(all_hashes),
        "figure_file_count_checked": 40, "group_results": group_reports,
        "source_sha256": EXPECTED_SOURCE_HASH, "ns3_commit": EXPECTED_COMMIT,
        "method": "all 1,920,032 time series data rows read; metrics recomputed from raw counters",
        "limitations": ["One seed/run per case", "No independent rerun of NS-3 in this I1 script", "Figure file count only, not pixel identity", "Paper testbed differs from NS-3", "Whole-duration Jain on T0 not valid as concurrent-fairness metric"]}
    (out / "i1_audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("VERIFIED I1: 32/32; raw hashes and metrics match; 20 PNG + 20 SVG", flush=True)
    print("OUTPUT:", out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=Path.home() / "projects/YeAH-TCP-NPE")
    args = parser.parse_args()
    audit(args.project.expanduser().resolve())

if __name__ == "__main__": main()
