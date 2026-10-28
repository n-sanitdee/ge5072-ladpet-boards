#!/usr/bin/env python3
"""Rebuild a week's boards: the section index and the tile view on each section page.

    python3 tools/build.py wk12

Reads <week>/sections.json. Each section page (<week>/<code>.html, a cleaned
"Save the Ladpet" export) gets a fitted tile grid of its companies; tapping a
tile shows the full board (the export as saved) at that company. The tile
block sits between BOARD-TILES markers, so re-running the script is safe.
Thumbnails are <week>/thumbs/<code>-<n>.jpg.
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Shared by both pages: choose a grid's column count so each photo is as big as
# the box allows (cells under 70 px wide are penalised because names get cut).
FIT_JS = """
function best(n,W,H,lines){
  var gap=8,b=null;
  for(var c=1;c<=n;c++){
    var r=Math.ceil(n/c),w=(W-(c-1)*gap)/c,h=(H-(r-1)*gap)/r;
    var fs=Math.max(10,Math.min(15,w*0.085)),side=Math.min(w-2,h-lines*1.25*fs-10);
    var score=w<70?side*0.75:side;
    if(!b||score>b.score)b={c:c,r:r,score:score,fs:fs};
  }
  return b;
}
function fitGrid(g){
  var n=g.children.length;if(!n)return;
  var b=best(n,g.clientWidth,g.clientHeight,+g.dataset.lines||2.5);
  g.style.gridTemplateColumns='repeat('+b.c+',minmax(0,1fr))';
  g.style.gridTemplateRows='repeat('+b.r+',minmax(0,1fr))';
  g.style.setProperty('--fs',b.fs.toFixed(1)+'px');
}
"""

TILE_CSS = """
.grid{flex:1;min-height:0;display:grid;gap:8px;grid-template-columns:repeat(auto-fill,minmax(90px,1fr));overflow:hidden}
.co{display:flex;flex-direction:column;min-height:0;min-width:0;border:1px solid #e3e5f1;border-radius:8px;overflow:hidden;background:#fff;text-decoration:none;color:inherit}
.ph{flex:1;min-height:0;position:relative;background:#eef0f8}
.ph img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;display:block}
.nm{flex:none;margin:4px 5px 0;overflow-wrap:break-word;font-size:var(--fs,12px);font-weight:600;line-height:1.25;text-align:center;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;height:2.5em}
.by{flex:none;margin:0 5px 4px;font-size:calc(var(--fs,12px)*.85);line-height:1.25;color:#64748b;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
"""


def esc(s):
    return html.escape(s, quote=True)


def section_page(week, sec):
    code = sec["code"].lower()
    path = ROOT / week / f"{code}.html"
    src = path.read_text(encoding="utf-8")
    src = re.sub(r"\n?<!-- BOARD-TILES -->.*?<!-- /BOARD-TILES -->\n?", "\n", src, flags=re.S)
    names = re.findall(r'<article id="p(\d+)"><h2>([^<]*)</h2>', src)
    assert len(names) == len(sec["companies"]), (code, len(names), len(sec["companies"]))
    cells = "\n".join(
        f'<a class="co" href="#p{n}"><span class="ph"><img src="thumbs/{code}-{n}.jpg" alt=""></span>'
        f'<span class="nm">{esc(co)}</span><span class="by">{nick}</span></a>'
        for (n, nick), co in zip(names, sec["companies"])
    )
    block = f"""<!-- BOARD-TILES -->
<style>
html.tiles,html.tiles body{{height:100%;overflow:hidden}}
html.tiles body{{display:flex;flex-direction:column;height:100dvh}}
html.tiles header{{padding:10px 16px;flex:none}}html.tiles header h1{{font-size:20px;margin:2px 0}}html.tiles header p{{font-size:13px}}
html.tiles body>p,html.tiles main,html.tiles footer,html.tiles .fixes{{display:none}}
#tiles{{display:none}}
html.tiles #tiles{{display:flex;flex-direction:column;flex:1;min-height:0;padding:12px 16px;gap:8px;width:100%;max-width:1400px;margin:0 auto;box-sizing:border-box}}
#tiles .hint{{flex:none;font-size:13px;color:#64748b;font-weight:600}}
{TILE_CSS}
.co:hover,.co:focus-visible{{border-color:#4f46e5;box-shadow:0 0 0 3px #c7d2fe;outline:none}}
.back,.float{{display:none}}html.full .back{{display:inline}}
html.full .float{{display:block;position:fixed;right:14px;bottom:14px;z-index:5;background:#4f46e5;color:#fff;text-decoration:none;font-weight:700;font-size:14px;padding:10px 14px;border-radius:999px;box-shadow:0 2px 6px rgba(30,27,75,.3)}}
article:target{{outline:3px solid #4f46e5;outline-offset:2px}}
article{{scroll-margin-top:12px}}
</style>
<a class="float" href="#">← All companies</a>
<div id="tiles"><div class="hint">Tap a company to read its full profile.</div><div class="grid" data-lines="3.75">
{cells}
</div></div>
<script>
{FIT_JS}
// Tile view by default; a #p<n> link shows the full board at that company
function view(){{
  var full=/^#p\\d+$/.test(location.hash),r=document.documentElement;
  r.classList.toggle('tiles',!full);r.classList.toggle('full',full);
  if(!full){{scrollTo(0,0);fitGrid(document.querySelector('#tiles .grid'));}}
  else{{var a=document.getElementById(location.hash.slice(1));if(a)a.scrollIntoView();}}
}}
view();addEventListener('hashchange',view);addEventListener('resize',function(){{if(!/^#p\\d+$/.test(location.hash))view();}});
</script>
<!-- /BOARD-TILES -->
"""
    src = src.replace("<main>", block + "<main>", 1)
    # header link back to the tiles while the full board is showing
    src = re.sub(r'<span class="back"> · <a href="#"[^>]*>[^<]*</a></span>', "", src)
    src = src.replace('· Ladpet · ' + sec["code"] + '</div>',
                      '· Ladpet · ' + sec["code"] + '<span class="back"> · <a href="#" style="color:#fff">← All companies</a></span></div>', 1)
    path.write_text(src, encoding="utf-8")


def index_page(week, cfg):
    tiles, soon = [], []
    for sec in cfg["sections"]:
        code = sec["code"].lower()
        cos = sec.get("companies") or []
        if cos:
            cells = "\n".join(
                f'<span class="co"><span class="ph"><img src="thumbs/{code}-{i}.jpg" alt=""></span>'
                f'<span class="nm">{esc(co)}</span></span>'
                for i, co in enumerate(cos, 1)
            )
            tiles.append(f'<a class="card" href="{code}.html"><span class="hd"><span class="sec">{sec["code"]}</span>'
                         f'<span class="n">{len(cos)} companies</span><span class="go">Open →</span></span>'
                         f'<span class="grid">\n{cells}\n</span></a>')
        else:
            soon.append(f'<div class="card empty"><span class="sec">{sec["code"]}</span>'
                        f'<span class="wait">Board coming after class · {esc(sec["class"])}</span></div>')
    out = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ladpet · {esc(cfg["short"])}</title>
<style>
html,body{{height:100%}}
body{{margin:0;font-family:system-ui,-apple-system,'Segoe UI',Roboto,Sarabun,'Leelawadee UI',Thonburi,sans-serif;background:#f5f6fc;color:#1e1b4b;display:flex;flex-direction:column;height:100dvh;overflow:hidden}}
header{{background:#4f46e5;color:#fff;padding:10px 16px;flex:none}}
header .k{{opacity:.85;font-size:12px;letter-spacing:.06em;text-transform:uppercase;font-weight:700}}
header h1{{margin:2px 0 0;font-size:20px;line-height:1.25}}header p{{margin:2px 0 0;opacity:.9;font-size:13px}}
main{{flex:1;min-height:0;padding:10px 12px;display:flex;flex-direction:column;gap:10px;width:100%;max-width:1600px;margin:0 auto;box-sizing:border-box}}
.boards{{flex:1;min-height:0;display:grid;gap:10px;grid-template-columns:repeat(2,minmax(0,1fr));grid-auto-rows:minmax(0,1fr)}}
.soon{{flex:none;display:grid;gap:8px;grid-template-columns:repeat(auto-fit,minmax(130px,1fr))}}
.card{{display:flex;flex-direction:column;min-height:0;min-width:0;background:#fff;border:1px solid #e3e5f1;border-radius:12px;padding:8px 10px;text-decoration:none;color:inherit;box-sizing:border-box}}
a.card{{transition:border-color .15s,box-shadow .15s}}
a.card:hover,a.card:focus-visible{{border-color:#4f46e5;box-shadow:0 0 0 3px #c7d2fe;outline:none}}
.card.empty{{background:#f0f1f8;border-style:dashed;padding:6px 10px;flex-direction:row;align-items:baseline;gap:8px}}
.hd{{display:flex;align-items:baseline;gap:8px;flex:none;margin-bottom:6px;min-width:0;overflow:hidden;white-space:nowrap}}
.card{{container-type:inline-size}}
@container (max-width:250px){{.n{{display:none}}}}
.sec{{font-size:20px;font-weight:800;color:#4f46e5}}
.empty .sec{{color:#94a3b8}}
.n{{font-size:12px;color:#64748b;font-weight:700;overflow:hidden;text-overflow:ellipsis;min-width:0}}
.go{{margin-left:auto;font-size:13px;font-weight:700;color:#4f46e5;white-space:nowrap}}
.empty .sec{{font-size:16px}}
.wait{{color:#64748b;font-size:12px;font-weight:600;line-height:1.3}}
{TILE_CSS}
footer{{flex:none;padding:0 16px 6px;color:#64748b;font-size:12px;text-align:center}}
</style></head><body>
<header><div class="k">GE5072 · Ladpet</div><h1>{esc(cfg["title"])}</h1>
<p>{esc(cfg["blurb"])} Tap a section to open its board.</p></header>
<main>
<div class="boards">
{chr(10).join(tiles)}
</div>
{'<div class="soon">' + chr(10).join(soon) + '</div>' if soon else ''}
</main>
<footer>Saved from Ladpet (GE5072) · names are the nicknames students chose.</footer>
<script>
{FIT_JS}
// Lay the sections out so the smallest photo on the page is as big as possible
function fit(){{
  var m=document.querySelector('.boards'),cards=[].slice.call(m.children),S=cards.length,gap=10;
  var W=m.clientWidth,H=m.clientHeight,pick=null;
  for(var C=1;C<=S;C++){{
    var R=Math.ceil(S/C),w=(W-(C-1)*gap)/C-22,h=(H-(R-1)*gap)/R-18-34,worst=Infinity;
    cards.forEach(function(k){{var g=k.querySelector('.grid');if(g)worst=Math.min(worst,best(g.children.length,w,h,2.5).score);}});
    if(!pick||worst>pick.worst)pick={{C:C,worst:worst}};
  }}
  m.style.gridTemplateColumns='repeat('+pick.C+',minmax(0,1fr))';
  m.querySelectorAll('.grid').forEach(fitGrid);
}}
fit();addEventListener('resize',fit);
</script>
</body></html>
"""
    (ROOT / week / "index.html").write_text(out, encoding="utf-8")


def main():
    week = sys.argv[1]
    cfg = json.loads((ROOT / week / "sections.json").read_text(encoding="utf-8"))
    for sec in cfg["sections"]:
        if sec.get("companies"):
            section_page(week, sec)
    index_page(week, cfg)


if __name__ == "__main__":
    main()
