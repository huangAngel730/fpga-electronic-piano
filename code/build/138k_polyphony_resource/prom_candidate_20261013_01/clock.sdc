create_clock -name sys_clk -period 25.000 [get_ports {clk}]
set_clock_uncertainty -setup 1.000 [get_clocks {sys_clk}]
set_clock_uncertainty -hold 0.650 [get_clocks {sys_clk}]
