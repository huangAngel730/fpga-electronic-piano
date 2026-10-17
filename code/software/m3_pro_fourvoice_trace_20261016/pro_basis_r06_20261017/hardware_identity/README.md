# Hardware identity validator

This isolated utility checks that a Tang Mega 138K Pro hardware record does not
promote reference-design facts into physical observations. It does not access a
board, invoke Gowin tools, or authorize programming.

Run against the pending production record from the repository root:

```powershell
python code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/hardware_identity/hardware_identity.py `
  --repo-root . `
  --record code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/hardware_identity/HARDWARE_IDENTITY_PENDING.json `
  --index code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/hardware_identity/REFERENCE_INDEX.json
```

Exit `0` means that the record is internally valid. `VALID_PENDING` is expected
until real photos and raw measurements are supplied; it is **not** board release.
Exit `2` is a fail-closed contract or evidence error.

An `OBSERVED` claim requires a hashed physical source of the appropriate kind.
Reference schematics/CST files can support candidate notes only. Fixture evidence
is accepted solely with `--allow-fixture` and must never be used for production.
Password, token, secret, private-key and license-key/server fields are rejected.
