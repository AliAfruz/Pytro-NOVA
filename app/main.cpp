// Pytro-NOVA Dashboard — native Qt 5/6 Widgets frontend.
// Python backend: backend/bridge.py (safe, read-only decoding of .nox files).
// Build with C++17, Qt Widgets and CMake; no QtCharts/PySide/Matplotlib needed.
#include <QtWidgets/QApplication>
#include "neon_fx.h"
#include <QtWidgets/QMainWindow>
#include <QtWidgets/QWidget>
#include <QtWidgets/QFrame>
#include <QtWidgets/QVBoxLayout>
#include <QtWidgets/QHBoxLayout>
#include <QtWidgets/QGridLayout>
#include <QtWidgets/QLabel>
#include <QtWidgets/QPushButton>
#include <QtWidgets/QComboBox>
#include <QtWidgets/QInputDialog>
#include <QtCore/QMap>
#include <QtCore/QSet>
#include <QtWidgets/QFileDialog>
#include <QtWidgets/QMessageBox>
#include <QtWidgets/QSplitter>
#include <QtWidgets/QTableView>
#include <QtWidgets/QHeaderView>
#include <QtWidgets/QStatusBar>
#include <QtWidgets/QProgressBar>
#include <QtWidgets/QScrollArea>
#include <QtWidgets/QSpinBox>
#include <QtWidgets/QDoubleSpinBox>
#include <QtWidgets/QCheckBox>
#include <QtWidgets/QTableWidget>
#include <QtWidgets/QTableWidgetItem>
#include <QtWidgets/QTabWidget>
#include <QtWidgets/QMenuBar>
#include <QtWidgets/QMenu>
#include "overlay_workspace.h"
#include <QtGui/QPainter>
#include <QtGui/QPainterPath>
#include <QtGui/QFont>
#include <QtGui/QAction>
#include <QtGui/QKeySequence>
#include <QtGui/QBrush>
#include <QtWidgets/QStyle>
#include <QtGui/QMouseEvent>
#include <QtGui/QWheelEvent>
#include <QtCore/QAbstractTableModel>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>
#include <QtCore/QJsonArray>
#include <QtCore/QProcess>
#include <QtCore/QStandardPaths>
#include <QtCore/QCoreApplication>
#include <QtCore/QFileInfo>
#include <QtCore/QDir>
#include <QtCore/QFile>
#include <QtCore/QTimer>
#include <QtCore/QPointF>
#include <QtCore/QVector>
#include <QtCore/QSignalBlocker>
#include <algorithm>
#include <cmath>
#include <limits>

namespace {
const QColor kCyan("#46e8fd"), kViolet("#b47aff"), kText("#dcefff"), kMuted("#7f9cbd");

QString asNumber(double value, int precision=5) {
    if (!std::isfinite(value)) return "—";
    return QString::number(value, 'g', precision);
}

QLabel *makeLabel(const QString &text, const QString &name={}) {
    auto *label = new QLabel(text);
    if (!name.isEmpty()) label->setObjectName(name);
    return label;
}

QFrame *makePanel(const QString &name="Panel") {
    auto *f = new QFrame;
    f->setObjectName(name);
    return f;
}
}

// Table is a view over the JSON decoded by Python. No measurement processing here.
class DataTableModel : public QAbstractTableModel {
public:
    explicit DataTableModel(QObject *parent=nullptr) : QAbstractTableModel(parent) {}
    void setDataset(const QJsonObject &obj) {
        beginResetModel();
        cols_ = obj.value("columns").toArray();
        rows_ = obj.value("values").toArray();
        endResetModel();
    }
    int rowCount(const QModelIndex &parent={}) const override {
        return parent.isValid()?0:rows_.size();
    }
    int columnCount(const QModelIndex &parent={}) const override {
        return parent.isValid()?0:cols_.size();
    }
    QVariant headerData(int section, Qt::Orientation orientation, int role=Qt::DisplayRole) const override {
        if (role!=Qt::DisplayRole) return {};
        if (orientation==Qt::Vertical) return section+1;
        if (section>=0 && section<cols_.size())
            return cols_[section].toObject().value("label").toString();
        return {};
    }
    QVariant data(const QModelIndex &index, int role=Qt::DisplayRole) const override {
        if (!index.isValid() || index.row()>=rows_.size() || index.column()>=cols_.size()) return {};
        if (role==Qt::TextAlignmentRole) return int(Qt::AlignRight | Qt::AlignVCenter);
        if (role!=Qt::DisplayRole) return {};
        const QJsonArray row=rows_[index.row()].toArray();
        if(index.column()>=row.size()) return {};
        const QJsonValue val=row[index.column()];
        return val.isDouble() ? QVariant(asNumber(val.toDouble(),11)) : val.toVariant();
    }
private:
    QJsonArray cols_, rows_;
};

class RingMeter : public QWidget {
public:
    explicit RingMeter(QWidget *parent=nullptr) : QWidget(parent) { setMinimumSize(142,130); }
    void setRatio(double r) { ratio_=std::clamp(r,0.0,1.0); update(); }
protected:
    void paintEvent(QPaintEvent*) override {
        QPainter p(this);
        p.setRenderHint(QPainter::Antialiasing);
        const double s=std::min(width(),height())-28;
        QRectF circle((width()-s)/2.0,(height()-s)/2.0,s,s);
        p.setPen(QPen(QColor("#20314f"),10,Qt::SolidLine,Qt::RoundCap));
        p.drawArc(circle, 210*16, -300*16);
        p.setPen(QPen(QColor(70,232,253,40),16,Qt::SolidLine,Qt::RoundCap));
        p.drawArc(circle, 210*16, int(-300*ratio_*16));
        QConicalGradient gradient(circle.center(),-30);
        gradient.setColorAt(0,kCyan);
        gradient.setColorAt(0.5,kViolet);
        gradient.setColorAt(1,kCyan);
        p.setPen(QPen(QBrush(gradient),9,Qt::SolidLine,Qt::RoundCap));
        p.drawArc(circle,210*16,int(-300*ratio_*16));
        p.setPen(kText);
        QFont number=p.font(); number.setPointSize(17); number.setBold(true);
        p.setFont(number);
        p.drawText(circle.adjusted(0,5,0,-5),Qt::AlignCenter,QString::number(ratio_*100.0,'f',0)+"%");
    }
private:
    double ratio_=0;
};

class PlotView : public QWidget {
public:
    explicit PlotView(QWidget *parent=nullptr) : QWidget(parent) {
        setMinimumSize(360,285);
        setMouseTracking(true);
    }
    void setDataset(const QJsonObject &dataset,int xCol,int yCol) {
        points_.clear();
        curves_.clear();
        focusedPeak_=-1;
        boundsReady_=false;
        zoom_=1;
        pointFocus_=-1;
        peaks_.clear();
        const QJsonArray cols=dataset.value("columns").toArray();
        if(xCol<0 || yCol<0 || xCol>=cols.size() || yCol>=cols.size()) { update(); return; }
        xLabel_=cols[xCol].toObject().value("label").toString();
        yLabel_=cols[yCol].toObject().value("label").toString();
        caption_=dataset.value("name").toString()+"  /  "+QString::number(dataset.value("point_count").toInt())+" samples";
        labelIntervals_=dataset.value("kind").toString()=="OCP";
        noGcdGlow_=dataset.value("kind").toString()=="GCD" || labelIntervals_;
        elapsedAxis_=cols[xCol].toObject().value("key").toString()=="cycle_time_s";
        accent_=dataset.value("kind").toString()=="CV" ? kViolet : kCyan;
        const QJsonArray records=dataset.value("values").toArray();
        // Every recorded cycle is displayed together, each with a separate
        // polyline and color. CV ScanNumber and imported cycle columns share
        // the same logic. No line joins distinct cycles or OCP intervals.
        int groupColumn=-1;
        int segmentColumn=-1;
        for(int j=0;j<cols.size();++j) {
            const QString key=cols[j].toObject().value("key").toString();
            if(key=="cycle" || (dataset.value("kind").toString()=="CV" && key=="scan")) groupColumn=j;
            if(key=="segment") segmentColumn=j;
        }
        QMap<int,int> curveLookup;
        const QVector<QColor> palette={QColor("#54ebff"),QColor("#ab91ff"),QColor("#ffca83"),
            QColor("#6ff2b6"),QColor("#ff86b5"),QColor("#87baff"),QColor("#f2e481"),
            QColor("#ff9b79"),QColor("#d389fa"),QColor("#89f0d9")};
        for(const auto &value:records) {
            QJsonArray row=value.toArray();
            if(row.size()<=std::max(xCol,yCol)) continue;
            double x=row[xCol].toDouble(std::numeric_limits<double>::quiet_NaN());
            double y=row[yCol].toDouble(std::numeric_limits<double>::quiet_NaN());
            if(std::isfinite(x)&&std::isfinite(y)) {
                const QPointF point(x,y);
                points_.append(point);
                int group=1;
                if(groupColumn>=0 && row.size()>groupColumn) group=row[groupColumn].toInt(1);
                if(!curveLookup.contains(group)) {
                    curveLookup.insert(group,curves_.size());
                    CycleCurve curve;
                    curve.group=group;
                    curve.color=palette[curves_.size()%palette.size()];
                    curves_.append(curve);
                }
                CycleCurve &curve=curves_[curveLookup[group]];
                curve.points.append(point);
                // A charge/discharge level ends when NOVA changes handler.
                // Do NOT invent a straight line between unrelated level traces.
                const int segment=(segmentColumn>=0 && row.size()>segmentColumn)? row[segmentColumn].toInt(1):1;
                if(curve.segments.isEmpty() || curve.lastSegment!=segment)
                    curve.segments.append(QVector<QPointF>{});
                curve.segments.last().append(point);
                curve.lastSegment=segment;
            }
        }
        recomputeVisibleBounds();
        update();
    }
    void resetZoom() { zoom_=1; pointFocus_=-1; update(); }
    void setVisibleCycle(int cycle) {
        QSet<int> selected;
        if(cycle>0) selected.insert(cycle);
        setVisibleCycles(selected);
    }
    void setVisibleCycles(const QSet<int> &cycles) {
        visibleCycles_=cycles;
        pointFocus_=-1;
        zoom_=1;
        recomputeVisibleBounds();
        update();
    }
    void recomputeVisibleBounds() {
        boundsReady_=false;
        for(const auto &curve:curves_) {
            if(!visibleCycles_.isEmpty() && !visibleCycles_.contains(curve.group)) continue;
            for(const auto &pt:curve.points) {
                if(!boundsReady_) {
                    xMin_=xMax_=pt.x();yMin_=yMax_=pt.y();boundsReady_=true;
                } else {
                    xMin_=std::min(xMin_,pt.x());xMax_=std::max(xMax_,pt.x());
                    yMin_=std::min(yMin_,pt.y());yMax_=std::max(yMax_,pt.y());
                }
            }
        }
        if(!boundsReady_) return;
        if(xMin_==xMax_) { xMin_-=1;xMax_+=1; }
        if(yMin_==yMax_) { yMin_-=0.1;yMax_+=0.1; }
        const double dx=(xMax_-xMin_)*0.035,dy=(yMax_-yMin_)*0.07;
        if(elapsedAxis_ && xMin_>=-1e-8) xMin_=0;
        else xMin_-=dx;
        xMax_+=dx;
        yMin_-=dy;yMax_+=dy;
    }
    void setPeaks(const QJsonArray &peaks, bool visible) {
        peaks_.clear();
        drawPeaks_ = visible;
        for(const auto &value : peaks) {
            const QJsonObject obj = value.toObject();
            peaks_.push_back({QPointF(obj.value("potential_v").toDouble(),obj.value("current_a").toDouble()),
                              obj.value("type").toString(),obj.value("row").toInt()});
        }
        update();
    }
    void setPeakVisibility(bool visible) { drawPeaks_=visible; update(); }
    void focusRow(int row) {
        for(int i=0;i<peaks_.size();++i) if(peaks_[i].row==row) {
            focusedPeak_=i; update(); return;
        }
        focusedPeak_=-1; update();
    }
protected:
    QRectF plotArea() const {
        return QRectF(86.0, 56.0,
                      static_cast<qreal>(std::max(1, width() - 122)),
                      static_cast<qreal>(std::max(1, height() - 122)));
    }
    QPointF pixel(const QPointF &p,const QRectF &a) const {
        const double cx=(xMin_+xMax_)/2, cy=(yMin_+yMax_)/2;
        const double dx=(xMax_-xMin_)/zoom_, dy=(yMax_-yMin_)/zoom_;
        return {a.center().x()+(p.x()-cx)/dx*a.width(),a.center().y()-(p.y()-cy)/dy*a.height()};
    }
    QPointF dataAt(const QPointF &p,const QRectF &a) const {
        const double cx=(xMin_+xMax_)/2, cy=(yMin_+yMax_)/2;
        const double dx=(xMax_-xMin_)/zoom_, dy=(yMax_-yMin_)/zoom_;
        return {cx+(p.x()-a.center().x())/a.width()*dx,cy-(p.y()-a.center().y())/a.height()*dy};
    }
    void paintEvent(QPaintEvent*) override {
        QPainter p(this);
        p.setRenderHint(QPainter::Antialiasing);
        QLinearGradient backdrop(0,0,width(),height());
        backdrop.setColorAt(0,QColor("#101932"));
        backdrop.setColorAt(1,QColor("#080f20"));
        p.fillRect(rect(),backdrop);
        // Soft star accents; fixed/deterministic so the plot remains calm and readable.
        for(int i=0;i<42;i++) {
            double xx=15+((i*197+37)%997)/997.0*(width()-30);
            double yy=12+((i*131+23)%991)/991.0*(height()-24);
            p.setPen(QColor(66,136,213,20+i%5*5));
            p.drawPoint(QPointF(xx,yy));
        }
        const QRectF a=plotArea();
        p.setPen(kMuted);
        if(!boundsReady_) {
            p.setFont(QFont("Segoe UI",12));
            p.drawText(rect(),Qt::AlignCenter,"OPEN A NOVA .NOX FILE TO DISPLAY DATA");
            return;
        }
        p.setFont(QFont("Segoe UI",9));
        const QPointF low=dataAt(QPointF(a.left(),a.bottom()),a);
        const QPointF high=dataAt(QPointF(a.right(),a.top()),a);
        for(int i=0;i<=6;i++) {
            const double f=i/6.0;
            const double x=a.left()+f*a.width(),y=a.bottom()-f*a.height();
            p.setPen(QPen(QColor("#2a3b57"),1));
            p.drawLine(QPointF(x,a.top()),QPointF(x,a.bottom()));
            p.drawLine(QPointF(a.left(),y),QPointF(a.right(),y));
            p.setPen(kMuted);
            p.drawText(QRectF(x-54,a.bottom()+8,108,19),Qt::AlignHCenter,asNumber(low.x()+f*(high.x()-low.x()),4));
            p.drawText(QRectF(3,y-10,a.left()-10,20),Qt::AlignRight|Qt::AlignVCenter,asNumber(low.y()+f*(high.y()-low.y()),4));
        }
        p.setPen(QPen(QColor("#4c85b3"),1));
        p.drawRect(a);
        p.setPen(kText);
        p.setFont(QFont("Segoe UI",10,QFont::DemiBold));
        p.drawText(QRectF(a.left(),12,a.width(),26),Qt::AlignLeft|Qt::AlignVCenter,caption_);
        p.setFont(QFont("Segoe UI",9));
        p.drawText(QRectF(a.left(),height()-42,a.width(),24),Qt::AlignHCenter,xLabel_);
        p.save();
        p.translate(15,a.center().y());p.rotate(-90);
        p.drawText(QRectF(-a.height()/2,-13,a.height(),26),Qt::AlignHCenter,yLabel_);
        p.restore();

        p.save(); p.setClipRect(a);
        const int shown=std::count_if(curves_.cbegin(),curves_.cend(),[this](const CycleCurve &curve) {
            return visibleCycles_.isEmpty() || visibleCycles_.contains(curve.group);
        });
        for(const auto &curve:curves_) {
            if(!visibleCycles_.isEmpty() && !visibleCycles_.contains(curve.group)) continue;
            // Each original NOVA handler is drawn as an independent path.
            // Never join discharge and charge records or OCP time gaps.
            for(const auto &trace:curve.segments) {
                if(trace.isEmpty()) continue;
                QPainterPath path;
                const int stride=std::max(1,static_cast<int>(trace.size())/2800);
                path.moveTo(pixel(trace.first(),a));
                for(int i=stride;i<trace.size();i+=stride)
                    path.lineTo(pixel(trace[i],a));
                if(trace.size()>1)path.lineTo(pixel(trace.last(),a));
                // Dense galvanostatic traces should remain line art, not a
                // neon-filled wall that hides individual cycles.
                if(!noGcdGlow_ && shown<=8) {
                    p.setPen(QPen(QColor(curve.color.red(),curve.color.green(),curve.color.blue(),32),5));
                    p.drawPath(path);
                }
                QColor ink=curve.color;
                if(shown>12) ink.setAlpha(145);
                p.setPen(QPen(ink,noGcdGlow_?1.55:1.8));
                p.drawPath(path);
                if(trace.size()<60 && shown<=5) {
                    p.setPen(Qt::NoPen);p.setBrush(ink);
                    for(const auto &pt:trace)p.drawEllipse(pixel(pt,a),1.5,1.5);
                }
            }
        }
        p.restore();
        // Show a compact cycle key; the selector provides access to all labels.
        if(curves_.size()>1) {
            p.setFont(QFont("Segoe UI",8,QFont::DemiBold));
            int n=0;
            for(const auto &curve:curves_) {
                if(!visibleCycles_.isEmpty() && !visibleCycles_.contains(curve.group))continue;
                if(n++>=7) {p.setPen(kMuted);p.drawText(QRectF(a.right()-100,a.top()+12+17*7,100,18),Qt::AlignRight,"More cycles…");break;}
                p.setPen(QPen(curve.color,3));
                const double sy=a.top()+17*n;
                p.drawLine(QPointF(a.right()-112,sy+5),QPointF(a.right()-96,sy+5));
                p.setPen(kText);
                p.drawText(QRectF(a.right()-92,sy-3,91,19),Qt::AlignLeft,
                    QString(labelIntervals_?"Interval %1":"Cycle %1").arg(curve.group));
            }
        }
        p.save();p.setClipRect(a);
        if(pointFocus_>=0 && pointFocus_<points_.size()) {
            const QPointF active=pixel(points_[pointFocus_],a);
            p.setPen(QPen(QColor(205,232,255,90),1,Qt::DashLine));
            p.drawLine(QPointF(active.x(),a.top()),QPointF(active.x(),a.bottom()));
            p.drawLine(QPointF(a.left(),active.y()),QPointF(a.right(),active.y()));
            p.setBrush(Qt::black);p.setPen(QPen(Qt::white,2));p.drawEllipse(active,5,5);
        }
        if(drawPeaks_) {
            for(int i=0;i<peaks_.size();++i) {
                const auto &peak=peaks_[i];
                const QPointF loc=pixel(peak.point,a);
                const bool reduction=peak.kind=="Reduction";
                const QColor hue=reduction ? QColor("#59f1df") : QColor("#f7b1ff");
                p.setBrush(QColor(9,18,39,220));
                p.setPen(QPen(hue,i==focusedPeak_?3.5:2.0));
                p.drawEllipse(loc,i==focusedPeak_?7:5,i==focusedPeak_?7:5);
                p.setFont(QFont("Segoe UI",9,QFont::DemiBold));
                p.setPen(hue);
                p.drawText(QRectF(loc.x()-52,loc.y()+(reduction?12:-30),104,20),Qt::AlignHCenter,
                           QString("%1 %2").arg(reduction?"Red":"Ox").arg(i+1));
            }
        }
        p.restore();
        if(pointFocus_>=0 && pointFocus_<points_.size()) {
            QString readout=QString("  X  %1       Y  %2  ").arg(asNumber(points_[pointFocus_].x(),7),asNumber(points_[pointFocus_].y(),7));
            p.setPen(accent_);p.setFont(QFont("Consolas",9));
            p.drawText(QRectF(a.left()+10,a.top()+9,a.width()-15,25),Qt::AlignRight,readout);
        }
    }
    void mouseMoveEvent(QMouseEvent *event) override {
        if(!boundsReady_) return;
        const QPointF pos=event->pos();
        const QRectF area=plotArea();
        if(!area.contains(pos)) { if(pointFocus_!=-1){ pointFocus_=-1;update(); } return; }
        int best=-1; double bestDistance=26*26;
        const int step=std::max(1,static_cast<int>(points_.size())/4000);
        for(int i=0;i<points_.size();i+=step) {
            const QPointF projected=pixel(points_[i],area);
            const double dx=projected.x()-pos.x(),dy=projected.y()-pos.y();
            const double d=dx*dx+dy*dy;
            if(d<bestDistance) { bestDistance=d; best=i; }
        }
        if(best!=pointFocus_) {pointFocus_=best;update();}
    }
    void leaveEvent(QEvent *) override { if(pointFocus_!=-1){pointFocus_=-1;update();} }
    void wheelEvent(QWheelEvent *event) override {
        if(!boundsReady_) return;
        zoom_=std::clamp(zoom_*(event->angleDelta().y()>0?1.24:1/1.24),1.0,40.0);
        update();event->accept();
    }
    void mouseDoubleClickEvent(QMouseEvent *) override {resetZoom();}
private:
    struct PeakMarker { QPointF point; QString kind; int row; };
    QVector<PeakMarker> peaks_;
    bool drawPeaks_=true;
    int focusedPeak_=-1;
    QVector<QPointF> points_;
    struct CycleCurve {
        int group=1;
        QVector<QPointF> points;
        QColor color;
        QVector<QVector<QPointF>> segments;
        int lastSegment=-1;
    };
    QVector<CycleCurve> curves_;
    QSet<int> visibleCycles_; // Empty = all; otherwise filter to comparable or selected cycles.
    bool elapsedAxis_=false, noGcdGlow_=false;
    bool labelIntervals_=false;
    QString xLabel_,yLabel_,caption_;
    QColor accent_=kCyan;
    bool boundsReady_=false;
    double xMin_=0,xMax_=1,yMin_=0,yMax_=1,zoom_=1;
    int pointFocus_=-1;
};

#include "advanced_dialog_api.h"

class MainWindow : public QMainWindow {
public:
    MainWindow() {
        setWindowTitle("PYTRO-NOVA  •  Metrohm Autolab Data Explorer");
        resize(1510,950);
        setMinimumSize(1040,680);
        applyTheme();
        createUi();
        setBusy(false);
        backendStatus_->setText((backendScript().isEmpty()||pythonExecutable().isEmpty())
                                ? "○ Python backend not detected" : "● Python backend ready");
    }
    void openFile(const QString &path) {
        if(path.isEmpty()||busy_) return;
        QStringList args={"read",path};
        fileTechnique_.clear();
        if(QStringList{"csv","tsv","txt"}.contains(QFileInfo(path).suffix().toLower())) {
            const QStringList options={"GCD","LSV","DPV","SWV","CA","CP","OCP"};
            bool accepted=false;
            const QString selected=QInputDialog::getItem(this,"Import electrochemical CSV",
                "Choose the technique (CSV columns must include SI units):",options,0,false,&accepted);
            if(!accepted||selected.isEmpty())return;
            fileTechnique_=selected;
            args<<"--technique"<<selected;
        }
        runBackend(args,Operation::Read,path);
    }
private:
    enum class Operation { Read, ExportOne, ExportAll, ExportText, Analyze, ExportPeaks };

    void applyTheme() {
        qApp->setStyleSheet(R"QSS(
            QMainWindow { background:#070c1b; }
            QWidget { color:#dfebff; font-family:'Segoe UI',Arial; font-size:10pt; }
            QLabel { background:transparent; }
            QFrame#Sidebar { background:#091329; border-right:1px solid #223659; }
            QLabel#Brand { font-size:25pt; font-weight:800; color:#effaff; }
            QLabel#Version { color:#56dffc; font-size:9pt; letter-spacing:2px; }
            QLabel#Muted { color:#91acce; }
            QLabel#Eyebrow { color:#53dcf4; font-weight:600; font-size:9pt; letter-spacing:2px; }
            QLabel#Title { font-size:23pt; font-weight:750; color:#eefaff; }
            QLabel#Section { color:#cdeeff; font-size:11pt; font-weight:700; }
            QLabel#StatName { color:#93aecb; font-size:9pt; }
            QLabel#StatValue { color:#e9fbff; font-size:17pt; font-weight:700; }
            QLabel#AccentNumber { color:#59e5f4; font-size:14pt; font-weight:700; }
            QFrame#Panel { background:rgba(13,26,51,220); border:1px solid #294263; border-radius:12px; }
            QFrame#Header { background:rgba(17,32,61,220); border:1px solid #28415e; border-radius:13px; }
            QFrame#StatCard { background:rgba(21,35,67,210); border:1px solid #284563; border-radius:12px; }
            QFrame#PlotPanel { background:rgba(11,23,48,223); border:1px solid #335b79; border-radius:12px; }
            QFrame#AnalysisPanel { background:rgba(13,27,54,224); border:1px solid #335b79; border-radius:12px; }
            QFrame#Drawer { background:rgba(12,24,50,225); border:1px solid #294263; border-radius:10px; }
            QFrame#GlassPanel { background:rgba(15,29,55,212); border:1px solid rgba(82,161,219,80); border-radius:14px; }
            QProgressBar { height:8px; border:none; border-radius:4px; background:#18253b; }
            QProgressBar::chunk { background:#54d9e6; border-radius:4px; }
            QSpinBox, QDoubleSpinBox { background:#13243f; border:1px solid #2c5674; border-radius:7px;
                 color:#eafaff; padding:5px 7px; min-height:22px; }
            QCheckBox { color:#acd4ed; padding:4px; }
            QTabWidget::pane { background:#091329; border:1px solid #263f5f; }
            QTabBar::tab { background:#12213e; padding:7px 16px; color:#9fc6de; border:1px solid #273b58; }
            QTabBar::tab:selected { background:#19405b; color:#76f4ff; }
            QScrollArea { background:transparent; border:0; }
            QScrollArea > QWidget > QWidget { background:transparent; }
            QPushButton { border:1px solid #294764; background:#122441; padding:10px 15px; border-radius:8px; color:#d8efff; }
            QPushButton:hover { background:#19355d; border-color:#4adcec; }
            QPushButton:pressed { background:#1e4870; }
            QPushButton:disabled { color:#586e88; border-color:#22304a; background:#10172b; }
            QPushButton#Primary { background:#147baa; color:#fff; border:1px solid #43dafa; font-weight:700; }
            QPushButton#Primary:hover { background:#199ec5; }
            QPushButton#Nav { text-align:left; background:transparent; border:1px solid transparent; padding:13px 16px; border-radius:9px; color:#a8c4e1; }
            QPushButton#Nav:hover { color:#f1fcff; background:#112a49; border-color:#224564; }
            QPushButton#Nav[active="true"] { background:#123e59; color:#55efff; border-color:#317d94; font-weight:700; }
            QComboBox { padding:8px 10px; color:#ecf8ff; background:#12243f; border:1px solid #2c5674; border-radius:8px; min-height:20px; }
            QComboBox::drop-down { border:0; width:21px; }
            QComboBox QAbstractItemView { background:#101d36; color:#e7f7ff; selection-background-color:#24617f; border:1px solid #32607a; }
            QTableView { background:#0a1328; alternate-background-color:#101e37; border:0; gridline-color:#263c59; selection-background-color:#235975; color:#d5eaff; }
            QHeaderView::section { background:#142441; color:#a5e8ff; padding:7px 9px; border:0; border-bottom:1px solid #315672; border-right:1px solid #253e59; font-weight:600; }
            QTableCornerButton::section { background:#142441; border:0; }
            QProgressBar { height:8px; border:none; border-radius:4px; background:#1b2a43; text-align:center; }
            QProgressBar::chunk { background:#54d9e6; border-radius:4px; }
            QSplitter::handle { background:#192f48; height:6px; }
            QStatusBar { border-top:1px solid #223956; color:#86cddf; }
            QMenuBar { background:#080e1d; }
            QMenuBar::item:selected { background:#173454; }
            QMenu { background:#101c36; border:1px solid #345675; }
            QMenu::item:selected { background:#275a7c; }
        )QSS");
    }

    QFrame *metric(const QString &name,QLabel *&number) {
        QFrame *f=makePanel("StatCard");
        auto *l=new QVBoxLayout(f); l->setContentsMargins(13,8,13,8);l->setSpacing(2);
        l->addWidget(makeLabel(name,"StatName"));
        number=makeLabel("—","StatValue");
        l->addWidget(number);
        return f;
    }
    QPushButton *nav(const QString &name) {
        auto *b=new QPushButton(name); b->setObjectName("Nav"); b->setCursor(Qt::PointingHandCursor);
        b->setProperty("active",false);
        navButtons_.append(b);
        return b;
    }
    void highlight(QPushButton *active) {
        for(auto *button:navButtons_) {
            button->setProperty("active",button==active);
            button->style()->unpolish(button);button->style()->polish(button);
            button->update();
        }
    }
    void createUi() {
        QAction *openAct=new QAction("Open measurement",this);openAct->setShortcut(QKeySequence::Open);
        connect(openAct,&QAction::triggered,this,[this]{chooseFile();});
        menuBar()->addAction(openAct);
        QAction *exportAct=new QAction("Export plot CSVs",this);
        connect(exportAct,&QAction::triggered,this,[this]{exportAll();});
        menuBar()->addAction(exportAct);
        QAction *txtAct=new QAction("Export clean TXT files",this);
        txtAct->setShortcut(QKeySequence(Qt::CTRL | Qt::SHIFT | Qt::Key_T));
        connect(txtAct,&QAction::triggered,this,[this]{exportText();});
        menuBar()->addAction(txtAct);
        QAction *overlayAct=new QAction("Open overlay workspace",this);
        overlayAct->setShortcut(QKeySequence(Qt::CTRL | Qt::SHIFT | Qt::Key_O));
        connect(overlayAct,&QAction::triggered,this,[this]{openOverlay();});
        menuBar()->addAction(overlayAct);

        auto *main=new QWidget;
        auto *root=new QHBoxLayout(main);root->setContentsMargins(0,0,0,0);root->setSpacing(0);
        auto *sidebar=makePanel("Sidebar");sidebar->setFixedWidth(202);
        auto *side=new QVBoxLayout(sidebar);side->setContentsMargins(12,17,12,12);side->setSpacing(7);
        side->addWidget(makeLabel("◈  PYTRO-NOVA","Brand"));
        side->addWidget(makeLabel("ELECTROCHEMISTRY  /  V3.9","Version"));
        side->addSpacing(16);
        navDashboard_=nav("▣    Dashboard");
        navCV_=nav("⌁    CV analysis");
        navEIS_=nav("◌    EIS / Nyquist");
        navOther_=nav("⌁    Other techniques");
        navOverlay_=nav("◇    Plot overlap");
        navTable_=nav("▤    Data explorer");
        navExport_=nav("⇩    Export results");
        for(auto *b:navButtons_)side->addWidget(b);
        side->addStretch(1);
        auto *sideStatus=makePanel("Panel");
        auto *sideStatLayout=new QVBoxLayout(sideStatus);sideStatLayout->setContentsMargins(12,12,12,12);
        sideStatLayout->addWidget(makeLabel("BACKEND LINK","Eyebrow"));
        backendStatus_=makeLabel("Checking Python…","Muted");
        backendStatus_->setWordWrap(true);
        sideStatLayout->addWidget(backendStatus_);
        side->addWidget(sideStatus);
        root->addWidget(sidebar);

        auto *content=new QWidget;
        auto *layout=new QVBoxLayout(content);layout->setContentsMargins(13,12,13,8);layout->setSpacing(8);
        root->addWidget(content,1);
        auto *header=makePanel("Header");
        auto *hdr=new QHBoxLayout(header);hdr->setContentsMargins(15,9,15,9);
        auto *headText=new QVBoxLayout;
        headText->addWidget(makeLabel("METROHM AUTOLAB  /  DATA SYSTEM","Eyebrow"));
        headText->addWidget(makeLabel("ELECTROCHEMISTRY  /  AURORA ENGINE","Title"));
        headline_=makeLabel("Native Qt dashboard  •  Python scientific engine  •  Afruz-EIS integration","Muted");
        headText->addWidget(headline_);
        hdr->addLayout(headText);hdr->addStretch(1);hdr->addWidget(new NeonOrbit);
        advancedButton_=new QPushButton("◈   ADVANCED LAB");advancedButton_->setObjectName("Primary");
        advancedButton_->setToolTip("Open Advanced Lab including Afruz-EIS auto circuit selection, smoothing, and fit diagnostics");
        advancedButton_->setEnabled(false);hdr->addWidget(advancedButton_);
        openButton_=new QPushButton("+   OPEN NOX / CSV");openButton_->setObjectName("Primary");
        openButton_->setMinimumWidth(168);hdr->addWidget(openButton_);
        setSoftGlow(header,QColor(48,160,225,70),28);
        layout->addWidget(header);

        auto *stats=new QHBoxLayout;stats->setSpacing(11);
        stats->addWidget(metric("MEASUREMENT SETS",datasetsValue_));
        stats->addWidget(metric("TOTAL DATA POINTS",pointsValue_));
        stats->addWidget(metric("CV RECORDS",cvValue_));
        stats->addWidget(metric("EIS SPECTRA",eisValue_));
        stats->addWidget(metric("OTHER TECHNIQUES",otherValue_));
        layout->addLayout(stats);

        auto *toolbar=makePanel("Panel");
        auto *tools=new QHBoxLayout(toolbar);tools->setContentsMargins(9,7,9,7);tools->setSpacing(7);
        tools->addWidget(makeLabel("DATASET","Eyebrow"));
        datasetBox_=new QComboBox;datasetBox_->setMinimumWidth(153);tools->addWidget(datasetBox_,2);
        tools->addWidget(makeLabel("X AXIS","Eyebrow"));
        xBox_=new QComboBox;tools->addWidget(xBox_,3);
        tools->addWidget(makeLabel("Y AXIS","Eyebrow"));
        yBox_=new QComboBox;tools->addWidget(yBox_,3);
        tools->addWidget(makeLabel("CYCLE VIEW","Eyebrow"));
        cycleBox_=new QComboBox;cycleBox_->setMinimumWidth(205);
        cycleBox_->setToolTip("All cycles are shown together by default; select one to inspect it.");
        cycleBox_->addItem("All cycles",0);
        tools->addWidget(cycleBox_,1);
        resetButton_=new QPushButton("Reset zoom");tools->addWidget(resetButton_);
        layout->addWidget(toolbar);

        // The graph owns the workspace. Data is an optional bottom drawer,
        // so the plot stays large even on 1366x768 Windows laptops.
        auto *workspace = new QSplitter(Qt::Horizontal);
        workspace->setChildrenCollapsible(false);
        auto *plotPanel=makePanel("PlotPanel");
        setSoftGlow(plotPanel,QColor(67,168,220,52),18);
        auto *plotLayout=new QVBoxLayout(plotPanel);
        plotLayout->setContentsMargins(9,9,9,9);plotLayout->setSpacing(5);
        auto *topPlot=new QHBoxLayout;
        topPlot->addWidget(makeLabel("◈  INTERACTIVE SIGNAL VISUALISATION","Section"));
        topPlot->addStretch(1);
        inspectorToggle_=new QPushButton("Hide analysis panel");
        inspectorToggle_->setToolTip("Use entire window width for the signal plot");
        topPlot->addWidget(inspectorToggle_);
        topPlot->addWidget(makeLabel("SCROLL TO ZOOM  •  DOUBLE-CLICK TO RESET","Muted"));
        overlayButton_=new QPushButton("◇  SEND TO OVERLAY");
        overlayButton_->setToolTip("Add this CV scan or EIS spectrum to a separate comparison window. Right-click the plot for EIS plot modes.");
        topPlot->insertWidget(1,overlayButton_);
        plotLayout->addLayout(topPlot);
        plot_=new PlotView;
        plot_->setContextMenuPolicy(Qt::CustomContextMenu);
        plot_->setToolTip("Right-click to send a technique-compatible dataset to an overlay. Zoom: wheel. Reset: double click.");
        plot_->setMinimumHeight(270);
        plotLayout->addWidget(plot_,1);
        workspace->addWidget(plotPanel);

        inspector_=makePanel("AnalysisPanel");
        inspector_->setMinimumWidth(255);
        inspector_->setMaximumWidth(320);
        auto *right=new QVBoxLayout(inspector_);
        right->setContentsMargins(12,12,12,12);right->setSpacing(8);
        right->addWidget(makeLabel("SIGNAL ANALYSIS","Section"));
        kindLabel_=makeLabel("Open a file to analyze","AccentNumber");
        kindLabel_->setWordWrap(true);right->addWidget(kindLabel_);
        currentSummary_=makeLabel("Automated peak search (CV) and impedance metrics (EIS)","Muted");
        currentSummary_->setWordWrap(true);right->addWidget(currentSummary_);
        showPeaksBox_=new QCheckBox("Show peak markers on plot");
        showPeaksBox_->setChecked(true);right->addWidget(showPeaksBox_);
        auto *parameterGrid=new QGridLayout;parameterGrid->setHorizontalSpacing(6);
        parameterGrid->addWidget(makeLabel("Smoothing","Muted"),0,0);
        windowSpin_=new QSpinBox;windowSpin_->setRange(5,51);windowSpin_->setSingleStep(2);windowSpin_->setValue(9);
        parameterGrid->addWidget(windowSpin_,0,1);
        parameterGrid->addWidget(makeLabel("Prominence (µA)","Muted"),1,0);
        prominenceSpin_=new QDoubleSpinBox;prominenceSpin_->setDecimals(2);prominenceSpin_->setRange(0,100000);prominenceSpin_->setValue(0);
        prominenceSpin_->setToolTip("0 means automatic threshold: 7% of current range");
        prominenceSpin_->setSuffix(" µA");parameterGrid->addWidget(prominenceSpin_,1,1);
        parameterGrid->addWidget(makeLabel("Min. spacing","Muted"),2,0);
        distanceSpin_=new QSpinBox;distanceSpin_->setRange(1,10000);distanceSpin_->setValue(6);
        parameterGrid->addWidget(distanceSpin_,2,1);
        right->addLayout(parameterGrid);
        analyzeButton_=new QPushButton("ANALYZE SIGNAL");analyzeButton_->setObjectName("Primary");
        right->addWidget(analyzeButton_);
        peaksBrief_=makeLabel("Peaks: —","AccentNumber");right->addWidget(peaksBrief_);
        metricsArea_=new QScrollArea;metricsArea_->setWidgetResizable(true);
        auto *metricsContainer=new QWidget;
        metricsLayout_=new QVBoxLayout(metricsContainer);
        metricsLayout_->setContentsMargins(2,3,2,3);metricsLayout_->setSpacing(8);
        metricsLayout_->addWidget(makeLabel("Open a file to see numerical results.","Muted"));
        metricsLayout_->addStretch(1);
        metricsArea_->setWidget(metricsContainer);
        right->addWidget(metricsArea_,1);
        warningsLabel_=makeLabel("Peak estimates should be checked against original NOVA traces.","Muted");
        warningsLabel_->setWordWrap(true);right->addWidget(warningsLabel_);
        workspace->addWidget(inspector_);
        workspace->setStretchFactor(0,8);
        workspace->setStretchFactor(1,2);
        workspace->setSizes({1020,284});
        layout->addWidget(workspace,1);

        auto *drawerBar=makePanel("Drawer");
        auto *drawerBarLayout=new QHBoxLayout(drawerBar);
        drawerBarLayout->setContentsMargins(10,4,10,4);
        drawerToggle_=new QPushButton("▸  SHOW DATA & PEAK RESULTS");
        drawerToggle_->setToolTip("Expand the measurements / peak table; hide to maximize the plot height");
        drawerBarLayout->addWidget(drawerToggle_);
        drawerBarLayout->addStretch(1);
        exportButton_=new QPushButton("Export selected plot CSVs");drawerBarLayout->addWidget(exportButton_);
        exportAllButton_=new QPushButton("◈  Export plot CSVs");
        exportAllButton_->setObjectName("Primary");
        exportAllButton_->setToolTip("Export only CV current-vs-voltage and EIS Nyquist, Bode magnitude and phase plot CSVs");
        drawerBarLayout->addWidget(exportAllButton_);
        exportTextButton_=new QPushButton("Export clean TXT");
        exportTextButton_->setToolTip("Full measurement columns + separate XY plots + recorded GCD/OCP segments as tab-separated text");
        drawerBarLayout->addWidget(exportTextButton_);
        exportPeaksButton_=new QPushButton("Export peaks CSV");drawerBarLayout->addWidget(exportPeaksButton_);
        savePlotButton_=new QPushButton("Save plot PNG");drawerBarLayout->addWidget(savePlotButton_);
        layout->addWidget(drawerBar);

        dataDrawer_=makePanel("Drawer");
        auto *drawerLayout=new QVBoxLayout(dataDrawer_);
        drawerLayout->setContentsMargins(7,7,7,7);
        dataTabs_=new QTabWidget;
        table_=new QTableView;
        model_=new DataTableModel(this);
        table_->setModel(model_);
        table_->setAlternatingRowColors(true);
        table_->setSelectionBehavior(QAbstractItemView::SelectRows);
        table_->setSelectionMode(QAbstractItemView::SingleSelection);
        table_->setSortingEnabled(false);
        table_->verticalHeader()->setDefaultSectionSize(26);
        table_->horizontalHeader()->setMinimumSectionSize(90);
        table_->horizontalHeader()->setStretchLastSection(true);
        peaksTable_=new QTableWidget(0,7);
        peaksTable_->setHorizontalHeaderLabels({"Peak", "Sweep", "Potential (V)", "Current (µA)","Prominence (µA)","Width½ (mV)","Data row"});
        peaksTable_->setEditTriggers(QAbstractItemView::NoEditTriggers);
        peaksTable_->setSelectionBehavior(QAbstractItemView::SelectRows);
        peaksTable_->setAlternatingRowColors(true);
        peaksTable_->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
        peaksTable_->verticalHeader()->setDefaultSectionSize(26);
        metricTable_=new QTableWidget(0,3);
        metricTable_->setHorizontalHeaderLabels({"Metric", "Value", "Unit"});
        metricTable_->setEditTriggers(QAbstractItemView::NoEditTriggers);
        metricTable_->setAlternatingRowColors(true);
        metricTable_->horizontalHeader()->setSectionResizeMode(0,QHeaderView::Stretch);
        metricTable_->horizontalHeader()->setSectionResizeMode(1,QHeaderView::ResizeToContents);
        metricTable_->horizontalHeader()->setSectionResizeMode(2,QHeaderView::ResizeToContents);
        dataTabs_->addTab(peaksTable_,"Detected Peaks");
        dataTabs_->addTab(metricTable_,"Analysis Metrics");
        dataTabs_->addTab(table_,"Raw Measurements");
        drawerLayout->addWidget(dataTabs_);
        dataDrawer_->setFixedHeight(224);
        dataDrawer_->hide();
        layout->addWidget(dataDrawer_);

        setCentralWidget(main);
        statusBar()->showMessage("READY  •  Select a .nox measurement file",0);
        connect(openButton_,&QPushButton::clicked,this,[this]{chooseFile();});
        connect(advancedButton_,&QPushButton::clicked,this,[this]{
            if(filePath_.isEmpty()||datasets_.isEmpty()||busy_)return;
            const int currentIndex=datasetBox_->currentIndex();
            const QString preferred=(currentIndex>=0 && currentIndex<datasets_.size())
                ? datasets_[currentIndex].toObject().value("name").toString() : QString();
            auto *dialog=createAdvancedLabDialog(filePath_,datasets_,preferred,pythonExecutable(),
                    QFileInfo(backendScript()).dir().filePath("advanced.py"),this);
            dialog->show();
        });
        connect(resetButton_,&QPushButton::clicked,plot_,&PlotView::resetZoom);
        connect(overlayButton_,&QPushButton::clicked,this,[this]{
            if(currentKind_=="CV")sendToOverlay(OverlayMode::CV);
            else if(currentKind_=="EIS")sendToOverlay(OverlayMode::Nyquist);
            else if(currentKind_=="GCD")sendToOverlay(OverlayMode::GCD);
            else if(currentKind_=="LSV")sendToOverlay(OverlayMode::LSV);
            else if(currentKind_=="DPV")sendToOverlay(OverlayMode::DPV);
            else if(currentKind_=="SWV")sendToOverlay(OverlayMode::SWV);
            else if(currentKind_=="CA")sendToOverlay(OverlayMode::CA);
            else if(currentKind_=="CP")sendToOverlay(OverlayMode::CP);
            else if(currentKind_=="OCP")sendToOverlay(OverlayMode::OCP);
            else openOverlay();
        });
        connect(plot_,&QWidget::customContextMenuRequested,this,[this](const QPoint &pos){
            QMenu menu(this);
            if(currentKind_=="CV") {
                auto *send=menu.addAction("◇  Send CV current vs voltage to Overlay");
                connect(send,&QAction::triggered,this,[this]{sendToOverlay(OverlayMode::CV);});
            } else if(currentKind_=="EIS") {
                auto *nyquist=menu.addAction("◇  Send EIS Nyquist to Overlay");
                auto *magnitude=menu.addAction("◇  Send EIS Bode magnitude to Overlay");
                auto *phase=menu.addAction("◇  Send EIS Bode phase to Overlay");
                connect(nyquist,&QAction::triggered,this,[this]{sendToOverlay(OverlayMode::Nyquist);});
                connect(magnitude,&QAction::triggered,this,[this]{sendToOverlay(OverlayMode::BodeMagnitude);});
                connect(phase,&QAction::triggered,this,[this]{sendToOverlay(OverlayMode::BodePhase);});
            } else if(currentKind_=="GCD"||currentKind_=="LSV"||currentKind_=="DPV"||
                      currentKind_=="SWV"||currentKind_=="CA"||currentKind_=="CP"||currentKind_=="OCP") {
                const QMap<QString,OverlayMode> modes={{"GCD",OverlayMode::GCD},{"LSV",OverlayMode::LSV},
                    {"DPV",OverlayMode::DPV},{"SWV",OverlayMode::SWV},{"CA",OverlayMode::CA},
                    {"CP",OverlayMode::CP},{"OCP",OverlayMode::OCP}};
                auto *send=menu.addAction("◇  Send "+currentKind_+" to Overlay");
                const OverlayMode mode=modes.value(currentKind_);
                connect(send,&QAction::triggered,this,[this,mode]{sendToOverlay(mode);});
            } else {
                auto *msg=menu.addAction("Open a supported dataset first");msg->setEnabled(false);
            }
            menu.addSeparator();
            auto *view=menu.addAction("Open Overlay Workspace");
            connect(view,&QAction::triggered,this,[this]{openOverlay();});
            menu.exec(plot_->mapToGlobal(pos));
        });
        connect(datasetBox_,QOverload<int>::of(&QComboBox::currentIndexChanged),this,[this](int i){selectDataset(i);});
        connect(xBox_,QOverload<int>::of(&QComboBox::currentIndexChanged),this,[this](int){plotSelection();});
        connect(yBox_,QOverload<int>::of(&QComboBox::currentIndexChanged),this,[this](int){plotSelection();});
        connect(cycleBox_,QOverload<int>::of(&QComboBox::currentIndexChanged),this,[this](int){
            applyCycleSelection();
        });
        connect(exportButton_,&QPushButton::clicked,this,[this]{exportCurrent();});
        connect(exportAllButton_,&QPushButton::clicked,this,[this]{exportAll();});
        connect(exportTextButton_,&QPushButton::clicked,this,[this]{exportText();});
        connect(savePlotButton_,&QPushButton::clicked,this,[this]{savePlot();});
        connect(inspectorToggle_,&QPushButton::clicked,this,[this]{
            const bool hide=inspector_->isVisible();
            inspector_->setVisible(!hide);
            inspectorToggle_->setText(hide?"Show analysis panel":"Hide analysis panel");
        });
        connect(drawerToggle_,&QPushButton::clicked,this,[this]{setDrawerVisible(!dataDrawer_->isVisible());});
        connect(showPeaksBox_,&QCheckBox::toggled,this,[this](bool enabled){refreshMarkers();});
        connect(analyzeButton_,&QPushButton::clicked,this,[this]{analyzeSelected();});
        connect(exportPeaksButton_,&QPushButton::clicked,this,[this]{exportPeaks();});
        connect(peaksTable_,&QTableWidget::cellClicked,this,[this](int row,int){
            if(row<0||row>=peakData_.size())return;
            const int dataRow=peakData_[row].toObject().value("row").toInt();
            plot_->focusRow(dataRow);
            if(dataRow>0 && dataRow<=model_->rowCount())table_->selectRow(dataRow-1);
        });
        connect(navDashboard_,&QPushButton::clicked,this,[this]{highlight(navDashboard_);if(!datasets_.isEmpty()) datasetBox_->setCurrentIndex(0);});
        connect(navCV_,&QPushButton::clicked,this,[this]{switchToKind("CV",navCV_);});
        connect(navEIS_,&QPushButton::clicked,this,[this]{switchToKind("EIS",navEIS_);});
        connect(navOther_,&QPushButton::clicked,this,[this]{
            QStringList names;QVector<int> indices;
            for(int i=0;i<datasets_.size();++i) {
                const auto ds=datasets_[i].toObject();
                const QString kind=ds.value("kind").toString();
                if(kind!="CV"&&kind!="EIS") {
                    names<<kind+"  /  "+ds.value("name").toString(); indices<<i;
                }
            }
            if(names.isEmpty()) {QMessageBox::information(this,"No other techniques",
                "Open a GCD, LSV, DPV, SWV, CA, CP or OCP .nox file, or import a CSV/TSV export.");return;}
            bool ok=false;
            QString choice=QInputDialog::getItem(this,"Select technique dataset","Available datasets:",names,0,false,&ok);
            if(ok) {highlight(navOther_);datasetBox_->setCurrentIndex(indices[names.indexOf(choice)]);}
        });
        connect(navOverlay_,&QPushButton::clicked,this,[this]{highlight(navOverlay_);openOverlay();});
        connect(navTable_,&QPushButton::clicked,this,[this]{
            highlight(navTable_);setDrawerVisible(true);dataTabs_->setCurrentWidget(table_);table_->setFocus();
        });
        connect(navExport_,&QPushButton::clicked,this,[this]{exportAll();});
        highlight(navDashboard_);
    }
    void setBusy(bool b) {
        busy_=b;
        openButton_->setDisabled(b);
        exportButton_->setDisabled(b||datasets_.isEmpty());
        exportAllButton_->setDisabled(b||datasets_.isEmpty());
        exportTextButton_->setDisabled(b||datasets_.isEmpty());
        savePlotButton_->setDisabled(b||datasets_.isEmpty());
        overlayButton_->setDisabled(b||datasets_.isEmpty());
        resetButton_->setDisabled(b||datasets_.isEmpty());
        datasetBox_->setDisabled(b||datasets_.isEmpty());
        xBox_->setDisabled(b||datasets_.isEmpty());
        yBox_->setDisabled(b||datasets_.isEmpty());
        for(auto *button:navButtons_) button->setDisabled(b);
        analyzeButton_->setDisabled(b||datasets_.isEmpty());
        advancedButton_->setDisabled(b||datasets_.isEmpty()||filePath_.isEmpty()||(currentKind_!="CV"&&currentKind_!="EIS")||!fileTechnique_.isEmpty());
        exportPeaksButton_->setDisabled(b||datasets_.isEmpty()||(currentKind_!="CV"&&currentKind_!="LSV"&&currentKind_!="DPV"&&currentKind_!="SWV"));
        windowSpin_->setDisabled(b||datasets_.isEmpty()||(currentKind_!="CV"&&currentKind_!="LSV"&&currentKind_!="DPV"&&currentKind_!="SWV"));
        prominenceSpin_->setDisabled(b||datasets_.isEmpty()||(currentKind_!="CV"&&currentKind_!="LSV"&&currentKind_!="DPV"&&currentKind_!="SWV"));
        distanceSpin_->setDisabled(b||datasets_.isEmpty()||(currentKind_!="CV"&&currentKind_!="LSV"&&currentKind_!="DPV"&&currentKind_!="SWV"));
    }
    QString backendScript() const {
        QString override=qEnvironmentVariable("PYTRO_NOVA_BACKEND_SCRIPT");
        if(override.isEmpty()) override=qEnvironmentVariable("NOVA_BACKEND_SCRIPT");
        if(!override.isEmpty()&&QFileInfo::exists(override)) return QFileInfo(override).absoluteFilePath();
        const QStringList starts={QCoreApplication::applicationDirPath(),QDir::currentPath()};
        for(const QString &start:starts) {
            QDir directory(start);
            for(int i=0;i<7;i++) {
                const QString candidate=directory.filePath("backend/bridge.py");
                if(QFileInfo::exists(candidate)) return QFileInfo(candidate).absoluteFilePath();
                // A Linux CMake install uses <prefix>/bin/PytroNOVA and
                // <prefix>/share/pytro-nova/backend/bridge.py.
                const QString installed=directory.filePath("../share/pytro-nova/backend/bridge.py");
                if(QFileInfo::exists(installed)) return QFileInfo(installed).absoluteFilePath();
                if(!directory.cdUp()) break;
            }
        }
        return {};
    }
    QString pythonExecutable() const {
        QString choice=qEnvironmentVariable("PYTRO_NOVA_PYTHON");
        if(choice.isEmpty()) choice=qEnvironmentVariable("NOVA_PYTHON");
        if(!choice.isEmpty()) return choice;
#ifdef Q_OS_WIN
        // A packaged Windows release includes its own isolated Python runtime.
        // Prefer it over py.exe and globally installed interpreters so the
        // decoder and scientific dependencies work on a clean Windows PC.
        const QDir appDir(QCoreApplication::applicationDirPath());
        const QString packaged=appDir.filePath("python/python.exe");
        if(QFileInfo::exists(packaged)) return QFileInfo(packaged).absoluteFilePath();
        const QStringList candidates={"py","python","python3"};
#else
        const QStringList candidates={"python3","python"};
#endif
        for(const auto &name:candidates) {
            choice=QStandardPaths::findExecutable(name);
            if(!choice.isEmpty()) return choice;
        }
        return {};
    }
    void runBackend(const QStringList &args,Operation op,const QString &fileOrDir) {
        if(busy_) return;
        const QString script=backendScript(), python=pythonExecutable();
        if(script.isEmpty()) {
            QMessageBox::critical(this,"Backend missing","Cannot find backend/bridge.py. Run from the extracted project folder, keeping backend/ alongside app/.");
            return;
        }
        if(python.isEmpty()) {
            QMessageBox::critical(this,"Python missing","Python 3 was not found. Install Python and add it to PATH, or set NOVA_PYTHON to the interpreter executable.");
            return;
        }
        if(process_) { process_->deleteLater(); process_=nullptr; }
        operation_=op;
        pendingPath_=fileOrDir;
        process_=new QProcess(this);
        process_->setProgram(python);
        QStringList argv;
#ifdef Q_OS_WIN
        if(QFileInfo(python).completeBaseName().compare("py",Qt::CaseInsensitive)==0) argv<<"-3";
#endif
        argv<<script;
        argv<<args;
        process_->setArguments(argv);
        setBusy(true);
        backendStatus_->setText("● Python backend active");
        statusBar()->showMessage(op==Operation::Read ? "Reading NOVA measurement file…" :
                                 ((op==Operation::Analyze||op==Operation::ExportPeaks)?"Analyzing signal with Python…":"Exporting data with Python…"));
        QProcess *active=process_;
        connect(active,QOverload<int,QProcess::ExitStatus>::of(&QProcess::finished),this,[this,active](int code,QProcess::ExitStatus state){
            if(active!=process_) return;
            const QByteArray output=active->readAllStandardOutput();
            const QString errors=QString::fromUtf8(active->readAllStandardError());
            active->deleteLater(); process_=nullptr;
            setBusy(false);
            backendStatus_->setText("● Python backend ready");
            if(state!=QProcess::NormalExit || code!=0) {
                QMessageBox::critical(this,"Python backend error",errors.isEmpty()?"Unable to read or export the file.":errors.trimmed());
                statusBar()->showMessage("Operation failed",10000);
                return;
            }
            QJsonParseError problem;
            const QJsonDocument json=QJsonDocument::fromJson(output,&problem);
            if(problem.error!=QJsonParseError::NoError||!json.isObject()) {
                QMessageBox::critical(this,"Backend protocol error","Expected JSON from Python: "+problem.errorString());
                return;
            }
            if(operation_==Operation::Read) loadDocument(json.object());
            else if(operation_==Operation::Analyze || operation_==Operation::ExportPeaks) {
                loadAnalysis(json.object());
                if(operation_==Operation::ExportPeaks) statusBar()->showMessage("Peak CSV exported to: "+pendingPath_,12000);
            }
            else if(operation_==Operation::ExportText) {
                const QJsonObject result=json.object();
                const QString folder=result.value("folder").toString();
                const int count=result.value("datasets").toInt();
                const int files=result.value("text_files").toInt();
                const int points=result.value("data_points").toInt();
                statusBar()->showMessage(QString("Exported %1 datasets / %2 TXT files → %3")
                    .arg(count).arg(files).arg(folder),20000);
                QMessageBox::information(this,"Clean TXT export complete",
                    QString("%1\n\n%2 datasets | %3 original data points | %4 TXT files\n\n"
                            "Folders: full_data, plot_data, recorded_segments (when available).\n"
                            "Data are tab-separated with units and original numerical precision.\n"
                            "See README.txt and manifest.json for signal provenance and warnings.\n"
                            "The input file was not modified.")
                    .arg(folder).arg(count).arg(points).arg(files));
            }
            else if(operation_==Operation::ExportAll) {
                const QJsonObject result=json.object();
                const QString folder=result.value("folder").toString();
                const int count=result.value("datasets").toInt();
                const int csvFiles=result.value("csv_files").toInt();
                const int points=result.value("data_points").toInt();
                statusBar()->showMessage(QString("Exported %1 datasets / %2 CSV files → %3")
                     .arg(count).arg(csvFiles).arg(folder),20000);
                QMessageBox::information(this,"Plot CSV export complete",
                    QString("Original NOX file unchanged. Each CSV has two plot columns.\n\n"
                            "%1\n\n%2 datasets | %3 data points | %4 CSV files\n\n"
                            "Each CSV contains exactly two plot-ready numeric columns.")
                    .arg(folder).arg(count).arg(points).arg(csvFiles));
            }
            else {
                const int count=json.object().value("datasets").toInt();
                statusBar()->showMessage(QString("Exported %1 dataset(s) to CSV").arg(count),12000);
            }
        });
        connect(active,&QProcess::errorOccurred,this,[this,active](QProcess::ProcessError err){
            if(active!=process_ || err!=QProcess::FailedToStart) return;
            active->deleteLater();process_=nullptr;setBusy(false);
            backendStatus_->setText("● Backend unavailable");
            QMessageBox::critical(this,"Python launch failed","Could not start the Python interpreter. Check NOVA_PYTHON or system PATH.");
        });
        active->start();
    }
    void chooseFile() {
        const QString path=QFileDialog::getOpenFileName(this,"Open NOVA or technique CSV",QDir::homePath(),"Metrohm NOVA (*.nox);;CSV/TSV (*.csv *.tsv *.txt);;All files (*.*)");
        if(!path.isEmpty()) openFile(path);
    }
    void loadDocument(const QJsonObject &doc) {
        metadata_=doc.value("metadata").toObject();
        datasets_=doc.value("datasets").toArray();
        filePath_=pendingPath_;
        int cvCount=0,eisCount=0,total=0;
        for(const auto &item:datasets_) {
            const QJsonObject ds=item.toObject();
            const QString kind=ds.value("kind").toString();
            if(kind=="CV") ++cvCount;
            if(kind=="EIS") ++eisCount;
            total+=ds.value("point_count").toInt();
        }
        totalPoints_=total;
        datasetsValue_->setText(QString::number(datasets_.size()));
        pointsValue_->setText(QString::number(total));
        cvValue_->setText(QString::number(cvCount));
        eisValue_->setText(QString::number(eisCount));
        otherValue_->setText(QString::number(datasets_.size()-cvCount-eisCount));
        headline_->setText(QString("FILE: %1  •  %2  •  %3")
                           .arg(metadata_.value("file").toString(),
                                metadata_.value("procedure").toString(),
                                metadata_.value("instrument").toString()));
        {QSignalBlocker blocker(datasetBox_);
            datasetBox_->clear();
            for(const auto &value:datasets_) {
                const auto ds=value.toObject();
                datasetBox_->addItem(ds.value("name").toString()+"  •  "+QString::number(ds.value("point_count").toInt())+" samples");
            }
            if(!datasets_.isEmpty()) datasetBox_->setCurrentIndex(0);
        }
        setBusy(false);
        if(!datasets_.isEmpty()) selectDataset(0);
        else {
            model_->setDataset({});plot_->setDataset({},-1,-1);
            kindLabel_->setText("No datasets"); peakData_=QJsonArray(); updatePeakTable();
            QMessageBox::information(this,"No measurements","No compatible recorded signals were identified. This file may use an unrecognized NOVA technique or serialization layout. Please provide it for decoder support.");
        }
        statusBar()->showMessage(QString("LOADED  •  %1 datasets  •  %2 total data points  •  %3")
                                 .arg(datasets_.size()).arg(total).arg(filePath_));
    }
    void selectDataset(int index) {
        if(index<0||index>=datasets_.size()) return;
        const QJsonObject ds=datasets_[index].toObject();
        model_->setDataset(ds);
        const QJsonArray cols=ds.value("columns").toArray();
        {QSignalBlocker xBlock(xBox_),yBlock(yBox_);
            xBox_->clear();yBox_->clear();
            for(const auto &v:cols) {
                const auto col=v.toObject();
                xBox_->addItem(col.value("label").toString(),col.value("key").toString());
                yBox_->addItem(col.value("label").toString(),col.value("key").toString());
            }
            int xi=xBox_->findData(ds.value("default_x").toString());
            int yi=yBox_->findData(ds.value("default_y").toString());
            xBox_->setCurrentIndex(xi>=0?xi:0);
            yBox_->setCurrentIndex(yi>=0?yi:std::min(1, static_cast<int>(cols.size()) - 1));
        }
        table_->resizeColumnsToContents();
        currentKind_=ds.value("kind").toString();
        // Show comparable GCD cycles by default. NOVA may contain tests with
        // radically different durations/voltage ceilings; overlaying all 23
        // on one x scale makes the shortest unreadable. Keep All accessible.
        {QSignalBlocker blocker(cycleBox_);
            cycleBox_->clear();
            cycleBox_->addItem("All cycles / intervals",QVariantList{});
            int groupCol=-1;
            for(int j=0;j<cols.size();++j) {
                const QString key=cols[j].toObject().value("key").toString();
                if(key=="cycle" || (currentKind_=="CV" && key=="scan")) { groupCol=j;break; }
            }
            QSet<int> seen;
            if(groupCol>=0) {
                for(const auto &val:ds.value("values").toArray()) {
                    const auto row=val.toArray();
                    if(row.size()>groupCol && row[groupCol].isDouble()) {
                        const int group=row[groupCol].toInt(1);
                        if(group>0)seen.insert(group);
                    }
                }
            }
            // Back-end groupings are explicitly visual recommendations, not
            // measurements of current density or recorded NOVA cycle numbers.
            if(currentKind_=="GCD") {
                const auto groups=ds.value("comparable_cycle_groups").toArray();
                for(const auto &item:groups) {
                    const auto obj=item.toObject();
                    QVariantList data;
                    for(const auto &v:obj.value("cycles").toArray())data.append(v.toInt());
                    if(data.size()<2)continue;
                    cycleBox_->addItem(obj.value("label").toString(),data);
                }
            }
            if(cycleBox_->count()>1)cycleBox_->insertSeparator(cycleBox_->count());
            QList<int> sorted=seen.values();std::sort(sorted.begin(),sorted.end());
            for(int group:sorted) {
                QVariantList data;data.append(group);
                cycleBox_->addItem(currentKind_=="OCP"?
                    QString("Interval %1").arg(group):QString("Cycle %1").arg(group),data);
            }
            int preferred=0;
            if(currentKind_=="GCD" && sorted.size()>3) {
                const QVariantList recommended=[&]() {
                    QVariantList data;
                    for(const auto &v:ds.value("recommended_cycles").toArray())data.append(v.toInt());
                    return data;
                }();
                for(int n=1;n<cycleBox_->count();++n)
                    if(!recommended.isEmpty() && cycleBox_->itemData(n).toList()==recommended)
                        {preferred=n;break;}
                if(preferred==0 && sorted.size()>0)preferred=cycleBox_->findText("Cycle "+QString::number(sorted.first()));
            }
            cycleBox_->setCurrentIndex(std::max(0,preferred));
            cycleBox_->setEnabled(cycleBox_->count()>1);
            cycleBox_->setToolTip(currentKind_=="GCD"?
                "Recommended: overlay cycles of comparable elapsed time and voltage range. "
                "Choose All to show every inferred cycle. These are not instrument-confirmed cycle IDs.":
                "Choose All or one recorded interval/scan.");
        }
        kindLabel_->setText(currentKind_+"  /  "+ds.value("name").toString());
        QString provenance=ds.value("source").toString();
        QString classification;
        if(provenance=="nox-provisional") classification="  •  PROVISIONAL NOVA FIELD MAPPING";
        else if(provenance=="csv") classification="  •  IMPORTED CSV";
        else if(provenance=="nox-verified-signal-plots") classification="  •  VERIFIED NOVA SIGNAL AXES";
        if(ds.value("cycle_count").toInt()>1)
            classification+=QString("  •  %1 groups / %2 recorded segments")
                .arg(ds.value("cycle_count").toInt()).arg(ds.value("segment_count").toInt());
        currentSummary_->setText(QString("%1 measured points  •  %2 signal columns%3")
                                 .arg(ds.value("point_count").toInt()).arg(cols.size()).arg(classification));
        peakData_=QJsonArray();analysis_=QJsonObject();
        metricTable_->setRowCount(0);
        peaksBrief_->setText("Scanning signal…");
        plotSelection();
        updatePeakTable();
        setBusy(false);
        analyzeSelected();
    }
    void applyCycleSelection() {
        QSet<int> selected;
        const QVariantList choices=cycleBox_->currentData().toList();
        for(const QVariant &item:choices) if(item.toInt()>0)selected.insert(item.toInt());
        plot_->setVisibleCycles(selected);
    }
    void plotSelection() {
        const int i=datasetBox_->currentIndex();
        if(i<0||i>=datasets_.size())return;
        const auto ds=datasets_[i].toObject();
        const int x=xBox_->currentIndex(),y=yBox_->currentIndex();
        plot_->setDataset(ds,x,y);
        applyCycleSelection();
        const auto rows=ds.value("values").toArray();
        double lo=std::numeric_limits<double>::infinity(),hi=-lo;
        for(const auto &r:rows) {
            QJsonArray row=r.toArray();
            if(y>=0&&y<row.size()&&row[y].isDouble()) {
                const double value=row[y].toDouble();
                lo=std::min(lo,value);hi=std::max(hi,value);
            }
        }
        refreshMarkers();
    }
    void switchToKind(const QString &kind,QPushButton *button) {
        for(int i=0;i<datasets_.size();i++) {
            if(datasets_[i].toObject().value("kind").toString()==kind) {
                highlight(button);datasetBox_->setCurrentIndex(i);return;
            }
        }
        QMessageBox::information(this,"Dataset not available","No "+kind+" dataset is loaded. Open a compatible .nox file.");
    }
    void setDrawerVisible(bool shown) {
        dataDrawer_->setVisible(shown);
        drawerToggle_->setText(shown?"▾  HIDE DATA & PEAK RESULTS":"▸  SHOW DATA & PEAK RESULTS");
    }
    QStringList analysisArgs() const {
        const int i=datasetBox_->currentIndex();
        if(i<0||i>=datasets_.size())return {};
        QStringList args={"analyze",filePath_,"--dataset",datasets_[i].toObject().value("name").toString()};
        if(currentKind_=="CV"||currentKind_=="LSV"||currentKind_=="DPV"||currentKind_=="SWV") {
            int w=windowSpin_->value(); if(w%2==0) ++w;
            args<<"--window"<<QString::number(w)
                <<"--prominence-ua"<<QString::number(prominenceSpin_->value(),'g',12)
                <<"--distance"<<QString::number(distanceSpin_->value());
        }
        if(!fileTechnique_.isEmpty())args<<"--technique"<<fileTechnique_;
        return args;
    }
    void analyzeSelected() {
        if(busy_||datasets_.isEmpty()||filePath_.isEmpty())return;
        runBackend(analysisArgs(),Operation::Analyze,filePath_);
    }
    void exportPeaks() {
        if(busy_||!(currentKind_=="CV"||currentKind_=="LSV"||currentKind_=="DPV"||currentKind_=="SWV")||datasets_.isEmpty())return;
        const QString filename=QFileDialog::getSaveFileName(this,"Export detected CV peaks",
                           QFileInfo(filePath_).completeBaseName()+"_peaks.csv","CSV (*.csv)");
        if(filename.isEmpty())return;
        QStringList args=analysisArgs();args<<"--peaks-csv"<<filename;
        runBackend(args,Operation::ExportPeaks,filename);
    }
    void refreshMarkers() {
        if(datasets_.isEmpty()||datasetBox_->currentIndex()<0)return;
        const bool cvAxis=((currentKind_=="CV"||currentKind_=="LSV"||currentKind_=="DPV"||currentKind_=="SWV") && xBox_->currentData().toString()=="potential_v" &&
                            yBox_->currentData().toString()=="current_a");
        plot_->setPeaks(cvAxis?peakData_:QJsonArray(),showPeaksBox_->isChecked());
    }
    void updatePeakTable() {
        peaksTable_->setRowCount(0);
        for(const auto &item:peakData_) {
            const QJsonObject peak=item.toObject();
            const int r=peaksTable_->rowCount();peaksTable_->insertRow(r);
            const QStringList cells={peak.value("type").toString(),peak.value("sweep").toString(),
                asNumber(peak.value("potential_v").toDouble(),7),
                asNumber(peak.value("current_a").toDouble()*1e6,7),
                asNumber(peak.value("prominence_a").toDouble()*1e6,7),
                peak.value("width_half_height_v").isDouble()?asNumber(peak.value("width_half_height_v").toDouble()*1e3,7):"—",
                QString::number(peak.value("row").toInt())};
            for(int c=0;c<cells.size();++c) {
                auto *cell=new QTableWidgetItem(cells[c]);
                if(c>=2) cell->setTextAlignment(Qt::AlignRight|Qt::AlignVCenter);
                peaksTable_->setItem(r,c,cell);
            }
        }
    }
    void loadAnalysis(const QJsonObject &result) {
        const int index=datasetBox_->currentIndex();
        if(index<0||result.value("dataset").toString()!=datasets_[index].toObject().value("name").toString())return;
        analysis_=result;
        peakData_=result.value("peaks").toArray();
        peaksBrief_->setText((currentKind_=="CV"||currentKind_=="LSV"||currentKind_=="DPV"||currentKind_=="SWV") ? QString("DETECTED PEAKS: %1").arg(peakData_.size()) : "TECHNIQUE METRICS");
        updatePeakTable();
        dataTabs_->setCurrentIndex((currentKind_=="CV"||currentKind_=="LSV"||currentKind_=="DPV"||currentKind_=="SWV")?0:1);
        refreshMarkers();
        while(QLayoutItem *item=metricsLayout_->takeAt(0)) {
            if(item->widget())item->widget()->deleteLater();
            delete item;
        }
        const QJsonArray metrics=result.value("metrics").toArray();
        metricTable_->setRowCount(0);
        for(const auto &value:metrics) {
            const QJsonObject m=value.toObject();
            auto *name=makeLabel(m.value("label").toString(),"StatName");name->setWordWrap(true);
            auto *number=makeLabel(asNumber(m.value("value").toDouble(),6)+"  "+m.value("unit").toString(),"AccentNumber");
            number->setWordWrap(true);
            if(!m.value("description").toString().isEmpty()) {
                number->setToolTip(m.value("description").toString());
            }
            metricsLayout_->addWidget(name);metricsLayout_->addWidget(number);
            const int r=metricTable_->rowCount(); metricTable_->insertRow(r);
            const QStringList fields={m.value("label").toString(),
                asNumber(m.value("value").toDouble(),9),m.value("unit").toString()};
            for(int c=0;c<fields.size();++c) {
                auto *entry=new QTableWidgetItem(fields[c]);
                entry->setToolTip(m.value("description").toString());
                metricTable_->setItem(r,c,entry);
            }
        }
        metricsLayout_->addStretch(1);
        const QJsonArray warnings=result.value("warnings").toArray();
        warningsLabel_->setText(warnings.isEmpty()?QString():warnings.first().toString());
        statusBar()->showMessage((currentKind_=="CV"||currentKind_=="LSV"||currentKind_=="DPV"||currentKind_=="SWV") ?
                QString("Analysis complete: %1 detected peak(s). Use 'Show data' to inspect and export them.").arg(peakData_.size()) :
                QString("Analysis metrics calculated (%1 values); review technique-specific warnings.").arg(metrics.size()),12000);
    }
    void exportCurrent() {
        if(busy_)return;
        const int index=datasetBox_->currentIndex();
        if(index<0||index>=datasets_.size())return;
        const QString selected=datasets_[index].toObject().value("name").toString();
        const QString dir=QFileDialog::getExistingDirectory(this,
            "Choose folder for selected plot CSVs", QFileInfo(filePath_).absolutePath());
        if(dir.isEmpty())return;
        QStringList args={"export-package",filePath_,"--dir",dir,"--dataset",selected};
        if(!fileTechnique_.isEmpty())args<<"--technique"<<fileTechnique_;
        runBackend(args,Operation::ExportAll,dir);
    }
    void exportAll() {
        if(busy_||datasets_.isEmpty())return;
        const QString dir=QFileDialog::getExistingDirectory(this,"Choose folder for plot CSV export",QFileInfo(filePath_).absolutePath());
        if(dir.isEmpty())return;
        QStringList args={"export-package",filePath_,"--dir",dir};
        if(!fileTechnique_.isEmpty())args<<"--technique"<<fileTechnique_;
        runBackend(args,Operation::ExportAll,dir);
    }
    void exportText() {
        if(busy_||datasets_.isEmpty())return;
        const QString dir=QFileDialog::getExistingDirectory(this,
            "Choose parent folder for separate TXT files",QFileInfo(filePath_).absolutePath());
        if(dir.isEmpty())return;
        QStringList args={"export-text",filePath_,"--dir",dir};
        if(!fileTechnique_.isEmpty())args<<"--technique"<<fileTechnique_;
        runBackend(args,Operation::ExportText,dir);
    }
    void openOverlay() {
        if(!overlayWindow_)overlayWindow_=new OverlayWindow(this);
        overlayWindow_->show();
        overlayWindow_->raise();
        overlayWindow_->activateWindow();
    }
    void sendToOverlay(OverlayMode mode) {
        const int index=datasetBox_->currentIndex();
        if(index<0||index>=datasets_.size()||filePath_.isEmpty()) {
            QMessageBox::information(this,"Nothing to overlay","Open a NOVA or CSV file and select a dataset first.");
            return;
        }
        if(!overlayWindow_)overlayWindow_=new OverlayWindow(this);
        QString error;
        QJsonObject overlayDataset=datasets_[index].toObject();
        // Send the *currently visible* comparable GCD group rather than
        // adding all 23 vastly different-duration cycles by surprise.
        if(currentKind_=="GCD") {
            const QVariantList choices=cycleBox_->currentData().toList();
            QSet<int> selected;
            for(const QVariant &item:choices) if(item.toInt()>0)selected.insert(item.toInt());
            if(!selected.isEmpty()) {
                const auto columns=overlayDataset.value("columns").toArray();
                int cycleCol=-1;
                for(int j=0;j<columns.size();++j)
                    if(columns[j].toObject().value("key").toString()=="cycle")cycleCol=j;
                if(cycleCol>=0) {
                    QJsonArray filtered;
                    for(const auto &value:overlayDataset.value("values").toArray()) {
                        const QJsonArray row=value.toArray();
                        if(row.size()>cycleCol && selected.contains(row[cycleCol].toInt()))filtered.append(value);
                    }
                    overlayDataset.insert("values",filtered);
                    overlayDataset.insert("point_count",filtered.size());
                    QStringList labels;
                    QList<int> sorted=selected.values();std::sort(sorted.begin(),sorted.end());
                    for(int c:sorted)labels<<QString::number(c);
                    overlayDataset.insert("name",overlayDataset.value("name").toString()+" [cycles "+labels.join(",")+"]");
                }
            }
        }
        if(!overlayWindow_->addDataset(overlayDataset,filePath_,mode,&error)) {
            QMessageBox::warning(this,"Incompatible overlay",error);
            return;
        }
        statusBar()->showMessage("Sent "+datasets_[index].toObject().value("name").toString()+" to overlay workspace.",9000);
    }
    void savePlot() {
        if(datasets_.isEmpty())return;
        const QString filename=QFileDialog::getSaveFileName(this,"Save plot image","nova_signal.png","PNG image (*.png)");
        if(filename.isEmpty())return;
        if(!plot_->grab().save(filename,"PNG"))
            QMessageBox::warning(this,"Save failed","Could not write the plot image.");
        else statusBar()->showMessage("Saved plot PNG: "+filename,10000);
    }

    QJsonObject metadata_;
    QJsonArray datasets_;
    QString filePath_,pendingPath_,fileTechnique_;
    int totalPoints_=0;
    bool busy_=false;
    Operation operation_=Operation::Read;
    QProcess *process_=nullptr;
    QLabel *datasetsValue_=nullptr,*pointsValue_=nullptr,*cvValue_=nullptr,*eisValue_=nullptr,*otherValue_=nullptr;
    QLabel *headline_=nullptr,*backendStatus_=nullptr,*kindLabel_=nullptr,*currentSummary_=nullptr;

    QComboBox *datasetBox_=nullptr,*xBox_=nullptr,*yBox_=nullptr,*cycleBox_=nullptr;
    QPushButton *advancedButton_=nullptr,*overlayButton_=nullptr;
    OverlayWindow *overlayWindow_=nullptr;
    QPushButton *openButton_=nullptr,*resetButton_=nullptr,*exportButton_=nullptr,*exportAllButton_=nullptr,*exportTextButton_=nullptr,*savePlotButton_=nullptr;
    QPushButton *navDashboard_=nullptr,*navCV_=nullptr,*navEIS_=nullptr,*navOther_=nullptr,*navOverlay_=nullptr,*navTable_=nullptr,*navExport_=nullptr;
    QVector<QPushButton*> navButtons_;
    PlotView *plot_=nullptr;
    QWidget *inspector_=nullptr,*dataDrawer_=nullptr;
    QScrollArea *metricsArea_=nullptr;
    QVBoxLayout *metricsLayout_=nullptr;
    QSpinBox *windowSpin_=nullptr,*distanceSpin_=nullptr;
    QDoubleSpinBox *prominenceSpin_=nullptr;
    QCheckBox *showPeaksBox_=nullptr;
    QPushButton *inspectorToggle_=nullptr,*drawerToggle_=nullptr,*analyzeButton_=nullptr,*exportPeaksButton_=nullptr;
    QLabel *peaksBrief_=nullptr,*warningsLabel_=nullptr;
    QTableWidget *peaksTable_=nullptr,*metricTable_=nullptr;
    QTabWidget *dataTabs_=nullptr;
    QJsonObject analysis_;
    QJsonArray peakData_;
    QString currentKind_;
    QTableView *table_=nullptr;
    DataTableModel *model_=nullptr;
};

int main(int argc,char *argv[]) {
    QApplication app(argc,argv);
    QApplication::setApplicationName("Pytro-NOVA");
    QApplication::setApplicationVersion("3.9.5");
    QApplication::setOrganizationName("Independent scientific viewer");
    // Used by Windows release CI to validate Qt GUI startup and that the
    // portable interpreter and decoder are adjacent to the executable.
    // Never opens a measurement, creates windows or changes user files.
    if(app.arguments().contains("--verify-runtime")) {
#ifdef Q_OS_WIN
        const QDir root(QCoreApplication::applicationDirPath());
        if(!QFileInfo::exists(root.filePath("backend/bridge.py"))) return 10;
        if(!QFileInfo::exists(root.filePath("python/python.exe"))) return 11;
#endif
        return 0;
    }
    MainWindow main;
    main.show();
    if(argc>1) QTimer::singleShot(0,&main,[&main,argv]{main.openFile(QString::fromLocal8Bit(argv[1]));});
    return app.exec();
}
