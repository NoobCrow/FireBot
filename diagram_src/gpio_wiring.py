import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, Rectangle
plt.rcParams['font.family']='DejaVu Sans'
names={1:'3V3',2:'5V',3:'GPIO2',4:'5V',5:'GPIO3',6:'GND',7:'GPIO4',8:'GPIO14',9:'GND',10:'GPIO15',
11:'GPIO17',12:'GPIO18',13:'GPIO27',14:'GND',15:'GPIO22',16:'GPIO23',17:'3V3',18:'GPIO24',19:'GPIO10',20:'GND',
21:'GPIO9',22:'GPIO25',23:'GPIO11',24:'GPIO8',25:'GND',26:'GPIO7',27:'ID_SD',28:'ID_SC',29:'GPIO5',30:'GND',
31:'GPIO6',32:'GPIO12',33:'GPIO13',34:'GND',35:'GPIO19',36:'GPIO16',37:'GPIO26',38:'GPIO20',39:'GND',40:'GPIO21'}
L='#2E8B57'; R='#1B8A9A'; S='#1F5FBF'; P='#C0392B'; G='#222222'
use={7:('M3 EN — Front-Right PWM',R),8:('M1 EN — Front-Left PWM',L),11:('M1 IN1 — Front-Left',L),
12:('M2 EN — Rear-Left PWM',L),13:('M1 IN2 — Front-Left',L),15:('M2 IN1 — Rear-Left',L),16:('M2 IN2 — Rear-Left',L),
18:('M3 IN1 — Front-Right',R),19:('Camera TILT servo',S),21:('Pump relay IN (active HIGH)',P),22:('M3 IN2 — Front-Right',R),
29:('M4 IN1 — Rear-Right',R),31:('M4 IN2 — Rear-Right',R),33:('Hose sweep servo',S),35:('M4 EN — Rear-Right PWM',R),
36:('Camera PAN servo',S),6:('Common GND (battery, L298N, buck, servos, relay)',G)}
fig,ax=plt.subplots(figsize=(12,8.6)); ax.set_xlim(0,12); ax.set_ylim(-1.9,21.3); ax.axis('off')
ax.add_patch(FancyBboxPatch((5.25,0.3),1.5,20.4,boxstyle='round,pad=0.05,rounding_size=0.2',fc='#1E6B30',ec='#0d3d19'))
ax.text(6,20.95,'Raspberry Pi 4 — 40-pin header',ha='center',fontsize=12,fontweight='bold')
for i in range(20):
    y=20.2-i
    for side,pin in ((0,2*i+1),(1,2*i+2)):
        x=5.65 if side==0 else 6.35
        on=pin in use; c=use[pin][1] if on else '#bbbbbb'
        ax.add_patch(Circle((x,y),0.2,fc=c if on else '#d9d9d9',ec='k',lw=0.8))
        ax.text(x,y,str(pin),ha='center',va='center',fontsize=6.5,color='white' if on else 'k')
        nx= 5.3 if side==0 else 6.7
        ax.text(nx-0.05 if side==0 else nx+0.05,y,names[pin],ha='right' if side==0 else 'left',va='center',
                fontsize=7.5,color='white',alpha=0) # spacer
        lx = 4.95 if side==0 else 7.05
        ax.text(lx,y,names[pin],ha='right' if side==0 else 'left',va='center',fontsize=8.5,
                color=c if on else '#888',fontweight='bold' if on else 'normal')
        if on:
            txt=use[pin][0]
            if side==0:
                ax.plot([3.9,4.2],[y,y],color=c,lw=1.5)
                ax.text(3.8,y,txt,ha='right',va='center',fontsize=9,color=c)
            else:
                ax.plot([7.8,8.1],[y,y],color=c,lw=1.5)
                ax.text(8.2,y,txt,ha='left',va='center',fontsize=9,color=c)
leg=[(L,'L298N #1 (left side: M1 Front-Left, M2 Rear-Left)'),(R,'L298N #2 (right side: M3 Front-Right, M4 Rear-Right)'),
     (S,'Servos (5 V rail, pigpio PWM)'),(P,'Pump relay'),(G,'Ground')]
for k,(c,t) in enumerate(leg):
    x=0.6+ (k%2)*6.0; y=-0.3-(k//2)*0.6
    ax.add_patch(Rectangle((x,y-0.18),0.35,0.36,fc=c)); ax.text(x+0.5,y,t,va='center',fontsize=8.8)
plt.savefig('../hardware/diagrams/fig_gpio_wiring.png',dpi=220,bbox_inches='tight')
