# Independent 640x480 transport prototype; no audio clock constraints.
create_clock -name sys_clk -period 20.000 [get_ports {sys_clk}]
create_generated_clock -name video_serial -source [get_ports {sys_clk}] -master_clock sys_clk -multiply_by 5 -divide_by 2 [get_pins {u_video_pll/PLLA_inst/CLKOUT0}]
create_generated_clock -name video_pixel -source [get_ports {sys_clk}] -master_clock sys_clk -multiply_by 1 -divide_by 2 [get_pins {u_video_pll/PLLA_inst/CLKOUT1}]
# External asynchronous reset is synchronized locally; no datapath false paths.
set_false_path -from [get_ports {sys_rst_n}]
# M2 isolated FULL probe only. No change to formal electronic-piano timing.
# Only the seven first-stage asynchronous inputs are exceptions.
set_false_path -to [get_pins {u_event_bridge/ack_meta_s0/D}]
set_false_path -to [get_pins {u_event_bridge/req_meta_s0/D}]
set_false_path -to [get_pins {u_event_bridge/desync_meta_s0/D}]
set_false_path -to [get_pins {u_control/u_score_mailbox/ack_meta_s0/D}]
set_false_path -to [get_pins {u_control/u_score_mailbox/req_meta_s0/D}]
set_false_path -to [get_pins {u_control/u_mode_mailbox/ack_meta_s0/D}]
set_false_path -to [get_pins {u_control/u_mode_mailbox/req_meta_s0/D}]
# Two distinct bundled-data mailboxes; no broad clock-group false path.
set_max_delay -from [get_regs {u_event_bridge/payload_hold*}] -to [get_regs {u_event_bridge/video_data*}] 10.000
set_max_delay -from [get_regs {u_control/u_score_mailbox/payload_hold*}] -to [get_regs {u_control/u_score_mailbox/dst_data*}] 10.000
# Explicit path reports for the surviving data bits; an Active constraint
# alone does not establish that synthesis retained all 64 or 98 payload bits.
report_timing -setup -from [get_regs {u_event_bridge/payload_hold*}] -to [get_regs {u_event_bridge/video_data*}] -max_paths 128 -max_common_paths 1
report_timing -setup -from [get_regs {u_control/u_score_mailbox/payload_hold*}] -to [get_regs {u_control/u_score_mailbox/dst_data*}] -max_paths 128 -max_common_paths 1
report_timing -setup -from [get_regs {u_event_bridge/ack_meta_s0}] -to [get_regs {u_event_bridge/ack_sync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_event_bridge/ack_meta_s0}] -to [get_regs {u_event_bridge/ack_sync_s0}] -max_paths 1
report_timing -setup -from [get_regs {u_event_bridge/req_meta_s0}] -to [get_regs {u_event_bridge/req_sync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_event_bridge/req_meta_s0}] -to [get_regs {u_event_bridge/req_sync_s0}] -max_paths 1
report_timing -setup -from [get_regs {u_event_bridge/desync_meta_s0}] -to [get_regs {u_event_bridge/video_desync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_event_bridge/desync_meta_s0}] -to [get_regs {u_event_bridge/video_desync_s0}] -max_paths 1
report_timing -setup -from [get_regs {u_control/u_score_mailbox/ack_meta_s0}] -to [get_regs {u_control/u_score_mailbox/ack_sync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_control/u_score_mailbox/ack_meta_s0}] -to [get_regs {u_control/u_score_mailbox/ack_sync_s0}] -max_paths 1
report_timing -setup -from [get_regs {u_control/u_score_mailbox/req_meta_s0}] -to [get_regs {u_control/u_score_mailbox/req_sync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_control/u_score_mailbox/req_meta_s0}] -to [get_regs {u_control/u_score_mailbox/req_sync_s0}] -max_paths 1
report_timing -setup -from [get_regs {u_control/u_mode_mailbox/ack_meta_s0}] -to [get_regs {u_control/u_mode_mailbox/ack_sync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_control/u_mode_mailbox/ack_meta_s0}] -to [get_regs {u_control/u_mode_mailbox/ack_sync_s0}] -max_paths 1
report_timing -setup -from [get_regs {u_control/u_mode_mailbox/req_meta_s0}] -to [get_regs {u_control/u_mode_mailbox/req_sync_s0}] -max_paths 1
report_timing -hold -from [get_regs {u_control/u_mode_mailbox/req_meta_s0}] -to [get_regs {u_control/u_mode_mailbox/req_sync_s0}] -max_paths 1
