# Failure history

RUN_01 was consumed once and failed before completing its seven cases.  The
first positive fixture reached an accepted MIDI event at cycle 988480 after
deliberate backpressure.  The bridge required the acceptance cycle to remain
inside the generator's nominal arrival window and rejected the row with
`EVENT_ACCEPT_PLAN_ASSOCIATION_NOT_UNIQUE:988480:[]`.  Frozen inputs all
matched; elapsed time was 0.20785880088806152 s and the raw stderr SHA-256 is
`e4704b2897dfa7b500427147460b5ca88b64e0545fe330486b2c89b2ab1ba147`.

The minimal repair keeps the payload-unique link but labels it
`PLAN_PAYLOAD_UNIQUE_OUTSIDE_ARRIVAL_WINDOW`; it does not turn the nominal
arrival window into an authoritative acceptance deadline.  RUN_02 is limited
to that failed positive fixture and the observed backpressure association.
