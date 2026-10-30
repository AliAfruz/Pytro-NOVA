#pragma once
// Small public interface: the large advanced analysis Qt implementation is compiled separately.
#include <QtWidgets/QDialog>
#include <QtCore/QString>
#include <QtCore/QJsonArray>
class QWidget;
QDialog *createAdvancedLabDialog(const QString &file,
                                 const QJsonArray &datasets,
                                 const QString &preferredDataset,
                                 const QString &python,
                                 const QString &backendScript,
                                 QWidget *parent = nullptr);
