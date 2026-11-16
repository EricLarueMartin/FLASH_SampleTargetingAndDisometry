import numpy as np
from scipy.optimize import least_squares
from scipy.ndimage import median_filter
from load import load
s=load('PolyAlDosCal_20261013_161112_732305_000006.raw')[:, ::-1, ::-1]
b=load('Alanine_20261013_145026_730724_000002.raw')[:, ::-1, ::-1]
bm=np.median(b,axis=0)
np.save('bm.npy',bm)
y0,x0=175,600; H=520
Y,X=np.mgrid[y0:y0+H,x0:x0+H].astype(float)
def model(p):
    A,cx,cy,sx,sy,th,c=p
    t=np.deg2rad(th); dx=X-cx; dy=Y-cy
    u= dx*np.cos(t)+dy*np.sin(t); v=-dx*np.sin(t)+dy*np.cos(t)
    return A*np.exp(-0.5*(u/sx)**2-0.5*(v/sy)**2)+c
res=[]
for i,f in enumerate(s):
    d=(f-bm)[y0:y0+H,x0:x0+H]
    # hit mask: compare to 5x5 median
    med=median_filter(d,5)
    mask=np.abs(d-med)<np.maximum(12,7*np.sqrt(2+0.3*np.clip(med,0,None)))
    p=[42,860,437,19,34,-15,0]
    for it in range(3):
        r=least_squares(lambda p:(model(p)-d)[mask],p)
        p=r.x; m=model(p); resid=d-m
        s0=1.4826*np.median(np.abs(resid[mask]))
        mask=(np.abs(resid)<7*np.sqrt(s0**2+0.3*np.clip(m-p[6],0,None)))&(np.abs(d-med)<np.maximum(12,7*np.sqrt(2+0.3*np.clip(med,0,None))))
    J=r.jac; cov=np.linalg.inv(J.T@J)*np.var(resid[mask])
    e=np.sqrt(np.diag(cov))
    print(i, np.round(p,3), 'err',np.round(e,3), 'masked',(~mask).sum(), 'rms',resid[mask].std().round(3))
    res.append(dict(p=p,e=e,d=d,m=m,mask=mask))
np.save('fits.npy',np.array([np.r_[r_['p'],r_['e']] for r_ in res]))
import pickle; pickle.dump(res,open('res.pkl','wb'))
