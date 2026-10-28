# GE5072 Ladpet boards

Saved snapshots of Ladpet class-wall boards, hosted for students on GitHub Pages.
The live Ladpet app is a separate repo (`ge5072-class-wall`).

- `wk12/` — Week 12 Final Project brainstorm ("Your Company"): CA48 + EC30 (26 Oct), TS66 (28 Oct, from the database backup).
  Built from the Ladpet "Save board" exports; the "not posted" list was removed and photos recompressed.

## Automatic boards (since 28 Oct 2026)

`.github/workflows/archive.yml` runs `tools/archive.py` every 10 minutes. It saves a Ladpet wall as a board when the
host pressed **Finish**, pressed **Close joining**, or the wall is 2½ h old — as long as its posts are showing (live or
revealed). Then it commits, publishes, and deletes walls that are 3 h old. Folder: wk12-company → `wk12/`, other
activities → their preset id (`wk13-spot9/`, …), a custom wall → `wall-<title>/`, or wherever a sections.json `"wall"`
names it. A data file is only replaced by the same wall, so hand-made boards stay; edit a post's `"company"` in its
data file to rename it and the next run keeps your name. Leading lists of full names ("First Last" lines) are dropped,
because this site is public. `python3 tools/archive.py --dry-run` shows what it would do.

## Adding a section board by hand

1. Clean the export (strip the header's "not posted" list, recompress photos ≤1400 px JPEG q82).
2. `python3 tools/extract.py <week> <code> <export.html>` — writes `<week>/data/<code>.json` plus `img/` photos and `thumbs/`.
3. Fill in each post's `"company"` in the data file.
4. `python3 tools/build.py <week>` — rebuilds the index and every section page (safe to re-run).

Every page fits one screen. The index shows every section in `<week>/sections.json` (sections without data show as small "coming soon" tiles). A section page shows each company as a tile with its photo and the start of its profile; tapping one opens that company's presentation slide (`#p<n>`): photo on the left, the whole profile on the right, sized to fit. ◀ ▶, the arrow keys or a presentation clicker (Page Up/Down) move between companies; Esc or "← All companies" goes back to the tiles.
