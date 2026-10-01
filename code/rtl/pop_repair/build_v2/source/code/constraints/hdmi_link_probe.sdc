# Independent 640x480 transport prototype; no audio clock constraints.
create_clock -name sys_clk -period 20.000 [get_ports {sys_clk}]
create_generated_clock -name video_serial -source [get_ports {sys_clk}] -master_clock sys_clk -multiply_by 5 -divide_by 2 [get_pins {u_video_pll/PLLA_inst/CLKOUT0}]
create_generated_clock -name video_pixel -source [get_ports {sys_clk}] -master_clock sys_clk -multiply_by 1 -divide_by 2 [get_pins {u_video_pll/PLLA_inst/CLKOUT1}]
# External asynchronous reset is synchronized locally; no datapath false paths.
set_false_path -from [get_ports {sys_rst_n}]
