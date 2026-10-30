# NOVA Lab 3.6 — Plot Overlay Workspace

## New desktop functionality

- The main signal plot now has a **right-click menu** for adding its dataset to a separate overlay window.
- For **CV**, select **Send CV current vs voltage to Overlay**.
- For **EIS**, choose **Send EIS Nyquist**, **Send EIS Bode magnitude**, or **Send EIS Bode phase**. These occupy separate tabs with compatible axes and units.
- A **Send to Overlay** plot button and **Plot overlap** sidebar item provide shortcuts. The application menu also has **Open overlay workspace** (`Ctrl+Shift+O`).
- The overlay window supports curves from **multiple files**: send curves, open another `.nox` in the main window, and send its data too.
- Each tab supports multiple color-coded curves, editable labels, hide/show, remove, clear, wheel zoom, double-click zoom reset, grid toggle, animated glow toggle, PNG export, and CSV export of visible curves.
- Curves remain in the overlay when the window is closed and reopened during the same application session.
- Strict family validation rejects CV in EIS tabs and EIS in CV tabs, even when called through the API. Nyquist and Bode plots cannot share axes.
- Bode frequency axes are logarithmic **for display only**; CSV keeps original frequency values.
- CV current is displayed in **µA** for readability, while CSV exports original current in **A**. No smoothing, interpolation, reordering, or fitting is performed in the overlay.

## Source layout

- `app/overlay_workspace.h` — public API, technique tab types, explicit family validation entry point
- `app/overlay_workspace.cpp` — separate window, render widget, curve controls and export
- `app/main.cpp` — context menu, toolbar and sidebar integration
- `CMakeLists.txt` — new compilation unit (preserves split-source / low-memory MinGW build)
- `tests/test_overlay_contract.py` — static UI integration assertions, sample decoder schema checks
- `examples/A110.001_CV_Overlay_Example.csv` — representative two-curve CSV example

## Scope and limits

Currently overlays **decoded raw measurement curves** from the main NOVA Lab viewer. Overlaying fitted Advanced Lab traces and other techniques requires further UI/backend integration. This is not an equivalent-circuit fitting feature; it does not modify the original data.

The C++/Qt code has not been compiled on the current Linux environment because Qt development headers are unavailable. Compile on Windows with your existing Qt 6.12.0 + MinGW 13.1.0 toolchain.
