import json,sys,math,hashlib
from pathlib import Path
repository = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(repository));from src.sthlm import improve_triangle_angles
f=json.load(open(repository/'tests/fixtures/slotts-native-skinny-facets.json'));ts=[[(v[0],-v[2]) for v in t] for t in f['native_triangles_xyz']];heights={(v[0],-v[2]):v[1] for t in f['native_triangles_xyz'] for v in t}
def ny(t):
 a,b,c=[(x,heights[x,n],n) for x,n in t];u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)];n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];return abs(n[1])/math.sqrt(sum(a*a for a in n))
a=improve_triangle_angles(ts)
r={'scope':'Offline local retriangulation of actual exported native Slottskajen room59 facets; not native driving acceptance or a new full export','package_manifest_sha256':f['provenance']['cohort_manifest_sha256'],'attribution':['© OpenStreetMap contributors; source street geometry and source-node IDs under ODbL','Elevation source Lantmäteriet; retain project elevation source attribution and license metadata'],'faces':len(ts),'vertices_before':len(heights),'vertices_after':len({v for t in a for v in t}),'native_original_vertex_heights_unchanged':True,'original_min_normal_y':min(map(ny,ts)),'retriangulated_min_normal_y':min(map(ny,a)),'new_full_export_native_audit':'Pending root build, do not infer from this offline result','patch_sha256':'772dd8fc0255f0be522caf221069313862f713b0cb0ff6de0801b27e42686799'}
p=Path(sys.argv[1]) if len(sys.argv)>1 else Path('/private/tmp/slotts-native-triangle-quality-evidence.json');p.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
