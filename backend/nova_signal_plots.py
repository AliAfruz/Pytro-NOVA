"""Recover NOVA's actual stored plot-series for galvanostatic and OCP levels.

Verified on user-supplied GCD.nox and self discharge.nox (NOVA EcoChemie100).
No instrument control and no arbitrary .NET object instantiation.
Plot X/Y are read verbatim and validated against the parent handler's
CalcTime / EI_0.CalcPotential arrays; no inference from a filename.
"""
from __future__ import annotations

import math
from gcd_groups import comparable_cycle_groups


def _clean_xy(params, expected_x, expected_y):
    x, y = params.get('X'), params.get('Y')
    if not (isinstance(x, list) and isinstance(y, list) and len(x) == len(y) and len(x) > 1):
        return None
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for a in (x, y) for v in a):
        return None
    # Verify both axes represent the claimed physical signals (not an arbitrary
    # user-created plot with the same plot command name).
    if not (isinstance(expected_x, list) and isinstance(expected_y, list)
            and len(x) == len(expected_x) == len(expected_y)):
        return None
    probe = {0, len(x) // 2, len(x) - 1}
    for i in probe:
        if not (math.isclose(x[i], expected_x[i], abs_tol=1e-6, rel_tol=1e-7)
                and math.isclose(y[i], expected_y[i], abs_tol=1e-6, rel_tol=1e-7)):
            return None
    return x, y


def recover_level_plots(objects, reader, deref_fn, parameter_fn):
    """Recover FHLevelGalvanostatic and FHLevelOcp PlotsEvst as grouped datasets.

    Consecutive galvanostatic rising/falling segments are paired into *inferred*
    cycles, never described as instrument-recorded cycle numbers. OCP levels are
    separate traces/intervals. Unpopulated signal placeholders are ignored.
    """
    by_kind = {'GCD': [], 'OCP': []}
    warnings = []
    seen_parents = set()
    for command in objects:
        if not isinstance(command, dict) or command.get('__class__') != 'EcoChemie.Shared.SignalSetCommand':
            continue
        if deref_fn(command.get('CommandBase+_name'), reader) != 'PlotsEvst':
            continue
        parent = deref_fn(command.get('ExecCommandBase+_parent'), reader)
        if not isinstance(parent, dict):
            continue
        cls = parent.get('__class__', '')
        fhname = deref_fn(parent.get('FunctionHandler+_name'), reader)
        if cls.endswith('.FHLevelOcp') and fhname == 'FHLevelOcp':
            kind = 'OCP'
        elif cls.endswith('.FHLevel') and fhname == 'FHLevelGalvanostatic':
            kind = 'GCD'
        else:
            continue
        # Each FHLevel can own more than one plot command. Keep one verified
        # time-potential trace per handler, not duplicated copies of one signal.
        parent_id = id(parent)
        if parent_id in seen_parents:
            continue
        plot_params = parameter_fn(command, reader)
        if not plot_params.get('X'):
            continue
        handler_params = parameter_fn(parent, reader)
        verified = _clean_xy(plot_params, handler_params.get('CalcTime'),
                             handler_params.get('EI_0.CalcPotential'))
        if verified is None:
            warnings.append(f'Skipped unverified {kind} time/potential plot; signal axes did not match the handler arrays.')
            continue
        seen_parents.add(parent_id)
        x, y = verified
        by_kind[kind].append({'x': x, 'y': y, 'start': x[0], 'end': x[-1],
                              'rising': y[-1] >= y[0]})

    result = []
    for kind, fragments in by_kind.items():
        if not fragments:
            continue
        # The signal's time origin is as stored by NOVA. Do not rebase X.
        # These recorded segments are in natural command execution order.
        # Assign groups for display; do not claim they are authoritative
        # electrochemical cycle IDs.
        fragments.sort(key=lambda f: f['start'])
        rows = []
        group_id = 0
        group_start = None
        for j, fragment in enumerate(fragments):
            if kind == 'OCP':
                group_id = j + 1
            elif j == 0 or (fragment['rising'] and not fragments[j-1]['rising']):
                group_id += 1
            elif j > 0 and fragment['rising'] == fragments[j-1]['rising']:
                # Multiple same-direction levels: draw as separate groups.
                group_id += 1
            segment_number = j+1
            phase = (1 if fragment['rising'] else -1) if kind == 'GCD' else 0
            if j == 0 or group_id != previous_group:
                group_start = fragment['start']
            previous_group = group_id
            for x, y in zip(fragment['x'], fragment['y']):
                rows.append([float(x), float(y), group_id, segment_number, phase,
                             float(x-group_start)])
        group_count = max(int(row[2]) for row in rows)
        comparable, recommended = comparable_cycle_groups(fragments, rows) if kind == "GCD" else ([], [])
        result.append({
            'name': f'{kind} 1', 'kind': kind,
            'columns': [
                {'key':'time_s','label':'Time (s)'},
                {'key':'potential_v','label':'Potential (V)'},
                {'key':'cycle','label':'Inferred cycle' if kind == 'GCD' else 'Interval'},
                {'key':'segment','label':'Recorded segment'},
                {'key':'phase','label':'Potential trend (+1 rising, -1 falling, 0 rest)'},
                {'key':'cycle_time_s','label':'Cycle / interval elapsed time (s) [derived]'},
            ],
            'values':rows, 'point_count':len(rows),
            'default_x':'cycle_time_s','default_y':'potential_v',
            'source':'nox-verified-signal-plots',
            'cycle_count':group_count, 'segment_count':len(fragments),
            'cycle_source':'inferred from potential trends, not instrument cycle counter' if kind=='GCD' else 'one interval per OCP level',
            'comparable_cycle_groups': comparable,
            'recommended_cycles': recommended,
            'note':'Measured time/potential preserved, displayed default X = derived elapsed time within group; switch X axis to Time (s) for original timestamps. No interpolation.',
        })
        if kind == 'GCD':
            warnings.append('GCD cycle IDs are inferred from potential trends, not recorded cycle numbers. Display defaults to comparable-duration curves instead of mixing very different test steps. Confirm current and cycle boundaries in NOVA before capacitance calculations.')
        else:
            warnings.append('OCP intervals use separate recorded levels; their interval labels are not a physical cycling count.')
    return result, warnings
