#pragma once
// Native Qt-only visual effects; no OpenGL/Qt Quick, safe for MinGW/Qt Widgets.
#include <QtWidgets/QWidget>
#include <QtWidgets/QFrame>
#include <QtWidgets/QGraphicsDropShadowEffect>
#include <QtGui/QPainter>
#include <QtGui/QRadialGradient>
#include <QtCore/QTimer>
#include <cmath>

class NeonOrbit final : public QWidget {
public:
    explicit NeonOrbit(QWidget *parent=nullptr) : QWidget(parent) {
        setFixedSize(102, 76);
        auto *timer = new QTimer(this);
        connect(timer,&QTimer::timeout,this,[this]{phase_ += 0.055; update();});
        timer->start(40);
    }
protected:
    void paintEvent(QPaintEvent*) override {
        QPainter p(this); p.setRenderHint(QPainter::Antialiasing,true);
        QPointF c(width()/2.0,height()/2.0);
        const qreal r=26.0;
        QRadialGradient aura(c,43);
        aura.setColorAt(0,QColor(40,222,255,75));
        aura.setColorAt(.56,QColor(123,92,246,36));
        aura.setColorAt(1,QColor(42,45,120,0));
        p.setPen(Qt::NoPen);p.setBrush(aura);p.drawEllipse(c,43,43);
        p.setBrush(Qt::NoBrush);
        for(int i=0;i<3;++i){
            QColor cl=i==0?QColor("#5fe6fa"):QColor("#af86fa");
            cl.setAlpha(i==0?200:105);
            p.setPen(QPen(cl,i==0?2.0:1.2));
            const qreal rr=r+i*5;
            p.drawArc(QRectF(c.x()-rr,c.y()-rr,2*rr,2*rr),int((phase_*110+i*105)*16),int(125*16));
            p.drawArc(QRectF(c.x()-rr,c.y()-rr,2*rr,2*rr),int((phase_*110+i*105+180)*16),int(85*16));
        }
        qreal dx=std::cos(phase_)*r,dy=std::sin(phase_)*r;
        p.setBrush(QColor("#89ffff"));p.setPen(Qt::NoPen);
        p.drawEllipse(c+QPointF(dx,dy),3.8,3.8);
        p.setBrush(QColor("#101d3b"));p.drawEllipse(c,15,15);
        p.setPen(QPen(QColor("#93e9ff"),1.2));p.drawEllipse(c,15,15);
        p.setPen(QColor("#c5f4ff"));p.setFont(QFont("Segoe UI",7,QFont::DemiBold));
        p.drawText(QRectF(c.x()-18,c.y()-10,36,20),Qt::AlignCenter,"NOVA");
    }
private:
    qreal phase_=0;
};

inline void setSoftGlow(QFrame *panel, const QColor &color=QColor(51,185,244,75), int blur=21) {
    auto *effect=new QGraphicsDropShadowEffect(panel);
    effect->setOffset(0,0);effect->setBlurRadius(blur);effect->setColor(color);
    panel->setGraphicsEffect(effect);
}
