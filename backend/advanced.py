"""Advanced, read-only electrochemical analysis for Pytro-NOVA 2.

Scientific calculations use NumPy and SciPy. Baseline algorithms, peak models,
CV comparisons and equivalent circuit fits are *estimates*, not validated
interpretations of a physical electrochemical system.

Protocol: python advanced.py {cv,compare,eis} INPUT.nox [options]
Prints one JSON response on stdout; clear error on stderr (exit status 2).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

from nox_reader import read_nox
from analysis import analyze_cv, _sweep_segments


def dependencies():
    try:
        import numpy as np
        from scipy.optimize import least_squares
        from scipy.signal import find_peaks
        from scipy.sparse import diags
        from scipy.sparse.linalg import spsolve
    except ImportError as exc:
        raise ValueError("Advanced analysis needs NumPy and SciPy. Run: py -3 -m pip install numpy scipy") from exc
    return np, least_squares, find_peaks, diags, spsolve


def series(ds, key, np):
    keys = [c['key'] for c in ds['columns']]
    if key not in keys:
        raise ValueError(f"Missing {key} in dataset {ds['name']}")
    values = np.asarray([r[keys.index(key)] for r in ds['values']], dtype=float)
    if values.size < 6 or not np.all(np.isfinite(values)):
        raise ValueError(f"Not enough finite samples in {key}")
    return values


def finite(value):
    if isinstance(value, (float, int)):
        return float(value) if math.isfinite(float(value)) else None
    return value


def baseline_asls(y, lam, p, np, diags, spsolve, max_iter=20):
    """Eilers asymmetric least-squares baseline for *positive* features.

    The method returns the lower envelope of its input; it is applied again to
    inverted current for cathodic features. It assumes a smooth baseline and
    positive-only features in the chosen polarity.
    """
    n = len(y)
    from scipy.sparse import eye
    from scipy.sparse import diags as scipy_diags
    from scipy.sparse import csc_matrix
    # D z is a second finite difference, implemented without a dense NxN matrix.
    d = scipy_diags([np.ones(n-2), -2*np.ones(n-2), np.ones(n-2)], [0,1,2], shape=(n-2,n), format='csc')
    penalty = lam * (d.T @ d)
    weights = np.ones(n)
    base = np.asarray(y)
    for _ in range(max_iter):
        w = scipy_diags(weights, 0, format='csc')
        base_new = np.asarray(spsolve(w + penalty, weights * y), dtype=float)
        new_weights = np.where(y > base_new, p, 1-p)
        if np.allclose(base, base_new, atol=1e-10, rtol=1e-8) and np.array_equal(weights, new_weights):
            base = base_new
            break
        base, weights = base_new, new_weights
    return base


def baseline_linear(y, np):
    # Endpoints averaged over up to 5 samples to reduce single-sample noise.
    n = len(y)
    k = max(1, min(5, n // 8))
    return np.linspace(float(np.median(y[:k])), float(np.median(y[-k:])), n)


def component(x, amplitude, center, width, shape, np):
    z = (x-center)/width
    if shape == 'gaussian':
        return amplitude * np.exp(-0.5*z*z)
    return amplitude / (1 + z*z)


def fit_branch(x, y, sweep, polarity, shape, max_components, baseline_method, lam, asymmetry,
               np, least_squares, find_peaks, diags, spsolve):
    """Fit peaks on one monotonic sweep, using polarity-specific baseline."""
    sign = 1 if polarity == 'Oxidation' else -1
    yp = sign * y
    baseline = (baseline_asls(yp, lam, asymmetry, np, diags, spsolve)
                if baseline_method == 'asls' else baseline_linear(yp, np))
    residual = yp - baseline
    # Positive peaks only; negative excursions are not fitted as this polarity.
    positive = np.maximum(residual, 0)
    scale = float(np.max(positive))
    if scale <= 1e-8:  # input in microamperes
        return [], sign*baseline, sign*baseline, float(np.sqrt(np.mean(residual**2)))
    smooth = np.convolve(positive, np.ones(5)/5, mode='same') if len(x)>9 else positive
    minimum_distance = max(3, len(x)//25)
    candidates, props = find_peaks(smooth, prominence=0.14*scale, distance=minimum_distance)
    if len(candidates) == 0:
        return [], sign*baseline, sign*baseline, float(np.sqrt(np.mean(residual**2)))
    selected = sorted(candidates, key=lambda i: positive[i], reverse=True)[:max_components]
    selected.sort(key=lambda i: x[i])
    span = float(max(x)-min(x))
    step = float(np.median(np.abs(np.diff(x))))
    width0 = max(span / (6*len(selected)), 1.5*step)
    width_min = max(step * 0.35, span / 3000)
    width_max = max(span, width_min*2)
    x0=[]; lower=[]; upper=[]
    for i in selected:
        x0.extend([float(positive[i]),float(x[i]),width0])
        lower.extend([0.0,float(min(x)),width_min])
        upper.extend([max(scale*5,1e-5),float(max(x)),width_max])

    def predict(v):
        answer=np.zeros_like(x)
        for j in range(len(selected)):
            answer += component(x,*v[3*j:3*j+3],shape,np)
        return answer
    result=least_squares(lambda v: predict(v)-positive, x0, bounds=(lower,upper),
                         max_nfev=3500,loss='soft_l1',f_scale=max(scale*.08,1e-7))
    fitted=predict(result.x)
    peaks=[]
    for j in range(len(selected)):
        amp,center,width = map(float,result.x[3*j:3*j+3])
        fwhm=width*(2*math.sqrt(2*math.log(2)) if shape=='gaussian' else 2)
        area=amp*width*(math.sqrt(2*math.pi) if shape=='gaussian' else math.pi)
        peaks.append({'sweep':sweep,'type':polarity,'center_v':center,
                      'amplitude_ua':sign*amp,'fwhm_mv':fwhm*1000,
                      'area_ua_v':sign*area,'shape':shape,
                      'status':'fit' if result.success else 'iteration limit'})
    error=float(np.sqrt(np.mean((positive-fitted)**2)))
    return peaks,sign*baseline,sign*(baseline+fitted),error


def advanced_cv(ds, *, baseline='asls', shape='gaussian', components=2,
                lam=1e5, asymmetry=.02):
    np, least_squares, find_peaks, diags, spsolve = dependencies()
    if baseline not in ('asls','linear') or shape not in ('gaussian','lorentzian'):
        raise ValueError('Unknown baseline method or peak shape')
    if not (1<=components<=6 and 100<=lam<=1e9 and 0.001<=asymmetry<=0.3):
        raise ValueError('Components: 1–6; lambda: 100–1e9; asymmetry: 0.001–0.3')
    if ds['kind']!='CV': raise ValueError('Choose a CV dataset')
    x=series(ds,'potential_v',np)
    y=series(ds,'current_a',np)*1e6  # internal current in µA
    sections=_sweep_segments(x.tolist())
    comp=[]; plot_series=[{'label':'Measured','x':x.tolist(),'y':y.tolist()}]
    errors=[]
    for branch,(a,b) in enumerate(sections,1):
        subx=x[a:b+1]; suby=y[a:b+1]
        # x is monotonic per sweep, but sort is necessary for fit initialization.
        order=np.argsort(subx)
        xx=subx[order]; yy=suby[order]
        if len(xx)<9 or xx[-1]-xx[0]<1e-9: continue
        sweep='Anodic' if subx[-1]>subx[0] else 'Cathodic'
        for polarity in ('Oxidation','Reduction'):
            peaks, base, fitted, err=fit_branch(xx,yy,sweep+f' {branch}',polarity,shape,components,
                  baseline,lam,asymmetry,np,least_squares,find_peaks,diags,spsolve)
            if peaks:
                comp.extend(peaks)
                plot_series.append({'label':f'{sweep} {branch} {polarity} fit','x':xx.tolist(),'y':fitted.tolist()})
                plot_series.append({'label':f'{sweep} {branch} {polarity} baseline','x':xx.tolist(),'y':base.tolist(), 'dashed':True})
                errors.append(err)
    comp.sort(key=lambda r:(r['sweep'],r['center_v']))
    rows=[]
    for i,item in enumerate(comp,1):
        rows.append({'id':i,**item})
    return {'mode':'cv','dataset':ds['name'],
            'settings':{'baseline':baseline,'shape':shape,'max_components_per_branch_and_polarity':components,
                        'asls_lambda':lam,'asls_asymmetry':asymmetry},
            'columns':['id','sweep','type','center_v','amplitude_ua','fwhm_mv','area_ua_v','shape','status'],
            'rows':rows,
            'summary':[{'name':'Resolved fitted components','value':len(rows),'unit':'count'},
                       {'name':'Sweep segments','value':len(sections),'unit':'count'},
                       {'name':'Mean component-fit RMS','value':finite(float(np.mean(errors))) if errors else None,'unit':'µA'}],
            'plot':{'x_label':'Applied potential (V)','y_label':'Current (µA)','title':ds['name']+' — baseline & deconvolution',
                    'series':plot_series},
            'warnings':['Baseline is estimated separately for positive and negative features per sweep.',
                        'Gaussian/Lorentzian fitting is phenomenological: broad/overlapping CV peaks may not obey these profiles.',
                        'Component area has units µA·V, not charge; conversion to coulombs requires scan-rate assumptions.',
                        'Always inspect fits, residuals and scan direction before interpreting peak chemistry.']}


def compare_cv(datasets, *, align='none'):
    np, *_ = dependencies()
    if len(datasets)<2: raise ValueError('Multi-CV comparison needs at least two CV datasets')
    if align not in ('none','oxidation'): raise ValueError('Unknown alignment option')
    cv=[d for d in datasets if d['kind']=='CV']
    if len(cv)<2: raise ValueError('Multi-CV comparison requires at least two CV datasets')
    peaks=[]
    for ds in cv:
        run=analyze_cv(ds,window=9)
        anodic=[p for p in run['peaks'] if p['type']=='Oxidation' and p['current_a']>0]
        cathodic=[p for p in run['peaks'] if p['type']=='Reduction' and p['current_a']<0]
        peaks.append((max(anodic,key=lambda p:p['prominence_a']) if anodic else None,
                      max(cathodic,key=lambda p:p['prominence_a']) if cathodic else None))
    ep0=peaks[0][0]['potential_v'] if peaks[0][0] else None
    rows=[]; plots=[]; traces=[]
    base_x=series(cv[0],'potential_v',np)
    base_y=series(cv[0],'current_a',np)*1e6
    for j,ds in enumerate(cv):
        x=series(ds,'potential_v',np)
        y=series(ds,'current_a',np)*1e6
        ep=peaks[j][0]['potential_v'] if peaks[j][0] else None
        ec=peaks[j][1]['potential_v'] if peaks[j][1] else None
        shift=(ep-ep0) if align=='oxidation' and ep is not None and ep0 is not None else 0.0
        xs=x-shift
        plots.append({'label':ds['name'],'x':xs.tolist(),'y':y.tolist()})
        # Compare corresponding monotonic branches independently, on a common
        # potential overlap grid (never compare a forward and reverse scan as one function).
        diffs=[]
        ba=_sweep_segments(base_x.tolist())
        sa=_sweep_segments(xs.tolist())
        for (a,b),(c,d) in zip(ba,sa):
            if (base_x[b]-base_x[a])*(xs[d]-xs[c])<0: continue
            xb,yb=base_x[a:b+1],base_y[a:b+1]
            xd,yd=xs[c:d+1],y[c:d+1]
            ib=np.argsort(xb); ic=np.argsort(xd)
            xx=xb[ib]; xy=yb[ib]; xx2=xd[ic]; yy2=yd[ic]
            if len(xx)<3 or len(xx2)<3: continue
            lo=max(float(xx[0]),float(xx2[0]));hi=min(float(xx[-1]),float(xx2[-1]))
            if hi<=lo: continue
            grid=np.linspace(lo,hi,120)
            diffs.extend((np.interp(grid,xx,xy)-np.interp(grid,xx2,yy2)).tolist())
        rmse=float(np.sqrt(np.mean(np.square(diffs)))) if diffs else None
        rows.append({'dataset':ds['name'],'samples':int(len(x)),
                    'anodic_peak_v':ep,'cathodic_peak_v':ec,
                    'peak_shift_mv':(ep-ep0)*1e3 if ep is not None and ep0 is not None else None,
                    'alignment_mv':shift*1e3,'max_current_ua':float(np.max(y)),
                    'min_current_ua':float(np.min(y)),
                    'branch_rmse_ua':rmse})
    return {'mode':'compare','dataset':', '.join(ds['name'] for ds in cv),
            'settings':{'alignment':align,'reference':cv[0]['name']},
            'columns':['dataset','samples','anodic_peak_v','cathodic_peak_v','peak_shift_mv','alignment_mv','max_current_ua','min_current_ua','branch_rmse_ua'],
            'rows':rows,
            'summary':[{'name':'Compared CV traces','value':len(rows),'unit':'count'},
                       {'name':'Reference','value':cv[0]['name'],'unit':''}],
            'plot':{'title':'CV overlay — '+align+' alignment','x_label':'Applied potential (V)','y_label':'Current (µA)','series':plots},
            'warnings':['Peak positions use uncorrected v1.1 CV detection and are descriptive.',
                        'Branch RMS is computed on overlapping interpolated potential domains, split by scan direction.',
                        'Peak alignment may obscure real electrochemical potential shifts; compare both aligned and unaligned traces.']}


def eis_impedance(freq, parameters, circuit, np):
    """Rs + (Rct || Cdl or Q(jω)^α) [+ σ(1-j)/√ω]."""
    omega=2*np.pi*freq
    rs,rct=parameters[:2]
    if circuit=='randles_rc':
        capacitance=parameters[2]
        parallel=1/(1/rct + 1j*omega*capacitance)
        return rs+parallel
    q,alpha=parameters[2:4]
    parallel=1/(1/rct + q*(1j*omega)**alpha)
    if circuit=='randles_cpe_warburg':
        sigma=parameters[4]
        return rs + parallel + sigma*(1-1j)/np.sqrt(omega)
    return rs+parallel


def advanced_eis(ds, *, circuit='randles_cpe', weighting='modulus'):
    np, least_squares, *_ = dependencies()
    if ds['kind']!='EIS': raise ValueError('Choose an EIS dataset')
    if circuit not in ('randles_rc','randles_cpe','randles_cpe_warburg'):
        raise ValueError('Circuit must be randles_rc, randles_cpe or randles_cpe_warburg')
    if weighting not in ('modulus','uniform'): raise ValueError('Unknown residual weighting')
    f=series(ds,'frequency_hz',np)
    zr=series(ds,'z_real_ohm',np)
    minuszi=series(ds,'neg_z_imag_ohm',np)
    if np.any(f<=0): raise ValueError('EIS frequencies must be positive for equivalent-circuit fitting')
    measured=zr-1j*minuszi
    maxz=float(max(np.max(np.abs(measured)),1e-6))
    realspan=max(float(np.ptp(zr)),float(np.median(np.abs(zr)))*.1,1e-3)
    rs0=max(1e-8,float(np.min(zr)))
    rct0=max(realspan,1e-4)
    peak_f=float(f[np.argmax(minuszi)])
    c0=np.clip(1/(2*math.pi*max(peak_f,1e-6)*rct0),1e-12,1e3)
    names=['Rs','Rct'];units=['Ω','Ω']
    if circuit=='randles_rc':
        p0=[rs0,rct0,c0];lower=[0,1e-9,1e-12];upper=[maxz*20,maxz*1e4,1e3]
        names+=['Cdl'];units+=['F']
    else:
        q0=c0*max(2*math.pi*peak_f,1)**(.12)
        p0=[rs0,rct0,float(np.clip(q0,1e-12,1e3)),.88]
        lower=[0,1e-9,1e-12,.3];upper=[maxz*20,maxz*1e4,1e3,1.0]
        names+=['Q','α'];units+=['S·s^α','dimensionless']
        if circuit=='randles_cpe_warburg':
            p0+=[maxz*.02*math.sqrt(2*math.pi*float(np.median(f)))]; lower+=[0];upper+=[maxz*1e4]
            names+=['σ'];units+=['Ω·s^-1/2']
    weight=1/np.maximum(np.abs(measured), maxz*1e-6) if weighting=='modulus' else np.ones(len(f))
    def resid(p):
        delta=(eis_impedance(f,p,circuit,np)-measured)*weight
        return np.r_[delta.real,delta.imag]
    result=least_squares(resid,p0,bounds=(lower,upper),max_nfev=6000,
                         x_scale='jac',ftol=1e-11,xtol=1e-11,gtol=1e-11)
    fit=eis_impedance(f,result.x,circuit,np)
    difference=fit-measured
    rmse=float(np.sqrt(np.mean(np.abs(difference)**2)))
    relative_raw_percent=100.0*rmse/max(float(np.sqrt(np.mean(np.abs(measured)**2))), 1e-12)
    wrmse=float(np.sqrt(np.mean(np.abs(difference*weight)**2)))
    # Report fit parameters but do not imply quantitative confidence intervals.
    rows=[{'parameter':name,'value':float(val),'unit':unit,
           'at_bound':bool(np.isclose(val,lo,rtol=1e-5,atol=1e-10) or np.isclose(val,hi,rtol=1e-5,atol=1e-10))}
          for name,val,unit,lo,hi in zip(names,result.x,units,lower,upper)]
    warnings=['Models are *candidate circuits*, not proofs of interfacial mechanism or uniqueness.',
              'All Z\' and -Z\'\' points fitted jointly; weighting is '+weighting+'.',
              'Fitted values may be non-identifiable over the available frequency range; inspect residuals and parameter bounds.',
              'No statistically valid parameter confidence intervals are available without replicate/noise information.']
    if relative_raw_percent > 10:
        warnings.insert(0, 'POOR FIT / MODEL MISMATCH: basic manual Randles models cannot describe many diffusion tails. Switch to EIS / AUTO CIRCUIT ENGINE (Afruz).')
    elif relative_raw_percent > 3:
        warnings.insert(0, 'Moderate fit quality. Consider the automatic Afruz-EIS model search and inspect residuals.')
    if any(r['at_bound'] for r in rows): warnings.insert(0,'At least one fitted parameter is on or near a bound; fit may be ill-conditioned.')
    if not result.success: warnings.insert(0,'Optimizer did not converge: '+result.message)
    return {'mode':'eis','dataset':ds['name'],
            'settings':{'circuit':circuit,'weighting':weighting,'success':bool(result.success),'solver_message':str(result.message)},
            'columns':['parameter','value','unit','at_bound'], 'rows':rows,
            'summary':[{'name':'RAW relative RMS','value':relative_raw_percent,'unit':'%'},
                       {'name':'Nyquist modulus RMSE','value':rmse,'unit':'Ω'},
                       {'name':'Weighted RMS','value':wrmse,'unit':'relative' if weighting=='modulus' else 'Ω'},
                       {'name':'Measurements','value':len(f),'unit':'frequencies'},
                       {'name':'Converged','value':bool(result.success),'unit':''}],
            'plot':{'title':'EIS Nyquist — '+circuit,'x_label':"Z' (Ω)",'y_label':"-Z'' (Ω)",
                    'series':[{'label':'Measured','x':zr.tolist(),'y':minuszi.tolist()},
                              {'label':'Circuit fit','x':fit.real.tolist(),'y':(-fit.imag).tolist()}]},
            'residual_plot':{'title':'Complex residuals by frequency', 'x_label':'log10 Frequency (Hz)', 'y_label':'Residual (Ω)',
                    'series':[{'label':'Z\' residual','x':np.log10(f).tolist(),'y':difference.real.tolist()},
                              {'label':'-Z\'\' residual','x':np.log10(f).tolist(),'y':(-difference.imag).tolist()}]},
            'warnings':warnings}


def run(argv=None):
    p=argparse.ArgumentParser(description='Pytro-NOVA advanced analysis backend')
    p.add_argument('mode',choices=['cv','compare','eis'])
    p.add_argument('input',help='NOVA .nox path')
    p.add_argument('--dataset',action='append',default=[],help='Exact dataset name; repeat for CV comparison')
    p.add_argument('--baseline',choices=['asls','linear'],default='asls')
    p.add_argument('--shape',choices=['gaussian','lorentzian'],default='gaussian')
    p.add_argument('--components',type=int,default=2)
    p.add_argument('--lambda-asls',type=float,default=1e5)
    p.add_argument('--asymmetry',type=float,default=.02)
    p.add_argument('--align',choices=['none','oxidation'],default='none')
    p.add_argument('--circuit',choices=['randles_rc','randles_cpe','randles_cpe_warburg','auto'],default='randles_cpe')
    p.add_argument('--search-depth',choices=['fast','deep','exhaustive'],default='exhaustive')
    p.add_argument('--precision',choices=['quick','balanced','afr_original'],default='afr_original',
                   help='Optimizer effort: original Afruz uses 8 multistarts, 8000 evaluations and hybrid search')
    p.add_argument('--smoothing',choices=['off','auto','light','strong'],default='off')
    p.add_argument('--fit-smoothed',action='store_true',help='Fit smoothed EIS instead of original (off by default)')
    p.add_argument('--weighting',choices=['modulus','uniform','proportional'],default='modulus')
    p.add_argument('--csv',help='Optional save results table as CSV')
    p.add_argument('--json-file',help='Optional save full result as JSON')
    args=p.parse_args(argv)
    doc=read_nox(args.input)
    datasets=doc['datasets']
    if args.dataset:
        missing=[name for name in args.dataset if not any(ds['name']==name for ds in datasets)]
        if missing: raise ValueError('Unknown dataset(s): '+', '.join(missing))
        chosen=[next(ds for ds in datasets if ds['name']==name) for name in args.dataset]
    else:
        chosen=[ds for ds in datasets if ds['kind']==('EIS' if args.mode=='eis' else 'CV')]
    if not chosen: raise ValueError('No suitable dataset found')
    if args.mode=='cv':
        result=advanced_cv(chosen[0],baseline=args.baseline,shape=args.shape,
                           components=args.components,lam=args.lambda_asls,asymmetry=args.asymmetry)
    elif args.mode=='compare':
        if len(set(ds['name'] for ds in chosen)) != len(chosen):
            raise ValueError('Comparison dataset names must be unique')
        result=compare_cv(chosen,align=args.align)
    else:
        if args.circuit=='auto':
            from auto_eis import analyze_auto_eis
            result=analyze_auto_eis(chosen[0],search_depth=args.search_depth,smoothing=args.smoothing,
                                    weighting='unit' if args.weighting=='uniform' else args.weighting,
                                    fit_smoothed=args.fit_smoothed,precision=args.precision)
        else:
            if args.weighting == 'proportional':
                raise ValueError('Proportional weighting is available for the Afruz auto engine, not the legacy manual fitter.')
            result=advanced_eis(chosen[0],circuit=args.circuit,weighting=args.weighting)
    if args.csv:
        with open(args.csv,'w',newline='',encoding='utf-8-sig') as stream:
            writer=csv.writer(stream);writer.writerow(result['columns'])
            for row in result['rows']:
                writer.writerow([row.get(key,'') for key in result['columns']])
    if args.json_file:
        Path(args.json_file).write_text(json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
    return result


def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr,'reconfigure'):sys.stderr.reconfigure(encoding='utf-8')
    try:
        print(json.dumps(run(),ensure_ascii=False,allow_nan=False,separators=(',',':')))
    except (OSError, ValueError, KeyError, TypeError, FloatingPointError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr)
        sys.exit(2)


if __name__=='__main__': main()
