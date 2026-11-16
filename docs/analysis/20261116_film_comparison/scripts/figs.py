import numpy as np, pickle, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
from scipy.ndimage import median_filter
from load import load
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.edgecolor':'#52514e','axes.labelcolor':'#0b0b0b','xtick.color':'#52514e','ytick.color':'#52514e'})
s=load('PolyAlDosCal_20261013_161112_732305_000006.raw')[:, ::-1, ::-1]
bm=np.load('bm.npy')
cam=np.array([42.2357,42.9171,42.4502,41.4009]); film=np.array([40.94,39.61,39.75,39.70]); lab=['B1','A1','A2','A3']
k=1.0563
import csv
rows=list(csv.DictReader(open('crosscal.csv')))[:4]
fig,axs=plt.subplots(1,4,figsize=(13,3.9),dpi=150)
cx0,cy0,h=862,437,130
for i,ax in enumerate(axs):
    d=median_filter((s[i]-bm),3)[cy0-h:cy0+h,cx0-h:cx0+h]
    im=ax.imshow(d,cmap='magma',vmin=0,vmax=48,extent=[cx0-h,cx0+h,cy0+h,cy0-h])
    r=rows[i]
    for n in (1,2):
        e=Ellipse((float(r['center_x']),float(r['center_y'])),2*n*float(r['sigma_x']),2*n*float(r['sigma_y']),angle=float(r['theta_deg']),fill=False,ec='#7fd3ff',lw=1.0,ls='-' if n==1 else '--')
        ax.add_patch(e)
    ax.set_title(f'Pulse {i+1} → film well {lab[i]}',fontsize=11,color='#0b0b0b')
    ax.text(0.03,0.04,f'camera {cam[i]/k:.1f} Gy\nfilm   {film[i]:.2f} Gy',transform=ax.transAxes,color='white',fontsize=10,family='DejaVu Sans Mono',va='bottom')
    ax.set_xticks([]);ax.set_yticks([])
cb=fig.colorbar(im,ax=axs,fraction=0.015,pad=0.01); cb.set_label('net DN (3×3 median)')
fig.savefig('fig/frames.png',bbox_inches='tight',facecolor='white')

# comparison
fig,ax=plt.subplots(1,2,figsize=(11,4.2),dpi=150,gridspec_kw={'width_ratios':[1.1,1]})
x=np.arange(4)
camGy=cam/k
ax[0].plot(x-0.08,film,'o',ms=9,color='#eb6834',label='EBT-XD film peak dose')
ax[0].plot(x+0.08,camGy,'s',ms=9,color='#2a78d6',label='DoseCam fitted peak ÷ 1.056 DN/Gy')
ax[0].set_xticks(x,[f'Pulse {i+1}\n{l}' for i,l in enumerate(lab)]); ax[0].set_ylabel('Peak dose (Gy)')
ax[0].set_ylim(38.5,41.5); ax[0].set_axisbelow(True); ax[0].grid(axis='y',color='#e6e5e1'); ax[0].legend(frameon=False,fontsize=9,loc='upper right')
for sp in ['top','right']: ax[0].spines[sp].set_visible(False)
dev=(camGy/film-1)*100
ax[1].bar(x,dev,color=['#2a78d6']*4,width=0.55,zorder=3)
ax[1].set_axisbelow(True); ax[1].axhline(0,color='#52514e',lw=1)
for xi,dv in zip(x,dev): ax[1].text(xi,dv+(0.15 if dv>0 else -0.15),f'{dv:+.1f}%',ha='center',va='bottom' if dv>0 else 'top',fontsize=10)
ax[1].axhspan(-2.2,2.2,color='#fbeee8',lw=0,zorder=0)
ax[1].text(3.45,1.95,'observed scatter\n±2.2% (1σ)',ha='right',va='top',fontsize=8.5,color='#52514e')
ax[1].set_xticks(x,lab); ax[1].set_ylabel('Camera − film (%)'); ax[1].set_ylim(-3.6,3.6); ax[1].grid(axis='y',color='#e6e5e1')
for sp in ['top','right']: ax[1].spines[sp].set_visible(False)
fig.tight_layout(); fig.savefig('fig/compare.png',bbox_inches='tight',facecolor='white')

# targeting frame
t=load('PolyAlDosCal_20261013_160908_654522_000004.raw')[0][::-1,::-1]
fig,ax=plt.subplots(figsize=(6,4.5),dpi=120)
lo,hi=np.percentile(t,[0.5,99.7]); ax.imshow(t,cmap='gray',vmin=lo,vmax=hi); ax.set_xticks([]);ax.set_yticks([])
ax.add_patch(Ellipse((860,438),4*19.6,4*34.7,angle=-15,fill=False,ec='#eb6834',lw=1.5))
fig.savefig('fig/targeting_raw.png',bbox_inches='tight')
