N32 D / C_FULL historical evidence association candidate, 2026-10-15
================================================================

Scope
-----
This is a read-only PC software checker and new successor association record.
It verifies exact historical bytes. It never extracts/imports/runs package code,
never invokes Icarus/VVP/Gowin, never downloads a bitstream or opens a serial port.
It does not alter any original D/C_FULL manifest, receipt, failure or consumed
marker. D remains PREPARED L0/L1, resources UNKNOWN, STA NOT_RUN, EDA calls zero.
M2 final review, hardware admission and future resource execution remain separate.

Run from the repository root with an already installed Python 3.10+ standard
library. No pip package, network, vendor tools or HDL simulator is required.
Paths below are examples; every --output must be a previously nonexistent path
inside this checkout's code/output/n32_d_cfull_binding_* tree. Arbitrary outputs,
dot-dot paths and reparse ancestry are rejected before mkdir; prepared/verified
children inside a task-prefixed acceptance directory are supported. --prepared
uses the same task output boundary, but historical ZIP/receipt inputs are read
only and may be elsewhere.
Run each command separately. The program supports isolated Python -I -S directly.

python -I -S -B -X utf8 code/software/n32_d_cfull_binding_candidate_20261015/binding_check.py prepare --abcd code/output/n32_publication_20261014_r01/transfer/M3_N32_ABCD_20261014_COMPLETE.zip --cfull code/output/n32_c_full_publication_20261014_r01/transfer/M3_N32_C_FULL_20261014.zip --receipt E:/FPGA/GAOYUNFPGA/Callback3/chat6/M2_REVIEW_RECEIPT.json --output code/output/n32_d_cfull_binding_prepare_20261015_r01

python -I -S -B -X utf8 code/software/n32_d_cfull_binding_candidate_20261015/binding_check.py verify --prepared code/output/n32_d_cfull_binding_prepare_20261015_r01 --output code/output/n32_d_cfull_binding_verify_20261015_r01

Prepare creates binding.json, prepared.json, receipt.json and events.jsonl in a
new exclusive directory. Verify re-reads the originals and recreates the whole
association, checks the saved binding and its identity, and produces new evidence
without changing the prepared directory. Success exits 0 with status
PASS_STATIC_BINDING_ONLY_T061_PARTIAL. Rejection exits 1 and records the exception,
actual argv/cwd, UTC times, source/docs/expectation SHA, runtime executable SHA and
available input before/after identities. argparse usage errors exit 2. Refusal to
overwrite an existing output cannot create a receipt in that existing directory;
the diagnostic goes to stdout/stderr for the external acceptance harness to keep.
Failure evidence is retained; no internal retry, path repair or tool replacement.

Independent identity authority
------------------------------
EXPECTED_IDENTITIES.json freezes the actual M2 receipt SHA and accepted ABCD and
C_FULL outer package lengths/SHA/commits, their D/C_FULL inner archive identities,
original and reused plans/receipts/capture, and original D handoff source identity.
The checker embeds the expectation file's exact SHA. There is no CLI override,
skip-SHA, prepare-current-input-as-expected, trust-candidate-manifest or execute
option. To qualify a different historical package requires a distinct reviewed
successor, not editing expected hashes to make a failure disappear.

The authority sources and their original paths/SHA are recorded in the expected
file and resulting binding. Only the actual M2 JSON receipt must be supplied;
the old handoff and review Markdown are provenance citations, not substitutes for
the approved package bytes. M2's original date/time and publication text are left
unaltered. SHA pins provide identity, not a cryptographic signature or new approval.

Exact checks and important distinctions
--------------------------------------
- ABCD 185 outer members, C_FULL 76, D 125 inner (124 data + MANIFEST),
  C_FULL 339 inner (338 data + MANIFEST). CRC, exact member sets and every manifest
  record length/SHA are checked. Inner and outer manifests must be the same bytes.
- D project manifest 45 records: 18 business HDL + 1 resource top + 2 include +
  5 ROM + 16 evidence + GPRJ/SDC/Tcl. All 45 payloads and evidence pointers match;
  the project subtree has no hidden inputs. GPRJ ordered19 HDL/device/SDC and Tcl
  project/top/include references are parsed as text, never evaluated.
- 25 shared business/include/ROM inputs map by full origin_snapshot, not basename,
  into current R02 plan inputs and original R01 history snapshot. All actual
  bytes, sizes and SHA must match. Every R01/R02 frozen input is checked against
  its plan, and source/tool after identities are compared with original records.
- D resource top m3_n32_resource fixes N32/RESPONSE1, disables injection and keeps
  clipped/public read ports. C_FULL simulated tb_c_n32_r1_v6 through
  b_n32_r1_wrapper plus vendor simulation model. The D resource top was NOT
  simulated by C_FULL. Shared business bytes are not proof of top equivalence.
- D still cites separately qualified segmented C, not continuous C_FULL. This new
  association explicitly records that difference, not a historical rebinding.
- Original R01 compile/simulate/check exit0 and mutation-check exit1 are preserved.
  R02 only rechecked software against the same real continuous capture; it did not
  run new RTL. Original capture is 45,522,685 bytes / daf92770... / exactly one END.
  Historical stats: 10,376 operations, 4,945 accepts, 4,942 publications, 158,144
  slot results, 4 retirements, max first-result347 cycles. These are provenance
  and existing report checks, NOT a repeat mathematical acceptance run.
- Normal C_FULL clipped is all0 and left/right equal; 24 named software mutations
  have 23 unique payloads. This does not add nonzero clip/stereo swap coverage,
  production N32, general continuous playing, synthesis, PnR, physical40MHz STA,
  board evidence or audible output. SDC25ns/setup1ns/hold.650ns are contract values,
  not measured slack. Reset upstream release and board I/O constraints remain M2.
- Historical installed-tool metadata is checked for continuity; no currently
  installed Icarus/Gowin executable/library is invoked or freshly qualified.

Security boundaries
-------------------
ZIP: no extraction; reject duplicate and casefold collisions, absolute/dot-dot/
backslash/drive/ADS/NUL/control/trailing-space/trailing-dot/reserved-device names,
non-NFC names, directories, symlinks and special files, encrypted entries, unknown
compression, bad CRC/truncation/overlap, >1,024 members, >64MiB archive or member,
>256MiB uncompressed total, or ratio>128. Real accepted archives fit these limits.
JSON: UTF-8, <=16MiB, bounded nesting, duplicate keys/NaN/Infinity rejected;
identity records have exactly bytes/int (not bool) and 64 lower-hex SHA fields.
Scoped contracts reject missing/extra D fields and bool-for-int substitution.
Filesystem inputs and outputs reject reparse/symlink ancestry; output never
overwrites. Archives and receipt are rehashed after verification. Sources/docs
and fixed expectations are rehashed before/after the CLI operation.

Software test interface
-----------------------
binding_check.py exports BindingError.code, ZipLimits, inspect_zip_bytes,
load_strict_json, validate_identity, validate_manifest_records,
validate_project_contract, validate_shared_inputs, validate_cfull_contract and
verify_bundle. Pure contract helpers let independent tests exercise semantic
counterexamples after structural parsing without exposing a production identity
bypass. Synthetic cases are software fixtures, not new N32 or D execution proof.
The separate test/harness/sealer files record actual tests and archive evidence.

Ownership / release
-------------------
Only this isolated candidate and task-prefixed new code/output directories are
written. Do not modify original D, C_FULL, formal RTL, ROM, protocol, constraints,
shared task/status tables or other dialogues. No package execution is authorized
by successful prepare/verify. Whole software delivery is self-reviewed; final
project acceptance belongs to M2. Handoff messages are pending user forwarding,
not automatically sent to any other conversation.
