create_clock -name sys_clk -period 20.000 [get_ports {sys_clk}]
create_generated_clock -name video_serial -source [get_ports {sys_clk}] -master_clock sys_clk -multiply_by 5 -divide_by 2 [get_pins {u_video_pll/PLLA_inst/CLKOUT0}]
create_generated_clock -name video_pixel -source [get_ports {sys_clk}] -master_clock sys_clk -multiply_by 1 -divide_by 2 [get_pins {u_video_pll/PLLA_inst/CLKOUT1}]
set_false_path -from [get_ports {sys_rst_n}]
# Exception applies only to the three first-stage CDC data pins.
# Their second-stage paths still receive normal setup/hold analysis.
set_false_path -to [get_pins {u_bridge/ack_meta_s0/D}]
set_false_path -to [get_pins {u_bridge/req_meta_s0/D}]
set_false_path -to [get_pins {u_bridge/desync_meta_s0/D}]
# Bundled-data mailbox: 64-bit payload must arrive well before request sync.
# 10 ns is below the 40 ns pixel period; the sink captures after two sync FFs.
set_max_delay -from [get_regs {u_bridge/payload_hold*}] -to [get_regs {u_bridge/video_data*}] 10.000
report_timing -setup -from [get_regs {u_bridge/ack_meta_s0}] -to [get_regs {u_bridge/ack_sync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_bridge/ack_meta_s0}] -to [get_regs {u_bridge/ack_sync_s0}] -max_paths 1
report_timing -setup -from [get_regs {u_bridge/req_meta_s0}] -to [get_regs {u_bridge/req_sync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_bridge/req_meta_s0}] -to [get_regs {u_bridge/req_sync_s0}] -max_paths 1
report_timing -setup -from [get_regs {u_bridge/desync_meta_s0}] -to [get_regs {u_bridge/video_desync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_bridge/desync_meta_s0}] -to [get_regs {u_bridge/video_desync_s0}] -max_paths 1
