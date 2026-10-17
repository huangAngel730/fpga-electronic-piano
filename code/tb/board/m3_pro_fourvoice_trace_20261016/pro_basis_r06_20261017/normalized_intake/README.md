# R06 normalized intake software fixtures

This directory contains only the case list for the new Python intake. The
self-test generates a bounded 836-cycle synthetic 61-field trace in an
exclusive run directory. It does not instantiate or inspect a DUT and does
not run HDL compilation or simulation.

The positive fixture exercises canonical preservation, the B2 29-column
projection and the repaired-D3 JSONL projection. Negative cases cover active
control X, wrong request identity, wrong epoch, a dropped source line,
same-edge order, a bad trace identity, EOF without finish and a missing frame
from a frozen independent plan. The cancellation pair proves that D3 exports
the active request ID while canonical data retains the independent cancel
reason, and rejects cancellation without an active request. Pending cases cover unfrozen same-edge,
frame-plan and finish contracts plus idle monitor X incompatibility with the
current B2 all-columns-known policy.
