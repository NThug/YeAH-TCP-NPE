#!/usr/bin/env python3
"""I2: compare ns-3 VERIFIED I1 data against exact published YeAH paper facts.

No NS-3 measurements are hard-coded. They are read from the 32-row I1
master CSV, which itself is independently calculated from raw simulations.

The only hard-coded reference input is a separately sourced exact table from
YeAH-TCP (2007), Table I, printed p.40 / PDF page 4. Missing values denote
'no packet loss observed', not an experimentally measured probability zero.

Outputs are derived summaries, NOT new measurements; no raw files are changed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

SOURCE_SHA = "460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969"
I1_MASTER_SHA = "3f7b0aa9f07d5b69770825decb35cee641b5ce1a77f0f52bca68407c6936400b"
REF_SHA = "4fd41070f3d728304b832b28ed3bd07edff56babf583922b202dca0b5768e468"
VALID_P = (1e-8, 1e-6, 1e-5, 1e-4)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for data in iter(lambda: f.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def loadcsv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def req(test, reason):
    if not test:
        raise RuntimeError(reason)


def writecsv(path, rows, columns):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def f(row, field):
    return float(row[field])


def main(project: Path):
    project = project.resolve()
    source = project / "simulation/yeah-experiment.cc"
    masterfile = project / "results/summary/i1/i1_master_summary.csv"
    reffile = project / "refs/paper_table_I_2007.csv"

    for path, expected in ((source, SOURCE_SHA), (masterfile, I1_MASTER_SHA), (reffile, REF_SHA)):
        req(path.is_file(), f"Missing input: {path}")
        req(sha256(path) == expected, f"SHA-256 MISMATCH: {path}; investigate, do not overwrite")

    master = loadcsv(masterfile)
    req(len(master) == 32, "I1 must contain exactly 32 cases")
    indexed = {r["id"]: r for r in master}
    req(len(indexed) == 32, "Duplicate case IDs in I1")
    req(all(r["source_sha256"] == SOURCE_SHA and int(r["sample_count"]) == 60001 for r in master), "Invalid source or samples")
    ref = loadcsv(reffile)
    req(len(ref) == 6, "Reference Table I needs six rows")

    out = project / "results/summary/i2"
    out.mkdir(parents=True, exist_ok=True)

    # Table I: exact published Reno probabilities, observed no-loss for YeAH.
    table1 = []
    for r in ref:
        tcp, rtt = r["tcp"], int(r["rtt_ms"])
        req(tcp in ("yeah", "reno") and rtt in (15, 60, 240), "Unexpected Table I entry")
        rr = indexed[f"t1-{tcp}-rtt{rtt}"]
        paper_val = r["paper_overflow_probability_exact"]
        req((tcp == "reno") == bool(paper_val), "Incorrect numeric/dash classification in paper")
        drops = int(rr["overflow_drops"])
        prob = f(rr, "overflow_probability")
        req(drops >= 0 and prob >= 0, "Invalid NS3 overflow metric")
        table1.append({
            "rtt_ms": rtt, "tcp": tcp,
            "paper_probability_exact": paper_val,
            "paper_note": r["paper_observation_note"],
            "ns3_overflow_probability": f"{prob:.12f}",
            "ns3_overflow_drops": drops,
            "ns3_queue_over_buffer_pct": rr["queue_over_buffer_pct"],
            "ns3_wire_utilization_pct": rr["wire_utilization_pct"],
            "ns3_case_id": rr["id"],
            "ns3_summary_sha256": rr["summary_sha256"],
            "comparison_limitation": "Different testbeds; sampling/denominator not proven identical; one NS3 run vs >=3 paper runs",
        })
    writecsv(out / "i2_table_I_comparison.csv", table1, list(table1[0]))

    # Figure 3, 5, 6, 7: report only our measured points; NEVER digitize paper curve.
    def row_metric(r, xname, xval):
        return {
            xname: xval, "tcp": r["tcp1"], "ns3_case_id": r["id"],
            "wire_utilization_pct": r["wire_utilization_pct"],
            "goodput_mbps": r["total_goodput_mbps"],
            "queue_over_buffer_pct": r["queue_over_buffer_pct"],
            "overflow_drops": r["overflow_drops"],
            "jain_whole_600s": r["jain_whole_duration"],
            "ns3_summary_sha256": r["summary_sha256"],
        }

    figs = {}
    figs["fig3"] = [row_metric(indexed[f"t1-{tcp}-rtt{rtt}"], "rtt_ms", rtt)
        for rtt in (15, 60, 240) for tcp in ("yeah", "reno")]
    figs["fig6"] = [row_metric(indexed[f"t2-{tcp}-beta{beta}"], "buffer_ratio", ratio)
        for ratio, beta in ((0.125, "0p125"), (0.25, "0p25"), (0.5, "0p5"), (1.0, "1p0")) for tcp in ("yeah", "reno")]
    figs["fig7"] = [row_metric(indexed[f"t3-{tcp}-ratio{rtt_ratio}"], "rtt_ratio", rtt_ratio)
        for rtt_ratio in (1, 2, 3, 4) for tcp in ("yeah", "reno")]
    figs["fig5"] = [row_metric(indexed[f"t4-{tcp}-p{pstr}"], "configured_loss_p", pstr)
        for pstr in ("1e-8", "1e-6", "1e-5", "1e-4") for tcp in ("yeah", "reno")]
    for figure, records in figs.items():
        writecsv(out / f"i2_{figure}_ns3_measured.csv", records, list(records[0]))

    # Validate pairing and interpret only signs/trends supported by the points.
    f3 = figs["fig3"]
    queue_pairs = [(float(f3[i]["queue_over_buffer_pct"]), float(f3[i+1]["queue_over_buffer_pct"])) for i in (0, 2, 4)]
    f6 = figs["fig6"]
    yeah6 = [float(f6[i]["queue_over_buffer_pct"]) for i in (0, 2, 4, 6)]
    f7 = figs["fig7"]
    jain_pairs = [(float(f7[i]["jain_whole_600s"]), float(f7[i+1]["jain_whole_600s"])) for i in (0, 2, 4, 6)]
    f5 = figs["fig5"]
    wire_pairs = [(float(f5[i]["wire_utilization_pct"]), float(f5[i+1]["wire_utilization_pct"])) for i in (0, 2, 4, 6)]
    comparison = {
        "paper_table_I_pdf_page": 4, "paper_table_I_print_page": 40,
        "fig3_yeah_queue_less_than_reno_at_all_measured_rtts": all(a < b for a, b in queue_pairs),
        "fig6_yeah_queue_normalized_first_last_pct": [yeah6[0], yeah6[-1]],
        "fig6_yeah_queue_normalized_increases_at_measured_points": all(a < b for a, b in zip(yeah6, yeah6[1:])),
        "fig7_jain_yeah_higher_than_reno_for_ratios_2_3_4": all(a > b for a, b in jain_pairs[1:]),
        "fig5_wire_yeah_higher_than_reno_by_p_order": [a > b for a, b in wire_pairs],
        "comparison_type": "Table I: exact numeric paper values; Figs 3/5/6/7: paper qualitative claims vs NS3 measured points",
        "limitations": [
            "No invented/digitized numerical values from paper figures",
            "Paper is a physical Linux testbed with SURGE and Limited Slow Start; NS-3 differs",
            "Paper >=3 repeats per point; NS3 exactly 1 run/point",
            "Paper Table I denominator not established equivalent to NS3 enqueue/drop-based formula",
            "T0 whole-duration Jain is not a simultaneous-flow fairness measure",
            "All fairness values explicitly refer to 0-600 s",
        ],
    }
    (out / "i2_comparison_audit.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    docs = project / "docs"
    docs.mkdir(exist_ok=True)
    lines = [
        "# I2 – Đối chiếu bài báo gốc và mô phỏng NS-3.44 (từ dữ liệu đã kiểm toán)",
        "", "**Trạng thái:** Đây là bảng đối chiếu tự động từ I1 đã khóa; không chạy thêm thí nghiệm.",
        "", "## Nguồn và giới hạn so sánh",
        "- Paper: A. Baiocchi, A. P. Castellani, F. Vacirca, *YeAH-TCP: Yet Another Highspeed TCP*, PFLDnet 2007, Table I (trang in 40, trang PDF 4); Figure 1, 3, 5, 6, 7 (trang in 39–41).",
        "- NS-3: `results/summary/i1/i1_master_summary.csv`, được tạo bởi `audit_I1.py` từ 32 lượt mô phỏng gốc đã kiểm toán.",
        "- Table I: số giấy báo về Reno là **chính xác**, dấu gạch ngang của YeAH có nghĩa **không phát hiện gói tràn** trong thí nghiệm; không thay bằng tỷ lệ 0 chính xác.",
        "- Chương trình NS-3 đo `overflow_probability = bottleneck_drops/(queue_enqueued+bottleneck_drops)` bằng trace của `DropTailQueue` (kiểm tra từ source). **Chưa chứng minh được mẫu số giống paper**; vì vậy không tính phần trăm sai lệch/nhân tỷ số như thể phép đo hoàn toàn đồng nhất.",
        "- Paper: Linux testbed, 500 Mbps, data packets 1500 bytes, có web cross-traffic SURGE trung bình 4 Mbps, Limited Slow Start, >=3 lần/điểm. NS-3: một seed/run, MSS 1448, không mô phỏng SURGE và Limited Slow Start. Không gọi đây là phép tái hiện chính xác hoàn toàn.",
        "", "## Table I – Các giá trị paper chính xác và NS-3 tính từ I1", "",
        "| RTT | TCP | Paper: xác suất tràn | NS-3: xác suất tràn | NS-3: số drop |",
        "|---:|---|---:|---:|---:|",
    ]
    for row in table1:
        p = row["paper_probability_exact"] or "– (không ghi nhận)"
        lines.append(f"| {row['rtt_ms']} ms | {row['tcp']} | {p} | {float(row['ns3_overflow_probability']):.10g} | {row['ns3_overflow_drops']} |")
    lines += [
        "", "## Đối chiếu xu hướng các hình (không dựng giá trị số paper từ ảnh)",
        f"- **Figure 3:** NS-3 YeAH có queue chuẩn hóa thấp hơn NewReno tại 15, 60, 240 ms: **{comparison['fig3_yeah_queue_less_than_reno_at_all_measured_rtts']}**. Paper mô tả YeAH duy trì hàng đợi thấp; mức giảm cụ thể KHÔNG được suy diễn từ nét vẽ.",
        f"- **Figure 6:** YeAH NS-3 đi từ {yeah6[0]:.4f}% (buffer 12,5% BDP) tới {yeah6[-1]:.4f}% (buffer 100% BDP), tăng tại các điểm đo: **{comparison['fig6_yeah_queue_normalized_increases_at_measured_points']}**. Paper mô tả YeAH có xu hướng giảm queue normalized khi buffer tăng; như vậy xu hướng thực nghiệm NS-3 này **không phù hợp với phát biểu định tính đó**, cần phân tích khác biệt mô hình.",
        f"- **Figure 7:** YeAH NS-3 có Jain cao hơn NewReno tại tỷ số 2/3/4: **{comparison['fig7_jain_yeah_higher_than_reno_for_ratios_2_3_4']}**. Mỗi tỷ số chỉ có 1 lượt, Jain đo toàn bộ 600s; không khẳng định YeAH luôn RTT-fair hoặc đường cong khớp paper.",
        f"- **Figure 5:** 4 so sánh wire utilization YeAH > NewReno theo p tăng dần: **{comparison['fig5_wire_yeah_higher_than_reno_by_p_order']}**. Paper cho biết YeAH chịu mất gói độc lập tốt hơn Reno; ở ba trong bốn giá trị đo của NS-3, nhận định về thứ hạng **không khớp**. Không có trị số chính xác của đường Figure 5 nếu chưa số hóa có kiểm chứng.",
        "- **Figure 1:** Chúng ta có T0 với flow2 start=60s, application stop=400s; dữ liệu TCP có thể drain sau stop. Đối chiếu cơ chế động ở mức định tính, không đo đối xứng hoàn toàn khi điều kiện paper không được mô tả đủ chi tiết.",
        "", "## Những kết luận KHÔNG được rút ra", "",
        "- Không kết luận thuật toán nào ưu việt trong mọi trường hợp.",
        "- Không gọi 'khớp 100% paper' chỉ vì chương trình đạt 100% audit.",
        "- Không dùng chỉ số Jain toàn thời gian của T0 như độ công bằng trong thời gian hai luồng thực sự hoạt động đồng thời.",
        "- Không chuyển dấu '–' của paper thành 0 như một xác suất chính xác hoặc trích trị số bất kỳ từ đồ thị paper mà không có phương pháp số hóa rõ ràng.",
    ]
    (docs / "I2_doi_chieu_paper_generated.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("VERIFIED I2: 32 I1 records linked; Table I 6 published comparisons; Figs 3/5/6/7 measured points derived")
    print("OUTPUT:", out)
    print("NOTES:", docs / "I2_doi_chieu_paper_generated.md")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, default=Path.home() / "projects/YeAH-TCP-NPE")
    args = ap.parse_args()
    main(args.project)
