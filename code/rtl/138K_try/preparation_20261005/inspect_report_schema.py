"""Inspect small real reports before implementing their collector."""
from collections import Counter
from pathlib import Path
import json
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'report_support'))
from check_hdmi_link_report import ReportParser
report = HERE / 'toolchain/60K/impl/pnr/tool_probe_tr_content.html'
parser = ReportParser()
parser.feed(report.read_text(encoding='utf-8'))
counts = Counter(section for section, _ in parser.rows)
for section in counts:
    if any(key in section for key in ['Summary', 'Slack', 'Frequency', 'Clock_Report', 'SDC_Report', 'TNS']):
        print(section, counts[section], json.dumps([r for s, r in parser.rows if s == section][:5]))
