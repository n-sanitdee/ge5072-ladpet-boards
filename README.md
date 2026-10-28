# GE5072 Ladpet boards

Saved snapshots of Ladpet class-wall boards, hosted for students on GitHub Pages.
The live Ladpet app is a separate repo (`ge5072-class-wall`).

- `wk12/` — Week 12 Final Project brainstorm ("Your Company"), CA48 and EC30, 26 Oct 2026.
  Built from the Ladpet "Save board" exports; the "not posted" list was removed and photos recompressed.

## Adding a section board

1. Clean the export (strip the header's "not posted" list, recompress photos ≤1400 px JPEG q82) and save it as `<week>/<code>.html`; give each `<article>` an `id="p<n>"`.
2. Make `<week>/thumbs/<code>-<n>.jpg` (≤480 px) for each post.
3. Add the company names to the section in `<week>/sections.json`.
4. `python3 tools/build.py <week>` — rebuilds the index and the section page's tile view (safe to re-run).

Each page fits one screen: the index shows every section (sections without a board yet show as small "coming" tiles); a section page shows its companies as tiles, and tapping one opens the full board at that company.
