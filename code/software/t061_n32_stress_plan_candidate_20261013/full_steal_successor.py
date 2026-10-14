"""Select the actual thirty-third allocation and swap full slot descriptors."""


FIELDS = ((4, 1), (5, 1), (6, 10), (7, 32), (8, 8), (9, 4), (10, 4), (11, 32))


def steal_index(operations):
    matches = [i for i, op in enumerate(operations)
               if op.get("case_id") == "C01_FILL32_STEAL33" and op.get("op") == "note_on"
               and (op.get("source"), op.get("channel"), op.get("note"), op.get("velocity"))
               == (3, 15, 100, 1000)]
    if len(matches) != 1:
        raise ValueError("C_FULL_STEAL_UNIQUE_INPUT_REQUIRED")
    index = matches[0]
    fills = [op for op in operations[:index]
             if op.get("case_id") == "C01_FILL32_STEAL33" and op.get("op") == "note_on"]
    if len(fills) != 32:
        raise ValueError("C_FULL_STEAL_AFTER_32_ALLOCATIONS")
    return index


def swap_descriptors(line):
    row = line.split()
    if len(row) != 12 or row[0] != "U":
        raise ValueError("C_FULL_STEAL_ROUTE_SCHEMA")
    for field, width in FIELDS:
        value, mask = int(row[field], 16), (1 << width)-1
        a, b = value & mask, (value >> width) & mask
        row[field] = "%x" % ((value & ~(mask | (mask << width))) | b | (a << width))
    return " ".join(row) + "\n"


def mutate_full_steal(original, operations):
    victim = steal_index(operations)
    active = None
    candidate = None
    complete = False
    for i, line in enumerate(original):
        row = line.split()
        if row and row[0] == "OP":
            if row[3] == "BEGIN":
                active = int(row[2])
            elif int(row[2]) == victim:
                complete = True
                break
            else:
                active = None
        elif row and row[0] == "U" and active == victim:
            candidate = i
    if not complete or candidate is None:
        raise ValueError("C_FULL_STEAL_OBSERVATION_REQUIRED")
    changed = list(original)
    changed[candidate] = swap_descriptors(original[candidate])
    if changed[candidate] == original[candidate]:
        raise ValueError("C_FULL_STEAL_MUTATION_NO_CHANGE")
    return changed, {"victim_operation": victim, "route_line_index": candidate,
                     "expected_victim_slot": 0, "mutated_victim_slot": 1,
                     "swapped_fields": ["occupied", "releasing", "velocity", "fcw",
                                        "note", "source", "channel", "generation"]}
