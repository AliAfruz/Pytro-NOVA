"""Minimal, lossless *plot-ready* CSV exports for Metrohm NOVA files.

CV/LSV/DPV/SWV: applied potential (V) versus current (A).
GCD/CP/OCP: time (s) versus potential (V). CA: time (s) versus current (A).
EIS: Nyquist (Z' vs -Z''), Bode magnitude and phase versus frequency.

Each curve gets one two-column CSV, no duplicate raw/analysis/meta CSV files.
Recorded numeric values are copied without smoothing, fitting, interpolation,
or any unit conversion.  Only currently decoded CV/EIS datasets are exported.
"""
from __future__ import annotations

import csv
import math
import os
import re
import shutil
import tempfile
from pathlib import Path
from techniques import TECHNIQUES


PLOT_SPEC = {
    'CV': (
        ('Current_vs_Voltage', ('potential_v', 'current_a')),
    ),
    'GCD': (('Potential_vs_Time', ('time_s','potential_v')),),
    'LSV': (('Current_vs_Voltage', ('potential_v','current_a')),),
    'DPV': (('Current_vs_Voltage', ('potential_v','current_a')),),
    'SWV': (('Current_vs_Voltage', ('potential_v','current_a')),),
    'CA': (('Current_vs_Time', ('time_s','current_a')),),
    'CP': (('Potential_vs_Time', ('time_s','potential_v')),),
    'OCP': (('Potential_vs_Time', ('time_s','potential_v')),),
    'EIS': (
        ('Nyquist', ('z_real_ohm', 'neg_z_imag_ohm')),
        ('Bode_Magnitude', ('frequency_hz', 'z_mod_ohm')),
        ('Bode_Phase', ('frequency_hz', 'neg_phase_deg')),
    ),
}


def _safe_filename(text):
    text = re.sub(r'[^\w.\-]+', '_', str(text), flags=re.UNICODE).strip('._')
    return text[:80] or 'measurement'


def _cell(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f'Non-numeric measurement value: {value!r}')
    if not math.isfinite(value):
        raise ValueError('Cannot export a nonfinite measurement value')
    # Keep the complete floating-point precision of the decoded measurement.
    return format(value, '.17g') if isinstance(value, float) else str(value)


def _write_xy_csv(path, headers, rows):
    with path.open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.writer(handle, lineterminator='\r\n')
        writer.writerow(headers)
        writer.writerows([_cell(n) for n in row] for row in rows)


def _make_output_dir(parent, basename):
    stem = _safe_filename(basename) + '_NOVA_PLOTS'
    for suffix in range(1, 10001):
        path = parent / (stem if suffix == 1 else f'{stem}_{suffix}')
        if not path.exists():
            return path
    raise OSError('Too many prior export folders')


def export_csv_package(doc, input_path, output_parent, dataset_name=None):
    """Export one plot CSV per CV/LSV/DPV/SWV/GCD/CA/CP/OCP, three for EIS.

    ``dataset_name`` optionally exports only the currently selected dataset.
    Creates a new non-overwriting output folder and returns a JSON-safe summary.
    """
    parent = Path(output_parent).expanduser().resolve()
    if not parent.is_dir():
        raise ValueError(f'CSV destination directory does not exist: {parent}')
    all_datasets = doc.get('datasets', [])
    if dataset_name is None:
        selected = list(enumerate(all_datasets, 1))
    else:
        selected = [(i, ds) for i, ds in enumerate(all_datasets, 1)
                    if ds.get('name') == dataset_name]
        if not selected:
            raise ValueError(f'Dataset {dataset_name!r} was not found')

    destination = _make_output_dir(parent, Path(input_path).stem)
    stage = Path(tempfile.mkdtemp(prefix='.nova_plot_csv_', dir=parent))
    files = []
    points = 0
    try:
        for number, ds in selected:
            kind = ds.get('kind')
            if kind not in PLOT_SPEC:
                # Do not silently label an unknown technique as CV/EIS.
                raise ValueError(f'Unsupported technique {kind!r} in {ds.get("name", number)}')
            columns = ds['columns']
            index = {col['key']: j for j, col in enumerate(columns)}
            values = ds['values']
            if len(values) != ds['point_count']:
                raise ValueError(f'Point count mismatch in {ds["name"]}')
            if any(len(row) != len(columns) for row in values):
                raise ValueError(f'Column count mismatch in {ds["name"]}')
            points += len(values)
            basename = f'{number:02d}_{_safe_filename(ds["name"])}'
            for title, requested in PLOT_SPEC[kind]:
                missing = [key for key in requested if key not in index]
                if missing:
                    raise ValueError(f'Missing {kind} columns {missing!r} in {ds["name"]}')
                filename = f'{basename}_{title}.csv'
                headers = [columns[index[key]]['label'] for key in requested]
                rows = ([row[index[key]] for key in requested] for row in values)
                _write_xy_csv(stage / filename, headers, rows)
                files.append(filename)

        (stage / 'README.txt').write_text(
            'PYTRO-NOVA | PLOT CSV EXPORT\n\n'
            f'Source: {Path(input_path).name}\n'
            f'Datasets exported: {len(selected)}\n\n'
            'CV: Applied potential (V) on X; working electrode current (A) on Y.\n'
            "EIS Nyquist: Z' (ohm) on X; -Z'' (ohm) on Y.\n"
            'EIS Bode magnitude: Frequency (Hz) on X; |Z| (ohm) on Y.\n'
            'EIS Bode phase: Frequency (Hz) on X; stored -Phase (deg) on Y.\n\n'
            'One header row + two numeric columns per CSV.\n'
            'Values are unsmoothed, unfitted and in original measurement order.\n'
            'Files are UTF-8 with BOM, comma separated, CRLF line endings, dot decimals.\n'
            'Other techniques: GCD/CP/OCP potential vs time; LSV/DPV/SWV current vs voltage; CA current vs time.\n'
            'All numeric values use SI units and measured point order, with no fit or smoothing.\n'
            'The source file remains unchanged; only successfully decoded signals are included.\n',
            encoding='utf-8'
        )
        os.rename(stage, destination)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise

    return {
        'ok': True, 'folder': str(destination), 'datasets': len(selected),
        'data_points': points, 'csv_files': len(files),
        'plot_csv_files': len(files), 'files': files,
    }
