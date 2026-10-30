# v3.4 — Clean CSV export

- Removed complete Excel workbook (.xlsx) export menu, button, Python CLI action, and Excel XML writer.
- Replaced it with **Export complete CSV package**, producing a new organized output folder.
- Preserved the individual dataset and peak CSV export commands.
- Added plot-ready CV and EIS coordinate CSVs, raw-data index, metadata, columns index, and separated peaks / metrics / warnings tables.
- Preserved raw numerical values, column labels, measurement order, and source measurement units; no smoothing or normalization of raw traces.
- Added staging and non-overwriting output directories to protect earlier exports.
- Added drag-and-drop Windows CSV export batch file and CSV package regression tests.

Advanced Lab visual/export commands are unchanged; generated fitting results are not automatically collected by the new clean CSV bundle.
