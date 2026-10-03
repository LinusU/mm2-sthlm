# Landstingshuset park fence

The original native PKG panels follow OSM fence `way/28975066` along Pilgatan,
Hantverkargatan and Södra Agnegatan, with `way/1013162648` continuing the eastern
edge. Their open endpoints remain open; the generator does not infer a southern
perimeter fence or connect the two ways across the service entrance.

`config/overrides/landstingshuset-fence.json` records the user's annotated map and
photograph separately from the OSM snapshot. It authors three entrances at sourced
path junction nodes: Pilgatan near the northwest corner, central Hantverkargatan,
and the lower Södra Agnegatan pedestrian entrance. Widths of 10, 8 and 6 metres
respectively are visual approximations from that annotation, not survey data.

Dark iron bars and rails have spear tips, muted gold collars, substantial posts
and a low grey stone plinth, matching the photograph. Panels are at most 2.5 metres
long. Terrain samples at their centre and endpoints ground and slope each mesh.
The native Directed path orientation places local +X along the source fence.
Each panel has a narrow independently rotated native collision box and one
breakable debris set, so impacts remove a small section rather than an entire
park edge. Iron, collars and plinth form three debris parts. Debris geometry is original project art.

`fences.write(out, city, height, source=None)` emits assets and returns native
placement metadata. The caller appends those records to the shared prop pathset;
this module never overwrites the tree placements or modifies engine code.

Unit checks cover all three clear openings, retained sourced fence length,
open ends, terrain grounding, narrow panel geometry, clipping, native asset
records and preservation of the caller's pathset. Actual visual and impact checks
must be performed in-engine; generator checks alone are not visual evidence.

# Norr Mälarstrand plank fence and gate

The second user annotation adds the southern property frontage along Norr
Mälarstrand. It uses the southern subchain of sourced fence `way/28975067`,
from node `318607131` by Pilgatan to `4325198572` on the eastern side. The short
western return in that way is excluded because the annotation marks the frontage.
This is separate from the iron park perimeter farther north.

The authored wooden gate is centered on source node `318607298`, where the
southern service drive approaches the fence. Its 5 metre width is an approximation
from the photograph and annotation. It fills the opening with a native breakable
prop: two slatted leaves with diagonal braces break into two separate debris
parts when hit. Adjacent panels use closely spaced vertical planks and rear rails
in dark desaturated green grey. Their assets are also native breakable props.
`gate_node` and `gate_width` are emitted for reproducible drive and impact checks.

## Actual engine verification

`evidence/fences/acceptance.json` records the tested package checksum, engine
revision `74c60897ef8472aceafea0bb871f2e46615a095c`, exact launch commands and
unmodified in-game screenshots at both reported cameras. The full-throttle
native car probe broke the gate into two active debris leaves, travelled 36.2 m,
and finished 13.7 m beyond its plane with four wheels grounded, finite state and
no resets. The iron and plank frontage screenshots were inspected in-game.
The map's 38 offline tests, build and validation passed before this commit.
