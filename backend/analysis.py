"""Numerical analysis for NOVA CV and EIS datasets.

Pure standard-library Python. Read-only; no instrument control. All metrics are
estimates from sampled signals. Peak detection uses a short Savitzky–Golay
smoother followed by SciPy-style local prominence on each sweep branch.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path
from statistics import median


def _series(ds, key):
    cols = [c['key'] for c in ds['columns']]
    if key not in cols:
        raise ValueError(f"Missing {key} in {ds['name']}")
    i = cols.index(key)
    return [float(row[i]) for row in ds['values']]


def _metric(key, label, value, unit, description=''):
    if value is None or not math.isfinite(value):
        return None
    return {'key': key, 'label': label, 'value': float(value), 'unit': unit, 'description': description}


def _savgol(values, window):
    """Cubic Savitzky–Golay smoothing with mirrored border points.

    Fits a degree-3 polynomial to equally spaced samples using a tiny normal
    equation solve, once for all points. Values are *not* baseline-corrected.
    """
    n = len(values)
    if n < 7:
        return list(values)
    window = max(5, min(int(window) | 1, n if n % 2 else n-1))
    if window < 5:
        return list(values)
    half = window//2
    degree=3
    x = list(range(-half, half+1))
    matrix = [[sum(float(v)**(r+c) for v in x) for c in range(degree+1)]
              for r in range(degree+1)]
    # Solve A z = e0; resulting symmetric coefficients weight each sample.
    a = [row[:] + [1.0 if i==0 else 0.0] for i,row in enumerate(matrix)]
    for i in range(degree+1):
        pivot=max(range(i, degree+1), key=lambda j:abs(a[j][i]))
        a[i],a[pivot]=a[pivot],a[i]
        denominator=a[i][i]
        for k in range(i,degree+2): a[i][k]/=denominator
        for j in range(degree+1):
            if j==i: continue
            factor=a[j][i]
            for k in range(i,degree+2): a[j][k]-=factor*a[i][k]
    z=[a[i][-1] for i in range(degree+1)]
    weights=[sum(z[r]*(float(v)**r) for r in range(degree+1)) for v in x]
    smoothed=[]
    for center in range(n):
        acc=0.0
        for shift,weight in zip(x,weights):
            idx=center+shift
            if idx<0: idx=-idx
            if idx>=n: idx=2*n-2-idx
            idx=max(0,min(n-1,idx))
            acc+=values[idx]*weight
        smoothed.append(acc)
    return smoothed


def _sweep_segments(voltage, min_length=9):
    """Split scan at clear voltage-ramp reversals. Overlap turning point."""
    n=len(voltage)
    if n<2: return [(0,n-1)] if n else []
    directions=[]
    for i in range(1,n):
        delta=voltage[i]-voltage[i-1]
        directions.append((1 if delta>0 else -1) if delta else 0)
    nonzero=next((v for v in directions if v),1)
    directions=[v or nonzero for v in directions]
    for i in range(1,len(directions)):
        if directions[i]==0: directions[i]=directions[i-1]
    turns=[0]
    for i in range(1,len(directions)):
        if directions[i]!=directions[i-1] and i-turns[-1]>=min_length:
            turns.append(i)
    turns.append(n-1)
    segments=[]
    for a,b in zip(turns,turns[1:]):
        if b-a>=min_length-1:segments.append((a,b))
    return segments or [(0,n-1)]


def _peak_prominence(trace, k, sign, left, right):
    """Relative prominence limited by nearest more-extreme sampled neighbor."""
    height=sign*trace[k]
    low_left=height
    for j in range(k-1,left-1,-1):
        v=sign*trace[j]
        if v>height:break
        low_left=min(low_left,v)
    low_right=height
    for j in range(k+1,right+1):
        v=sign*trace[j]
        if v>height:break
        low_right=min(low_right,v)
    return max(0.,height-max(low_left,low_right))


def _peak_width(voltage, smooth, k, sign, prominence, left, right):
    """Approximate width at half prominence in volts; None if uncrossed."""
    level=sign*smooth[k]-prominence*0.5
    a=b=None
    for j in range(k-1,left-1,-1):
        if sign*smooth[j] <= level:
            v0=sign*smooth[j];v1=sign*smooth[j+1]
            f=(level-v0)/(v1-v0) if v1!=v0 else 0.0
            a=voltage[j]+f*(voltage[j+1]-voltage[j]);break
    for j in range(k+1,right+1):
        if sign*smooth[j] <= level:
            v0=sign*smooth[j-1];v1=sign*smooth[j]
            f=(level-v0)/(v1-v0) if v1!=v0 else 0.0
            b=voltage[j-1]+f*(voltage[j]-voltage[j-1]);break
    return abs(b-a) if a is not None and b is not None else None


def _cv_charge(time, current):
    qpos=qneg=0.0
    for i in range(1,len(time)):
        dt=time[i]-time[i-1]
        if dt<=0:continue
        a,b=current[i-1],current[i]
        if a>=0 and b>=0: qpos+=dt*(a+b)/2
        elif a<=0 and b<=0: qneg+=dt*(a+b)/2
        elif a*b<0:
            frac=abs(a)/(abs(a)+abs(b))
            qa=dt*frac*a/2
            qb=dt*(1-frac)*b/2
            if qa>0: qpos+=qa
            else: qneg+=qa
            if qb>0: qpos+=qb
            else: qneg+=qb
    return qpos,qneg


def analyze_cv(ds, *, window=9, prominence_ua=0.0, min_distance=6):
    if window<5 or window>51 or window%2==0:
        raise ValueError('Smoothing window must be an odd integer from 5 to 51')
    if prominence_ua<0 or not math.isfinite(prominence_ua):
        raise ValueError('Peak prominence must be a finite nonnegative number (µA)')
    if min_distance<1 or min_distance>10000:
        raise ValueError('Minimum peak distance must be 1–10000 data points')
    voltage=_series(ds,'potential_v')
    current=_series(ds,'current_a')
    time=_series(ds,'time_s')
    n=len(voltage)
    if n<3:
        return {'dataset':ds['name'],'kind':'CV','settings':{},'peaks':[],'metrics':[], 'warnings':['Too few samples for peak analysis.']}
    smooth=_savgol(current,window)
    segments=_sweep_segments(voltage)
    threshold=(prominence_ua*1e-6 if prominence_ua>0 else
               (max(smooth)-min(smooth))*0.07)
    peak_candidates=[]
    for branch,(left,right) in enumerate(segments, start=1):
        direction='Anodic sweep' if voltage[right]>=voltage[left] else 'Cathodic sweep'
        for sign,peak_type in [(1,'Oxidation'),(-1,'Reduction')]:
            for k in range(left+1,right):
                mid=sign*smooth[k]
                if mid<sign*smooth[k-1] or mid<=sign*smooth[k+1]:continue
                prominence=_peak_prominence(smooth,k,sign,left,right)
                if prominence < threshold or prominence<=0:continue
                peak_candidates.append({'index':k,'row':k+1,'branch':branch,'sweep':direction,
                                        'type':peak_type,'potential_v':voltage[k],
                                        'current_a':current[k], 'smoothed_current_a':smooth[k],
                                        'prominence_a':prominence,
                                        'width_half_height_v':_peak_width(voltage,smooth,k,sign,prominence,left,right)})
    # Enforce spacing separately for each branch + peak polarity (retain largest).
    retained=[]
    for peak in sorted(peak_candidates,key=lambda p:p['prominence_a'], reverse=True):
        if all(peak['branch']!=p['branch'] or peak['type']!=p['type'] or
               abs(peak['index']-p['index'])>=min_distance for p in retained):
            retained.append(peak)
    peaks=sorted(retained,key=lambda p:p['index'])
    for i,p in enumerate(peaks,1): p['id']=i

    qplus,qminus=_cv_charge(time,current)
    rates=[abs((voltage[i]-voltage[i-1])/(time[i]-time[i-1])) for i in range(1,n)
           if time[i]-time[i-1]>0 and abs(voltage[i]-voltage[i-1])>1e-8]
    metrics=[
        _metric('i_max','Maximum measured current',max(current)*1e6,'µA'),
        _metric('i_min','Minimum measured current',min(current)*1e6,'µA'),
        _metric('potential_span','Potential span',max(voltage)-min(voltage),'V'),
        _metric('scan_rate','Median absolute scan rate',median(rates) if rates else None,'V/s'),
        _metric('q_anodic','Integrated positive charge',qplus*1e3,'mC','Integrates positive current against elapsed time'),
        _metric('q_cathodic','Integrated negative charge',qminus*1e3,'mC','Signed integration of negative current against time'),
    ]
    anodic=[p for p in peaks if p['type']=='Oxidation' and p['current_a']>0]
    cathodic=[p for p in peaks if p['type']=='Reduction' and p['current_a']<0]
    if anodic and cathodic:
        pa=max(anodic,key=lambda x:x['prominence_a'])
        pc=max(cathodic,key=lambda x:x['prominence_a'])
        metrics.extend([
            _metric('e_pa','Oxidation peak potential',pa['potential_v'],'V'),
            _metric('e_pc','Reduction peak potential',pc['potential_v'],'V'),
            _metric('delta_ep','Peak potential separation',abs(pa['potential_v']-pc['potential_v'])*1000,'mV'),
            _metric('i_ratio','Absolute peak-current ratio',abs(pa['current_a']/pc['current_a']) if pc['current_a'] else None,'ratio'),
        ])
    metrics=[m for m in metrics if m is not None]
    warnings=["Peak positions are computed from smoothed, uncorrected current; no capacitive baseline was subtracted.",
              "Charge is time-integrated measured current, not isolated faradaic peak charge.",
              "Verify all peak assignments with the original NOVA measurement before scientific reporting."]
    return {'dataset':ds['name'],'kind':'CV',
            'settings':{'window':window,'prominence_ua':prominence_ua,'effective_prominence_ua':threshold*1e6,
                        'min_distance':min_distance,'segments':len(segments)},
            'peaks':peaks,'metrics':metrics,'smoothed_current_a':smooth,'warnings':warnings}


def analyze_eis(ds):
    f=_series(ds,'frequency_hz');zr=_series(ds,'z_real_ohm');zi=_series(ds,'neg_z_imag_ohm')
    modulus=_series(ds,'z_mod_ohm');phase=_series(ds,'neg_phase_deg')
    if not f: return {'dataset':ds['name'],'kind':'EIS','peaks':[],'metrics':[], 'warnings':['No frequency points.']}
    at_high=max(range(len(f)),key=lambda i:f[i])
    at_low=min(range(len(f)),key=lambda i:f[i])
    at_peak=max(range(len(f)),key=lambda i:zi[i])
    rs=zr[at_high];r_low=zr[at_low]
    span=r_low-rs
    metrics=[
        _metric('high_freq','Highest measured frequency',f[at_high],'Hz'),
        _metric('low_freq','Lowest measured frequency',f[at_low],'Hz'),
        _metric('z_max','Maximum impedance modulus',max(modulus),'Ω'),
        _metric('rs_approx','High-frequency real impedance (Rs proxy)',rs,'Ω'),
        _metric('low_zreal','Low-frequency real impedance',r_low,'Ω'),
        _metric('rct_proxy','Real-impedance span (Rct proxy)',span,'Ω','Not a fitted charge-transfer resistance'),
        _metric('max_imag','Maximum -Im(Z)',zi[at_peak],'Ω'),
        _metric('f_max_imag','Frequency at max -Im(Z)',f[at_peak],'Hz'),
        _metric('tau_apparent','Apparent time constant',1/(2*math.pi*f[at_peak]) if f[at_peak]>0 else None,'s'),
        _metric('max_phase','Maximum recorded -phase',max(phase),'°'),
    ]
    return {'dataset':ds['name'],'kind':'EIS','settings':{},'peaks':[],
            'metrics':[m for m in metrics if m],
            'warnings':['Rs/Rct indicators use measured endpoint values, not circuit-model fitting.',
                        'The apparent time constant assumes a single dominant relaxation and should not be treated as a fitted parameter.']}


def analyze_dataset(ds, **kwargs):
    if ds['kind']=='CV': return analyze_cv(ds,**kwargs)
    if ds['kind']=='EIS': return analyze_eis(ds)
    raise ValueError('Analysis not available for this measurement type')


def export_peaks_csv(analysis, target):
    """Save detected CV peaks with full-precision numbers and sweep metadata."""
    keys=['id','type','branch','sweep','row','potential_v','current_a','smoothed_current_a','prominence_a','width_half_height_v']
    with open(target,'w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f)
        w.writerow(keys)
        for p in analysis['peaks']:
            w.writerow([p.get(k) for k in keys])


def analyze_time_technique(ds):
    """Physical-unit summaries; no capacitance claims without current/active mass."""
    kind=ds['kind']
    time=_series(ds,'time_s')
    ykey='current_a' if kind=='CA' else 'potential_v'
    y=_series(ds,ykey)
    if not time:
        return {'dataset':ds['name'],'kind':kind,'settings':{},'peaks':[],
                'metrics':[],'warnings':['Empty measurement.']}
    metrics=[_metric('duration','Elapsed duration',max(time)-min(time),'s'),
             _metric('minimum','Minimum '+ykey,min(y),'A' if kind=='CA' else 'V'),
             _metric('maximum','Maximum '+ykey,max(y),'A' if kind=='CA' else 'V')]
    warnings=['Values use instrument-provided time and signal columns; no smoothing or baseline subtraction.']
    if len(time)>1 and time[-1]>time[0]:
        metrics.append(_metric('avg_slope','End-to-end signal slope',(y[-1]-y[0])/(time[-1]-time[0]),
                               'A/s' if kind=='CA' else 'V/s'))
    if kind=='GCD':
        columns=[col['key'] for col in ds['columns']]
        if 'current_a' in columns:
            current=_series(ds,'current_a')
            positive=negative=0.
            for i in range(1,len(time)):
                dt=time[i]-time[i-1]
                if dt<=0:continue
                q=0.5*(current[i]+current[i-1])*dt
                if q>=0:positive+=q
                else:negative+=-q
            metrics.extend([_metric('q_charge','Integrated positive charge',positive,'C'),
                            _metric('q_discharge','Integrated negative charge',negative,'C')])
            if not any(v<0 for v in current) or not any(v>0 for v in current):
                warnings.append('Current does not reverse sign: do not infer separate charge/discharge capacities.')
        else:
            warnings.append('GCD capacitance/capacity not calculated: current trace is unavailable.')
        warnings.append('Mass-normalized capacitance and IR-drop correction require verified active mass and cycle boundaries.')
    if kind=='CA' and len(time)>1:
        positive=negative=0.
        for i in range(1,len(time)):
            dt=time[i]-time[i-1]
            if dt>0:
                area=0.5*(y[i]+y[i-1])*dt
                if area>0:positive+=area
                else:negative+=abs(area)
        metrics.extend([_metric('q_positive','Positive integrated charge',positive,'C'),
                        _metric('q_negative','Negative integrated charge',negative,'C')])
    return {'dataset':ds['name'],'kind':kind,'settings':{},'peaks':[],
            'metrics':[m for m in metrics if m], 'warnings':warnings}


def analyze_sweep_technique(ds, *, window=9, prominence_ua=0., min_distance=6):
    """Voltage-sweep peak search, without applying CV-cycle-specific metrics."""
    cols=[c['key'] for c in ds['columns']]
    if 'time_s' in cols:
        surrogate=ds
    else:
        surrogate={**ds, 'columns':ds['columns']+[{'key':'time_s','label':'Sample index (not time)'}],
                   'values':[row+[float(i)] for i,row in enumerate(ds['values'])]}
    out=analyze_cv(surrogate,window=window,prominence_ua=prominence_ua,min_distance=min_distance)
    out['kind']=ds['kind']
    out['metrics']=[_metric('points','Measured points',ds['point_count'],'points')]
    out['metrics']=[m for m in out['metrics'] if m]
    out['warnings']=['Peak detection operates on smoothed current for localization; reported peak current is the original measured value.',
                     'Baseline, pulse subtraction and technique-specific waveforms must be verified before interpreting peak heights.']
    return out


_previous_analyze_dataset = analyze_dataset

def analyze_dataset(ds, **kwargs):
    if ds['kind'] in ('LSV','DPV','SWV'):
        return analyze_sweep_technique(ds,**kwargs)
    if ds['kind'] in ('GCD','CA','CP','OCP'):
        return analyze_time_technique(ds)
    return _previous_analyze_dataset(ds,**kwargs)
