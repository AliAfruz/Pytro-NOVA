# NOVA Lab v3.9.1 — Qt build hotfix

Fixes a Qt 6.12 compilation error from v3.9 (`curve.segments.append({})` overload ambiguity). No changes to numerical data. Run `BUILD_AND_RUN_WINDOWS.ps1` on your previously configured Windows Qt 6.12/MinGW system.

# NOVA Lab v3.9 — GCD Display Fix

**Fixes the GCD plot compression and false connecting lines.** See [CHANGES_v3_9.md](CHANGES_v3_9.md) for diagnosis and precise behavior.

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

## Earlier documentation

# NOVA Lab v3.6.1 — Overlay Workspace (Qt 6 Build Fix)

Native **C++ Qt 6 desktop frontend** and **Python NOVA `.nox` decoding / electrochemical analysis backend**. This edition adds a separate multi-curve comparison window to the existing v3.5 exporter, Afruz-EIS analysis, CV peak tools and animated scientific dashboard.

## Install on your Windows PC

1. Download the v3.6 ZIP and **Extract All** under `C:\path\to\NOVA\`, keeping the `NOVA_Lab_v3_6_1_Overlay_Fixed` folder.
2. Close other running NOVA Lab windows (the build will replace the executable).
3. In PowerShell:

```powershell
cd "C:\path\to\NOVA\NOVA_Lab_v3_6_1_Overlay_Fixed"
powershell -ExecutionPolicy Bypass -File .\BUILD_AND_RUN_WINDOWS.ps1
```

The build script uses **Qt 6.12.0**, **MinGW 13.1.0**, **CMake** and **Ninja**, just like the v3.5 package. Keep your old v3.5 folder until v3.6 compiles and opens successfully.

For later launches, run `RUN_NOVALAB_WINDOWS.bat` from the project directory.

## How to overlay CV curves

1. Open a `.nox` file in the main NOVA Lab window.
2. Select `CV 1` from the dataset list.
3. **Right-click the central graph** and select **Send CV current vs voltage to Overlay** (or click `SEND TO OVERLAY`).
4. The separate **MULTI-CURVE OVERLAY LAB** opens on the **CV • I–V** tab.
5. In the main window select `CV 2`, right-click the graph, and send it to Overlay as well. Two colored curves now share the same plot.
6. You can load another `.nox` file in the main app and send its CV data into the same persistent overlay window.

## How to overlay EIS curves

1. Select an EIS dataset in the main window.
2. Right-click its graph and choose **Send EIS Nyquist to Overlay**, **Send EIS Bode magnitude to Overlay**, or **Send EIS Bode phase to Overlay**.
3. Repeat for other EIS datasets. The workspace uses separate tabs:

| Tab | X axis | Y axis |
| --- | --- | --- |
| CV I–V | Applied potential (V) | WE current (µA) |
| EIS Nyquist | Z′ (Ω) | −Z″ (Ω) |
| EIS Bode magnitude | Frequency (Hz), log display | \|Z\| (Ω) |
| EIS Bode phase | Frequency (Hz), log display | −Phase (degrees) |

**CV data cannot be sent to EIS tabs** and **EIS data cannot be sent to CV tabs**. Nyquist and Bode curves also cannot be combined on one axes due to incompatible units. Nonpositive frequencies are excluded from logarithmic Bode plots, with original source files left unchanged.

## Overlay window controls

- **Show:** check or uncheck a row in the curve list to hide/reveal it.
- **Color:** select a curve and assign a different color.
- **Rename:** set a more useful legend label.
- **Remove / Clear this tab:** remove one/all curves from the selected technique tab.
- **Wheel zoom / double click:** zoom and reset; **Reset zoom** also available by button.
- **Grid / Soft glow:** change plot presentation (data unaffected).
- **Save overlay PNG:** export the currently selected plot tab as an image.
- **Export visible curves CSV:** export selected tab's visible curves to **one tidy CSV**. Columns include source filename, dataset, label, technique, plot mode, original point index, and two measured numeric columns. Source numerical values are stored without smoothing. CV values are exported in **amperes** despite the display's microampere scaling. Bode frequencies are exported in **Hz** (not logarithms).
- Use the main menu's **Open overlay workspace** (`Ctrl+Shift+O`) to reopen the window. Closing it hides the overlay and retains curves within the session.

## Other v3.5 tools preserved

- Standard plot CSV export: **one CV current–voltage CSV per CV run**, and **three EIS CSVs** (Nyquist, Bode magnitude, Bode phase) per EIS spectrum.
- Python CV peak analysis, baseline and fit tools; Afruz-EIS automatic circuit model fitting; GUI animations and large graph layout.
- Offline reading of supported Metrohm NOVA data; the `.nox` file is never modified.

## Tests

```powershell
$env:METROHM_SAMPLE = "C:\path\to\A110.001.nox"
py -3 -m unittest discover -s tests -v
```

The tests cover Python decoding, analysis, CSV export and static overlay wiring. This package is **not Windows Qt build-verified** on the authoring environment; your local Qt 6 / MinGW build is the final compile test. Overlays currently accept decoded **raw** measurements from the main viewer; fit component overlays from the Advanced Lab are not yet included.

## Change log

See `CHANGES_v3_6.md` for a detailed overlay feature list and technical scope. Third-party model/fit licensing remains governed by the included `LICENSE` and the imported Afruz-EIS files.

## v3.6.1 — Qt 6.12 / MinGW compiler correction

The v3.6 overlay window had two compilation defects in `app/overlay_workspace.cpp`:

- Added the missing `<QtCore/QJsonArray>` include (plus explicit `QJsonValue` header).
- Renamed the color palette array `palette` to `curvePalette` to avoid accidental name resolution to `QWidget::palette()`.

The `yy` errors reported by MinGW were downstream parser errors caused by the incomplete `QJsonArray` type. No measurement format or curve selection behavior was changed.

To update the old v3.6 folder instead of downloading a new project, replace `app/overlay_workspace.cpp` with the version included in v3.6.1, then build again. No need to delete your old working projects.

Compilation requires Windows Qt 6.12 and MinGW, which are not available in the authoring environment; the corrected source has passed static checks and Python regression tests.

## v3.7 — GCD, LSV, DPV, SWV, CA, CP and OCP

The existing CV/EIS pipeline has been extended with a technique-aware plot workspace,
unit-labelled CSV/TSV import, conservative NOVA function-handler recognition, raw
plot CSV exports and strict same-technique overlay groups. Details and scientific
limitations are in **[CHANGES_v3_7.md](CHANGES_v3_7.md)**.

Launch `Open measurement`, select a `.nox` or `.csv` file. For CSV select its
technique in the popup. Click **Other techniques** to switch between these
measurements; use **Send to Overlay** or right-click the curve. The overlay
workspace provides separate tabs for all techniques; no CV/EIS/GCD mixing.

**Real `.nox` samples are required** to verify or extend the proprietary NOVA
handler mappings for GCD, LSV, DPV, SWV, CA, CP and OCP. The included sample
`A110.001.nox` only verifies CV and EIS. Synthetic CSV demos in
`examples/new_techniques/` verify the full nonproprietary import/plot pipeline.

Windows build (from extracted folder):

```powershell
powershell -ExecutionPolicy Bypass -File .\BUILD_AND_RUN_WINDOWS.ps1
```
