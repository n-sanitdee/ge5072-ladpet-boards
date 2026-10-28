# GE5072 Ladpet boards

Saved snapshots of Ladpet class-wall boards, hosted for students on GitHub Pages.
The live Ladpet app is a separate repo (`ge5072-class-wall`).

- `wk12/` — Week 12 Final Project brainstorm ("Your Company"), CA48 and EC30, 26 Oct 2026.
  Built from the Ladpet "Save board" exports; the "not posted" list was removed and photos recompressed.

## Adding a section board

1. Clean the export (strip the header's "not posted" list, recompress photos ≤1400 px JPEG q82).
2. `python3 tools/extract.py <week> <code> <export.html>` — writes `<week>/data/<code>.json` plus `img/` photos and `thumbs/`.
3. Fill in each post's `"company"` in the data file.
4. `python3 tools/build.py <week>` — rebuilds the index and every section page (safe to re-run).

Every page fits one screen. The index shows every section in `<week>/sections.json` (sections without data show as small "coming soon" tiles). A section page shows each company as a tile with its photo and the start of its profile; tapping one opens the full board at that company (`#p<n>`).
