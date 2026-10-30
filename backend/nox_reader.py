"""Read measured CV/EIS datasets from legacy Metrohm Autolab NOVA .nox files.

Pure Python; no NOVA, proprietary DLLs, .NET, pandas, or network required.
The .nox file is treated as *data*, never deserialized with .NET BinaryFormatter.

CLI examples:
    python nox_reader.py --summary measurement.nox
    python nox_reader.py --json measurement.nox > measurement.json
    python nox_reader.py --csv-dir exports measurement.nox
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import os
from pathlib import Path

from nrbf_lite import all_streams, deref, NrbfError
from techniques import extract_nox_techniques
from nova_signal_plots import recover_level_plots

CV_COLS = [
    ("potential_v", "Applied potential (V)"),
    ("time_s", "Time (s)"),
    ("current_a", "WE(1) current (A)"),
    ("we_potential_v", "WE(1) potential (V)"),
    ("scan", "Scan"),
    ("index", "Index"),
    ("q_plus_c", "Q+ (C)"),
    ("q_minus_c", "Q- (C)"),
]
EIS_COLS = [
    ("frequency_hz", "Frequency (Hz)"),
    ("z_real_ohm", "Z' (ohm)"),
    ("neg_z_imag_ohm", "-Z'' (ohm)"),
    ("z_mod_ohm", "|Z| (ohm)"),
    ("neg_phase_deg", "-Phase (deg)"),
]


def _r(value, reader):
    return deref(value, reader.objects)


def _list(value, reader):
    """Materialise one .NET List<T> preserving its _size (ignore spare capacity)."""
    value = _r(value, reader)
    if isinstance(value, list):
        return [_r(x, reader) for x in value]
    if not isinstance(value, dict):
        return []
    member = value.get('_items', value.get('Collection`1+items'))
    if member is None:
        return []
    values = _r(member, reader)
    if isinstance(values, dict):
        values = _list(values, reader)
    if not isinstance(values, list):
        return []
    return [_r(x, reader) for x in values[:value.get('_size',len(values))]]


def _parameters(command, reader):
    params = None
    for name in ('FunctionHandler+_commandParameters13', 'CommandBase+_commandParameters13'):
        if name in command:
            params = _r(command[name], reader)
            break
    if not isinstance(params, dict):
        return {}
    seq = _list(params.get('Collection`1+items', params.get('CollectionBase+list')), reader)
    result = {}
    for item in seq:
        if not isinstance(item, dict):
            continue
        name = _r(item.get('CommandParameter+_name',item.get('_name')), reader)
        if not isinstance(name,str):
            continue
        param = _r(item.get('_parameter', item.get('CommandParameter+_parameter')), reader)
        if not isinstance(param,dict):
            continue
        val = _r(param.get('_value',param.get('ParameterObject+_value')), reader)
        if isinstance(val,dict) or isinstance(val,list):
            result[name] = _list(val,reader)
        elif isinstance(val,(int,float,str,bool)):
            result[name] = val
    return result


def _dataset(kind, index, cols, arrays):
    counts=[len(arrays[k]) for k,_ in cols]
    if not counts or not counts[0]:return None
    if len(set(counts))!=1:
        raise ValueError(f"{kind} #{index}: columns have different lengths {counts}; refusing to misalign")
    for key,_ in cols:
        if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in arrays[key]):
            raise ValueError(f"{kind} #{index}: invalid numeric values in {key}")
    return {
        'name':f'{kind} {index}',
        'kind':kind,
        'columns':[{'key':key,'label':label} for key,label in cols],
        'values':[[arrays[k][i] for k,_ in cols] for i in range(counts[0])],
        'point_count':counts[0],
        'default_x': ('potential_v' if kind == 'CV' else 'z_real_ohm'),
        'default_y': ('current_a' if kind == 'CV' else 'neg_z_imag_ohm'),
    }


def read_nox(file_path):
    """Return a JSON-serialisable dict containing metadata and populated measurements.

    CV: FHCyclicVoltammetry2 arrays; EIS: plot signals (Nyquist/Bode).
    Procedure-only .nox files legitimately have zero recorded datasets.
    """
    path=Path(file_path)
    streams=all_streams(path)
    if not streams:
        raise NrbfError('Empty file')
    root,reader=streams[-1]
    if not isinstance(root,dict) or 'ProcedureDescription' not in root.get('__class__',''):
        raise NrbfError('NRBF data, but not a recognised NOVA ProcedureDescription')
    info={
        'file':path.name,
        'procedure':_r(root.get('_text'),reader) or _r(root.get('_name'),reader) or '',
        'instrument':_r(root.get('_instrument'),reader) or '',
        'remarks':_list(root.get('_remarks'),reader),
        'stream_count':len(streams),
        'file_size_bytes':path.stat().st_size,
    }
    objects=list(reader.objects.values())
    datasets=[]
    cv_number=0
    for command in objects:
        if not isinstance(command,dict) or command.get('__class__')!='EcoChemie.Autolab.FunctionHandlers.FHCyclicVoltammetry2':
            continue
        param = _parameters(command,reader)
        pairs={
            'potential_v':'SetpointApplied',
            'time_s':'CalcTime',
            'current_a':'EI_0.CalcCurrent',
            'we_potential_v':'EI_0.CalcPotential',
            'scan':'ScanNumber',
            'index':'Index',
            'q_plus_c':'QPlus',
            'q_minus_c':'QMin',
        }
        if not isinstance(param.get('SetpointApplied'),list) or not param['SetpointApplied']:
            continue
        cv_number+=1
        arrays={key: param.get(name,[]) for key,name in pairs.items()}
        ds=_dataset('CV',cv_number,CV_COLS,arrays)
        if ds: datasets.append(ds)

    # The SignalSetCommand's plotted X/Y/Z columns include the complete EIS
    # spectrum and preserve the frequency order measured in NOVA.
    groups={}
    for command in objects:
        if not isinstance(command,dict) or command.get('__class__')!='EcoChemie.Shared.SignalSetCommand':
            continue
        name=_r(command.get('CommandBase+_name'),reader)
        if name not in ('PlotsNyquist','PlotsBodeModulus'):
            continue
        axes=_parameters(command,reader)
        if not all(isinstance(axes.get(k),list) and axes[k] for k in ('X','Y','Z')):
            continue
        parent=_r(command.get('ExecCommandBase+_parent'),reader)
        group=groups.setdefault(id(parent), {})
        group[name]=axes
    eis_num=0
    for group in groups.values():
        ny=group.get('PlotsNyquist')
        if not ny:continue
        n=len(ny['X'])
        if len(ny['Y'])!=n or len(ny['Z'])!=n:
            continue
        bode=group.get('PlotsBodeModulus')
        if (bode and len(bode['X'])==n and len(bode['Y'])==n and len(bode['Z'])==n
                and all(math.isclose(f,g,rel_tol=1e-7,abs_tol=1e-9)
                        for f,g in zip(ny['Z'],bode['X']))):
            modulus=bode['Y']; minus_phase=bode['Z']
        else:
            # Derive values only if the stored Bode data isn't available.
            modulus=[math.hypot(x,y) for x,y in zip(ny['X'],ny['Y'])]
            minus_phase=[math.degrees(math.atan2(y,x)) for x,y in zip(ny['X'],ny['Y'])]
        arrays={
            'frequency_hz':ny['Z'],
            'z_real_ohm':ny['X'],
            'neg_z_imag_ohm':ny['Y'],
            'z_mod_ohm':modulus,
            'neg_phase_deg':minus_phase,
        }
        eis_num+=1
        ds=_dataset('EIS',eis_num,EIS_COLS,arrays)
        if ds:datasets.append(ds)
    new_datasets, technique_warnings=extract_nox_techniques(objects,reader,_r,_parameters)
    datasets.extend(new_datasets)
    plot_datasets, plot_warnings = recover_level_plots(objects, reader, _r, _parameters)
    datasets.extend(plot_datasets)
    return {'metadata':info, 'datasets':datasets, 'warnings':technique_warnings+plot_warnings}


def export_csv(dataset, filename):
    """Export one dataset as UTF-8 CSV with full-precision numeric readings."""
    with open(filename,'w',newline='',encoding='utf-8-sig') as f:
        writer=csv.writer(f)
        writer.writerow([c['label'] for c in dataset['columns']])
        writer.writerows(dataset['values'])


def main():
    p=argparse.ArgumentParser(description='Open Metrohm Autolab NOVA .nox measurement data.')
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--json',action='store_true',help='Print decoded data as JSON on stdout (for C++ Qt viewer)')
    mode.add_argument('--summary',action='store_true',help='Show datasets and measurement count')
    mode.add_argument('--csv-dir',metavar='DIR',help='Export each dataset to a CSV in this folder')
    p.add_argument('file',help='.nox file to read')
    args=p.parse_args()
    try:
        doc=read_nox(args.file)
        if args.json:
            print(json.dumps(doc,ensure_ascii=False,allow_nan=False,separators=(',',':')))
        elif args.summary:
            meta=doc['metadata']
            print('File:',meta['file'])
            print('Procedure:',meta['procedure'])
            print('Instrument:',meta['instrument'])
            print('Datasets:',len(doc['datasets']))
            for ds in doc['datasets']:
                print('  -',ds['name'],':',ds['point_count'],'points')
        else:
            folder=Path(args.csv_dir)
            folder.mkdir(parents=True,exist_ok=True)
            for ds in doc['datasets']:
                filename=folder / f"{Path(args.file).stem}_{ds['name'].replace(' ','_')}.csv"
                export_csv(ds,filename)
                print(filename)
            if not doc['datasets']:
                print('No populated CV/EIS measurements; the .nox may be a procedure template.')
    except (OSError,NrbfError,ValueError,KeyError,TypeError) as e:
        p.exit(1,f'ERROR: {e}\n')


if __name__=='__main__':main()
