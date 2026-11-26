"""Dựng báo cáo Word từ nội dung trong content*.py.

    python nguon/build.py BaoCao_CloudShop_AutoScaling_AWS.docx   (chạy trong docs/bao_cao)
Sau đó mở bằng Word để cập nhật mục lục: powershell -File nguon/cap_nhat_muc_luc.ps1 <đường dẫn docx> <đường dẫn pdf>
"""
import os as _os; _os.chdir(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # chạy từ thư mục docs/bao_cao
import re, os, sys, copy
from PIL import Image
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.opc.constants import RELATIONSHIP_TYPE as RT

from content_refs import REFS
from content1 import MEMBERS, TASKS, ABBR, THANKS, INTRO, CH1
from content2 import CH2
from content3 import CH3

OUT = sys.argv[1]
TMP = "nguon/_tmp"; os.makedirs(TMP, exist_ok=True)
FONT = "Times New Roman"
BLUE = RGBColor(0x1F, 0x4E, 0x9A)
LINKBLUE = RGBColor(0x05, 0x63, 0xC1)
HEAD_FILL = "C5E0B3"
LOGO = "nguon/logo_ictu.png"

# ---------- đánh số trước: trích dẫn, hình, bảng ----------
ALL = INTRO + CH1 + CH2 + CH3
cite_order = []
def scan_text(t):
    for m in re.finditer(r"\[@([^\]]+)\]", t):
        for k in re.split(r";\s*", m.group(1)):
            k = k.strip().lstrip("@")
            if k not in REFS: raise SystemExit("thiếu tài liệu: " + k)
            if k not in cite_order: cite_order.append(k)
def walk_texts(b):
    kind = b[0]
    if kind in ("p", "h2", "h3", "code"): yield b[1]
    elif kind in ("bullets", "num"): yield from b[1]
    elif kind == "table":
        for row in b[3]: yield from row
labels = {}
chap = 0; nf = {}; nt = {}
for b in ALL:
    for t in walk_texts(b): scan_text(t)
    if b[0] == "chapter": chap += 1
    if b[0] == "fig":
        nf[chap] = nf.get(chap, 0) + 1
        opt = b[4] if len(b) > 4 else {}
        if opt.get("label"): labels["fig:" + opt["label"]] = (f"Hình {chap}.{nf[chap]}", "fig_" + opt["label"])
    if b[0] == "table":
        nt[chap] = nt.get(chap, 0) + 1
        if len(b) > 5 and b[5]: labels["tab:" + b[5]] = (f"Bảng {chap}.{nt[chap]}", "tab_" + b[5])
REFNUM = {k: i + 1 for i, k in enumerate(cite_order)}
unused = [k for k in REFS if k not in REFNUM]
if unused: print("Tài liệu chưa được trích dẫn (sẽ bỏ):", unused)

# ---------- tiện ích XML ----------
_bm = [100]
def set_cell_shading(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), fill); tcPr.append(shd)
def set_run_font(run, size=None, bold=None, italic=None, color=None, name=FONT):
    run.font.name = name
    rpr = run._element.get_or_add_rPr(); rf = rpr.find(qn("w:rFonts"))
    if rf is None: rf = OxmlElement("w:rFonts"); rpr.insert(0, rf)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"): rf.set(qn(a), name)
    if size: run.font.size = Pt(size)
    if bold is not None: run.font.bold = bold
    if italic is not None: run.font.italic = italic
    if color is not None: run.font.color.rgb = color
def add_bookmark(p, name):
    _bm[0] += 1
    s = OxmlElement("w:bookmarkStart"); s.set(qn("w:id"), str(_bm[0])); s.set(qn("w:name"), name)
    e = OxmlElement("w:bookmarkEnd"); e.set(qn("w:id"), str(_bm[0]))
    pPr = p._p.find(qn("w:pPr"))
    if pPr is not None: pPr.addnext(s)
    else: p._p.insert(0, s)
    p._p.append(e)
def make_run_el(text, size, bold=False, italic=False, color=None, underline=False, font=FONT):
    r = OxmlElement("w:r"); rpr = OxmlElement("w:rPr")
    rf = OxmlElement("w:rFonts")
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"): rf.set(qn(a), font)
    rpr.append(rf)
    if bold: rpr.append(OxmlElement("w:b"))
    if italic: rpr.append(OxmlElement("w:i"))
    if color:
        c = OxmlElement("w:color"); c.set(qn("w:val"), color); rpr.append(c)
    sz = OxmlElement("w:sz"); sz.set(qn("w:val"), str(int(size * 2))); rpr.append(sz)
    if underline:
        u = OxmlElement("w:u"); u.set(qn("w:val"), "single"); rpr.append(u)
    r.append(rpr); t = OxmlElement("w:t"); t.text = text; t.set(qn("xml:space"), "preserve"); r.append(t)
    return r
def add_link(p, text, size, url=None, anchor=None, underline=True, bold=False, italic=False, font=FONT):
    h = OxmlElement("w:hyperlink")
    if url: h.set(qn("r:id"), p.part.relate_to(url, RT.HYPERLINK, is_external=True))
    else: h.set(qn("w:anchor"), anchor); h.set(qn("w:history"), "1")
    h.append(make_run_el(text, size, bold=bold, italic=italic, color="0563C1" if url else "1F4E9A", underline=underline, font=font))
    p._p.append(h)
def add_field(p, instr, placeholder="Nhấn chuột phải → Update Field để cập nhật", size=13):
    def fc(t):
        r = OxmlElement("w:r"); f = OxmlElement("w:fldChar"); f.set(qn("w:fldCharType"), t); r.append(f); return r
    p._p.append(fc("begin"))
    r = OxmlElement("w:r"); it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = " " + instr + " "; r.append(it); p._p.append(r)
    p._p.append(fc("separate")); p._p.append(make_run_el(placeholder, size)); p._p.append(fc("end"))
def keep_next(p): p.paragraph_format.keep_with_next = True

# ---------- văn bản nội dòng ----------
TOK = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\[@[^\]]+\]|\{(?:fig|tab):[a-z0-9_]+\}|https?://[^\s<>()]+[^\s<>().,;:]|\*[^*\s][^*]*?\*)")
def add_inline(p, text, size=13, bold=False, italic=False, color=None):
    for part in TOK.split(text):
        if not part: continue
        if part.startswith("**") and part.endswith("**"):
            add_inline(p, part[2:-2], size, True, italic, color)
        elif part.startswith("`") and part.endswith("`"):
            r = p.add_run(part[1:-1]); set_run_font(r, size - 1.5, bold, italic, color, name="Consolas")
        elif part.startswith("[@"):
            keys = [k.strip().lstrip("@") for k in re.split(r";\s*", part[2:-1])]
            for i, k in enumerate(keys):
                if i: r = p.add_run(", "); set_run_font(r, size, bold, italic, color)
                add_link(p, f"[{REFNUM[k]}]", size, anchor=f"ref_{REFNUM[k]}", underline=False, bold=bold, italic=italic)
        elif part.startswith("{") and part.endswith("}"):
            lab, bm = labels[part[1:-1]]
            add_link(p, lab, size, anchor=bm, underline=False, bold=bold, italic=italic)
        elif part.startswith("http"):
            add_link(p, part, size - 0.5, url=part, bold=bold, italic=italic)
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            add_inline(p, part[1:-1], size, bold, True, color)
        else:
            r = p.add_run(part); set_run_font(r, size, bold, italic, color)

# ---------- tài liệu và kiểu ----------
doc = Document()
st = doc.styles
normal = st["Normal"]; normal.font.name = FONT; normal.font.size = Pt(13)
normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
normal.paragraph_format.space_after = Pt(0); normal.paragraph_format.line_spacing = 1.15
def mkstyle(name, base="Normal", size=13, bold=False, italic=False, align=None, before=0, after=6, ls=1.3, indent=None, keep=False):
    s = st.add_style(name, 1); s.base_style = st[base]
    s.font.name = FONT; s.font.size = Pt(size); s.font.bold = bold; s.font.italic = italic
    pf = s.paragraph_format; pf.space_before = Pt(before); pf.space_after = Pt(after); pf.line_spacing = ls
    if align is not None: pf.alignment = align
    if indent is not None: pf.first_line_indent = Cm(indent)
    if keep: pf.keep_with_next = True
    return s
mkstyle("Noi dung", align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=1.27, after=6, ls=1.5)
mkstyle("Caption Hinh", size=12, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, before=3, after=10, ls=1.15)
mkstyle("Caption Bang", size=12, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, before=8, after=4, ls=1.15, keep=True)
mkstyle("Hinh", align=WD_ALIGN_PARAGRAPH.CENTER, before=6, after=0, ls=1.0, keep=True)
mkstyle("O bang", size=12, after=1, ls=1.1)
for lvl, (size, align, before, after) in {1: (16, WD_ALIGN_PARAGRAPH.CENTER, 0, 18), 2: (14, None, 10, 6), 3: (13, None, 6, 4)}.items():
    h = st[f"Heading {lvl}"]; h.font.name = FONT; h.font.size = Pt(size); h.font.bold = True; h.font.italic = False
    h.font.color.rgb = RGBColor(0, 0, 0)
    rpr = h.element.get_or_add_rPr(); rf = rpr.find(qn("w:rFonts"))
    if rf is None: rf = OxmlElement("w:rFonts"); rpr.insert(0, rf)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"): rf.set(qn(a), FONT)
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
        if rf.get(qn(a)) is not None: del rf.attrib[qn(a)]
    pf = h.paragraph_format; pf.space_before = Pt(before); pf.space_after = Pt(after); pf.keep_with_next = True; pf.line_spacing = 1.5
    if align is not None: pf.alignment = align
    if lvl == 1: pf.page_break_before = True
# kiểu mục lục toc 1..3 (tên chuẩn của Word)
styles_el = doc.styles.element
for lvl, ind, bold in ((1, 0, True), (2, 1.0, False), (3, 2.0, False), (4, 0, False)):
    s = OxmlElement("w:style"); s.set(qn("w:type"), "paragraph"); s.set(qn("w:styleId"), f"TOC{lvl}")
    n = OxmlElement("w:name"); n.set(qn("w:val"), f"toc {lvl}"); s.append(n)
    b = OxmlElement("w:basedOn"); b.set(qn("w:val"), "Normal"); s.append(b)
    ui = OxmlElement("w:uiPriority"); ui.set(qn("w:val"), "39"); s.append(ui)
    pPr = OxmlElement("w:pPr")
    tabs = OxmlElement("w:tabs"); tab = OxmlElement("w:tab"); tab.set(qn("w:val"), "right"); tab.set(qn("w:leader"), "dot"); tab.set(qn("w:pos"), str(int(15.5 / 2.54 * 1440))); tabs.append(tab); pPr.append(tabs)
    sp = OxmlElement("w:spacing"); sp.set(qn("w:before"), "60" if lvl == 1 else "0"); sp.set(qn("w:after"), "40"); sp.set(qn("w:line"), "336"); sp.set(qn("w:lineRule"), "auto"); pPr.append(sp)
    indel = OxmlElement("w:ind"); indel.set(qn("w:left"), str(int(ind / 2.54 * 1440))); indel.set(qn("w:right"), "400"); pPr.append(indel)
    s.append(pPr)
    rPr = OxmlElement("w:rPr")
    if bold: rPr.append(OxmlElement("w:b"))
    s.append(rPr); styles_el.append(s)

def P(text="", style="Noi dung", align=None, size=13, bold=False, italic=False, color=None):
    p = doc.add_paragraph(style=style)
    if align is not None: p.alignment = align
    if text: add_inline(p, text, size, bold, italic, color)
    return p
def heading(text, lvl):
    p = doc.add_paragraph(style=f"Heading {lvl}")
    r = p.add_run(text); set_run_font(r, {1: 16, 2: 14, 3: 13}[lvl], True, False, RGBColor(0, 0, 0))
    return p

def img_path(path, crop=None):
    im = Image.open(path)
    if crop: im = im.crop(crop)
    if path.lower().endswith(".png") and "anh_demo" in path.replace("\\", "/"):
        out = os.path.join(TMP, os.path.basename(path).rsplit(".", 1)[0] + ("_c" if crop else "") + ".jpg")
        im.convert("RGB").save(out, quality=88); return out
    if crop:
        out = os.path.join(TMP, os.path.basename(path).rsplit(".", 1)[0] + "_c.png"); im.save(out); return out
    return path

fig_ctr = {}; tab_ctr = {}; cur_chap = [0]
def render(blocks):
    for b in blocks:
        k = b[0]
        if k == "chapter":
            cur_chap[0] += 1; heading(b[1], 1)
        elif k == "h2": heading(b[1], 2)
        elif k == "h3": heading(b[1], 3)
        elif k == "p": P(b[1])
        elif k == "bullets":
            for t in b[1]: P("– " + t)
        elif k == "num":
            for i, t in enumerate(b[1]): P(f"{i+1}. " + t)
        elif k == "code":
            p = doc.add_paragraph(style="Normal"); p.paragraph_format.left_indent = Cm(1); p.paragraph_format.space_after = Pt(6)
            pPr = p._p.get_or_add_pPr(); shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:fill"), "F2F2F2"); pPr.append(shd)
            r = p.add_run(b[1]); set_run_font(r, 11, name="Consolas")
        elif k == "eq":
            p = doc.add_paragraph(style="Normal"); pf = p.paragraph_format; pf.space_before = Pt(4); pf.space_after = Pt(6)
            pf.tab_stops.add_tab_stop(Cm(8), WD_TAB_ALIGNMENT.CENTER); pf.tab_stops.add_tab_stop(Cm(16), WD_TAB_ALIGNMENT.RIGHT)
            r = p.add_run("\t" + b[1]); set_run_font(r, 13, italic=True)
            r = p.add_run(f"\t({b[2]})"); set_run_font(r, 13)
        elif k == "fig":
            path, cap, width = b[1], b[2], b[3]; opt = b[4] if len(b) > 4 else {}
            c = cur_chap[0]; fig_ctr[c] = fig_ctr.get(c, 0) + 1; num = f"Hình {c}.{fig_ctr[c]}"
            p = doc.add_paragraph(style="Hinh"); p.add_run().add_picture(img_path(path, opt.get("crop")), width=Cm(min(width, 15.5)))
            cp = doc.add_paragraph(style="Caption Hinh"); r = cp.add_run(f"{num}. {cap}"); set_run_font(r, 12, italic=True)
            if opt.get("label"): add_bookmark(cp, "fig_" + opt["label"])
        elif k == "table":
            cap, head, rows, widths = b[1], b[2], b[3], b[4]; label = b[5] if len(b) > 5 else None
            c = cur_chap[0]; tab_ctr[c] = tab_ctr.get(c, 0) + 1; num = f"Bảng {c}.{tab_ctr[c]}"
            cp = doc.add_paragraph(style="Caption Bang"); r = cp.add_run(f"{num}. {cap}"); set_run_font(r, 12, italic=True)
            if label: add_bookmark(cp, "tab_" + label)
            make_table(head, rows, widths)
            sp = doc.add_paragraph(style="Normal"); sp.paragraph_format.space_after = Pt(4); sp.paragraph_format.line_spacing = 0.8
def make_table(head, rows, widths, center_cols=()):
    t = doc.add_table(rows=1 + len(rows), cols=len(head)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    tot = sum(widths)
    if tot > 15.5: widths = [w * 15.5 / tot for w in widths]
    t.autofit = False
    tblPr = t._tbl.tblPr; lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed"); tblPr.append(lay)
    for i, w in enumerate(widths):
        for cell in t.columns[i].cells: cell.width = Cm(w)
    for i, h in enumerate(head):
        cell = t.rows[0].cells[i]; set_cell_shading(cell, HEAD_FILL); cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p = cell.paragraphs[0]; p.style = st["O bang"]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER; add_inline(p, h, 12, bold=True)
    trPr = t.rows[0]._tr.get_or_add_trPr(); th = OxmlElement("w:tblHeader"); trPr.append(th)
    for ri, row in enumerate(rows):
        tr = t.rows[ri + 1]; trPr = tr._tr.get_or_add_trPr(); cs = OxmlElement("w:cantSplit"); trPr.append(cs)
        for ci, val in enumerate(row):
            cell = tr.cells[ci]
            vals = val if isinstance(val, list) else [val]
            for vi, v in enumerate(vals):
                p = cell.paragraphs[0] if vi == 0 else cell.add_paragraph()
                p.style = st["O bang"]
                if ci in center_cols or (len(head) > 3 and ci > 0 and len(str(v)) <= 8): p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                add_inline(p, v, 12)
        if row and row[0] == "Tổng cộng":
            for cell in tr.cells:
                for p in cell.paragraphs:
                    for r in p.runs: r.font.bold = True
    return t

def page_number_footer(section):
    section.footer.is_linked_to_previous = False
    p = section.footer.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.style = st["Normal"]
    add_field(p, "PAGE", placeholder="1", size=12)
def set_pgnum(section, fmt, start=1):
    sp = section._sectPr; pg = OxmlElement("w:pgNumType"); pg.set(qn("w:fmt"), fmt); pg.set(qn("w:start"), str(start)); sp.append(pg)
def margins(section):
    section.page_width = Cm(21); section.page_height = Cm(29.7)
    section.top_margin = Cm(2.5); section.bottom_margin = Cm(2.2); section.left_margin = Cm(3.5); section.right_margin = Cm(2)
    section.header_distance = Cm(1.2); section.footer_distance = Cm(1.0)

# ---------- BÌA ----------
s0 = doc.sections[0]; margins(s0)
sp = s0._sectPr; pb = OxmlElement("w:pgBorders"); pb.set(qn("w:offsetFrom"), "text")
for side in ("top", "left", "bottom", "right"):
    e = OxmlElement(f"w:{side}"); e.set(qn("w:val"), "double"); e.set(qn("w:sz"), "12"); e.set(qn("w:space"), "14"); e.set(qn("w:color"), "000000"); pb.append(e)
sp.append(pb)
def cover_line(text, size, bold=False, color=None, before=0, after=0, italic=False, underline=False, align=WD_ALIGN_PARAGRAPH.CENTER):
    p = doc.add_paragraph(style="Normal"); p.alignment = align; p.paragraph_format.space_before = Pt(before); p.paragraph_format.space_after = Pt(after)
    if text:
        r = p.add_run(text); set_run_font(r, size, bold, italic, color); r.font.underline = underline
    return p
cover_line("TRƯỜNG ĐẠI HỌC CÔNG NGHỆ THÔNG TIN VÀ TRUYỀN THÔNG", 13, before=6)
p = cover_line("KHOA CÔNG NGHỆ THÔNG TIN", 13, bold=True, after=14)
pPr = p._p.get_or_add_pPr(); bdr = OxmlElement("w:pBdr"); bt = OxmlElement("w:bottom")
bt.set(qn("w:val"), "single"); bt.set(qn("w:sz"), "6"); bt.set(qn("w:space"), "2"); bt.set(qn("w:color"), "000000"); bdr.append(bt); pPr.append(bdr)
p.paragraph_format.left_indent = Cm(3.6); p.paragraph_format.right_indent = Cm(3.6)
p = cover_line("", 13, before=10, after=24); p.add_run().add_picture(LOGO, width=Cm(4.2))
RED = RGBColor(0xE0, 0x1B, 0x1B); CBLUE = RGBColor(0x2E, 0x74, 0xB5)
cover_line("BÁO CÁO MINI PROJECT", 26, bold=True, color=RED, before=10, after=4)
cover_line("HỌC PHẦN ĐIỆN TOÁN ĐÁM MÂY (PUBLIC CLOUD)", 17, bold=True, color=RED, after=22)
p = cover_line("Đề tài:", 13, bold=True, italic=True, underline=True, align=WD_ALIGN_PARAGRAPH.LEFT, after=6); p.paragraph_format.left_indent = Cm(0.6)
cover_line("XÂY DỰNG VÀ TRIỂN KHAI HỆ THỐNG WEBSITE", 15, bold=True, after=2)
cover_line("THƯƠNG MẠI ĐIỆN TỬ KHẢ TRỢ NĂNG (AUTO-SCALING)", 15, bold=True, after=2)
cover_line("TRÊN NỀN TẢNG ĐIỆN TOÁN ĐÁM MÂY AWS", 15, bold=True, after=26)
info = doc.add_table(rows=3, cols=2); info.alignment = WD_TABLE_ALIGNMENT.CENTER; info.autofit = False
lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed"); info._tbl.tblPr.append(lay)
for i, w in enumerate((5.4, 7.0)):
    for cell in info.columns[i].cells: cell.width = Cm(w)
rows = [("Tên nhóm:", ["NHÓM ........"]), ("Sinh viên thực hiện:", [MEMBERS[0] + " (#)"] + MEMBERS[1:]), ("Giáo viên hướng dẫn:", ["..............................."])]
for ri, (lab, vals) in enumerate(rows):
    c0, c1 = info.rows[ri].cells
    p = c0.paragraphs[0]; p.style = st["Normal"]; p.paragraph_format.space_after = Pt(8); r = p.add_run(lab); set_run_font(r, 13, True)
    for vi, v in enumerate(vals):
        p = c1.paragraphs[0] if vi == 0 else c1.add_paragraph(); p.style = st["Normal"]; p.paragraph_format.space_after = Pt(3 if vi < len(vals) - 1 else 8)
        r = p.add_run(v); set_run_font(r, 13, True, color=CBLUE if ri < 2 else None)
cover_line("", 13, after=40)
cover_line("THÁI NGUYÊN, NĂM 2026", 13, bold=True, before=120)

# ---------- PHẦN ĐẦU (số La Mã) ----------
s1 = doc.add_section(WD_SECTION.NEW_PAGE); margins(s1)
s1._sectPr.remove(s1._sectPr.find(qn("w:pgBorders"))) if s1._sectPr.find(qn("w:pgBorders")) is not None else None
set_pgnum(s1, "lowerRoman"); page_number_footer(s1)
heading("LỜI CẢM ƠN", 1)
for t in THANKS: P(t)
P("Thái Nguyên, ngày …… tháng …… năm 2026", align=WD_ALIGN_PARAGRAPH.RIGHT, italic=True).paragraph_format.first_line_indent = Cm(0)
p = P("Nhóm sinh viên thực hiện", align=WD_ALIGN_PARAGRAPH.RIGHT, bold=True); p.paragraph_format.first_line_indent = Cm(0); p.paragraph_format.right_indent = Cm(0.4)
for m in MEMBERS:
    p = P(m, align=WD_ALIGN_PARAGRAPH.RIGHT, bold=True); p.paragraph_format.first_line_indent = Cm(0); p.paragraph_format.right_indent = Cm(0.6); p.paragraph_format.space_after = Pt(0); p.paragraph_format.line_spacing = 1.15
heading("MỤC LỤC", 1)
p = doc.add_paragraph(style="Normal"); add_field(p, 'TOC \\o "1-3" \\h \\z \\u')
heading("PHÂN CÔNG NHIỆM VỤ", 1)
P("**Phân công nhiệm vụ theo tiến độ thực hiện:**").paragraph_format.first_line_indent = Cm(0)
make_table(["Stt", "Tên nhiệm vụ", "Người thực hiện"], [[str(i + 1), t, ppl] for i, (t, ppl) in enumerate(TASKS)], [1.2, 9.6, 5.2], center_cols=(0,))
p = P("**Phân công nhiệm vụ theo thành viên thực hiện:**"); p.paragraph_format.first_line_indent = Cm(0); p.paragraph_format.space_before = Pt(12); p.paragraph_format.page_break_before = True
rows = []
for i, m in enumerate(MEMBERS):
    mine = ["– " + t for t, ppl in TASKS if m in ppl]
    rows.append([str(i + 1), m, mine, ""])
make_table(["Stt", "Thành viên", "Nhiệm vụ", "Chữ ký"], rows, [1.2, 3.6, 8.8, 2.4], center_cols=(0,))
heading("DANH SÁCH CÁC BẢNG", 1)
p = doc.add_paragraph(style="Normal"); add_field(p, 'TOC \\h \\z \\t "Caption Bang,4"')
heading("DANH SÁCH CÁC HÌNH", 1)
p = doc.add_paragraph(style="Normal"); add_field(p, 'TOC \\h \\z \\t "Caption Hinh,4"')
heading("DANH MỤC CÁC TỪ VIẾT TẮT", 1)
make_table(["Từ viết tắt", "Tên đầy đủ / Diễn giải"], [[a, b] for a, b in ABBR], [3.4, 12.6])
heading("MỞ ĐẦU", 1)
render(INTRO)

# ---------- NỘI DUNG (số Ả Rập) ----------
s2 = doc.add_section(WD_SECTION.NEW_PAGE); margins(s2)
if s2._sectPr.find(qn("w:pgBorders")) is not None: s2._sectPr.remove(s2._sectPr.find(qn("w:pgBorders")))
set_pgnum(s2, "decimal"); page_number_footer(s2)
render(CH1 + CH2 + CH3)
heading("TÀI LIỆU THAM KHẢO", 1)
for k in cite_order:
    n = REFNUM[k]; txt, url = REFS[k]
    p = doc.add_paragraph(style="Normal"); pf = p.paragraph_format
    pf.left_indent = Cm(1.2); pf.first_line_indent = Cm(-1.2); pf.space_after = Pt(6); pf.line_spacing = 1.25; p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    pf.tab_stops.add_tab_stop(Cm(1.2))
    r = p.add_run(f"[{n}]\t{txt} "); set_run_font(r, 13)
    r = p.add_run("URL: "); set_run_font(r, 13)
    add_link(p, url, 12.5, url=url)
    add_bookmark(p, f"ref_{n}")
# bìa không có số trang
s0.footer.is_linked_to_previous = False
doc.core_properties.title = "Báo cáo mini project: CloudShop Auto Scaling trên AWS"
doc.core_properties.author = ", ".join(MEMBERS)
doc.save(OUT)
n_cite = sum(len(re.split(r";\s*", m)) for b in ALL for t in walk_texts(b) for m in re.findall(r"\[@([^\]]+)\]", t))
print("saved", OUT, "refs", len(cite_order), "in-text", n_cite, "figs", sum(fig_ctr.values()), "tables", sum(tab_ctr.values()))
