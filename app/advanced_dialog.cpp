#include "advanced_dialog.h"
#include "advanced_dialog_api.h"

QDialog *createAdvancedLabDialog(const QString &file,
                                 const QJsonArray &datasets,
                                 const QString &preferredDataset,
                                 const QString &python,
                                 const QString &backendScript,
                                 QWidget *parent) {
    return new AdvancedLabDialog(file, datasets, preferredDataset, python, backendScript, parent);
}
