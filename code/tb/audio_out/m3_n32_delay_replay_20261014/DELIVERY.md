# M3 N32 delay replay delivery

Status is filled by the actual `run_replay.py` receipts.  The intended claim
is limited to an isolated path:

`frozen C_FULL real publications → frozen M1 stereo delay RTL → frozen M2 transport/I2S/observer`

Expected deliverables in the task output directory:

- `PRE_EXECUTION_IDENTITY.json`: machine, tool, input/source SHA and budgets;
- `extracted_capture/`: paired K/P vector, source JSONL and extraction receipt;
- positive and compiled-mutant compile/simulation logs and traces;
- independent checker receipts and Python self-test logs;
- `COMMANDS.jsonl`: complete command, exit code, timeout and elapsed records;
- `RESULT.json` and `FINAL_RECEIPT.json`;
- `SEALED_RESULT_R01/{MANIFEST.json,seal.json,snapshot.zip}`;
- `transfer/M3_N32_DELAY_REPLAY_20261015.zip` and transfer receipt.

No Git write, synthesis, PnR, STA, programmer, cabling, download or flash is
part of this execution.  M2 remains responsible for final review and any
production integration/resource/physical timing decision.
