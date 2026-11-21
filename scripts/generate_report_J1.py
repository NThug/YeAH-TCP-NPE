#!/usr/bin/env python3
"""Build the YeAH-TCP report from the VERIFIED I1/I2 CSV and the figures generated on WSL.
No experimental metric is hardcoded in this script. All numerical result tables read the CSV.
Run: python3 scripts/generate_report_J1.py from YeAH-TCP-NPE root.
Requires: python-docx; matplotlib figures and I1/I2 analysis already produced.
"""
from __future__ import annotations
import csv, hashlib, sys, os
from pathlib import Path
from collections import defaultdict
from docx import Document
from docx.shared import Inches, Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT/'simulation/yeah-experiment.cc'
MASTER = ROOT/'results/summary/i1/i1_master_summary.csv'
I2 = ROOT/'results/summary/i2'
FIGS = ROOT/'results/figures'
REF = ROOT/'refs/paper_table_I_2007.csv'
OUT = ROOT/'report/Bao_cao_YeAH_TCP_BAN_NHAP_J1.docx'
NEEDED = [SRC, MASTER, REF, *[I2/f for f in ('i2_table_I_comparison.csv','i2_fig3_ns3_measured.csv','i2_fig5_ns3_measured.csv','i2_fig6_ns3_measured.csv','i2_fig7_ns3_measured.csv')], *[FIGS/p for p in ('h1/t0-yeah-reno_cwnd.png','h1/t0-yeah-reno_queue.png','h1/t1_rtt_queue.png','h1/t1_rtt_overflow.png','h2/t2_buffer_queue_normalized.png','h2/t2_buffer_goodput.png','h3/t3_rtt_ratio_fairness_0_600.png','h4/t4_loss_wire_utilization.png','h4/t4_loss_goodput.png')]]
missing = [str(x.relative_to(ROOT)) for x in NEEDED if not x.is_file()]
if missing:
    sys.exit('ERROR: Missing verified data/input files:\n  ' + '\n  '.join(missing))

def readcsv(p):
    with p.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

master = readcsv(MASTER)
if len(master) != 32 or any(int(float(r['sample_count'])) != 60001 for r in master):
    sys.exit('ERROR: I1 master lacks exactly 32 × 60001 verified samples.')
source_hash = hashlib.sha256(SRC.read_bytes()).hexdigest()
if len({r['source_sha256'] for r in master}) != 1 or master[0]['source_sha256'] != source_hash:
    sys.exit('ERROR: Simulation source hash does not match verified I1 master.')
byid = {r['id']: r for r in master}
if len(byid) != 32:
    sys.exit('ERROR: Scenario IDs are not unique')
for row in readcsv(I2/'i2_table_I_comparison.csv'):
    raw = byid[row['ns3_case_id']]
    if row['ns3_summary_sha256'] != raw['summary_sha256']:
        sys.exit('ERROR: I2 vs I1 summary hash mismatch '+row['ns3_case_id'])

def n(row, field): return float(row[field])
def fmt(x, dec=2): return f'{float(x):,.{dec}f}'.replace(',',' ')  # avoid decimal locale ambiguity

def set_cell_shading(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement('w:shd'); sh.set(qn('w:fill'), fill); tcPr.append(sh)

def no_split(row):
    trPr=row._tr.get_or_add_trPr(); keep=OxmlElement('w:cantSplit'); trPr.append(keep)

def keep_with_next(p): p.paragraph_format.keep_with_next=True

doc=Document()
sec=doc.sections[0]
sec.page_width=Cm(21);sec.page_height=Cm(29.7)
sec.top_margin=Cm(2);sec.bottom_margin=Cm(2);sec.left_margin=Cm(2.35);sec.right_margin=Cm(2.15)
sec.header_distance=Cm(.9);sec.footer_distance=Cm(1.0)
normal=doc.styles['Normal']; normal.font.name='Times New Roman'; normal.font.size=Pt(11.5); normal.font.color.rgb=RGBColor(33,42,51)
normal._element.rPr.rFonts.set(qn('w:eastAsia'),'Times New Roman')
normal.paragraph_format.space_after=Pt(5)
normal.paragraph_format.line_spacing=1.13
for name, pts, color in [('Title',18,RGBColor(27,57,84)),('Heading 1',14,RGBColor(24,59,92)),('Heading 2',12.5,RGBColor(29,67,95)),('Heading 3',11.6,RGBColor(45,72,91))]:
    st=doc.styles[name];st.font.name='Times New Roman';st.font.size=Pt(pts);st.font.bold=True;st.font.color.rgb=color
    st.paragraph_format.space_before=Pt(12 if name=='Heading 1' else 7)
    st.paragraph_format.space_after=Pt(5)
    st.paragraph_format.keep_with_next=True
for name in ('Caption','Table Note'):
    if name not in doc.styles: doc.styles.add_style(name,WD_STYLE_TYPE.PARAGRAPH)
    s=doc.styles[name];s.font.name='Times New Roman';s.font.size=Pt(9.5);s.font.italic=True;s.font.color.rgb=RGBColor(81,91,101)
    s.paragraph_format.space_before=Pt(2);s.paragraph_format.space_after=Pt(7)
# header/footer
hdr=sec.header.paragraphs[0];hdr.alignment=WD_ALIGN_PARAGRAPH.RIGHT
hr=hdr.add_run('BÀI TẬP LỚN ĐÁNH GIÁ HIỆU NĂNG MẠNG  |  YeAH-TCP');hr.font.size=Pt(8);hr.font.color.rgb=RGBColor(95,107,116)
footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
fr=footer.add_run('Bản nháp J1 – Số liệu H1–H4 đã kiểm toán  |  Trang ');fr.font.size=Pt(9)
fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');footer._p.append(fld)

def p(text='', style=None, bold_begin=None):
    paragraph=doc.add_paragraph(style=style)
    if bold_begin and text.startswith(bold_begin):
        paragraph.add_run(bold_begin).bold=True;paragraph.add_run(text[len(bold_begin):])
    else: paragraph.add_run(text)
    return paragraph

def heading(text,level=1): return doc.add_heading(text,level)

def bullet(text):
    par=doc.add_paragraph(style='List Bullet');par.add_run(text);return par

def add_table(headers, rows, widths=None, note=None):
    tab=doc.add_table(rows=1,cols=len(headers));tab.style='Table Grid';tab.alignment=WD_TABLE_ALIGNMENT.CENTER
    for j,h in enumerate(headers):
        c=tab.rows[0].cells[j];c.text=str(h);set_cell_shading(c,'E7EDF3');c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
        for run in c.paragraphs[0].runs:run.bold=True;run.font.size=Pt(9.2)
    no_split(tab.rows[0]);
    for row in rows:
        cells=tab.add_row().cells;no_split(tab.rows[-1])
        for j, v in enumerate(row):
            cells[j].text=str(v);cells[j].vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for par in cells[j].paragraphs:
                par.paragraph_format.space_after=Pt(1);par.paragraph_format.space_before=Pt(1)
                for run in par.runs:run.font.size=Pt(9.15)
    if note:p(note,style='Table Note')
    else:p('Nguồn: bảng CSV đã kiểm toán H1–H4; kết quả từ một lần chạy/cấu hình.',style='Table Note')
    return tab

def image(path, caption, width=15.3):
    path=FIGS/path
    par=doc.add_paragraph();par.alignment=WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.space_before=Pt(7);par.paragraph_format.space_after=Pt(2)
    par.add_run().add_picture(str(path),width=Cm(width))
    cp=doc.add_paragraph(style='Caption');cp.alignment=WD_ALIGN_PARAGRAPH.CENTER;cp.add_run(caption)

# COVER
p1=doc.add_paragraph();p1.alignment=WD_ALIGN_PARAGRAPH.CENTER;p1.paragraph_format.space_before=Pt(29)
r=p1.add_run('ĐẠI HỌC QUỐC GIA HÀ NỘI\nTRƯỜNG ĐẠI HỌC CÔNG NGHỆ');r.bold=True;r.font.size=Pt(14)
doc.add_paragraph('\n')
p2=doc.add_paragraph();p2.alignment=WD_ALIGN_PARAGRAPH.CENTER;p2.paragraph_format.space_before=Pt(55)
r=p2.add_run('BÁO CÁO BÀI TẬP LỚN\nĐÁNH GIÁ HIỆU NĂNG MẠNG');r.bold=True;r.font.size=Pt(19);r.font.color.rgb=RGBColor(22,50,78)
p3=doc.add_paragraph();p3.alignment=WD_ALIGN_PARAGRAPH.CENTER;p3.paragraph_format.space_before=Pt(26)
r=p3.add_run('TÁI HIỆN VÀ ĐÁNH GIÁ THỰC NGHIỆM\nYE AH-TCP TRÊN NS-3.44'.replace('YE AH','YeAH'));r.bold=True;r.font.size=Pt(16)
p4=doc.add_paragraph();p4.alignment=WD_ALIGN_PARAGRAPH.CENTER
r=p4.add_run('Theo bài báo: “YeAH-TCP: Yet Another Highspeed TCP” (2007)');r.italic=True;r.font.size=Pt(11)
doc.add_paragraph('\n\n')
for text in ['Sinh viên thực hiện: [BỔ SUNG HỌ VÀ TÊN]','Mã sinh viên: [BỔ SUNG MÃ SỐ]','Lớp học phần: [BỔ SUNG]','Giảng viên: [XÁC NHẬN NẾU CẦN]']:
    par=doc.add_paragraph();par.paragraph_format.left_indent=Cm(3.6);par.add_run(text)
doc.add_paragraph('\n\n')
p5=doc.add_paragraph();p5.alignment=WD_ALIGN_PARAGRAPH.CENTER;p5.add_run('HÀ NỘI, THÁNG 11 NĂM 2026')
doc.add_page_break()

# Abstract / methodology and contents
heading('MỤC LỤC',1)
for title in ['1. Xác định ý tưởng chính của bài báo','2. Cải tiến và mô hình YeAH-TCP','3. Cài đặt mô hình trên NS-3.44','4. Kiểm tra tính đúng đắn và khả năng tái lập','5. Kịch bản và kết quả thí nghiệm','6. Đối chiếu paper, nhận xét và kết luận','Tài liệu tham khảo','Phụ lục – Hướng dẫn tái lập']:
    p(title)
p('Lưu ý: cập nhật mục lục và số trang trong Microsoft Word sau khi điền thông tin bìa và chốt bản cuối.',style='Table Note')
heading('Phạm vi và nguyên tắc sử dụng dữ liệu',2)
p('Báo cáo sử dụng 32 lượt mô phỏng NS-3.44 thuộc H1–H4, mỗi lượt 600 giây, seed=1/run=1. Dữ liệu gốc đã được kiểm toán; các bảng và hình được tạo bằng script Python đọc từ CSV. Đây là phép tái hiện có chọn lọc trên bộ mô phỏng, không phải bản sao hoàn toàn testbed Linux vật lý của bài báo [1].')
p('Số liệu chính xác từ paper chỉ được lấy từ Table I. Đối với các Figure 1, 3, 5, 6 và 7, báo cáo chỉ đối chiếu phạm vi và xu hướng, không số hóa tùy tiện các điểm trên đường cong.')

heading('1. Xác định ý tưởng chính của bài báo')
heading('1.1. Bối cảnh và vấn đề nghiên cứu',2)
p('Trong mạng có tích băng thông–độ trễ (Bandwidth–Delay Product, BDP) lớn, TCP cần duy trì một lượng lớn dữ liệu đang truyền để khai thác hết dung lượng liên kết. Đối với TCP Reno, quy tắc tăng cửa sổ tắc nghẽn xấp xỉ một segment mỗi RTT trong Congestion Avoidance làm tốc độ tăng cwnd chậm; khi phát hiện mất gói, phản ứng giảm cửa sổ mạnh có thể làm giảm hiệu quả sử dụng liên kết. Các biến thể TCP tốc độ cao tăng cwnd mạnh hơn, nhưng có thể tạo hàng đợi lớn và ảnh hưởng đến lưu lượng chia sẻ nút nghẽn [1].')
p('BDP (bit) = C (bit/s) × RTT (s). Trong bài báo, hiệu quả sử dụng đường truyền không phải mục tiêu duy nhất; tác giả còn đánh giá độ dài hàng đợi, mất gói, tính công bằng giữa luồng và khả năng hoạt động với buffer nhỏ hoặc mất gói không do tắc nghẽn.')
heading('1.2. Ý tưởng cốt lõi của YeAH-TCP',2)
p('YeAH-TCP (Yet Another Highspeed TCP) kết hợp cơ chế ước lượng tắc nghẽn dựa trên độ trễ RTT với phản ứng khi mất gói. Thuật toán sử dụng hai chế độ: Fast Mode tăng cwnd theo Scalable TCP (STCP), còn Slow Mode tăng theo Reno. Sự chuyển chế độ dựa trên ước lượng lượng dữ liệu tại hàng đợi và mức tăng RTT. Thuật toán cũng có cơ chế giảm tải chủ động (precautionary decongestion) nhằm hạn chế việc duy trì hàng đợi lớn [1].')
p('Sáu mục tiêu trong bài báo gồm: (1) khai thác băng thông lớn, (2) hạn chế gây áp lực cho router, (3) thân thiện với Reno, (4) công bằng giữa các luồng và với RTT không đồng đều, (5) chịu được mất gói ngẫu nhiên, (6) vẫn hoạt động tốt khi buffer nhỏ.')

heading('2. Cải tiến và mô hình YeAH-TCP')
heading('2.1. Các đại lượng điều khiển',2)
p('Ký hiệu RTTbase là RTT nhỏ nhất từng quan sát và RTTmin là RTT nhỏ nhất trong chu kỳ đo hiện tại. Theo cơ chế của YeAH [1]:')
for formula in ['RTTqueue = RTTmin − RTTbase','Q ≈ cwnd × RTTqueue / RTTmin','L = RTTqueue / RTTbase']:
    pp=doc.add_paragraph();pp.alignment=WD_ALIGN_PARAGRAPH.CENTER;pp.add_run(formula).bold=True
p('Ở đây cwnd được hiểu theo số segment; Q là số segment xếp hàng do đầu gửi ước lượng từ RTT, không phải phép đo trực tiếp hàng đợi tại router. Hàng đợi thực tế trong NS-3 được đọc độc lập từ thiết bị tại bottleneck.')
heading('2.2. Quy tắc vận hành',2)
bullet('Fast Mode: tăng cửa sổ theo quy tắc Scalable TCP để nhanh chóng tận dụng dung lượng khi tín hiệu tắc nghẽn thấp.')
bullet('Slow Mode: sử dụng cơ chế tăng cửa sổ của NewReno để giảm mức độ thăm dò khi có dấu hiệu tăng hàng đợi hoặc độ trễ.')
bullet('Precautionary decongestion: chủ động điều chỉnh cửa sổ trong một số điều kiện hàng đợi lớn, không nhất thiết chờ sự kiện mất gói.')
bullet('Xử lý mất gói: mức giảm cửa sổ phụ thuộc tình trạng cạnh tranh được thuật toán suy đoán, với bảo vệ về mức giảm tối thiểu/tối đa.')
heading('2.3. Đối chiếu cơ chế paper với NS-3.44',2)
add_table(['Cơ chế','Điểm trong mã NS-3.44','Nội dung cần kiểm chứng'],[
('Thu thập RTT','TcpYeah::PktsAcked','RTTbase, RTTmin, số mẫu RTT'),
('Q và L','TcpYeah::IncreaseWindow','Ước lượng nghẽn và chọn Fast/Slow'),
('Tăng cwnd nhanh','TcpScalable::IncreaseWindow','Đường tăng STCP'),
('Tăng cwnd chậm','TcpNewReno::CongestionAvoidance','Nhánh Slow Mode'),
('Giảm khi mất gói','TcpYeah::GetSsThresh','Căn cứ bytesInFlight và m_lastQ'),
],note='Nguồn: source TcpYeah của NS-3.44 đã thu thập và đối chiếu ở bước E; không chỉnh sửa implementation upstream.')
p('Một chi tiết đáng lưu ý ở source NS-3.44: biểu thức “1 / m_phy” thực hiện phép chia nguyên khi m_phy là số nguyên (giá trị mặc định 8), dẫn tới ngưỡng bằng 0 thay vì 1/8 theo số thực. Đây là khác biệt implementation có thể ảnh hưởng chuyển chế độ, nhưng báo cáo này chưa có thử nghiệm cô lập ảnh hưởng của riêng chi tiết đó. Không khẳng định đây là nguyên nhân đã được chứng minh của các chênh lệch với paper.')

heading('3. Cài đặt mô hình trên NS-3.44')
heading('3.1. Môi trường và cấu trúc mạng',2)
p('Mô phỏng sử dụng NS-3.44 (Git commit 43dce6710b8df69685e3479c1d33a571dda714ea), Ubuntu 24.04 trong WSL2, build profile optimized. Mô hình có bốn node: hai sender, một router và một receiver; hai đường access 1 Gbps nối tới router, đường chung từ router đến receiver là bottleneck 500 Mbps. Các sender không nối trực tiếp với bottleneck, phù hợp tinh thần bố trí testbed paper [1].')
add_table(['Thành phần','Thiết lập được xác nhận'],[
('Bottleneck','500 Mbps, link point-to-point, propagation one-way 1 ms'),
('Hai access link','1 Gbps, trễ được cấu hình từ RTT mục tiêu'),
('Đóng gói và TCP','MTU 1500 bytes, MSS 1448 bytes, TCP timestamps/SACK'),
('Hàng đợi','FIFO DropTail tại bottleneck; một queue đo trực tiếp'),
('Ứng dụng','BulkSendApplication → PacketSink, hai luồng TCP'),
('Buffer','⌊β × C × min(RTT1,RTT2)/(8 × 1500)⌋ gói'),
('Mất gói ngẫu nhiên','RateErrorModel, đơn vị per-packet tại giao diện nhận bottleneck'),
('Thu thập dữ liệu','Mẫu mỗi 10 ms; 60.001 mẫu trong 600 s'),
('Lặp thực nghiệm','1 lượt/cấu hình (seed=1, run=1)'),
],note='Đọc từ simulation/yeah-experiment.cc và các bảng I1/I2 đã kiểm toán; dấu ⌊ ⌋ chỉ lấy phần nguyên xuống.')
heading('3.2. Các file chương trình và đường đi dữ liệu',2)
for text in ['simulation/yeah-experiment.cc: xây dựng topology, chọn TCP từng sender, kết nối trace và xuất CSV.','scripts/run_H1.py … run_H4.py: thực thi ma trận tham số, lưu log, cấu hình và hash theo lượt.','results/raw/experiments/h1…h4/: summary.csv, timeseries.csv, config và thông tin trạng thái.','scripts/analyze_H1.py … analyze_H4.py: tính lại chỉ số, đối chiếu hash, tạo bảng và 20 cặp hình PNG/SVG.','scripts/audit_I1.py: kiểm toán chung; scripts/compare_I2.py: đối chiếu với Table I và các Figure của paper.']:
    bullet(text)
p('Mã SHA-256 chương trình mô phỏng sử dụng cho 32 lượt chạy: '+source_hash+'. Tất cả bảng chính trong báo cáo sử dụng CSV đã xác nhận thay vì nhập dữ liệu đo thủ công.')
heading('3.3. Các độ đo',2)
for formula in ['Goodput_i (Mbps) = 8 × bytes_received_i / (duration × 10⁶)','Wire utilization = 8 × bytes_bottleneck_tx / (C × duration)','Normalized queue = mean(queue_packets) / buffer_packets','Jain = (x₁ + x₂)² / [2(x₁² + x₂²)]','Overflow probability (NS-3) = drop_count / (enqueue_count + drop_count)']:
    pp=doc.add_paragraph();pp.paragraph_format.left_indent=Cm(.6);pp.add_run(formula)
p('Goodput tính theo byte ứng dụng nhận được, trong khi wire utilization tính trên byte bắt đầu truyền qua bottleneck, gồm overhead/ảnh hưởng truyền lại. Queue tại router và Q do YeAH ước lượng không được đồng nhất. Với T0, chỉ số Jain toàn 600 giây không phù hợp để đánh giá công bằng lúc hai luồng đồng thời hoạt động.')

heading('4. Kiểm tra tính đúng đắn và khả năng tái lập')
heading('4.1. Kiểm tra thuật toán và mô hình',2)
p('Bộ kiểm thử upstream tcp-yeah-test của NS-3.44 đã báo PASS. Pilot F xác nhận chương trình tạo CSV và trace; G1 chạy lại cùng mã nguồn, seed và cấu hình cho file summary/timeseries trùng từng byte; G2 xác nhận lựa chọn hỗn hợp YeAH/NewReno, CUBIC với RTT khác nhau và khả năng đếm random drops; G3 kiểm tra diễn biến thời gian và thời lượng dài; G4 đối chiếu build default/optimized ở các kịch bản được chọn. Các kết quả này chứng minh tính nhất quán ở phạm vi đã thử, không phải chứng minh mô hình tương đương paper trong mọi điều kiện.')
heading('4.2. Kiểm toán 32 lượt mô phỏng chính thức',2)
add_table(['Tiêu chí','Kết quả đã kiểm toán'],[
('Tập kịch bản','H1: 8, H2: 8, H3: 8, H4: 8 (tổng 32)'),
('Độ dài trace','60.001 mẫu/lượt; tổng 1.920.032 dòng dữ liệu'),
('Hash CSV gốc','64/64 file summary/timeseries khớp trạng thái đã ghi'),
('Hash mã nguồn','32/32 lượt trùng mã nguồn C++ đã khóa'),
('Tính lại chỉ số','Goodput, wire utilization, queue, drops, Jain: đạt'),
('Tái tạo bảng','12/12 CSV tổng hợp khớp từng byte'),
('Hình kết quả','20 PNG và 20 SVG, tạo bởi script phân tích'),
('I1 và I2 trên WSL','Cả hai lệnh kiểm chứng đã trả về VERIFIED'),
],note='Nguồn: log chạy analyze_H1–H4, audit_I1.py và compare_I2.py trên WSL; I1/I2 đã được xác nhận trong cuộc trao đổi.')
p('Việc ảnh PNG không trùng hash giữa hai môi trường không được xem là bằng chứng đổi dữ liệu; tiêu chí kiểm toán là nguồn CSV, công thức và script tạo hình. Dữ liệu gốc không bị sửa để làm khớp hình paper.')

heading('5. Test thí nghiệm trên các kịch bản và thu kết quả')
heading('5.1. Ma trận kịch bản',2)
add_table(['Nhóm','Mục tiêu','Biến số chính','Số lượt'],[
('H1 / T0','Luồng đến/rời mạng','Luồng 2 bắt đầu 60 s, dừng ứng dụng 400 s','2'),
('H1 / T1','Ảnh hưởng RTT','RTT1=RTT2=15, 60, 240 ms','6'),
('H2 / T2','Ảnh hưởng buffer','β = 0,125; 0,25; 0,5; 1,0','8'),
('H3 / T3','Tính công bằng theo RTT','RTT2/RTT1 = 1, 2, 3, 4','8'),
('H4 / T4','Mất gói ngẫu nhiên','p = 10⁻⁸, 10⁻⁶, 10⁻⁵, 10⁻⁴','8'),
],note='32 lượt, mỗi lượt 600 giây; tất cả dùng bottleneck 500 Mbps, build optimized, seed=1/run=1. Không có nhóm H5.')
heading('5.2. T0 – Luồng TCP tham gia và rời mạng',2)
p('Hai luồng được kiểm tra ở RTT 80/80 ms, buffer bằng 100% BDP. Luồng 1 chạy từ 0 đến 600 giây; ứng dụng luồng 2 bắt đầu ở giây 60 và được yêu cầu dừng ở giây 400. Vì TCP có buffer gửi, thời điểm hết dữ liệu nhận tại đích có thể trễ hơn thời điểm dừng ứng dụng. Do đó không được hiểu các đường cwnd/queue như phản ứng tức thời chính xác tại giây 400.')
image('h1/t0-yeah-reno_cwnd.png','Hình 1. Cwnd của YeAH và NewReno trong kịch bản có luồng đến/rời. Nguồn: analyze_H1.py từ T0.',14.6)
image('h1/t0-yeah-reno_queue.png','Hình 2. Hàng đợi bottleneck trong kịch bản YeAH–NewReno. Nguồn: analyze_H1.py từ T0.',14.6)
p('Kịch bản T0 nhằm quan sát động học, không đánh giá công bằng bằng chỉ số Jain tổng hợp trên toàn 600 giây bởi hai luồng không có cùng thời gian hoạt động.')
heading('5.3. T1 – Ảnh hưởng RTT',2)
rt_rows=[]
for rtt in (15,60,240):
    y=byid[f't1-yeah-rtt{rtt}'];r=byid[f't1-reno-rtt{rtt}']
    rt_rows.append([str(rtt), fmt(n(y,'total_goodput_mbps')), fmt(n(r,'total_goodput_mbps')), fmt(n(y,'queue_over_buffer_pct')), fmt(n(r,'queue_over_buffer_pct')),str(int(n(y,'overflow_drops'))),str(int(n(r,'overflow_drops')))])
add_table(['RTT (ms)','Goodput YeAH','Goodput Reno','Queue Y (%)','Queue R (%)','Drop Y','Drop R'],rt_rows,note='Đơn vị goodput: Mbps; Queue: % buffer; Drop: số gói tràn bottleneck. Nguồn: i2_fig3_ns3_measured.csv và I1 master.')
image('h1/t1_rtt_queue.png','Hình 3. Chiều dài hàng đợi chuẩn hóa theo RTT từ các kịch bản T1. Nguồn: analyze_H1.py.',15.1)
p('Trong ba mức RTT đo được, YeAH có queue/buffer thấp hơn NewReno. Tuy vậy, cả hai đều phát sinh tràn hàng đợi; các mức mất gói không bằng kết quả quan sát của paper. Kết quả không suy rộng cho các RTT 30, 120 và 480 ms vì chưa mô phỏng các mức đó.')
doc.add_page_break()
heading('5.4. T2 – Ảnh hưởng kích thước buffer',2)
buf_rows=[]
for beta, bid in [('12,5%','0p125'),('25%','0p25'),('50%','0p5'),('100%','1p0')]:
 y=byid[f't2-yeah-beta{bid}'];r=byid[f't2-reno-beta{bid}']
 buf_rows.append([beta, str(int(n(y,'buffer_packets'))),fmt(n(y,'total_goodput_mbps')),fmt(n(r,'total_goodput_mbps')),fmt(n(y,'queue_over_buffer_pct')),fmt(n(r,'queue_over_buffer_pct'))])
add_table(['β (% BDP)','Buffer gói','Goodput Y','Goodput R','Queue Y (%)','Queue R (%)'],buf_rows,note='RTT 80/80 ms, C=500 Mbps; goodput Mbps và Queue/%buffer; nguồn: i2_fig6_ns3_measured.csv.')
image('h2/t2_buffer_queue_normalized.png','Hình 4. Hàng đợi chuẩn hóa theo kích thước buffer. Nguồn: analyze_H2.py.',15.1)
image('h2/t2_buffer_goodput.png','Hình 5. Goodput theo kích thước buffer. Nguồn: analyze_H2.py.',15.1)
p('Ở β=0,125, YeAH có goodput cao hơn NewReno trong lượt chạy tương ứng; ở β=1,0, NewReno có goodput cao hơn trong toàn bộ 600 giây. Đường queue chuẩn hóa của YeAH tăng theo bốn mức β đã đo; điều này không tương thích với xu hướng được tác giả mô tả trong paper, cần thảo luận về khác biệt testbed và implementation.')
doc.add_page_break()
heading('5.5. T3 – Fairness theo tỷ số RTT',2)
fair=[]
for ratio in (1,2,3,4):
 y=byid[f't3-yeah-ratio{ratio}'];r=byid[f't3-reno-ratio{ratio}']
 fair.append([str(ratio),fmt(n(y,'jain_whole_duration'),6),fmt(n(r,'jain_whole_duration'),6)])
add_table(['RTT₂/RTT₁','Jain (YeAH)','Jain (NewReno)'],fair,note='Jain được tính trên goodput hai luồng trong toàn bộ 600 giây; mỗi cấu hình mới 1 lần chạy.')
image('h3/t3_rtt_ratio_fairness_0_600.png','Hình 6. Jain theo tỷ số RTT; nguồn: analyze_H3.py, khoảng 0–600 giây.',15.1)
p('YeAH có Jain cao hơn NewReno tại tỷ số 2, 3 và 4 của bộ dữ liệu này, nhưng đường Jain không giảm đơn điệu từ tỷ số 3 sang 4. Kết quả theo cửa sổ 300–600 giây còn có thể thay đổi tương quan thứ hạng, nên không kết luận một thuật toán luôn công bằng hơn trong mọi giai đoạn.')
heading('5.6. T4 – Ảnh hưởng của xác suất mất gói ngẫu nhiên',2)
loss_rows=[]
for p_val, key in [('10⁻⁸','1e-8'),('10⁻⁶','1e-6'),('10⁻⁵','1e-5'),('10⁻⁴','1e-4')]:
 y=byid[f't4-yeah-p{key}'];r=byid[f't4-reno-p{key}']
 loss_rows.append([p_val,fmt(n(y,'total_goodput_mbps')),fmt(n(r,'total_goodput_mbps')),str(int(n(y,'random_drops'))),str(int(n(r,'random_drops')))])
add_table(['p cấu hình','Goodput Y (Mbps)','Goodput R (Mbps)','Random drop Y','Random drop R'],loss_rows,note='RTT 200/200 ms, buffer 8333 gói, 600 giây; nguồn: i2_fig5_ns3_measured.csv và I1 master.')
image('h4/t4_loss_wire_utilization.png','Hình 7. Wire utilization theo xác suất lỗi cấu hình. Nguồn: analyze_H4.py.',15.1)
image('h4/t4_loss_goodput.png','Hình 8. Goodput theo xác suất lỗi cấu hình. Nguồn: analyze_H4.py.',15.1)
p('Tại p=10⁻⁸, cả hai luồng không ghi nhận random drop trong một lần chạy, không đồng nghĩa xác suất mất gói thực sự bằng 0. NewReno có goodput cao hơn YeAH tại ba mức p đầu, còn tại p=10⁻⁴ YeAH cao hơn trong một lần đo. Kết quả này không đủ để tuyên bố ý nghĩa thống kê hoặc khả năng chịu lỗi tổng quát.')

doc.add_page_break()
heading('6. Đối chiếu paper, nhận xét và kết luận')
heading('6.1. Đối chiếu định lượng với Table I',2)
rows=[]
for row in readcsv(I2/'i2_table_I_comparison.csv'):
 paper = '– (không ghi nhận)' if row['tcp']=='yeah' else f"{float(row['paper_probability_exact']):.10f}"
 rows.append([row['rtt_ms'],row['tcp'],paper,f"{float(row['ns3_overflow_probability']):.10f}",row['ns3_overflow_drops']])
add_table(['RTT (ms)','TCP','Paper: P overflow','NS-3: P overflow','NS-3: số gói'],rows,note='Paper: Table I [1], giá trị Reno công bố chính xác; dấu “–” là không quan sát thấy gói tràn. NS-3: số liệu CSV đã kiểm toán theo công thức drop/(enqueue+drop); mẫu số giữa hai nghiên cứu chưa được chứng minh đồng nhất.')
p('Điểm khác biệt đáng chú ý: YeAH không được paper ghi nhận tràn buffer trong các thử nghiệm Table I, còn NS-3 của chúng ta lần lượt ghi nhận 412, 1968 và 6581 drop ở RTT 15, 60 và 240 ms. Không tính “% sai lệch” từ dấu gạch ngang, không coi dấu đó là một xác suất đúng bằng 0; cũng không so trực tiếp số đếm với xác suất paper.')
heading('6.2. Đối chiếu theo Figure',2)
add_table(['Hình paper','Phạm vi tái hiện NS-3','Mức đối chiếu có căn cứ'],[
('Figure 1','T0: hai luồng, join 60 s, app stop 400 s','Diễn biến cwnd và queue định tính; không khẳng định match điểm-điểm.'),
('Figure 3','T1: RTT 15, 60, 240 ms','YeAH queue/buffer thấp hơn Reno tại cả ba RTT đo được.'),
('Figure 5','T4: p=10⁻⁸,10⁻⁶,10⁻⁵,10⁻⁴','YeAH có utilization > Reno chỉ tại 10⁻⁴ trong bốn mức đo.'),
('Figure 6','T2: β=0,125–1,0','Xu hướng YeAH queue/%buffer tăng tại 4 điểm, không giống mô tả paper.'),
('Figure 7','T3: RTT ratio 1–4','YeAH Jain cao hơn Reno tại 2, 3, 4; không suy rộng thống kê.'),
],note='Các Figure paper không có bảng dữ liệu số chính xác đi kèm trong tài liệu được dùng; không nội suy các điểm của đường paper từ ảnh.')
heading('6.3. Nguyên nhân khả dĩ của khác biệt và giới hạn',2)
for t in [
 'Khác biệt nền tảng: paper dùng Linux kernel/testbed vật lý, trong khi chương trình dùng mô phỏng NS-3.44 và implementation TcpYeah tích hợp sẵn.',
 'Khác biệt điều kiện: paper mô tả web cross traffic SURGE trung bình 4 Mbps và Limited Slow Start trong testbed; hai cơ chế đó chưa được tái hiện trong chương trình.',
 'Khác biệt thiết lập TCP: chương trình dùng MSS 1448 byte với IPv4/TCP timestamps, initial cwnd 10 segment và ssthresh không giới hạn; paper mô tả packet data 1500 byte và thiết lập kernel khác.',
 'Khác biệt định nghĩa đo: mẫu số xác suất overflow và thời điểm ghi nhận packet/queue giữa paper với NS-3 chưa được chứng minh giống nhau.',
 'Khác biệt implementation: nhánh điều kiện “1 / m_phy” trong TcpYeah NS-3.44 là phép chia nguyên; chưa có đối chứng sửa riêng biểu thức này nên không thể khẳng định nhân quả.',
 'Giới hạn thống kê và phạm vi: 1 run cho mỗi cấu hình, không có phương sai/khoảng tin cậy; chỉ khảo sát lựa chọn các điểm của Figure 1, 3, 5, 6, 7. Không tái hiện Figure 4 hoặc Figure 8 đầy đủ.'
]: bullet(t)
p('Các mục trên là giải thích có căn cứ về điều kiện không đồng nhất hoặc giả thuyết cần kiểm tra thêm, không phải bằng chứng đã phân rã định lượng đóng góp của từng nguyên nhân.')
heading('6.4. Kết luận',2)
p('Bài tập đã xây dựng được mô hình bottleneck hai luồng trên NS-3.44, thực thi 32 lượt mô phỏng 600 giây và kiểm toán lại toàn bộ dữ liệu cùng các bảng, hình bằng script. Kết quả chứng minh có thể tái lập quy trình xử lý và cho thấy một số xu hướng tương đồng với paper (đặc biệt là mức chiếm dụng hàng đợi YeAH ở nhóm RTT đã đo), nhưng cũng có khác biệt đáng kể về tràn buffer, tác động buffer và mất gói ngẫu nhiên.')
p('Vì không tái hiện toàn bộ testbed vật lý và chỉ có một lần chạy mỗi cấu hình, nghiên cứu không tuyên bố xác nhận toàn diện các kết quả công bố năm 2007. Giá trị chính của BTL là một quy trình mô phỏng minh bạch, dữ liệu kiểm chứng được, và phân tích trung thực các điểm phù hợp, không phù hợp và giới hạn.')

heading('TÀI LIỆU THAM KHẢO')
p('[1] A. Baiocchi, A. P. Castellani, F. Vacirca, “YeAH-TCP: Yet Another Highspeed TCP,” PFLDnet, 2007.')
p('[2] NS-3 Consortium, ns-3.44 source code: src/internet/model/tcp-yeah.{cc,h}, tcp-scalable.cc, tcp-congestion-ops.cc, tcp-yeah-test.cc (Git commit 43dce6710b8df69685e3479c1d33a571dda714ea).')
p('[3] Báo cáo thực nghiệm nội bộ: các gói raw H1–H4 và bản nhật ký thực nghiệm v14, kết quả I1/I2 tái tạo trên Ubuntu 24.04 WSL2 (20/11/2026).')
heading('PHỤ LỤC – HƯỚNG DẪN TÁI LẬP')
p('Trong thư mục dự án YeAH-TCP-NPE, có các dữ liệu raw, bảng I1/I2, mã nguồn C++, script thực nghiệm và phân tích. Trên máy đã cài NS-3.44 và dependencies, sử dụng các lệnh:')
for command in ['python3 scripts/analyze_H1.py','python3 scripts/analyze_H2.py','python3 scripts/analyze_H3.py','python3 scripts/analyze_H4.py','python3 scripts/audit_I1.py','python3 scripts/compare_I2.py','python3 scripts/generate_report_J1.py']:
  par=doc.add_paragraph();par.paragraph_format.left_indent=Cm(.4);run=par.add_run(command);run.font.name='Consolas';run.font.size=Pt(9)
p('Khi làm hồ sơ nộp, cần giữ đúng phiên bản source và các script, kèm README mô tả cách đặt chương trình vào scratch/ của NS-3. Bản báo cáo sẽ cần bổ sung họ tên, mã sinh viên, số trang mục lục và soát lần cuối trước khi xuất PDF.')

OUT.parent.mkdir(parents=True,exist_ok=True)
doc.save(OUT)
print('REPORT:',OUT)
print('SOURCE_SHA256:',source_hash)
print('SCENARIOS:',len(master),'TOTAL_SAMPLES:',sum(int(float(x['sample_count'])) for x in master))
