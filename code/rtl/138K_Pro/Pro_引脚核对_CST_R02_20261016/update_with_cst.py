"""Add the supplied Pro CST to a preserved schematic-only reference."""
from collections import defaultdict
import hashlib
import html
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
BASE = ROOT / "Pro_引脚核对_20261016"
CST = ROOT / "tang_mega_138k-pro_pins.cst"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(headers, rows, cls=""):
    return '<div class="tablewrap"><table class="'+cls+'"><thead><tr>'+''.join('<th>'+html.escape(str(x))+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'


baseline_manifest = json.loads((BASE / 'manifest.json').read_text(encoding='utf-8'))
for entry in baseline_manifest:
    assert sha(BASE / entry['path']) == entry['sha256'], entry['path']
text = CST.read_text(encoding='utf-8-sig')
locations, attributes = {}, {}
other_constraints = []
for number, line in enumerate(text.splitlines(), 1):
    code = line.split('//', 1)[0].strip()
    match = re.fullmatch(r'IO_LOC\s+"([^"]+)"\s+([^;]+);', code)
    if match:
        port, balls = match.groups()
        assert port not in locations, ('duplicate IO_LOC', port)
        locations[port] = {'balls': [x.strip() for x in balls.split(',')], 'line': number}
    match = re.fullmatch(r'IO_PORT\s+"([^"]+)"\s+([^;]+);', code)
    if match:
        port, settings = match.groups()
        assert port not in attributes, ('duplicate IO_PORT', port)
        attributes[port] = {'settings': settings.strip(), 'line': number}
    if code and not code.startswith(('IO_LOC ', 'IO_PORT ')):
        other_constraints.append({'line': number, 'text': code})
assert len(locations) > 100
assert set(attributes) <= set(locations)
by_ball = defaultdict(list)
for port, location in locations.items():
    for position, ball in enumerate(location['balls']):
        by_ball[ball].append((port, position))

data = json.loads((BASE / 'pin_relationships.json').read_text(encoding='utf-8'))
data['revision'] = 'R02_WITH_SUPPLIED_CST'
data['cst_source'] = {'name': CST.name, 'path': str(CST), 'bytes': CST.stat().st_size, 'sha256': sha(CST),
                      'provenance': '用户补充的Pro参考CST；文件未写明PCB修订、完整器件Part或B/C步进，未独立鉴定下载来源',
                      'io_loc_count': len(locations), 'io_port_count': len(attributes), 'other_constraints': other_constraints}
data['sources'].append(data['cst_source'])
matched = 0
for row in data['rows']:
    # The first ball is only an index into the supplied CST, never a silent
    # resolution of conflicting board connectivity.
    ball_match = re.match(r'^([A-Z]+\d+)', row['ball'])
    ball = ball_match.group(1) if ball_match else ''
    entries = by_ball.get(ball, [])
    row['cst_alias'] = '；'.join(port + (f'（差分第{pos+1}球）' if len(locations[port]['balls']) > 1 else '') for port, pos in entries) or '未列'
    row['cst_electrical'] = '；'.join(f'{port}: {attributes[port]["settings"]}' for port, _ in entries if port in attributes) or '未列/不适用'
    row['cst_lines'] = '；'.join(f'IO_LOC L{locations[port]["line"]}' + (f'，IO_PORT L{attributes[port]["line"]}' if port in attributes else '') for port, _ in entries) or '—'
    row['cst_coverage'] = '球位有对应CST项（不自动证明同一物理网络）' if entries else '本CST未覆盖；保留原理图依据'
    if entries:
        matched += 1
    if row['net'] == 'PMOD0_IO1':
        assert locations['pmod_0[5]']['balls'] == ['N26']
        row['ball'] = 'N26（CST+p5一致）'
        row['note'] = '静态映射采用N26：CST pmod_0[5]及底板p5一致；底板p16 J22/9、MIC_D1仍标L22，原件矛盾保留。CST未写PCB版本，实物接线前仍需核版本/通断。与MIC-ARRAY复用。'
        row['source'] = '4071 p5、p16（矛盾）；4072 p5；新增CST L46'
    if row['net'] in ('SDRAM_DM0', 'SDRAM_DM1'):
        row['note'] += ' 新CST pin_header[26]/[27]分别支持L22/M24，但p5跨页网络矛盾仍未解决；不能仅凭CST认定实际铜线连通。'
    if row['net'].startswith('USR_KEY.'):
        row['note'] += ' CST下标不是S编号：S0→key[0]，S1→key[2]，S2→key[1]，S3→key[3]。'
    if row['net'].startswith('USR_LED.'):
        row['note'] += ' CST下标不是LED丝印：LED0→led[1]，LED1→led[0]，LED2..5→led[2..5]。'
    if row['net'] == 'PA_EN' or row['group'] == 'UART':
        assert not entries, ('unexpected new coverage', row['net'])
        row['note'] += ' 本次CST没有该球位/端口约束；迁移工程需根据原理图补齐，禁止把未列当作无需约束。'
    if row['group'] in ('PMOD0', 'PMOD1', 'PMOD2'):
        row['note'] += ' CST pmod_n[]编号按插座行交错排列，不能当作原理图IO编号。'

findings = [
    ['主时钟', 'clk=P16，IO_LOC L3', '与核心板50 MHz U8一致；CST没有指定该端口IO_TYPE，不能把默认推断写成已显式约束。'],
    ['核心复位/按键', 'rst=U4；IO_TYPE=LVCMOS15，BANK_VCCIO=1.5', '对应核心SW5高有效按键，不是底板S0低有效按键；若沿用sys_rst_n需明确反相，或选S0/K16。'],
    ['音频', 'HP_BCK=E22，HP_WS=F24，HP_DIN=G24', '与PT8211 U6一致；BANK_VCCIO=3.3，未显式写IO_TYPE。'],
    ['PMOD0_IO1', 'pmod_0[5]=N26（L46）', 'CST与底板p5一致，静态表采用N26；p16 L22注记与实物版本仍待核。'],
    ['R17候选MIDI', 'pmod_0[1]=R17（L50）', '对应原理图PMOD0_IO3、底板J22/5；不能当作PMOD0_IO1，也不是NEO的PMOD0_IO5。'],
    ['按键下标', 'key[0]=K16；key[1]=G15；key[2]=F15；key[3]=G16', '实物S0/S1/S2/S3分别对应key[0]/key[2]/key[1]/key[3]。'],
    ['LED下标', 'led[0]=R26；led[1]=J14', '实物LED1/LED0分别对应led[0]/led[1]；其余led[2..5]同名。'],
    ['UART与功放', '未列P15、N16、H17，未列uart_tx/pa_en', '不能直接把整份CST用到现有顶层；需要补P15/N16/H17，功放H17高有效逻辑仍须改RTL。'],
    ['HDMI输出', 'tmds_d_p_0[]与tmds_clk_p_0均为LVDS25、BANK_VCCIO=3.3', 'P/N球位与HDMI A原理图一致；这些是参考CST明确属性，不表示新的工程已综合/PnR/STA通过。'],
    ['扩展SDRAM DM', 'pin_header[26]=L22；pin_header[27]=M24', '支持p16标注，但p5的PCIE_WAKE/M.2_GPIO0连线矛盾仍保留；不能升级为实物连通已证。'],
    ['通用示例边界', f'{len(locations)}条IO_LOC、{len(attributes)}条IO_PORT，另有{len(other_constraints)}条实例约束', '包含DDR、LCD、CMOS等示例端口和特定ddr_top_inst层级，不能整份复制进四复音顶层。'],
]
data['cst_findings'] = findings
for conflict in data['conflicts']:
    if conflict[0] == 'PMOD0_IO1':
        conflict[1] = '新增CST pmod_0[5]=N26与4071 p5一致；p16 J22/9、MIC_D1标L22仍矛盾。'
        conflict[2] = '静态候选取N26，保留原件差异；实物版本及通断待确认，不冒称完全解决。'
    if conflict[0] == 'SDRAM_DM0/DM1':
        conflict[1] += ' 新CST pin_header[26]/[27]也标L22/M24，仍不能闭合p5网络。'
data['conflicts'].append(['CST来源与适配版本', '文件未注明PCB修订/完整Part/B或C步进，且UART/PA_EN没有定义。', '记录用户补充来源和SHA；不把该通用CST当作可直接使用的四复音工程约束。'])

assert locations['clk']['balls'] == ['P16']
assert locations['rst']['balls'] == ['U4'] and 'IO_TYPE=LVCMOS15' in attributes['rst']['settings']
assert [locations[p]['balls'] for p in ('HP_BCK', 'HP_WS', 'HP_DIN')] == [['E22'], ['F24'], ['G24']]
assert [locations[f'key[{i}]']['balls'][0] for i in range(4)] == ['K16', 'G15', 'F15', 'G16']
assert locations['led[0]']['balls'] == ['R26'] and locations['led[1]']['balls'] == ['J14']
assert all(ball not in by_ball for ball in ['P15', 'N16', 'H17'])
assert len([r for r in data['rows'] if r['group'].startswith('PMOD') and r['cst_alias'] != '未列']) == 24
assert all('BANK_VCCIO=3.3' in r['cst_electrical'] for r in data['rows'] if r['group'].startswith('PMOD'))
assert all(sha(Path(source['path'])) == source['sha256'] for source in data['sources'])

inventory = [dict(port=port, balls=loc['balls'], io_loc_line=loc['line'],
                  attributes=attributes.get(port), review='参考项枚举；未声称全部外设/DDR均完成原理图核验') for port, loc in locations.items()]
(OUT / 'cst_inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
(OUT / 'pin_relationships.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

body = (BASE / '138K_Pro_引脚关系与适配核对.html').read_text(encoding='utf-8')
body = body.replace('Tang Mega 138K Pro 引脚关系表</h1>', 'Tang Mega 138K Pro 引脚关系表 · CST 补充版 R02</h1>')
body = body.replace('· 核对日期：2026-10-16', '· 核对日期：2026-10-16 · 已纳入用户补充的 Pro CST')
body = body.replace('<a href="#critical">当前工程对应</a>', '<a href="#cst">新增CST核对</a><a href="#critical">当前工程对应</a>')
section = '<section id="cst"><h2>新增CST核对结果</h2><p>这是用户补充的通用Pro引脚参考，不是已经适配四复音顶层的工程CST。原CST未修改，旧版报告保持原字节。</p>' + table(['项目', 'CST明确内容', '核对与边界'], findings) + '</section>'
body = body.replace('<section id="critical">', section+'<section id="critical">')
header = ['接口', '网络', 'FPGA球位', 'Bank', '设计电压', '可接触终点', '底板BTB', '核心板BTB', '电平/复用/限制', '依据（PDF页码）', '新增CST端口与行号', 'CST电气属性（原文）']
keys = ['group', 'net', 'ball', 'bank', 'voltage', 'endpoint', 'dock', 'core', 'note', 'source']
values = [[r[k] for k in keys] + [r['cst_alias']+'；'+r['cst_lines'], r['cst_electrical']] for r in data['rows']]
body, count = re.subn(r'<div class="tablewrap"><table class="pins">.*?</table></div>', lambda _: table(header, values, 'pins'), body, count=1, flags=re.S)
assert count == 1
body = re.sub(r'(<section id="issues"><h2>冲突与待确认</h2>).*?(</section><section id="plan">)',
              lambda m: m.group(1)+table(['项目', '已发现事实/限制', '处理'], data['conflicts'])+m.group(2), body, count=1, flags=re.S)
body = body.replace('<section id="sources"><h2>原件、版本与证据</h2>', '<section id="sources"><h2>原件、版本与证据</h2>'+f'<div class="card"><a href="{CST.as_uri()}">{html.escape(CST.name)}</a><br><span class="small">用户补充；PCB修订/完整器件版本未写明</span><div class="sha">SHA-256 {sha(CST)}</div></div>')
body = body.replace('href="evidence/', 'href="../Pro_引脚核对_20261016/evidence/')
body = body.replace('.pins{min-width:1510px;', '.pins{min-width:2050px;')
(OUT / '138K_Pro_引脚关系与适配核对_CST_R02.html').write_text(body, encoding='utf-8')

baseline_validation = json.loads((BASE / 'validation.json').read_text(encoding='utf-8'))
validation = dict(baseline_validation, revision='R02_WITH_SUPPLIED_CST', old_report_files_unchanged=True,
                  cst_sha256=sha(CST), cst_io_loc_count=len(locations), cst_io_port_count=len(attributes),
                  rows_with_cst_alias=matched, missing_required_cst_balls=['P15', 'N16', 'H17'],
                  pm0_io1='N26 corroborated by CST and BTB schematic; p16 annotation conflict retained',
                  checked_aliases=['clk', 'rst', 'key[0..3]', 'led[0..5]', 'pmod_0..2', 'HP_BCK', 'HP_WS', 'HP_DIN', 'HDMI_A'],
                  unreviewed_scope='Full DDR/LCD/CMOS functionality, timing and physical continuity not verified')
(OUT / 'validation.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
(OUT / '入口说明.txt').write_text('打开138K_Pro_引脚关系与适配核对_CST_R02.html。\n本版补充CST别名、行号、属性及覆盖缺口，旧版报告未覆盖。\nPMOD0_IO1静态取N26（CST+p5一致），p16 L22矛盾保留。\nUART P15/N16和功放H17未在参考CST列出，仍需原理图补齐；功放高有效适配结论不变。\nkey[]、led[]、pmod[]下标不等于原理图IO/板上丝印编号。\n仅静态核对L0，未修改原RTL/CST/.fs，未构建、烧录或实测。\n', encoding='utf-8')
handoff = (BASE / 'M2_待用户转发_尚未送达.txt').read_text(encoding='utf-8')
handoff += '\n\nR02补充（待用户转发，尚未送达）：用户新增tang_mega_138k-pro_pins.cst，SHA='+sha(CST)+f'，静态解析{len(locations)}条IO_LOC/{len(attributes)}条IO_PORT。入口改为chat10/Pro_引脚核对_CST_R02_20261016/138K_Pro_引脚关系与适配核对_CST_R02.html，原报告不覆盖。\n'
handoff += 'CST pmod_0[5]=N26支持p5，PMOD0_IO1候选静态采用N26，p16的L22矛盾仍留待实物确认。key[2]是S1/F15，key[1]是S2/G15；led[1]是LED0/J14，led[0]是LED1/R26；R17是pmod_0[1]，原理图PMOD0_IO3、J22/5。CST rst为U4/LVCMOS15，对应核心高有效按键，不是底板S0。\n'
handoff += '本CST没有P15/N16/H17，不能直接替代现有顶层CST。主时钟/音频/HDMI球位交叉核一致；DM0/DM1的跨页连线矛盾未解决。未请求或执行Pro构建/硬件下载，写集仍仅chat10报告目录，未提交/推送。\n'
(OUT / 'M2_待用户转发_尚未送达.txt').write_text(handoff, encoding='utf-8')
for entry in baseline_manifest:
    assert sha(BASE / entry['path']) == entry['sha256'], entry['path']
print(json.dumps({'io_loc':len(locations), 'io_port':len(attributes), 'other':len(other_constraints), 'table_rows':len(data['rows']), 'matched_rows':matched, 'originals_unchanged':True, 'hardware_run':False}))
