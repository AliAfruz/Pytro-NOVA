#pragma once

#include <QtWidgets/QMainWindow>
#include <QtCore/QJsonObject>
#include <QtCore/QString>

// Curves may share one axes only when they use exactly the same X/Y semantics.
// CV and EIS cannot be mixed. Nyquist, Bode magnitude and Bode phase also
// occupy independent tabs because their axes and units differ.
enum class OverlayMode {
    CV = 0,
    Nyquist = 1,
    BodeMagnitude = 2,
    BodePhase = 3,
    GCD = 4, LSV = 5, DPV = 6, SWV = 7, CA = 8, CP = 9, OCP = 10
};

class OverlayWindow final : public QMainWindow {
public:
    explicit OverlayWindow(QWidget *parent = nullptr);
    ~OverlayWindow() override;
    bool addDataset(const QJsonObject &dataset, const QString &sourceFile,
                    OverlayMode mode, QString *error = nullptr);
    void showMode(OverlayMode mode);

private:
    struct Private;
    Private *d_ = nullptr;
    void refresh();
    void savePlot();
    void exportCsv();
    void recolorSelected();
    void renameSelected();
    void removeSelected();
    void clearCurrent();
};
