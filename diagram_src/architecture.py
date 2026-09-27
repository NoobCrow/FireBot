import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
plt.rcParams['font.family']='DejaVu Sans'
fig,ax=plt.subplots(figsize=(13,6.2)); ax.set_xlim(0,13); ax.set_ylim(-0.15,6.2); ax.axis('off')
def box(x,y,w,h,t,fc,fs=10,bold=False,ec='#333',lw=1.2):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.02,rounding_size=0.12",fc=fc,ec=ec,lw=lw))
    ax.text(x+w/2,y+h/2,t,ha='center',va='center',fontsize=fs,fontweight='bold' if bold else 'normal')
    return (x,y,w,h)
def group(x,y,w,h,t,ec='#999',ls='--',lw=1.2):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.02,rounding_size=0.15",fc='none',ec=ec,ls=ls,lw=lw))
    ax.text(x+w/2,y+h-0.22,t,ha='center',va='center',fontsize=11.5,fontweight='bold',color='#0046A0' if ec!='#999' else '#333')
def arr(p,q,c='#222',ls='-',lab=None,lx=0,ly=0.12):
    ax.annotate('',xy=q,xytext=p,arrowprops=dict(arrowstyle='-|>',color=c,lw=1.4,ls=ls,mutation_scale=14))
    if lab: ax.text((p[0]+q[0])/2+lx,(p[1]+q[1])/2+ly,lab,ha='center',fontsize=8.5,color=c,bbox=dict(fc='white',ec='none',pad=0.5))

# groups
group(0.2,3.3,2.6,2.7,'Perception')
group(0.2,0.2,2.6,2.8,'Power')
group(3.3,0.2,4.6,5.8,'Raspberry Pi 4 (Edge AI, on-device)',ec='#0046A0',ls='-',lw=1.8)
group(8.4,0.2,4.4,5.8,'Actuation')

cam=box(0.5,4.4,2.0,0.8,'Pi Camera v1.3\n640×480 RGB','#D6E9F8')
pt =box(0.5,3.5,2.0,0.7,'Pan / Tilt servos\nGPIO 16 / GPIO 10','#D6E9F8',fs=9)
bat=box(0.5,1.7,2.0,0.75,'3S LiPo\n11.1 V','#FDE2C8')
bk =box(0.5,0.45,2.0,0.85,'Buck converter\n11.1 V → 5 V','#FDE2C8')

cap=box(3.7,4.5,3.8,0.7,'Picamera2 frame capture','#E4ECF7')
yo =box(3.7,3.35,3.8,0.8,'YOLO fire detector (NCNN, CPU)\nconf ≥ 0.40 · NMS IoU 0.45','#E4ECF7',fs=9.5)
fsm=box(3.7,1.55,3.8,1.4,'Control state machine\nSEARCH → TRACK → APPROACH\n→ HOLD → SPRAY\n(+ local REACQUIRE)','#E4ECF7',fs=9.5,bold=False)
lg =box(3.7,0.45,3.8,0.7,'Live display + console log','#EEEEEE',fs=9.5)

l298=box(8.7,4.4,1.9,0.8,'2 × L298N\nIN1/IN2 + PWM EN','#DDF0DD',fs=9)
mot =box(10.8,4.4,1.8,0.8,'4 × DC motors\ndiff. drive','#DDF0DD',fs=9)
rel =box(8.7,2.9,1.9,0.8,'Relay module\nGPIO 9 (active HIGH)','#F9D5D5',fs=8.8)
pmp =box(10.8,2.9,1.8,0.8,'Water pump\n+ reservoir','#F9D5D5',fs=9)
hose=box(8.7,1.4,1.9,0.8,'Hose sweep servo\nGPIO 13','#F9D5D5',fs=9)
noz =box(10.8,1.4,1.8,0.8,'Hose / nozzle','#F9D5D5',fs=9)

arr((2.5,4.8),(3.7,4.85),lab='CSI')
arr((5.6,4.5),(5.6,4.15)); arr((5.6,3.35),(5.6,2.95))
arr((5.6,1.55),(5.6,1.15),ls='--')
arr((3.7,2.1),(2.5,3.85),lab='pan / tilt\ncommands',lx=0.15,ly=-0.2)
arr((1.5,4.2),(1.5,4.4),ls='--')
arr((7.5,2.7),(8.7,4.6),lab='direction + PWM',lx=-0.35,ly=0.2)
arr((7.5,2.3),(8.7,3.3),lab='pump on/off',lx=-0.3,ly=0.1)
arr((7.5,1.9),(8.7,1.8),lab='sweep',lx=-0.2,ly=0.1)
arr((10.6,4.8),(10.8,4.8)); arr((10.6,3.3),(10.8,3.3)); arr((10.6,1.8),(10.8,1.8),ls='--')
arr((11.7,2.9),(11.7,2.2),c='#1f77b4',lab='water',lx=0.35,ly=-0.05)
# power
arr((1.5,1.7),(1.5,1.3),c='#C06000')
ax.plot([2.5,3.05,3.05],[2.07,2.07,0.0],color='#C06000',lw=1.4)
ax.plot([3.05,8.15,8.15],[0.0,0.0,4.8],color='#C06000',lw=1.4)
arr((8.15,4.8),(8.7,4.8),c='#C06000'); ax.text(8.2,0.6,'11.1 V',rotation=90,fontsize=8.5,color='#C06000')
arr((2.5,0.85),(3.3,0.85),c='#C06000'); ax.text(2.9,0.95,'5 V',fontsize=8.5,color='#C06000',ha='center')
ax.text(1.5,0.28,'5 V also feeds servos + relay',ha='center',fontsize=7.8,color='#C06000')
plt.savefig('../hardware/diagrams/fig_architecture.png',dpi=220,bbox_inches='tight'); 
