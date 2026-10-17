# R7-C C9 mechanical oracle bridge successor

Status: `L0_STATIC_SOURCE_READY_NOT_RUN`.

This additive successor binds the published C9 source closure, source decision, capture contract, 74-field normalized schema and 67-port observer exports by exact path, byte count and SHA-256. It accepts a JSONL trace whose rows contain the exact ordered 74 fields and emits a mechanical row index. Every output row retains the full fields object, source path, capture SHA, source line, cycle, epoch, PRE_NBA phase and raw-line SHA.

Role A's future `PUBLIC_ROWS_C9.jsonl` uses `M3_R7A_C9_PUBLIC_ROW_V1`, so it is not the native R7-C envelope. The `--input-format r7a-public-c9` adapter consumes that file directly: it requires Role A's exact envelope and source tuple, verifies the same 74-field set, copies every field value into frozen schema order, carries `raw_sha256` into `raw_capture_sha256`, and leaves `plan_association=null`. It preserves the upstream source, raw ports, missing reasons, events and semantics under `upstream_evidence`. If the published base binding still has a pending trace, the CLI binds the actual input path, byte count and SHA-256 in memory and records that descriptor in the result. The physical Role A row also stays bound by `raw_line_sha256`; no hand-edited intermediary JSON is needed. The actual `PUBLIC_ROWS_C9.jsonl` is still absent because Role A execution has not occurred.

The bridge preserves `apply_kind`, `apply_mask`, `router_apply_seq`, `router_apply_seq_valid`, `config_take`, and the separate upstream/effect/feedback clip masks. Kinds 3/4/8 with zero data/sequence and invalid sequence are classified as invalid-cause sentinels. A valid sequence zero remains legal. Kinds 1/2 sharing one valid sequence remain two ordered rows. Because no independent plan body and actual acceptance mapping are available, any non-null `apply_event_seq` or declaration-only association is rejected; the output sequence remains null and pending. Router sequence equality cannot substitute for that evidence.

`advance_frame_req_id` remains a request tag and never becomes FRAME F. FRAME F comes only from `frame_tick`. Four-lane advance requires exact 4-bit `1111`; partial masks and X/Z/null keep their raw value plus an explicit false or pending reason. Raw `audio_stable` is retained while its owner-approved policy remains pending.

The callable CLI is:

```text
python c9_oracle_bridge.py --binding <binding.json> --trace <rows.jsonl> --repo-root <repo> --input-format <r7c-contract|r7a-public-c9> --output <index.json>
```

`selftest.py` exposes import-side-effect-free `run_case(case_id, output_dir)`. The 17 cases in `CASES.json` are new C9 successor cases and remain `NOT_RUN`; they neither reuse nor consume the old R7-C group. The list includes Role A adapter positive and field-loss negative cases, both unexecuted. No candidate was imported, no DSP oracle was created, and no Python/HDL/EDA/device test was run while preparing this source.

The original bridge, its first failure evidence, repaired single-case evidence, and its remaining old cases are unchanged. Real C9 trace, independent input-plan mapping, actual lane-tick evidence, `audio_stable` policy, full frame plan, PCM/oracle validation and execution authority remain pending. `board_release_allowed=false`.
