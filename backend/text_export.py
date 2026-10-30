"""Reproducible, non-overwriting TXT/TSV exports of decoded NOVA measurements.

No smoothing, resampling, unit conversion, or inferred column values are applied.
Derived/inferred columns already supplied by the decoder are explicitly named.
"""
from __future__ import annotations

import csv
import json
import math
import os
import shutil
import tempfile
from pathlib import Path

from csv_package import PLOT_SPEC, _cell, _safe_filename


def _format_value(value):
    _cell(value)  # Numeric type/finiteness validation shared with the CSV exporter.
    # Shortest decimal that round-trips to the same binary64 float.
    return repr(value) if isinstance(value, float) else str(value)


def _write_tsv(path, headers, rows):
    """Tab-separated UTF-8, shortest lossless round-trippable float strings."""
    with path.open('w', newline='', encoding='utf-8') as output:
        writer = csv.writer(output, delimiter='\t', lineterminator='\n')
        writer.writerow(headers)
        for row in rows:
            writer.writerow([_format_value(number) for number in row])


def _select_datasets(document, dataset_name):
    all_datasets = document.get('datasets', [])
    selected = [(idx, ds) for idx, ds in enumerate(all_datasets, 1)
                if dataset_name is None or ds.get('name') == dataset_name]
    if dataset_name is not None and not selected:
        raise ValueError(f'Dataset {dataset_name!r} was not found')
    if not selected:
        raise ValueError('No populated datasets found in source measurement')
    return selected


def _validate_dataset(ds):
    name = ds.get('name', '<unnamed>')
    columns = ds['columns']
    rows = ds['values']
    if not columns or len({col['key'] for col in columns}) != len(columns):
        raise ValueError(f'Invalid or duplicate columns in {name}')
    if len(rows) != ds['point_count']:
        raise ValueError(f'Point count mismatch in {name}')
    for lineno, row in enumerate(rows, 1):
        if len(row) != len(columns):
            raise ValueError(f'Column count mismatch in {name}, row {lineno}')
        for value in row:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f'Nonfinite or non-numeric measurement in {name}, row {lineno}')
    return {col['key']: index for index, col in enumerate(columns)}


def export_text_package(document, input_path, output_parent, dataset_name=None):
    """Export full datasets, plot-ready XY files, and original recorded segments.

    Output is created in a uniquely named folder. Contents are written to a
    staging directory and published only after successful completion.
    """
    parent = Path(output_parent).expanduser().resolve()
    if not parent.is_dir():
        raise ValueError(f'TXT destination directory does not exist: {parent}')
    selected = _select_datasets(document, dataset_name)
    base = _safe_filename(Path(input_path).stem) + '_NOVA_TEXT'
    destination = None
    for seq in range(1, 10001):
        candidate = parent / (base if seq == 1 else f'{base}_{seq}')
        if not candidate.exists():
            destination = candidate
            break
    if destination is None:
        raise OSError('Too many prior TXT export folders')
    stage = Path(tempfile.mkdtemp(prefix='.nova_text_stage_', dir=parent))
    files = []
    total_points = 0
    try:
        for idx, ds in selected:
            column_index = _validate_dataset(ds)
            columns = ds['columns']
            rows = ds['values']
            total_points += len(rows)
            name = f'{idx:02d}_{_safe_filename(ds["name"])}'
            raw_path = Path('full_data') / f'{name}_All_Columns.txt'
            (stage / raw_path.parent).mkdir(exist_ok=True)
            _write_tsv(stage / raw_path, [col['label'] for col in columns], rows)
            files.append({'path': raw_path.as_posix(), 'dataset': ds['name'],
                          'type': 'all_columns', 'rows': len(rows),
                          'keys': [col['key'] for col in columns]})

            # Preserve both measured axes and original order. EIS has three
            # distinct plots, rather than a fabricated single mixed plot.
            for plot_name, keys in PLOT_SPEC.get(ds['kind'], ()):
                missing = [key for key in keys if key not in column_index]
                if missing:
                    raise ValueError(f'Missing {ds["kind"]} columns {missing!r} in {ds["name"]}')
                plot_path = Path('plot_data') / f'{name}_{plot_name}.txt'
                (stage / plot_path.parent).mkdir(exist_ok=True)
                _write_tsv(stage / plot_path,
                           [columns[column_index[key]]['label'] for key in keys],
                           ([row[column_index[key]] for key in keys] for row in rows))
                files.append({'path': plot_path.as_posix(), 'dataset': ds['name'],
                              'type': 'xy_plot', 'rows': len(rows), 'keys': list(keys)})

            # Separate actual recorded GCD/OCP plot fragments to prevent
            # plotters from drawing false lines between instrument levels.
            # "cycle" values, if present, are INFERRED by the decoder.
            if ds['kind'] in ('GCD', 'OCP') and 'segment' in column_index:
                segment_col = column_index['segment']
                grouped = {}
                for row in rows:
                    segment = row[segment_col]
                    if not float(segment).is_integer() or segment <= 0:
                        raise ValueError(f'Invalid recorded segment identifier in {ds["name"]}')
                    grouped.setdefault(int(segment), []).append(row)
                for segment, subset in grouped.items():
                    segment_path = Path('recorded_segments') / f'{name}_Segment_{segment:04d}.txt'
                    (stage / segment_path.parent).mkdir(exist_ok=True)
                    _write_tsv(stage / segment_path, [col['label'] for col in columns], subset)
                    files.append({'path': segment_path.as_posix(), 'dataset': ds['name'],
                                  'type': 'recorded_segment', 'rows': len(subset),
                                  'segment_id': segment,
                                  'keys': [col['key'] for col in columns]})

        manifest = {
            'format': 'Pytro-NOVA TSV 1',
            'source_file': Path(input_path).name,
            'source_metadata': document.get('metadata', {}),
            'warnings': document.get('warnings', []),
            'datasets': [{'name': ds['name'], 'kind': ds['kind'],
                          'point_count': ds['point_count'], 'columns': ds['columns'],
                          **({'cycle_source': ds['cycle_source']}
                             if 'cycle_source' in ds else {})}
                         for _, ds in selected],
            'files': files,
        }
        (stage / 'manifest.json').write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False) + '\n',
            encoding='utf-8')
        (stage / 'README.txt').write_text(
            'PYTRO-NOVA - CLEAN TEXT EXPORT\n\n'
            f'Source: {Path(input_path).name}\n'
            f'Datasets: {len(selected)} | total original measurement rows: {total_points}\n\n'
            'full_data/: one TXT per decoded dataset; every column and row retained.\n'
            'plot_data/: separate two-column TXT files for each scientific XY plot.\n'
            'recorded_segments/: GCD/OCP segments in separate TXT files, where available.\n'
            'manifest.json: provenance, original units, dataset names, and decoder warnings.\n\n'
            'Plain UTF-8 text, TAB separators, one header row with units, LF newlines,\n'
            'period decimal separator; shortest lossless round-trip float values.\n'
            'No interpolation, smoothing, fitting or added physical measurements.\n'
            'Inferred GCD cycle labels and derived elapsed times are explicitly marked;\n'
            'do not interpret inferred cycles as NOVA-recorded cycle counter values.\n'
            'Signals not decoded from the original file cannot be recovered by export.\n'
            'The source file is never modified.\n',
            encoding='utf-8')
        os.rename(stage, destination)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return {
        'ok': True, 'folder': str(destination), 'datasets': len(selected),
        'data_points': total_points, 'text_files': len(files),
        'files': [file['path'] for file in files],
    }
