#!/usr/bin/env python3
"""J2.3: scientifically conservative review of sections 5 and 6 ONLY.

Inputs are the J2.2 Word and locked I1/I2 datasets. Outputs a separate J2.3
Word. Nothing is written to simulation/, raw/, summary/, or figures/.

Run from the project: python3 scripts/generate_report_J2_3.py
Requires python-docx.
"""
from __future__ import annotations
import csv
import hashlib
from pathlib import Path
from docx import Document

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'report/Bao_cao_YeAH_TCP_J2_2.docx'
NEW = ROOT / 'report/Bao_cao_YeAH_TCP_J2_3.docx'
SOURCE = ROOT / 'simulation/yeah-experiment.cc'
MASTER = ROOT / 'results/summary/i1/i1_master_summary.csv'
COMPARE = ROOT / 'results/summary/i2/i2_table_I_comparison.csv'
RAW = ROOT / 'results/raw/experiments'
SHA = '460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969'
for path in [OLD, SOURCE, MASTER, COMPARE]:
    if not path.is_file():
        raise SystemExit(f'ERROR: missing required input {path}')
if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SHA:
    raise SystemExit('ERROR: source differs from 32 recorded experiments')
with MASTER.open(newline='', encoding='utf-8-sig') as f:
    master = list(csv.DictReader(f))
with COMPARE.open(newline='', encoding='utf-8-sig') as f:
    paper_comparison = list(csv.DictReader(f))
if len(master) != 32 or len({r['id'] for r in master}) != 32:
    raise SystemExit('ERROR: master must contain 32 unique scenarios')
if len(paper_comparison) != 6 or {(int(r['rtt_ms']),r['tcp']) for r in paper_comparison} != {
    (rt,tcp) for rt in (15,60,240) for tcp in ('yeah','reno')
}:
    raise SystemExit('ERROR: Table I comparison must have exact six pairs')
master_by_id = {r['id']:r for r in master}
for r in master:
    if r['source_sha256'] != SHA or int(r['sample_count']) != 60001 or int(float(r['duration_s'])) != 600:
        raise SystemExit('ERROR: source/version/duration/sample mismatch: '+r['id'])
    for fname,sha_key in [('summary.csv','summary_sha256'),('timeseries.csv','timeseries_sha256')]:
        f = RAW/r['batch'].lower()/r['id']/fname
        if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest() != r[sha_key]:
            raise SystemExit('ERROR: raw CSV hash mismatch: '+str(f))
for r in paper_comparison:
    base = master_by_id.get(r['ns3_case_id'])
    if not base or base['summary_sha256'] != r['ns3_summary_sha256']:
        raise SystemExit('ERROR: I2 comparison not linked to original I1 file')
    if abs(float(base['overflow_probability'])-float(r['ns3_overflow_probability']))>1e-10:
        raise SystemExit('ERROR: I2 overflow probability differs from I1')
    if int(base['overflow_drops']) != int(r['ns3_overflow_drops']):
        raise SystemExit('ERROR: I2 overflow counts differ from I1')

# Explicit guards for ALL reported values used in the revised prose.
def byid(id): return master_by_id[id]
def approx(actual,expected,eps=0.011): return abs(float(actual)-expected)<eps
for rt,v1,v2 in [(15,70.99,72.95),(60,46.94,59.50),(240,0.73,50.99)]:
    if not approx(byid(f't1-yeah-rtt{rt}')['queue_over_buffer_pct'],v1) or not approx(byid(f't1-reno-rtt{rt}')['queue_over_buffer_pct'],v2):
        raise SystemExit('ERROR: T1 queue assertions disagree with I1')
for beta,id_,expected in [('0p125','t2-yeah-beta0p125',401.81),('0p5','t2-yeah-beta0p5',469.72),('1p0','t2-yeah-beta1p0',461.00)]:
    if not approx(byid(id_)['total_goodput_mbps'], expected):
        raise SystemExit('ERROR: T2 goodput assertion disagrees with I1: '+beta)
for i in (1,2,3,4):
    y=float(byid(f't3-yeah-ratio{i}')['jain_whole_duration'])
    n=float(byid(f't3-reno-ratio{i}')['jain_whole_duration'])
    if i>1 and not y>n:
        raise SystemExit('ERROR: T3 fairness interpretation no longer holds')
for s in ('1e-8','1e-6','1e-5','1e-4'):
    y=float(byid('t4-yeah-p'+s)['total_goodput_mbps'])
    n=float(byid('t4-reno-p'+s)['total_goodput_mbps'])
    if (y>n) != (s=='1e-4'):
        raise SystemExit('ERROR: T4 goodput ordering no longer holds: '+s)

doc = Document(OLD)
before_tables = [[tuple(c.text for c in row.cells) for row in t.rows] for t in doc.tables]
before_media = sorted([p.blob for p in doc.part.related_parts.values() if p.content_type.startswith('image/')])
# Ignore field/footer metadata: all actual report paragraphs in Sections 1-4 must stay untouched.
start5 = [i for i,p in enumerate(doc.paragraphs) if p.style.name=='Heading 1' and p.text.startswith('5. ') ]
start6 = [i for i,p in enumerate(doc.paragraphs) if p.style.name=='Heading 1' and p.text.startswith('6. ') ]
end6   = [i for i,p in enumerate(doc.paragraphs) if p.style.name=='Heading 1' and p.text=='TÀI LIỆU THAM KHẢO']
if list(map(len,(start5,start6,end6))) != [1,1,1] or not start5[0]<start6[0]<end6[0]:
    raise SystemExit('ERROR: unexpected report section structure')
unchanged_before=[p.text for p in doc.paragraphs[:start5[0]]]
unchanged_after=[p.text for p in doc.paragraphs[end6[0]:]]
revisions={
'Hai luồng được kiểm tra ở RTT 80/80 ms':
    'Trong T0, cả hai liên kết truy cập được cấu hình RTT danh định 80 ms và buffer bằng 100% BDP. Luồng 1 hoạt động trong toàn bộ 600 giây; ứng dụng của luồng 2 bắt đầu tại giây 60 và được yêu cầu dừng tại giây 400. Do bộ đệm gửi TCP và dữ liệu đang truyền, thời điểm ứng dụng dừng không đồng nhất với thời điểm PacketSink ngừng nhận. Hai hình cwnd và queue mô tả động học của cấu hình này; không thể khẳng định trùng định lượng Figure 1 nếu thiếu các thông số gốc của hình trong paper.',
'Kịch bản T0 nhằm quan sát động học':
    'T0 là kiểm thử động học luồng tham gia/rời mạng, không phải phép đánh giá Jain toàn kỳ. Khi muốn đánh giá tính công bằng lúc hai luồng cùng gửi, phải dùng goodput đo trên cùng một cửa sổ hai luồng đang hoạt động; Jain tính trên toàn bộ 600 giây không có ý nghĩa đó.',
'Trong ba mức RTT đo được, YeAH có queue/buffer':
    'Tại RTT 15, 60 và 240 ms, tỷ lệ queue/buffer của YeAH lần lượt là 70,99%, 46,94% và 0,73%; tương ứng NewReno là 72,95%, 59,50% và 50,99%. Vì vậy YeAH thấp hơn NewReno về hàng đợi trung bình chuẩn hóa ở cả ba điểm, nhưng điều đó không đồng nghĩa YeAH luôn duy trì hàng đợi nhỏ tuyệt đối (chẳng hạn 70,99% tại 15 ms). Cả hai thuật toán đều ghi nhận tràn buffer. Với RTT 240 ms, việc trung bình queue thấp nhưng vẫn có overflow không tự mâu thuẫn: queue là mẫu lấy mỗi 10 ms, còn drop là bộ đếm sự kiện. Chưa phân tích chi tiết các burst giữa những lần lấy mẫu để kết luận nguyên nhân. Không ngoại suy cho RTT 30, 120 hoặc 480 ms chưa mô phỏng.',
'Ở β=0,125, YeAH có goodput cao hơn NewReno':
    'Ở β=0,125, YeAH đạt goodput 401,81 Mbps so với 358,07 Mbps của NewReno; ở β=1,0, YeAH đạt 461,00 Mbps so với 481,23 Mbps của NewReno (đều đo trên 600 giây). Goodput YeAH không tăng đơn điệu theo β: tại β=0,5 đạt 469,72 Mbps, lớn hơn tại β=1,0. Tỷ lệ queue/buffer của YeAH tăng tại bốn điểm β đã đo, trái với mô tả xu hướng giảm trong Figure 6 của paper. Vì mẫu số buffer cũng thay đổi theo β, không được đánh đồng queue chuẩn hóa với số gói chờ tuyệt đối. Đây là khác biệt quan sát được; chưa có thí nghiệm cô lập nguyên nhân.',
'YeAH có Jain cao hơn NewReno tại tỷ số 2, 3 và 4':
    'Với tỷ số RTT₂/RTT₁ bằng 1, cả hai thuật toán đạt Jain gần 1 khi tính trong 600 giây. Tại tỷ số 2, 3 và 4, YeAH có Jain toàn kỳ cao hơn NewReno trong từng cấu hình đã đo; song Jain tại tỷ số 4 lại cao hơn tỷ số 3 ở cả hai thuật toán. Kết quả theo riêng cửa sổ 300–600 giây có thể thay đổi thứ hạng, nên mọi đánh giá công bằng phải ghi rõ khoảng đo. Mỗi điểm chỉ có một run, không có cơ sở phát biểu YeAH luôn công bằng hơn.',
'Tại p=10⁻⁸, cả hai luồng không ghi nhận random drop':
    'Ở p=10⁻⁸, hai kịch bản đều ghi nhận 0 random drop trong một lần chạy; đây không phải phép đo xác suất bằng 0. Trong bốn xác suất cấu hình, goodput NewReno cao hơn YeAH tại 10⁻⁸, 10⁻⁶, 10⁻⁵; YeAH cao hơn tại 10⁻⁴. Chỉ số wire utilization và goodput là hai đại lượng khác nhau, dù đều phản ánh mức sử dụng mạng. Số gói rơi do lỗi ngẫu nhiên cũng không thể đem so trực tiếp giữa hai thuật toán như một phép đo độ bền vững độc lập, vì số gói đi qua mô hình lỗi không giống nhau. Chưa có đủ lượt chạy để kết luận có ý nghĩa thống kê.',
'Điểm khác biệt đáng chú ý: YeAH không được paper ghi nhận tràn buffer':
    'Table I của paper ghi “–” đối với YeAH tại RTT 15, 60 và 240 ms, nghĩa là không quan sát thấy gói tràn trong các lượt đo của tác giả, không phải xác suất đúng bằng 0. NS-3 ghi nhận tương ứng 412, 1.968 và 6.581 sự kiện tràn; xác suất NS-3 được tính từ số drop/(enqueue + drop) trên hàng đợi bottleneck. Chỉ các giá trị xác suất Reno của paper là các số công bố trực tiếp trong Table I. Vì mẫu số và điều kiện đo của paper chưa được chứng minh trùng NS-3, báo cáo trình bày hai cột song song nhưng không tính phần trăm sai lệch hoặc khẳng định tỷ số định lượng tương đương.',
'Các Figure paper không có bảng dữ liệu số chính xác đi kèm':
    'Figures 1, 3, 5, 6 và 7 của paper được đối chiếu ở mức phạm vi kịch bản và xu hướng được tác giả mô tả, không gán số đọc bằng mắt từ đường cong cho các điểm chưa công bố. Số đo NS-3 là dữ liệu thực nghiệm riêng, không phải phép số hóa hay phép nội suy dữ liệu bài báo.',
'Khác biệt điều kiện: paper mô tả web cross traffic SURGE':
    'Khác biệt điều kiện: paper mô tả web cross traffic theo SURGE (lưu lượng trung bình khoảng 4 Mbps) và Limited Slow Start; những thành phần này không được triển khai trong mô hình NS-3 của BTL. Chưa có thí nghiệm riêng chứng minh mức tác động của từng thành phần.',
'Khác biệt implementation: nhánh điều kiện “1 / m_phy”':
    'Khác biệt implementation: biểu thức (1 / m_phy) trong nhánh quyết định chế độ của TcpYeah NS-3.44 thực hiện phép chia nguyên theo kiểu dữ liệu được khai báo. Tuy nhiên, BTL chưa chạy phiên bản chỉ sửa riêng biểu thức này, nên chỉ ghi nhận khác biệt mã nguồn, không quy kết đây là nguyên nhân đã được chứng minh cho mọi sai lệch hiệu năng.',
'Bài tập đã xây dựng được mô hình bottleneck':
    'Bài tập xây dựng mô hình bottleneck hai luồng trên NS-3.44 và thực hiện 32 kịch bản, mỗi kịch bản 600 giây. Dữ liệu raw đã được kiểm toán, các bảng và hình có script tái tạo. Trong các cấu hình đã đo, YeAH có queue/buffer trung bình thấp hơn NewReno ở ba RTT của T1, nhưng có mức hàng đợi cao tại RTT 15 ms; trong T2, xu hướng queue/buffer của YeAH khác Figure 6; trong T4, thứ hạng goodput giữa hai thuật toán thay đổi theo xác suất lỗi. Đây là kết quả thực nghiệm của mô hình NS-3.44, không được gọi là xác nhận định lượng toàn diện cho paper.',
'Vì không tái hiện toàn bộ testbed vật lý':
    'Bài tập không tái hiện đầy đủ testbed Linux vật lý, SURGE, Limited Slow Start và các cấu hình thuật toán đối chứng khác của paper; mỗi kịch bản cũng chỉ chạy một lần với seed/run = 1/1. Vì vậy, các nhận xét chỉ áp dụng cho tập cấu hình thực nghiệm được công bố trong báo cáo, không có kiểm định ý nghĩa thống kê hoặc suy luận nhân quả về từng khác biệt. Điểm mạnh của BTL là chuỗi tái tạo và kiểm toán minh bạch, không phải sự trùng khớp cưỡng ép với kết quả năm 2007.'
}
for prefix,newtext in revisions.items():
    matches=[(i,p) for i,p in enumerate(doc.paragraphs) if p.text.startswith(prefix)]
    if len(matches)!=1 or not start5[0]<=matches[0][0]<end6[0]:
        raise SystemExit('ERROR: expected unique paragraph in sections 5-6: '+prefix)
    matches[0][1].text=newtext

# Verify invariant sections and exact tables and embedded image payloads.
if [p.text for p in doc.paragraphs[:start5[0]]] != unchanged_before:
    raise SystemExit('ERROR: section 1-4 content unexpectedly changed')
if [p.text for p in doc.paragraphs[end6[0]:]] != unchanged_after:
    raise SystemExit('ERROR: references / appendix unexpectedly changed')
if [[tuple(c.text for c in row.cells) for row in t.rows] for t in doc.tables] != before_tables:
    raise SystemExit('ERROR: table text unexpectedly changed')
if sorted([p.blob for p in doc.part.related_parts.values() if p.content_type.startswith('image/')]) != before_media:
    raise SystemExit('ERROR: embedded images unexpectedly changed')
# Layout-only cleanup: J2.2's explicit blank page-break paragraph immediately
# before T3 can produce a completely blank page after Section T2 grows in J2.3.
# Put the page-break on the T3 heading itself instead. This changes no content.
heading_t3 = [p for p in doc.paragraphs if p.text.startswith('5.5. T3 – Fairness')]
if len(heading_t3) != 1: raise SystemExit('ERROR: cannot locate T3 heading')
t3 = heading_t3[0]
prev = t3._p.getprevious()
if prev is None or 'w:type="page"' not in prev.xml:
    raise SystemExit('ERROR: unexpected layout: expected explicit break immediately before T3')
prev.getparent().remove(prev)
t3.paragraph_format.page_break_before = True

for footer in doc.sections[0].footer.paragraphs:
    for run in footer.runs:
        if 'Bản rà soát J2.2' in run.text:
            run.text=run.text.replace('Bản rà soát J2.2','Bản rà soát J2.3')
NEW.parent.mkdir(parents=True,exist_ok=True)
doc.save(NEW)
print(f'REPORT: {NEW}')
print(f'SOURCE_SHA256: {SHA}')
print('SCENARIOS: 32 TOTAL_SAMPLES: 1920032')
print(f'J2.3 VERIFIED: {len(revisions)} science revisions, 10 tables and 8 images unchanged; 64 raw CSV hashes match')
print('SCOPE: sections 5-6 revised; sections 1-4 and references/appendix unchanged')
