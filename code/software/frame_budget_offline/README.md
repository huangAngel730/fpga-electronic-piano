# R04 audio-frame budget offline analyzer

This directory is an isolated software-only companion for a future approved
R04 ModelSim run.  It does **not** launch ModelSim and does not claim that the
R04 whole system, synthesis, timing, or hardware passes.

## Frozen contract used

- R04 portable input ZIP:
  `code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1双音色延迟_ModelSim自包含输入_20261015.zip`
- ZIP SHA-256:
  `1101f1af0809530a150143456aab8ff9a1c66373e9ccbc174c6459e8c916b3bf`
- Frozen TB member: `inputs/tb_m2_m1td_real_chain.sv`
- Frozen TB SHA-256:
  `6325f8f0e332e30cb32d573080c5191b7a516b821a3e08bb531a1b53f9148ee6`
- The frozen TB requires `status_max_processing_cycles < 834`.  Its current
  portable package is `PREPARED_NOT_EXECUTED`; this tool does not change that
  status.

## Minimum CSV contract

The future simulation exporter must write one row for every audio frame in a
single reset lifetime.  UTF-8 CSV (an optional UTF-8 BOM is accepted) needs
these four fields (additional fields are allowed and ignored):

| Field | Meaning |
|---|---|
| `frame_index` | Zero-based, contiguous frame sequence number |
| `frame_cycles` | Distance from the previous frame tick; only 833 or 834 is valid for 40 MHz / 48 kHz |
| `max_processing_cycles` | Nondecreasing cumulative hardware status value observed at this frame |
| `underrun_count` | Nondecreasing cumulative frame-underrun counter |

Acceptance requires every frame period to be 833/834 cycles, the final
`max_processing_cycles` to be strictly less than 834, and the final cumulative
`underrun_count` to be zero.  The JSON summary preserves the input byte count,
SHA-256, 833/834 histogram, maximum status value, underrun count, verdict, and
specific rejection reasons.

The CSV does not contain an independent per-frame internal processing latency.
Therefore this analyzer can check the exported cumulative maximum for
monotonicity and deadline compliance, but cannot reconstruct or independently
prove internal RTL latency.

## Commands and exit codes

Run from this directory with a verified Python 3 interpreter:

```powershell
python -B .\frame_budget_offline.py .\samples\pass_833_834.csv --summary .\evidence\pass_summary.json
python -B .\frame_budget_offline.py .\samples\fail_processing_834.csv --summary .\evidence\fail_processing_834_summary.json
python -B .\frame_budget_offline.py .\samples\fail_underrun.csv --summary .\evidence\fail_underrun_summary.json
python -B .\frame_budget_offline.py .\samples\error_missing_field.csv --summary .\evidence\error_missing_field_summary.json
python -B .\run_acceptance.py
```

CLI exit codes:

- `0`: CSV is valid and all offline budget rules pass.
- `1`: CSV is well formed but a deadline, frame-period, counter, or underrun
  rule fails.
- `2`: CSV/file/schema error prevents a trustworthy decision.

`run_acceptance.py` expects the valid case to exit 0, the two policy-negative
cases to exit 1, and the malformed schema case to exit 2.  It also runs six
unit tests and writes:

- `evidence/acceptance.txt`
- `evidence/ACCEPTANCE_RECEIPT.json`
- three deterministic case summaries

Actual bounded self-check performed for this delivery:

```text
C:\Users\songdongkuan\miniconda3\python.exe -B .\run_acceptance.py
unit_tests: expected=0 actual=0 PASS (6 tests)
valid_833_834_distribution: expected=0 actual=0 PASS
reject_processing_834: expected=1 actual=1 PASS
reject_underrun: expected=1 actual=1 PASS
reject_missing_field_schema: expected=2 actual=2 PASS
OVERALL: PASS; process exit 0
```

## Scope and unverified items

Verified here: parser behavior, 833/834 distribution reporting, strict
`max_processing_cycles < 834`, nonzero-underrun rejection, malformed evidence
rejection, counter rollback detection, and deterministic summary generation.

Not verified here: real `vlog`/`vsim`, any actual R04 frame export, MIDI/audio
function, RTL arithmetic, ModelSim tool identity, synthesis, Gowin, PnR/STA,
bitstream, board behavior, DAC output, or end-to-end latency.  The future real
ModelSim input combination and execution budget still require M2 confirmation.
