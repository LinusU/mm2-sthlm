# Exposed tunnel wall at Hundra Knutars Backe

Circuit 6's source-road turn near (-1189.9175, 16.959347, -418.60782) intersected an exposed tunnel retaining wall whose top protruded about 45 cm above the upper asphalt. The exact source fixture reproduces that collision geometry.

The fix queries spatially intersecting upper ground-road profiles and caps a small exposed wall-top protrusion 5 cm below that surface. It retains all wall triangles, underground floors, source profiles, covered roofs, lamps and portal rules. Covered shells and lower roads have explicit unchanged-output tests. The RED/GREEN logs are focused offline source-mesh evidence; full native race acceptance is a separate test.

Source attribution: © OpenStreetMap contributors (ODbL); © Lantmäteriet (CC BY 4.0). Exact source provenance is retained in tests/fixtures/tunnel-surface-wall-intrusion.json.
