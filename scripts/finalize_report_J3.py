#!/usr/bin/env python3
"""J3: presentation-only finalization of the VERIFIED J2.3 Word.

This script never writes to simulation/, results/raw/, results/summary/ or
results/figures/. It verifies the locked simulator source and 64 raw hashes,
then updates the COVER and TABLE OF CONTENTS only. Scientific content, all
10 tables and the 8 embedded experiment images are byte-preserved.

Run from anywhere: python3 scripts/finalize_report_J3.py
Optional: --student-name, --student-id, --class-name, --lecturer
It does NOT invent missing personal information.
"""
from __future__ import annotations
import argparse, csv, hashlib
from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Pt, Cm
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/'report/Bao_cao_YeAH_TCP_J2_3.docx'
SIM=ROOT/'simulation/yeah-experiment.cc'
MASTER=ROOT/'results/summary/i1/i1_master_summary.csv'
RAW=ROOT/'results/raw/experiments'
LOCKED='460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
for p in (INPUT,SIM,MASTER):
    if not p.is_file(): raise SystemExit(f'MISSING INPUT: {p}')
if sha(SIM)!=LOCKED: raise SystemExit('STOP: source hash differs from 32 locked experiments')
with MASTER.open(encoding='utf-8-sig',newline='') as f: items=list(csv.DictReader(f))
if len(items)!=32 or len({r['id'] for r in items})!=32: raise SystemExit('STOP: expected 32 unique scenarios')
for r in items:
    if r['source_sha256']!=LOCKED or int(r['sample_count'])!=60001: raise SystemExit('STOP: source/sample mismatch: '+r['id'])
    for name,col in [('summary.csv','summary_sha256'),('timeseries.csv','timeseries_sha256')]:
        file=RAW/r['batch'].lower()/r['id']/name
        if not file.is_file() or sha(file)!=r[col]: raise SystemExit('STOP: raw hash mismatch: '+str(file))

ap=argparse.ArgumentParser()
for name in ('student-name','student-id','class-name','lecturer'):
    ap.add_argument('--'+name,default=None)
args=ap.parse_args()
metadata={'student-name': args.student_name,'student-id':args.student_id,'class-name':args.class_name,'lecturer':args.lecturer}

D=Document(INPUT)
original_tables=[[tuple(c.text for c in row.cells) for row in t.rows] for t in D.tables]
original_images=sorted([hashlib.sha256(p.blob).hexdigest() for p in D.part.related_parts.values() if p.content_type.startswith('image/')])
# Invariant: science starts at the first numbered Heading 1.
science_start=[i for i,p in enumerate(D.paragraphs) if p.style.name=='Heading 1' and p.text.startswith('1. Xác định')]
if len(science_start)!=1: raise SystemExit('STOP: unexpected J2.3 structure')
science=[(p.text,p.style.name) for p in D.paragraphs[science_start[0]:]]

cover={6:('Sinh viên thực hiện: ','student-name'), 7:('Mã sinh viên: ','student-id'), 8:('Lớp học phần: ','class-name'), 9:('Giảng viên: ','lecturer')}
for idx,(prefix,key) in cover.items():
    old=D.paragraphs[idx]
    if not old.text.startswith(prefix): raise SystemExit('STOP: unexpected cover line: '+str(idx))
    val=metadata[key]
    if val is not None and not val.strip(): raise SystemExit('STOP: invalid empty '+key)
    if val is not None:
        # Make sure user data is supplied explicitly; do not invent.
        if len(old.runs)==1:old.runs[0].text=prefix+val.strip()
        else:old.text=prefix+val.strip()

# Format table of contents: do NOT change scientific report content.
toc_title=D.paragraphs[13]
if toc_title.text.strip()!='MỤC LỤC': raise SystemExit('STOP: expected TOC heading')
toc_title.style='Title' # removes it from future automatic Heading 1 tables
for idx in range(14,23):
    if idx>=len(D.paragraphs): raise SystemExit('STOP: missing TOC old entries')
entries=D.paragraphs[14:23]
if not D.paragraphs[14].text.startswith('1. Xác định') or not D.paragraphs[22].text.startswith('Lưu ý:'):
    raise SystemExit('STOP: unexpected TOC entries')
# Put eight visible TOC entries with Word PAGEREF fields pointing to section
# bookmarks. Their cached values are populated after a layout verification.
# A final Word Ctrl+A -> F9 recalculates page numbers when the cover changes.
entries_main = [
    ('1. Xác định ý tưởng chính của bài báo', 'toc_section1'),
    ('2. Cải tiến và mô hình YeAH-TCP', 'toc_section2'),
    ('3. Cài đặt mô hình trên NS-3.44', 'toc_section3'),
    ('4. Kiểm tra tính đúng đắn và khả năng tái lập', 'toc_section4'),
    ('5. Test thí nghiệm trên các kịch bản và thu kết quả', 'toc_section5'),
    ('6. Đối chiếu paper, nhận xét và kết luận', 'toc_section6'),
    ('TÀI LIỆU THAM KHẢO', 'toc_references'),
    ('PHỤ LỤC – HƯỚNG DẪN TÁI LẬP', 'toc_appendix'),
]
from docx.enum.text import WD_TAB_ALIGNMENT, WD_TAB_LEADER
for number, (title, bookmark) in enumerate(entries_main, 101):
    heading = [x for x in D.paragraphs if x.text.strip() == title and x.style.name == 'Heading 1']
    if len(heading)!=1: raise SystemExit('STOP: missing or duplicate body heading: '+title)
    el = heading[0]._p
    start = OxmlElement('w:bookmarkStart')
    start.set(qn('w:id'),str(number))
    start.set(qn('w:name'),bookmark)
    end = OxmlElement('w:bookmarkEnd')
    end.set(qn('w:id'),str(number))
    el.insert(0,start)
    el.append(end)
for i, (title, bookmark) in enumerate(entries_main):
    pp=entries[i]
    pp.clear()
    pp.style='Normal'
    pp.paragraph_format.space_after=Pt(5)
    pp.paragraph_format.tab_stops.add_tab_stop(Cm(16), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
    pp.add_run(title)
    pp.add_run('\t')
    # A true PAGEREF field with cached page label, initially '00'.
    r=OxmlElement('w:r');x=OxmlElement('w:fldChar');x.set(qn('w:fldCharType'),'begin');r.append(x);pp._p.append(r)
    r=OxmlElement('w:r');x=OxmlElement('w:instrText');x.set(qn('xml:space'),'preserve');x.text=f' PAGEREF {bookmark} \\h ';r.append(x);pp._p.append(r)
    r=OxmlElement('w:r');x=OxmlElement('w:fldChar');x.set(qn('w:fldCharType'),'separate');r.append(x);pp._p.append(r)
    r=OxmlElement('w:r');x=OxmlElement('w:t');x.text='00';r.append(x);pp._p.append(r)
    r=OxmlElement('w:r');x=OxmlElement('w:fldChar');x.set(qn('w:fldCharType'),'end');r.append(x);pp._p.append(r)
# Old note was a drafting instruction, not scientific content: remove it.
entries[8]._p.getparent().remove(entries[8]._p)
# A separate TOC page is more readable; the body starts on the following page.
scope=[p for p in D.paragraphs if p.text=='Phạm vi và nguyên tắc sử dụng dữ liệu']
if len(scope)!=1:raise SystemExit('STOP: missing scope heading')
scope[0].paragraph_format.page_break_before=True
settings=D.settings._element
update=settings.find(qn('w:updateFields'))
if update is None:
    update=OxmlElement('w:updateFields');settings.append(update)
update.set(qn('w:val'),'true')
# Only presentation metadata: describe as candidate, not final ready.
D.sections[0].different_first_page_header_footer=True
for paragraph in D.sections[0].footer.paragraphs:
    for run in paragraph.runs:
        if 'Bản rà soát J2.3' in run.text:
            run.text=run.text.replace('Bản rà soát J2.3 – Số liệu H1–H4 đã kiểm toán','YeAH-TCP / NS-3.44')

# Audit invariant: all content from the first scientific Heading onwards, tables, and images.
newstart=[i for i,p in enumerate(D.paragraphs) if p.style.name=='Heading 1' and p.text.startswith('1. Xác định')]
if len(newstart)!=1 or science != [(p.text,p.style.name) for p in D.paragraphs[newstart[0]:]]:
    raise SystemExit('STOP: scientific body changed')
if original_tables != [[tuple(c.text for c in row.cells) for row in t.rows] for t in D.tables]:
    raise SystemExit('STOP: tables changed')
images=sorted([hashlib.sha256(p.blob).hexdigest() for p in D.part.related_parts.values() if p.content_type.startswith('image/')])
if images!=original_images:raise SystemExit('STOP: embedded images changed')
if len(D.tables)!=10 or len(images)!=8:raise SystemExit('STOP: tables/image count changed')
missing=[k for k,v in metadata.items() if v is None]
name='Bao_cao_YeAH_TCP_J3_DU_THAO.docx' if missing else 'Bao_cao_YeAH_TCP_J3_DA_DIEN_BIA.docx'
out=ROOT/'report'/name
out.parent.mkdir(parents=True,exist_ok=True)
if out.exists():
    raise SystemExit('STOP: output already exists; preserve your edits by renaming or archiving the existing J3 first: '+str(out))
D.save(out)
print('REPORT:',out)
print('SOURCE_SHA256:',LOCKED)
print('VERIFIED J3: 32 runs, 64 raw CSV hashes; science unchanged; 10 tables and 8 images identical')
print('TOC: 8 PAGEREF entries; update in Microsoft Word using Ctrl+A then F9')
if missing: print('NOT READY FOR SUBMISSION: missing cover metadata',','.join(missing))
else: print('COVER FIELDS: provided explicitly; still requires final visual and submission review')
