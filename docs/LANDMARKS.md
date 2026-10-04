# Thirty Stockholm landmarks

`assets/landmarks/stockholm-thirty.json` selects exactly thirty landmarks inside
this map's source boundary. OSM source IDs own horizontal position and footprint;
separate authored parameters own approximate heights, roof forms and palettes.
The original restrained geometry is designed for the native PSDL/MM2 look. This
is schematic city art, not surveyed architectural reconstruction.

Four dedicated prior assets remain intact: Stadshuset, Rådhuset, the user-photo
green waterfront pavilion and Kristinehovs malmgård. The other twenty-six replace
generic extrusions with individually selected silhouettes: octagonal twin
Högalid towers; slender Klara/Tyska/Oscars spires; Riddarholmen's open iron ribs;
Katarina/Gustaf Vasa/Hedvig Eleonora/Adolf Fredrik domes; library rotunda; blue
Konserthuset with ten columns; Vasa roof masts; Nordiska end gables/turrets;
Wrangel round towers; civic mansards and palace pavilions; modern glass bands
and tall office slabs. Tall church bays use one quiet masonry repeat rather
than apartment floors. Entrances are original wood panels at ground level.

All reference pages and authored heights are recorded per entry in the JSON.
Primary research includes the congregations, building operators, Statens
fastighetsverk, Royal Court, Försvarsmakten, Stockholm Library and property owner
Areim. Photography informs shape and colors only. No reference photograph,
Google image pixels, retail texture or retail model is redistributed. Existing
user-supplied photograph provenance stays in the earlier dedicated asset files.

Specific research corrections: the congregation describes Högalid's towers as
octagonal and the heritage brochure locates them flanking the eastern choir;
Storkyrkan's restored lantern is deep red; Stockholm Library describes a 24 m
rotunda surrounded by lower wings; SFV documents Vasa's three roof masts and
copper roof; Areim documents DN-skrapan's white/grey-blue ceramic bays. Estimates
remain labeled as authored even where a published height guided the choice.

## Integration API

`landmarks.replaces(building)` selects the twenty-six replacement IDs plus
Högalid's nested `relation/17957127`. Skip their generic building export, then
call `landmarks.export(writer, city, out)` before dedicated courthouse/pavilion
exports. Export writes deterministic original `lm_*` texture PNGs and adds
`city["landmarks"]` with emitted source IDs and rendering metadata. The existing
four are recorded without replacing their authored meshes or materials.

The nested Högalid relation is the nave and belongs inside the wider church/
columbarium footprint. Native visual inspection caught its generic export
creating a third spire. The replacement now emits one nave, two authored tower
caps and a lower columbarium, preserving the actual source courtyard voids.
No source snapshot, elevation code, road topology or bridge geometry changes.

## Verification

Acceptance uses the external native engine revision
`b3d9804489bdcd576dd4b85b3f40fec75c545071`, not a standalone viewer. Exact capture
commands, source revision and artifact checksums are recorded in
`docs/LANDMARK_QA.json`. Reproduce each camera with:

```sh
/Users/linus/coding/mm2-sthlm/.cache/engine/mm2 --mods dist --city stockholm \
  --no-profile --no-hud --no-pvs --frames 45 \
  --cam=-500,110,1350,-26,-14 --screenshot .cache/landmarks-hogalid.png
```

Run the standard AGENTS.md Ruff, full unittest, offline build and validate gates
before committing. Offline tests cover thirty unique source IDs, preserved
prior assets, finite native geometry, silhouette distinctions and suppression
of the nested church's extra spire. The isolated package also passes native circuit driving (102/102 checkpoints,
1,503.8 m, zero impacts/resets), relocated-package loading in an empty working
directory, a second independent city and missing-chunk rejection. The coordinator
reruns driving acceptance after the road/bridge work is merged. Free-camera
screenshots are visual evidence only. Högalid doorway visibility remains
unconfirmed in the close camera; rising terrain occupies its foreground.

## Authored inventory

Heights are schematic metres above each terrain-seated building base.

| Landmark | Source | Body / total m | Form | Reference |
| --- | --- | --- | --- | --- |
| Stockholms stadshus | `relation/29368` | 24 / 106 | existing | [Reference](https://stadshuset.stockholm/en/) |
| Rådhuset | `way/24488933` | 14.5 / 53 | existing | [Reference](https://domstol.se/stockholms-tingsratt/) |
| Green waterfront pavilion (user photo landmark) | `way/1049742528` | 4.2 / 6.2 | existing | Preserved user-photo art |
| Kristinehovs malmgård | `way/88413905` | 6 / 10 | existing | [Reference](https://kristinehovsmalmgard.se/) |
| Stockholms slott | `relation/34394` | 30 / 39 | palace | [Reference](https://kungligaslotten.se/english/royal-palaces-and-sites/the-royal-palace.html) |
| Karlbergs slott | `relation/11144024` | 15 / 22 | palace | [Reference](https://www.forsvarsmakten.se/mhsk/) |
| Storkyrkan | `way/8049504` | 22 / 63 | baroque | [Reference](https://www.svenskakyrkan.se/stockholmsdomkyrkoforsamling/renovering) |
| Tyska kyrkan | `way/8049509` | 20 / 96 | gothic | [Reference](https://www.svenskakyrkan.se/deutschegemeinde) |
| Riddarholmskyrkan | `way/23841420` | 20 / 87 | lattice | [Reference](https://kungligaslotten.se/vara-besoksmal/riddarholmskyrkan.html) |
| Högalidskyrkan | `relation/1257127` | 20 / 68.5 | twin | [Reference](https://www.svenskakyrkan.se/hogalid/lokaler) |
| Katarina kyrka | `way/37079169` | 20 / 64.5 | dome | [Reference](https://www.svenskakyrkan.se/filer/502017/Guide-KatarinaKyrka-WWW.pdf) |
| Sofia kyrka | `way/1350868500` | 23 / 78 | gothic | [Reference](https://svenskakyrkan.se/sofia/sofia-kyrka) |
| Klara kyrka | `way/163637452` | 23 / 116 | gothic | [Reference](https://www.svenskakyrkan.se/stockholmsdomkyrkoforsamling/sta-clara-kyrka) |
| Engelbrektskyrkan | `way/21572801` | 25 / 65 | gothic | [Reference](https://svenskakyrkan.se/engelbrekt/engelbrektskyrkan) |
| Stockholms stadsbibliotek | `way/31990167` | 13 / 24 | rotunda | [Reference](https://biblioteket.stockholm.se/about-the-stockholm-public-library-by-gunnar-asplund) |
| Konserthuset | `way/18779818` | 19 / 24 | columns | [Reference](https://konserthuset.se/om-oss/byggnaden/) |
| Dramaten | `way/24210110` | 20 / 29 | theatre | [Reference](https://www.sfv.se/vara-fastigheter/sverige/stockholms-lan/kulturinstitutioner/dramaten/) |
| Operahuset | `way/16108358` | 27 / 41.5 | theatre | [Reference](https://operan.se/om-operan/) |
| Nationalmuseum | `way/24968329` | 25 / 33.5 | museum | [Reference](https://nationalmuseum.se/en/byggnadens-historia) |
| Nordiska museet | `way/348345482` | 29 / 64 | nordic | [Reference](https://nordiskamuseet.se/en/about-us/the-history-of-the-building/) |
| Vasamuseet | `way/27288534` | 22 / 49 | vasa | [Reference](https://www.sfv.se/vara-fastigheter/sverige/stockholms-lan/museer/vasamuseet) |
| Kulturhuset | `way/40859302` | 21 / 23 | glass | [Reference](https://kulturhusetstadsteatern.se/kulturhuset-stadsteatern/kulturhuset-stadsteaterns-historia) |
| DN-skrapan | `way/247981011` | 80 / 84 | slab | [Reference](https://www.areim.se/properties/trangkaren-7/) |
| Skatteskrapan | `way/37046494` | 82 / 85.5 | slab | [Reference](https://www.skrapan.se/hitta-hit/) |
| Gustaf Vasa kyrka | `way/35275663` | 22 / 60 | dome | [Reference](https://www.svenskakyrkan.se/gustav-vasa-forsamling/gustaf-vasa-kyrka) |
| Adolf Fredriks kyrka | `way/42038493` | 18 / 43.5 | dome | [Reference](https://www.svenskakyrkan.se/adolffredrik/in-english) |
| Hedvig Eleonora kyrka | `way/27741605` | 20 / 59 | dome | [Reference](https://www.svenskakyrkan.se/hedvigeleonoraoscars/hedvig-eleonora-kyrka) |
| Oscarskyrkan | `way/32137548` | 23 / 76 | gothic | [Reference](https://www.svenskakyrkan.se/hedvigeleonoraoscars/oscarskyrkan) |
| Kungliga biblioteket | `way/15803083` | 18 / 26 | museum | [Reference](https://www.sfv.se/vara-fastigheter/sverige/stockholms-lan/oevrigt/kungliga-biblioteket) |
| Wrangelska palatset | `way/34590009` | 23 / 32.5 | round | [Reference](https://www.sfv.se/vara-fastigheter/sverige/stockholms-lan/riddarholmen/wrangelska-palatset) |
