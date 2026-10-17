# R06 MIDI stimulus candidate

This isolated package generates a physical 31250-baud MIDI byte timeline and a
testbench-only public-port driver.  It is not a Pro DUT result and does not
select slots, retire Release voices, choose a preemption victim, or assign a
generation.  Those fields remain `PENDING_M1_SOURCE_SEMANTICS`.

The plan covers four solos, four different notes arriving serially and then
held together, one-by-one releases, different velocities, NoteOn velocity 0,
same-note retrigger, a fifth-note boundary, Running Status, an interleaved F8
real-time byte, reset/recovery and public event backpressure.  Each physical
byte has its own sequence and start/stop cycle; each expected event has an
`event_seq`, normalized public 64-bit value and arrival window.  Four NoteOn
messages are never represented as a same-cycle input.

`midi_public_port_driver.sv` drives only `sys_rst_n`, `midi_rx` and the public
downstream `event_ready`.  It observes only `event_valid/event_data` and writes
handshakes to a log.  It has no private hierarchy references.

Validation is limited to one bounded Python/software run.  No HDL compiler,
simulator, Gowin tool or hardware is authorized in this package.
