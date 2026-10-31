# Pro C: 50 MHz reference and real PLL output 2 at 40 MHz.
create_clock -name ref_clk -period 20.000 [get_ports {sys_clk_50m}]
create_generated_clock -name core_clk -source [get_ports {sys_clk_50m}] -master_clock ref_clk -multiply_by 4 -divide_by 5 [get_pins {u_audio/u_audio_pll/u_pll/PLL_inst/CLKOUT2}]
create_generated_clock -name serial_clk -source [get_ports {sys_clk_50m}] -master_clock ref_clk -multiply_by 5 -divide_by 2 [get_pins {u_audio/u_audio_pll/u_pll/PLL_inst/CLKOUT0}]
create_generated_clock -name pixel_clk -source [get_ports {sys_clk_50m}] -master_clock ref_clk -multiply_by 1 -divide_by 2 [get_pins {u_audio/u_audio_pll/u_pll/PLL_inst/CLKOUT1}]
set_clock_uncertainty -setup 1.000 -from [get_clocks {core_clk}] -to [get_clocks {core_clk}]
set_clock_uncertainty -hold 0.750 -from [get_clocks {core_clk}] -to [get_clocks {core_clk}]
# External inputs are asynchronous; RTL retains its two-stage synchronizers.
set_false_path -from [get_ports {sys_rst_n}]
set_false_path -from [get_ports {key_n[0]}]
set_false_path -from [get_ports {key_n[1]}]
set_false_path -from [get_ports {midi_rx}]
set_false_path -from [get_ports {ble_uart_rx}]
# Core/pixel/serial are related outputs of one physical PLL. Retain inter-clock
# data/hold analysis; do not add broad asynchronous clock groups or false paths.
set_clock_uncertainty -setup 1.000 -from [get_clocks {pixel_clk}] -to [get_clocks {pixel_clk}]
set_clock_uncertainty -hold 0.750 -from [get_clocks {pixel_clk}] -to [get_clocks {pixel_clk}]
set_clock_uncertainty -setup 0.250 -from [get_clocks {serial_clk}] -to [get_clocks {serial_clk}]
set_clock_uncertainty -hold 0.100 -from [get_clocks {serial_clk}] -to [get_clocks {serial_clk}]
# Retained conservative candidate output constraints, not board measurements.
set_output_delay -clock core_clk -max 5.000 [get_ports {i2s_bclk i2s_lrck i2s_din}]
set_output_delay -clock core_clk -min 0.000 [get_ports {i2s_bclk i2s_lrck i2s_din}]
# Original audio setup/hold requirements remain. GOWIN_06 demonstrated that
# an experimental extra min1ns was added on top of the existing0.750ns hold
# uncertainty; it was not a route-only target. Remove that experiment and
# retain automatic hold repair. Route1 regressed actual GOWIN_07 timing;
# R07 restores route2 and fixes the actual data/physical cones. The next
# routed report must independently pass the original audio hold.
# PLL_INIT lock crosses to asynchronous-assert/synchronous-release reset.
# Exempt only the two synchronizer asynchronous CLEAR pins; retain D/CLK
# timing and all downstream synchronized reset recovery/removal checks.
set_false_path -to [get_pins {u_audio/u_reset_sync/sync_chain_0_s0/CLEAR u_audio/u_reset_sync/sync_chain_1_s0/CLEAR}]

# Stable bundled CDC data. Every bit has an absolute max-delay bound; this also
# bounds bit-to-bit skew by the same value (nonnegative data path delays).
# The receiver captures only after the two-stage request synchronizer. Source
# holds data until returned ACK. No domain-wide asynchronous clock exception.
set_max_delay -from [get_regs {u_score_visual/u_display/frame_hold*}] -to [get_regs {u_score_visual/u_display/frame_snapshot*}] 25.000
set_min_delay -from [get_regs {u_score_visual/u_display/frame_hold*}] -to [get_regs {u_score_visual/u_display/frame_snapshot*}] 0.000
set_max_delay -from [get_regs {u_score_visual/u_display/u_events/payload_hold*}] -to [get_regs {u_score_visual/u_display/u_events/video_data*}] 40.000
set_min_delay -from [get_regs {u_score_visual/u_display/u_events/payload_hold*}] -to [get_regs {u_score_visual/u_display/u_events/video_data*}] 0.000
# Synthesis absorbs tag_hold into tag_queue's synchronous BSRAM output.
# A core-clock launch collection includes the RAM clock-to-output arc; the
# only destination collection is the 33-bit video tag capture, not a domain.
set_max_delay -from [get_clocks {core_clk}] -to [get_regs {u_score_visual/u_display/u_events/video_tag*}] 40.000
set_min_delay -from [get_clocks {core_clk}] -to [get_regs {u_score_visual/u_display/u_events/video_tag*}] 0.000
set_max_delay -from [get_regs {u_score_visual/u_display/match_epoch_core*}] -to [get_regs {u_score_visual/u_display/match_epoch_pixel*}] 40.000
set_min_delay -from [get_regs {u_score_visual/u_display/match_epoch_core*}] -to [get_regs {u_score_visual/u_display/match_epoch_pixel*}] 0.000
set_max_delay -from [get_regs {u_score_visual/u_display/u_score_mailbox/payload_hold*}] -to [get_regs {u_score_visual/u_display/u_score_mailbox/dst_data*}] 40.000
set_min_delay -from [get_regs {u_score_visual/u_display/u_score_mailbox/payload_hold*}] -to [get_regs {u_score_visual/u_display/u_score_mailbox/dst_data*}] 0.000
# Only first-stage single-bit CDC captures are intentionally metastable.
set_false_path -to [get_pins {u_score_visual/u_display/frame_meta*/D u_score_visual/u_display/flush_meta*/D u_score_visual/u_display/clear_meta*/D u_score_visual/u_display/ready_meta*/D u_score_visual/u_display/fault_meta*/D}]
set_false_path -to [get_pins {u_score_visual/u_display/u_events/ack_meta*/D u_score_visual/u_display/u_events/req_meta*/D u_score_visual/u_display/u_events/desync_meta*/D}]
set_false_path -to [get_pins {u_score_visual/u_display/u_score_mailbox/ack_meta*/D u_score_visual/u_display/u_score_mailbox/req_meta*/D}]
# Asynchronous assertion / synchronous release: exempt synchronizer CLEAR only.
# All downstream reset recovery/removal and data paths remain analyzed.
# Identical core resets merged into u_audio/u_reset_sync. Human video reset
# merged into u_pixel_reset. R05 uses pixel release for the DVI reset input;
# 125MHz remains only on dedicated serializer resources, without fabric reset
# flops. Removed human_fault/fatal exports have no surviving capture pins.
set_false_path -to [get_pins {u_score_visual/u_display/u_pixel_reset/sync_chain*/CLEAR}]
set_false_path -to [get_pins {u_score_visual/u_display/u_score_mailbox/u_src_reset/sync_chain*/CLEAR u_score_visual/u_display/u_score_mailbox/u_dst_reset/sync_chain*/CLEAR}]


# R09: R08 exact pin queries returned no paths, so remove unproven max3.
# Explicit global reports preserve natural recovery/removal checks; filtered
# reports are diagnostics only and may be empty without indicating a pass.
# First remove R08 four ineffective max3 constraints and eight empty pin queries.
# These explicit global reports must remain; diagnostics must never replace them.
# No timing requirement is changed by this file.
report_timing -recovery -max_paths 256 -max_common_paths 8
report_timing -removal -max_paths 256 -max_common_paths 8
report_high_fanout_nets -slr -min_fanout 70 -max_fanout 80 -max_nets 100
report_timing -recovery -from_clock [get_clocks {pixel_clk}] -to_clock [get_clocks {serial_clk}] -max_paths 64 -max_common_paths 8
report_timing -removal -from_clock [get_clocks {pixel_clk}] -to_clock [get_clocks {serial_clk}] -max_paths 64 -max_common_paths 8
report_timing -recovery -from_clock [get_clocks {pixel_clk}] -through [get_nets {u_score_visual/u_display/dvi_rst_n}] -max_paths 256 -max_common_paths 8
report_timing -removal -from_clock [get_clocks {pixel_clk}] -through [get_nets {u_score_visual/u_display/dvi_rst_n}] -max_paths 256 -max_common_paths 8

# R10 half-cycle verification. Keep explicit unfiltered setup/hold reports
# because adding filtered report_timing commands replaces vendor defaults.
# Pixel-clock and public reset-net diagnostics expose the unchanged two-stage
# rising-edge reset output to the new falling-edge DVI release D pin.
report_timing -setup -max_paths 25 -max_common_paths 1
report_timing -hold -max_paths 25 -max_common_paths 1
report_timing -setup -from_clock [get_clocks {pixel_clk}] -to_clock [get_clocks {pixel_clk}] -max_paths 256 -max_common_paths 8
report_timing -hold -from_clock [get_clocks {pixel_clk}] -to_clock [get_clocks {pixel_clk}] -max_paths 256 -max_common_paths 8
report_timing -setup -from_clock [get_clocks {pixel_clk}] -through [get_nets {u_score_visual/u_display/pixel_rst_n}] -to_clock [get_clocks {pixel_clk}] -max_paths 64 -max_common_paths 8
report_timing -hold -from_clock [get_clocks {pixel_clk}] -through [get_nets {u_score_visual/u_display/pixel_rst_n}] -to_clock [get_clocks {pixel_clk}] -max_paths 64 -max_common_paths 8

# R05 diagnostic expansion only; no constraint relaxation.
report_timing -hold -max_paths 256 -max_common_paths 1

# R08 additional observer/page CDC only; all R07 timing requirements retained.
set_max_delay -from [get_regs {u_score_visual/u_display/u_waveform_overlay/u_page_mailbox/payload_hold*}] -to [get_regs {u_score_visual/u_display/u_waveform_overlay/u_page_mailbox/dst_data*}] 40.000
set_min_delay -from [get_regs {u_score_visual/u_display/u_waveform_overlay/u_page_mailbox/payload_hold*}] -to [get_regs {u_score_visual/u_display/u_waveform_overlay/u_page_mailbox/dst_data*}] 0.000
set_false_path -to [get_pins {u_score_visual/u_display/u_waveform_overlay/u_page_mailbox/ack_meta*/D u_score_visual/u_display/u_waveform_overlay/u_page_mailbox/req_meta*/D}]
set_false_path -to [get_pins {u_score_visual/u_display/u_waveform_overlay/u_page_mailbox/u_src_reset/sync_chain*/CLEAR u_score_visual/u_display/u_waveform_overlay/u_page_mailbox/u_dst_reset/sync_chain*/CLEAR}]
# PCM reset synchronizers merge into page-mailbox reset FFs; their four CLEAR pins are already covered above.

# R13 R02: actual analysis engines are intentionally unattached.
# Removed only four old waveform-bridge queries, whose target RAM/CDC is absent.
# Original audio, related clocks, DVI, score/live and page-mailbox timing remain.
# Three-bit atomic page/timbre payload uses the same page-mailbox max/min bounds.
