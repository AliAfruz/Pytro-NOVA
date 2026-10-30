# NOVA Lab v3.8 — Real GCD / self-discharge decoding and grouped cycles

## What changed in this release

**C++/Qt frontend, Python backend.** The previous “No measurements” problem with two
NOVA files supplied for this update has been corrected. Older CV/EIS and provisional
LSV/DPV/SWV/CA/CP imports are preserved.

- **NOVA legacy ArrayList parameters**: in addition to `Collection`1+items`, the
  decoder now reads `CollectionBase+list` command collections. This is the
  decisive difference in these genuine files.
- **Real galvanostatic and OCP readings**: reconstruct actual plotted
  `PlotsEvst` X=CalcTime and Y=EI_0.CalcPotential samples, only after confirming
  they agree with the owning `FHLevelGalvanostatic` or `FHLevelOcp` handler.
  Empty plot placeholders and duplicate signal commands are skipped.
- **Cycle-aware plotting**: all cycles of a dataset are drawn in the **same main
  plot by default** with separate colors, not joined by spurious straight lines.
  **CYCLES → All cycles** shows everything; choose a single cycle/interval to
  inspect it. The same logic applies to multi-scan CV and imported technique CSVs.
- **Elapsed vs original time**: the default GCD/OCP X axis is **Cycle / interval
  elapsed time (s) [derived]**, aligning curves at t=0. You can change **X AXIS**
  to **Time (s)** to plot original NOVA time coordinates. The raw timestamps and
  voltages are unchanged.
- **Separate Overlay window**: sending a multi-cycle dataset to Overlay now
  creates a separate curve for each cycle, with independent colors/visibility.
  CV, GCD, OCP and EIS remain in their own compatible technique tabs.
- **Large data performance**: Qt limits *rendered* vertices/hover scans for
  responsiveness, but retains every raw point in the data table and exports.

### Verified directly against your two uploaded `.nox` files

| File | Decoded sets | Original measurement points | Grouping |
|---|---|---:|---|
| `GCD.nox` | GCD 1 | 82,795 | 44 populated galvanostatic segments, 23 inferred groups |
| `self discharge.nox` | CV 1, GCD 1, OCP 1 | 1,312 + 121,615 + 72,000 | 14 GCD segments / 8 inferred groups; 6 OCP intervals |
| `A110.001.nox` | CV 1, CV 2, EIS 1 | 202 + 202 + 40 | Existing CV/EIS results preserved |

**Scientific provenance:** For GCD, cycle identifiers were *inferred* from
rising/falling potential segments; they were not read from an authoritative
cycle-counter field. The data don't supply verified current vs time, so this
release intentionally does **not** calculate gravimetric capacitance or capacity
from those GCD voltage traces. OCP interval labels are separate rest measurements,
not cycles. Procedure titles may be generic/incorrect in NOVA; classification
here uses verified measured signal handlers instead.

**Coverage:** Additional NOVA technique variants can have different serialization
layouts. LSV, DPV, SWV, CA and CP CSV imports and provisional specialized handlers
remain available; do not assume arbitrary proprietary `.nox` files can be decoded.

## Windows install / launch (your existing Qt setup)

Extract this project to `C:\path\to\NOVA\NOVA_Lab_v3_8_Cycles`
then run in PowerShell:

```powershell
cd "C:\path\to\NOVA\NOVA_Lab_v3_8_Cycles"
powershell -ExecutionPolicy Bypass -File .\BUILD_AND_RUN_WINDOWS.ps1
```

Open `GCD.nox` or `self discharge.nox`, and select **GCD 1** or **OCP 1** from
DATASET. All inferred groups/intervals appear together. The build script accepts
an optional .nox path as an argument.

No new Python libraries are needed for the NOVA decoder; the optional Afruz-EIS
analysis tools still use NumPy and SciPy.

## Tests

```powershell
py -3 -m unittest discover -s tests -v
```

Optional tests with original NOVA files (not redistributed): set
`METROHM_SAMPLE`, `METROHM_GCD_SAMPLE`, `METROHM_SELF_DISCHARGE_SAMPLE`
to their full paths in your environment before running tests.

---
