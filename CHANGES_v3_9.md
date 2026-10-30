# NOVA Lab v3.9 — GCD plotting correction

This update addresses the unreadable, filled-in GCD plot shown for the real user-supplied `GCD.nox` sample.

## Root causes

* Its 23 inferred GCD cycles have **very different** durations (approximately 0.6 to 4,173 seconds). Drawing them all on one zero-based x-axis compresses most cycles into a thin region.
* The v3.8 Qt plot concatenated adjacent NOVA `FHLevel` traces within a cycle, drawing **non-measured straight lines** across charge/discharge handler boundaries. In `self discharge.nox`, a 1,200 s OCP step can also lie between galvanostatic levels.
* The plot bounds were computed globally, including hidden cycles. Choosing a short cycle left it stuck on a large x-axis.
* The 7 px glow on every trace obscured small curves.

## What changed

* Backend adds `comparable_cycle_groups` and `recommended_cycles` as **display-only metadata**, grouping adjacent inferred cycles of similar elapsed duration and voltage range.
* Main Qt GCD view initially selects a comparable set: **cycles 17–18** on the supplied `GCD.nox`. You can select other groups, any single cycle, or **All cycles**.
* Switching the cycle view resets zoom and dynamically refits both axes to the *visible* curves; derived elapsed time starts at zero.
* The plot renders each original `Recorded segment` as an independent path. There is no invented line across level transitions or OCP gaps.
* Glow is disabled for dense GCD/OCP lines, so individual curves remain distinguishable.
* Sending a GCD view to the Overlay workspace passes the selected cycles only. The overlay also respects recorded segment breaks.
* Every recorded measurement point, cycle label, original timestamp, and exported CSV value is unchanged.

## Scientific note

These remain **inferred grouping IDs**, not an authoritative NOVA cycle counter. Similar duration/voltage is **not proof of equal applied current** or physically equivalent electrochemical conditions. Confirm experiment settings before using the groups for rate-capability or cycle-retention conclusions. In particular, `GCD.nox` appears to mix tests of very different time scales; using “All cycles” is still allowed but not ideal for comparison.

## Build

Windows with Qt 6.12.0 + MinGW 13.1.0, in PowerShell:

```powershell
cd "C:\path\to\NOVA\NOVA_Lab_v3_9_GCD_Display_Fix"
powershell -ExecutionPolicy Bypass -File .\BUILD_AND_RUN_WINDOWS.ps1
```

The native C++/Qt code requires compilation on your Windows system. Python regression checks have been run against actual .nox samples, but Windows Qt compilation is not available in this environment.
