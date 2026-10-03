# Stockholm bridge inventory

Source audit: 2026-10-03. Feature identifiers come from the checked-in
`sources/expanded/osm.json.gz`, never from an invented route. Locations below
are approximate longitude/latitude averages of source vertices, not surveyed
bridge centres. The approved boundary and explicit crossing exclusions take
precedence over a name or the acquisition envelope.

All included motor bridge corridors receive exact exported road-triangle
undersides, source-edge railing openings at real connecting nodes, and short
longitudinal girders. Structural meshes add no driveable connections. Colours,
member dimensions, arch spacing and elevations are original visual/gameplay
estimates. Water-crossing arch members are suppressed anywhere they would
occupy another source road corridor. No photograph pixels are shipped.

## Main connections

"Playable candidate" means the source has a motor road and the crossing needs
its complete source corridor selected by normalization. It is not a claim that
an integrated native vehicle run has passed. Foot/cycle bridges are scenery;
they do not become invented motor-road links. The runtime
`bridge_structure_rules.structures` enumerates the actual exported selections.

| Bridge | Approximate lon, lat | Motor source way IDs | Inventory status / appearance |
| --- | --- | --- | --- |
| Barnhusbron | 18.04705, 59.33549 | 22884861, 836036317, 836036318, 1278897963, 1278897964, 1278897965 | Playable candidate; girder |
| Beckholmsbron | 18.10204, 59.322 | 5173793 | Playable candidate; girder; baseline mask truncation requires repair |
| Bobergsbron | 18.08464, 59.35247 | 159170191, 738678822, 738678823 | Playable candidate; girder |
| Centralbron | 18.06137, 59.32704 | 4802609, 4830965, 5788349, 5788351, 8513540, 20278074, 20278673, 23000195, 23000196, 27423358, 35477773, 35477774, 233761058, 233761064, 261818767, 705708959, 1126757833, 1126757835 | Playable candidate; girder |
| Djurgårdsbron | 18.09385, 59.33113 | 23620161, 1088248978, 1088248984 | Playable candidate; steel arch |
| Djurgårdsbrunnsbron | 18.13219, 59.32968 | 10504639 | Playable candidate; girder |
| Ekelundsbron | 18.01296, 59.34065 | 237312768 | Playable candidate; girder; northern boundary selection controls approach |
| Hebbes bro | 18.06604, 59.32388 | none | Scenery / omitted motor topology; pedestrian or cycle source |
| Kastellholmsbron | 18.08767, 59.3237 | 43023609 | Playable candidate; girder |
| Kungsbron | 18.05226, 59.33267 | 4488522, 4488523, 4488526, 4491179, 27423309, 28217634, 127674505, 167816638, 189936526, 261818776, 467760758, 1337963903 | Playable candidate; girder |
| Lilla Sjötullsbron | 18.14705, 59.32658 | none | Scenery / omitted motor topology; pedestrian or cycle source |
| Lilla Västerbron | 18.02218, 59.32936 | 30687722, 100905137, 1338916516, 1338916517 | Playable candidate; girder |
| Långholmsbron | 18.02814, 59.31933 | 56195833 | Playable candidate; girder |
| Mariebergsbron | 18.00975, 59.32574 | 4647975, 1434814093 | Playable candidate; girder |
| Norrbro | 18.07001, 59.32824 | 120287587, 120288408 | Playable candidate; stone arch |
| Pålsundsbron | 18.03422, 59.32017 | 10433 | Playable candidate; girder |
| Reimersholmsbron | 18.02615, 59.31849 | 23049017 | Playable candidate; girder |
| Riddarholmsbron | 18.06563, 59.32538 | 120346762, 165626101, 335216928 | Playable candidate; girder |
| Riksbron | 18.06708, 59.32821 | none | Scenery / omitted motor topology; pedestrian or cycle source |
| Sankt Eriksbron | 18.03491, 59.33743 | 4491048, 155195596 | Playable candidate; girder |
| Skeppsholmsbron | 18.07927, 59.32724 | 4741923 | Playable candidate; girder |
| Slussbron | 18.07378, 59.321 | 770895951, 770895959 | Playable candidate; girder |
| Stadshusbron | 18.05659, 59.32819 | 4647958, 680061607 | Playable candidate; girder |
| Stallbron | 18.06834, 59.32699 | none | Scenery / omitted motor topology; pedestrian or cycle source |
| Strömbron | 18.07313, 59.3289 | 35969580, 959169606, 1337078899 | Playable candidate; girder |
| Strömsborgsbron | 18.0641, 59.32724 | 5120305, 386722952 | Playable candidate; girder; Strömsborg missing from baseline included island references |
| Vasabron | 18.06388, 59.32763 | 28345891, 162142154 | Playable candidate; steel arch |
| Västerbron | 18.0299, 59.32196 | 28274837, 49778495 | Playable candidate; authored twin steel arches |

## Source island anchors

`config/overrides/bridge-land-anchors.json` records deterministic corrections
inside the existing Djurgården/Gamla stan scope. Beckholmen's reference is
(18.100005, 59.320760), inside the 60,647 m² source land component that
contains bridge endpoint node 35970109 and Beckholmsvägen way 5173795.
The original (18.096, 59.324) reference pointed at the wrong land component.
[Stockholm city's Beckholmen plan](https://vaxer.stockholm/projekt/djurgarden/beckholmen/)
independently confirms island identity.

Strömsborg's reference is (18.063056, 59.327113), inside the 2,276 m² source
land component and named `place=islet` way 4879618. Its bridge endpoint
180940 connects Strömsborgsbron way 5120305 to island service way 109578671.
[Stockholm city's Vasabron project](https://vaxer.stockholm/projekt/norrmalm/forstarkning-av-vasabron/)
confirms the island access relationship. Include the sourced island, then
verify that full bridge source lines fit the corrected mask; these anchors
never authorize accepting a bridge outside the approved boundary.

## Internal viaducts and ramps

The earlier named whitelist silently dropped Centralbron (`highway=trunk`),
its ramps and many source viaduct streets. Source bridge tags inside the mask
must select eligible motor roads independent of the bridge's name. Preserve
source nodes/layers and original excluded routes. Relevant groups include
Klarabergsviadukten, Blekholmsterrassen, Blekholmstorget, Kungsbroplan,
Fleminggatan, Gjörwellsgatan, Dalagatan, Malmskillnadsgatan, Regeringsgatan,
Mäster Samuelsgatan, Nils Ericsons Plan, Ringvägen, Swedenborgsgatan,
Rosenlundsgatan and source unnamed motor ramps. Their structures use the
same original conservative girder style, with no guessed support piers in
lower traffic corridors.

Centralbron ramps include Vattugatan, Herkuleskopplet, Klarasjörampen,
Klarastrandskopplet, Blekholmskopplet, Norra/Södra Klarabergskopplet,
Västra/Östra Kungsbrokopplet, Riddarfjärdsavfarten/-påfarten and Söderkopplet.
Whether individual tails are included is decided from the approved mask and
source connectivity, never by straight-line reconstruction across missing data.

## Boundary scenery / excluded crossings

Tranebergsbron, the bridges to Lilla/Stora Essingen, Lidingö crossings and
southern bridges leaving Södermalm stay impassable. The southern source
names include Liljeholmsbron, Årstabron, Skansbron, Skanstullsbron and
Johanneshovsbron. A short bridge-tagged approach can lie completely inside
the mask while its named route leaves it; this does not override exclusion.
No playable scenery connection has been added.

Railway-only bridges and metro bridge structures are omitted from driveable
roads. Pedestrian/cycle-only crossings above are recorded as scenery/omitted
motor topology; their visual export is separate from road connectivity.

## Appearance research

References checked on 2026-10-03. Descriptions are intentionally simplified:

- [Västerbron, Stockholmskällan](https://stockholmskallan.stockholm.se/teman/Stockholmsplatser/vasterbron/): steel arch form supports the original twin-arch mesh. Source alignment and user reference photographs informed the existing estimate.
- [Norrbro, Stockholmskällan](https://stockholmskallan.stockholm.se/teman/Stockholmsplatser/norrbro/): stone bridge; muted masonry ribs distinguish it from modern concrete slabs. The generator's arch spacing is an estimate, not an exact reconstruction.
- [Vasabron reinforcement, Stockholm city](https://vaxer.stockholm/projekt/norrmalm/forstarkning-av-vasabron/): steel arches over Norrström; simple dark ribs represent their outline. Current engineering reinforcement is not claimed to be fully modeled.
- [Djurgårdsbron, City Museum photograph and description](https://stockholmskallan.stockholm.se/post/2560): three steel spans; small arch ribs use estimated spacing. Original 1897 photograph, unknown photographer, Stadsmuseet SSMC001516. Historical appearance reference only, no image pixels copied.
- [Djurgårdsbrunnsbron, Samfundet S:t Erik / Stockholmskällan](https://stockholmskallan.stockholm.se/post/29442): preserved swing bridge; the map represents a fixed closed crossing, with no invented opening animation.
- [Skeppsholmsbron foundation work, Statens fastighetsverk](https://www.sfv.se/uppdraget/byggprojekt/grundforstarkning-av-skeppsholmsbron-i-stockholm): source connection between Blasieholmen and Skeppsholmen; conservative dark iron railing/girder estimate.
- [Skeppsholmsbron, Visit Stockholm](https://www.visitstockholm.se/o/skeppsholmsbron/): landmark gold crown remains a detail not yet reconstructed by the generic railing.
- [City library bridge bibliography, Stockholmskällan](https://stockholmskallan.stockholm.se/post/97): cross-checks the named main connections and viaduct coverage. The other small bridges currently use conservative girder outlines rather than unverified distinctive architecture.

## Clearance and reproducible probes

`bridges.crossing_constraints(roads, bridge_ids)` derives exact source
centreline crossings with strictly lower source layers. Shared OSM nodes are
real connections and are not underpass constraints. The estimated gameplay
separation is 5.5 m, including 0.74 m to the static slab underside. This is
not a survey or an assertion about legal vehicle clearance.

`bridges.enforce_crossing_clearance` runs on dense `elevated_points` before
road field construction. Cosine profile corrections extend at least 120 m
on each side and scale with lift to avoid abrupt ramps. Shared endpoint
heights propagate into connecting source ways. The report records source
IDs, local XY, lift, blend radius and remaining separation. Native coordinates
are `(local east, Y, -local north)`.

`bridges.crossing_report(city, road_field, deck_field)` records lower road Y,
deck Y, slab underside clearance and native XYZ, using source-aware fields
when available. Inspect Sankt Eriksbron / Kungsholms strand, Västerbron /
Långholmen lower streets, Lilla Västerbron / Rålambshovsleden, Centralbron /
Riddarholmen and Tegelbacken, Barnhusbron and Klarabergsviadukten. An actual
car drive must traverse deck approaches plus representative lower streets;
a screenshot or physics-only replay alone cannot establish visual evidence.

## Verification status

Focused tests cover exact native slab planes, winding/chunk bounds, genuine
source crossing classification, smooth lift/approach continuity and open
bridge railing portals. Required full unit checks pass in the isolated bridge
worktree (92 tests). Baseline offline build and validation passed (55 parts, 38,264 rooms).
The native-facet sink integration and final profile corrections require the
integrated rebuild. Integrated whitelist/profile build and native deck/below-
deck screenshots and vehicle drive results must be recorded after integration.
Do not treat this source inventory as completed native evidence.

## Integrated export rules

Native bridge roads and their structural railings are grouped by source layer.
A single XY union cannot represent a lower roadway and a deck crossing it.
Clearance adjustments use one height variable per actual source node and a
cosine envelope measured by cumulative source-graph distance, preserving
junctions without restarting the lift at each way split. Minimum authored road
separation is 5.5 m; nominal slab thickness is 0.7 m with a 0.04 m road gap.
All 160 detected ordered source-layer crossings pass the numerical clearance
check in the first integrated source profile run. This does not certify native
collision surfaces or every bridge approach: targeted driving remains separate.

Helgeandsholmen's earlier reference pointed inside Stadsholmen. The corrected
reference (18.0686, 59.3284) selects its actual 29,798 m² coast/water component,
including source parks120288399 and120288396. Boundary islands are selected
from real source land components, not drawn connections across water.

Targeted native driving now passes upper Centralbron way233761058 (59.2m)
and lower Vattugatan way4802608 (59.9m), zero impacts/resets and four contacts.
The combined full circuit also completes102/102 gates. Exact evidence and
source hashes are in evidence/overnight-driving/acceptance.json. Relative OSM
layer numbers alone are insufficient for adjacent ramps; overlapping source
profiles differing by more than0.5m are assigned different mesh union groups.
This is tested with same-layer stacked roads, then verified in the real map.

Reproduce the targeted courses after an offline build:

```sh
.venv/bin/python scripts/check-road-driving.py --engine .cache/engine/mm2 \
  --output /tmp/stockholm-road-probes \
  --case 233761058:44.51469027037892:119.51469027037892 \
  --case 4802608:84.08399315999104:159.08399315999105 \
  --case 30678772:1:64.21544084679579
```
