# Tang Mega 138K Pro isolated candidate timing requirements.
# These object paths match the frozen wrapper hierarchy but must be resolved
# again against the first real Pro netlist. This file is not an STA result.

create_clock -name ref_clk -period 20.000 [get_ports {sys_clk_50m}]

# Frozen TMDS_PLL plan: 50 MHz reference -> 40 MHz core, 25 MHz pixel,
# 125 MHz serializer. The first Pro build must prove these pins exist.
create_generated_clock -name core_clk -source [get_ports {sys_clk_50m}] -master_clock ref_clk -multiply_by 4 -divide_by 5 [get_pins {u_legacy/u_visual/u_video_pll/PLLA_inst/CLKOUT2}]
create_generated_clock -name video_pixel -source [get_ports {sys_clk_50m}] -master_clock ref_clk -multiply_by 1 -divide_by 2 [get_pins {u_legacy/u_visual/u_video_pll/PLLA_inst/CLKOUT1}]
create_generated_clock -name video_serial -source [get_ports {sys_clk_50m}] -master_clock ref_clk -multiply_by 5 -divide_by 2 [get_pins {u_legacy/u_visual/u_video_pll/PLLA_inst/CLKOUT0}]

set_clock_uncertainty -setup 1.000 -from [get_clocks {core_clk}] -to [get_clocks {core_clk}]
set_clock_uncertainty -hold 0.650 -from [get_clocks {core_clk}] -to [get_clocks {core_clk}]

set_output_delay -clock core_clk -max 5.000 [get_ports {i2s_bclk}]
set_output_delay -clock core_clk -min 0.000 [get_ports {i2s_bclk}]
set_output_delay -clock core_clk -max 5.000 [get_ports {i2s_lrck}]
set_output_delay -clock core_clk -min 0.000 [get_ports {i2s_lrck}]
set_output_delay -clock core_clk -max 5.000 [get_ports {i2s_din}]
set_output_delay -clock core_clk -min 0.000 [get_ports {i2s_din}]

# Board inputs are asynchronous to the generated 40 MHz core domain. Only
# synchronized first stages may receive CDC exceptions in the physical SDC.
set_false_path -from [get_ports {sys_rst_n}]
set_false_path -from [get_ports {midi_rx}]
set_false_path -from [get_ports {key_n[0]}]
set_false_path -from [get_ports {key_n[1]}]

# The seven visual mailbox first-stage exceptions from the frozen design are
# retained as required object checks, not assumed valid before the Pro netlist.
set_false_path -to [get_pins {u_legacy/u_visual/u_event_bridge/ack_meta_s0/D}]
set_false_path -to [get_pins {u_legacy/u_visual/u_event_bridge/req_meta_s0/D}]
set_false_path -to [get_pins {u_legacy/u_visual/u_event_bridge/desync_meta_s0/D}]
set_false_path -to [get_pins {u_legacy/u_visual/u_control/u_score_mailbox/ack_meta_s0/D}]
set_false_path -to [get_pins {u_legacy/u_visual/u_control/u_score_mailbox/req_meta_s0/D}]
set_false_path -to [get_pins {u_legacy/u_visual/u_control/u_mode_mailbox/ack_meta_s0/D}]
set_false_path -to [get_pins {u_legacy/u_visual/u_control/u_mode_mailbox/req_meta_s0/D}]
