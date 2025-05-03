"""Shared export utilities: docx/pptx builders and common helpers."""

import copy, os, re, sys
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from lxml import etree
from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches as PptInches, Cm as PptCm, Pt as PptPt, Emu
from pptx.dml.color import RGBColor as PptRGBColor
from pptx.oxml.ns import qn as pptx_qn
# ── Shared Constants ──────────────────────────────────────

PPT_TEMPLATE = "templates/ppt_template.pptx"
TNR = "Times New Roman"
FZ_ST = "方正书宋_GBK"
FZ_HT = "方正黑体_GBK"
FZ_KT = "方正楷体_GBK"
FZ_XBS = "方正小标宋简体"
CN_FONTS = ["方正书宋_GBK", "宋体", "SimSun"]

X2 = Pt(18)     # 小二号
X4 = Pt(12)     # 小四号
W5 = Pt(10.5)   # 五号


# ── Shared Helpers ────────────────────────────────────────


def _set_run_font(run, latin=TNR, ea=FZ_ST, size=W5, color=RGBColor(0, 0, 0)):
    """Set Latin + East-Asian fonts on a run via XML."""
    run.font.name = latin
    run.font.size = size
    run.font.color.rgb = color
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.insert(0, rFonts)
    rFonts.set(qn("w:ascii"), latin)
    rFonts.set(qn("w:hAnsi"), latin)
    rFonts.set(qn("w:eastAsia"), ea)


def _set_paragraph_spacing(p):
    """Zero spacing, 1.5 line, grid alignment on."""
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.line_spacing = 1.5
    pPr = p._element.get_or_add_pPr()
    spacing = pPr.find(qn("w:spacing"))
    if spacing is None:
        spacing = OxmlElement("w:spacing")
        pPr.append(spacing)
    spacing.set(qn("w:before"), "0")
    spacing.set(qn("w:after"), "0")
    spacing.set(qn("w:line"), "360")
    spacing.set(qn("w:lineRule"), "auto")


def _setup_16k_page(doc):
    """Set 16开 page size with narrow margins."""
    section = doc.sections[0]
    section.page_width = Cm(18.4)
    section.page_height = Cm(26.0)
    section.top_margin = Cm(1.27)
    section.bottom_margin = Cm(1.27)
    section.left_margin = Cm(1.27)
    section.right_margin = Cm(1.27)


def _setup_default_style(doc):
    """Set Normal style to TNR + 方正书宋_GBK, 五号, 1.5 spacing."""
    style = doc.styles["Normal"]
    style.font.name = TNR
    style.font.size = W5
    style.font.color.rgb = RGBColor(0, 0, 0)
    rPr = style.element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.insert(0, rFonts)
    rFonts.set(qn("w:ascii"), TNR)
    rFonts.set(qn("w:hAnsi"), TNR)
    rFonts.set(qn("w:eastAsia"), FZ_ST)
    pf = style.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.line_spacing = 1.5


def _add_page_header_footer(doc, label):
    """Add centered header and PAGE/NUMPAGES footer to all sections."""
    for section in doc.sections:
        header = section.header
        header.is_linked_to_previous = False
        hp = header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_paragraph_spacing(hp)
        run = hp.add_run("Lume @Irving Wu")
        _set_run_font(run, size=Pt(9))

        footer = section.footer
        footer.is_linked_to_previous = False
        fp = footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_paragraph_spacing(fp)

        def _add_fp_run(text):
            r = fp.add_run(text)
            _set_run_font(r, size=Pt(9))
            return r

        _add_fp_run(f"{label} 第")
        fld1 = OxmlElement("w:fldChar")
        fld1.set(qn("w:fldCharType"), "begin")
        r1 = fp.add_run(); r1._element.append(fld1)
        instr1 = OxmlElement("w:instrText")
        instr1.text = " PAGE "
        r2 = fp.add_run(); r2._element.append(instr1)
        fld2 = OxmlElement("w:fldChar")
        fld2.set(qn("w:fldCharType"), "end")
        r3 = fp.add_run(); r3._element.append(fld2)
        _add_fp_run(" 页 / 共 ")
        fld3 = OxmlElement("w:fldChar")
        fld3.set(qn("w:fldCharType"), "begin")
        r4 = fp.add_run(); r4._element.append(fld3)
        instr2 = OxmlElement("w:instrText")
        instr2.text = " NUMPAGES "
        r5 = fp.add_run(); r5._element.append(instr2)
        fld4 = OxmlElement("w:fldChar")
        fld4.set(qn("w:fldCharType"), "end")
        r6 = fp.add_run(); r6._element.append(fld4)
        _add_fp_run(" 页")


# ── Writing Helpers (markdown → docx) ────────────────────


def _add_inline_paragraph(doc, text, bold=False, size=Pt(12), alignment=None, style_name=None):
    """Add a paragraph, parsing **bold** and *italic* inline markers."""
    if style_name:
        p = doc.add_paragraph(style=style_name)
    else:
        p = doc.add_paragraph()
    _set_paragraph_spacing(p)
    if alignment is not None:
        p.alignment = alignment
    _append_inline_runs(p, text, size, bold)
    return p


def _append_inline_runs(p, text, base_size, base_bold):
    """Parse **bold**, *italic*, and `code` inline markers anywhere in text."""
    pattern = r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)"
    parts = re.split(pattern, text)
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            run = p.add_run(part[2:-2])
            _set_run_font(run, ea=FZ_HT, size=base_size)
            run.bold = True
        elif part.startswith("*") and part.endswith("*"):
            run = p.add_run(part[1:-1])
            _set_run_font(run, size=base_size)
            run.italic = True
        elif part.startswith("`") and part.endswith("`"):
            run = p.add_run(part[1:-1])
            _set_run_font(run, size=base_size)
        else:
            run = p.add_run(part.replace("`", ""))
            _set_run_font(run, size=base_size)
            if base_bold:
                run.bold = True
                rPr = run._element.get_or_add_rPr()
                rFonts = rPr.find(qn("w:rFonts"))
                if rFonts is not None:
                    rFonts.set(qn("w:eastAsia"), FZ_HT)


def _is_table_line(line):
    return "|" in line and line.strip().startswith("|")


def _parse_table(doc, lines, start_idx):
    """Parse a markdown table starting at start_idx. Returns next index after table."""
    rows = []
    i = start_idx
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            break
        if not _is_table_line(stripped):
            break
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        rows.append(cells)
        i += 1

    if len(rows) < 2:
        return start_idx + 1

    header = rows[0]
    data_start = 1
    if data_start < len(rows) and all(re.match(r"^[-:]+$", c) for c in rows[data_start]):
        data_start = 2

    data_rows = rows[data_start:]
    if not data_rows:
        return i

    table = doc.add_table(rows=1 + len(data_rows), cols=len(header))
    table.style = "Table Grid"

    for ci, cell_text in enumerate(header):
        cell = table.rows[0].cells[ci]
        cell.paragraphs[0].clear()
        run = cell.paragraphs[0].add_run(cell_text)
        _set_run_font(run, size=Pt(11))
        run.bold = True
        _set_paragraph_spacing(cell.paragraphs[0])

    for ri, row in enumerate(data_rows):
        for ci, cell_text in enumerate(row):
            if ci < len(header):
                cell = table.rows[ri + 1].cells[ci]
                cell.paragraphs[0].clear()
                run = cell.paragraphs[0].add_run(cell_text)
                _set_run_font(run, size=Pt(11))
                _set_paragraph_spacing(cell.paragraphs[0])

    doc.add_paragraph()
    return i


# ── Listening Helpers ────────────────────────────────────


_CLEAN_BULLETS = re.compile(r"^[·•\-*○●◎◇◆□■△▲▽▼▷▶▸▹▾▿☐☑]\s*")


def _add_content_with_cleanup(paragraph, content_text):
    """Add content text to paragraph, stripping bullet prefixes."""
    text = _CLEAN_BULLETS.sub("", content_text)
    run = paragraph.add_run(text)
    _set_run_font(run)
    return run


def _add_heading(doc, text, size):
    p = doc.add_paragraph()
    _set_paragraph_spacing(p)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    _set_run_font(run, ea=FZ_HT, size=size)


def _add_paragraph(doc, text):
    p = doc.add_paragraph()
    _set_paragraph_spacing(p)
    run = p.add_run(text)
    _set_run_font(run)


# ── PDF Docx Helpers ─────────────────────────────────────


def _add_p(doc, text="", bold=False, latin=TNR, ea=FZ_ST, size=W5, indent=0, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY):
    p = doc.add_paragraph()
    _set_paragraph_spacing(p)
    p.alignment = alignment
    if indent:
        if indent is True:
            indent = 2
        p.paragraph_format.first_line_indent = Cm(0.37 * indent)
    if text:
        parts = re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*|\+\+[^+]+\+\+)", text)
        for part in parts:
            if not part:
                continue
            if part.startswith("**") and part.endswith("**"):
                run = p.add_run(part[2:-2])
                _set_run_font(run, latin=latin, ea=ea, size=size)
                run.bold = True
            elif part.startswith("++") and part.endswith("++"):
                run = p.add_run(part[2:-2])
                _set_run_font(run, latin=latin, ea=ea, size=size)
                run.underline = True
            elif part.startswith("*") and part.endswith("*"):
                run = p.add_run(part[1:-1])
                _set_run_font(run, latin=latin, ea=ea, size=size)
                run.italic = True
                if bold:
                    run.bold = True
            else:
                run = p.add_run(part)
                _set_run_font(run, latin=latin, ea=ea, size=size)
                if bold:
                    run.bold = True
    return p


def _add_heading_p(doc, text, size=X4):
    p = doc.add_paragraph()
    _set_paragraph_spacing(p)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    _set_run_font(run, ea=FZ_HT, size=size)


def _num_to_chinese(n):
    """Convert integer to Chinese quantifier (1→'一', 2→'两', 12→'十二')."""
    digits_standalone = ["", "一", "两", "三", "四", "五", "六", "七", "八", "九"]
    digits_compound  = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
    tens = ["", "十", "二十", "三十", "四十", "五十", "六十", "七十", "八十", "九十"]
    if n <= 0:
        return ""
    if n <= 9:
        return digits_standalone[n]
    if n <= 19:
        return "十" + (digits_compound[n - 10] if n > 10 else "")
    if n <= 99:
        t = n // 10
        u = n % 10
        return tens[t] + (digits_compound[u] if u else "")
    return str(n)


def _est_width(text):
    """Precise width at 10.5pt: Latin 0.19cm avg, CJK 0.37cm, narrow 0.11cm, space 0.09cm."""
    w = 0
    for ch in text:
        code = ord(ch)
        if code >= 0x4E00:
            w += 0.37
        elif code >= 0x3000:
            w += 0.37
        elif ch in 'il1|:;,.!?\'':
            w += 0.11
        elif ch in 'mwWM%':
            w += 0.25
        elif ch == ' ':
            w += 0.09
        elif ch == '\t':
            pass
        else:
            w += 0.19
    return w


def _add_options_line(doc, options, num_cols, indent=1.5):
    """Smart layout: 1-line / 2-line / separate, with precise column width check."""
    if not options:
        return
    usable = 15.86 - 0.56
    parts = [f"{chr(65+j)}. {opt}" for j, opt in enumerate(options)]

    def _col_w(n):
        return (usable - 0.15 * (n - 1)) / n

    cw = _col_w(num_cols)
    if all(_est_width(p) <= cw for p in parts):
        p = _add_p(doc, indent=indent)
        from docx.enum.text import WD_TAB_ALIGNMENT
        for col in range(1, num_cols):
            p.paragraph_format.tab_stops.add_tab_stop(Cm(col * (cw + 0.15)), WD_TAB_ALIGNMENT.LEFT)
        run = p.add_run("\t".join(parts))
        _set_run_font(run, size=W5)
        return

    if num_cols == 4:
        cw2 = _col_w(2)
        if all(_est_width(p) <= cw2 for p in parts[:2]) and all(_est_width(p) <= cw2 for p in parts[2:]):
            from docx.enum.text import WD_TAB_ALIGNMENT
            for line_parts in ["\t".join(parts[:2]), "\t".join(parts[2:])]:
                p = _add_p(doc, indent=indent)
                p.paragraph_format.tab_stops.add_tab_stop(Cm(cw2 + 0.15), WD_TAB_ALIGNMENT.LEFT)
                run = p.add_run(line_parts)
                _set_run_font(run, size=W5)
            return

    for opt_text in parts:
        _add_p(doc, opt_text, indent=indent)


def _add_cloze_options_block(doc, options, blank_nums=None):
    """Render cloze options with A/B/C/D columns aligned using tab stops."""
    if not options:
        return
    parsed = []
    for opt_text in options:
        parts = [p.strip() for p in re.split(r"(?:^|\s+)[A-D]\.\s*", opt_text) if p.strip()]
        if len(parts) == 4:
            parsed.append(parts)
        else:
            parts = [p.strip() for p in re.split(r"\s+(?=[A-D]\.)", opt_text) if p.strip()]
            if len(parts) == 4:
                parsed.append(parts)
            else:
                parsed.append([opt_text, "", "", ""])

    if not parsed:
        return

    max_widths = [0, 0, 0, 0]
    for row in parsed:
        for ci in range(4):
            max_widths[ci] = max(max_widths[ci], len(row[ci]) if ci < len(row) else 0)

    usable = 15.86
    total_chars = sum(max_widths) + 12
    char_w = 0.3 if total_chars > 0 else 0.3
    positions = [0]
    for ci in range(3):
        pos = sum(max_widths[:ci+1]) * char_w + (ci+1) * 1.0
        positions.append(pos)
        if positions[-1] > usable:
            positions[-1] = usable * (ci+1) / 4

    from docx.enum.text import WD_TAB_ALIGNMENT
    for ri, row in enumerate(parsed):
        p = doc.add_paragraph()
        _set_paragraph_spacing(p)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        tab_stops = p.paragraph_format.tab_stops
        for pos in positions[1:]:
            if pos < usable:
                tab_stops.add_tab_stop(Cm(pos), WD_TAB_ALIGNMENT.LEFT)
        qid = blank_nums[ri] if blank_nums and ri < len(blank_nums) else (ri + 41)
        q_num = f"{qid}. "
        parts = []
        for ci in range(4):
            if ci < len(row):
                parts.append(f"{chr(65+ci)}. {row[ci]}")
        run = p.add_run(q_num + "\t".join(parts))
        _set_run_font(run, size=W5)


def _add_underline_line(doc):
    """Add a full-width underline line using underscore characters."""
    UL = "_____________________________________________________________________________________"
    p = doc.add_paragraph()
    _set_paragraph_spacing(p)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(UL)
    _set_run_font(run, size=W5)
    return p



"""
build_pptx.py — Fill 模板.pptx with exam JSON data.

Usage:
  python build_pptx.py                  # reads data.json in same dir
  python build_pptx.py some_exam.json   # reads given JSON
"""

import copy, json, os, re, sys
from lxml import etree
from pptx import Presentation
from pptx.util import Pt, Emu
from pptx.dml.color import RGBColor as _PptRGB
from pptx.enum.text import PP_ALIGN

# ── Paths ────────────────────────────────────────────────────

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "templates", "ppt_template.pptx")
OUTPUT   = os.path.join(HERE, "output.pptx")
DEFAULT_JSON = os.path.join(HERE, "data.json")

# ── Layout ───────────────────────────────────────────────────

FONT_CN    = "微软雅黑"
FONT_LATIN = "Times New Roman"
SIZE_BODY   = Pt(24)
SIZE_TITLE  = Pt(28)
SIZE_SOURCE = Pt(44)
SIZE_ENGLISH = Pt(80)
COLOR_BODY   = _PptRGB(0, 0, 0)
COLOR_TITLE  = _PptRGB(0x31, 0x9D, 0xCD)

CONTENT_X = 650000
CONTENT_Y = 760000
CONTENT_W = 11000000
CONTENT_H = 5500000

# First-line indent ≈ 2 chars at 24pt
BODY_INDENT = Emu(685800)

# Body textbox position inside Plaque (keep original left/width, expand down)
# Template TextBox 2: left=647700  width=10896600
BODY_LEFT  = 647700
BODY_TOP   = 900000
BODY_WIDTH = 10896600
# Plaque bottom = 262467 + 6333066 = 6595533
# Title bottom = 439389 + 523220 = 962609
# Body area: top=900000, bottom=6595533 → available 5695533 EMU
# 120% line-spacing default: 24pt×1.2≈365 760 EMU, Pt(2) space_after=25 400
# 15 lines × 365 760 + 8×25 400 ≈ 5 689 600 ≤ 5 695 533 ✓
BODY_HEIGHT = 5695533
MAX_BODY_LINES = 15
_BODY_AVAIL_W = BODY_WIDTH       # wrap width = shape width (no lIns/rIns by default)

# Option indentation and gap
OPT_INDENT = "    "              # 4 spaces before first option
OPT_GAP    = "    "              # 4 spaces between options on same row

# At 24pt: 1 pt = 12700 EMU; 1 char ≈ 0.55~1.0 pt-width
_PT_EMU = 24 * 12700
_CHAR_W = {"cjk": _PT_EMU, "wide": int(_PT_EMU * 0.65), "norm": int(_PT_EMU * 0.45),
           "narr": int(_PT_EMU * 0.25), "sp": int(_PT_EMU * 0.25), "cap": int(_PT_EMU * 0.60)}

def _opt_text_width(text):
    """Estimate EMU width of option text at 24pt."""
    w = 0
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff' or '\u3040' <= ch <= '\u30ff' or '\uac00' <= ch <= '\ud7af':
            w += _CHAR_W["cjk"]
        elif ch == ' ':
            w += _CHAR_W["sp"]
        elif ch.isupper() or ch.isdigit():
            w += _CHAR_W["cap"]
        elif ch in 'wm':
            w += _CHAR_W["wide"]
        elif ch in 'il.,;:\'\"!':
            w += _CHAR_W["narr"]
        else:
            w += _CHAR_W["norm"]
    return w

_AVAIL_OPT_W = BODY_WIDTH - _opt_text_width(OPT_INDENT)  # usable width for option text
_OPT_GAP_W   = _opt_text_width(OPT_GAP)
_COL_W4 = BODY_WIDTH // 4  # column width for 4-col layout
_COL_W2 = BODY_WIDTH // 2  # column width for 2-col layout
_INDENT_W = _opt_text_width(OPT_INDENT)

def _pack_opts(options):
    """Pack options into balanced rows (1, 2, or 4 per row — never 3).
    Each option must stay inside its tab-stop column, else fall back.
    Returns list of (row_text_with_tabs, n_cols).
    """
    n = len(options)
    letters = [chr(65 + i) for i in range(n)]
    opts_w = [_opt_text_width(f"{l}. {t}") for l, t in zip(letters, options)]

    # Try 4-col: all 4 must fit and each within its column
    if n == 4:
        if (_INDENT_W + opts_w[0] <= _COL_W4 and
            all(opts_w[j] <= _COL_W4 for j in range(1, 4))):
            txt = OPT_INDENT + "\t".join(f"{l}. {t}" for l, t in zip(letters, options))
            return [(txt, 4)]

    # Try 2-col: each pair must fit and each option within half-width
    if n >= 2:
        valid = True
        for i in range(0, n, 2):
            for j in range(2):
                idx = i + j
                if idx >= n:
                    continue
                max_w = _COL_W2 - (_INDENT_W if j == 0 else 0)
                if opts_w[idx] > max_w:
                    valid = False
                    break
            if not valid:
                break
        if valid:
            rows = []
            for i in range(0, n, 2):
                pair = [(letters[j], options[j]) for j in range(i, min(i+2, n))]
                txt = OPT_INDENT + "\t".join(f"{l}. {t}" for l, t in pair)
                rows.append((txt, 2))
            return rows

    # Fallback: 1 per row
    return [(OPT_INDENT + f"{l}. {t}", 1) for l, t in zip(letters, options)]

# Template index map
T = {"title": 0, "reading": 1, "seven": 2, "cloze": 3,
     "grammar": 4, "writing": 5, "continuation": 6}
TEMPLATE_COUNT = 7

# ── Helpers ──────────────────────────────────────────────────

def _visual_lines(text, avail_w):
    """Estimate visual lines a paragraph wraps into at 24pt within avail_w EMU."""
    if not text:
        return 0
    total_w = _opt_text_width(text)
    return max(1, (total_w + avail_w - 1) // avail_w)


def _split_body(text):
    """Split body text into Plaque-sized chunks at natural paragraph boundaries."""
    paras = [t for t in text.split("\n") if t.strip()]
    if not paras:
        return [""]
    chunks, cur, cur_lines = [], [], 0
    for p in paras:
        pl = _visual_lines(p, _BODY_AVAIL_W)
        if cur_lines + pl > MAX_BODY_LINES and cur:
            chunks.append("\n".join(cur))
            cur, cur_lines = [p], pl
        else:
            cur.append(p)
            cur_lines += pl
    if cur:
        chunks.append("\n".join(cur))
    return chunks


def _strip_md(text):
    """Just strip heading markers and flatten blanks — bold/italic stays in the text for _set_body to convert."""
    if not text:
        return text
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{2,}', r'\n', text)
    return text.strip()


def _set_run_ea_font(run, typeface):
    """Set East-Asian font on a run (xml level)."""
    rPr = run._r.get_or_add_rPr()
    for child in list(rPr):
        if child.tag.endswith('}ea'):
            rPr.remove(child)
    ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    ea = etree.SubElement(rPr, f"{{{ns}}}ea")
    ea.set("typeface", typeface)


def _find(slide, name):
    for s in slide.shapes:
        if s.name == name:
            return s
    available = [s.name for s in slide.shapes]
    print(f"[PPT DEBUG] _find '{name}' NOT FOUND. Available: {available}")
    return None


def _remove(slide, name):
    s = _find(slide, name)
    if s:
        s._element.getparent().remove(s._element)


def _set_title(slide, text):
    s = _find(slide, "TextBox 3")
    if s:
        tf = s.text_frame
        tf.clear()
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = text
        r.font.size = SIZE_TITLE
        r.font.color.rgb = COLOR_TITLE
        r.font.bold = True
        r.font.name = FONT_CN
        _set_run_ea_font(r, FONT_CN)


MD_PATTERN = r'(\*\*(.+?)\*\*)|(\+\+(.+?)\+\+)|(?<![*])\*(.+?)\*(?!\*)'

def _parse_md_line(line):
    """Split line into (text, bold, italic, underline) segments.
    **bold**  *italic*  ++underline++
    """
    segments = []
    last = 0
    for m in re.finditer(MD_PATTERN, line):
        if m.start() > last:
            segments.append((line[last:m.start()], False, False, False))
        if m.group(1):       # **bold**
            segments.append((m.group(2), True, False, False))
        elif m.group(3):     # ++underline++
            segments.append((m.group(4), False, False, True))
        elif m.group(5):     # *italic*
            segments.append((m.group(5), False, True, False))
        last = m.end()
    if last < len(line):
        segments.append((line[last:], False, False, False))
    return segments


def _set_body(slide, text, left=None, top=None, width=None, height=None):
    """Fill the body area. Keeps existing TextBox 2 (expands it), converts MD to formatting.
    Optional left/top/width/height override the defaults (for non-reading templates)."""
    tb = _find(slide, "TextBox 2")
    if tb is None:
        tb = slide.shapes.add_textbox(Emu(BODY_LEFT), Emu(BODY_TOP),
                                       Emu(BODY_WIDTH), Emu(BODY_HEIGHT))
    else:
        # Keep template's left/top; expand width/height (defaults to Plaque-bounds)
        tbl, tbt = tb.left, tb.top
        tbw = Emu(width if width is not None else BODY_WIDTH)
        tbh = Emu(height if height is not None else BODY_HEIGHT)
        # Compute available height from template's top
        avail_h = 6595533 - (tbt if height is None else 0)
        tbh = Emu(height if height is not None else avail_h)
        tb.left, tb.top, tb.width, tb.height = tbl, tbt, tbw, tbh
    tf = tb.text_frame
    tf.clear()
    tf.word_wrap = True
    # Zero insets so wrap-width matches _BODY_AVAIL_W (= BODY_WIDTH)
    txBody = tb._element.find('{http://schemas.openxmlformats.org/presentationml/2006/main}txBody')
    if txBody is not None:
        bp = txBody.find('{http://schemas.openxmlformats.org/drawingml/2006/main}bodyPr')
        if bp is not None:
            bp.set('lIns', '0')
            bp.set('rIns', '0')
            bp.set('tIns', '0')
            bp.set('bIns', '0')
    idx = 0
    for line in text.split("\n"):
        if not line.strip():
            continue
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.JUSTIFY
        p.space_after = Pt(2)
        pPr = p._p.get_or_add_pPr()
        pPr.set("indent", str(BODY_INDENT))
        segments = _parse_md_line(line)
        for seg_text, bold, italic, underline in segments:
            r = p.add_run()
            r.text = seg_text
            r.font.size = SIZE_BODY
            r.font.color.rgb = COLOR_BODY
            r.font.bold = bold
            r.font.italic = italic
            r.font.underline = underline
            r.font.name = FONT_LATIN
            _set_run_ea_font(r, FONT_CN)
        idx += 1


def _set_side(slide, text, shape_name, left=None, top=None, width=None, height=None, font_size=None, line_sp=None, tab_stops=None):
    print(f"[PPT DEBUG] _set_side shape='{shape_name}', text_len={len(text) if text else 0}")
    s = _find(slide, shape_name)
    if s:
        if left is not None: s.left = Emu(left)
        if top is not None:  s.top = Emu(top)
        if width is not None: s.width = Emu(width)
        if height is not None: s.height = Emu(height)
        tf = s.text_frame
        tf.clear()
        # Zero insets so text uses full textbox width
        txBody = s._element.find('{http://schemas.openxmlformats.org/presentationml/2006/main}txBody')
        if txBody is not None:
            bp = txBody.find('{http://schemas.openxmlformats.org/drawingml/2006/main}bodyPr')
            if bp is not None:
                bp.set('lIns', '0')
                bp.set('rIns', '0')
                bp.set('tIns', '0')
                bp.set('bIns', '0')
        for i, line in enumerate(text.split("\n")):
            if not line.strip():
                continue
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.JUSTIFY
            p.space_after = Pt(2)
            if font_size and line_sp:
                p.line_spacing = Pt(int(font_size * line_sp))
            else:
                p.line_spacing = Pt(24)
            if tab_stops:
                pPr = p._p.get_or_add_pPr()
                from lxml import etree as _lx_side
                tl = pPr.find('{http://schemas.openxmlformats.org/drawingml/2006/main}tabLst')
                if tl is None:
                    tl = _lx_side.SubElement(pPr, '{http://schemas.openxmlformats.org/drawingml/2006/main}tabLst')
                for ts in tab_stops:
                    tab = _lx_side.SubElement(tl, '{http://schemas.openxmlformats.org/drawingml/2006/main}tab')
                    tab.set('pos', str(ts))
                    tab.set('algn', 'l')
            for seg_text, bold, italic, underline in _parse_md_line(line):
                r = p.add_run()
                r.text = seg_text
                r.font.size = Pt(font_size) if font_size else SIZE_BODY
                r.font.color.rgb = COLOR_BODY
                r.font.bold = bold
                r.font.italic = italic
                r.font.underline = underline
                r.font.name = FONT_LATIN
                _set_run_ea_font(r, FONT_CN)


# ── Tab-stop helpers ────────────────────────────────────────

_QNS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _add_tab_stops(pPr, n_cols):
    """Add tab stops to a paragraph for n_cols-per-row layout."""
    step = BODY_WIDTH // n_cols
    tabLst = etree.SubElement(pPr, f"{{{_QNS}}}tabLst")
    for ci in range(1, n_cols):
        t = etree.SubElement(tabLst, f"{{{_QNS}}}tab")
        t.set("pos", str(step * ci))
        t.set("algn", "l")


def _set_questions(slide, lines):
    """Fill body area with question text. `lines` is list of (text, n_cols).
    Questions bold+title-color; options normal; tab stops for n_cols>1."""
    tb = _find(slide, "TextBox 2")
    if tb is None:
        tb = slide.shapes.add_textbox(Emu(BODY_LEFT), Emu(BODY_TOP),
                                       Emu(BODY_WIDTH), Emu(BODY_HEIGHT))
    else:
        tbl, tbt = tb.left, tb.top
        avail_h = 6595533 - tbt
        tb.left, tb.top, tb.width, tb.height = tbl, tbt, Emu(BODY_WIDTH), Emu(avail_h)
    tf = tb.text_frame
    tf.clear()
    tf.word_wrap = True
    txBody = tb._element.find('{http://schemas.openxmlformats.org/presentationml/2006/main}txBody')
    if txBody is not None:
        bp = txBody.find('{http://schemas.openxmlformats.org/drawingml/2006/main}bodyPr')
        if bp is not None:
            bp.set('lIns', '0')
            bp.set('rIns', '0')
            bp.set('tIns', '0')
            bp.set('bIns', '0')
    first = True
    for text, n_cols in lines:
        if not text.strip():
            continue
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = PP_ALIGN.JUSTIFY
        p.space_after = Pt(2)
        pPr = p._p.get_or_add_pPr()
        pPr.set("indent", "0")
        if n_cols > 1:
            _add_tab_stops(pPr, n_cols)
        is_question = text.strip() and text.strip()[0].isdigit()
        for seg_text, bold, italic, underline in _parse_md_line(text):
            r = p.add_run()
            r.text = seg_text
            r.font.size = SIZE_BODY
            if is_question:
                r.font.bold = True
                r.font.color.rgb = COLOR_TITLE
            else:
                r.font.bold = bold
                r.font.color.rgb = COLOR_BODY
            r.font.italic = italic
            r.font.underline = underline
            r.font.name = FONT_LATIN
            _set_run_ea_font(r, FONT_CN)


# ── Slide clone / delete ─────────────────────────────────────

def _clone(prs, template_idx):
    print(f"[PPT DEBUG] _clone template_idx={template_idx}, total_slides={len(prs.slides)}")
    src = prs.slides[template_idx]
    layout = src.slide_layout
    new_slide = prs.slides.add_slide(layout)
    for s in list(new_slide.shapes):
        s._element.getparent().remove(s._element)
    print(f"[PPT DEBUG] _clone copying {len(src.shapes)} shapes from template #{template_idx}")
    for s in src.shapes:
        try:
            new_slide.shapes._spTree.append(copy.deepcopy(s._element))
        except Exception as e:
            print(f"[PPT DEBUG] _clone WARNING: failed to copy shape '{s.name}' (type={s.shape_type}): {e}")
    for _, rel in src.part.rels.items():
        if "image" in rel.reltype or "media" in rel.reltype:
            try:
                new_slide.part.rels.get_or_add(rel.reltype, rel.target_part)
            except Exception:
                pass
    return new_slide


def _delete_template_slides(prs, count=TEMPLATE_COUNT):
    print(f"[PPT DEBUG] _delete_template_slides count={count}, current_slides={len(prs.slides)}")
    ns = {"r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    for _ in range(count):
        sld = prs.slides._sldIdLst[0]
        rId = sld.get(etree.QName(ns["r"], "id"))
        if rId:
            try:
                prs.part.drop_rel(rId)
            except Exception:
                pass
        prs.slides._sldIdLst.remove(sld)


# ── Slide filler ─────────────────────────────────────────────

def _fill(slide, title, body, side_text=None, side_shape=None):
    _set_title(slide, title)
    _set_body(slide, _strip_md(body))
    if side_text and side_shape:
        _set_side(slide, _strip_md(side_text), side_shape)


def _gen_section(prs, template_idx, title, text, side_text=None, side_shape=None):
    chunks = _split_body(text)
    slides = []
    for ci, chunk in enumerate(chunks):
        cside = side_text
        s = _clone(prs, template_idx)
        _fill(s, title, chunk, side_text=cside, side_shape=side_shape)
        slides.append(s)
    return slides


# ── Content formatters ───────────────────────────────────────

def _fmt_passage_text(p):
    """Format a reading passage (text only, no questions)."""
    return _strip_md(p.get("text", ""))


def _fmt_passage_questions(p, start_num):
    """Format reading questions with global numbering starting at start_num.
    Returns list of question-groups. Each group is [(text, n_cols), ...].
    """
    groups = []
    for qi, q in enumerate(p.get("questions", [])):
        qid = q.get("id", start_num + qi)
        group = [(f"{qid}. {q.get('question', '')}", 1)]
        group.extend(_pack_opts(q.get("options", [])))
        groups.append(group)
    return groups


def _fmt_seven(data):
    """Return (body_text, opts_text) for seven-choices."""
    body = _strip_md(data.get("text", ""))
    opts = "\n".join(f"{chr(65+i)}. {opt}" for i, opt in enumerate(data.get("options", [])))
    return body, _strip_md(opts)


def _parse_cloze_blanks(text):
    """Parse cloze text into (paragraph, [blank_numbers]) list."""
    import re
    result = []
    for p in text.split("\n"):
        p = p.strip()
        if not p:
            continue
        # Match both formats: "41.______" and "___21___"
        blanks = re.findall(r'(\d+)\.\s*_{3,}|_{3,}(\d+)_{3,}', p)
        nums = []
        for a, b in blanks:
            nums.append(int(a or b))
        result.append((p, nums))
    return result


def _fmt_cloze_opt(opt_str, qid):
    """Format one cloze option line with question number + tab-aligned ABCD.
    e.g. '41. A. security\tB. achievement\tC. belonging\tD. responsibility'"""
    import re
    parts = re.findall(r'[A-D]\.\s+.*?(?=\s+[A-D]\.\s|$)', opt_str)
    return f"{qid}. " + "\t".join(parts)


def _fmt_grammar(data):
    return _strip_md(data.get("text", ""))


def _set_writing(slide, data):
    """Fill the writing template with structured sections."""
    tb = _find(slide, "TextBox 2")
    if tb is None:
        return
    tbl, tbt = tb.left, tb.top
    avail_h = 6595533 - tbt
    tb.left, tb.top, tb.width, tb.height = tbl, tbt, Emu(BODY_WIDTH), Emu(avail_h)
    tf = tb.text_frame
    tf.clear()
    tf.word_wrap = True
    txBody = tb._element.find('{http://schemas.openxmlformats.org/presentationml/2006/main}txBody')
    if txBody is not None:
        bp = txBody.find('{http://schemas.openxmlformats.org/drawingml/2006/main}bodyPr')
        if bp is not None:
            bp.set('lIns', '0')
            bp.set('rIns', '0')
            bp.set('tIns', '0')
            bp.set('bIns', '0')

    from pptx.enum.text import PP_ALIGN as _ALIGN

    def _add_run(p, text, bold=False):
        r = p.add_run()
        r.text = text
        r.font.size = SIZE_BODY
        r.font.color.rgb = COLOR_BODY
        r.font.bold = bold
        r.font.name = FONT_LATIN
        _set_run_ea_font(r, FONT_CN)
        return r

    def _add_with_md(p, text):
        for seg_text, bold, italic, underline in _parse_md_line(text):
            r = p.add_run()
            r.text = seg_text
            r.font.size = SIZE_BODY
            r.font.color.rgb = COLOR_BODY
            r.font.bold = bold
            r.font.italic = italic
            r.font.underline = underline
            r.font.name = FONT_LATIN
            _set_run_ea_font(r, FONT_CN)

    idx = 0

    # 1. Topic (with body indent, MD formatting)
    for line in data.get("topic", "").split("\n"):
        if not line.strip():
            continue
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.alignment = _ALIGN.JUSTIFY
        p.space_after = Pt(2)
        pPr = p._p.get_or_add_pPr()
        pPr.set("indent", str(BODY_INDENT))
        _add_with_md(p, line)
        idx += 1

    # 2. 注意 paragraph (首行缩进) — after topic
    _note = "注意：\n1. 写作词数应为80个左右；\n2. 请按如下格式在答题卡的相应位置作答。"
    for nline in _note.split("\n"):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.alignment = _ALIGN.JUSTIFY
        p.space_after = Pt(2)
        pPr = p._p.get_or_add_pPr()
        pPr.set("indent", str(BODY_INDENT))
        _add_with_md(p, nline)
        idx += 1

    # 3. Title (bold, centered, no indent) — if present
    title = data.get("title")
    if title:
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.alignment = _ALIGN.CENTER
        p.space_after = Pt(2)
        _add_run(p, title, bold=True)
        idx += 1

    # 3. Salutation (no indent) — if present
    sal = data.get("salutation")
    if sal:
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.space_after = Pt(2)
        _add_run(p, sal)
        idx += 1

    # 4. Opening (no indent) — if present
    opn = data.get("opening")
    if opn:
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.alignment = _ALIGN.JUSTIFY
        p.space_after = Pt(2)
        pPr = p._p.get_or_add_pPr()
        pPr.set("indent", str(BODY_INDENT))
        _add_run(p, opn)
        idx += 1

    # 5. Two underscore lines (no indent) — always before closing, or at end
    for _ in range(2):
        p = tf.add_paragraph()
        p.space_after = Pt(2)
        _add_run(p, "_" * 71)
        idx += 1

    # 6. Closing (right-align, no indent) — if present
    cls = data.get("closing")
    if cls:
        for line in cls.split("\n"):
            p = tf.add_paragraph()
            p.alignment = _ALIGN.RIGHT
            p.space_after = Pt(2)
            _add_run(p, line)
            idx += 1


def _set_continuation_reading(slide, data):
    """Fill reading-material slides (intro line + passage, no indent on intro)."""
    tb = _find(slide, "TextBox 2")
    if tb is None:
        return
    tbl, tbt = tb.left, tb.top
    avail_h = 6595533 - tbt
    tb.left, tb.top, tb.width, tb.height = tbl, tbt, Emu(BODY_WIDTH), Emu(avail_h)
    tf = tb.text_frame
    tf.clear()
    tf.word_wrap = True
    txBody = tb._element.find('{http://schemas.openxmlformats.org/presentationml/2006/main}txBody')
    if txBody is not None:
        bp = txBody.find('{http://schemas.openxmlformats.org/drawingml/2006/main}bodyPr')
        if bp is not None:
            bp.set('lIns', '0')
            bp.set('rIns', '0')
            bp.set('tIns', '0')
            bp.set('bIns', '0')

    from pptx.enum.text import PP_ALIGN as _ALIGN

    def _add_with_md(p, text):
        for seg_text, bold, italic, underline in _parse_md_line(text):
            r = p.add_run()
            r.text = seg_text
            r.font.size = SIZE_BODY
            r.font.color.rgb = COLOR_BODY
            r.font.bold = bold
            r.font.italic = italic
            r.font.underline = underline
            r.font.name = FONT_LATIN
            _set_run_ea_font(r, FONT_CN)

    idx = 0

    # Intro line (only on first page — passed via data["_intro"])
    intro = data.get("_intro", "")
    if intro:
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.alignment = _ALIGN.JUSTIFY
        p.space_after = Pt(2)
        _add_with_md(p, intro)
        idx += 1

    # Reading paragraphs (indent)
    for para in data.get("_paras", data.get("text", "")).split("\n"):
        para = para.strip()
        if not para:
            continue
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.alignment = _ALIGN.JUSTIFY
        p.space_after = Pt(2)
        pPr = p._p.get_or_add_pPr()
        pPr.set("indent", str(BODY_INDENT))
        _add_with_md(p, para)
        idx += 1


def _set_continuation_prompts(slide, data):
    """Fill the continuation writing prompts slide."""
    tb = _find(slide, "TextBox 2")
    if tb is None:
        return
    tbl, tbt = tb.left, tb.top
    avail_h = 6595533 - tbt
    tb.left, tb.top, tb.width, tb.height = tbl, tbt, Emu(BODY_WIDTH), Emu(avail_h)
    tf = tb.text_frame
    tf.clear()
    tf.word_wrap = True
    txBody = tb._element.find('{http://schemas.openxmlformats.org/presentationml/2006/main}txBody')
    if txBody is not None:
        bp = txBody.find('{http://schemas.openxmlformats.org/drawingml/2006/main}bodyPr')
        if bp is not None:
            bp.set('lIns', '0')
            bp.set('rIns', '0')
            bp.set('tIns', '0')
            bp.set('bIns', '0')

    from pptx.enum.text import PP_ALIGN as _ALIGN

    def _add_run(p, text):
        r = p.add_run()
        r.text = text
        r.font.size = SIZE_BODY
        r.font.color.rgb = COLOR_BODY
        r.font.name = FONT_LATIN
        _set_run_ea_font(r, FONT_CN)
        return r

    def _add_with_md(p, text):
        for seg_text, bold, italic, underline in _parse_md_line(text):
            r = p.add_run()
            r.text = seg_text
            r.font.size = SIZE_BODY
            r.font.color.rgb = COLOR_BODY
            r.font.bold = bold
            r.font.italic = italic
            r.font.underline = underline
            r.font.name = FONT_LATIN
            _set_run_ea_font(r, FONT_CN)

    idx = 0

    # 1. 注意 (no indent)
    p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
    p.space_after = Pt(2)
    _add_run(p, "注意：")
    idx += 1

    # 2. Rule lines (indent)
    for rule in ["1. 续写词数应为150个左右；", "2. 请按如下格式在答题卡的相应位置作答。"]:
        p = tf.add_paragraph()
        p.alignment = _ALIGN.JUSTIFY
        p.space_after = Pt(2)
        pPr = p._p.get_or_add_pPr()
        pPr.set("indent", str(BODY_INDENT))
        _add_run(p, rule)
        idx += 1

    # 3. Format prompts
    prompts = data.get("format", [])
    for pi, prompt in enumerate(prompts):
        # Prompt hint line (indent)
        p = tf.add_paragraph()
        p.alignment = _ALIGN.JUSTIFY
        p.space_after = Pt(2)
        pPr = p._p.get_or_add_pPr()
        pPr.set("indent", str(BODY_INDENT))
        _add_with_md(p, prompt)
        idx += 1
        # Two underscore rows
        for _ in range(2):
            p = tf.add_paragraph()
            p.space_after = Pt(2)
            _add_run(p, "_" * 71)
            idx += 1


def _fmt_listening(data):
    out = ["第一节  短对话（共5小题）"]
    for item in data.get("section1", []):
        out.append(item.get("question", ""))
        for oi, opt in enumerate(item.get("options", [])):
            out.append(f"  {chr(65+oi)}. {opt}")
    out.append("第二节  长对话 / 独白（共15小题）")
    for grp in data.get("section2", []):
        sid, eid = grp.get("start_id", "?"), grp.get("end_id", "?")
        out.append(f"听第{sid}至{eid}段材料，回答第{sid}至{eid}题。")
        for item in grp.get("items", []):
            out.append(item.get("question", ""))
            for oi, opt in enumerate(item.get("options", [])):
                out.append(f"  {chr(65+oi)}. {opt}")
    return _strip_md("\n".join(out))


# ── Main pipeline ────────────────────────────────────────────

def build_pdf_pptx(json_data=None, output_path=None):
    print(f"[PPT DEBUG] Building PPTX, data keys: {list(json_data.keys()) if isinstance(json_data, dict) else type(json_data)}")
    # ── Load data ──
    if json_data is None:
        with open(DEFAULT_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
    elif isinstance(json_data, str):
        with open(json_data, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json_data

    prs = Presentation(TEMPLATE)
    print(f"[PPT DEBUG] Template loaded: {len(prs.slides)} slides")

    # ── Title slide ──
    print("[PPT DEBUG] Cloning title slide...")
    title_slide = _clone(prs, T["title"])
    tb = _find(title_slide, "TextBox 6")
    if tb:
        tf = tb.text_frame
        tf.clear()
        p1 = tf.paragraphs[0]; p1.alignment = PP_ALIGN.LEFT
        r1 = p1.add_run(); r1.text = data.get("source", "试卷来源")
        r1.font.size = SIZE_SOURCE; r1.font.color.rgb = _PptRGB(0, 0, 0)
        r1.font.name = FONT_CN; _set_run_ea_font(r1, FONT_CN)
        p2 = tf.add_paragraph()
        r2 = p2.add_run(); r2.text = "英语"
        r2.font.size = SIZE_ENGLISH; r2.font.bold = True
        r2.font.color.rgb = _PptRGB(0, 0, 0)
        r2.font.name = FONT_CN; _set_run_ea_font(r2, FONT_CN)

    # ── Reading ──
    reading = data.get("reading", {})
    qid = 21   # first reading question number after listening (1-20)
    for pk in ["passageA", "passageB", "passageC", "passageD"]:
        p = reading.get(pk)
        if not p:
            continue
        label = f"{pk[-1].upper()} 篇阅读"
        # Passage text slides — split at paragraph boundaries
        for chunk in _split_body(_fmt_passage_text(p)):
            s = _clone(prs, T["reading"])
            _set_title(s, label)
            _set_body(s, chunk)
        # Questions slides — visual-line split, same 14-line limit as Plaque
        MAX_Q_LINES = 14
        q_groups = _fmt_passage_questions(p, qid)
        if q_groups:
            slides_lines = []
            cur, cur_vl = [], 0
            for group in q_groups:
                g_vl = sum(_visual_lines(t, _BODY_AVAIL_W) for t, _ in group)
                if cur_vl + g_vl > MAX_Q_LINES and cur:
                    slides_lines.append(cur)
                    cur, cur_vl = list(group), g_vl
                else:
                    cur.extend(group)
                    cur_vl += g_vl
            if cur:
                slides_lines.append(cur)
            for lines in slides_lines:
                s = _clone(prs, T["reading"])
                print(f"[PPT DEBUG] Cloned reading slide for {pk}")
                _set_title(s, label)
                _set_questions(s, lines)
        qid += len(p.get("questions", []))

    # ── Seven-choices ──
    sc = data.get("seven_choices")
    if sc:
        body, opts = _fmt_seven(sc)
        # Split body at 13 lines using narrower left-column width
        SEVEN_MAX = 15
        SEVEN_BODY_LEFT = 609601
        SEVEN_BODY_TOP = 900000
        SEVEN_BODY_WIDTH = 6771540
        SEVEN_BODY_HEIGHT = 5695533
        SEVEN_BODY_AVAIL = SEVEN_BODY_WIDTH  # wrap width (no insets after lIns=0)
        SEVEN_SIDE_LEFT = 7675036
        SEVEN_SIDE_TOP = 900000
        SEVEN_SIDE_WIDTH = 4076698
        SEVEN_SIDE_HEIGHT = 5695533
        # Set explicit 100% line spacing so height calculation matches rendering
        SIDE_LN_PCT = 1.0
        # Auto-size side font if options overflow Plaque
        opt_font_pt = 24
        while opt_font_pt >= 14:
            total_h = 0
            for line in opts.split("\n"):
                if not line.strip():
                    continue
                w24 = _opt_text_width(line)
                vl = max(1, (w24 * opt_font_pt // 24 + SEVEN_SIDE_WIDTH - 1) // SEVEN_SIDE_WIDTH)
                total_h += vl * opt_font_pt * 12700 * SIDE_LN_PCT
            total_h += (opts.count("\n") + 1) * 2 * 12700
            if total_h <= SEVEN_SIDE_HEIGHT:  # ≤ full textbox height (tIns/bIns zeroed later)
                break
            opt_font_pt -= 1
        paras = [t for t in body.split("\n") if t.strip()]
        chunks, cur, cur_vl = [], [], 0
        for p in paras:
            pl = _visual_lines(p, SEVEN_BODY_AVAIL)
            if cur_vl + pl > SEVEN_MAX and cur:
                chunks.append("\n".join(cur))
                cur, cur_vl = [p], pl
            else:
                cur.append(p)
                cur_vl += pl
        if cur:
            chunks.append("\n".join(cur))

        for chunk in chunks:
            print("[PPT DEBUG] Cloning seven_choices slide...")
            s = _clone(prs, T["seven"])
            _set_title(s, "七选五")
            _set_body(s, chunk,
                      left=SEVEN_BODY_LEFT, top=SEVEN_BODY_TOP,
                      width=SEVEN_BODY_WIDTH, height=SEVEN_BODY_HEIGHT)
            _set_side(s, opts, "TextBox 1",
                      left=SEVEN_SIDE_LEFT, top=SEVEN_SIDE_TOP,
                      width=SEVEN_SIDE_WIDTH, height=SEVEN_SIDE_HEIGHT,
                      font_size=opt_font_pt, line_sp=SIDE_LN_PCT)

    # ── Cloze ──
    cloze_data = data.get("cloze")
    if cloze_data:
        import re as _re_cloze
        text = _strip_md(cloze_data.get("text", ""))
        opts_list = cloze_data.get("options", [])
        parsed = _parse_cloze_blanks(text)

        # Cloze template dimensions
        CLOZE_BODY_L = 609600
        CLOZE_BODY_T = 962609
        CLOZE_BODY_W = 10972799
        CLOZE_BODY_H = 3217735   # top to separator (4180344 - 962609)
        CLOZE_SIDE_L = 654127
        CLOZE_SIDE_T = 4180344
        CLOZE_SIDE_W = 10812450
        CLOZE_SIDE_H = 2415189   # separator to Plaque bottom

        CLOZE_MAX_BODY = 8
        CLOZE_MAX_SIDE = 7

        # Paginate: natural paragraphs, ≤8 body lines, ≤6 blanks
        pages = []
        cur_body, cur_blanks, cur_vl = [], [], 0
        for para_text, blanks in parsed:
            p_vl = _visual_lines(para_text, CLOZE_BODY_W)
            p_nb = len(blanks)
            overflow = (cur_vl + p_vl > CLOZE_MAX_BODY) or (len(cur_blanks) + p_nb > CLOZE_MAX_SIDE)
            if overflow and cur:
                pages.append((cur_body, cur_blanks))
                cur_body, cur_blanks, cur_vl = [para_text], list(blanks), p_vl
            else:
                cur_body.append(para_text)
                cur_blanks.extend(blanks)
                cur_vl += p_vl
        if cur:
            pages.append((cur_body, cur_blanks))

        print(f"[PPT DEBUG] cloze_data keys: {list(cloze_data.keys())}, opts_list len={len(opts_list)}")
        print(f"[PPT DEBUG] cloze raw text (first 200): {text[:200]}")
        parsed = _parse_cloze_blanks(text)
        print(f"[PPT DEBUG] parsed paragraphs: {len(parsed)}, blanks per para: {[blanks for _, blanks in parsed]}")
        for body_lines, blank_nums in pages:
            print(f"[PPT DEBUG] Cloze page: blank_nums={blank_nums}, body_lines={len(body_lines)}")
            s = _clone(prs, T["cloze"])
            _set_title(s, "完形填空")
            _set_body(s, "\n".join(body_lines),
                      left=CLOZE_BODY_L, top=CLOZE_BODY_T,
                      width=CLOZE_BODY_W, height=CLOZE_BODY_H)
            opt_lines = []
            for i, qid in enumerate(sorted(blank_nums)):
                opt_str = opts_list[i] if i < len(opts_list) else ""
                print(f"[PPT DEBUG] blank#{i} qid={qid} opt_str={'EMPTY' if not opt_str else opt_str[:60]}")
                formatted = _fmt_cloze_opt(opt_str, qid)
                print(f"[PPT DEBUG]   formatted={formatted[:80]}")
                opt_lines.append(formatted)
            print(f"[PPT DEBUG] opt_lines count={len(opt_lines)}, shape_names=[{', '.join(s.name for s in s.shapes)}]")
            if opt_lines:
                _set_side(s, "\n".join(opt_lines), "TextBox 5",
                          left=CLOZE_SIDE_L, top=CLOZE_SIDE_T,
                          width=CLOZE_SIDE_W, height=CLOZE_SIDE_H,
                          tab_stops=[CLOZE_SIDE_W // 4, CLOZE_SIDE_W // 2,
                                     CLOZE_SIDE_W * 3 // 4])

    # ── Grammar ──
    gram = data.get("grammar")
    if gram:
        for chunk in _split_body(gram.get("text", "")):
            print("[PPT DEBUG] Cloning grammar slide...")
            s = _clone(prs, T["grammar"])
            _set_title(s, "语法填空")
            _set_body(s, chunk)

    # ── Practical writing ──
    writing = data.get("writing")
    if writing:
        topic = writing.get("topic", "")
        chunks = _split_body(topic)
        for pi, chunk in enumerate(chunks):
            print("[PPT DEBUG] Cloning writing slide...")
            s = _clone(prs, T["writing"])
            _set_title(s, "应用文写作")
            if pi == 0:
                _set_writing(s, {**writing, "topic": chunk})
            else:
                _set_body(s, chunk)

    # ── Continuation ──
    cont = data.get("continuation")
    if cont:
        intro_text = "阅读下面材料，根据其内容和所给段落开头语续写两段，使之构成一篇完整的短文。"
        full_text = intro_text + "\n\n" + cont.get("text", "")
        for chunk in _split_body(full_text):
            s = _clone(prs, T["continuation"])
            _set_title(s, "读后续写")
            _set_body(s, chunk)

        # Continuation prompts (new slide, separate)
        print("[PPT DEBUG] Cloning continuation slide...")
        s = _clone(prs, T["continuation"])
        _set_title(s, "读后续写")
        _set_continuation_prompts(s, cont)

    # Listening section intentionally skipped — not converted

    # ── Delete original templates ──
    _delete_template_slides(prs)

    # ── Save ──
    out = output_path or OUTPUT
    prs.save(out)
    print(f"✅ {len(prs.slides)} slides → {os.path.basename(out)}")
    return out


# ── Docx Builders ────────────────────────────────────────

def build_writing_docx(content, filepath):
    """Build a 16开 .docx from markdown content and save to filepath."""
    doc = Document()
    _setup_16k_page(doc)
    _setup_default_style(doc)

    lines = content.split("\n")
    i = 0
    while i < len(lines):
        stripped = lines[i].rstrip()
        if not stripped:
            i += 1
            continue

        lstripped = stripped.lstrip()

        if _is_table_line(stripped):
            i = _parse_table(doc, lines, i)
            continue

        if lstripped.startswith(">"):
            quote_text = lstripped[1:].lstrip()
            p = doc.add_paragraph()
            _set_paragraph_spacing(p)
            p.paragraph_format.left_indent = Cm(0.8)
            _append_inline_runs(p, quote_text, Pt(11), False)
            for run in p.runs:
                run.italic = True
                run.font.color.rgb = RGBColor(80, 80, 80)
            i += 1
            continue

        if lstripped.startswith("```"):
            i += 1
            code_lines = []
            while i < len(lines):
                if lines[i].rstrip().lstrip().startswith("```"):
                    i += 1
                    break
                code_lines.append(lines[i].rstrip())
                i += 1
            if code_lines:
                p = doc.add_paragraph()
                _set_paragraph_spacing(p)
                _append_inline_runs(p, "\n".join(code_lines), Pt(11), False)
            continue

        if re.match(r"^[-*_]{3,}$", lstripped):
            p = doc.add_paragraph()
            _set_paragraph_spacing(p)
            pPr = p._element.get_or_add_pPr()
            pBdr = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            bottom.set(qn("w:val"), "single")
            bottom.set(qn("w:sz"), "6")
            bottom.set(qn("w:space"), "4")
            bottom.set(qn("w:color"), "C0C0C0")
            pBdr.append(bottom)
            pPr.append(pBdr)
            i += 1
            continue

        if lstripped.startswith("# "):
            _add_inline_paragraph(doc, lstripped[2:], bold=True, size=Pt(16), alignment=WD_ALIGN_PARAGRAPH.CENTER)
        elif lstripped.startswith("## "):
            _add_inline_paragraph(doc, lstripped[3:], bold=True, size=Pt(14))
        elif lstripped.startswith("### "):
            _add_inline_paragraph(doc, lstripped[4:], bold=True, size=Pt(13))
        elif lstripped.startswith("#### "):
            _add_inline_paragraph(doc, lstripped[5:], bold=True, size=Pt(12))
        elif lstripped.startswith("- ") or lstripped.startswith("* "):
            _add_inline_paragraph(doc, lstripped[2:], size=Pt(12), style_name="List Bullet")
        elif lstripped[0].isdigit() and ". " in lstripped[:4]:
            _add_inline_paragraph(doc, lstripped.split(". ", 1)[1], size=Pt(12), style_name="List Number")
        else:
            _add_inline_paragraph(doc, stripped, size=Pt(12))

        i += 1

    _add_page_header_footer(doc, "读后续写思路")
    doc.save(filepath)


def build_listening_docx(json_data, filepath):
    """Build listening .docx from AI-organized JSON and save to filepath."""
    doc = Document()
    _setup_16k_page(doc)
    _setup_default_style(doc)

    # --- Section 1 ---
    _add_heading(doc, "第一节", Pt(12))
    _add_p(doc, "听下面5段对话。每段对话后有一个小题，从题中所给的A、B、C三个选项中选出最佳选项。听完每段对话后，你都有10秒钟的时间来回答有关小题和阅读下一小题。每段对话读两遍。",
           ea=FZ_ST, size=W5, indent=True)
    sec1 = json_data.get("section1", [])
    for item in sec1:
        qid = item.get("id", "")
        content = item.get("content", "")
        p = doc.add_paragraph()
        _set_paragraph_spacing(p)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(f"听下面的录音，回答第{qid}小题。")
        _set_run_font(run, ea=FZ_HT, size=W5)
        for sub_line in content.split("\n"):
            sub = sub_line.strip()
            if sub:
                p2 = doc.add_paragraph()
                _set_paragraph_spacing(p2)
                p2.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                _add_content_with_cleanup(p2, sub)

    _add_paragraph(doc, "第一节到此结束。")

    # --- Section 2 ---
    _add_heading(doc, "第二节", Pt(12))
    _add_p(doc, "听下面5段对话或独白。每段对话或独白后有几个小题，从题中所给的A、B、C三个选项中选出最佳选项。听每段对话或独白前，你将有时间阅读各个小题，每小题5秒钟；听完后，各小题将给出5秒钟的作答时间。每段对话或独白读两遍。",
           ea=FZ_ST, size=W5, indent=True)
    sec2 = json_data.get("section2", [])
    sec2_len = len(sec2)
    for idx, item in enumerate(sec2):
        start_id = item.get("start_id", "")
        end_id = item.get("end_id", "")
        content = item.get("content", "")
        is_last = idx == sec2_len - 1

        q_count = end_id - start_id + 1 if isinstance(start_id, int) and isinstance(end_id, int) else 0
        gap = f"、{end_id}" if q_count == 2 else f"至第{end_id}"
        p = doc.add_paragraph()
        _set_paragraph_spacing(p)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(f"听下面的录音，回答第{start_id}{gap}小题。现在你有{5 * q_count}秒的时间回答以下{_num_to_chinese(q_count)}个小题。")
        _set_run_font(run, ea=FZ_HT, size=W5)

        for sub_line in content.split("\n"):
            sub = sub_line.strip()
            if sub:
                p2 = doc.add_paragraph()
                _set_paragraph_spacing(p2)
                p2.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                if is_last:
                    p2.paragraph_format.first_line_indent = Cm(0.74)
                _add_content_with_cleanup(p2, sub)

    _add_paragraph(doc, "听力到此结束。")

    _add_page_header_footer(doc, "听力材料")
    doc.save(filepath)


def build_pdf_docx(json_data, filepath):
    d = json_data
    doc = Document()
    _setup_16k_page(doc)
    _setup_default_style(doc)

    # ── Title: source ──
    source = d.get("source", "")
    if source:
        p = doc.add_paragraph()
        _set_paragraph_spacing(p)
        p.paragraph_format.line_spacing = 1.0
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(source)
        _set_run_font(run, ea=FZ_XBS, size=X2)

    # ── Subject ──
    p = doc.add_paragraph()
    _set_paragraph_spacing(p)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("英语试题")
    _set_run_font(run, ea=FZ_HT, size=X2)

    # ── 注意事项 ──
    _add_p(doc, "注意事项：", ea=FZ_HT, size=W5, alignment=WD_ALIGN_PARAGRAPH.LEFT)
    notes = [
        "答卷前，考生务必将自己的班级、姓名、考号填写在答题卡上。",
        "回答选择题时，选出每小题答案后，用铅笔把答题卡上对应题目的答案标号涂黑。如需改动，用橡皮擦干净后，再选涂其他答案标号。回答非选择题时，将答案写在答题卡上。写在本试卷上无效。",
        "考试结束后，将本试卷和答题卡一并交回。",
    ]
    for i, note in enumerate(notes):
        _add_p(doc, f"{i+1}. {note}", ea=FZ_KT, size=W5, indent=True)

    def _prompt(text):
        _add_p(doc, text, ea=FZ_ST, size=W5, indent=True)

    def _eng(text, indent=True, bold=False, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY):
        _add_p(doc, text, ea=FZ_ST, size=W5, indent=indent, bold=bold, alignment=alignment)

    def _center_label(text):
        _add_p(doc, text, ea=FZ_ST, size=W5, bold=True, alignment=WD_ALIGN_PARAGRAPH.CENTER)

    def _render_text(text):
        """Render text line by line, handling markdown tables."""
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            if not stripped:
                i += 1
                continue
            if _is_table_line(stripped):
                i = _parse_table(doc, lines, i)
            else:
                _eng(stripped, indent=True)
                i += 1

    # ── Listening ──
    listening = d.get("listening", {})
    if listening:
        _add_heading_p(doc, "第一部分 听力（共两节，满分30分）", X4)
        _prompt("做题时，先将答案标在试卷上。录音内容结束后，你将有两分钟的时间将试卷上的答案转涂到答题卡上。")

        sec1 = listening.get("section1", [])
        if sec1:
            _add_heading_p(doc, "第一节（共5小题；每小题1.5分，满分7.5分）", W5)
            _prompt("听下面5段对话。每段对话后有一个小题，从题中所给的A、B、C三个选项中选出最佳选项。听完每段对话后，你都有10秒钟的时间来回答有关小题和阅读下一小题。每段对话读两遍。")
            for i, item in enumerate(sec1):
                _eng(f"{i+1}. {item.get('question', '')}", indent=False)
                _add_options_line(doc, item.get("options", []), 3)

        sec2 = listening.get("section2", [])
        if sec2:
            _add_heading_p(doc, "第二节（共15小题；每小题1.5分，满分22.5分）", W5)
            _prompt("听下面5段对话或独白。每段对话或独白后有几个小题，从题中所给的A、B、C三个选项中选出最佳选项。听每段对话或独白前，你将有时间阅读各个小题，每小题5秒钟；听完后，各小题将给出5秒钟的作答时间。每段对话或独白读两遍。")
            for grp in sec2:
                sid = grp.get("start_id", 0)
                eid = grp.get("end_id", 0)
                items = grp.get("items", [])
                if not items and grp.get("question"):
                    items = [grp]
                if sid and eid and items:
                    gap = f"、{eid}" if eid - sid == 1 else f"至第{eid}"
                    _add_p(doc, f"听下面的录音，回答第{sid}{gap}小题。",
                           ea=FZ_HT, size=W5, alignment=WD_ALIGN_PARAGRAPH.LEFT)
                for qi, q in enumerate(items):
                    n = sid + qi if sid else qi + 6
                    _eng(f"{n}. {q.get('question', '')}", indent=False)
                    _add_options_line(doc, q.get("options", []), 3)

    # ── Reading ──
    reading = d.get("reading", {})
    if reading:
        _add_heading_p(doc, "第二部分 阅读（共两节，满分50分）", X4)
        _add_heading_p(doc, "第一节（共15小题；每小题2.5分，满分37.5分）", W5)
        _prompt("阅读下列短文，从每题所给的A、B、C、D四个选项中选出最佳选项。")

        q_num = 21
        for key in ["passageA", "passageB", "passageC", "passageD"]:
            psg = reading.get(key)
            if not psg:
                continue
            label = key[-1].upper()
            _center_label(label)
            _render_text(psg.get("text", ""))
            for qi, q in enumerate(psg.get("questions", [])):
                _eng(f"{q_num}. {q.get('question', '')}", indent=False)
                _add_options_line(doc, q.get("options", []), 4)
                q_num += 1

    # ── Seven choices ──
    sc = d.get("seven_choices", {})
    if sc:
        _add_heading_p(doc, "第二节（共5小题；每小题2.5分，满分12.5分）", W5)
        _prompt("根据短文内容，从短文后的选项中选出能填入空白处的最佳选项。选项中有两项为多余选项。")
        _render_text(sc.get("text", ""))
        for j, opt in enumerate(sc.get("options", [])):
            _eng(f"{chr(65+j)}. {opt}", indent=1.5)

    # ── Cloze ──
    cloze = d.get("cloze", {})
    if cloze:
        _add_heading_p(doc, "第三部分 语言知识运用（共两节，满分30分）", X4)
        _add_heading_p(doc, "第一节 完形填空（共15小题；每小题1分，满分15分）", W5)
        _prompt("阅读下面短文，从每题所给的A、B、C、D四个选项中选出可以填入空白处的最佳选项。")
        _render_text(cloze.get("text", ""))
        parsed = _parse_cloze_blanks(cloze.get("text", ""))
        blank_nums = []
        for _, nums in parsed:
            blank_nums.extend(nums)
        _add_cloze_options_block(doc, cloze.get("options", []), blank_nums if blank_nums else None)

    # ── Grammar ──
    gram = d.get("grammar", {})
    if gram:
        _add_heading_p(doc, "第二节 语法填空（共10小题；每小题1.5分，满分15分）", W5)
        _prompt("阅读下面短文，在空白处填入1个适当的单词或括号内单词的正确形式。")
        _render_text(gram.get("text", ""))

    # ── Writing ──
    writing = d.get("writing", {})
    continuation = d.get("continuation", {})
    if writing or continuation:
        _add_heading_p(doc, "第四部分 写作（共两节，满分40分）", X4)

    if writing:
        _add_heading_p(doc, "第一节 应用文写作（满分15分）", W5)
        topic = writing.get("topic", "")
        if topic:
            for topic_line in topic.split("\n"):
                line = topic_line.strip()
                if not line:
                    continue
                _prompt(line)
        _prompt("注意：")
        _prompt("1. 写作词数应为80个左右；")
        _prompt("2. 请按如下格式在答题卡的相应位置作答。")
        title = writing.get("title", "")
        if title:
            _eng(title, indent=False, bold=True, alignment=WD_ALIGN_PARAGRAPH.CENTER)
        salutation = writing.get("salutation", "")
        if salutation:
            _eng(salutation, indent=False, alignment=WD_ALIGN_PARAGRAPH.LEFT)
        opening = writing.get("opening", "")
        if opening:
            _eng(opening, indent=True, alignment=WD_ALIGN_PARAGRAPH.LEFT)
        for _ in range(3):
            _add_underline_line(doc)
        closing = writing.get("closing", "")
        if closing:
            for cl_line in closing.split("\n"):
                if cl_line.strip():
                    _eng(cl_line.strip(), indent=False, alignment=WD_ALIGN_PARAGRAPH.RIGHT)

    if continuation:
        _add_heading_p(doc, "第二节 读后续写（满分25分）", W5)
        _prompt("阅读下面材料，根据其内容和所给段落开头语续写两段，使之构成一篇完整的短文。")
        _render_text(continuation.get("text", ""))
        _prompt("注意：")
        _prompt("1. 续写词数应为150个左右；")
        _prompt("2. 请按如下格式在答题卡的相应位置作答。")
        fmt = continuation.get("format", [])
        if isinstance(fmt, list):
            for prompt in fmt:
                _eng(prompt, indent=True)
                for _ in range(3):
                    _add_underline_line(doc)
        else:
            for line in fmt.split("\n"):
                _eng(line.strip() if line.strip() else "", indent=not line.strip().startswith("_"))

    _add_page_header_footer(doc, "英语试卷")
    doc.save(filepath)

