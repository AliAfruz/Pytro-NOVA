# NOVA Lab v3.7 — Multi-technique workspace

## New techniques

| Technique | Plot axes | Analysis (preliminary) | Overlay | Plot CSV |
|---|---|---|---|---|
| GCD | time (s) vs potential (V) | duration, potential extrema, charge integration **if current exists** | GCD only | 1 |
| LSV | potential (V) vs current (A) | provisional peak detection | LSV only | 1 |
| DPV | potential (V) vs current (A) | provisional peak detection; pulse semantics must be verified | DPV only | 1 |
| SWV | potential (V) vs current (A) | provisional peak detection | SWV only | 1 |
| CA | time (s) vs current (A) | extrema, charge integral, duration | CA only | 1 |
| CP | time (s) vs potential (V) | potential trend, duration | CP only | 1 |
| OCP | time (s) vs potential (V) | potential drift, duration | OCP only | 1 |

**Existing CV and EIS features are unchanged.** EIS retains three separate Nyquist/Bode overlay modes. CV/LSV/DPV/SWV are intentionally **not** overlaid together because distinct techniques can have different acquisition semantics.

## How to load

1. **.nox:** Open measurement. The backend recognizes populated technique-specific NOVA function handlers when their stored arrays match a known schema; this is **provisional** for new techniques and has not been verified on real GCD/LSV/DPV/SWV `.nox` examples.
2. **.csv/.tsv:** Open measurement; select the correct technique when prompted. Headers must identify columns and units, e.g. `Time (s),Potential (V),Current (mA)` for GCD or `Potential (V),Current (µA)` for DPV. `Current (mA)` and `Current (µA)` are converted to A.
3. In the **Other techniques** sidebar or dataset chooser, select the measurement. Right-click the plot to send it to the correct overlay tab. Export only plot-ready CSV through the main export actions.

## Important scientific limitations

- No automatic interpretation of unknown proprietary .NET field layouts. A new `.nox` variant can be readable but lack recognized arrays; please supply files from your NOVA version to add/test precise mappings.
- Raw numerical values are not smoothed or modified. CV-style peak search is provisional for pulse techniques and **not** pulse-background subtraction, and should not be used for quantitative electrochemical conclusions without verification.
- GCD-specific capacitance needs active mass, cell/working-electrode convention, applied current, IR-drop handling and validated half-cycle boundaries. This release avoids inventing these values.
- All new samples in `examples/new_techniques/` are **synthetic demonstrations**, not acquired NOVA data.
- Advanced Lab's Afruz-EIS fitting and CV advanced peak fitter still apply to their existing techniques only; new techniques use the main analysis inspector.
