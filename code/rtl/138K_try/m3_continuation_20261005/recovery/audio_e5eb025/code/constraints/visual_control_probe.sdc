# Independent M2 control-mailbox experiment; no M3 renderer or audio.
create_clock -name sys_clk -period 20.000 [get_ports {sys_clk}]
create_generated_clock -name video_serial -source [get_ports {sys_clk}] -master_clock sys_clk -multiply_by 5 -divide_by 2 [get_pins {u_video_pll/PLLA_inst/CLKOUT0}]
create_generated_clock -name video_pixel -source [get_ports {sys_clk}] -master_clock sys_clk -multiply_by 1 -divide_by 2 [get_pins {u_video_pll/PLLA_inst/CLKOUT1}]
set_false_path -from [get_ports {sys_rst_n}]
set_false_path -to [get_pins {u_control/u_score_mailbox/ack_meta_s0/D}]
set_false_path -to [get_pins {u_control/u_score_mailbox/req_meta_s0/D}]
set_false_path -to [get_pins {u_control/u_mode_mailbox/ack_meta_s0/D}]
set_false_path -to [get_pins {u_control/u_mode_mailbox/req_meta_s0/D}]
# Score width=98; mode has no variable payload and is observed by toggle.
set_max_delay -from [get_regs {u_control/u_score_mailbox/payload_hold*}] -to [get_regs {u_control/u_score_mailbox/dst_data*}] 10.000
report_timing -setup -from [get_regs {u_control/u_score_mailbox/ack_meta_s0}] -to [get_regs {u_control/u_score_mailbox/ack_sync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_control/u_score_mailbox/ack_meta_s0}] -to [get_regs {u_control/u_score_mailbox/ack_sync_s0}] -max_paths 1
report_timing -setup -from [get_regs {u_control/u_score_mailbox/req_meta_s0}] -to [get_regs {u_control/u_score_mailbox/req_sync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_control/u_score_mailbox/req_meta_s0}] -to [get_regs {u_control/u_score_mailbox/req_sync_s0}] -max_paths 1
report_timing -setup -from [get_regs {u_control/u_mode_mailbox/ack_meta_s0}] -to [get_regs {u_control/u_mode_mailbox/ack_sync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_control/u_mode_mailbox/ack_meta_s0}] -to [get_regs {u_control/u_mode_mailbox/ack_sync_s0}] -max_paths 1
report_timing -setup -from [get_regs {u_control/u_mode_mailbox/req_meta_s0}] -to [get_regs {u_control/u_mode_mailbox/req_sync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_control/u_mode_mailbox/req_meta_s0}] -to [get_regs {u_control/u_mode_mailbox/req_sync_s0}] -max_paths 1
report_timing -setup -from [get_regs {u_control/u_score_mailbox/payload_hold*}] -to [get_regs {u_control/u_score_mailbox/dst_data*}] -max_paths 98 -max_common_paths 1
