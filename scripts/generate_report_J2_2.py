#!/usr/bin/env python3
"""J2.2: source-audited revisions to report sections 3 and 4 only.

This program uses the existing J2.1 Word as its exact base and performs checks
against the locked NS-3.44 C++ source and original H1--H4 CSVs before writing a
separate J2.2 DOCX. It NEVER writes to raw/ or overwrites J2.1.

Run from anywhere: python3 scripts/generate_report_J2_2.py
Requires python-docx. Prior stage J2.1 must have been generated on this machine.
"""
from __future__ import annotations
import csv, hashlib
from pathlib import Path
from docx import Document
from docx.shared import Pt

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'simulation/yeah-experiment.cc'
OLD = ROOT/'report/Bao_cao_YeAH_TCP_J2_1.docx'
NEW = ROOT/'report/Bao_cao_YeAH_TCP_J2_2.docx'
MASTER = ROOT/'results/summary/i1/i1_master_summary.csv'
RAW = ROOT/'results/raw/experiments'
EXPECTED_SHA = '460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969'
for q in (SOURCE,OLD,MASTER):
    if not q.is_file(): raise SystemExit(f'ERROR: required file missing: {q}')
source_bytes = SOURCE.read_bytes()
if hashlib.sha256(source_bytes).hexdigest() != EXPECTED_SHA:
    raise SystemExit('ERROR: source hash does not match the locked experiment version')
src = source_bytes.decode('utf-8')
required_code = (
    'nodes.Create(4)', 'RngSeedManager::SetSeed(seed)', 'RngSeedManager::SetRun(run)',
    'SetReceiveErrorModel(em)', 'ERROR_UNIT_PACKET', 'TraceConnectWithoutContext("PhyTxBegin"',
    'std::floor(bdpPackets * ratio)', 'MilliSeconds(10)', 'if (Simulator::Now() < endTime)',
    'TraceConnectWithoutContext("Enqueue"', 'TraceConnectWithoutContext("Drop"',
    'SndBufSize', 'RcvBufSize', 'Timestamp', 'Sack', 'WindowScaling',
)
for needle in required_code:
    if needle not in src: raise SystemExit(f'ERROR: simulation source missing expected mechanism: {needle}')
with MASTER.open(newline='', encoding='utf-8-sig') as f: master=list(csv.DictReader(f))
if len(master)!=32 or len({r['id'] for r in master})!=32:
    raise SystemExit('ERROR: I1 master must have 32 unique scenarios')
if any(r['source_sha256']!=EXPECTED_SHA or int(float(r['sample_count']))!=60001 for r in master):
    raise SystemExit('ERROR: I1 master source/sample mismatch')
queue_counts=set(); max_wire=set()
for r in master:
    p=RAW/r['batch'].lower()/r['id']/'summary.csv'
    s=RAW/r['batch'].lower()/r['id']/'timeseries.csv'
    if not p.is_file() or not s.is_file(): raise SystemExit(f'ERROR: missing original CSV: {p} or {s}')
    if hashlib.sha256(p.read_bytes()).hexdigest()!=r['summary_sha256']:
        raise SystemExit(f'ERROR: summary checksum mismatch {r["id"]}')
    if hashlib.sha256(s.read_bytes()).hexdigest()!=r['timeseries_sha256']:
        raise SystemExit(f'ERROR: time series checksum mismatch {r["id"]}')
    with p.open(newline='', encoding='utf-8-sig') as f: raw=next(csv.DictReader(f))
    queue_counts.add(int(raw['queue_samples']))
    max_wire.add(int(raw['max_wire_packet_bytes']))
    if (int(float(raw['initial_cwnd_segments']))!=10 or int(float(raw['mss_bytes']))!=1448 or
        int(float(raw['initial_ssthresh_segments']))!=0 or int(float(raw['seed']))!=1 or
        int(float(raw['run']))!=1 or int(float(raw['duration_s']))!=600):
        raise SystemExit('ERROR: experiment configuration mismatch in '+r['id'])
if queue_counts!={60000}: raise SystemExit(f'ERROR: unexpected queue_samples across runs: {queue_counts}')
if max_wire!={1502}: raise SystemExit(f'ERROR: unexpected max_wire_packet_bytes: {max_wire}')

doc=Document(OLD)
def get_exact(text):
    hits=[p for p in doc.paragraphs if p.text.strip()==text.strip() and p.style.name=='Heading 1']
    if len(hits)!=1: raise SystemExit('ERROR: report J2.1 mismatch; exact paragraph not found once: '+text[:90])
    return hits[0]
def get_by_prefix(prefix):
    hits=[p for p in doc.paragraphs if p.text.startswith(prefix)]
    if len(hits)!=1: raise SystemExit('ERROR: report J2.1 mismatch; paragraph prefix not unique: '+prefix)
    return hits[0]
def replace(prefix, text):
    p=get_by_prefix(prefix)
    p.text=text
    return p

def insert_after(reference, text, style=None):
    from docx.oxml import OxmlElement
    from docx.text.paragraph import Paragraph
    newp=OxmlElement('w:p')
    reference._p.addnext(newp)
    p=Paragraph(newp, reference._parent)
    if style: p.style=style
    p.add_run(text)
    return p

# SECTION 3 ONLY: topology, observable counters, and precise measurement semantics.
replace('Mô phỏng sử dụng NS-3.44',
    'Mô phỏng sử dụng NS-3.44 (Git commit 43dce6710b8df69685e3479c1d33a571dda714ea), Ubuntu 24.04 trong WSL2, build optimized. '
    'Mô hình đúng bốn node: hai sender (node 0, 1), router (node 2) và receiver (node 3); '
    'mỗi sender nối tới router bằng liên kết access 1 Gbps; router nối receiver bằng bottleneck 500 Mbps, trễ lan truyền một chiều 1 ms. '
    'Hai liên kết access đặt trễ một chiều bằng RTT mục tiêu/2 − 1 ms, nên RTT cấu hình là RTT truyền lan danh định, chưa bao gồm các thành phần hàng đợi và xử lý gói. '
    'Bottleneck sử dụng hàng đợi thiết bị DropTail dạng FIFO, không dùng root queue disc bổ sung; hai access queue có giới hạn 20.000 gói. '
    'Các tham số trên lấy từ simulation/yeah-experiment.cc (node, link và queue), không phải suy đoán từ đồ thị kết quả.')
replace('Goodput_i (Mbps) =',
    'Goodput_i (Mbps) = 8 × rx_i_bytes / (T × 10⁶), với rx_i_bytes = PacketSink::GetTotalRx() tại cuối lượt; T = 600 giây. '
    'Với T0, luồng 2 không hoạt động suốt 600 giây, nên goodput toàn kỳ không phản ánh riêng giai đoạn hai luồng cùng truyền.')
replace('Wire utilization =',
    'Wire utilization (tỷ lệ) = 8 × wire_bytes / (C × T); wire_bytes là tổng Packet::GetSize() tại trace PhyTxBegin của thiết bị router → receiver trong thời gian đo, '
    'không phải tổng byte payload ở PacketSink. Với toàn bộ 32 lượt, max_wire_packet_bytes trong CSV là 1502 byte; phép đếm này bao gồm những byte được ghi nhận tại PhyTxBegin '
    'và không được xem là phép đo chính xác tất cả overhead vật lý (preamble, inter-frame gap).')
replace('Normalized queue =',
    'Normalized queue = queue_mean_packets / buffer_packets; queue_mean_packets là trung bình mẫu GetNPackets() của queue thiết bị đầu ra router. '
    'Source ghi 60.001 dòng time series (t = 0, 0,01, …, 600 s tính theo thời điểm bắt đầu đo) nhưng chỉ dùng 60.000 mẫu trước thời điểm kết thúc để tính trung bình hàng đợi; '
    'queue_max_sampled là giá trị cực đại trong các mẫu, không nhất thiết là cực đại tuyệt đối giữa hai lần lấy mẫu.')
replace('Jain =',
    'Jain = (x₁ + x₂)² / [2(x₁² + x₂²)], trong đó x_i là goodput từng luồng trên đúng khoảng đo; '
    'không diễn giải Jain toàn thời lượng T0 như công bằng khi cả hai luồng cùng hoạt động vì thời gian hoạt động không đồng nhất.')
replace('Overflow probability (NS-3) =',
    'Overflow probability (NS-3) = bottleneck_drops / (queue_enqueued + bottleneck_drops). '
    'Cả tử và mẫu là các sự kiện trace trên queue thiết bị router → receiver. Random drops do RateErrorModel tại đầu nhận và other drops trên những thiết bị khác được đếm riêng; '
    'không mặc định mẫu số của xác suất mất gói trong paper là đồng nhất.')
replace('Goodput tính theo byte ứng dụng nhận được',
    'Ứng dụng gửi là BulkSend (MaxBytes = 0, không giới hạn tổng byte), ứng dụng nhận là PacketSink. '
    'MSS = 1448 byte với MTU = 1500 byte, TCP timestamps, SACK và window scaling được bật; initial cwnd = 10 segment, initial ssthresh được đặt UINT32_MAX, '
    'send/receive socket buffer = 64 MiB, delayed ACK count = 2. RateErrorModel sử dụng ERROR_UNIT_PACKET và được gắn tại thiết bị nhận của liên kết bottleneck, '
    'không phải mô hình mất gói được cài trên sender. Thuật toán điều khiển tắc nghẽn được chọn theo node thông qua TcpL4Protocol trước khi tạo BulkSend socket. '
    'Không mô phỏng SURGE hoặc Limited Slow Start; vì vậy không thể xem cấu hình này đồng nhất hoàn toàn với paper.')
sec4=get_exact('4. Kiểm tra tính đúng đắn và khả năng tái lập')
sec4.insert_paragraph_before('3.4. Cửa sổ đo và giới hạn của phép đo',style='Heading 2')
sec4.insert_paragraph_before(
 'Thời gian đo được tính từ startTime = 1 s tới endTime = 1 s + duration. Dữ liệu time series bao gồm mẫu ở mốc cuối để đối chiếu bộ đếm tích lũy, '
 'trong khi trung bình queue chỉ lấy các mẫu có Simulator::Now() < endTime. '
 'WireTx chỉ cộng byte với startTime ≤ t < endTime; PacketSink nhận dữ liệu theo lịch thực tế của ứng dụng. '
 'Bởi vậy không được trộn lẫn goodput đo tại ứng dụng, mức sử dụng liên kết tại trace PhyTxBegin và xác suất rơi tại DropTail.')

# SECTION 4 ONLY: what upstream unit tests and validation can/cannot establish.
replace('Bộ kiểm thử upstream tcp-yeah-test của NS-3.44',
    'Bộ kiểm thử upstream tcp-yeah-test của NS-3.44 báo PASS 1/1 test suite theo tests/tcp-yeah-unit-test.log; '
    'đây là kiểm tra thuật toán có sẵn, không tự chứng minh topology BTL đúng hay kết quả tương đương paper. '
    'Pilot F xác nhận chương trình tạo trace và CSV; G1 chạy lại cùng source, seed và tham số cho hai CSV trùng từng byte; '
    'G2 kiểm tra lựa chọn YeAH/NewReno theo node, CUBIC với RTT bất đối xứng và bộ đếm random drops; '
    'G3 benchmark mô phỏng dài và diễn biến utilization; G4 xác nhận các trace đã chọn không đổi khi chuyển default sang optimized. '
    'Những phép thử này chỉ xác nhận chức năng và tính nhất quán trong phạm vi cấu hình đã thực hiện.')
replace('Việc ảnh PNG không trùng hash',
    'Kiểm toán H1–H4 đối chiếu SHA-256 của 64 CSV gốc theo trạng thái thực thi, tính lại goodput/queue/drop/Jain từ dữ liệu và tái tạo bảng bằng script; '
    'audit_I1.py đạt 32/32 và compare_I2.py liên kết đủ 32 hồ sơ đo với bảng đối chiếu paper. '
    'Độ đồng nhất nhị phân của ảnh PNG giữa các môi trường không phải tiêu chí kết luận dữ liệu đổi; phải truy xuất hình tới CSV và mã tạo hình. '
    'Không sử dụng kiểm toán này để khẳng định tính đúng tuyệt đối của mô hình hoặc sự phù hợp thống kê với paper.')
sec5=get_exact('5. Test thí nghiệm trên các kịch bản và thu kết quả')
sec5.insert_paragraph_before('4.3. Giới hạn của việc kiểm thử',style='Heading 2')
sec5.insert_paragraph_before(
 'Để tránh đánh đồng tính tái lập với tính hợp lệ khoa học, báo cáo tách ba mức chứng cứ: '
 '(i) mã nguồn và cấu hình đúng theo các file đã khóa, (ii) số liệu CSV và bảng được kiểm toán độc lập, '
 '(iii) mức độ tương đồng với paper cần phân tích riêng ở phần 6. '
 'Các thí nghiệm chỉ có seed/run = 1/1 mỗi cấu hình, không cung cấp phương sai hoặc khoảng tin cậy; '
 'unit test upstream không kiểm tra lỗi phép chia nguyên 1 / m_phy theo công thức paper. '
 'Đây là giới hạn của BTL, không phải bằng chứng dữ liệu bị chỉnh sửa.')

# Apply accurate stage label without altering data tables or later sections.
for footer in doc.sections[0].footer.paragraphs:
    if 'Bản rà soát J2.1' in footer.text:
        for run in footer.runs:
            if 'Bản rà soát J2.1' in run.text:
                run.text=run.text.replace('Bản rà soát J2.1','Bản rà soát J2.2')

NEW.parent.mkdir(parents=True,exist_ok=True)
doc.save(NEW)
print('REPORT:',NEW)
print('SOURCE_SHA256:', EXPECTED_SHA)
print('SCENARIOS:',len(master),'TOTAL_SAMPLES:',sum(int(float(r['sample_count'])) for r in master))
print('QUEUE_SAMPLES_PER_CASE:', next(iter(queue_counts)))
print('MAX_WIRE_PACKET_BYTES_OBSERVED:',next(iter(max_wire)))
print('SCOPE: sections 3-4 revised; sections 1-2 and 5-6, all 10 tables and 8 images retained')
