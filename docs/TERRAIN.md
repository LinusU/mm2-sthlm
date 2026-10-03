# Offline Stockholm terrain

`src/terrain.py` reads `sources/terrain/stockholm_10m.npz`; map builds do not
need the source service or raster processing libraries. `TerrainGrid.height(x,
n)` returns a bilinear height in metres for the project's local east/north
coordinates. It raises `ValueError` outside the fixture or when any of the four
interpolation cells is nodata. The fixture covers the expanded bounds
17.970–18.174 E, 59.286–59.373 N, plus 20 m, with 10 m spacing. The recorded
coverage check found 1,131,599 valid cells and no nodata.

The local coordinate system uses the same WGS84 equirectangular calculation as
`sthlm.project`, centered at 18.045 E, 59.328 N. The raster values remain
absolute RH2000 gravity-related heights, in metres up. They are not shifted to
game water level or interpreted as bridge/deck elevations. The sidecar
`sources/terrain/metadata.json` records CRS, transform, grid dimensions,
resampling, source tile hashes, fixture hash, nodata counts, and source-sidecar
hashes. Original per-tile `*_info.json` and `*_ursprung.json` are retained in
`sources/terrain/provenance/`; `ursprung` polygons carry acquisition dates,
methods and source-reported height accuracy. Dates vary spatially, including
2020-02-19 and 2023-05-09; the tile is not represented as having one acquisition
date. Source methods include airborne laser scanning and photogrammetric image
matching.

The supplied tiles identify Lantmäteriet as producer and use compound
EPSG:5845 (SWEREF99 TM horizontal, RH2000 vertical), with 1 m Float32 samples
and -9999 nodata. The exact catalogue product title is not present in the tile
sidecars and remains to be confirmed. The applicable terms supplied for this
delivery are Lantmäteriet's [CC BY 4.0 terms, v1.0 dated 2025-02-01,
DNR LM2025/009266](https://www.lantmateriet.se/globalassets/geodata/geodataprodukter/anvandningsvillkor_for_vardefulla_datamangder.pdf).
That document requires the product name, `© Lantmäteriet`, a description of
modifications, and a link to CC BY 4.0. Its PDF is retained in `provenance/`
and its SHA-256 is recorded in `metadata.json`. The data is modified by clipping
to the expanded Stockholm bounds plus 20 m and bilinearly resampling from 1 m
to the 10 m project-local grid. The final attribution should use the confirmed
catalogue product name. No credentials or acquisition secrets are stored in
the project.

The fixture was warped from the six listed 1 m tiles into the local grid at
10 m spacing using bilinear resampling (Rasterio 1.5.2 / GDAL bundled with that
wheel, pyproj 3.8.0, NumPy 2.5.3). The original source rasters remain in ignored
`.cache/terrain/lantmateriet/`; only the clipped compressed grid and compact
provenance records are checked in.

Rebuild the fixture from the original cached downloads:

```sh
.venv/bin/pip install -r requirements-acquisition.txt
.venv/bin/python scripts/acquire-terrain.py
./scripts/sthlm build --offline
./scripts/sthlm validate
```

The rebuild script verifies every source TIFF checksum before processing.
It writes fixed NPZ ZIP timestamps; two successive rebuilds produced identical
fixture bytes. The regular map build verifies the fixture against its retained
SHA-256 before sampling. Normal CI uses the committed fixture and needs neither
the original multi-gigabyte tiles nor Rasterio/pyproj.

The game generator samples this ground grid into roads, shoulders, buildings
and props. It keeps a documented nominal 0.9 m minimum for road beds at low
quays, clears supported bridge decks using separate estimated profiles, and
blends road shoulders. These are generated playable surfaces, not claims that
the raw measured ground was changed or that bridge decks were surveyed.

[The delivery footprint check](../sources/terrain/provenance/coverage.json)
confirms that the six TIFF footprints cover the user-supplied WGS84 rectangle
17.960,59.285,18.185,59.375. Their combined SWEREF99 TM extent is
660000–690000 E, 6570000–6590000 N. This is a geometric coverage check;
raster nodata was checked exhaustively for the actual generated 10 m fixture,
not for unused 1 m cells across the full delivery.
