"""Numerical parity check: original Afruz-EIS engine vs NOVA's integrated copy.

Usage:
  py tools/compare_original_afruz.py C:\\path\\Afruz-EIS.zip C:\\path\\A110.005.nox --dataset 'EIS 2'
  py tools/compare_original_afruz.py C:\\path\\Afruz-EIS.zip C:\\path\\EIS_2.csv

This checks identical fitting on exactly the same values; it is NOT a test of
scientific adequacy or equivalent-circuit identifiability.
"""
from __future__ import annotations
import argparse
import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from auto_eis import extract_spectrum
from afr_eis.fitting import FitSettings as IntegratedSettings, fit_model as integrated_fit


def from_csv(path: Path):
    with path.open('r', encoding='utf-8-sig', newline='') as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError('CSV has no header row')
        names = reader.fieldnames
        def norm(s):
            return s.lower().replace(' ', '').replace('′', "'").replace('″', "''").replace('ω','ohm').replace('Ω','ohm')
        def choose(items, kind):
            for token in items:
                match = next((n for n in names if token in norm(n)), None)
                if match is not None:
                    return match
            raise ValueError(f'Cannot identify {kind} column in {names!r}')
        fc = choose(['frequency', 'freq', 'f(hz)'], 'frequency')
        re = choose(["z'(", "z'(ohm)", 'zreal', 're(z)'], 'real impedance')
        im = choose(["-z''", '-zimag', "z''", 'zimag', 'im(z)'], 'imaginary impedance')
        rows = list(reader)
        f = np.array([float(r[fc]) for r in rows], dtype=float)
        real = np.array([float(r[re]) for r in rows], dtype=float)
        raw_im = np.array([float(r[im]) for r in rows], dtype=float)
        # In the original Afruz-EIS importer, labels beginning with '-' denote
        # stored -Z'' and are negated to yield the underlying complex imaginary part.
        imag = -raw_im if norm(im).startswith('-') else raw_im
        good = (np.isfinite(f) & (f > 0) & np.isfinite(real) & np.isfinite(imag))
        if np.sum(good) < 9:
            raise ValueError('Need at least 9 valid positive-frequency points')
        order = np.argsort(f[good])[::-1]
        return f[good][order], (real[good] + 1j*imag[good])[order]


def load(path: Path, dataset: str):
    if path.suffix.lower() == '.nox':
        from nox_reader import read_nox
        spectra = [d for d in read_nox(path)['datasets'] if d['kind'] == 'EIS']
        if dataset:
            spectra = [d for d in spectra if d['name'] == dataset]
        if len(spectra) != 1:
            raise ValueError(f'Choose exactly one EIS dataset using --dataset. Available: '
                             f"{[d['name'] for d in read_nox(path)['datasets'] if d['kind']=='EIS']}")
        return extract_spectrum(spectra[0])
    return from_csv(path)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('original_archive', type=Path, help='Original Afruz-EIS.zip (contains eis_studio/)')
    p.add_argument('spectrum', type=Path, help='Metrohm NOVA .nox or EIS CSV')
    p.add_argument('--dataset', default=None, help='Exact NOX EIS dataset, for example EIS 2')
    p.add_argument('--circuit', default='R-(R||C)', help='Circuit key tested by both engines')
    p.add_argument('--precision', choices=['quick','original'], default='original')
    args = p.parse_args()
    if not args.original_archive.is_file():
        p.error('Original Afruz-EIS ZIP file not found')
    if not args.spectrum.is_file():
        p.error('Spectrum input not found')

    sys.path.insert(0, str(args.original_archive.resolve()))
    from eis_studio.fitting import FitSettings as OriginalSettings, fit_model as original_fit
    from eis_studio.models import CIRCUITS as OriginalCircuits
    from afr_eis.models import CIRCUITS as IntegratedCircuits

    if args.circuit not in OriginalCircuits or args.circuit not in IntegratedCircuits:
        p.error('Circuit key is absent from one of the model libraries')
    f, z = load(args.spectrum, args.dataset)
    config = dict(weighting='modulus', robust_loss='soft_l1',
                  max_nfev=(8000 if args.precision=='original' else 900),
                  multistart=(8 if args.precision=='original' else 2),
                  optimizer=('hybrid' if args.precision=='original' else 'least_squares'))
    print(f'Dataset: {args.spectrum.name}, points={len(f)}, f={min(f):.5g}..{max(f):.5g} Hz')
    print(f'Input Zreal={min(z.real):.6g}..{max(z.real):.6g} Ω, '
          f'ImZ={min(z.imag):.6g}..{max(z.imag):.6g} Ω')
    print(f'Circuit: {args.circuit}; optimizer: {config["optimizer"]}')
    orig = original_fit(f.copy(), z.copy(), args.circuit, OriginalSettings(**config))
    port = integrated_fit(f.copy(), z.copy(), args.circuit, IntegratedSettings(**config))
    param_errors = {name: abs(orig.params[name] - port.params[name]) for name in orig.params}
    curve_delta = float(np.max(np.abs(orig.z_fit - port.z_fit)))
    print(f'Original RMSE: {orig.rmse:.12g} Ω; NOVA RMSE: {port.rmse:.12g} Ω')
    print(f'Maximum fitted-curve difference: {curve_delta:.12g} Ω')
    print(f'Maximum parameter difference: {max(param_errors.values(), default=0):.12g}')
    ok = np.allclose(orig.z_fit, port.z_fit, rtol=1e-9, atol=1e-10)
    if ok:
        print('PARITY PASS: the two numeric engines agree for this dataset, model and settings.')
        print('If GUI fits differ, investigate dataset selection, input sign, circuit/model and settings.')
    else:
        print('PARITY FAILURE: the numeric engines disagree. Report this output for debugging.')
        sys.exit(1)
    print('NOTE: Engine parity does NOT mean the chosen model fits your EIS spectrum well.')


if __name__ == '__main__':
    main()
