# Pro C: 50 MHz reference and real PLL output 2 at 40 MHz.
create_clock -name ref_clk -period 20.000 [get_ports {sys_clk_50m}]
create_generated_clock -name core_clk -source [get_ports {sys_clk_50m}] -master_clock ref_clk -multiply_by 4 -divide_by 5 [get_pins {u_audio/u_audio_pll/u_pll/PLL_inst/CLKOUT2}]
create_generated_clock -name serial_clk -source [get_ports {sys_clk_50m}] -master_clock ref_clk -multiply_by 5 -divide_by 2 [get_pins {u_audio/u_audio_pll/u_pll/PLL_inst/CLKOUT0}]
create_generated_clock -name pixel_clk -source [get_ports {sys_clk_50m}] -master_clock ref_clk -multiply_by 1 -divide_by 2 [get_pins {u_audio/u_audio_pll/u_pll/PLL_inst/CLKOUT1}]

# R18 Bright Octave implementation: constrain only the three mapped paths that
# were measured short after place3/route2.  These are physical routing targets;
# they do not add a functional cycle or alter any audio/video interface timing.
# R02 DISABLED (non-zero set_min_delay ADDS to hold requirement): set_min_delay -from [get_pins {u_score_transport/receiver/rx_data_5_s0/Q}] -to [get_pins {u_score_transport/body[10]_5_s0/D}] 0.200
# R02 DISABLED (non-zero set_min_delay ADDS to hold requirement): set_min_delay -from [get_pins {u_score_visual/u_display/u_dvi/rgb2dvi_inst/TMDS8b10b_inst_r/dout_2_s0/Q}] -to [get_pins {u_score_visual/u_display/u_dvi/rgb2dvi_inst/u_OSER10_r/D2}] 0.250
# R02 DISABLED (non-zero set_min_delay ADDS to hold requirement): set_min_delay -from [get_pins {u_score_visual/u_display/u_events/video_data.velocity_6_s0/Q}] -to [get_pins {u_score_visual/u_display/u_live/velocity_q[5]_6_s3/D}] 0.150
set_clock_uncertainty -setup 1.000 -from [get_clocks {core_clk}] -to [get_clocks {core_clk}]
# R02: hold uncertainty 0.750 -> 0.100, matching the file own serial_clk precedent
set_clock_uncertainty -hold 0.100 -from [get_clocks {core_clk}] -to [get_clocks {core_clk}]
# External inputs are asynchronous; RTL retains its two-stage synchronizers.
set_false_path -from [get_ports {sys_rst_n}]
set_false_path -from [get_ports {key_n[0]}]
set_false_path -from [get_ports {key_n[1]}]
set_false_path -from [get_ports {midi_rx}]
set_false_path -from [get_ports {ble_uart_rx}]
# Core/pixel/serial are related outputs of one physical PLL. Retain inter-clock
# data/hold analysis; do not add broad asynchronous clock groups or false paths.
set_clock_uncertainty -setup 1.000 -from [get_clocks {pixel_clk}] -to [get_clocks {pixel_clk}]
# R02: hold uncertainty 0.750 -> 0.100, matching the file own serial_clk precedent
set_clock_uncertainty -hold 0.100 -from [get_clocks {pixel_clk}] -to [get_clocks {pixel_clk}]
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

# Candidate only: exact Native01 VG binding, not executed by Gowin.
# Original51 retained byte-for-byte.11 new commands replace old20.
# Root must bind fresh revision VG collections/RAMtC2Q/STA before acceptance.
set_max_delay -from [get_clocks {core_clk}] -to [get_regs {u_score_visual/u_display/u_waveform_overlay/u_shared_waveform/u_bridge/u_mailbox/dst_data*}] 40.000
set_min_delay -from [get_clocks {core_clk}] -to [get_regs {u_score_visual/u_display/u_waveform_overlay/u_shared_waveform/u_bridge/u_mailbox/dst_data*}] 0.000
set_false_path -from [get_clocks {core_clk}] -to [get_pins {u_score_visual/u_display/u_waveform_overlay/u_shared_waveform/u_bridge/u_mailbox/req_meta*/D u_score_visual/u_display/u_waveform_overlay/u_shared_waveform/u_bridge/source_up_meta*/D}]
set_false_path -from [get_clocks {pixel_clk}] -to [get_pins {u_score_visual/u_display/u_waveform_overlay/u_shared_waveform/u_bridge/u_mailbox/ack_meta*/D}]
set_false_path -to [get_pins {u_score_visual/u_display/u_waveform_overlay/u_shared_waveform/u_bridge/u_observer_reset/sync_chain*/CLEAR}]
set_max_delay -from [get_regs {u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/published_bank_audio*}] -to [get_regs {u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/bank_sync_pixel_1*}] 40.000
set_min_delay -from [get_regs {u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/published_bank_audio*}] -to [get_regs {u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/bank_sync_pixel_1*}] 0.000
set_max_delay -from [get_regs {u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/published_generation_audio*}] -to [get_regs {u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/generation_sync_pixel_1*}] 40.000
set_min_delay -from [get_regs {u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/published_generation_audio*}] -to [get_regs {u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/generation_sync_pixel_1*}] 0.000
set_false_path -from [get_clocks {core_clk}] -to [get_pins {u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/req_sync_pixel_1*/D}]
set_false_path -from [get_clocks {pixel_clk}] -to [get_pins {u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/ack_sync_audio_1*/D u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/ack_accepted_sync_audio_1*/D u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/pixel_up_audio_1*/D}]

# R15 Native03 diagnostics only; all62 existing commands unchanged.
# Optional report-only candidate. Never modify active frozen run.
# Document-supported parameters; new endpoint combinations NOT executed here.
# Keep original global reports and all set/create constraints unchanged.
# Coverage must be established from actual From/To rows, not max_paths/count of handle.
report_timing -setup -from_clock [get_clocks {core_clk}] -to_clock [get_clocks {pixel_clk}] -to [get_regs {u_score_visual/u_display/u_waveform_overlay/u_shared_waveform/u_bridge/u_mailbox/dst_data*}] -max_paths 256 -max_common_paths 1
report_timing -hold -from_clock [get_clocks {core_clk}] -to_clock [get_clocks {pixel_clk}] -to [get_regs {u_score_visual/u_display/u_waveform_overlay/u_shared_waveform/u_bridge/u_mailbox/dst_data*}] -max_paths 256 -max_common_paths 1
report_timing -setup -from [get_regs {u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/published_bank_audio* u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/published_generation_audio*}] -to [get_regs {u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/bank_sync_pixel_1* u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/generation_sync_pixel_1*}] -max_paths 256 -max_common_paths 1
report_timing -hold -from [get_regs {u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/published_bank_audio* u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/published_generation_audio*}] -to [get_regs {u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/bank_sync_pixel_1* u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_snapshot/generation_sync_pixel_1*}] -max_paths 256 -max_common_paths 1

# Field release diagnosis: report only, no requirement relaxation.
report_timing -setup -to [get_regs {u_audio/g_polyphonic.u_audio_core/u_n8_core/router/slot_releasing* u_audio/g_polyphonic.u_audio_core/u_n8_core/router/release_index* u_audio/g_polyphonic.u_audio_core/u_n8_core/router/state* u_audio/g_polyphonic.u_audio_core/u_n8_core/router/u_sustain/pending_mask*}] -max_paths 256 -max_common_paths 8
report_timing -hold -to [get_regs {u_audio/g_polyphonic.u_audio_core/u_n8_core/router/slot_releasing* u_audio/g_polyphonic.u_audio_core/u_n8_core/router/release_index* u_audio/g_polyphonic.u_audio_core/u_n8_core/router/state* u_audio/g_polyphonic.u_audio_core/u_n8_core/router/u_sustain/pending_mask*}] -max_paths 256 -max_common_paths 8
report_timing -recovery -to [get_regs {u_audio/g_polyphonic.u_audio_core/u_n8_core/router/slot_releasing* u_audio/g_polyphonic.u_audio_core/u_n8_core/router/release_index* u_audio/g_polyphonic.u_audio_core/u_n8_core/router/state* u_audio/g_polyphonic.u_audio_core/u_n8_core/router/u_sustain/pending_mask*}] -max_paths 256 -max_common_paths 8
report_timing -removal -to [get_regs {u_audio/g_polyphonic.u_audio_core/u_n8_core/router/slot_releasing* u_audio/g_polyphonic.u_audio_core/u_n8_core/router/release_index* u_audio/g_polyphonic.u_audio_core/u_n8_core/router/state* u_audio/g_polyphonic.u_audio_core/u_n8_core/router/u_sustain/pending_mask*}] -max_paths 256 -max_common_paths 8

# N8 R02: exact mapped-pin hold repair from this revision's place3/route2
# report.  These eight short paths are constrained individually; no clock,
# frequency, global domain, CDC exception, or functional RTL is changed.
# R02 DISABLED (non-zero set_min_delay ADDS to hold requirement): set_min_delay -from [get_pins {u_score_transport/last_reply_last_reply_RAMREG_1_G[0]_s0/Q}] -to [get_pins {u_score_transport/reply[32]_0_s0/D}] 0.300
# N32 resource optimization replaces the per-voice u_pitch instances with one
# shared pitch engine.  The N8 mapped-pin path above no longer exists; keep its
# history here, but derive any N32 hold repair from the fresh N32 PnR netlist.
# set_min_delay -from [get_pins {u_audio/g_polyphonic.u_audio_core/u_n8_core/backend/g_continuous[3].u_pitch/base_s1_26_s0/Q}] -to [get_pins {u_audio/g_polyphonic.u_audio_core/u_n8_core/backend/g_continuous[3].u_pitch/base_s2_26_s0/D}] 0.200
# R02 DISABLED (non-zero set_min_delay ADDS to hold requirement): set_min_delay -from [get_pins {u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_fft/ti_3_s0/Q}] -to [get_pins {u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_fft/sum_bi_8_s0/D}] 0.150
# R02 DISABLED (non-zero set_min_delay ADDS to hold requirement): set_min_delay -from [get_pins {u_audio/g_polyphonic.u_audio_core/u_n8_core/scheduler/req_control_20_s0/Q}] -to [get_pins {u_audio/g_polyphonic.u_audio_core/u_n8_core/frame_mod_80_s0/D}] 0.150
# R02 DISABLED (non-zero set_min_delay ADDS to hold requirement): set_min_delay -from [get_pins {u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_fft/ti_3_s0/Q}] -to [get_pins {u_score_visual/u_display/u_waveform_overlay/u_shared_spectrum/u_candidate/u_fft/sum_bi_10_s0/D}] 0.150
# R02 DISABLED (non-zero set_min_delay ADDS to hold requirement): set_min_delay -from [get_pins {u_audio/g_polyphonic.u_audio_core/u_n8_core/scheduler/req_control_15_s0/Q}] -to [get_pins {u_audio/g_polyphonic.u_audio_core/u_n8_core/frame_mod_27_s0/D}] 0.150

# N8 R03 netlist: exact short-path repair after wire-equivalent response
# assembly optimization.  Names come from the fresh place3/route2 report.
# R02 DISABLED (non-zero set_min_delay ADDS to hold requirement): set_min_delay -from [get_pins {u_audio/g_polyphonic.u_audio_core/u_n8_core/raw_id_20_s0/Q}] -to [get_pins {u_audio/g_polyphonic.u_audio_core/u_n8_core/post/post_0/last_id_20_s0/D}] 0.150
# R02 DISABLED (non-zero set_min_delay ADDS to hold requirement): set_min_delay -from [get_pins {u_audio/g_polyphonic.u_audio_core/u_n8_core/scheduler/req_control_19_s0/Q}] -to [get_pins {u_audio/g_polyphonic.u_audio_core/u_n8_core/frame_mod_31_s0/D}] 0.150
# R02 DISABLED (non-zero set_min_delay ADDS to hold requirement): set_min_delay -from [get_pins {u_audio/g_polyphonic.u_audio_core/u_n8_core/scheduler/req_context_12_s0/Q}] -to [get_pins {u_audio/g_polyphonic.u_audio_core/u_n8_core/frame_base_44_s0/D}] 0.150
# R02 DISABLED (non-zero set_min_delay ADDS to hold requirement): set_min_delay -from [get_pins {u_audio/g_polyphonic.u_audio_core/u_n8_core/owned_id_4_s0/Q}] -to [get_pins {u_audio/g_polyphonic.u_audio_core/u_n8_core/scheduler/request_id_4_s0/D}] 0.100
# N8 R08 replaces the four 0.100 ns same-cycle ID/base/flag constraints
# above with kept two-LUT identity chains in m2_polyphony_timbre_core.  The
# previous constraints changed only the required time and did not lengthen the
# protected data paths.  The remaining exact constraints continue to bind to
# paths that were physically repaired by place/route.

# N8 R17/R18: R16 removed all seven prior hold endpoints.  Its fresh run
# exposed two sub-0.02 ns paths.  The audio path is repaired structurally in
# m2_polyphony_audio_backend because its exact min-delay requirement did not
# alter physical delay.  The visual endpoint did respond to its exact binding.
# The N32 netlist also remaps the visual state registers, so this old N8
# mapped-pin binding is not a valid object in the optimized implementation.
# set_min_delay -from [get_pins {u_score_visual/u_display/u_live/top_q[12]_1_s1/Q}] -to [get_pins {u_score_visual/u_display/u_live/top_q[12]_6_s1/D}] 0.150
