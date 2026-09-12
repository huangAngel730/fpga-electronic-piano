# Hardware notes

The key inputs are active-low. Enable internal pull-ups or add about 10 kohm
external pull-ups; a pressed key connects its input to ground.

Do not connect a low-impedance speaker directly to `audio_out`.

```text
FPGA audio_out -> 1 kohm -> NPN/MOSFET driver -> buzzer or amplifier
FPGA GND -------------------------------------> common ground
```

If pitch is wrong, verify `CLK_FREQ_HZ`. If keys are unstable, check polarity,
pull-ups, and debounce time. Probe `audio_out` before debugging the amplifier.
