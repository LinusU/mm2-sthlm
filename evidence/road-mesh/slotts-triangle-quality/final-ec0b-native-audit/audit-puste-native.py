import sys,json,math
from pathlib import Path
sys.path.insert(0,'/Users/linus/coding/mm2-sthlm/tests');from test_vertex_pools import read_native
from shapely.geometry import Polygon,Point
root=Path(sys.argv[1])/'city/stockholm.parts';tris=[]
for file in [*root.glob('part_1_-2*.psdl'),*root.glob('part_1_-1*.psdl')]:
 w=read_native(file)
 for rid,(_,attrs,flags) in enumerate(w.rooms,1):
  k=0;texture=''
  while k<len(attrs):
   code=attrs[k];kind=(code>>3)&15;counts={10:1,2:4,5:3,6:3,11:6,7:4};words=attrs[k+1:k+1+counts[kind]]
   if kind==10:texture=w.textures[((code&7)*256+words[0])-1]
   if kind in (2,5,6):
    vs=[w.vertices[i] for i in words]
    for inds in ([(0,1,2),(2,1,3)] if kind==2 else [(0,1,2)]):
     t=[vs[i] for i in inds];xy=Polygon([(v[0],v[2]) for v in t])
     if not xy.is_empty and xy.intersects(Polygon([(1265,810),(1277,810),(1277,822),(1265,822)])):tris.append((file.name,rid,texture,t,xy))
   k+=counts[kind]+1
records=[]
for cx,cz in [(1271.601,816.1808)]:
 rows=[];walls=[]
 for dx in [i*.25 for i in range(-12,13)]:
  for dz in [i*.25 for i in range(-12,13)]:
   x,z=cx+dx,cz+dz;hits=[]
   for file,rid,tex,t,poly in tris:
    if not poly.covers(Point(x,z)):continue
    a,b,c=t;den=(b[2]-c[2])*(a[0]-c[0])+(c[0]-b[0])*(a[2]-c[2])
    if abs(den)<1e-10:continue
    u=((b[2]-c[2])*(x-c[0])+(c[0]-b[0])*(z-c[2]))/den;v=((c[2]-a[2])*(x-c[0])+(a[0]-c[0])*(z-c[2]))/den;y=u*a[1]+v*b[1]+(1-u-v)*c[1];hits.append([y,tex,rid])
   rows.append({'xz':[x,z],'offset':[dx,dz],'hits':hits})
 for file,rid,tex,t,poly in tris:
  a,b,c=t;ab=[b[i]-a[i] for i in range(3)];ac=[c[i]-a[i] for i in range(3)];n=[ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0]];norm=math.sqrt(sum(v*v for v in n))
  if norm<1e-10:continue
  ny=abs(n[1])/norm;d=poly.distance(Point(cx,cz))
  if ny<.9 and d<4:walls.append({'distance_xz':d,'normal_y':ny,'texture':tex,'room':rid,'triangle':t})
 records.append({'centre':[cx,cz],'grid':rows,'near_steep_faces':sorted(walls,key=lambda r:r['distance_xz'])})
Path(sys.argv[2]).write_text(json.dumps(records,indent=2)+'\n')
for r in records:
 heights=[h[0] for q in r['grid'] for h in q['hits']];print(r['centre'],'range',min(heights),max(heights),'steep',len(r['near_steep_faces']));print(json.dumps(r['near_steep_faces'][:3],indent=2))
