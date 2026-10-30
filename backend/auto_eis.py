"""Pytro-NOVA v3: EIS model discovery built on the user-supplied Afruz-EIS fit engine.

Numerical model selection is diagnostic, not proof of a physical circuit.
By default all fits use ORIGINAL complex measurements; any Savitzky-Golay
smoothing is an auxiliary visual curve unless fit_smoothed=True is specified.
"""
from __future__ import annotations

import math
import numpy as np
from scipy.signal import savgol_filter

from afr_eis.models import CIRCUITS
from afr_eis.fitting import FitSettings, auto_fit

FAST_MODELS = (
    "R", "R-(R||C)", "R-(R||CPE)", "R-(R||CPE)-W",
    "R-(CPE||(R+W))", "R-(R||CPE)-Wo", "R-(R||CPE)-(R||CPE)",
)
DEEP_MODELS = FAST_MODELS + (
    "R-(R||CPE)-Ws", "R-(R||CPE)-Wf", "R-(R||CPE)-G",
    "R-L-(R||CPE)", "R-(R||CPE)-(R||CPE)-Wo",
    "R-TLMo", "R-(R||CPE)-TLMo", "R-(R||CPE)-TLMs",
)
EXHAUSTIVE_MODELS = tuple(CIRCUITS.keys())


def _n(v):
    """Make SciPy / NumPy results safe for JSON's allow_nan=False."""
    if isinstance(v, (float, int, np.number)):
        n = float(v)
        return n if math.isfinite(n) else None
    return v


def extract_spectrum(ds):
    columns = [c['key'] for c in ds['columns']]
    needed = ('frequency_hz', 'z_real_ohm', 'neg_z_imag_ohm')
    if ds.get('kind') != 'EIS' or any(k not in columns for k in needed):
        raise ValueError('Expected EIS frequency, Z-real and -Z-imag columns')
    raw = np.asarray(ds['values'], dtype=float)
    if raw.ndim != 2 or raw.shape[0] < 9:
        raise ValueError('Auto-fit requires at least 9 impedance measurements')
    frequency = raw[:, columns.index('frequency_hz')]
    real = raw[:, columns.index('z_real_ohm')]
    imag_negative = raw[:, columns.index('neg_z_imag_ohm')]
    mask = np.isfinite(frequency) & np.isfinite(real) & np.isfinite(imag_negative) & (frequency > 0)
    frequency, z = frequency[mask], (real[mask] - 1j*imag_negative[mask])
    if len(frequency) < 9:
        raise ValueError('At least 9 positive, finite-frequency EIS points are required')
    order = np.argsort(frequency)[::-1]
    frequency, z = frequency[order], z[order]
    if np.unique(frequency).size != len(frequency):
        raise ValueError('Duplicate EIS frequencies: remove or average replicate values before circuit fitting')
    return frequency, z


def smooth_eis(frequency, z, mode='auto'):
    """Savgol applied on UNIFORM log10(f) samples, interpolated back to data.

    Returns the original array when smoothing is unwarranted. Never silently
    modifies the measurements. Length is restricted to small conservative windows.
    """
    if mode == 'off':
        return z.copy(), 0, 'Smoothing off — raw impedance preserved'
    if mode not in ('auto', 'light', 'strong'):
        raise ValueError('Smoothing must be off, auto, light, or strong')
    n = len(frequency)
    if n < 9:
        return z.copy(), 0, 'Too few points for smoothing'
    f_up = frequency[::-1]
    z_up = z[::-1]
    x = np.log10(f_up)
    grid = np.linspace(x[0], x[-1], n)
    grid_real = np.interp(grid, x, z_up.real)
    grid_imag = np.interp(grid, x, z_up.imag)
    # The high-frequency signal can be quite flat; normalize both components
    # separately when making an auto-smoothing decision.
    span = max(float(np.ptp(z.real)), float(np.ptp(z.imag)), 1e-12)
    curvature = np.median(np.abs(np.diff(grid_real, n=2))) + np.median(np.abs(np.diff(grid_imag, n=2)))
    strength = float(curvature / span)
    if mode == 'auto':
        if strength < 0.0004:
            return z.copy(), 0, 'Auto: trace appears smooth — raw measurements shown'
        window = 5 if strength < 0.03 else 7
    else:
        window = 5 if mode == 'light' else 9
    if window > n:
        window = n if n % 2 else n - 1
    def filt(v):
        return savgol_filter(v, window_length=window, polyorder=2, mode='interp')
    zr, zi = filt(grid_real), filt(grid_imag)
    filtered = np.interp(x, grid, zr) + 1j * np.interp(x, grid, zi)
    return filtered[::-1], window, f'{mode.capitalize()}: Savitzky–Golay on log-frequency grid (window {window}, order 2)'


def analyze_auto_eis(ds, *, search_depth='fast', smoothing='auto', weighting='modulus', fit_smoothed=False, precision='balanced'):
    if search_depth not in ('fast', 'deep', 'exhaustive'):
        raise ValueError('Search depth must be fast, deep or exhaustive')
    if weighting not in ('unit', 'modulus', 'proportional'):
        raise ValueError('Weighting must be unit, modulus, or proportional')
    if precision not in ('quick', 'balanced', 'afr_original'):
        raise ValueError('Precision must be quick, balanced, or afr_original')
    f, z = extract_spectrum(ds)
    z_smooth, window, smoothing_note = smooth_eis(f, z, smoothing)
    target = z_smooth if fit_smoothed else z
    model_set = FAST_MODELS if search_depth == 'fast' else (DEEP_MODELS if search_depth == 'deep' else EXHAUSTIVE_MODELS)
    keys = [k for k in model_set if k in CIRCUITS]
    # The original Afruz-EIS app normally uses 8 starts, 8000 evaluations,
    # and a hybrid global/local search. Previous NOVA integration limited it to
    # 2–3 starts and 650–1100 evaluations; those are low-budget *quick* settings.
    # Do not silently downgrade scientific optimizer settings.
    budgets = {
        'quick': dict(max_nfev=900, multistart=2, optimizer='least_squares'),
        'balanced': dict(max_nfev=5000, multistart=5, optimizer='least_squares'),
        'afr_original': dict(max_nfev=8000, multistart=8, optimizer='hybrid'),
    }
    options = FitSettings(weighting=weighting, robust_loss='soft_l1', **budgets[precision])
    fits = auto_fit(f, target, model_keys=keys, settings=options)
    # Preserve original Afruz-EIS selection semantics: the first ranked candidate
    # is the displayed best fit, including when it did not formally converge.
    # In that case we issue an explicit warning below rather than silently
    # substituting a different circuit from further down the ranking.
    best = fits[0]
    best_model = CIRCUITS[best.model_key]
    fit_on_original = best_model.function(f, *[best.params[p.name] for p in best_model.params])
    res = fit_on_original - z
    rmse_original = math.sqrt(float(np.mean(np.abs(res)**2)))
    # Quality is evaluated against RAW data, even when a filtered preview is drawn.
    reference_scale = float(np.sqrt(np.mean(np.abs(z)**2)))
    relative_raw_percent = 100.0 * rmse_original / max(reference_scale, 1e-12)
    quality = 'poor' if relative_raw_percent > 10 else ('review' if relative_raw_percent > 3 else 'numerically close')

    rows = []
    for rank, result in enumerate(fits, 1):
        rows.append({
            'Rank': rank, 'Model': result.model_name, 'Key': result.model_key,
            'Parameters': len(CIRCUITS[result.model_key].params),
            'Converged': bool(result.success), 'RMSE (ohm)': _n(result.rmse),
            'Relative RMSE (%)': _n(result.relative_rmse_percent),
            'AICc': _n(result.aicc), 'BIC': _n(result.bic),
            'Score': _n(result.rank_score),
            'Warnings': ' | '.join(result.warnings),
        })
    parameters = []
    for defn in best_model.params:
        name = defn.name
        parameters.append({'Parameter':name, 'Value':_n(best.params.get(name)),
                           'Std. error':_n(best.stderr.get(name)),
                           'Unit':str(defn.unit),
                           'Note':'See fit diagnostics / model identifiability'})

    summary = [
        {'name':'Fit quality vs raw', 'value': quality, 'unit':''},
        {'name':'Relative RMS vs raw', 'value': _n(relative_raw_percent), 'unit':'%'},
        {'name':'Best circuit', 'value':best.model_name,'unit':''},
        {'name':'RMSE vs RAW', 'value':_n(rmse_original),'unit':'Ω'},
        {'name':'AICc', 'value':_n(best.aicc),'unit':''},
        {'name':'Candidates', 'value':len(fits),'unit':''},
    ]
    warnings = list(dict.fromkeys(str(w) for w in best.warnings))
    if quality == 'poor':
        warnings.insert(0, 'POOR FIT: the best tested circuit still misses the raw spectrum substantially. Try more models / different weighting; do not report fitted circuit parameters as validated.')
    elif quality == 'review':
        warnings.insert(0, 'MODERATE FIT: review Nyquist/Bode residuals and parameter identifiability.')
    if fit_smoothed:
        warnings.append('Fit target was smoothed: parameter values may be biased; compare to the raw-data fit.')
    else:
        warnings.append('Fits use original, unsmoothed impedance; smoothing changes only the display curve.')
    warnings.append('Automatic circuit ranking is not proof of a unique mechanism. Inspect model complexity, parameter errors and residuals.')
    if math.isfinite(best.max_abs_correlation) and best.max_abs_correlation >= 0.95:
        warnings.append('Severe parameter correlation: fitted component values may not be identifiable.')
    if math.isfinite(best.jacobian_condition) and best.jacobian_condition > 1e7:
        warnings.append('Ill-conditioned fit Jacobian: parameter uncertainties may be unreliable.')
    if not best.success:
        warnings.append('Best-ranked candidate did not meet the optimizer convergence criterion.')
    result = {
        'type':'eis_auto',
        'columns':['Rank','Model','Key','Parameters','Converged','RMSE (ohm)',
                   'Relative RMSE (%)','AICc','BIC','Score','Warnings'],
        'rows':rows,
        'parameters':parameters,
        'summary':summary,
        'warnings':warnings,
        'fit_quality':{'label':quality,'rmse_raw_ohm':_n(rmse_original),'relative_rms_raw_percent':_n(relative_raw_percent)},
        'optimizer':{'precision':precision,'max_nfev':options.max_nfev,'multistart':options.multistart,'optimizer':options.optimizer,'robust_loss':options.robust_loss},
        'smoothing':{'mode':smoothing,'window':window,'description':smoothing_note,
                     'fit_smoothed':bool(fit_smoothed)},
        'best_model':{'key':best.model_key,'name':best.model_name,
                      'expression':best_model.expression,
                      'description':best_model.description,
                      'converged':bool(best.success),'solver_message':best.message,
                      'max_abs_parameter_correlation':_n(best.max_abs_correlation),
                      'jacobian_condition':_n(best.jacobian_condition),
                      'relative_rmse_percent':_n(best.relative_rmse_percent)},
        'plot':{'title':'Automatic Circuit Fit — '+best.model_name,
                'x_label':"Z′ (Ω)", 'y_label':"−Z″ (Ω)",
                'series':[
                    {'label':'Measured • RAW','x':z.real.tolist(),'y':(-z.imag).tolist()},
                    {'label':'Best-fit • '+best.model_key,'x':fit_on_original.real.tolist(),
                     'y':(-fit_on_original.imag).tolist()},
                    *([{'label':'Smoothed preview','x':z_smooth.real.tolist(),
                        'y':(-z_smooth.imag).tolist(),'dashed':True}] if window else []),
                ]},
        'bode_plot':{'title':'Bode — impedance magnitude', 'x_label':'log10(f / Hz)', 'y_label':'|Z| (Ω)',
                    'series':[{'label':'Measured','x':np.log10(f).tolist(),'y':np.abs(z).tolist()},
                              {'label':'Model','x':np.log10(f).tolist(),'y':np.abs(fit_on_original).tolist()}]},
        'residual_plot':{'title':'Complex residuals vs frequency','x_label':'log10(f / Hz)','y_label':'Model − raw (Ω)',
                         'series':[{'label':'Real','x':np.log10(f).tolist(),'y':res.real.tolist()},
                                   {'label':'Imaginary','x':np.log10(f).tolist(),'y':res.imag.tolist()}]},
        'diagnostics':{'frequency_hz':f.tolist(),
                       'measured_real_ohm':z.real.tolist(),
                       'measured_neg_imag_ohm':(-z.imag).tolist(),
                       'predicted_real_ohm':fit_on_original.real.tolist(),
                       'predicted_neg_imag_ohm':(-fit_on_original.imag).tolist(),
                       'smoothed_real_ohm':z_smooth.real.tolist(),
                       'smoothed_neg_imag_ohm':(-z_smooth.imag).tolist(),
                       'residual_real_ohm':res.real.tolist(),
                       'residual_imag_ohm':res.imag.tolist()},
        'search':{'depth':search_depth,'weighting':weighting,'precision':precision,
                  'models_checked':keys,'fitted_count':len(fits)}
    }
    return result
