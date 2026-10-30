# v3.2 — Original Afruz-EIS parity update

NOVA v3.1 was not configured to reproduce the default behaviour of Afruz-EIS:
it started with 15 candidate models and a lower-effort bounded optimizer, instead
of the Afruz GUI's all-model hybrid 8-start/8000-evaluation default.

Changes:
- Qt Auto Circuit UI defaults to Exhaustive (all 19 candidates) and AFRUZ ORIGINAL precision.
- Backend CLI uses the same default when options are omitted.
- Best circuit selection now uses `ranking[0]` exactly like the original Afruz GUI,
  rather than silently replacing a top-ranked non-converged result with another model.
- Original numeric model and fitting source files remain unmodified.
- Added `tools/compare_original_afruz.py` for direct end-to-end comparison of fit
  parameters and predicted curves between the original Afruz module and NOVA's copy.

## Important

This improves compatibility; it does **not** establish a good fit to the user's
EIS 2 dataset. The original .nox file or CSV for EIS 2 and the original
Afruz-EIS fit settings are needed for a fair case-specific comparison. Do not
conflate a low numerical residual with a unique electrochemical circuit.
- Added `tools/compare_eis_inputs.py` for frequency-matched NOX vs Afruz CSV comparison, including a sign-reversal check.
- Display smoothing is now Off by default for raw-data visual parity; it remains optional.
