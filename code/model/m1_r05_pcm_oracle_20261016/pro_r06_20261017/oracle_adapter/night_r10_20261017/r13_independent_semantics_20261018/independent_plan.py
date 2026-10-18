"""Independent input-word semantics. Observed PCM never enters this API."""


def word_fields(word):
    if type(word) is not int or not 0 <= word < 1 << 64 or word & 63:
        raise ValueError('INDEPENDENT_EVENT_WORD')
    return dict(kind=word >> 61, source=(word >> 57) & 15,
                channel=(word >> 53) & 15, note=(word >> 46) & 127,
                velocity=(word >> 36) & 1023)


def classify(mapping, allocator_factory):
    """Static plan classifier; allocator_factory is the unchanged pinned Oracle.

    Caller supplies independently approved epoch mapping. This never derives an
    epoch from trace, does not decide real finish, and is not run by assembly.
    """
    rows, previous, model = [], None, None
    for event in mapping:
        epoch = event['epoch']
        if type(epoch) is not int or epoch < 0:
            raise ValueError('INDEPENDENT_EPOCH_REQUIRED')
        if previous is not None and epoch < previous:
            raise ValueError('PLAN_EPOCH_ORDER')
        if epoch != previous:
            model, previous = allocator_factory(), epoch
        word = word_fields(int(event['expected_event_hex'], 16))
        ident = (word['source'], word['channel'], word['note'])
        matched = next((i for i, slot in enumerate(model.slots)
                        if slot is not None and slot[:3] == ident), None)
        on = word['kind'] == 0 and word['velocity'] > 0
        off = word['kind'] == 1 or word['kind'] == 0 and word['velocity'] == 0
        if not (on or off):
            raise ValueError('UNSUPPORTED_CONTROL_PROFILE')
        before = list(model.slots)
        if on:
            _, lane, _, _, allocation = model.step(1, 1, 0, *ident, 0)
            classification, stages = allocation, [1, 2]
        elif matched is None:
            lane, classification, stages = None, 'ignored_off', [7]
        elif before[matched][3] == 'active':
            lane, classification, stages = matched, 'matching_off', [6, 3, 4]
            model.step(1, 0, 1, *ident, 0)
        else:
            # Repeated off to a still-releasing slot has a kind6 control but no
            # new active->release transition. Never manufacture kind3/kind4.
            lane, classification, stages = matched, 'already_releasing_off', [6]
        rows.append(dict(event_seq=event['event_seq'], epoch=epoch,
                         expected_event_hex=event['expected_event_hex'],
                         identity=list(ident), lane=lane, classification=classification,
                         required_stages=stages, slots_before=before,
                         slots_after=list(model.slots), recency=list(model.order)))
    return rows


def validate_independent_plan(plan):
    if plan.get('independent_of_trace') is not True:
        raise ValueError('INDEPENDENT_PLAN_REQUIRED')
    seen, previous = set(), {}
    for event in plan['events']:
        key = event['epoch'], event['event_seq']
        if key in seen:
            raise ValueError('DUPLICATE_PLAN_EVENT')
        seen.add(key)
        word_fields(int(event['expected_event_hex'], 16))
        window = event['arrival_window']
        lo, hi = window['min_cycle'], window['max_cycle']
        if type(lo) is not int or type(hi) is not int or not 0 <= lo <= hi:
            raise ValueError('PLAN_ARRIVAL_WINDOW')
        if event['epoch'] in previous and lo < previous[event['epoch']]:
            raise ValueError('PLAN_EVENT_ORDER')
        previous[event['epoch']] = lo
    return plan


class ClockContract:
    """Sorted FRAME cursor and reset intervals; no set of every capture cycle."""
    def __init__(self, frames, reset, geometry):
        if frames.get('independent_of_trace') is not True:
            raise ValueError('FRAME_PLAN_NOT_INDEPENDENT')
        if reset.get('independent_of_trace') is not True or reset.get('profile') != 'ASSERT_OBSERVED_LOW_BEFORE_RELEASE_V1':
            raise ValueError('RESET_PROFILE_MISSING')
        self.frames = iter((ep['epoch'], cycle) for ep in frames['epochs'] for cycle in ep['frame_cycles'])
        self.next_frame, self.previous_frame = next(self.frames, None), None
        self.ranges, self.range_cursor = reset['low_ranges'], 0
        edges = reset.get('raw_edges', [])
        if not self.ranges or len(edges) != 2 * len(self.ranges):
            raise ValueError('RESET_ORIGINAL_EDGES_REQUIRED')
        last_end, last_time = -1, -1
        for i, interval in enumerate(self.ranges):
            lo, hi = interval['first_cycle'], interval['last_cycle']
            if not last_end < lo <= hi:
                raise ValueError('RESET_RANGES_OVERLAP_OR_REORDER')
            last_end = hi
            for edge, value, sampled in ((edges[2*i], 0, lo), (edges[2*i+1], 1, hi+1)):
                if edge['epoch'] != interval['epoch'] or edge['value'] != value or edge['first_sampled_cycle'] != sampled or not edge['time_ps'] > last_time:
                    raise ValueError('RESET_EDGE_SAMPLE_LINK')
                last_time = edge['time_ps']
        self.finish = frames['finish']
        self.geometry, self.cycle, self.epoch = geometry, -1, -1

    def row(self, fields):
        cycle, epoch = fields['cycle'], fields['epoch']
        if type(cycle) is not int or type(epoch) is not int or cycle != self.cycle + 1:
            raise ValueError('PUBLIC_POSEDGE_COVERAGE_GAP')
        self.cycle = cycle
        while self.range_cursor < len(self.ranges) and cycle > self.ranges[self.range_cursor]['last_cycle']:
            self.range_cursor += 1
        interval = self.ranges[self.range_cursor] if self.range_cursor < len(self.ranges) else None
        low = interval is not None and interval['first_cycle'] <= cycle <= interval['last_cycle']
        if fields['rst_n'] != int(not low):
            raise ValueError('RESET_ROWS_AND_ORIGINAL_PLAN_DIFFER')
        if low and epoch != interval['epoch'] or not low and epoch != self.epoch:
            raise ValueError('EPOCH_WITHOUT_RESET')
        self.epoch = epoch
        key = epoch, cycle
        if self.next_frame is not None and self.next_frame < key:
            raise ValueError('FRAME_PLAN_COVERAGE_MISMATCH')
        expected = self.next_frame == key
        if fields['frame_tick'] != int(expected):
            raise ValueError('FRAME_PLAN_COVERAGE_MISMATCH')
        if expected:
            self.previous_frame, self.next_frame = self.next_frame, next(self.frames, None)
            if self.next_frame is not None and self.next_frame <= self.previous_frame:
                raise ValueError('DUPLICATE_FRAME_PLAN_CYCLE')
        end = (self.finish['epoch'], self.finish['cycle'])
        if fields['finish'] != int(key == end) or key > end:
            raise ValueError('FINISH_MUST_BE_UNIQUE_FINAL_ROW')

    def complete(self):
        if self.next_frame is not None or self.cycle != self.geometry['row_count'] - 1 or self.cycle != self.finish['cycle']:
            raise ValueError('FRAME_OR_FINISH_INCOMPLETE')
