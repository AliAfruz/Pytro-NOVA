# NOVA Lab v3.6.1 — Qt Overlay Compiler Fix

## Root cause of failed v3.6 build

1. `app/overlay_workspace.cpp` used `QJsonArray` by value but only indirectly included its forward declaration. Add `#include <QtCore/QJsonArray>`.
2. A file-scope `palette` array collided with the inherited `QWidget::palette()` lookup inside `OverlayWindow::addDataset()`. Rename array to `curvePalette` and update the reference.
3. Subsequent `yy` undeclared errors were cascading diagnostics from the incomplete JSON type.

No scientific numerical or CSV calculation was changed. Run `BUILD_AND_RUN_WINDOWS.ps1` in the extracted v3.6.1 root folder.
