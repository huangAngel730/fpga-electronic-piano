"""Inspect actual retained report schemas; no hardware conclusions."""
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'preparation_20261005/report_support'))
from check_hdmi_link_report import ReportParser

original = HERE.parent / 'M2_DVI_V0171_originals_20261005/originals/V0171/impl/pnr'
out = {}
for name in ['audio_visual_coexistence_top_tr_content.html', 'audio_visual_coexistence_top.pin.html']:
    parser = ReportParser()
    parser.feed((original / name).read_text(encoding='utf-8'))
    sections = sorted({s for s, r in parser.rows})
    chosen = {s: [r for section, r in parser.rows if section == s][:5]
              for s in sections if s in ['MIN_PULSE_WIDTH_TABLE', 'Pinout_by_Port_Name',
                                         'Total_Negative_Slack_Report', 'Bus_Skew_Report']
              or any(word in s.lower() for word in ['exception', 'cdc', 'uncert', 'bus'])}
    out[name] = {'sections': sections, 'selected_rows': chosen}
(HERE / 'original_report_schema.json').write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
print(json.dumps(out, indent=2))
