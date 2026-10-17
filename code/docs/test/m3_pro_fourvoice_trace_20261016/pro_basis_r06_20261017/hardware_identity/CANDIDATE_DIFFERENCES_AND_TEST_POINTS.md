# Pro hardware identity: candidate differences and physical test points

Status: source-backed preparation only. No board was connected, powered, measured,
programmed or operated. Every physical fact remains `UNKNOWN/PENDING`.

## Candidate identity differences

| Item | Pro 4072 + Dock 4071f3 candidate | Legacy 138K C + NEO 31005 | Required physical check |
|---|---|---|---|
| Core/Dock | Core drawing 4072 Rev1.10; Dock drawing 4071f3 Rev1.5 | 30354 + NEO 31005 | One in-focus overview and separate revision/silkscreen photos |
| Device | Schematic symbol `GW5AT-LV138FPG676A` | Different legacy package context | Full chip marking photo, including suffix and stepping |
| MIDI input | `R17 = PMOD0_IO3 = J22/5`; shared with `SSPI_WP_N` candidate | `R17 = PMOD0_IO5 = J9/8` | Adapter direction label, connector pin, idle/high/low at FPGA side, and shared-config safety |
| PT8211 serial | `BCK E22`, `WS F24`, `DIN G24` | `Y17`, `AB17`, `AA16` | Unpowered continuity first; active waveform only after release |
| PA enable | `H17`, XPT4809 pin 5; candidate high=work, low=off | `AB16`; legacy evidence says low-active | Component marking, continuity and safe enable polarity; never infer from legacy record |
| Bank rails | Bank3 candidate 3.3 V; Bank4/5 candidate selectable 3.3/1.8 V | Legacy table records 3.3 V design facts | Raw DMM/scope readings on this physical unit |

## Test-point plan (not permission to execute)

1. With power removed, photograph core front/back, Dock front/back, full device
   marking, board/Dock revision silkscreens, voltage-select straps, PT8211 and PA
   component markings. Keep original image metadata.
2. Locate Pro-specific Bank 3/4/5 rail measurement points from the actual PCB and
   the 4072/4071f3 drawings. Old TP21/TP22/FB13/TP23 labels from the C/NEO board
   are **not accepted** until visual and continuity evidence proves the same net.
3. Record DMM model/serial, range, calibration status, ground reference, power
   state and UTC/local timestamp. Capture raw CSV or instrument export for each
   Bank 3/4/5 rail; a typed summary or screenshot alone is insufficient.
4. Before attaching MIDI, prove adapter signal direction is adapter-output to
   FPGA-input, measure FPGA-side idle/high/low, and prove common ground. Do not
   connect an unknown or 5 V logic output to the FPGA.
5. Before audio operation, prove PT8211/PA population, serial-pin continuity and
   PA enable polarity. Use a safe headphone/line/load path; do not directly drive
   an unverified passive speaker.
6. Record the official PDF page or CST line used for each candidate separately
   from the physical evidence. A reference page never upgrades a measurement.

## Raw evidence schema

Photos require original filename, SHA-256, bytes, capture time, subject, visible
marking and an explicit `PHYSICAL_PHOTO` index entry. Measurement CSV/export
requires original filename, SHA-256, instrument model/serial, range, units,
ground point, test point/net, power state, timestamp and raw samples. Commercial
tool evidence may record executable path/hash/version and a non-secret runtime
receipt, but must never contain a license key, server value, token or password.
