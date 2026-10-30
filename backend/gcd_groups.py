"""Visual comparison groups for measured GCD segments.

The group assignments are deliberately *plot recommendations*, not a claim
about instrument cycle numbers, applied current, or sample identity.
"""
from __future__ import annotations

import math


def comparable_cycle_groups(fragments, rows):
    """Return contiguous cycles with similar time scale and voltage ceiling.

    `fragments` are time-ordered, signal-verified level records. `rows` contain
    [time, potential, inferred_cycle, segment, trend, derived_cycle_time].
    Avoid overlaying e.g. a 4 s formation cycle and a 4,000 s hold as though
    they were repetitions under the same conditions.
    """
    stats = {}
    for time_s, potential_v, cycle, _segment, _phase, elapsed_s in rows:
        cycle = int(cycle)
        if cycle not in stats:
            stats[cycle] = [elapsed_s, elapsed_s, potential_v, potential_v, 1]
        else:
            rec = stats[cycle]
            rec[0] = min(rec[0], elapsed_s)
            rec[1] = max(rec[1], elapsed_s)
            rec[2] = min(rec[2], potential_v)
            rec[3] = max(rec[3], potential_v)
            rec[4] += 1
    if not stats:
        return [], []

    cycles = sorted(stats)
    groups = []
    current = [cycles[0]]
    def match(c1, c2):
        a, b = stats[c1], stats[c2]
        da = a[1] - a[0]
        db = b[1] - b[0]
        if da <= 0 or db <= 0:
            return False
        # 30% tolerance on duration and 8% of potential span on upper cutoff.
        duration_ratio = max(da, db) / min(da, db)
        voltage_span = max(a[3]-a[2], b[3]-b[2], 0.25)
        return (duration_ratio <= 1.30 and
                abs(a[3]-b[3]) <= max(0.035, 0.08*voltage_span) and
                abs(a[2]-b[2]) <= max(0.035, 0.08*voltage_span))

    for cycle in cycles[1:]:
        if cycle == current[-1]+1 and match(current[-1], cycle):
            current.append(cycle)
        else:
            if len(current) >= 2:
                groups.append(current)
            current = [cycle]
    if len(current) >= 2:
        groups.append(current)

    summaries = []
    for group in groups:
        durations = [stats[c][1] - stats[c][0] for c in group]
        count = sum(stats[c][4] for c in group)
        summaries.append({
            'cycles': group,
            'label': f'Cycles {group[0]}–{group[-1]} · {min(durations):.0f}–{max(durations):.0f} s',
            'points': count,
            'duration_min_s': min(durations),
            'duration_max_s': max(durations),
        })
    # Favor a multi-curve view containing many real data points without
    # silently plotting unrelated durations/voltage limits together.
    default = max(summaries, key=lambda entry: (len(entry['cycles']) >= 2, entry['points']))['cycles'] if summaries else [cycles[0]]
    return summaries, default
