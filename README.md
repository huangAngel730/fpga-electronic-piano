# FPGA Electronic Piano

A vendor-neutral Verilog project for an eight-key FPGA electronic piano.

## Features

- Eight active-low keys for the C4 to C5 natural scale
- Two-stage input synchronization and key debounce
- High-note priority when multiple keys are pressed
- Phase-accumulator tone generation
- One-bit square-wave audio output
- Self-checking simulation testbench

## Layout

```text
rtl/          Synthesizable Verilog
tb/           Simulation testbench
constraints/  Board-specific pin constraints
docs/         Hardware notes
```

## Getting started

1. Add all files under `rtl/` to Vivado, Quartus, or another FPGA tool.
2. Set `electronic_piano_top` as the top module.
3. Add a board-specific constraint file under `constraints/`.
4. Set `CLK_FREQ_HZ` to the actual oscillator frequency.
5. Synthesize, implement, and program the FPGA.

Do not connect an 8-ohm speaker directly to an FPGA pin. See `docs/hardware.md`.

## Planned improvements

- Chromatic notes and octave switching
- Sine-wave DDS and ADSR envelope
- Polyphony
- OLED or seven-segment note display
- MIDI input

This repository is intended to remain private for team collaboration.
