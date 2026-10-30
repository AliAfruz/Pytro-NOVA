#pragma once
// Native Qt Advanced Lab workspace. The Python process performs *all* analysis.
// This is a header-only widget included after the existing dashboard PlotView.
#include <QtWidgets/QDialog>
#include "neon_fx.h"
#include <QtWidgets/QProgressBar>
#include <QtWidgets/QCheckBox>
#include <QtGui/QLinearGradient>
#include <QtGui/QWheelEvent>
#include <QtGui/QMouseEvent>
#include <QtCore/QTimer>
#include <QtWidgets/QVBoxLayout>
#include <QtWidgets/QHBoxLayout>
#include <QtWidgets/QGridLayout>
#include <QtWidgets/QGroupBox>
#include <QtWidgets/QComboBox>
#include <QtWidgets/QSpinBox>
#include <QtWidgets/QDoubleSpinBox>
#include <QtWidgets/QLabel>
#include <QtWidgets/QPushButton>
#include <QtWidgets/QStackedWidget>
#include <QtWidgets/QListWidget>
#include <QtWidgets/QTableWidget>
#include <QtWidgets/QHeaderView>
#include <QtWidgets/QSplitter>
#include <QtWidgets/QTabWidget>
#include <QtWidgets/QFileDialog>
#include <QtWidgets/QMessageBox>
#include <QtWidgets/QScrollArea>
#include <QtWidgets/QSizePolicy>
#include <QtGui/QPainter>
#include <QtGui/QPainterPath>
#include <QtCore/QProcess>
#include <QtCore/QFileInfo>
#include <QtCore/QFile>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>
#include <QtCore/QJsonArray>
#include <QtCore/QDir>
#include <QtCore/QTextStream>
#include <cmath>
#include <algorithm>
#include <limits>

class AdvancedPlot : public QWidget {
public:
    explicit AdvancedPlot(QWidget *parent=nullptr):QWidget(parent) {
        setMinimumSize(420,260);
        auto *pulse=new QTimer(this);
        connect(pulse,&QTimer::timeout,this,[this]{ glowPhase_ += .05; if(isVisible())update(); });
        pulse->start(85);
    }
    void setChart(const QJsonObject &obj) {
        lines_.clear();
        title_=obj.value("title").toString();
        xLabel_=obj.value("x_label").toString();yLabel_=obj.value("y_label").toString();
        const QColor hues[]={QColor("#5ce9fa"),QColor("#e1a2ff"),QColor("#ffe0a2"),QColor("#6ef0b1"),QColor("#f46d9c"),QColor("#6399ff")};
        double xlo=std::numeric_limits<double>::infinity(),xhi=-xlo,ylo=xlo,yhi=-xlo;
        int k=0;
        for(const auto &v:obj.value("series").toArray()) {
            auto s=v.toObject();
            Line item;item.name=s.value("label").toString();item.dashed=s.value("dashed").toBool();
            item.color=hues[k++%6];
            const auto xs=s.value("x").toArray(),ys=s.value("y").toArray();
            for(int i=0;i<std::min(xs.size(),ys.size());++i) {
                if(!xs[i].isDouble()||!ys[i].isDouble())continue;
                const double x=xs[i].toDouble(),y=ys[i].toDouble();
                if(!std::isfinite(x)||!std::isfinite(y))continue;
                item.pts.append({x,y});
                xlo=std::min(x,xlo);xhi=std::max(x,xhi);ylo=std::min(y,ylo);yhi=std::max(y,yhi);
            }
            if(!item.pts.isEmpty())lines_.append(item);
        }
        valid_=!lines_.isEmpty();
        if(valid_) {
            if(xlo==xhi) {xlo-=1;xhi+=1;}
            if(ylo==yhi) {ylo-=1;yhi+=1;}
            const double dx=(xhi-xlo)*.05,dy=(yhi-ylo)*.10;
            xmin_=xlo-dx;xmax_=xhi+dx;ymin_=ylo-dy;ymax_=yhi+dy;
            fullXmin_=xmin_;fullXmax_=xmax_;fullYmin_=ymin_;fullYmax_=ymax_;
        }
        update();
    }
protected:
    void wheelEvent(QWheelEvent *event) override {
        if(!valid_)return;
        const double factor=event->angleDelta().y()>0?.82:1.22;
        const double xcen=(xmin_+xmax_)/2.0, ycen=(ymin_+ymax_)/2.0;
        const double dx=std::max((xmax_-xmin_)*factor,(fullXmax_-fullXmin_)*0.0005);
        const double dy=std::max((ymax_-ymin_)*factor,(fullYmax_-fullYmin_)*0.0005);
        xmin_=xcen-dx/2;xmax_=xcen+dx/2;
        ymin_=ycen-dy/2;ymax_=ycen+dy/2;
        update();event->accept();
    }
    void mouseDoubleClickEvent(QMouseEvent *) override {
        if(!valid_)return;
        xmin_=fullXmin_;xmax_=fullXmax_;ymin_=fullYmin_;ymax_=fullYmax_;
        update();
    }
    void paintEvent(QPaintEvent *) override {
        QPainter p(this);p.setRenderHint(QPainter::Antialiasing);
        QLinearGradient backdrop(0,0,width(),height());
        backdrop.setColorAt(0,QColor("#101d37"));
        backdrop.setColorAt(1,QColor("#070f22"));
        p.fillRect(rect(),backdrop);
        if(!valid_) {p.setPen(QColor("#95b7d0"));p.drawText(rect(),Qt::AlignCenter,"RUN AN ANALYSIS TO SEE FITTED CURVES");return;}
        QRectF box(83,49,std::max(1,width()-125),std::max(1,height()-127));
        p.setFont(QFont("Segoe UI",9));
        for(int k=0;k<=5;++k) {
            double frac=k/5.;double px=box.left()+frac*box.width(),py=box.bottom()-frac*box.height();
            p.setPen(QPen(QColor("#243a57"),1));
            p.drawLine(QPointF(px,box.top()),QPointF(px,box.bottom()));
            p.drawLine(QPointF(box.left(),py),QPointF(box.right(),py));
            p.setPen(QColor("#aec4db"));
            p.drawText(QRectF(px-48,box.bottom()+6,96,23),Qt::AlignHCenter,QString::number(xmin_+frac*(xmax_-xmin_),'g',4));
            p.drawText(QRectF(1,py-12,box.left()-9,23),Qt::AlignRight|Qt::AlignVCenter,QString::number(ymin_+frac*(ymax_-ymin_),'g',4));
        }
        p.setPen(QPen(QColor("#34617e"),1));p.drawRect(box);
        p.setPen(QColor("#ebfaff"));p.setFont(QFont("Segoe UI",10,QFont::DemiBold));
        p.drawText(QRectF(box.left(),9,box.width(),26),Qt::AlignLeft|Qt::AlignVCenter,title_);
        p.setFont(QFont("Segoe UI",9));
        p.drawText(QRectF(box.left(),height()-39,box.width(),24),Qt::AlignHCenter,xLabel_);
        p.save();p.translate(14,box.center().y());p.rotate(-90);
        p.drawText(QRectF(-box.height()/2,-12,box.height(),24),Qt::AlignHCenter,yLabel_);p.restore();
        auto tr=[&](QPointF pt){return QPointF(box.left()+(pt.x()-xmin_)/(xmax_-xmin_)*box.width(),
                       box.bottom()-(pt.y()-ymin_)/(ymax_-ymin_)*box.height());};
        p.save();p.setClipRect(box);
        for(const auto &line:lines_) {
            if(line.pts.size()<2)continue;
            QPainterPath trace;trace.moveTo(tr(line.pts[0]));
            for(int i=1;i<line.pts.size();++i)trace.lineTo(tr(line.pts[i]));
            if(!line.dashed) {
                QColor glow=line.color;
                glow.setAlpha(25 + int(16*(1+std::sin(glowPhase_))));
                p.setPen(QPen(glow,7.0));p.drawPath(trace);
                glow.setAlpha(85);
                p.setPen(QPen(glow,3.4));p.drawPath(trace);
            }
            p.setPen(QPen(line.color,line.dashed?1.4:2, line.dashed?Qt::DashLine:Qt::SolidLine));
            p.drawPath(trace);
        }
        p.restore();
        // Legend is below the plot, with truncated names; the detailed series are in result JSON.
        int cursor=83;int count=0;
        for(const auto &line:lines_) {
            if(count>=4||cursor+120>width())break;
            p.setPen(QPen(line.color,2));p.drawLine(cursor,height()-9,cursor+15,height()-9);
            p.setPen(QColor("#c6e0f2"));p.drawText(cursor+19,height()-4,line.name.left(20));
            cursor += std::min(230, std::max(123, 20 + static_cast<int>(line.name.size()) * 6)); ++count;
        }
        if(lines_.size()>count) {p.setPen(QColor("#8faac5"));p.drawText(width()-75,height()-4,"+"+QString::number(lines_.size()-count));}
    }
private:
    struct Line {QString name;QColor color;bool dashed=false;QVector<QPointF> pts;};
    QVector<Line> lines_;bool valid_=false;
    QString title_,xLabel_,yLabel_;
    double xmin_=0,xmax_=1,ymin_=0,ymax_=1;
    double fullXmin_=0,fullXmax_=1,fullYmin_=0,fullYmax_=1;
    double glowPhase_=0;
};

class AdvancedLabDialog final : public QDialog {
public:
    AdvancedLabDialog(const QString &file,const QJsonArray &datasets,const QString &preferredDataset,
                      const QString &python,const QString &backendScript,QWidget *parent=nullptr)
        :QDialog(parent),file_(file),python_(python),script_(backendScript) {
        setWindowTitle("PYTRO-NOVA 3  •  Afruz Circuit Engine + Advanced Analysis");
        resize(1430,895);setMinimumSize(1000,670);
        setAttribute(Qt::WA_DeleteOnClose);
        createUi(datasets);
        if(!preferredDataset.isEmpty()) {
            const int i=autoData_->findText(preferredDataset);
            if(i>=0) { autoData_->setCurrentIndex(i); eisData_->setCurrentIndex(i); }
            const int j=cvData_->findText(preferredDataset);
            if(j>=0) cvData_->setCurrentIndex(j);
        }
    }
    ~AdvancedLabDialog() override {
        if(process_ && process_->state()!=QProcess::NotRunning) { process_->kill();process_->waitForFinished(1000); }
    }
private:
    static QLabel *text(const QString &s){auto *v=new QLabel(s);v->setWordWrap(true);return v;}
    void createUi(const QJsonArray &datasets) {
        auto *layout=new QVBoxLayout(this);layout->setContentsMargins(14,12,14,12);layout->setSpacing(10);
        auto *heading=new QHBoxLayout;
        auto *title=text("ADVANCED ANALYSIS LAB  /  V3.2");title->setStyleSheet("font-size:18pt;font-weight:750;color:#5eeaff;");
        heading->addWidget(title);heading->addStretch(1);
        heading->addWidget(new NeonOrbit);
        auto *note=text("CV FITTING  •  AFRUZ-EIS AUTO CIRCUIT DISCOVERY");note->setStyleSheet("color:#9bc6e4;");heading->addWidget(note);
        layout->addLayout(heading);
        auto *split=new QSplitter(Qt::Horizontal);split->setChildrenCollapsible(false);layout->addWidget(split,1);
        auto *controls=new QFrame;controls->setObjectName("GlassPanel");controls->setMinimumWidth(292);controls->setMaximumWidth(390);
        auto *ctl=new QVBoxLayout(controls);ctl->setContentsMargins(8,5,8,5);
        ctl->addWidget(text("ANALYSIS MODE"));
        mode_=new QComboBox;mode_->addItems({"CV  /  Baseline + peak deconvolution","CV  /  Multi-run comparison","EIS  /  MANUAL (3 simple circuits)", "EIS  /  AUTO CIRCUIT ENGINE (Afruz)"});
        ctl->addWidget(mode_);
        pages_=new QStackedWidget;ctl->addWidget(pages_);
        auto *cvpage=new QWidget;auto *cvl=new QVBoxLayout(cvpage);cvl->setContentsMargins(0,10,0,0);
        cvl->addWidget(text("CV DATASET"));cvData_=new QComboBox;cvl->addWidget(cvData_);
        cvl->addWidget(text("BASELINE CORRECTION"));baseline_=new QComboBox;
        baseline_->addItem("Asymmetric least-squares (AsLS)","asls");baseline_->addItem("Linear endpoint baseline","linear");
        cvl->addWidget(baseline_);
        cvl->addWidget(text("PEAK PROFILE"));shape_=new QComboBox;
        shape_->addItem("Gaussian","gaussian");shape_->addItem("Lorentzian","lorentzian");cvl->addWidget(shape_);
        cvl->addWidget(text("MAXIMUM COMPONENTS PER BRANCH / POLARITY"));components_=new QSpinBox;
        components_->setRange(1,6);components_->setValue(2);cvl->addWidget(components_);
        cvl->addWidget(text("AsLS smoothness λ"));lambda_=new QDoubleSpinBox;
        lambda_->setDecimals(0);lambda_->setRange(100,1e9);lambda_->setValue(1e5);lambda_->setSingleStep(1e4);
        cvl->addWidget(lambda_);
        cvl->addWidget(text("AsLS asymmetry p"));asymmetry_=new QDoubleSpinBox;
        asymmetry_->setDecimals(3);asymmetry_->setRange(.001,.3);asymmetry_->setSingleStep(.005);asymmetry_->setValue(.02);
        cvl->addWidget(asymmetry_);
        cvl->addWidget(text("Multiple peaks are fitted on each monotonic sweep; oxidation and reduction are handled separately."));
        cvl->addStretch(1);pages_->addWidget(cvpage);
        auto *comparepage=new QWidget;auto *col=new QVBoxLayout(comparepage);col->setContentsMargins(0,10,0,0);
        col->addWidget(text("SELECT TWO OR MORE CV DATASETS"));cvList_=new QListWidget;
        cvList_->setSelectionMode(QAbstractItemView::MultiSelection);col->addWidget(cvList_,1);
        col->addWidget(text("POTENTIAL AXIS ALIGNMENT"));align_=new QComboBox;
        align_->addItem("No alignment (preserve peak shifts)","none");
        align_->addItem("Align by oxidation peak potential","oxidation");col->addWidget(align_);
        col->addWidget(text("RMS comparison is calculated separately on matching sweep branches."));
        pages_->addWidget(comparepage);
        auto *eispage=new QWidget;auto *eisl=new QVBoxLayout(eispage);eisl->setContentsMargins(0,10,0,0);
        eisl->addWidget(text("IMPEDANCE DATASET"));eisData_=new QComboBox;eisl->addWidget(eisData_);
        eisl->addWidget(text("CIRCUIT MODEL"));circuit_=new QComboBox;
        circuit_->addItem("Rs + (Rct || Cdl)","randles_rc");
        circuit_->addItem("Rs + (Rct || CPE)","randles_cpe");
        circuit_->addItem("Rs + (Rct || CPE) + Warburg","randles_cpe_warburg");eisl->addWidget(circuit_);
        eisl->addWidget(text("RESIDUAL WEIGHTING"));weighting_=new QComboBox;
        weighting_->addItem("Relative magnitude (recommended)","modulus");weighting_->addItem("Uniform (absolute Ω)","uniform");eisl->addWidget(weighting_);
        eisl->addWidget(text("MANUAL LEGACY MODE: only three Randles circuits are available here. Long diffusion tails will be underfit. Use AUTO CIRCUIT ENGINE for model discovery."));
        eisl->addStretch(1);pages_->addWidget(eispage);
        auto *autopage=new QWidget;auto *autoLayout=new QVBoxLayout(autopage);
        autoLayout->setContentsMargins(0,10,0,0);autoLayout->setSpacing(9);
        autoLayout->addWidget(text("EIS DATASET"));autoData_=new QComboBox;autoLayout->addWidget(autoData_);
        autoLayout->addWidget(text("MODEL DISCOVERY DEPTH"));depth_=new QComboBox;
        depth_->addItem("Fast • 7 core topologies", "fast");
        depth_->addItem("Deep • 15 diffusion / CPE / porous models", "deep");
        depth_->addItem("Exhaustive • all 19 models (slow)", "exhaustive");
        depth_->setCurrentIndex(2);  // Default to ALL 19 models, as in Afruz-EIS
        autoLayout->addWidget(depth_);
        autoLayout->addWidget(text("OPTIMIZER PRECISION"));precision_=new QComboBox;
        precision_->addItem("Balanced • 5 starts, 5000 evaluations","balanced");
        precision_->addItem("Quick preview • 2 starts, 900 evaluations","quick");
        precision_->addItem("AFRUZ ORIGINAL • hybrid / 8 starts / 8000 eval (slow)","afr_original");
        precision_->setCurrentIndex(2);  // Hybrid, 8 starts, 8000 evaluations (Afruz-EIS GUI default)
        autoLayout->addWidget(precision_);
        autoLayout->addWidget(text("AUTO SMOOTHING / PLOT PREVIEW"));smoothing_=new QComboBox;
        smoothing_->addItem("Auto • adaptive log-frequency SG", "auto");
        smoothing_->addItem("Off • raw data only", "off");
        smoothing_->addItem("Light • SG window 5", "light");
        smoothing_->addItem("Strong • SG window 9", "strong");
        smoothing_->setCurrentIndex(1); // Strict parity: display raw data by default
        autoLayout->addWidget(smoothing_);
        fitSmoothed_=new QCheckBox("Fit smoothed values (experimental)");
        fitSmoothed_->setChecked(false);
        fitSmoothed_->setToolTip("Off (recommended): all circuit fitting uses the ORIGINAL EIS readings, even if smoothing is shown.");
        autoLayout->addWidget(fitSmoothed_);
        autoLayout->addWidget(text("COMPLEX RESIDUAL WEIGHTING"));autoWeight_=new QComboBox;
        autoWeight_->addItem("Magnitude normalized", "modulus");
        autoWeight_->addItem("Uniform in ohms", "unit");
        autoWeight_->addItem("Proportional", "proportional");
        autoLayout->addWidget(autoWeight_);
        autoLayout->addWidget(text("Afruz-EIS ORIGINAL DEFAULT: 19 models, hybrid optimizer, 8 starts and 8000 evaluations. Full auto fitting can take several minutes. The exact selected circuit must be validated against residuals."));
        autoLayout->addStretch(1);pages_->addWidget(autopage);
        for(const auto &v:datasets) {
            const auto ds=v.toObject();const auto name=ds.value("name").toString();
            if(ds.value("kind").toString()=="CV") {
                cvData_->addItem(name);
                cvList_->addItem(name);
            } else if(ds.value("kind").toString()=="EIS") {eisData_->addItem(name);autoData_->addItem(name);}
        }
        for(int i=0;i<cvList_->count();i++)cvList_->item(i)->setSelected(true);
        connect(mode_,QOverload<int>::of(&QComboBox::currentIndexChanged),pages_,&QStackedWidget::setCurrentIndex);
        // Default to actual Afruz automatic search when EIS measurements exist.
        // Prior builds opened the legacy 3-circuit fitter and looked like auto-fit.
        const int startupMode=autoData_->count()>0 ? 3 : 0;
        mode_->setCurrentIndex(startupMode);pages_->setCurrentIndex(startupMode);
        connect(eisData_,QOverload<int>::of(&QComboBox::currentIndexChanged),this,[this](int i){
            if(i>=0 && i<autoData_->count() && autoData_->currentIndex()!=i)autoData_->setCurrentIndex(i);
        });
        connect(autoData_,QOverload<int>::of(&QComboBox::currentIndexChanged),this,[this](int i){
            if(i>=0 && i<eisData_->count() && eisData_->currentIndex()!=i)eisData_->setCurrentIndex(i);
        });
        connect(mode_,QOverload<int>::of(&QComboBox::currentIndexChanged),this,[this](int i){
            analyze_->setText(i==3 ? "RUN AFRUZ AUTO-FIT" : "RUN ADVANCED ANALYSIS");
        });
        ctl->addStretch(1);
        analyze_=new QPushButton(mode_->currentIndex()==3 ? "RUN AFRUZ AUTO-FIT" : "RUN ADVANCED ANALYSIS");analyze_->setObjectName("Primary");ctl->addWidget(analyze_);
        auto *exrow=new QHBoxLayout;
        csv_=new QPushButton("Export CSV");json_=new QPushButton("Export JSON");
        exrow->addWidget(csv_);exrow->addWidget(json_);ctl->addLayout(exrow);
        save_=new QPushButton("Save figure PNG");ctl->addWidget(save_);
        busyBar_=new QProgressBar;busyBar_->setRange(0,0);busyBar_->setTextVisible(false);
        busyBar_->setVisible(false);ctl->addWidget(busyBar_);
        cancel_=new QPushButton("CANCEL FIT");cancel_->setVisible(false);ctl->addWidget(cancel_);
        connect(cancel_,&QPushButton::clicked,this,[this]{ if(process_)process_->kill(); });
        ctl->addWidget(text("Automatic model selection is a ranking of mathematical candidates, not proof of mechanism."));
        split->addWidget(controls);

        auto *body=new QFrame;body->setObjectName("GlassPanel");auto *bl=new QVBoxLayout(body);bl->setContentsMargins(0,0,0,0);bl->setSpacing(7);
        plots_=new QTabWidget;
        plot_=new AdvancedPlot;residual_=new AdvancedPlot;bode_=new AdvancedPlot;
        plots_->addTab(plot_,"MAIN PLOT / NYQUIST");plots_->addTab(residual_,"EIS RESIDUALS");
        plots_->addTab(bode_,"BODE / MAGNITUDE");
        plots_->setTabEnabled(1,false);plots_->setTabEnabled(2,false);
        bl->addWidget(plots_,6);
        summary_=text("Select an analysis and press RUN ADVANCED ANALYSIS.");
        summary_->setMinimumHeight(28);summary_->setStyleSheet("color:#62eaf3;font-weight:650;");
        bl->addWidget(summary_);
        resultTabs_=new QTabWidget;
        results_=new QTableWidget;results_->setEditTriggers(QAbstractItemView::NoEditTriggers);
        results_->setAlternatingRowColors(true);results_->setSelectionBehavior(QAbstractItemView::SelectRows);
        params_=new QTableWidget;params_->setEditTriggers(QAbstractItemView::NoEditTriggers);
        params_->setAlternatingRowColors(true);params_->setSelectionBehavior(QAbstractItemView::SelectRows);
        resultTabs_->addTab(results_,"FIT RESULTS / MODEL LEADERBOARD");
        resultTabs_->addTab(params_,"BEST-FIT CIRCUIT PARAMETERS");
        resultTabs_->setMinimumHeight(170);
        bl->addWidget(resultTabs_,2);
        modelInfo_=text("Model expressions, warnings, and quality indicators appear after auto-fit.");
        modelInfo_->setStyleSheet("color:#a9d9f2;");modelInfo_->setMaximumHeight(55);
        bl->addWidget(modelInfo_);
        warning_=text("Numerical analysis is exploratory. Model fits are not proof of mechanism.");
        warning_->setStyleSheet("color:#cfbadf;");warning_->setMaximumHeight(60);bl->addWidget(warning_);
        status_=text("Ready");status_->setStyleSheet("color:#9cc9e2;");bl->addWidget(status_);
        split->addWidget(body);split->setStretchFactor(0,0);split->setStretchFactor(1,1);
        split->setSizes({326,1050});
        connect(analyze_,&QPushButton::clicked,this,[this]{execute();});
        connect(csv_,&QPushButton::clicked,this,[this]{exportCsv();});
        connect(json_,&QPushButton::clicked,this,[this]{exportJson();});
        connect(save_,&QPushButton::clicked,this,[this]{savePlot();});
        csv_->setEnabled(false);json_->setEnabled(false);save_->setEnabled(false);
    }
    QStringList arguments() const {
        const int mode=mode_->currentIndex();QStringList args;
        if(mode==0) {
            if(cvData_->currentText().isEmpty())return {};
            args<<"cv"<<file_<<"--dataset"<<cvData_->currentText()
                <<"--baseline"<<baseline_->currentData().toString()
                <<"--shape"<<shape_->currentData().toString()
                <<"--components"<<QString::number(components_->value())
                <<"--lambda-asls"<<QString::number(lambda_->value(),'g',12)
                <<"--asymmetry"<<QString::number(asymmetry_->value(),'g',12);
        } else if(mode==1) {
            args<<"compare"<<file_;
            int count=0;
            for(int i=0;i<cvList_->count();++i)if(cvList_->item(i)->isSelected()) {
                args<<"--dataset"<<cvList_->item(i)->text();++count;
            }
            if(count<2)return {};
            args<<"--align"<<align_->currentData().toString();
        } else if(mode==2) {
            if(eisData_->currentText().isEmpty())return {};
            args<<"eis"<<file_<<"--dataset"<<eisData_->currentText()
                <<"--circuit"<<circuit_->currentData().toString()
                <<"--weighting"<<weighting_->currentData().toString();
        } else {
            if(autoData_->currentText().isEmpty())return {};
            args<<"eis"<<file_<<"--dataset"<<autoData_->currentText()
                <<"--circuit"<<"auto"
                <<"--search-depth"<<depth_->currentData().toString()
                <<"--precision"<<precision_->currentData().toString()
                <<"--smoothing"<<smoothing_->currentData().toString()
                <<"--weighting"<<autoWeight_->currentData().toString();
            if(fitSmoothed_->isChecked())args<<"--fit-smoothed";
        }
        return args;
    }
    void execute() {
        if(process_)return;
        QStringList args=arguments();
        if(args.isEmpty()) {
            QMessageBox::information(this,"Select data","Choose an applicable CV/EIS dataset, or at least two CV runs for comparison.");return;
        }
        if(!QFileInfo::exists(script_)) {
            QMessageBox::critical(this,"Missing backend","Cannot find backend/advanced.py next to backend/bridge.py.");return;
        }
        process_=new QProcess(this);
        process_->setProgram(python_);
        QStringList full;
#ifdef Q_OS_WIN
        if(QFileInfo(python_).completeBaseName().compare("py",Qt::CaseInsensitive)==0)full<<"-3";
#endif
        full<<script_;full<<args;
        process_->setArguments(full);
        analyze_->setDisabled(true);busyBar_->setVisible(true);cancel_->setVisible(true);
        status_->setText("Computing in Python — candidate models may take a few minutes…");
        auto *active=process_;
        connect(active,QOverload<int,QProcess::ExitStatus>::of(&QProcess::finished),this,
                [this,active](int code,QProcess::ExitStatus state) {
            if(active!=process_)return;
            QByteArray output=active->readAllStandardOutput();QString err=QString::fromUtf8(active->readAllStandardError());
            active->deleteLater();process_=nullptr;analyze_->setEnabled(true);
            busyBar_->setVisible(false);cancel_->setVisible(false);
            if(code!=0 || state!=QProcess::NormalExit) {
                status_->setText("Analysis failed");
                QMessageBox::critical(this,"Python analysis error",err.isEmpty()?"The process returned an error.":err.trimmed());return;
            }
            QJsonParseError error;
            const QJsonDocument doc=QJsonDocument::fromJson(output,&error);
            if(error.error!=QJsonParseError::NoError || !doc.isObject()) {
                QMessageBox::critical(this,"Analysis protocol error",error.errorString());return;
            }
            result_=doc.object();showResult();
        });
        connect(active,&QProcess::errorOccurred,this,[this,active](QProcess::ProcessError err){
            if(active!=process_||err!=QProcess::FailedToStart)return;
            active->deleteLater();process_=nullptr;analyze_->setEnabled(true);
            busyBar_->setVisible(false);cancel_->setVisible(false);
            status_->setText("Cannot launch Python");
            QMessageBox::critical(this,"Cannot launch backend","Check NOVA_PYTHON and your installed Python interpreter.");
        });
        active->start();
    }
    QString format(QJsonValue v) const {
        if(v.isNull()||v.isUndefined())return "—";
        if(v.isBool())return v.toBool()?"yes":"no";
        if(v.isDouble())return QString::number(v.toDouble(),'g',8);
        return v.toString();
    }
    void showResult() {
        const auto cols=result_.value("columns").toArray();const auto rows=result_.value("rows").toArray();
        results_->clear();results_->setColumnCount(cols.size());results_->setRowCount(rows.size());
        QStringList labels;for(auto c:cols)labels<<c.toString();results_->setHorizontalHeaderLabels(labels);
        for(int r=0;r<rows.size();++r) {
            const auto obj=rows[r].toObject();
            for(int c=0;c<cols.size();++c) {
                auto *item=new QTableWidgetItem(format(obj.value(cols[c].toString())));
                results_->setItem(r,c,item);
            }
        }
        results_->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
        results_->horizontalHeader()->setStretchLastSection(true);
        plot_->setChart(result_.value("plot").toObject());
        const bool hasResidual=result_.value("residual_plot").isObject();
        plots_->setTabEnabled(1,hasResidual);
        if(hasResidual)residual_->setChart(result_.value("residual_plot").toObject());
        const bool hasBode=result_.value("bode_plot").isObject();
        plots_->setTabEnabled(2,hasBode);
        if(hasBode)bode_->setChart(result_.value("bode_plot").toObject());
        const auto pars=result_.value("parameters").toArray();
        const QStringList paramKeys={"Parameter","Value","Std. error","Unit","Note"};
        params_->clear();params_->setColumnCount(paramKeys.size());params_->setRowCount(pars.size());
        params_->setHorizontalHeaderLabels(paramKeys);
        for(int r=0;r<pars.size();++r) {
            const auto obj=pars[r].toObject();
            for(int c=0;c<paramKeys.size();++c)
                params_->setItem(r,c,new QTableWidgetItem(format(obj.value(paramKeys[c]))));
        }
        params_->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
        params_->horizontalHeader()->setStretchLastSection(true);
        resultTabs_->setTabEnabled(1,!pars.isEmpty());
        resultTabs_->setCurrentIndex(0);
        const auto best=result_.value("best_model").toObject();
        modelInfo_->setText(best.isEmpty()?"":QString("CIRCUIT  %1    •    %2    •    correlation: %3")
            .arg(best.value("expression").toString(),best.value("description").toString(),
                 format(best.value("max_abs_parameter_correlation"))));
        plots_->setCurrentIndex(0);
        QStringList summaries;
        for(const auto &v:result_.value("summary").toArray()) {
            const auto obj=v.toObject();
            summaries<<QString("%1: %2 %3").arg(obj.value("name").toString(),format(obj.value("value")),obj.value("unit").toString());
        }
        summary_->setText(summaries.join("    •    "));
        QStringList warnings;
        for(const auto &v:result_.value("warnings").toArray())warnings<<v.toString();
        warning_->setText(warnings.join("   |   "));
        warning_->setToolTip(warnings.join("\n"));
        status_->setText(QString("Analysis complete: %1 result rows • use tabs and export controls").arg(rows.size()));
        csv_->setEnabled(true);json_->setEnabled(true);save_->setEnabled(true);
    }
    void exportCsv() {
        if(result_.isEmpty())return;
        const QString target=QFileDialog::getSaveFileName(this,"Export advanced results",QDir::homePath()+"/nova_advanced.csv","CSV files (*.csv)");
        if(target.isEmpty())return;
        QFile file(target);
        if(!file.open(QIODevice::WriteOnly|QIODevice::Text)) {QMessageBox::critical(this,"Export error",file.errorString());return;}
        QTextStream out(&file);
        auto cell=[](QString v){if(v.contains(',')||v.contains('"')||v.contains('\n')){v.replace('"',"\"\"");return '"'+v+'"';}return v;};
        const auto cols=result_.value("columns").toArray();const auto rows=result_.value("rows").toArray();
        QStringList heads;for(auto c:cols)heads<<cell(c.toString());out<<heads.join(',')<<'\n';
        for(const auto &v:rows) {
            QStringList fields;auto row=v.toObject();
            for(auto c:cols)fields<<cell(format(row.value(c.toString())));
            out<<fields.join(',')<<'\n';
        }
        status_->setText("CSV exported: "+target);
    }
    void exportJson() {
        if(result_.isEmpty())return;
        const QString target=QFileDialog::getSaveFileName(this,"Export full analysis",QDir::homePath()+"/nova_advanced.json","JSON (*.json)");
        if(target.isEmpty())return;
        QFile file(target);
        if(!file.open(QIODevice::WriteOnly)) {QMessageBox::critical(this,"Export error",file.errorString());return;}
        file.write(QJsonDocument(result_).toJson(QJsonDocument::Indented));
        status_->setText("Full analysis JSON exported: "+target);
    }
    void savePlot() {
        const QString target=QFileDialog::getSaveFileName(this,"Save chart",QDir::homePath()+"/nova_advanced.png","PNG (*.png)");
        if(target.isEmpty())return;
        auto *widget=plots_->currentIndex()==1?residual_:(plots_->currentIndex()==2?bode_:plot_);
        if(!widget->grab().save(target,"PNG")) QMessageBox::critical(this,"Export error","Failed to save PNG.");
        else status_->setText("PNG saved: "+target);
    }
    QString file_,python_,script_;
    QProcess *process_=nullptr;QJsonObject result_;
    QComboBox *mode_=nullptr,*cvData_=nullptr,*baseline_=nullptr,*shape_=nullptr,*eisData_=nullptr,*align_=nullptr,*circuit_=nullptr,*weighting_=nullptr;
    QComboBox *autoData_=nullptr,*depth_=nullptr,*precision_=nullptr,*smoothing_=nullptr,*autoWeight_=nullptr;
    QCheckBox *fitSmoothed_=nullptr;
    QProgressBar *busyBar_=nullptr;QPushButton *cancel_=nullptr;QLabel *modelInfo_=nullptr;
    QSpinBox *components_=nullptr;QDoubleSpinBox *lambda_=nullptr,*asymmetry_=nullptr;
    QListWidget *cvList_=nullptr;QStackedWidget *pages_=nullptr;
    QPushButton *analyze_=nullptr,*csv_=nullptr,*json_=nullptr,*save_=nullptr;
    QLabel *summary_=nullptr,*warning_=nullptr,*status_=nullptr;
    QTabWidget *plots_=nullptr,*resultTabs_=nullptr;AdvancedPlot *plot_=nullptr,*residual_=nullptr,*bode_=nullptr;
    QTableWidget *results_=nullptr,*params_=nullptr;
};
