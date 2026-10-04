import sys,json,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
from src.sthlm import improve_triangle_angles
exec(open(Path(__file__).with_name('audit-slotts-native.py')).read().split('records=[]')[0])
ts=[[(v[0],-v[2]) for v in t] for f,r,tex,t,p in tris if r==59 and tex=='sthlm_oldtown_setts'];levels={(v[0],-v[2]):v[1] for f,r,tex,t,p in tris if r==59 and tex=='sthlm_oldtown_setts' for v in t}
def ny(t):
 a,b,c=[(x,levels[x,n],n) for x,n in t];u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)];n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];return abs(n[1])/math.sqrt(sum(a*a for a in n))
print('native',len(ts),min(map(ny,ts)))
for i in range(3):ts=improve_triangle_angles(ts);print('extra12',i,min(map(ny,ts)))
