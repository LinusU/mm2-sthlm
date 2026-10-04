# Seventy additional Stockholm landmarks

This separate inventory extends the first thirty landmarks to exactly one hundred.
The source IDs resolve to retained building geometry in the checked-in expanded
OpenStreetMap snapshot. Their authored heights are approximate silhouette values,
not surveyed dimensions. Position, footprint and courtyard voids remain sourced.
No photographs, retail meshes, engine code or vehicle physics are included.

## Integration

Import `additional_landmarks.replaces` alongside the original landmark replacement
hook. Skip generic building/facade generation when either hook returns true. After
`landmarks.export(writer, city, out)`, call
`additional_landmarks.export(writer, city, out)` in the expanded non-minimal build.
The second export appends seventy metadata records to `city["landmarks"]` and
creates its own `ms_*` texture resources. Keep the first thirty export in place;
its existing dedicated art and `lm_door` texture are retained.

The inventory validator rejects source IDs reused as another landmark's primary
ID or nested alias, including the first thirty aliases. It also rejects duplicate
names, unknown form types and inverted heights. Missing normalized source features
are a build error rather than silently reducing the landmark count.

## Original artwork

Compact primitives distinguish roof form and massing: hipped/mansard roofs,
Renaissance stepped gables, pavilions, clock lanterns, round towers, church spires,
domes, open timber belfry legs, industrial chimney, roof skylight, glass slabs and
rooftop sign. Source courtyard holes remain open. Facade detail is procedural
window, masonry and trim texture art, rather than per-window mesh geometry.

Kastellet's round tower, flat wings and white parapet were checked against SFV's
published exterior photograph. Hällestadsstapeln's open base and shingled crown
were checked against the Skansen/DigitaltMuseum photograph. These photographs are
reference only and are not redistributed. Other reference/image pages are recorded
per entry below. Low polygon artwork omits sculpture, exact fenestration, complex
roof sculpture and interiors; reference links do not imply measured reconstruction.

## Source and verification

Pinned expanded OSM snapshot SHA-256: `18c1b3b750430d78bf3b6fb367856c14c3c43893172ee5f348a7c426caf82914`.

Tests normalize the checked-in snapshot offline, prove every feature lies inside
the included boundary, check the source name and authored anchor, verify one hundred
unique identities including nested aliases, generate every actual footprint through
the native PSDL writer, constrain heights/coordinates, preserve courtyard coverage,
and check all seventy original facade resources. Door panels use a four-centimetre
wall offset to avoid z-fighting. The isolated all-100 package passed Ruff, 133 unit tests, offline build and
validation. At 750 m packing it contains 90 native parts; the largest has 36,188
vertices. Twelve representative native engine captures were inspected for silhouette
and materials. Native continuous driving completed 102/102 checkpoints, travelling
1,503.6 m with zero impacts or resets. Exact commands, camera poses, package/source
hashes and distinct visual/physics records are in [ADDITIONAL-LANDMARK-QA.json](ADDITIONAL-LANDMARK-QA.json).

Evidence uses engine `b3d9804489bdcd576dd4b85b3f40fec75c545071` and the isolated
first-thirty plus additional-seventy build. Root combined features require a fresh
integration build and native acceptance. The seventy models were all source and
geometry tested; twelve were individually visually inspected. Offline geometry
checks and physics records are not in-engine visual evidence.

## Inventory

| Landmark | Source ID | Form | Body / total height (m) | Reference and image page |
| --- | --- | --- | --- | --- |
| Riksdagshuset | `relation/34395` | attic | 28 / 39 | [Reference](https://sv.wikipedia.org/wiki/Riksdagshuset_i_Stockholm) |
| Rosenbad | `relation/279566` | turrets | 28 / 38 | [Reference](https://sv.wikipedia.org/wiki/Rosenbad) |
| Arvfurstens palats | `relation/279567` | pediment | 15 / 20 | [Reference](https://sv.wikipedia.org/wiki/Arvfurstens_palats) |
| Sagerska huset | `way/141844590` | mansard | 18 / 24 | [Reference](https://sv.wikipedia.org/wiki/Sagerska_huset) |
| Centralposthuset | `relation/174078` | clock | 25 / 40 | [Reference](https://www.sfv.se/vara-fastigheter/sverige/stockholms-lan/regeringsbyggnader/centralposthuset) |
| Stockholms centralstation | `way/35473137` | pediment | 13 / 20 | [Reference](https://sv.wikipedia.org/wiki/Stockholms_centralstation) |
| Norra Latin | `way/18779654` | pavilions | 20 / 28 | [Reference](https://sv.wikipedia.org/wiki/Norra_Latin) |
| Riksbanken | `relation/17075471` | flat | 24 / 27 | [Reference](https://sv.wikipedia.org/wiki/Riksbankshuset) |
| NK | `way/1347756608` | sign | 26 / 39 | [Reference](https://stockholmskallan.stockholm.se/teman/foretagande-i-stockholm/nordiska-kompaniet/) |
| Hallwylska palatset | `relation/2440883` | turrets | 18 / 27 | [Reference](https://hallwylskamuseet.se/palatsets-historia/byggnaden/) |
| Bååtska palatset | `relation/2171352` | pediment | 16 / 23 | [Reference](https://sv.wikipedia.org/wiki/Bååtska_palatset) |
| Fersenska palatset | `relation/280988` | mansard | 20 / 27 | [Reference](https://sv.wikipedia.org/wiki/Fersenska_palatset) |
| Tändstickspalatset | `relation/2524360` | flat | 22 / 25 | [Reference](https://sv.wikipedia.org/wiki/Tändstickspalatset) |
| Börshuset | `relation/255059` | pediment | 19 / 29 | [Reference](https://sv.wikipedia.org/wiki/Börshuset) |
| Riddarhuset | `way/8049544` | mansard | 19 / 29 | [Reference](https://sv.wikipedia.org/wiki/Riddarhuspalatset) |
| Bondeska palatset | `way/16095343` | pavilions | 18 / 28 | [Reference](https://sv.wikipedia.org/wiki/Bondeska_palatset) |
| Tessinska palatset | `way/41079299` | hip | 20 / 26 | [Reference](https://sv.wikipedia.org/wiki/Tessinska_palatset) |
| Axel Oxenstiernas palats | `way/170363224` | hip | 18 / 24 | [Reference](https://sv.wikipedia.org/wiki/Axel_Oxenstiernas_palats) |
| Petersenska huset | `relation/229849` | stepped | 22 / 31 | [Reference](https://sv.wikipedia.org/wiki/Petersenska_huset) |
| Grillska huset | `way/170139121` | curved-gable | 17 / 24 | [Reference](https://sv.wikipedia.org/wiki/Grillska_huset) |
| Schantzska huset | `way/406181935` | stepped | 18 / 26 | [Reference](https://sv.wikipedia.org/wiki/Schantzska_huset) |
| Birger Jarls torn | `way/34590001` | roundtower | 15 / 20 | [Reference](https://hyresgast.sfv.se/vara-fastigheter/hyresgast-och-felanmalan/stockholms-lan/birger-jarls-torn/) |
| Schering Rosenhanes palats | `relation/21288970` | hip | 20 / 27 | [Reference](https://sv.wikipedia.org/wiki/Schering_Rosenhanes_palats) |
| Sparreska palatset | `way/108507585` | hip | 20 / 26 | [Reference](https://www.sfv.se/vara-fastigheter/sverige/stockholms-lan/riddarholmen/sparreska-palatset) |
| Kammarrättens hus | `way/108507592` | pediment | 21 / 27 | [Reference](https://sv.wikipedia.org/wiki/Kammarrättens_hus) |
| Gamla riksdagshuset | `relation/139295` | pediment | 24 / 31 | [Reference](https://sv.wikipedia.org/wiki/Gamla_riksdagshuset) |
| Strömsborg | `way/16095382` | turrets | 16 / 23 | [Reference](https://sv.wikipedia.org/wiki/Strömsborg) |
| Grand Hôtel | `relation/18489276` | mansard | 29 / 37 | [Reference](https://grandhotel.se/om-grand-hotel/historia) |
| Historiska museet | `relation/93398` | flat | 14 / 17 | [Reference](https://historiska.se/besok-oss/) |
| Östermalms Saluhall | `way/120023281` | turrets | 13 / 23 | [Reference](https://sv.wikipedia.org/wiki/Östermalms_Saluhall) |
| H M Konungens Hovstall | `way/124255734` | stepped | 12 / 20 | [Reference](https://www.sfv.se/vara-fastigheter/sverige/stockholms-lan/oevrigt/kungliga-hovstallet) |
| Radiohuset | `way/15791780` | modern | 25 / 29 | [Reference](https://sv.wikipedia.org/wiki/Radiohuset) |
| Filmhuset | `relation/19247595` | brutalist | 19 / 22 | [Reference](https://sv.wikipedia.org/wiki/Filmhuset) |
| Berwaldhallen | `way/5174887` | hip | 10 / 14 | [Reference](https://sv.wikipedia.org/wiki/Berwaldhallen) |
| Sjöhistoriska museet | `way/10502251` | clock | 11 / 20 | [Reference](https://sv.wikipedia.org/wiki/Sjöhistoriska_museet) |
| Etnografiska museet | `way/10502303` | hip | 8 / 12 | [Reference](https://www.etnografiskamuseet.se/) |
| Cirkus | `way/5192172` | rotunda | 12 / 23 | [Reference](https://sv.wikipedia.org/wiki/Cirkus,_Stockholm) |
| Biologiska museet | `way/33114307` | stave | 9 / 20 | [Reference](https://sv.wikipedia.org/wiki/Biologiska_museet,_Stockholm) |
| Liljevalchs konsthall | `way/33114705` | skylight | 10 / 14 | [Reference](https://sv.wikipedia.org/wiki/Liljevalchs_konsthall) |
| Abbamuseet | `way/33275424` | modern | 14 / 17 | [Reference](https://sv.wikipedia.org/wiki/Abbamuseet) |
| Rosendals slott | `way/145662484` | hip | 8 / 13 | [Reference](https://sv.wikipedia.org/wiki/Rosendals_slott) |
| Waldemarsuddes oljekvarn | `way/34838584` | windmill | 12 / 19 | [Reference](https://sv.wikipedia.org/wiki/Waldemarsuddes_oljekvarn) |
| Bredablick | `way/33407172` | battlements | 28 / 30 | [Reference](https://www.nationalstadsparken.se/om-parken/slott-och-byggnader/bredablick-pa-skansen/) |
| Seglora kyrka | `way/33407223` | timber-church | 8 / 24 | [Reference](https://sv.wikipedia.org/wiki/Seglora_kyrka) |
| Hällestadsstapeln | `way/33485731` | belfry | 13 / 34.5 | [Reference](https://commons.wikimedia.org/wiki/Category:Hällestadsstapeln) |
| Skogaholms herrgård | `way/23620156` | pavilions | 6 / 10 | [Reference](https://sv.wikipedia.org/wiki/Skogaholms_herrgård) |
| Kastellet | `way/49744847` | castle | 9 / 20 | [Reference](https://www.sfv.se/vara-fastigheter/sverige/stockholms-lan/skepps-och-kastellholmen/kastellet-pa-kastellholmen) |
| Gamla Sjökrigsskolan | `way/93976580` | clock | 16 / 25 | [Reference](https://sv.wikipedia.org/wiki/Gamla_Sjökrigsskolan) |
| Kungliga Konsthögskolan | `relation/1364108` | flat | 18 / 21 | [Reference](https://sv.wikipedia.org/wiki/Kungliga_Konsthögskolan) |
| Reimers malmgård | `way/43136289` | hip | 7 / 11 | [Reference](https://sv.wikipedia.org/wiki/Reimers_malmgård) |
| Stora Bryggeriet | `way/478436194` | industrial | 18 / 29 | [Reference](https://sv.wikipedia.org/wiki/Stora_Bryggeriet) |
| Sportpalatset | `way/1356201195` | terrace | 28 / 58 | [Reference](https://stockholmskallan.stockholm.se/post/29483) |
| Sankt Erikspalatset | `way/1360293334` | corner-tower | 28 / 58 | [Reference](https://sv.wikipedia.org/wiki/Sankt_Erikspalatset) |
| Sven-Harrys konstmuseum | `way/137165681` | roof-house | 18 / 23 | [Reference](https://sv.wikipedia.org/wiki/Sven-Harrys_konstmuseum) |
| Bonniers konsthall | `way/35205940` | glass | 14 / 17 | [Reference](https://sv.wikipedia.org/wiki/Bonniers_konsthall) |
| Wenner-Gren Center | `way/23511958` | slab | 70 / 74 | [Reference](https://sv.wikipedia.org/wiki/Wenner-Gren_Center) |
| Stockholms gamla observatorium | `way/771856432` | observatory | 8 / 15 | [Reference](https://sisab.se/sv/fastigheter/vara-fastigheter/norra-innerstaden/observatoriet2/) |
| Sankt Johannes kyrka | `way/42037293` | gothic | 22 / 86.5 | [Reference](https://sv.wikipedia.org/wiki/Sankt_Johannes_kyrka,_Stockholm) |
| Maria Magdalena kyrka | `way/156840831` | baroque | 16 / 45 | [Reference](https://sv.wikipedia.org/wiki/Maria_Magdalena_kyrka,_Stockholm) |
| Stockholms moské | `way/37079917` | mosque | 15 / 21 | [Reference](https://sv.wikipedia.org/wiki/Stockholms_moské) |
| Laurinska huset | `way/37293917` | corner-tower | 26 / 41 | [Reference](https://sv.wikipedia.org/wiki/Laurinska_huset) |
| Münchenbryggeriet | `way/17392811` | industrial | 28 / 39 | [Reference](https://sv.wikipedia.org/wiki/Münchenbryggeriet) |
| Södra stadshuset | `way/37265277` | pavilions | 12 / 20 | [Reference](https://sv.wikipedia.org/wiki/Södra_stadshuset) |
| Folksamhuset | `way/42672700` | slab | 77 / 80 | [Reference](https://sv.wikipedia.org/wiki/Folksamhuset) |
| Söder Torn | `way/37299689` | round-slab | 82 / 86 | [Reference](https://sv.wikipedia.org/wiki/Söder_torn) |
| Ersta kyrka | `way/117481563` | octagon | 13 / 24 | [Reference](https://sv.wikipedia.org/wiki/Ersta_kyrka) |
| Allhelgonakyrkan | `way/108375151` | timber-church | 11 / 34 | [Reference](https://sv.wikipedia.org/wiki/Allhelgonakyrkan,_Stockholm) |
| Heleneborg | `way/74757502` | hip | 8 / 13 | [Reference](https://sv.wikipedia.org/wiki/Heleneborg) |
| Ekermanska malmgården | `way/58264111` | hip | 4 / 8 | [Reference](https://sv.wikipedia.org/wiki/Ekermanska_malmgården) |
| Fåfängan | `way/140046247` | pavilion | 4 / 7 | [Reference](https://sv.wikipedia.org/wiki/Fåfängan) |
