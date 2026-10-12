# T052 128-edge public-port preparation

This directory is a static preparation for a future, separately authorized RTL capture.
It does not modify the frozen v5 DUT and has not been compiled or simulated.

- `tb_t052_publication_control_128.sv` drives all public inputs from a fixed 170-bit memory image. DUT outputs never affect the driver.
- `t052_public_observer.sv` reads public ports only, samples at each `posedge` before NBA updates, and records full input/output windows plus explicit reset transitions.
- `controls_128.hex` is generated from the M2 plan by the software in `rtl_capture_precheck_20261012`; its content is checked byte-for-byte against that plan.

The future runner must extract the frozen v5 DUT from M2's tracked `RAW_EVIDENCE.zip`, extract the read-only DDS/mixer/ROM closure, verify every SHA, copy this directory into a fresh output directory, and pass all six identity plusargs. No execution is authorized by this directory.
