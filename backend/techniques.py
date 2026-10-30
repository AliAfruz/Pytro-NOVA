"""Explicit schemas for supported electrochemical measurement curves.

Important: non-CV/EIS NOX field names vary with NOVA procedure/version. We do
not guess unknown .NET objects are measurements; import CSV/TSV when unrecognized.
"""
from __future__ import annotations

import csv
import math
import re
from pathlib import Path

# Columns are SI, labels include units. One source signal maps to one column.
COLUMNS = {
    'potential_v': 'Potential (V)',
    'time_s': 'Time (s)',
    'current_a': 'Current (A)',
    'cycle': 'Cycle',
    'step': 'Step',
    'pulse_current_a': 'Differential current (A)',
    'forward_current_a': 'Forward current (A)',
    'reverse_current_a': 'Reverse current (A)',
    'charge_c': 'Charge (C)',
}

TECHNIQUES = {
    'GCD': {'required': ('time_s','potential_v'), 'optional': ('current_a','cycle','step','charge_c'), 'default': ('time_s','potential_v'), 'label':'Galvanostatic charge/discharge'},
    'LSV': {'required': ('potential_v','current_a'), 'optional': ('time_s','cycle'), 'default': ('potential_v','current_a'), 'label':'Linear sweep voltammetry'},
    'DPV': {'required': ('potential_v','current_a'), 'optional': ('pulse_current_a','time_s','cycle'), 'default': ('potential_v','current_a'), 'label':'Differential pulse voltammetry'},
    'SWV': {'required': ('potential_v','current_a'), 'optional': ('forward_current_a','reverse_current_a','time_s','cycle'), 'default': ('potential_v','current_a'), 'label':'Square-wave voltammetry'},
    'CA': {'required': ('time_s','current_a'), 'optional': ('potential_v','step'), 'default': ('time_s','current_a'), 'label':'Chronoamperometry'},
    'CP': {'required': ('time_s','potential_v'), 'optional': ('current_a','step'), 'default': ('time_s','potential_v'), 'label':'Chronopotentiometry'},
    'OCP': {'required': ('time_s','potential_v'), 'optional': (), 'default': ('time_s','potential_v'), 'label':'Open-circuit potential'},
}

# Exact/recognizable .NET function-handler class suffixes only. No guessing
# from procedure text (which may contain a command name without data).
HANDLER_WORDS = {
    'GCD': ('galvanostaticchargedischarge', 'galvanostaticcycling', 'chargeanddischarge'),
    'LSV': ('linearsweepvoltammetry', 'linearsweep'),
    'DPV': ('differentialpulsevoltammetry', 'differentialpulse'),
    'SWV': ('squarewavevoltammetry', 'squarewave'),
    'CA': ('chronoamperometry', 'chronoamperometric'),
    'CP': ('chronopotentiometry', 'chronopotentiometric'),
    'OCP': ('opencircuitpotential', 'opencircuit'),
}

# NOVA parameter keys observed in legacy CV files are first; remaining
# candidates are conservative aliases that require populated equal-length arrays.
PARAM_ALIASES = {
    'potential_v': ('EI_0.CalcPotential','SetpointApplied','CalcPotential','Potential','WE(1) potential','Ewe','Ewe/V','Voltage'),
    'time_s': ('CalcTime','Time','EI_0.CalcTime','ElapsedTime','time/s'),
    'current_a': ('EI_0.CalcCurrent','CalcCurrent','Current','WE(1) current','I','<I>'),
    'pulse_current_a': ('DifferentialCurrent','DifferentialCurrentCalculated','DeltaCurrent','PulseCurrent'),
    'forward_current_a': ('ForwardCurrent','IFwd'),
    'reverse_current_a': ('ReverseCurrent','IRev'),
    'cycle': ('CycleNumber','Cycle','ScanNumber'),
    'step': ('StepNumber','Step','Index'),
    'charge_c': ('Charge','CalcCharge','QPlus'),
}

# CSV input aliases deliberately require explicit units for ambiguous values.
CSV_ALIASES = {
    'potential_v': ('potential(v)','potential/v','voltage(v)','voltage/v','ewe/v','ewe(v)','appliedpotential(v)','we(1)potential(v)','v(v)'),
    'time_s': ('time(s)','time/s','elapsedtime(s)','elapsedtime/s','t(s)','t/s'),
    'current_a': ('current(a)','current/a','we(1)current(a)','i(a)','i/a','current(ma)','current/ma','current(ua)','current/ua','current(µa)','current(μa)'),
    'pulse_current_a': ('differentialcurrent(a)','differentialcurrent/ma','deltacurrent(a)','deltacurrent/ma'),
    'forward_current_a': ('forwardcurrent(a)','forwardcurrent(ma)'),
    'reverse_current_a': ('reversecurrent(a)','reversecurrent(ma)'),
    'cycle': ('cycle','cyclenumber','scan','scannumber'),
    'step': ('step','stepnumber'),
    'charge_c': ('charge(c)','charge/c'),
}

def _norm(s):
    return re.sub(r'\s+', '', str(s).strip().lower())


def make_dataset(kind, number, arrays, *, source='import', column_order=None):
    """Build a validated dataset without padding or interpolating missing values."""
    if kind not in TECHNIQUES:
        raise ValueError(f'Unsupported technique {kind}: choose {", ".join(TECHNIQUES)}')
    spec=TECHNIQUES[kind]
    for key in spec['required']:
        if key not in arrays or not arrays[key]:
            raise ValueError(f'{kind}: missing required signal {key}')
    n=len(arrays[spec['required'][0]])
    keys=column_order or [key for key in (*spec['required'],*spec['optional']) if key in arrays and len(arrays[key])==n]
    if not all(k in keys for k in spec['required']):
        raise ValueError(f'{kind}: required columns missing after filtering')
    for key in keys:
        if len(arrays[key]) != n:
            raise ValueError(f'{kind} {key}: length mismatch, refusing to align by position')
        if not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in arrays[key]):
            raise ValueError(f'{kind} {key}: nonfinite/non-numeric input')
    return {'name':f'{kind} {number}', 'kind':kind,
            'columns':[{'key':k,'label':COLUMNS[k]} for k in keys],
            'values':[[float(arrays[k][i]) for k in keys] for i in range(n)],
            'point_count':n, 'default_x':spec['default'][0], 'default_y':spec['default'][1],
            'source':source}


def read_technique_csv(path, kind):
    """Import a CSV/TSV technique with explicit SI units. No silent unit guesses."""
    path=Path(path)
    if kind not in TECHNIQUES:
        raise ValueError(f'Choose a technique: {", ".join(TECHNIQUES)}')
    with path.open('r', encoding='utf-8-sig',newline='') as f:
        sample=f.read(8192);f.seek(0)
        try: dialect=csv.Sniffer().sniff(sample,delimiters=',;\t')
        except csv.Error: dialect=csv.excel
        rows=csv.reader(f,dialect)
        try:header=next(rows)
        except StopIteration:raise ValueError('Empty CSV file')
        mapping={}
        for idx,h in enumerate(header):
            hn=_norm(h)
            for key,aliases in CSV_ALIASES.items():
                if hn in aliases and key not in mapping:
                    multiplier=1e-3 if 'ma)' in hn or '/ma' in hn else (1e-6 if 'ua)' in hn or '/ua' in hn or 'µa)' in hn or 'μa)' in hn else 1)
                    mapping[key]=(idx,multiplier)
        # For DPV, the differential/pulse signal is the ordinate when supplied.
        # Preserve this fact in metadata; do not silently call an unrelated
        # absolute-current column the differential current.
        if kind=='DPV' and 'pulse_current_a' in mapping:
            mapping['current_a']=mapping['pulse_current_a']
        needed=TECHNIQUES[kind]['required']
        missing=[key for key in needed if key not in mapping]
        if missing:raise ValueError(f'{kind}: CSV missing {missing}; use units in column headers, e.g. "Time (s)", "Potential (V)", "Current (A)"')
        arrays={k:[] for k in mapping}
        for lineno,row in enumerate(rows,2):
            if not row or all(not cell.strip() for cell in row):continue
            try:
                for key,(idx,scale) in mapping.items():
                    arrays[key].append(float(row[idx].strip())*scale)
            except (IndexError,ValueError) as exc:
                raise ValueError(f'Invalid numerical data at CSV row {lineno}: {exc}') from exc
    ds=make_dataset(kind,1,arrays,source='csv')
    if kind=='DPV' and 'pulse_current_a' in arrays:
        ds['signal_note']='DPV plot uses supplied differential-current channel.'
    return {'metadata':{'file':path.name,'procedure':f'Imported {TECHNIQUES[kind]["label"]} CSV',
                        'instrument':'CSV import (user-supplied)', 'source_format':'CSV/TSV'},
            'datasets':[ds], 'warnings':['Imported CSV, not parsed from Metrohm NOVA binary. Confirm units and signal attribution.']}


def extract_nox_techniques(objects, reader, deref_fn, parameter_fn):
    """Recognize populated technique-specific function handlers in NOVA NRBF.

    Heuristic mapping is provisional and requires real GCD/LSV/DPV/SWV files
    before it can be certified. Unknown record classes remain untouched.
    """
    output=[]
    counts={k:0 for k in TECHNIQUES}
    warnings=[]
    for command in objects:
        if not isinstance(command,dict):continue
        cls=str(command.get('__class__',''))
        if 'FunctionHandlers.' not in cls:continue
        name=cls.rsplit('.',1)[-1].lower()
        kind=next((k for k,words in HANDLER_WORDS.items() if any(w in name for w in words)),None)
        if kind is None:continue
        try: params=parameter_fn(command,reader)
        except (TypeError,ValueError,KeyError):continue
        arrays={}
        for key,alternates in PARAM_ALIASES.items():
            for alias in alternates:
                values=params.get(alias)
                if isinstance(values,list) and values and all(isinstance(v,(int,float)) for v in values):
                    arrays[key]=values
                    break
        # For pulse methods, 'current_a' may be the differential measured current.
        if kind in ('DPV','SWV') and 'current_a' not in arrays and 'pulse_current_a' in arrays:
            arrays['current_a']=arrays['pulse_current_a']
        counts[kind]+=1
        n=len(arrays.get(TECHNIQUES[kind]['required'][0],[]))
        arrays={k:v for k,v in arrays.items() if len(v)==n}
        try:
            ds=make_dataset(kind,counts[kind],arrays,source='nox-provisional')
            output.append(ds)
        except ValueError as exc:
            warnings.append(f'Could not decode {cls}: {exc}')
    return output,warnings
