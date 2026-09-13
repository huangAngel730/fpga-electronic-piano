import base64, json, shutil
from pathlib import Path
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

B64 = 'eyJoZWFkaW5nIjoi5Lmd44CB5ZCE6LWb6YGT6aKE6K6h5oiQ5pys57uf6K6hIiwiYmFzaXMiOiLkvLDnrpflj6PlvoTvvIjmiKroh7MyMDI25bm0OeaciDbml6XvvInvvJrljZXkvY3kuLrkurrmsJHluIHvvJvpu5jorqTlt7LmnInml6XluLjlvIDlj5HnlLXohJHlkozmma7pgJpIRE1J5pi+56S65Zmo77yM5LiN6K6h5Lq65bel44CB5beu5peF5ZKM5oql5ZCN55u45YWz6LS555So77yb6K6h5YWl5byA5Y+R5p2/44CB6LWb6aKY5LiT55So5pGE5YOP5aS044CB5Lyg5oSf5Zmo44CBREFD44CB55S15py644CB57uT5p6E5Lu2562J44CC5a6e6ZmF6YeH6LSt5bu66K6u6aKd5aSW6aKE55WZMTAl772eMjAl55qE6L+Q6LS544CB5aSH5Lu25ZKM6L+U5bel6aKE566X44CCIiwiaGVhZGVycyI6WyLmjpLlkI0iLCLljoLllYYiLCLotZvpopgiLCLoh6rotK3pooTorqHmiJDmnKwiLCLmiJDmnKznrYnnuqciLCLkuLvopoHph4fotK3pobkiLCLlgJ/nlKgv5bey5pyJ6K6+5aSH5ZCO55qE5oiQ5pysIl0sInJvd3MiOltbMSwi5piT54G15oCdIiwi5a6e5pe25Zu+5YOP6L6557yY5qOA5rWLIiwiMjgwMO+9njQyMDDlhYMiLCLpq5giLCJWRi1UaTYwRjIyNeadv+OAgeaRhOWDj+WktOOAgee6v+adkCIsIuW3suaciS/lgJ/liLDmnb/ljaHlkI7nuqYxNTDvvZ40MDDlhYMiXSxbMiwi5a6J6LevIiwiSERNSeWkmuWqkuS9k+aSreaUvuezu+e7nyIsIjcwMO+9njE0MDDlhYMiLCLkvY4iLCJIWDRTMjBD5p2/44CB5a2Y5YKo5Y2h44CB6Z+z6aKR6L2s5o6lIiwi5YCf5p2/5oiQ5Yqf5ZCO57qmMTAw772eMzAw5YWDIl0sWzMsIuWuiei3ryIsIuWunuaXtuaVsOWtl+WbvuWDj+WkhOeQhuezu+e7nyIsIjEyMDDvvZ4yMjAw5YWDIiwi5LitIiwiSFgxUDM1Qeadv+OAgeaRhOWDj+WktOOAgee6v+adkCIsIuWAn+adv+aIkOWKn+WQjue6pjE1MO+9njQwMOWFgyJdLFs0LCLpq5jkupEiLCLlpJrpn7PoibLlkIjmiJDnlLXlrZDkuZDlmajlvJXmk44iLCI3MDDvvZ4xNTAw5YWDIiwi5L2OIiwiVGFuZyBNZWdhIDYwS+OAgUkyUyBEQUPjgIHkvKDmhJ/lmajjgIHlip/mlL4iLCLlgJ/mnb/miJDlip/lkI7nuqYxNTDvvZ41MDDlhYMiXSxbNSwi5piT54G15oCdIiwiUklTQy1W77yLRlBHQSAyROWbvuW9ouWKoOmAn+W8leaTjiIsIjI3MDDvvZ40MDAw5YWDIiwi6auYIiwiVGk2MEYyMjXmnb/jgIHlrZjlgqjljaHjgIHmjqfliLblmagiLCLkuLvopoHmiJDmnKzmmK/mjIflrprlvIDlj5Hmnb8iXSxbNiwi5a6J6LevIiwi5Zu+5YOP6YeH6ZuG5Y6L57yp5LiO5pm66IO96aKE5aSE55CG5Yqg6YCfIiwiMzAwMO+9njYwMDDlhYMiLCLpq5giLCJGUEdB77yLUkszNTc25byC5p6E5p2/44CB5pGE5YOP5aS044CB5a2Y5YKoIiwi5YCf5p2/5oiQ5Yqf5Y+v6ZmN5L2O57qmMjAwMO+9njQ1MDDlhYMiXSxbNywi57Sr5YWJ5ZCM5YibIiwi5Lu75oSP6KeS5bqm55W45Y+Y55+r5q2jIiwiMTgwMO+9njM1MDDlhYMiLCLkuK3pq5giLCLnm5jlj6Q1MC82Nzbmnb/jgIHmkYTlg4/lpLTjgIHmoIflrprmnb8iLCLlgJ/mnb/miJDlip/lkI7nuqYyMDDvvZ42MDDlhYMiXSxbOCwiQU1EIiwi6Ieq5Li76YCJ6aKY6LWb6YGT77yI5Yid57qn57uE77yJIiwiMTgwMO+9njM1MDDlhYMiLCLkuK3pq5giLCJQWU5RLVoy5oiW5ZCM57qn5p2/44CB5Lyg5oSf5ZmoL+WkluiuviIsIuacieeOsOaIkOadv+aIlui/nOeoi+i1hOa6kOaXtue6pjDvvZ41MDDlhYMiXSxbOSwi6auY5LqRIiwi5a6e5pe25ae/5oCB5o6n5Yi257O757ufIiwiMTAwMO+9njIyMDDlhYMiLCLkuK0iLCJKMjgw5ae/5oCB5o6n5Yi25aWX5Lu244CB5aSH55So57uT5p6E5Lu2Iiwi5YCf5aWX5Lu25oiQ5Yqf5ZCO57qmMTAw772eNDAw5YWDIl0sWzEwLCLlronot68iLCLpo57pvpnns7vliJdTb0Pmmbrog73lt6XkuJrlupTnlKgiLCIyNTAw772eNTUwMOWFgyIsIumrmCIsIumjnum+mVNvQ+adv+OAgeW3peS4muS8oOaEn+WZqOOAgemAmuS/oeaooeWdlyIsIuWFt+S9k+aIkOacrOmaj+W3peS4muWcuuaZr+WPmOWMliJdLFsxMSwi5piT54G15oCdIiwi6Ieq55Sx6YCJ6aKY77ya5byA5pS+5Yib5paw6K6+6K6hIiwiMjgwMO+9njYwMDDlhYMiLCLpq5giLCJUaTYw5bmz5Y+w5Y+K6Ieq6YCJ5Lyg5oSf5ZmoL+aJp+ihjOWZqCIsIumrmOW6puWPluWGs+S6juiHqumAiemimOebriJdLFsxMiwi6auY5LqRIiwi5byA5pS+5Z6L6aKY55uuIiwiNTAw772eMzUwMOWFgyIsIuS4rSIsIlRhbmcvQUNH5p2/5Y+K6Ieq6YCJ5aSW6K6+Iiwi6YCJVGFuZ+Wwj+adv+WPr+aYvuiRl+mZjeaIkOacrCJdLFsxMywi57Sr5YWJ5ZCM5YibIiwiU09QQ+WIm+aWsOW6lOeUqCIsIjEyMDDvvZ4zMDAw5YWDIiwi5Lit6auYIiwiU09QQ+W8gOWPkeW5s+adv+OAgeaRhOWDj+WktC/kvKDmhJ/lmagiLCLoi6XojrflgJ/mnb/mlK/mjIHlj6/kvY7kuo41MDDlhYMiXSxbMTQsIuWuiei3ryIsIuiHquS4u+WRvemimCIsIjYwMO+9njUwMDDlhYMiLCLkuK3pq5giLCLlronot6/mnb/ljaHlj4roh6rpgInlpJborr4iLCLojIPlm7Tlj5blhrPkuo7pgInpopjlkozmnb/ljaHlnovlj7ciXSxbMTUsIuaYk+eBteaAnSIsIkFJ5a6e5pe257uY55S777yP6aOO5qC85YyW6KeG6aKR5riy5p+TIiwiMzAwMO+9njUwMDDlhYMiLCLpq5giLCJUaTYwRjIyNeadv+OAgVNDNDMx5pGE5YOP5aS044CB5pi+56S66ZO+6LevIiwi566X5rOV6LCD6K+V6L+Y6ZyA6KaB6L6D5by6UEPnrpflipsiXSxbMTYsIuaYk+eBteaAnSIsIuWkmuaooeaAgUFJ5pm66IO957uI56uvIiwiMzIwMO+9njU1MDDlhYMiLCLpq5giLCJUaTYw5p2/44CB5pGE5YOP5aS044CB57qi5aSW5rip5bqm5Y+K546v5aKD5Lyg5oSf5ZmoIiwi5Lyg5oSf5Zmo5pWw6YeP5ZKM57uT5p6E5Lu25o6o6auY5oiQ5pysIl0sWzE3LCJBTUQiLCLoh6rkuLvpgInpopjotZvpgZPvvIjpq5jnuqfnu4TvvIkiLCIyNTAw772eODAwMOWFgyIsIumrmCIsIlp5bnEvS3JpYS9WZXJzYWzmnb/lj4rkuJPkuJrlpJborr4iLCLkvb/nlKjpq5jnq69LcmlhL1ZlcnNhbOaXtuaIkOacrOabtOmrmCJdLFsxOCwi57Sr5YWJ5ZCM5YibIiwiUklTQy1W5oyH5Luk6ZuGQ1BV6K6+6K6hIiwiODAw772eMjUwMOWFgyIsIuS4rSIsIuebmOWPpEZQR0Hmnb/jgIHkuIvovb3lmajjgIHkuLLlj6PpmYTku7YiLCLov5znqIvlubPlj7Av5YCf5p2/5pe257qmMO+9njMwMOWFgyJdLFsxOSwi57Sr5YWJ5ZCM5YibIiwi6auY57qn6L6F5Yqp6am+6am257O757ufIiwiMzUwMO+9njgwMDDlhYMiLCLlvojpq5giLCJGUEdB77yLUkszNTY45p2/44CB5aSa6Lev5pGE5YOP5aS044CB5pi+56S6L+WtmOWCqCIsIuWAn+WIsOW8guaehOadv+WQjuS7jemcgOWkmuaRhOWDj+WktOaKleWFpSJdLFsyMCwi6auY5LqRIiwi5YW36Lqr5pm66IO95py65Zmo5Lq65oSf55+l5LiO5o6n5Yi2IiwiMzUwMO+9njgwMDDlhYMiLCLlvojpq5giLCJBQ0c3MjDjgIHmnLrlmajkurrlupXnm5jjgIHnlLXmnLrjgIHkvKDmhJ/lmajjgIHlj6/pgIlSSzM1ODgiLCLmnLrmorDku7blkozlpIfnlKjlmajku7bpnIDpooTnlZnpooTnrpciXSxbMjEsIkFNRCIsIuWFt+i6q+aZuuiDvei1m+mBkyIsIjE2MDAw772eMzAwMDDlhYMiLCLmnoHpq5giLCJSeXplbiBBSSBQQ+OAgUtSMjYwL1BZTlHjgIHmnLrlmajkurrlj4rkvKDmhJ/lmagiLCLoi6VBSSBQQ+WSjOadv+WNoeWdh+WAn+WIsO+8jOe6pjE1MDDvvZ41MDAw5YWDIl0sWzIyLCJBTUQiLCJSVEwvSExT5pys5Zyw5pm66IO95L2T6K6+6K6h6LWb6YGTIiwiMO+9njEwMDDlhYPvvIjkupHotYTmupDvvIkiLCLkvY4v5p6B6auYIiwi5a6Y5pa5Uk9DbeS6kei1hOa6kO+8m+aIluiHquWkhzMyR0LmmL7lrZhBTUQgR1BVIiwi6Ieq5bu6R1BV546v5aKD57qmOTAwMO+9njI1MDAw5YWDIl1dLCJub3RlcyI6WyLmiJDmnKznrYnnuqflj4LogIPvvJrkvY7iiaQxNTAw5YWD77yb5Lit57qmMTUwMO+9njI1MDDlhYPvvJvkuK3pq5jnuqYyNTAw772eMzUwMOWFg++8m+mrmOe6pjM1MDDvvZ44MDAw5YWD77yb5b6I6auY57qmODAwMO+9njE1MDAw5YWD77yb5p6B6auY77yeMTUwMDDlhYPjgIIiLCLlronot6/jgIHpq5jkupHlkozntKvlhYnlkIzliJvmjIfljZflnYfmj5DkvpvkuI3lkIzlvaLlvI/nmoTmnInpmZDmnb/ljaHlgJ/nlKgv55Sz6K+35pSv5oyB77yM5piv5ZCm6I635om55LiN6IO95L2c5Li66aKE566X55qE5ZSv5LiA5YmN5o+Q44CCIiwi5piT54G15oCd5oyH5a6aVGk2MEYyMjXlubPlj7DnmoTlhazlvIDlm73pmYXlvIDlj5HlpZfku7bku7fmoLzovoPpq5jvvIzlm73lhoXotZvkuovmnb/lkozlkIjkvZzmnb/lrp7pmYXku7fmoLzpnIDlkJHmjqjojZDmuKDpgZPor6Lku7fjgIIiLCJBTUQgUlRML0hMU+acrOWcsOaZuuiDveS9k+WPr+S9v+eUqOi1m+S6i+S6kei1hOa6kO+8jOeOsOmHkeaIkOacrOi+g+S9ju+8m+iLpeiHquihjOi0reS5sDMyR0LmmL7lrZhHUFXmiJZBSeW3peS9nOerme+8jOehrOS7tuaIkOacrOS8muaIkOS4uuaJgOacieaWueWQkeS4reacgOmrmOeahOS4gOaho+OAgiIsIuaRhOWDj+WktOOAgeaYvuekuuWZqOOAgVNE5Y2h44CB55S15rqQ44CB56S65rOi5Zmo5ZKM6YC76L6R5YiG5p6Q5Luq5aaC5p6c5a6e6aqM5a6k5bey5pyJ77yM5Y+v5LuO6KGo5Lit5omj6Zmk5a+55bqU6LS555So44CCIl19'

SRC = Path('2026_FPGA_award_rate_topic_analysis.docx')
BACKUP = Path('2026_FPGA_award_rate_topic_analysis_before_cost.docx')

def style_run(run, size=8, bold=False, color=None):
    run.font.name = 'Microsoft YaHei'
    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)

def cell_text(cell, text, bold=False, color=None, left=False, size=7.2):
    cell.text = ''
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT if left else WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    style_run(p.add_run(str(text)), size, bold, color)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

def shade(cell, fill):
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), fill)
    cell._tc.get_or_add_tcPr().append(shd)

if not SRC.exists():
    raise FileNotFoundError(SRC)
data = json.loads(base64.b64decode(B64).decode('utf-8'))
doc = Document(SRC)
if any(p.text.strip() == data['heading'] for p in doc.paragraphs):
    print('Cost section already exists; no changes made.')
    raise SystemExit(0)
shutil.copy2(SRC, BACKUP)

p = doc.add_paragraph()
p.add_run().add_break(WD_BREAK.PAGE)
p = doc.add_paragraph()
style_run(p.add_run(data['heading']), 15, True, (31, 78, 121))
p = doc.add_paragraph()
style_run(p.add_run(data['basis']), 8.5, False, (89, 89, 89))

tbl = doc.add_table(rows=1, cols=7)
tbl.style = 'Table Grid'
tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
tbl.autofit = False
widths = [0.75, 1.4, 4.7, 2.2, 1.35, 5.0, 4.8]
for j, header in enumerate(data['headers']):
    shade(tbl.cell(0,j), '1F4E79')
    cell_text(tbl.cell(0,j), header, True, (255,255,255), size=7.3)
    tbl.cell(0,j).width = Cm(widths[j])
for row in data['rows']:
    cells = tbl.add_row().cells
    for j, value in enumerate(row):
        cell_text(cells[j], value, j == 3, None, j in (2,5,6), 7.0)
        cells[j].width = Cm(widths[j])
    if row[0] <= 3:
        for cell in cells: shade(cell, 'E2F0D9')
    elif row[0] in (21,22):
        for cell in cells: shade(cell, 'FCE4D6')

p = doc.add_paragraph()
style_run(p.add_run('Notes'), 10, True, (31,78,121))
for note in data['notes']:
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_after = Pt(1)
    style_run(p.add_run(note), 8.3)

doc.save(SRC)
print(SRC.resolve())
print(BACKUP.resolve())
