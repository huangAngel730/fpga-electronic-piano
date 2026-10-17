"""Source-clock calendar, not capture-derived timing or physical STA.

Replay b2_audio_backend's PITCH/ADVANCE/SETTLE/ROM/GAIN/ACCUM states.
L is post-NBA GAIN; A and the first visible valid are pre-NBA TB taps.
The B2b wrapper adds two edges (bank commit qualification and registered HOLD)
to the backend's first visible valid. P/O handshake delay is a separate event.
"""
from dataclasses import dataclass


def deadline_missed(first_visible, accepted):
    """Both source age registers reset at admission, exclude that edge."""
    return int(first_visible - accepted - 1 >= 833)


@dataclass(frozen=True)
class Calendar:
    advance: int
    lanes: tuple
    backend_first: int

    @property
    def wrapper_first(self):
        return self.backend_first + 2


def backend_calendar(accepted, n, response):
    if (type(accepted) is not int or accepted < 0 or type(n) is not int
            or n not in (4, 8, 16, 32) or type(response) is not int
            or not 1 <= response <= 64):
        raise ValueError('CLOCK_PARAMETERS')
    cycle, state, wait, slot = accepted, 'PITCH', 7, 0
    lanes, advance = [], None
    while True:
        cycle += 1
        if state == 'PITCH':
            if wait != 1:
                wait -= 1
            else:
                state = 'ADVANCE'
        elif state == 'ADVANCE':
            advance, wait, state = cycle, 4, 'SETTLE'
        elif state == 'SETTLE':
            if wait:
                wait -= 1
            else:
                state = 'ROM_START'
        elif state == 'ROM_START':
            wait, state = response, 'ROM_WAIT'
        elif state == 'ROM_WAIT':
            if wait != 1:
                wait -= 1
            else:
                state = 'GAIN'
        elif state == 'GAIN':
            lanes.append(cycle)
            state = 'ACCUM'
        elif state == 'ACCUM':
            if slot == n - 1:
                # result_valid <= 1 at this edge; pre-NBA observer sees it next.
                return Calendar(advance, tuple(lanes), cycle + 1)
            slot += 1
            state = 'ROM_START'
