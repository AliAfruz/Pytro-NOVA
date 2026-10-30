# NOVA Lab v3.5 — Minimal Plot CSV Export

Replaces the 20–40-file v3.4 export bundle with exactly the CSVs needed for scientific plotting.

- **CV:** one CSV per CV dataset, two columns: Applied potential (V), WE current (A).
- **EIS:** three CSVs per EIS dataset: Nyquist (`Z'`, `-Z''`), Bode magnitude (`Frequency`, `|Z|`), Bode phase (`Frequency`, `-Phase`).
- **No duplicates:** no raw-data copies, time-series exports, metadata.csv, peaks.csv, metrics.csv, or index CSVs in the normal export.
- **Precise:** preserved source values (17-digit round-trip), recorded order, native units, no smoothing or calculated fits.
- **Selected:** "Export selected plot CSVs" produces only the selected CV or EIS dataset's plot files.
- **All:** "Export plot CSVs" produces all currently decoded CV/EIS plots in a new folder.
- Each folder contains a plain-text README (not another CSV).
- "Export peaks CSV" remains a separate, optional manual action in the CV analysis tools.

The existing backend data decoder, original datasets in NOVA, animated Qt GUI, and advanced analysis are not modified.
