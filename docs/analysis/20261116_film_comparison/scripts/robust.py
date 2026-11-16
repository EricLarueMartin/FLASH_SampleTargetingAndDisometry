import numpy as np
from scipy.optimize import least_squares
from scipy.ndimage import median_filter, uniform_filter
from load import load
s=load('PolyAlDosCal_20261013_161112_732305_000006.raw')[:, ::-1, ::-1]
bm=np.load('bm.npy')
y0,x0=175,600; H=520
Y,X=np.mgrid[y0:y0+H,x0:x0+H].astype(float)
def model(p):
    A,cx,cy,sx,sy,th,c=p
    t=np.deg2rad(th); dx=X-cx; dy=Y-cy
    u= dx*np.cos(t)+dy*np.sin(t); v=-dx*np.sin(t)+dy*np.cos(t)
    return A*np.exp(-0.5*(u/sx)**2-0.5*(v/sy)**2)+c
def fit(d,mask):
    r=least_squares(lambda p:(model(p)-d)[mask],[42,862,437,20,35,-15,0]); return r.x
out={}
for i,f in enumerate(s):
    d=(f-bm)[y0:y0+H,x0:x0+H]; med=median_filter(d,5)
    row={}
    row['nomask']=fit(d,np.ones_like(d,bool))[0]
    for T in [12,20,30,50]:
        row[f'hit>{T}']=fit(d,(d-med)<T)[0]
    row['sym12']=fit(d,np.abs(d-med)<12)[0]
    row['med3']=fit(median_filter(d,3),np.ones_like(d,bool))[0]
    row['mean3_masked50']=None
    # pixel stats
    row['frac>50']=((d-med)>50).mean(); row['frac>20']=((d-med)>20).mean(); row['frac<-12']=((d-med)<-12).mean()
    print(i,{k:(round(v,3) if isinstance(v,float) else v) for k,v in row.items()})
