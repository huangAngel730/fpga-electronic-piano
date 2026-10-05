# Single-clock tool probe, NOT the frozen V0171 timing constraints.
create_clock -name sys_clk -period 20.000 [get_ports {sys_clk}]
set_clock_uncertainty -setup 0.500 -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]
set_clock_uncertainty -hold 0.550 -from [get_clocks {sys_clk}] -to [get_clocks {sys_clk}]
