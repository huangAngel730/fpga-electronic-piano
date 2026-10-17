# Failure and repair history

`RUN_01` completed its bounded software checks with exit 0, but post-run source
review found that the generated first RESET assertion occurred at cycle 5120
and the driver defaulted `sys_rst_n` high.  That left an unintended active
window at simulation start.  The raw RUN_01 streams and products are retained.

The single permitted minimal repair sets the driver default reset low, starts
the control plan at cycle 0, and enforces the configured idle-bit interval
after every reset release before a later MIDI byte.  RUN_02 is the only repair
run.  This is a TB stimulus correction, not a DUT, HDL simulation, or Pro
functional result.
