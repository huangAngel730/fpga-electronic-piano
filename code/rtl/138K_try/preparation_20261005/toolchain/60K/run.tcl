puts {M3 TOOLCHAIN SUPPORT PROBE ONLY; NOT V0171}
open_project {tool_probe.gprj}
set_option -top_module tool_probe
set_option -verilog_std v2001
run all
