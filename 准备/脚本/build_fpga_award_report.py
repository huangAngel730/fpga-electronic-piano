import base64, json
from pathlib import Path
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

B64 = 'eyJ0aXRsZSI6IjIwMjblubRGUEdB5Yib5paw6K6+6K6h6LWb6YGT5b6X5aWW546H5LiO6YCJ6aKY5YiG5p6QIiwiZGF0ZSI6IjIwMjblubQ55pyINuaXpSIsImRpc2NsYWltZXIiOiLor7TmmI7vvJrlrpjmlrnmsqHmnInlhazluIPlkITkvIHkuJrjgIHlkITotZvpopjnmoTmiqXlkI3kurrmlbDlkozojrflpZbkurrmlbDjgILooajkuK3nmoTliIbotZvpopjlvpflpZbnjofvvIzmmK/nu5PlkIjpopjnm67pmr7luqbjgIHlhazlvIDotYTmlpnjgIHmkp7popjnqIvluqbjgIHnoazku7bpo47pmanlkozlm6LpmJ/og4zmma/nu5nlh7rnmoTlhrPnrZbkvLDorqHvvIzkuI3mmK/lrpjmlrnnu5/orqHjgIIiLCJoaXN0b3J5IjpbWyIyMDI05bm0IiwiMzMwOCIsIjY4OSIsIjIwLjglIl0sWyIyMDI15bm0IiwiMzkwMSIsIjc1MiIsIjE5LjMlIl0sWyLkuKTlubTlkIjorqEiLCI3MjA5IiwiMTQ0MSIsIjIwLjAlIl1dLCJoZWFkZXJzIjpbIuaOkuWQjSIsIuWOguWVhiIsIui1m+mimCIsIuS7u+aEj+WbveWutuWlluS8sOiuoSIsIumrmOWlluS4iumZkCIsIuWujOi1m+mjjumZqSIsIuaSnumimOeoi+W6piIsIkFJ5Y+v5om/5ouF5q+U5L6LIl0sInJvd3MiOltbMSwi5piT54G15oCdIiwi6LWb6aKY5Zub77yaRlBHQeWunuaXtuWbvuWDj+i+uee8mOajgOa1iyIsIjM1Je+9njUwJSIsIuS4reetiSIsIuS9jiIsIuaegemrmCIsIjgwJe+9njkwJSJdLFsyLCLlronot68iLCLpgInpopjkuIDvvJpIRE1J5aSa5aqS5L2T5pKt5pS+57O757ufIiwiMzIl772eNDYlIiwi5Lit6auYIiwi5Lit5L2OIiwi5p6B6auYIiwiNzUl772eODUlIl0sWzMsIuWuiei3ryIsIumAiemimOS6jO+8muWunuaXtuaVsOWtl+WbvuWDj+WkhOeQhuezu+e7nyIsIjMwJe+9njQ0JSIsIumrmCIsIuS4reetiSIsIuW+iOmrmCIsIjgwJe+9njkwJSJdLFs0LCLpq5jkupEiLCLpgInpopjkuozvvJrlpJrpn7PoibLlkIjmiJDnlLXlrZDkuZDlmajlvJXmk44iLCIyOCXvvZ40MiUiLCLlvojpq5giLCLkuK3nrYkiLCLkuK3kvY4iLCI4MCXvvZ45MCUiXSxbNSwi5piT54G15oCdIiwi6LWb6aKY5LqM77yaUklTQy1W77yLRlBHQSAyROWbvuW9ouWKoOmAn+W8leaTjiIsIjI3Je+9njQwJSIsIuW+iOmrmCIsIuS4reetiSIsIuS4reetiSIsIjgwJe+9njkwJSJdLFs2LCLlronot68iLCLpgInpopjkuInvvJrlm77lg4/ph4fpm4bljovnvKnkuI7mmbrog73pooTlpITnkIbliqDpgJ8iLCIyNCXvvZ4zOCUiLCLlvojpq5giLCLkuK3pq5giLCLkuK3nrYkiLCI3NSXvvZ44NSUiXSxbNywi57Sr5YWJ5ZCM5YibIiwi6YCJ6aKY5LqM77ya5Lu75oSP6KeS5bqm55W45Y+Y55+r5q2jIiwiMjMl772eMzclIiwi5b6I6auYIiwi5Lit6auYIiwi5Lit5L2OIiwiNzUl772eODUlIl0sWzgsIkFNRCIsIuiHquS4u+mAiemimOi1m+mBk++8iOWInee6p+e7hO+8iSIsIjIyJe+9njM2JSIsIumrmCIsIuS4reetiSIsIuS4reetiSIsIjgwJe+9njkwJSJdLFs5LCLpq5jkupEiLCLpgInpopjkuIDvvJrlrp7ml7blp7/mgIHmjqfliLbns7vnu58iLCIyMiXvvZ4zNSUiLCLpq5giLCLkuK3pq5giLCLkuK3nrYkiLCI2MCXvvZ43NSUiXSxbMTAsIuWuiei3ryIsIumAiemimOWbm++8mumjnum+meezu+WIl1NvQ+aZuuiDveW3peS4muW6lOeUqCIsIjIwJe+9njMzJSIsIumrmCIsIuS4remrmCIsIuS4reetiSIsIjcwJe+9njg1JSJdLFsxMSwi5piT54G15oCdIiwi6Ieq55Sx6YCJ6aKY77ya5byA5pS+5Yib5paw6K6+6K6hIiwiMTgl772eMzIlIiwi5b6I6auYIiwi6KeG6YCJ6aKY6ICM5a6aIiwi5Lit5L2OIiwiNjUl772eODUlIl0sWzEyLCLpq5jkupEiLCLpgInpopjlm5vvvJrlvIDmlL7lnovpopjnm64iLCIxOCXvvZ4zMSUiLCLlvojpq5giLCLop4bpgInpopjogIzlrpoiLCLkuK3kvY4iLCI2NSXvvZ44NSUiXSxbMTMsIue0q+WFieWQjOWImyIsIumAiemimOWbm++8mlNPUEPliJvmlrDlupTnlKgiLCIxOCXvvZ4zMCUiLCLpq5giLCLkuK3pq5giLCLkuK3nrYkiLCI3MCXvvZ44NSUiXSxbMTQsIuWuiei3ryIsIumAiemimOS6lO+8muiHquS4u+WRvemimCIsIjE3Je+9njMwJSIsIuW+iOmrmCIsIuinhumAiemimOiAjOWumiIsIuS4reS9jiIsIjY1Je+9njg1JSJdLFsxNSwi5piT54G15oCdIiwi6LWb6aKY5LiA77yaQUnlrp7ml7bnu5jnlLvvvI/po47moLzljJbop4bpopHmuLLmn5MiLCIxNSXvvZ4yOCUiLCLlvojpq5giLCLpq5giLCLkuK3nrYkiLCI3MCXvvZ44NSUiXSxbMTYsIuaYk+eBteaAnSIsIui1m+mimOS4ie+8muWkmuaooeaAgUFJ5pm66IO957uI56uvIiwiMTQl772eMjclIiwi5b6I6auYIiwi6auYIiwi5Lit562JIiwiNjUl772eODAlIl0sWzE3LCJBTUQiLCLoh6rkuLvpgInpopjotZvpgZPvvIjpq5jnuqfnu4TvvIkiLCIxNCXvvZ4yNiUiLCLlvojpq5giLCLpq5giLCLlvojpq5giLCI3NSXvvZ45MCUiXSxbMTgsIue0q+WFieWQjOWImyIsIumAiemimOS4gO+8mlJJU0MtVuaMh+S7pOmbhkNQVeiuvuiuoSIsIjEyJe+9njI0JSIsIuW+iOmrmCIsIuW+iOmrmCIsIuS4remrmCIsIjgwJe+9njkwJSJdLFsxOSwi57Sr5YWJ5ZCM5YibIiwi6YCJ6aKY5LiJ77ya6auY57qn6L6F5Yqp6am+6am257O757ufIiwiMTAl772eMjIlIiwi5b6I6auYIiwi5p6B6auYIiwi5Lit6auYIiwiNjUl772eODAlIl0sWzIwLCLpq5jkupEiLCLpgInpopjkuInvvJrlhbfouqvmmbrog73mnLrlmajkurrmhJ/nn6XkuI7mjqfliLYiLCIxMCXvvZ4yMiUiLCLlvojpq5giLCLmnoHpq5giLCLkuK3pq5giLCI2MCXvvZ43NSUiXSxbMjEsIkFNRCIsIuWFt+i6q+aZuuiDvei1m+mBkyIsIjgl772eMjAlIiwi5p6B6auYIiwi5p6B6auYIiwi6auYIiwiNjAl772eNzUlIl0sWzIyLCJBTUQiLCJSVEwvSExT5pys5Zyw5pm66IO95L2T6K6+6K6h6LWb6YGTIiwiOCXvvZ4xOCUiLCLmnoHpq5giLCLmnoHpq5giLCLlvojpq5giLCI3NSXvvZ45MCUiXV0sImNvbmNsdXNpb24iOiLoi6XllK/kuIDnm67moIfmmK/ojrflvpfku7vmhI/lm73lrrblpZbvvIzkvJjlhYjpgInmi6nmmJPngbXmgJ3otZvpopjlm5vvvIhGUEdB5a6e5pe25Zu+5YOP6L6557yY5qOA5rWL77yJ77yb5YW25qyh5piv5a6J6Lev6YCJ6aKY5LiA77yISERNSeWkmuWqkuS9k+aSreaUvu+8ieWSjOWuiei3r+mAiemimOS6jO+8iOWunuaXtuaVsOWtl+WbvuWDj+WkhOeQhu+8ieOAgiJ9'

def c(text):
    return text.encode('ascii').decode('unicode_escape')

def style_run(run, size=9, bold=False, color=None):
    run.font.name = 'Microsoft YaHei'
    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)

def cell_text(cell, text, bold=False, color=None, left=False):
    cell.text = ''
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT if left else WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(0)
    style_run(p.add_run(str(text)), 8, bold, color)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

def shade(cell, fill):
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), fill)
    cell._tc.get_or_add_tcPr().append(shd)

data = json.loads(base64.b64decode(B64).decode('utf-8'))
doc = Document()
sec = doc.sections[0]
sec.orientation = WD_ORIENT.LANDSCAPE
sec.page_width, sec.page_height = sec.page_height, sec.page_width
sec.top_margin = sec.bottom_margin = Cm(1.2)
sec.left_margin = sec.right_margin = Cm(1.1)
normal = doc.styles['Normal']
normal.font.name = 'Microsoft YaHei'
normal._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
normal.font.size = Pt(10)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
style_run(p.add_run(data['title']), 20, True, (31, 78, 121))
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
style_run(p.add_run(data['date']), 10, False, (89, 89, 89))
p = doc.add_paragraph()
style_run(p.add_run(data['disclaimer']), 9, False, (192, 80, 77))

p = doc.add_paragraph()
style_run(p.add_run(c(r'\u5386\u5c4a\u603b\u4f53\u5f97\u5956\u7387')), 12, True, (31,78,121))
hist = doc.add_table(rows=1, cols=4)
hist.style = 'Table Grid'
hist.alignment = WD_TABLE_ALIGNMENT.CENTER
hist_headers = [c(r'\u5e74\u4efd'), c(r'\u62a5\u540d\u961f\u4f0d'), c(r'\u83b7\u5956\u961f\u4f0d'), c(r'\u5f97\u5956\u7387')]
for j, h in enumerate(hist_headers):
    shade(hist.cell(0,j), '1F4E79'); cell_text(hist.cell(0,j), h, True, (255,255,255))
for i, row in enumerate(data['history']):
    cells = hist.add_row().cells
    for j, value in enumerate(row): cell_text(cells[j], value, i == 2)

p = doc.add_paragraph()
style_run(p.add_run(c(r'\u5168\u90e8\u8d5b\u9898\u7efc\u5408\u5bf9\u6bd4')), 12, True, (31,78,121))
tbl = doc.add_table(rows=1, cols=8)
tbl.style = 'Table Grid'
tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
tbl.autofit = False
widths = [0.8, 1.4, 7.4, 2.2, 1.4, 1.6, 1.6, 2.0]
for j, h in enumerate(data['headers']):
    shade(tbl.cell(0,j), '1F4E79'); cell_text(tbl.cell(0,j), h, True, (255,255,255))
    tbl.cell(0,j).width = Cm(widths[j])
for row in data['rows']:
    cells = tbl.add_row().cells
    for j, value in enumerate(row):
        cell_text(cells[j], value, j == 3 and row[0] <= 5, None, j == 2)
        cells[j].width = Cm(widths[j])
    if row[0] <= 3:
        for item in cells: shade(item, 'E2F0D9')
    elif row[0] <= 5:
        for item in cells: shade(item, 'FFF2CC')

p = doc.add_paragraph()
style_run(p.add_run(c(r'\u7ed3\u8bba\uff1a')), 10, True, (31,78,121))
style_run(p.add_run(data['conclusion']), 10)

out = Path('2026_FPGA_award_rate_topic_analysis.docx')
doc.save(out)
print(out.resolve())
