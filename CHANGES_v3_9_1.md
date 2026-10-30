# NOVA Lab v3.9.1 — Qt 6 compilation correction

The Qt 6.12 / MinGW 13 build failed with an ambiguous `QList::append({})` overload in `PlotView::setDataset`. The code now explicitly appends `QVector<QPointF>{}`. A source-regression test has been updated to prevent this reintroduction. Measurement extraction, cycle grouping, and plot logic are unchanged.

The GUI has not been compiled in this environment: compile using `BUILD_AND_RUN_WINDOWS.ps1` on Windows.
