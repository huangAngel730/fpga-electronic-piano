from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "可打开文档"

JOBS = [
    (ROOT / "2026_FPGA_award_rate_topic_analysis.docx", "01_topic_comparison.docx"),
    (ROOT / "高云选题2_实时多音色合成电子乐器引擎分析.docx", "02_topic2_analysis.docx"),
    (ROOT / "高云选题2_提前购买与准备清单.docx", "03_purchase_preparation.docx"),
    (ROOT / "高云选题2_AI全程开发可行性与协作方案.docx", "04_ai_development_workflow.docx"),
    (ROOT / "外设模块采购清单.docx", "05_peripheral_list.docx"),
]


def iter_blocks(document):
    body = document.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


def set_font(run, size=10.5, bold=False, color=None, family="微软雅黑"):
    run.font.name = family
    props = run._element.get_or_add_rPr()
    for key in ("w:ascii", "w:hAnsi", "w:eastAsia"):
        props.rFonts.set(qn(key), family)
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)


def apply_base_styles(document):
    normal = document.styles["Normal"]
    normal.font.name = "微软雅黑"
    normal.font.size = Pt(10.5)
    normal._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "微软雅黑")
    for name, size, color in [
        ("Title", 21, (0, 0, 0)),
        ("Heading 1", 16, (31, 78, 121)),
        ("Heading 2", 13, (47, 84, 114)),
        ("Heading 3", 11, (68, 68, 68)),
    ]:
        style = document.styles[name]
        style.font.name = "微软雅黑"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(*color)
        style._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "微软雅黑")


def safe_style_name(paragraph):
    name = paragraph.style.name if paragraph.style is not None else "Normal"
    allowed = {
        "Normal", "Title", "Subtitle", "Heading 1", "Heading 2", "Heading 3",
        "List Bullet", "List Bullet 2", "List Number", "List Number 2",
    }
    return name if name in allowed else "Normal"


def copy_paragraph(source, target_doc):
    xml = source._p.xml
    if 'w:type="page"' in xml:
        target_doc.add_page_break()
        if not source.text.strip():
            return
    target = target_doc.add_paragraph(style=safe_style_name(source))
    target.alignment = source.alignment
    target.paragraph_format.space_after = Pt(4)
    target.paragraph_format.line_spacing = 1.2
    if not source.text:
        return
    for src_run in source.runs:
        if not src_run.text:
            continue
        run = target.add_run(src_run.text)
        size = src_run.font.size.pt if src_run.font.size else 10.5
        family = "Consolas" if src_run.font.name == "Consolas" else "微软雅黑"
        set_font(run, size=size, bold=bool(src_run.bold), family=family)
    if not target.runs:
        set_font(target.add_run(source.text))


def copy_table(source, target_doc):
    rows = len(source.rows)
    cols = len(source.columns)
    target = target_doc.add_table(rows=rows, cols=cols)
    target.style = "Table Grid"
    target.alignment = WD_TABLE_ALIGNMENT.CENTER
    for row_index, source_row in enumerate(source.rows):
        no_split = OxmlElement("w:cantSplit")
        target.rows[row_index]._tr.get_or_add_trPr().append(no_split)
        for col_index, source_cell in enumerate(source_row.cells):
            cell = target.cell(row_index, col_index)
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if row_index == 0 else WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run(source_cell.text)
            set_font(run, size=8.2, bold=(row_index == 0), color=(255, 255, 255) if row_index == 0 else None)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if row_index == 0:
                shd = OxmlElement("w:shd")
                shd.set(qn("w:fill"), "1F4E79")
                cell._tc.get_or_add_tcPr().append(shd)
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    target.rows[0]._tr.get_or_add_trPr().append(header)
    target_doc.add_paragraph()


def rebuild(source_path, output_path):
    source = Document(source_path)
    target = Document()
    apply_base_styles(target)
    section = target.sections[0]
    section.top_margin = Cm(1.8)
    section.bottom_margin = Cm(1.8)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)
    for block in iter_blocks(source):
        if isinstance(block, Paragraph):
            copy_paragraph(block, target)
        else:
            copy_table(block, target)
    target.core_properties.title = next((p.text for p in target.paragraphs if p.text.strip()), output_path.stem)
    target.core_properties.author = ""
    target.save(output_path)


OUT_DIR.mkdir(exist_ok=True)
created = []
for source_path, output_name in JOBS:
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    output_path = OUT_DIR / output_name
    rebuild(source_path, output_path)
    with ZipFile(output_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError(f"DOCX ZIP validation failed: {output_path}")
    check = Document(output_path)
    if not check.paragraphs and not check.tables:
        raise RuntimeError(f"Rebuilt document is empty: {output_path}")
    created.append(output_path)

index = OUT_DIR / "00_README.txt"
index.write_text(
    "兼容版Word文档\n\n"
    "01_topic_comparison.docx  FPGA赛题对比与得奖率\n"
    "02_topic2_analysis.docx  高云选题二完整分析\n"
    "03_purchase_preparation.docx  提前购买与准备清单\n"
    "04_ai_development_workflow.docx  AI全程开发协作方案\n"
    "05_peripheral_list.docx  简化外设模块采购清单\n\n"
    "这些文件使用短英文文件名和简化OOXML结构，原文件仍保留在上级目录。\n",
    encoding="utf-8",
)

for path in created:
    print(path)
