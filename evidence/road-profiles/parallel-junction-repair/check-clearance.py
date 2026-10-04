import sys,json,copy
from pathlib import Path
import numpy as np
from shapely.geometry import Point,LineString
sys.path.insert(0,'/private/tmp/checkpoint-profile-repair/src')
from elevation import align_parallel_bridge_profiles
from bridges import crossing_constraints

def probe(roads, bridge_ids):
    lookup={r['id']:r for r in roads};out=[]
    def height(road_id, xy):
        points=lookup[road_id]['elevated_points'];line=LineString([p[:2] for p in points]);stations=[0.0]
        import math
        for a,b in zip(points,points[1:]):stations.append(stations[-1]+math.dist(a[:2],b[:2]))
        return float(np.interp(line.project(Point(xy)),stations,[p[2] for p in points]))
    for p in crossing_constraints(roads, bridge_ids):
        p['actual_vertical_separation_m']=height(p['upper'],p['position'])-height(p['lower'],p['position']);out.append(p)
    return out

fixture=json.loads(Path('/private/tmp/checkpoint-profile-repair/tests/fixtures/bridge-alignment-source-junctions.json').read_text());old=copy.deepcopy(fixture['roads']);new=copy.deepcopy(old);align_parallel_bridge_profiles(new,anchor_nodes=fixture['anchor_nodes']);cases=[('exact123bridgefixture',old,new,[r['id'] for r in old])]
c=json.loads(Path('/private/tmp/checkpoint-junction261f-mods/stockholm/normalized.json').read_text());old=copy.deepcopy(c['roads']);new=copy.deepcopy(old);bridges=set(c['bridge_ways']);ordinary=[r for r in new if r['id'] not in bridges and r['id'] not in set(c.get('tunnel_ways',[]))];align_parallel_bridge_profiles([r for r in new if r['id'] in bridges],anchor_nodes={n for r in ordinary for n in r['nodes']});cases.append(('fullimmutable261sourcegraph',old,new,c['bridge_ways']))
report={'scope':'Read-only actual source-profile clearance analysis before/after alignment and exact-node reconciliation. No changes to root source or native package. Native fixed-point material surfaces are not evaluated by this profile probe.','cases':[]}
for name,old,new,ids in cases:
    a=probe(old,ids);b=probe(new,ids);rows=[]
    for p,q in zip(a,b):
        assert (p['upper'],p['lower'],p['position'])==(q['upper'],q['lower'],q['position'])
        rows.append({**p,'before_m':p['actual_vertical_separation_m'],'after_m':q['actual_vertical_separation_m'],'delta_m':q['actual_vertical_separation_m']-p['actual_vertical_separation_m']})
    reduced=[r for r in rows if r['delta_m'] < -1e-7];violations=[r for r in rows if r['after_m']<5.5-.03];case={'name':name,'probe_count':len(rows),'minimum_before_m':min(r['before_m'] for r in rows),'minimum_after_m':min(r['after_m'] for r in rows),'reduced_clearances':reduced,'after_below_tolerance':violations,'probes':rows};report['cases'].append(case);print(name,'probes',len(rows),'min',case['minimum_before_m'],case['minimum_after_m'],'reduced',len(reduced),'violations',len(violations));print(reduced)
Path('/private/tmp/checkpoint-bridge-profile-clearance-analysis.json').write_text(json.dumps(report,indent=2)+'\n')
