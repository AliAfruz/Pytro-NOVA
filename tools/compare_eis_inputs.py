"""Compare a Metrohm NOVA EIS dataset with an Afruz-EIS CSV export.

Compares raw complex impedance at matched frequencies; no smoothing or fits.
Example:
    py tools/compare_eis_inputs.py A110.005.nox 'EIS 2' original_export.csv
"""
import argparse
from pathlib import Path
import numpy as np
from compare_original_afruz import load


def main():
    ap = argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('nox_file', type=Path)
    ap.add_argument('dataset', help='EIS dataset name, e.g. "EIS 2"')
    ap.add_argument('original_export_csv', type=Path)
    args=ap.parse_args()
    f1,z1=load(args.nox_file,args.dataset)
    f2,z2=load(args.original_export_csv,None)
    matched=[]
    for i,fr in enumerate(f1):
        nearest=int(np.argmin(np.abs(np.log(f2/fr))))
        rel=abs(f2[nearest]-fr)/fr
        if rel<0.0002:
            matched.append((i,nearest))
    print(f'NOVA points: {len(f1)}; Afruz CSV points: {len(f2)}; frequency matches: {len(matched)}')
    if len(matched)<min(len(f1),len(f2))*.8:
        print('WARNING: Fewer than 80% of frequencies match. Files may be different measurements or use different frequency units.')
    if not matched:
        return
    a=np.array([z1[i] for i,_ in matched]); b=np.array([z2[j] for _,j in matched])
    rmse=lambda d: float(np.sqrt(np.mean(np.abs(d)**2)))
    print(f'Mean complex magnitude difference: {float(np.mean(np.abs(a-b))):.9g} Ω')
    print(f'Complex RMSE: {rmse(a-b):.9g} Ω')
    print(f'Complex RMSE if imaginary sign reversed in Afruz CSV: {rmse(a-b.conjugate()):.9g} Ω')
    print(f'Max complex difference: {float(np.max(np.abs(a-b))):.9g} Ω')
    if rmse(a-b.conjugate()) < rmse(a-b)*0.1:
        print('ALERT: Imaginary sign conventions probably differ between the two exports.')
    elif rmse(a-b) < 1e-6:
        print('INPUT PARITY PASS: the two imports agree within 1e-6 ohm on matched points.')
    else:
        print('INPUTS DIFFER: check that they are the same dataset, frequency units, and sign convention.')

if __name__=='__main__':
    main()
