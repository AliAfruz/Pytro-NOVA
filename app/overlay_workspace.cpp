#include "overlay_workspace.h"
#include "neon_fx.h"

#include <QtWidgets/QApplication>
#include <QtWidgets/QWidget>
#include <QtWidgets/QTabBar>
#include <QtWidgets/QLineEdit>
#include <QtWidgets/QFrame>
#include <QtWidgets/QLabel>
#include <QtWidgets/QPushButton>
#include <QtWidgets/QTableWidget>
#include <QtWidgets/QHeaderView>
#include <QtWidgets/QAbstractItemView>
#include <QtWidgets/QCheckBox>
#include <QtWidgets/QVBoxLayout>
#include <QtWidgets/QHBoxLayout>
#include <QtWidgets/QSplitter>
#include <QtWidgets/QFileDialog>
#include <QtWidgets/QColorDialog>
#include <QtWidgets/QInputDialog>
#include <QtWidgets/QMessageBox>
#include <QtWidgets/QStatusBar>
#include <QtWidgets/QToolTip>
#include <QtGui/QPainter>
#include <QtGui/QPainterPath>
#include <QtGui/QMouseEvent>
#include <QtGui/QWheelEvent>
#include <QtCore/QJsonArray>
#include <QtCore/QMap>
#include <QtCore/QJsonValue>
#include <QtCore/QTimer>
#include <QtCore/QFile>
#include <QtCore/QTextStream>
#include <QtCore/QSignalBlocker>
#include <QtCore/QFileInfo>
#if QT_VERSION >= QT_VERSION_CHECK(6, 0, 0)
#include <QtCore/QStringConverter>
#endif
#include <array>
#include <algorithm>
#include <cmath>
#include <limits>

namespace {
const QColor cyan("#52dcf6"), pale("#d8edff"), muted("#87a8c9");
const std::array<QColor, 10> curvePalette{
    QColor("#50e8f9"), QColor("#ae8aff"), QColor("#ffbb78"), QColor("#6ef4c0"),
    QColor("#fb83b5"), QColor("#80b4ff"), QColor("#f3e07f"), QColor("#db8cff"),
    QColor("#ff866c"), QColor("#80e0cf")
};

QString modeName(OverlayMode mode) {
    switch(mode) {
    case OverlayMode::CV: return "CV / CURRENT vs VOLTAGE";
    case OverlayMode::Nyquist: return "EIS / NYQUIST";
    case OverlayMode::BodeMagnitude: return "EIS / BODE MAGNITUDE";
    case OverlayMode::BodePhase: return "EIS / BODE PHASE";
    case OverlayMode::GCD: return "GCD / VOLTAGE vs TIME";
    case OverlayMode::LSV: return "LSV / CURRENT vs VOLTAGE";
    case OverlayMode::DPV: return "DPV / CURRENT vs VOLTAGE";
    case OverlayMode::SWV: return "SWV / CURRENT vs VOLTAGE";
    case OverlayMode::CA: return "CA / CURRENT vs TIME";
    case OverlayMode::CP: return "CP / VOLTAGE vs TIME";
    case OverlayMode::OCP: return "OCP / VOLTAGE vs TIME";
    }
    return "Unknown technique";
}
QString modeKind(OverlayMode mode) {
    if(mode==OverlayMode::CV) return "CV";
    if(mode==OverlayMode::Nyquist||mode==OverlayMode::BodeMagnitude||mode==OverlayMode::BodePhase)return "EIS";
    return modeName(mode).section(' ',0,0);
}
QString xKey(OverlayMode mode) {
    if(mode==OverlayMode::Nyquist)return "z_real_ohm";
    if(mode==OverlayMode::BodeMagnitude||mode==OverlayMode::BodePhase)return "frequency_hz";
    if(mode==OverlayMode::GCD||mode==OverlayMode::CA||mode==OverlayMode::CP||mode==OverlayMode::OCP)return "time_s";
    return "potential_v";
}
QString yKey(OverlayMode mode) {
    if(mode==OverlayMode::Nyquist)return "neg_z_imag_ohm";
    if(mode==OverlayMode::BodeMagnitude)return "z_mod_ohm";
    if(mode==OverlayMode::BodePhase)return "neg_phase_deg";
    if(mode==OverlayMode::GCD||mode==OverlayMode::CP||mode==OverlayMode::OCP)return "potential_v";
    return "current_a";
}
QString rawXTitle(OverlayMode mode) {
    if(mode==OverlayMode::Nyquist)return "Z real (ohm)";
    if(mode==OverlayMode::BodeMagnitude||mode==OverlayMode::BodePhase)return "Frequency (Hz)";
    if(mode==OverlayMode::GCD||mode==OverlayMode::CA||mode==OverlayMode::CP||mode==OverlayMode::OCP)return "Time (s)";
    return "Potential (V)";
}
QString rawYTitle(OverlayMode mode) {
    if(mode==OverlayMode::Nyquist)return "-Z imaginary (ohm)";
    if(mode==OverlayMode::BodeMagnitude)return "|Z| (ohm)";
    if(mode==OverlayMode::BodePhase)return "-Phase (deg)";
    if(mode==OverlayMode::GCD||mode==OverlayMode::CP||mode==OverlayMode::OCP)return "Potential (V)";
    return "Current (A)";
}
QString xTitle(OverlayMode mode) {
    if(mode==OverlayMode::BodeMagnitude||mode==OverlayMode::BodePhase)return "Frequency (Hz) — logarithmic scale";
    if(mode==OverlayMode::Nyquist)return "Z′ (Ω)";
    return rawXTitle(mode);
}
QString yTitle(OverlayMode mode) {
    if(mode==OverlayMode::CV||mode==OverlayMode::LSV||mode==OverlayMode::DPV||mode==OverlayMode::SWV||mode==OverlayMode::CA)
        return "Current (µA)";
    if(mode==OverlayMode::Nyquist)return "−Z″ (Ω)";
    if(mode==OverlayMode::BodeMagnitude)return "|Z| (Ω)";
    if(mode==OverlayMode::BodePhase)return "−Phase (degrees)";
    return "Potential (V)";
}
QString valueText(double value) { return QString::number(value, 'g', 6); }
QString csvEscape(QString value) {
    if(value.contains('"')||value.contains(',')||value.contains('\n')||value.contains('\r')) {
        value.replace('"', "\"\""); return '"' + value + '"';
    }
    return value;
}

struct Curve {
    QString sourceFile;
    QString dataset;
    QString name;
    QColor color;
    QVector<QPointF> rawPoints;
    QVector<int> segmentStarts;  // NOVA handler boundaries; raw points remain unchanged.
    bool visible=true;
};

using CurveSet = std::array<QVector<Curve>, 11>;

int tabIndex(OverlayMode mode) { return static_cast<int>(mode); }
OverlayMode fromTab(int index) {
    return static_cast<OverlayMode>(std::clamp(index, 0, 10));
}

// Display transforms only; stored and CSV-exported values stay original.
QPointF displayPoint(const QPointF &raw, OverlayMode mode) {
    if(mode==OverlayMode::CV || mode==OverlayMode::LSV || mode==OverlayMode::DPV ||
       mode==OverlayMode::SWV || mode==OverlayMode::CA) return {raw.x(), raw.y()*1e6};
    if(mode==OverlayMode::BodeMagnitude || mode==OverlayMode::BodePhase)
        return {std::log10(raw.x()), raw.y()};
    return raw;
}

class OverlayPlot : public QWidget {
public:
    explicit OverlayPlot(QWidget *parent=nullptr) : QWidget(parent) {
        setMinimumSize(510, 360);
        setMouseTracking(true);
        ticker_.setInterval(80);
        connect(&ticker_, &QTimer::timeout, this, [this] { phase_+=0.13; update(); });
        ticker_.start();
    }
    void setData(OverlayMode mode, const QVector<Curve> *curves) {
        mode_=mode;
        curves_=curves;
        zoom_=1;
        hoverSeries_=-1;
        computeBounds();
        update();
    }
    void setAnimation(bool enabled) {
        if(enabled) ticker_.start(); else ticker_.stop();
        update();
    }
    void setGrid(bool enabled) { grid_=enabled; update(); }
    void resetZoom() { zoom_=1; update(); }
    void updateData() { computeBounds(); update(); }
protected:
    QRectF chartRect() const {
        return QRectF(91.0, 50.0, std::max(1.0, double(width()-124)),
                      std::max(1.0, double(height()-132)));
    }
    void computeBounds() {
        bounds_=false;
        if(!curves_)return;
        for(const Curve &curve:*curves_) {
            if(!curve.visible)continue;
            for(const QPointF &raw:curve.rawPoints) {
                if(!std::isfinite(raw.x())||!std::isfinite(raw.y()))continue;
                if((mode_==OverlayMode::BodeMagnitude||mode_==OverlayMode::BodePhase) && raw.x()<=0)continue;
                const QPointF pt=displayPoint(raw,mode_);
                if(!bounds_) {
                    xmin_=xmax_=pt.x(); ymin_=ymax_=pt.y(); bounds_=true;
                } else {
                    xmin_=std::min(xmin_,pt.x()); xmax_=std::max(xmax_,pt.x());
                    ymin_=std::min(ymin_,pt.y()); ymax_=std::max(ymax_,pt.y());
                }
            }
        }
        if(bounds_) {
            if(xmax_==xmin_) {xmin_-=1; xmax_+=1;}
            if(ymax_==ymin_) {ymin_-=1; ymax_+=1;}
            const double dx=(xmax_-xmin_)*0.06,dy=(ymax_-ymin_)*0.09;
            xmin_-=dx;xmax_+=dx;ymin_-=dy;ymax_+=dy;
        }
    }
    QPointF pixel(const QPointF &value, const QRectF &area) const {
        double xc=(xmin_+xmax_)/2, yc=(ymin_+ymax_)/2;
        double xr=(xmax_-xmin_)/zoom_, yr=(ymax_-ymin_)/zoom_;
        return {area.center().x()+(value.x()-xc)/xr*area.width(),
                area.center().y()-(value.y()-yc)/yr*area.height()};
    }
    QString xTick(double value) const {
        if(mode_==OverlayMode::BodeMagnitude||mode_==OverlayMode::BodePhase)
            return valueText(std::pow(10.0, value));
        return valueText(value);
    }
    void paintEvent(QPaintEvent *) override {
        QPainter p(this);p.setRenderHint(QPainter::Antialiasing,true);
        QLinearGradient bg(0,0,width(),height());
        bg.setColorAt(0,QColor("#111d37"));bg.setColorAt(1,QColor("#080e20"));
        p.fillRect(rect(),bg);
        const QRectF a=chartRect();
        p.setPen(pale);p.setFont(QFont("Segoe UI",10,QFont::DemiBold));
        p.drawText(QRectF(a.left(),9,a.width(),28),Qt::AlignLeft|Qt::AlignVCenter,modeName(mode_));
        if(!bounds_) {
            p.setPen(muted);p.setFont(QFont("Segoe UI",12));
            p.drawText(rect(),Qt::AlignCenter,"SEND COMPATIBLE CURVES HERE\nRIGHT-CLICK A MAIN PLOT → SEND TO OVERLAY");
            return;
        }
        p.setFont(QFont("Segoe UI",9));
        const double midx=(xmin_+xmax_)/2,midy=(ymin_+ymax_)/2;
        const double xr=(xmax_-xmin_)/zoom_,yr=(ymax_-ymin_)/zoom_;
        for(int i=0;i<=6;i++) {
            const double f=double(i)/6;
            double px=a.left()+a.width()*f,py=a.bottom()-a.height()*f;
            if(grid_) {
                p.setPen(QPen(QColor("#2c425d"),1));
                p.drawLine(QPointF(px,a.top()),QPointF(px,a.bottom()));
                p.drawLine(QPointF(a.left(),py),QPointF(a.right(),py));
            }
            p.setPen(muted);
            p.drawText(QRectF(px-55,a.bottom()+7,110,21),Qt::AlignHCenter,
                       xTick(midx-xr/2+f*xr));
            p.drawText(QRectF(1,py-10,a.left()-9,20),Qt::AlignRight|Qt::AlignVCenter,
                       valueText(midy-yr/2+f*yr));
        }
        p.setPen(QPen(QColor("#4f8ab1"),1));p.drawRect(a);
        p.setPen(pale);p.drawText(QRectF(a.left(),height()-40,a.width(),23),Qt::AlignHCenter,xTitle(mode_));
        p.save();p.translate(17,a.center().y());p.rotate(-90);
        p.drawText(QRectF(-a.height()/2,-13,a.height(),26),Qt::AlignHCenter,yTitle(mode_));p.restore();
        p.save();p.setClipRect(a);
        int seriesIndex=-1;
        for(const Curve &curve:*curves_) {
            ++seriesIndex;
            if(!curve.visible||curve.rawPoints.isEmpty())continue;
            QPainterPath path;
            // Prevent fake connecting lines across different GCD/CP/OCP
            // handler recordings, including long self-discharge rest periods.
            QVector<int> boundaries;boundaries.append(0);
            for(int offset:curve.segmentStarts)
                if(offset>0 && offset<curve.rawPoints.size())boundaries.append(offset);
            boundaries.append(curve.rawPoints.size());
            for(int seg=0;seg+1<boundaries.size();++seg) {
                const int begin=boundaries[seg],end=boundaries[seg+1];
                if(begin>=end)continue;
                bool started=false;
                const int stride=std::max(1,(end-begin)/2800);
                for(int i=begin;i<end;i+=stride) {
                    const QPointF &raw=curve.rawPoints[i];
                    if((mode_==OverlayMode::BodeMagnitude||mode_==OverlayMode::BodePhase)&&raw.x()<=0) {
                        started=false;continue;
                    }
                    const QPointF pt=pixel(displayPoint(raw,mode_),a);
                    if(!started){path.moveTo(pt);started=true;} else path.lineTo(pt);
                }
                const QPointF &last=curve.rawPoints[end-1];
                if(started && (mode_!=OverlayMode::BodeMagnitude && mode_!=OverlayMode::BodePhase || last.x()>0))
                    path.lineTo(pixel(displayPoint(last,mode_),a));
            }
            QColor glow=curve.color;
            glow.setAlpha(30 + (ticker_.isActive()?int(13+12*std::sin(phase_)):0));
            // No strong glow on large multi-cycle GCD overlays.
            if(mode_!=OverlayMode::GCD && mode_!=OverlayMode::OCP) {
                p.setPen(QPen(glow,7,Qt::SolidLine,Qt::RoundCap));p.drawPath(path);
            }
            p.setPen(QPen(curve.color,seriesIndex==hoverSeries_?2.5:1.7,Qt::SolidLine,Qt::RoundCap));
            p.drawPath(path);
        }
        p.restore();
        // The legend is rebuilt on every paint, reflecting visibility and curve names.
        int legendY=int(a.top()+8);
        for(const Curve &curve:*curves_) {
            if(!curve.visible)continue;
            p.setPen(QPen(curve.color,4));
            p.drawLine(QPointF(a.left()+12,legendY+8),QPointF(a.left()+32,legendY+8));
            p.setPen(pale);p.setFont(QFont("Segoe UI",9));
            p.drawText(QRectF(a.left()+38,legendY, std::max(40.0,a.width()-52),19),
                       Qt::AlignLeft|Qt::AlignVCenter,curve.name);
            legendY+=21;
            if(legendY>a.bottom()-35)break;
        }
    }
    void wheelEvent(QWheelEvent *event) override {
        if(!bounds_)return;
        zoom_=std::clamp(zoom_*(event->angleDelta().y()>0?1.24:1/1.24),1.0,30.0);
        update();event->accept();
    }
    void mouseDoubleClickEvent(QMouseEvent *) override {resetZoom();}
    void mouseMoveEvent(QMouseEvent *event) override {
        if(!bounds_||!chartRect().contains(event->pos())||!curves_) {hoverSeries_=-1;return;}
        double nearest=10*10;
        int series=-1;QPointF match;
        for(int i=0;i<curves_->size();++i) {
            const Curve &curve=curves_->at(i);
            if(!curve.visible)continue;
            const int step=std::max(1,int(curve.rawPoints.size())/4500);
            for(int index=0;index<curve.rawPoints.size();index+=step) {
                const QPointF &raw=curve.rawPoints[index];
                if((mode_==OverlayMode::BodeMagnitude||mode_==OverlayMode::BodePhase)&&raw.x()<=0)continue;
                const QPointF pt=pixel(displayPoint(raw,mode_),chartRect());
                const double dx=pt.x()-event->pos().x(),dy=pt.y()-event->pos().y();
                const double dist=dx*dx+dy*dy;
                if(dist<nearest) {nearest=dist;series=i;match=raw;}
            }
        }
        if(series!=hoverSeries_) {hoverSeries_=series;update();}
#if QT_VERSION >= QT_VERSION_CHECK(6, 0, 0)
        const QPoint tipLocation=event->globalPosition().toPoint();
#else
        const QPoint tipLocation=event->globalPos();
#endif
        if(series>=0)
            QToolTip::showText(tipLocation,
                 QString("%1\nX: %2\nY: %3").arg(curves_->at(series).name,
                      valueText(match.x()), valueText(match.y())),this);
        else QToolTip::hideText();
    }
private:
    QTimer ticker_;
    const QVector<Curve> *curves_=nullptr;
    OverlayMode mode_=OverlayMode::CV;
    bool bounds_=false,grid_=true;
    double xmin_=0,xmax_=1,ymin_=0,ymax_=1,zoom_=1,phase_=0;
    int hoverSeries_=-1;
};
}

struct OverlayWindow::Private {
    CurveSet groups;
    int serial=0;
    QTabBar *tabs=nullptr;
    QTableWidget *table=nullptr;
    OverlayPlot *plot=nullptr;
    QLabel *summary=nullptr;
    QCheckBox *animation=nullptr;
    QCheckBox *grid=nullptr;
    QPushButton *remove=nullptr,*color=nullptr,*rename=nullptr,*clear=nullptr,*save=nullptr,*csv=nullptr;
};

OverlayWindow::OverlayWindow(QWidget *parent) : QMainWindow(parent), d_(new Private) {
    setWindowFlags(Qt::Window);
    setWindowTitle("PYTRO-NOVA  •  PLOT OVERLAY WORKSPACE");
    resize(1440,890);
    setMinimumSize(950,610);
    setStyleSheet(R"QSS(
        QMainWindow {background:#060d1d;}
        QWidget {color:#dbf0ff;font-family:'Segoe UI';font-size:10pt;}
        QLabel {background:transparent;}
        QFrame#OverlayPanel {background:#0c1a34;border:1px solid #2c5075;border-radius:13px;}
        QLabel#OverlayTitle {font-size:20pt;color:#f0fbff;font-weight:750;}
        QLabel#OverlayHint {color:#94b5d5;}
        QPushButton {background:#162d4c;border:1px solid #34668a;border-radius:8px;padding:8px 12px;color:#d7f5ff;}
        QPushButton:hover {background:#20537a;}
        QPushButton#Primary {background:#086c91;border:1px solid #49d9ed;font-weight:700;}
        QPushButton#Danger {background:#3e2039;border:1px solid #8b4a6b;}

        QTabBar::tab {background:#132341;padding:10px 18px;margin-right:3px;border-top-left-radius:7px;border-top-right-radius:7px;}
        QTabBar::tab:selected {background:#245b83;color:#f3fbff;}
        QTableWidget {background:#0b162c;alternate-background-color:#112441;gridline-color:#233d5b;border:0;color:#e1f5ff;}
        QHeaderView::section {background:#153151;color:#b9eafd;padding:8px;border:0;border-right:1px solid #304e68;}
        QCheckBox {color:#bdddf0;}
        QSplitter::handle {background:#192e4a;}
    )QSS");
    auto *body=new QWidget;
    auto *root=new QVBoxLayout(body);root->setContentsMargins(16,14,16,12);root->setSpacing(12);
    auto *header=new QFrame;header->setObjectName("OverlayPanel");
    auto *head=new QHBoxLayout(header);
    auto *intro=new QVBoxLayout;
    auto *title=new QLabel("◈  MULTI-CURVE OVERLAY LAB");title->setObjectName("OverlayTitle");
    auto *hint=new QLabel("Overlays are separated by technique family (CV, EIS, GCD, LSV, DPV, SWV, CA, CP, OCP). Raw measurements are unchanged.");
    hint->setObjectName("OverlayHint");hint->setWordWrap(true);
    intro->addWidget(title);intro->addWidget(hint);
    head->addLayout(intro,1);head->addWidget(new NeonOrbit);
    setSoftGlow(header,QColor(46,165,218,56),24);
    root->addWidget(header);
    d_->tabs=new QTabBar;
    d_->tabs->addTab("CV  •  I–V");
    d_->tabs->addTab("EIS  •  Nyquist");
    d_->tabs->addTab("EIS  •  Bode |Z|");
    d_->tabs->addTab("EIS  •  Bode phase");
    d_->tabs->addTab("GCD  •  E–t");
    d_->tabs->addTab("LSV  •  I–V");
    d_->tabs->addTab("DPV  •  I–V");
    d_->tabs->addTab("SWV  •  I–V");
    d_->tabs->addTab("CA  •  I–t");
    d_->tabs->addTab("CP  •  E–t");
    d_->tabs->addTab("OCP  •  E–t");
    d_->tabs->setUsesScrollButtons(true);
    root->addWidget(d_->tabs);
    // A tab bar selects independent, axis-compatible groups; the plot stays full height.
    auto *split=new QSplitter(Qt::Horizontal);
    split->setChildrenCollapsible(false);
    auto *plotPanel=new QFrame;plotPanel->setObjectName("OverlayPanel");
    auto *plotLayout=new QVBoxLayout(plotPanel);plotLayout->setContentsMargins(8,8,8,8);
    auto *plotControls=new QHBoxLayout;
    d_->summary=new QLabel("No curves yet");d_->summary->setObjectName("OverlayHint");
    plotControls->addWidget(d_->summary,1);
    auto *reset=new QPushButton("Reset zoom");plotControls->addWidget(reset);
    d_->grid=new QCheckBox("Grid");d_->grid->setChecked(true);plotControls->addWidget(d_->grid);
    d_->animation=new QCheckBox("Soft glow");d_->animation->setChecked(true);plotControls->addWidget(d_->animation);
    plotLayout->addLayout(plotControls);
    d_->plot=new OverlayPlot;
    plotLayout->addWidget(d_->plot,1);
    split->addWidget(plotPanel);
    auto *listPanel=new QFrame;listPanel->setObjectName("OverlayPanel");
    listPanel->setMinimumWidth(270);
    auto *listLayout=new QVBoxLayout(listPanel);
    auto *seriesTitle=new QLabel("CURVES IN THIS TAB");seriesTitle->setObjectName("OverlayTitle");
    seriesTitle->setStyleSheet("font-size:13pt;");listLayout->addWidget(seriesTitle);
    auto *tip=new QLabel("Toggle visibility in the table. Select a curve to change its color, name or remove it.");
    tip->setObjectName("OverlayHint");tip->setWordWrap(true);listLayout->addWidget(tip);
    d_->table=new QTableWidget(0,3);
    d_->table->setHorizontalHeaderLabels({"Show", "Curve / file", "Points"});
    d_->table->setSelectionBehavior(QAbstractItemView::SelectRows);
    d_->table->setSelectionMode(QAbstractItemView::SingleSelection);
    d_->table->setAlternatingRowColors(true);
    d_->table->setEditTriggers(QAbstractItemView::NoEditTriggers);
    d_->table->verticalHeader()->hide();
    d_->table->horizontalHeader()->setSectionResizeMode(0,QHeaderView::ResizeToContents);
    d_->table->horizontalHeader()->setSectionResizeMode(1,QHeaderView::Stretch);
    d_->table->horizontalHeader()->setSectionResizeMode(2,QHeaderView::ResizeToContents);
    listLayout->addWidget(d_->table,1);
    auto *buttons=new QHBoxLayout;
    d_->color=new QPushButton("Color");d_->rename=new QPushButton("Rename");d_->remove=new QPushButton("Remove");
    d_->remove->setObjectName("Danger");
    buttons->addWidget(d_->color);buttons->addWidget(d_->rename);buttons->addWidget(d_->remove);
    listLayout->addLayout(buttons);
    d_->clear=new QPushButton("Clear this tab");listLayout->addWidget(d_->clear);
    d_->csv=new QPushButton("Export visible curves CSV");d_->csv->setObjectName("Primary");
    d_->save=new QPushButton("Save overlay PNG");
    listLayout->addWidget(d_->csv);listLayout->addWidget(d_->save);
    split->addWidget(listPanel);
    split->setStretchFactor(0, 8);split->setStretchFactor(1, 2);
    split->setSizes({1030,315});
    root->addWidget(split,1);
    setCentralWidget(body);
    statusBar()->showMessage("Right-click the main Pytro-NOVA plot to send a curve to an overlay tab.");
    connect(d_->tabs,&QTabBar::currentChanged,this,[this](int){refresh();});
    connect(reset,&QPushButton::clicked,d_->plot,[this]{d_->plot->resetZoom();});
    connect(d_->grid,&QCheckBox::toggled,d_->plot,[this](bool v){d_->plot->setGrid(v);});
    connect(d_->animation,&QCheckBox::toggled,d_->plot,[this](bool v){d_->plot->setAnimation(v);});
    connect(d_->table,&QTableWidget::itemChanged,this,[this](QTableWidgetItem *item){
        if(item->column()!=0)return;
        const int idx=d_->tabs->currentIndex(),r=item->row();
        if(r<0||r>=d_->groups[idx].size())return;
        d_->groups[idx][r].visible=item->checkState()==Qt::Checked;
        d_->plot->updateData();
        const int visible=static_cast<int>(std::count_if(d_->groups[idx].cbegin(),d_->groups[idx].cend(),
                      [](const Curve &c){return c.visible;}));
        d_->summary->setText(QString("%1 curves  •  %2 visible").arg(d_->groups[idx].size()).arg(visible));
        d_->save->setEnabled(visible>0);
        d_->csv->setEnabled(visible>0);
    });
    connect(d_->color,&QPushButton::clicked,this,[this]{recolorSelected();});
    connect(d_->rename,&QPushButton::clicked,this,[this]{renameSelected();});
    connect(d_->remove,&QPushButton::clicked,this,[this]{removeSelected();});
    connect(d_->clear,&QPushButton::clicked,this,[this]{clearCurrent();});
    connect(d_->save,&QPushButton::clicked,this,[this]{savePlot();});
    connect(d_->csv,&QPushButton::clicked,this,[this]{exportCsv();});
    refresh();
}

OverlayWindow::~OverlayWindow() {delete d_;}

bool OverlayWindow::addDataset(const QJsonObject &dataset, const QString &sourceFile,
                               OverlayMode mode, QString *error) {
    auto fail=[&](const QString &why){if(error)*error=why;return false;};
    const QString kind=dataset.value("kind").toString();
    if(kind!=modeKind(mode))
        return fail(QString("Cannot place %1 data on a %2 overlay. Technique families cannot be mixed.")
                    .arg(kind,modeKind(mode)));
    const QJsonArray columns=dataset.value("columns").toArray();
    int x=-1,y=-1;
    for(int i=0;i<columns.size();++i) {
        const QString key=columns.at(i).toObject().value("key").toString();
        if(key==xKey(mode))x=i;
        if(key==yKey(mode))y=i;
    }
    if(x<0||y<0)
        return fail(QString("Dataset lacks the columns for %1 (%2 / %3).")
                  .arg(modeName(mode), xKey(mode), yKey(mode)));
    const QString dataName=dataset.value("name").toString();
    const QString origin=QFileInfo(sourceFile).absoluteFilePath();
    QVector<Curve> &group=d_->groups[tabIndex(mode)];
    for(int i=0;i<group.size();++i) {
        if(group[i].sourceFile==origin&&group[i].dataset==dataName) {
            showMode(mode);
            statusBar()->showMessage("This curve is already in the overlay tab. Select it to edit its appearance.",7000);
            d_->table->selectRow(i);
            return true;
        }
    }
    // One incoming multi-cycle dataset becomes one curve *per cycle*.
    // This avoids physically invalid straight lines across independent
    // GCD charge/discharge cycles or separate OCP recording intervals.
    int cycleCol=-1;
    for(int i=0;i<columns.size();++i) {
        const QString key=columns[i].toObject().value("key").toString();
        if(key=="cycle" || (kind=="CV" && key=="scan")) {cycleCol=i;break;}
    }
    const QJsonArray values=dataset.value("values").toArray();
    QMap<int,QVector<QPointF>> grouped;
    QMap<int,QVector<int>> groupSegmentStarts;
    QMap<int,int> lastSegments;
    int segmentCol=-1;
    for(int i=0;i<columns.size();++i)
        if(columns[i].toObject().value("key").toString()=="segment")segmentCol=i;
    for(const QJsonValue &value:values) {
        const QJsonArray row=value.toArray();
        if(row.size()<=std::max(x,y)||!row[x].isDouble()||!row[y].isDouble())continue;
        const double xx=row[x].toDouble(), yy=row[y].toDouble();
        if(!std::isfinite(xx)||!std::isfinite(yy))continue;
        if((mode==OverlayMode::BodeMagnitude||mode==OverlayMode::BodePhase)&&xx<=0)continue;
        const int cycle=(cycleCol>=0 && row.size()>cycleCol)?row[cycleCol].toInt(1):1;
        const int segment=(segmentCol>=0 && row.size()>segmentCol)?row[segmentCol].toInt(1):1;
        if(grouped.contains(cycle) && !grouped[cycle].isEmpty() && lastSegments.value(cycle,-1)!=segment)
            groupSegmentStarts[cycle].append(grouped[cycle].size());
        grouped[cycle].push_back(QPointF(xx,yy));
        lastSegments[cycle]=segment;
    }
    if(grouped.isEmpty())return fail("The dataset has no finite, plottable values for this overlay.");
    int total=0;
    for(auto it=grouped.cbegin();it!=grouped.cend();++it) {
        Curve curve;
        curve.dataset=dataName;
        curve.sourceFile=origin;
        curve.name=QFileInfo(origin).fileName()+"  •  "+dataName;
        if(grouped.size()>1)
            curve.name += (kind=="OCP" ? QString("  /  Interval %1").arg(it.key()) : QString("  /  Cycle %1").arg(it.key()));
        curve.color=curvePalette.at(d_->serial++%int(curvePalette.size()));
        curve.rawPoints=it.value();
        curve.segmentStarts=groupSegmentStarts.value(it.key());
        total+=curve.rawPoints.size();
        group.push_back(std::move(curve));
    }
    showMode(mode);
    d_->table->selectRow(group.size()-grouped.size());
    statusBar()->showMessage(QString("Added %1 to %2 (%3 measured points, %4 curves)")
          .arg(dataName,modeName(mode)).arg(total).arg(grouped.size()),8000);
    return true;
}
void OverlayWindow::showMode(OverlayMode mode) {
    d_->tabs->setCurrentIndex(tabIndex(mode));
    refresh();
    show();raise();activateWindow();
}
void OverlayWindow::refresh() {
    const int tab=d_->tabs->currentIndex();
    const QVector<Curve> &curves=d_->groups[tab];
    {QSignalBlocker blocker(d_->table);
        d_->table->setRowCount(0);
        for(int i=0;i<curves.size();++i) {
            const Curve &c=curves[i];
            const int row=d_->table->rowCount();d_->table->insertRow(row);
            auto *visibility=new QTableWidgetItem;
            visibility->setFlags(Qt::ItemIsSelectable|Qt::ItemIsEnabled|Qt::ItemIsUserCheckable);
            visibility->setCheckState(c.visible?Qt::Checked:Qt::Unchecked);
            d_->table->setItem(row,0,visibility);
            auto *label=new QTableWidgetItem(c.name);label->setForeground(c.color);
            label->setToolTip(c.sourceFile+"\n"+c.dataset);
            d_->table->setItem(row,1,label);
            auto *points=new QTableWidgetItem(QString::number(c.rawPoints.size()));
            points->setTextAlignment(Qt::AlignRight|Qt::AlignVCenter);
            d_->table->setItem(row,2,points);
        }
    }
    const int shown=std::count_if(curves.cbegin(),curves.cend(),[](const Curve &c){return c.visible;});
    d_->summary->setText(QString("%1 curves  •  %2 visible").arg(curves.size()).arg(shown));
    d_->plot->setData(fromTab(tab),&curves);
    d_->remove->setEnabled(!curves.isEmpty());d_->rename->setEnabled(!curves.isEmpty());
    d_->color->setEnabled(!curves.isEmpty());d_->clear->setEnabled(!curves.isEmpty());
    d_->save->setEnabled(shown>0);d_->csv->setEnabled(shown>0);
}
void OverlayWindow::recolorSelected() {
    const int row=d_->table->currentRow(),tab=d_->tabs->currentIndex();
    if(row<0||row>=d_->groups[tab].size())return;
    QColor value=QColorDialog::getColor(d_->groups[tab][row].color,this,"Curve color");
    if(value.isValid()) {d_->groups[tab][row].color=value;refresh();d_->table->selectRow(row);}
}
void OverlayWindow::renameSelected() {
    const int row=d_->table->currentRow(),tab=d_->tabs->currentIndex();
    if(row<0||row>=d_->groups[tab].size())return;
    bool ok=false;
    const QString name=QInputDialog::getText(this,"Curve label","Legend label:",QLineEdit::Normal,
                                           d_->groups[tab][row].name,&ok).trimmed();
    if(ok&&!name.isEmpty()) {d_->groups[tab][row].name=name;refresh();d_->table->selectRow(row);}
}
void OverlayWindow::removeSelected() {
    const int row=d_->table->currentRow(),tab=d_->tabs->currentIndex();
    if(row<0||row>=d_->groups[tab].size())return;
    d_->groups[tab].removeAt(row);
    refresh();
    if(!d_->groups[tab].isEmpty())d_->table->selectRow(std::min(row,int(d_->groups[tab].size())-1));
}
void OverlayWindow::clearCurrent() {
    const int tab=d_->tabs->currentIndex();
    if(d_->groups[tab].isEmpty())return;
    if(QMessageBox::question(this,"Clear overlay tab","Remove all curves from this plot tab?")!=QMessageBox::Yes)return;
    d_->groups[tab].clear();refresh();
}
void OverlayWindow::savePlot() {
    QString base="NOVA_"+QString::number(d_->tabs->currentIndex()+1)+"_Overlay.png";
    const QString path=QFileDialog::getSaveFileName(this,"Save overlay plot",base,"PNG image (*.png)");
    if(path.isEmpty())return;
    if(!d_->plot->grab().save(path,"PNG"))
        QMessageBox::warning(this,"PNG export failed","Could not save the overlay image.");
    else statusBar()->showMessage("Saved: "+path,10000);
}
void OverlayWindow::exportCsv() {
    const int tab=d_->tabs->currentIndex();
    const OverlayMode mode=fromTab(tab);
    const auto &curves=d_->groups[tab];
    QString suggest="NOVA_"+QString::number(tab+1)+"_Overlay.csv";
    const QString path=QFileDialog::getSaveFileName(this,"Export visible overlay curves",suggest,"CSV (*.csv)");
    if(path.isEmpty())return;
    QFile file(path);
    if(!file.open(QIODevice::WriteOnly|QIODevice::Text)) {
        QMessageBox::warning(this,"CSV export failed",file.errorString());return;
    }
    QTextStream out(&file);
#if QT_VERSION >= QT_VERSION_CHECK(6,0,0)
    out.setEncoding(QStringConverter::Utf8);
#else
    out.setCodec("UTF-8");
#endif
    out<<"source_file,dataset,curve_label,technique,plot_type,point_index,"
       <<csvEscape(rawXTitle(mode))<<","<<csvEscape(rawYTitle(mode))<<"\n";
    int total=0;
    for(const Curve &c:curves) {
        if(!c.visible)continue;
        int row=0;
        for(const QPointF &pt:c.rawPoints) {
            out<<csvEscape(QFileInfo(c.sourceFile).fileName())<<","<<csvEscape(c.dataset)<<","<<csvEscape(c.name)
               <<","<<modeKind(mode)<<","<<csvEscape(modeName(mode))<<","<<(++row)<<","
               <<QString::number(pt.x(),'g',17)<<","<<QString::number(pt.y(),'g',17)<<"\n";
            ++total;
        }
    }
    file.close();
    if(file.error()!=QFile::NoError)
        QMessageBox::warning(this,"CSV export failed",file.errorString());
    else statusBar()->showMessage(QString("Exported %1 original measurement pairs to %2").arg(total).arg(path),12000);
}
