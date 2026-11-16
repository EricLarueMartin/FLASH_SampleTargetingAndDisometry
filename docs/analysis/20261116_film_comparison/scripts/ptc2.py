import numpy as np, pickle
res=pickle.load(open('res.pkl','rb'))
def cstd(x,n=4):
    x=x.copy()
    for _ in range(n):
        s=x.std(); mu=x.mean(); x=x[np.abs(x-mu)<3.5*s]
    return x.var()*1.0  # slight clip bias ignored
bins=np.array([0,0.5,2,4,7,10,14,18,22,26,30,34,38,45])
allrows=[]
for i,j in [(0,1),(2,3),(0,2),(1,3),(0,3),(1,2)]:
    ri,rj=res[i],res[j]
    mi=ri['m']-ri['p'][6]; mj=rj['m']-rj['p'][6]
    di=ri['d']-ri['p'][6]; dj=rj['d']-rj['p'][6]
    mask=ri['mask']&rj['mask']
    k=np.where(mj>0.3, mi/np.maximum(mj,1e-9), 1.0)
    x=di-k*dj
    for lo,hi in zip(bins[:-1],bins[1:]):
        sel=mask&(mi>=lo)&(mi<hi)&((mj>0.5)|(hi<=0.5))&(k<1.5)&(k>0.67)
        if sel.sum()<150: continue
        v=cstd(x[sel])
        allrows.append((i,j,mi[sel].mean(),(k[sel]**2).mean(),(k[sel]**2*mj[sel]).mean(),v,sel.sum()))
R=np.array(allrows)
# model: v = sb2*(1+k2) + g*(mi + k2 mj) + c*(mi^2 + k2 mj^2)~ c*mi^2*(1+k2)... use 2*mi^2 approx
A=np.c_[1+R[:,3], R[:,2]+R[:,4]]
sol,*_=np.linalg.lstsq(A,R[:,5],rcond=None); print('linear: sb2=%.3f g=%.4f DN/e (%.2f e/DN)'%(sol[0],sol[1],1/sol[1]))
A2=np.c_[1+R[:,3], R[:,2]+R[:,4], R[:,2]**2*(1+R[:,3])]
sol2,*_=np.linalg.lstsq(A2,R[:,5],rcond=None); print('quad: sb2=%.3f g=%.4f c=%.2e  -> rel multiplicative %.2f%%'%(sol2[0],sol2[1],sol2[2],100*np.sqrt(max(sol2[2],0))))
# bootstrap on pairs-of-bins
rng=np.random.default_rng(1); bs=[]
for _ in range(2000):
    idx=rng.integers(0,len(R),len(R)); s,*_=np.linalg.lstsq(A[idx],R[idx,5],rcond=None); bs.append(s[1])
print('g bootstrap sd', np.std(bs), ' e/DN 68%%: %.2f-%.2f'%tuple(1/np.percentile(bs,[84,16])))
for r in R: print(np.round(r,3))
# background variance from no-beam frames, same ROI, pair diffs
from load import load
b=load('Alanine_20261013_145026_730724_000002.raw')[:, ::-1, ::-1][:,175:695,600:1120]
dv=[cstd((b[n]-b[n+1]).ravel())/2 for n in range(0,33,2)]
print('no-beam per-frame temporal var (pairdiff/2):', np.round(np.median(dv),3))
