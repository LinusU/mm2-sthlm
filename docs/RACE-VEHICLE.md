# Original race vehicle

`src/race_vehicle.py` exports an original compact hatchback for native opponents:
PKG3 body, glass, lamps, four wheel meshes, an explicit BND hull and native
vehCarSim tuning. It uses `sthlm_racer` so all events can field real competitors
without retail assets. Steering acts on the front axle. There are no engine or
vehicle physics implementations in this repository.

The simple geometry and textures are authored procedurally, MIT licensed.
Dimensions: 1.66 m body width, 3.8 m length, 2.5 m wheelbase, 0.32 m tyre radius.
Tuning describes a 1,100 kg, 180 hp compact. Native field semantics were checked
against rust-mm2 `069768a`'s vehicle importer. Audio, cabin and damage art are
not authored yet.

Native load development probe used an independent flat PSDL fixture and pinned
b3d9804 engine: 264.9 m travel, four wheel contacts, zero impacts/resets.
This verifies importer/physics wiring, not race performance calibration. The
initial missing-bound attempt was rejected because its centered fallback hull
prevented wheel contact; the corrected asset includes an explicit hull and
places the tyre contact plane at the native model origin. Final race acceptance
must use the combined package and current engine.
