ram_mesh_import - Windows standalone build (no Python needed)

Files
  ram_mesh_import.exe  the tool
  dry_run.bat          drag a DXF (or a folder of DXFs) onto it: checks the drawing, opens the dashboard
  build.bat            drag a DXF (or a folder) onto it: builds the RAM Concept .cpt model with the mesh
  test_sample.bat      double-click to run the included sample drawing
  config.json          slab thickness, concrete names, column defaults, mesh size, units, layer names
  examples\sample_level.dxf   sample floor on the BBR layers

First time
  1. Double-click test_sample.bat. A dashboard should open in your browser.
  2. Open build.bat in Notepad and set CONCEPT_PY to the "python" folder inside your
     RAM Concept installation, then save.
  3. Edit config.json for your project.

Layers read from the DXF (polylines, millimetres):
  BBR-Slabs, BBR-Opening, BBR-Drop Panels, BBR-Columns, BBR-Walls, BBR-Beams
