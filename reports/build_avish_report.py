#!/usr/bin/env python3
"""Build Avish's THOA report as PDF + DOCX from avish_report.md (single source of truth).

Flowcharts are drawn with reportlab graphics, rendered to PNG, and embedded
in both the PDF and the DOCX.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD_PATH = ROOT / "avish_report.md"
OUT_DIR = ROOT / "reports"
FIG_DIR = OUT_DIR / "figures"
LOGO_PATH = OUT_DIR / "vit_logo.png"

BODY_FONT = "Times-Roman"
BODY_BOLD = "Times-Bold"
BODY_ITAL = "Times-Italic"
FONT_SIZE = 12
LEADING = round(12 * 1.15, 2)  # 13.8

class Block:
    def __init__(self, kind, text):
        self.kind = kind  # h2, h3, body, bullet, fig, brk
        self.text = text

def parse_md() -> tuple:
    raw = MD_PATH.read_text(encoding="utf-8")
    blocks = []
    for chunk in raw.split("[PAGE BREAK]"):
        for line in chunk.splitlines():
            line = line.rstrip()
            if not line.strip() or line.strip() == "---":
                continue
            if line.startswith("[FIGURE:"):
                blocks.append(Block("fig", line[9:-1].strip()))
            elif line.startswith("### "):
                blocks.append(Block("h3", line[4:]))
            elif line.startswith("## "):
                blocks.append(Block("h2", line[3:]))
            elif line.startswith("- "):
                blocks.append(Block("bullet", line[2:]))
            else:
                blocks.append(Block("body", line))
        blocks.append(Block("brk", ""))
    if blocks and blocks[-1].kind == "brk":
        blocks.pop()

    body_start = next(i for i, b in enumerate(blocks)
                      if b.kind == "h2" and b.text.startswith("Abstract"))
    cover = [b for b in blocks[:body_start] if b.kind == "body"]
    body = blocks[body_start:]
    return cover, body

def fill_cover_text(t: str) -> str:
    return t.replace("[VIT LOGO — top center]", "@LOGO@")

def html_escape(t: str) -> str:
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", t)
    return t

# ----------------------------------------------------------------------------
# Flowcharts: drawn with Pillow -> PNG (no external renderer needed)
# ----------------------------------------------------------------------------
from PIL import Image, ImageFont, ImageDraw

SCALE = 2

_FONT_CACHE = {}

def _font(size, bold=False):
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    candidates = [
        ("/Library/Fonts/Times New Roman.ttf" if not bold else "/Library/Fonts/Times New Roman Bold.ttf", None),
        ("/System/Library/Fonts/Helvetica.ttc", 0 if not bold else 1),
        ("/System/Library/Fonts/Supplemental/Arial.ttf", None),
        ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", None),
    ]
    for path, idx in candidates:
        try:
            f = ImageFont.truetype(path, size * SCALE, index=idx)
            _FONT_CACHE[key] = f
            return f
        except Exception:
            continue
    f = ImageFont.load_default(size * SCALE)
    _FONT_CACHE[key] = f
    return f

BLUE = "#dbeafe"; BLUE_S = "#3b82f6"
GREY = "#e5e7eb"; GREY_S = "#6b7280"
GREEN = "#dcfce7"; GREEN_S = "#16a34a"
AMBER = "#fef3c7"; AMBER_S = "#d97706"
PALE = "#f1f5f9"; PALE_S = "#94a3b8"
INK = "#111827"; LINE = "#374151"

class Canvas:
    """Simple helper over PIL: coordinates in design units, SCALE-scaled output."""
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.img = Image.new("RGB", (w * SCALE, h * SCALE), "white")
        from PIL import ImageDraw
        self.d = ImageDraw.Draw(self.img)

    def box(self, cx, cy, w, h, text, fill=GREY, stroke=GREY_S, size=8, bold=True):
        x0, y0 = (cx - w / 2) * SCALE, (cy - h / 2) * SCALE
        x1, y1 = (cx + w / 2) * SCALE, (cy + h / 2) * SCALE
        self.d.rounded_rectangle([x0, y0, x1, y1], radius=8 * SCALE,
                                 fill=fill, outline=stroke, width=max(1, SCALE))
        lines = text.split("\n")
        lh = size * SCALE * 1.25
        start = (cy * SCALE) - (lh * (len(lines) - 1)) / 2
        for i, ln in enumerate(lines):
            self.d.text((cx * SCALE, start + i * lh), ln, font=_font(size, bold),
                        fill=INK, anchor="mm")

    def arrow(self, x1, y1, x2, y2):
        import math
        s, l = SCALE, 7 * SCALE
        self.d.line([x1 * s, y1 * s, x2 * s, y2 * s], fill=LINE, width=max(1, s))
        ang = math.atan2(y2 - y1, x2 - x1)
        self.d.polygon([(x2 * s, y2 * s),
                        ((x2 - l * math.cos(ang - 0.4)) * s, (y2 - l * math.sin(ang - 0.4)) * s),
                        ((x2 - l * math.cos(ang + 0.4)) * s, (y2 - l * math.sin(ang + 0.4)) * s)],
                       fill=LINE)

    def label(self, x, y, text, size=8, color=INK, bold=True, anchor="mm"):
        self.d.text((x * SCALE, y * SCALE), text, font=_font(size, bold), fill=color, anchor=anchor)

    def note(self, y, text, h=22, fill=PALE, stroke=PALE_S):
        self.box(220, y, 440, h, text, fill=fill, stroke=stroke, size=7.5)

    def save(self, path):
        self.img.save(path)

def fig_thoa_flow():
    c = Canvas(440, 330)
    c.box(220, 310, 210, 34, "Living donor case", fill=AMBER, stroke=AMBER_S)
    c.arrow(220, 293, 220, 276)
    c.box(220, 258, 240, 38, "Near-relative under Section 2(i)?", fill=AMBER, stroke=AMBER_S)
    c.arrow(140, 239, 110, 222)
    c.label(150, 244, "Yes", size=8)
    c.arrow(300, 239, 330, 222)
    c.label(290, 244, "No", size=8)
    c.box(110, 204, 200, 34, "Form 1 (or Form 2 for spouse)", fill=BLUE, stroke=BLUE_S)
    c.box(330, 204, 220, 34, "Form 3 + Form 11 + financial affidavit\n+ police verification", fill=BLUE, stroke=BLUE_S)
    c.arrow(110, 187, 110, 170)
    c.arrow(330, 187, 330, 170)
    c.box(110, 152, 200, 36, "Routine documentation;\ntransplant proceeds", fill=GREEN, stroke=GREEN_S)
    c.box(330, 152, 220, 36, "Authorization Committee inquiry\n(S.9(3)): affection and attachment", fill=GREEN, stroke=GREEN_S)
    c.note(96, "Foreign national involved: additional Form 21 (S.9(1A)) and mandatory committee review")
    c.note(62, "Proposed mapping: rules REL-01 to REL-05. Non-relative and foreign cases always terminate\nin committee review; the system never approves", h=34)
    return c

def fig_pipeline():
    c = Canvas(440, 300)
    c.box(73, 262, 130, 34, "Document upload", fill=PALE, stroke=PALE_S)
    c.arrow(138, 262, 168, 262)
    c.box(220, 262, 150, 34, "Multimodal LLM\nextraction agent", fill=BLUE, stroke=BLUE_S)
    c.arrow(293, 262, 322, 262)
    c.box(367, 262, 146, 34, "Pydantic schema\nvalidation", fill=BLUE, stroke=BLUE_S)
    c.arrow(367, 245, 367, 232)
    c.box(367, 214, 146, 36, "Deterministic rule engine:\n16 rules cited to THOA sections", fill=GREY, stroke=GREY_S)
    c.arrow(367, 196, 367, 184)
    c.box(367, 166, 146, 36, "Flags + explanations\n(no score, no verdict)", fill=GREY, stroke=GREY_S)
    c.arrow(293, 166, 240, 166)
    c.box(165, 166, 150, 36, "Human Authorization\nCommittee decision", fill=GREEN, stroke=GREEN_S)
    c.arrow(90, 148, 90, 130)
    c.box(90, 112, 150, 36, "Immutable audit log", fill=AMBER, stroke=AMBER_S)
    c.label(293, 118, "No LLM anywhere in the decision path; the\nsystem is structurally incapable of approving",
            size=7.5, color="#374151", anchor="lm")
    c.note(76, "AI does extraction only. The decision path is deterministic, traceable, and human-terminated.", h=24)
    return c

def fig_privacy():
    c = Canvas(440, 290)
    c.box(220, 262, 300, 34, "Uploaded documents (consent recorded as a versioned event)", fill=AMBER, stroke=AMBER_S)
    c.arrow(110, 244, 110, 228)
    c.arrow(220, 244, 220, 228)
    c.arrow(330, 244, 330, 228)
    c.box(110, 210, 190, 36, "At rest: AES-256-GCM\nencrypted storage", fill=BLUE, stroke=BLUE_S)
    c.box(220, 210, 190, 36, "In use: masked views\n(XXXX-XXXX-1234)", fill=BLUE, stroke=BLUE_S)
    c.box(330, 210, 190, 36, "In transit: TLS 1.3\nAPI traffic", fill=BLUE, stroke=BLUE_S)
    c.arrow(110, 192, 110, 176)
    c.arrow(220, 192, 220, 176)
    c.arrow(330, 192, 330, 176)
    c.box(220, 158, 420, 34, "Role-based access: reviewers see only assigned cases (least privilege)", fill=GREY, stroke=GREY_S)
    c.arrow(220, 140, 220, 126)
    c.box(220, 108, 420, 34, "Append-only audit log: actor, action, timestamp, immutable", fill=GREEN, stroke=GREEN_S)
    c.note(66, "Retention: configurable, aligned with clinical and legal record-keeping norms; auto-archive after case closure", h=24)
    return c

def render_figures():
    from PIL import ImageFont  # noqa: F401 (ensures import order)
    FIG_DIR.mkdir(exist_ok=True)
    out = {}
    for name, fn in (("thoa_flow", fig_thoa_flow), ("pipeline", fig_pipeline), ("privacy", fig_privacy)):
        c = fn()
        p = FIG_DIR / f"{name}.png"
        c.save(str(p))
        out[name] = p
    return out

# ----------------------------------------------------------------------------
# PDF (reportlab)
# ----------------------------------------------------------------------------
def build_pdf(cover, body, figs) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    PageBreak, Image, Flowable)
    from reportlab.lib import colors

    st_body = ParagraphStyle("body", fontName=BODY_FONT, fontSize=FONT_SIZE,
                             leading=LEADING, alignment=TA_JUSTIFY, spaceAfter=6)
    st_h2 = ParagraphStyle("h2", fontName=BODY_BOLD, fontSize=14, leading=17,
                           spaceBefore=8, spaceAfter=6, textColor=colors.black)
    st_h3 = ParagraphStyle("h3", fontName=BODY_BOLD, fontSize=12.5, leading=15,
                           spaceBefore=6, spaceAfter=4, textColor=colors.black)
    st_bullet = ParagraphStyle("bullet", parent=st_body, leftIndent=18,
                               bulletIndent=6, alignment=TA_LEFT, spaceAfter=5)
    st_cap = ParagraphStyle("caption", fontName=BODY_ITAL, fontSize=10,
                            leading=13, alignment=TA_CENTER, spaceBefore=4, spaceAfter=10,
                            textColor=colors.HexColor("#4b5563"))
    st_cover = ParagraphStyle("cover", fontName=BODY_FONT, fontSize=13,
                              leading=17, alignment=TA_CENTER)
    st_cover_b = ParagraphStyle("cover_b", fontName=BODY_BOLD, fontSize=13,
                                leading=17, alignment=TA_CENTER)

    def footer(canv, doc):
        if doc.page > 1:
            canv.saveState()
            canv.setFont(BODY_FONT, 9)
            canv.drawCentredString(A4[0] / 2, 1.1 * cm, f"Page {doc.page}")
            canv.restoreState()

    pdf = OUT_DIR / "avish_report.pdf"
    doc = SimpleDocTemplate(str(pdf), pagesize=A4,
                            leftMargin=2.5 * cm, rightMargin=2.5 * cm,
                            topMargin=2.5 * cm, bottomMargin=2.2 * cm,
                            title="Legal and Ethical Foundations of an AI-Assisted THOA Compliance System",
                            author="Avish Sharma")
    story = []

    # ---- Cover: balanced full-page layout ----
    story.append(Spacer(1, 1.0 * cm))
    if LOGO_PATH.exists():
        img = Image(str(LOGO_PATH), width=6.0 * cm, height=6.0 * cm)
        img.hAlign = "CENTER"
        story.append(img)
    story.append(Spacer(1, 1.0 * cm))
    story.append(Paragraph("<b>VELLORE INSTITUTE OF TECHNOLOGY</b>",
                           ParagraphStyle("v", parent=st_cover, fontSize=22, leading=27)))
    story.append(Spacer(1, 0.4 * cm))
    for blk in cover:
        line = fill_cover_text(blk.text)
        if "@LOGO@" in line or "VELLORE INSTITUTE OF TECHNOLOGY" in line or not line.strip():
            continue
        if "Project Title:" in line:
            story.append(Spacer(1, 3.6 * cm))
            story.append(Paragraph(html_escape(line),
                                   ParagraphStyle("c2", parent=st_cover, fontSize=16, leading=21, spaceBefore=4)))
            story.append(Spacer(1, 4.2 * cm))
        elif "Submitted by:" in line or "Submitted to:" in line:
            story.append(Paragraph(html_escape(line), st_cover_b))
        else:
            story.append(Paragraph(html_escape(line), st_cover))
    story.append(PageBreak())

    # ---- Body ----
    i = 0
    while i < len(body):
        blk = body[i]
        if blk.kind == "brk":
            story.append(PageBreak())
        elif blk.kind == "fig":
            png = figs.get(blk.text)
            if png:
                img = Image(str(png), width=9.0 * cm, height=9.0 * cm * 0.68)
                img.hAlign = "CENTER"
                story.append(img)
            i += 1
            if i < len(body) and body[i].kind == "body" and body[i].text.startswith("Figure"):
                story.append(Paragraph(html_escape(body[i].text), st_cap))
        elif blk.kind == "h2":
            story.append(Paragraph(html_escape(blk.text), st_h2))
        elif blk.kind == "h3":
            story.append(Paragraph(html_escape(blk.text), st_h3))
        elif blk.kind == "bullet":
            story.append(Paragraph(html_escape(blk.text), st_bullet, bulletText="\u2022"))
        else:
            story.append(Paragraph(html_escape(blk.text), st_body))
        i += 1

    doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=footer)
    return pdf

# ----------------------------------------------------------------------------
# DOCX (python-docx)
# ----------------------------------------------------------------------------
def build_docx(cover, body, figs) -> Path:
    from docx import Document
    from docx.shared import Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    doc = Document()

    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(FONT_SIZE)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    pf = normal.paragraph_format
    pf.line_spacing = 1.2
    pf.space_after = Pt(7)

    for name, size in (("Heading 1", 18), ("Heading 2", 14), ("Heading 3", 12.5)):
        st = doc.styles[name]
        st.font.name = "Times New Roman"
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = RGBColor(0, 0, 0)
        st.paragraph_format.line_spacing = 1.2
        st.paragraph_format.space_before = Pt(12 if name != "Heading 1" else 0)
        st.paragraph_format.space_after = Pt(7)

    sec = doc.sections[0]
    sec.top_margin = Cm(2.5)
    sec.bottom_margin = Cm(2.2)
    sec.left_margin = Cm(2.5)
    sec.right_margin = Cm(2.5)
    sec.different_first_page_header_footer = True
    ftr = sec.footer
    fp = ftr.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = fp.add_run()
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    run._r.append(fld)

    def add_rich(p, text):
        for part in re.split(r"(\*\*.*?\*\*)", text):
            if not part:
                continue
            if part.startswith("**") and part.endswith("**"):
                r = p.add_run(part[2:-2])
                r.bold = True
            else:
                p.add_run(part)

    def cover_para(text="", size=13, bold=False, space_after=6):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = 1.15
        if text:
            r = p.add_run(text)
            r.font.size = Pt(size)
            r.bold = bold
        return p

    # ---- Cover ----
    if LOGO_PATH.exists():
        p = cover_para(space_after=18)
        p.add_run().add_picture(str(LOGO_PATH), width=Cm(5.5))
    else:
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        cell.width = Cm(5.5)
        cp = cell.paragraphs[0]
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = cp.add_run("[ INSERT VIT LOGO HERE ]")
        r.font.size = Pt(9)
        r.italic = True
        r.font.color.rgb = RGBColor(128, 128, 128)
        tcPr = cell._tc.get_or_add_tcPr()
        borders = OxmlElement("w:tcBorders")
        for edge in ("top", "left", "bottom", "right"):
            el = OxmlElement(f"w:{edge}")
            el.set(qn("w:val"), "dashed")
            el.set(qn("w:sz"), "6")
            el.set(qn("w:color"), "808080")
            borders.append(el)
        tcPr.append(borders)

    cover_para("VELLORE INSTITUTE OF TECHNOLOGY", size=22, bold=True, space_after=22)
    for blk in cover:
        line = fill_cover_text(blk.text)
        if "@LOGO@" in line or not line.strip():
            continue
        if "VELLORE INSTITUTE OF TECHNOLOGY" in line:
            continue
        if "Project Title:" in line:
            cover_para("", space_after=24)
            cover_para(line, size=16, bold=True, space_after=26)
        elif "Submitted by:" in line or "Submitted to:" in line:
            cover_para(line, size=13, space_after=8)
        else:
            cover_para(line, size=13, space_after=6)

    doc.add_page_break()

    # ---- Body ----
    i = 0
    while i < len(body):
        blk = body[i]
        if blk.kind == "brk":
            doc.add_page_break()
        elif blk.kind == "fig":
            png = figs.get(blk.text)
            if png:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.add_run().add_picture(str(png), width=Cm(9.0))
            i += 1
            if i < len(body) and body[i].kind == "body" and body[i].text.startswith("Figure"):
                cap = doc.add_paragraph()
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cr = cap.add_run(body[i].text.replace("*", ""))
                cr.italic = True
                cr.font.size = Pt(10)
        elif blk.kind == "h2":
            p = doc.add_heading(level=2)
            add_rich(p, blk.text)
        elif blk.kind == "h3":
            p = doc.add_heading(level=3)
            add_rich(p, blk.text)
        elif blk.kind == "bullet":
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.line_spacing = 1.2
            p.paragraph_format.space_after = Pt(5)
            add_rich(p, blk.text)
        else:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            add_rich(p, blk.text)
        i += 1

    out = OUT_DIR / "avish_report.docx"
    doc.save(str(out))
    return out

def main():
    OUT_DIR.mkdir(exist_ok=True)
    cover, body = parse_md()
    figs = render_figures()
    pdf = build_pdf(cover, body, figs)
    docx = build_docx(cover, body, figs)

    from pypdf import PdfReader
    r = PdfReader(str(pdf))
    total = len(r.pages)
    inference_page = None
    for i, page in enumerate(r.pages, 1):
        text = page.extract_text() or ""
        if "8. Inference" in text:
            inference_page = i
    print(f"PDF: {pdf} | {total} pages | Inference on page {inference_page}")
    print(f"DOCX: {docx}")
    if total != 11 or inference_page != 11:
        print("WARNING: layout is not cover=1 ... inference=11")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
