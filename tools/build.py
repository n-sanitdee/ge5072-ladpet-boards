#!/usr/bin/env python3
"""Rebuild a week's boards: the section index and one page per section.

    python3 tools/build.py wk12

Reads <week>/sections.json (sections + class times) and <week>/data/<code>.json
(posts, made by tools/extract.py). A section with no data file shows on the
index as "coming soon". Photos: <week>/img/<code>-<n>.jpg, thumbnails in thumbs/.

Every page fits one screen. A section page opens as a grid of company tiles
(photo + the start of the profile); tapping one shows the full board at that
company (#p<n>).
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ACCENT = {"CA48": "#db2777", "EC30": "#0d9488", "BS11": "#c2410c",
          "TS66": "#7c3aed", "CA50": "#2563eb", "AC21": "#15803d"}
TINTS = ["#ffd9e2", "#fff0b3", "#cdf3e4", "#d4e8ff", "#e6dcff", "#ffe0c7"]

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&family=Mitr:wght@400;500&'
         'family=Nunito:wght@500;700;800&family=Noto+Sans+Thai:wght@400;600&display=swap" rel="stylesheet">')

BASE_CSS = """
:root{--ink:#1d1a3a;--muted:#5f5b80;--paper:#fffaf2;--acc:#6d4aff}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--paper) radial-gradient(#e8dfcf 1.2px,transparent 1.4px) 0 0/18px 18px;color:var(--ink);
  font-family:'Nunito','Noto Sans Thai',system-ui,-apple-system,'Segoe UI',sans-serif}
.dsp{font-family:'Fredoka','Mitr','Noto Sans Thai',system-ui,sans-serif}
header.top{position:relative;overflow:hidden;background:var(--acc);color:#fff;padding:12px 18px 14px;flex:none;border-bottom:3px solid var(--ink)}
header.top::before{content:"";position:absolute;right:-40px;top:-60px;width:180px;height:180px;border-radius:50%;background:rgba(255,255,255,.14)}
header.top::after{content:"";position:absolute;right:120px;bottom:-46px;width:84px;height:84px;border-radius:50%;background:#ffd34d;border:3px solid var(--ink)}
header.top .row{position:relative;z-index:1;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.pill{display:inline-block;background:#fff;color:var(--ink);border:2px solid var(--ink);border-radius:999px;padding:1px 10px;font-weight:800;font-size:12px;letter-spacing:.04em;text-transform:uppercase;text-decoration:none}
a.pill:hover{background:#ffd34d}
header.top h1{position:relative;z-index:1;margin:6px 0 2px;font-size:clamp(20px,3.2vw,30px);line-height:1.2;font-weight:600}
header.top p{position:relative;z-index:1;margin:0;font-size:13px;font-weight:700;opacity:.92;max-width:62ch}
.sticker{display:inline-block;background:#fff;color:var(--ink);border:2px solid var(--ink);border-radius:10px;padding:0 9px;
  box-shadow:3px 3px 0 var(--ink);transform:rotate(-3deg);font-weight:700}
.card{background:#fff;border:2px solid var(--ink);border-radius:16px;box-shadow:4px 4px 0 var(--ink)}
a.card,a.co{text-decoration:none;color:inherit;transition:transform .12s,box-shadow .12s}
a.card:hover,a.card:focus-visible,a.co:hover,a.co:focus-visible{transform:translate(-2px,-2px);box-shadow:6px 6px 0 var(--ink);outline:none}
footer{flex:none;text-align:center;color:var(--muted);font-size:12px;font-weight:700;padding:4px 16px 8px}
@media (max-width:560px){header.top::after{display:none}header.top{padding:10px 14px 12px}}
"""


def esc(s):
    return html.escape(s, quote=True)


# ---------- profile text → headed sections ----------

NUM = re.compile(r"^\s*(\d{1,2})\s*\.\s*(?!\d)(.*)$")
BULLET = re.compile(r"^[*•\-–]\s+(.*)$")
COLON = re.compile(r"^([^\d*•\-–:][^:]{0,38}?)\s*:\s*(.+)$")
KNOWN = re.compile(r"^(products?\s*(?:&|and|/)\s*services?|history\s*(?:&|and)\s*milestones?|goals?|"
                   r"customers?\s*(?:&|and)\s*markets?|what makes \S+(?: it)? different|numbers that changed|"
                   r"key figures[^()]{0,30})(\s*\([^)]*\)?)?", re.I)
HEADWORD = re.compile(r"products?|services?|history|milestone|goals?|customers?|markets?|different|numbers|figures|"
                      r"sales|strengths?|company|business|conclusion|summary|ผลิตภัณฑ์|ประวัติ|เป้าหมาย|ลูกค้า|"
                      r"แตกต่าง|จุดเด่น|ตัวเลข|สรุป", re.I)
ICONS = [(r"number|figure|sales|metric|ตัวเลข|ยอดขาย", "📈"), (r"goal|เป้าหมาย", "🎯"),
         (r"customer|market|ลูกค้า|ตลาด", "👥"), (r"different|strength|achieve|แตกต่าง|จุดเด่น|จุดต่าง", "✨"),
         (r"product|service|ผลิตภัณฑ์|บริการ", "🛍️"), (r"history|milestone|founded|ประวัติ|ก่อตั้ง", "📜"),
         (r"company|business", "🏢"), (r"conclusion|summary|สรุป", "💬")]


def norm(s):
    s = re.sub(r"company\s*(name|profile)", "", s.lower())
    return re.sub(r"[\W_]+", "", s)


def icon(h):
    for pat, ic in ICONS:
        if re.search(pat, h, re.I):
            return ic
    return ""


def tidy_heading(h):
    h = h.strip().strip(":").strip()
    if h and h == h.lower() and re.search(r"[a-z]", h):
        h = re.sub(r"\b([a-z])", lambda m: m.group(1).upper(), h)
    return h


def split_numbered(rest):
    c = re.match(r"^([^:]{2,60}?)\s*:\s*(.*)$", rest)
    if c and re.search(r"[A-Za-z฀-๿]", c.group(1)):
        return c.group(1), c.group(2)
    if len(rest) <= 60:
        return rest, ""
    k = KNOWN.match(rest)
    if k:
        return k.group(0), rest[k.end():]
    return "", rest


def parse(text, company):
    lines = [l.strip() for l in text.replace("\r", "").split("\n")]
    lines = [l.replace("\\.", ".") for l in lines if l]
    tagline = None
    if lines and not NUM.match(lines[0]):
        nf, nc = norm(lines[0]), norm(company)
        if nf and (nf in nc or (nc in nf and len(nf) <= len(nc) + 3)):
            lines = lines[1:]
        elif nc and nc in nf and len(lines[0]) <= 80:
            tagline, lines = lines[0], lines[1:]
    numbered = any(NUM.match(l) for l in lines)
    secs, cur = [], None
    for l in lines:
        m = NUM.match(l)
        if m:
            h, body = split_numbered(m.group(2).strip())
            cur = {"h": tidy_heading(h), "items": [("t", body.strip())] if body.strip() else []}
            secs.append(cur)
            continue
        b = BULLET.match(l)
        c = None if b else COLON.match(l)
        if c and re.search(r"[A-Za-z฀-๿]", c.group(1)):
            if numbered and cur is not None:
                cur["items"].append(("kv", c.group(1).strip(), c.group(2).strip()))
            else:
                cur = {"h": tidy_heading(c.group(1)), "items": [("t", c.group(2).strip())]}
                secs.append(cur)
            continue
        # in a numbered profile the numbers mark the headings; otherwise guess from short topic lines
        if not b and (re.fullmatch(r"(conclusion|summary|สรุป)\W*", l, re.I) if numbered else
                      len(l) <= 45 and not l.endswith(".") and HEADWORD.search(l) and (cur is None or cur["items"])):
            cur = {"h": tidy_heading(l), "items": []}
            secs.append(cur)
            continue
        if cur is None:
            cur = {"h": "", "items": []}
            secs.append(cur)
        cur["items"].append(("b", b.group(1)) if b else ("t", l))
    return tagline, secs


def short_heading(h):
    s = re.sub(r"\s*\([^)]*[฀-๿][^)]*\)?\s*$", "", h).strip()
    return s or h


def excerpt_html(tagline, secs):
    out = [f'<p class="tg">{esc(tagline)}</p>'] if tagline else []
    for s in secs:
        parts = [f"{esc(i[1])}: {esc(i[2])}" if i[0] == "kv" else esc(i[1]) for i in s["items"]]
        head = f'<b>{icon(s["h"])} {esc(short_heading(s["h"]))}</b> ' if s["h"] else ""
        out.append(f"<p>{head}{' · '.join(parts)}</p>")
    return "".join(out)


def full_html(tagline, secs):
    out = [f'<p class="tg">{esc(tagline)}</p>'] if tagline else []
    for s in secs:
        if s["h"]:
            out.append(f'<h3><span class="ic">{icon(s["h"]) or "•"}</span>{esc(s["h"])}</h3>')
        ul = []
        for i in s["items"]:
            if i[0] == "b":
                ul.append(f"<li>{esc(i[1])}</li>")
                continue
            if ul:
                out.append("<ul>" + "".join(ul) + "</ul>")
                ul = []
            out.append(f"<p><b>{esc(i[1])}:</b> {esc(i[2])}</p>" if i[0] == "kv" else f"<p>{esc(i[1])}</p>")
        if ul:
            out.append("<ul>" + "".join(ul) + "</ul>")
    return "".join(out)


# ---------- section page ----------

def jpeg_size(path):
    b = path.read_bytes()
    i = 2
    while i < len(b):
        marker, size = b[i + 1], int.from_bytes(b[i + 2:i + 4], "big")
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            return int.from_bytes(b[i + 7:i + 9], "big"), int.from_bytes(b[i + 5:i + 7], "big")
        i += 2 + size
    raise ValueError(f"no SOF in {path}")


SECTION_CSS = """
html.tiles,html.tiles body{height:100%;overflow:hidden}
html.tiles body{display:flex;flex-direction:column;height:100dvh}
html.tiles #board,html.tiles footer,html.tiles .float{display:none}
html.full #tiles{display:none}
#tiles{flex:1;min-height:0;display:flex;flex-direction:column;gap:10px;padding:14px 18px 16px;width:100%;max-width:1840px;margin:0 auto}
.hint{flex:none;font-weight:800;font-size:13px;color:var(--muted)}
.hint b{color:var(--acc)}
.grid{flex:1;min-height:0;display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}
.co{display:flex;min-width:0;min-height:0;overflow:hidden;background:#fff;border:2px solid var(--ink);border-radius:16px;box-shadow:4px 4px 0 var(--ink)}
.grid.v .co{flex-direction:column}
.co .ph{flex:none;position:relative;background:var(--tint);width:var(--pw,40%)}
.grid.v .co .ph{width:auto;height:var(--phh,45%);border-bottom:2px solid var(--ink)}
.grid.h .co .ph{border-right:2px solid var(--ink)}
.co .ph img{position:absolute;inset:6px;width:calc(100% - 12px);height:calc(100% - 12px);object-fit:contain;border-radius:8px}
.co.pic .ph{flex:1;width:auto;height:auto}
.co .tx{flex:1;min-width:0;min-height:0;display:flex;flex-direction:column;padding:8px 11px 7px;font-size:var(--fs,12px)}
.co.pic .tx{flex:none}
.grid.h .co.pic .tx{width:42%}
.co .nm{flex:none;font-family:'Fredoka','Mitr','Noto Sans Thai',sans-serif;font-weight:600;font-size:1.32em;line-height:1.15;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.co .by{flex:none;margin:3px 0 4px;font-size:.88em;font-weight:800;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.co .by span,.post .by span{background:var(--tint);border:1.5px solid var(--ink);border-radius:999px;padding:0 7px;color:var(--ink)}
.co .det{flex:1;min-height:0;overflow:hidden;line-height:1.38;-webkit-mask-image:linear-gradient(#000 62%,transparent);mask-image:linear-gradient(#000 62%,transparent)}
.co .det p{margin:0 0 3px}
.co .det b{color:var(--acc);font-weight:800}
.co .det .tg,.post .tg{font-style:italic;font-weight:700}
.co .more{flex:none;align-self:flex-end;font-weight:800;font-size:.92em;color:var(--acc)}
.grid.tight .co .more,.grid.tight .co .det b{display:none}
.grid.tight .co .by{margin:2px 0 3px}
@media (max-width:560px){#tiles{padding:10px 12px 12px;gap:8px}.grid{gap:10px}}
.co.pic .det{flex:none;color:var(--muted);font-weight:700;-webkit-mask-image:none;mask-image:none}
#board{padding:16px 18px 10px;max-width:1840px;margin:0 auto}
.covers{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:0 0 16px;font-weight:800;font-size:13px}
.covers span{background:#fff;border:2px solid var(--ink);border-radius:999px;padding:2px 10px;font-weight:700}
.posts{columns:3 320px;column-gap:20px}
.post{break-inside:avoid;margin:0 0 20px;overflow:hidden;scroll-margin-top:14px}
.post .ph{background:var(--tint);padding:10px;border-bottom:2px solid var(--ink)}
.post .ph img{display:block;width:100%;height:auto;border-radius:10px}
.post .bd{padding:12px 16px 14px;line-height:1.5;font-size:15px}
.post h2{margin:0;font-size:22px;font-weight:600;line-height:1.2}
.post .by{margin:4px 0 8px;font-weight:800;font-size:13px;color:var(--muted)}
.post h3{margin:12px 0 2px;font-size:15px;font-weight:800;color:var(--acc);display:flex;gap:6px;align-items:baseline}
.post p{margin:2px 0}.post ul{margin:2px 0;padding-left:20px}
.post:target{box-shadow:0 0 0 5px var(--acc),6px 6px 0 5px var(--ink);animation:pop .5s ease-out}
@keyframes pop{0%{transform:scale(.97)}60%{transform:scale(1.015)}100%{transform:none}}
.float{position:fixed;right:16px;bottom:16px;z-index:5;background:var(--ink);color:#fff;text-decoration:none;font-weight:800;font-size:14px;
  padding:10px 16px;border-radius:999px;border:2px solid #fff;box-shadow:3px 3px 0 var(--acc)}
.float:hover{background:var(--acc)}
@media (prefers-reduced-motion:reduce){.post:target{animation:none}a.co,a.card{transition:none}}
"""

FIT_TILES = """
// Pick the column count that gives every tile the most room at a card-like shape,
// then lay each tile out photo-left (wide tiles) or photo-top (tall tiles)
function fitTiles(){
  var g=document.querySelector('#tiles .grid');if(!g)return;
  var n=g.children.length,gap=parseFloat(getComputedStyle(g).rowGap)||14,W=g.clientWidth,H=g.clientHeight,b=null;
  for(var c=1;c<=n;c++){
    var r=Math.ceil(n/c),w=(W-(c-1)*gap)/c,h=(H-(r-1)*gap)/r,a=w/h;
    var s=w*h*Math.exp(-Math.abs(Math.log(a/1.6))*0.9)*(w<150?0.6:1);
    if(!b||s>b.s)b={c:c,r:r,w:w,h:h,s:s};
  }
  var hz=b.w>=1.25*b.h,tw=hz?b.w*0.58:b.w;
  g.className='grid '+(hz?'h':'v')+(b.h<170||b.w<150?' tight':'');
  g.style.gridTemplateColumns='repeat('+b.c+',minmax(0,1fr))';
  g.style.gridTemplateRows='repeat('+b.r+',minmax(0,1fr))';
  g.style.setProperty('--pw',Math.min(b.h-4,b.w*0.42)+'px');
  g.style.setProperty('--phh',Math.min(b.w*0.68,b.h*0.46)+'px');
  g.style.setProperty('--fs',Math.max(10.5,Math.min(13.5,tw/22)).toFixed(1)+'px');
}
// Tile view by default; a #p<n> link shows the full board at that company
function view(){
  var full=/^#p\\d+$/.test(location.hash),r=document.documentElement;
  r.className=full?'full':'tiles';
  if(full){var a=document.getElementById(location.hash.slice(1));if(a)a.scrollIntoView();}
  else{scrollTo(0,0);fitTiles();}
}
view();addEventListener('hashchange',view);
addEventListener('resize',function(){if(document.documentElement.className=='tiles')fitTiles();});
"""


def section_page(week, cfg, sec, data):
    code, lc = sec["code"], sec["code"].lower()
    posts = data["posts"]
    tiles, cards = [], []
    for i, p in enumerate(posts):
        tint = TINTS[i % len(TINTS)]
        tagline, secs = parse(p["text"], p["company"])
        has_text = bool(secs or tagline)
        img_t = f'<span class="ph"><img src="thumbs/{lc}-{p["n"]}.jpg" alt=""></span>' if p["photo"] else ""
        det = excerpt_html(tagline, secs) if has_text else "The details are in the picture."
        tiles.append(
            f'<a class="co{"" if has_text else " pic"}" href="#p{p["n"]}" style="--tint:{tint}">{img_t}'
            f'<span class="tx"><span class="nm">{esc(p["company"])}</span>'
            f'<span class="by">by <span>{esc(p["nick"])}</span></span>'
            f'<span class="det">{det}</span><span class="more">Read more →</span></span></a>')
        img_f = ""
        if p["photo"]:
            # real width/height keep the board from shifting while photos load, so #p<n> lands on the right card
            w, h = jpeg_size(ROOT / week / "img" / f"{lc}-{p['n']}.jpg")
            img_f = (f'<div class="ph"><img src="img/{lc}-{p["n"]}.jpg" width="{w}" height="{h}" '
                     f'alt="{esc(p["company"])}" loading="lazy"></div>')
        cards.append(
            f'<article class="post card" id="p{p["n"]}" style="--tint:{tint}">{img_f}<div class="bd">'
            f'<h2 class="dsp">{esc(p["company"])}</h2><div class="by">by <span>{esc(p["nick"])}</span></div>'
            f'{full_html(tagline, secs)}</div></article>')
    covers = "".join(f"<span>{esc(c)}</span>" for c in data.get("prompt", []))
    covers = f'<div class="covers">Each profile covers: {covers}</div>' if covers else ""
    day = data["saved"].split(" at ")[0]
    page = f"""<!doctype html>
<html lang="en" class="tiles"><head><meta charset="utf-8"><meta name="robots" content="noindex"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ladpet · {esc(cfg["short"])} · {code}</title>
<script>document.documentElement.className=/^#p\\d+$/.test(location.hash)?'full':'tiles'</script>
{FONTS}
<style>{BASE_CSS}{SECTION_CSS}:root{{--acc:{ACCENT.get(code, "#6d4aff")}}}</style></head><body>
<header class="top"><div class="row"><a class="pill" href="./">← All sections</a><span class="pill">GE5072 · Ladpet</span></div>
<h1 class="dsp"><span class="sticker">{code}</span> {esc(cfg["activity"])}</h1>
<p>{esc(day)} · {len(posts)} companies</p></header>
<section id="tiles"><div class="hint">Tap a company to read its <b>full profile</b>.</div><div class="grid">
{chr(10).join(tiles)}
</div></section>
<section id="board">{covers}<div class="posts">
{chr(10).join(cards)}
</div></section>
<a class="float" href="#">← All companies</a>
<footer>Saved from Ladpet (GE5072) · names are the nicknames students chose.</footer>
<script>{FIT_TILES}</script>
</body></html>
"""
    (ROOT / week / f"{lc}.html").write_text(page, encoding="utf-8")


# ---------- index ----------

INDEX_CSS = """
html,body{height:100%;overflow:hidden}
body{display:flex;flex-direction:column;height:100dvh}
main{flex:1;min-height:0;display:flex;flex-direction:column;gap:12px;padding:14px 18px 10px;width:100%;max-width:1840px;margin:0 auto}
.boards{flex:1;min-height:0;display:grid;gap:16px;grid-template-columns:repeat(2,minmax(0,1fr));grid-auto-rows:minmax(0,1fr)}
a.card{display:flex;flex-direction:column;min-width:0;min-height:0;padding:10px 12px 12px;container-type:inline-size}
.hd{flex:none;display:flex;align-items:center;gap:10px;margin-bottom:9px;min-width:0;white-space:nowrap;overflow:hidden;padding:3px 3px 4px 2px}
.hd .sticker{background:var(--acc);color:#fff;font-size:20px;font-family:'Fredoka',sans-serif}
.hd .n{font-weight:800;font-size:13px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;min-width:0}
.hd .go{margin-left:auto;flex:none;background:var(--ink);color:#fff;border-radius:999px;padding:3px 12px;font-weight:800;font-size:13px}
a.card:hover .go{background:var(--acc)}
@container (max-width:250px){.hd .n{display:none}}
.mini{flex:1;min-height:0;display:grid;gap:8px;grid-template-columns:repeat(auto-fill,minmax(90px,1fr));overflow:hidden}
.mc{display:flex;flex-direction:column;min-width:0;min-height:0;border:2px solid var(--ink);border-radius:10px;overflow:hidden;background:#fff}
.mc .ph{flex:1;min-height:0;position:relative;background:var(--tint);border-bottom:2px solid var(--ink)}
.mc .ph img{position:absolute;inset:4px;width:calc(100% - 8px);height:calc(100% - 8px);object-fit:contain;border-radius:5px}
.mc .nm{flex:none;margin:4px 5px;height:2.5em;overflow-wrap:break-word;font-size:var(--fs,12px);font-weight:800;line-height:1.25;text-align:center;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.soon{flex:none;display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.soon .card{display:flex;align-items:center;gap:10px;padding:7px 10px;border-style:dashed;box-shadow:none;background:rgba(255,255,255,.75);min-width:0}
.soon .sticker{background:#fff;color:var(--acc);font-size:17px;font-family:'Fredoka',sans-serif;box-shadow:2px 2px 0 var(--ink)}
.soon .w{font-size:12px;font-weight:700;color:var(--muted);line-height:1.3;white-space:nowrap;min-width:0;overflow:hidden;text-overflow:ellipsis}
.soon .w b{display:block;color:var(--ink);font-weight:800}
@media (max-width:560px){header.top p{display:none}main{padding:10px 12px 8px;gap:10px}.boards{gap:12px}.soon{gap:8px;grid-template-columns:repeat(2,minmax(0,1fr))}
  .soon .sticker{font-size:15px;padding:0 6px}.soon .w{font-size:11px;white-space:normal}}
"""

FIT_INDEX = """
// Column count that gives each company the biggest photo inside a box
function best(n,W,H){
  var gap=8,b=null;
  for(var c=1;c<=n;c++){
    var r=Math.ceil(n/c),w=(W-(c-1)*gap)/c,h=(H-(r-1)*gap)/r;
    var fs=Math.max(10,Math.min(14,w*0.085)),side=Math.min(w-4,h-2.5*1.25*fs-14);
    var score=w<70?side*0.75:side; // narrow cells cut the names
    if(!b||score>b.score)b={c:c,r:r,score:score,fs:fs};
  }
  return b;
}
function fitGrid(g){
  var b=best(g.children.length,g.clientWidth,g.clientHeight);
  g.style.gridTemplateColumns='repeat('+b.c+',minmax(0,1fr))';
  g.style.gridTemplateRows='repeat('+b.r+',minmax(0,1fr))';
  g.style.setProperty('--fs',b.fs.toFixed(1)+'px');
}
// Lay the sections out so the smallest photo on the page is as big as possible
function fit(){
  var m=document.querySelector('.boards');if(!m||!m.children.length)return;
  var cards=[].slice.call(m.children),S=cards.length,gap=parseFloat(getComputedStyle(m).rowGap)||16,W=m.clientWidth,H=m.clientHeight,pick=null;
  for(var C=1;C<=S;C++){
    var R=Math.ceil(S/C),w=(W-(C-1)*gap)/C-28,h=(H-(R-1)*gap)/R-26-46,worst=Infinity;
    cards.forEach(function(k){worst=Math.min(worst,best(k.querySelector('.mini').children.length,w,h).score);});
    if(w<200)worst*=0.8; // squeezed cards cut the header and names
    if(!pick||worst>pick.worst)pick={C:C,worst:worst};
  }
  m.style.gridTemplateColumns='repeat('+pick.C+',minmax(0,1fr))';
  m.querySelectorAll('.mini').forEach(fitGrid);
}
fit();addEventListener('resize',fit);
"""


def index_page(week, cfg, datas):
    boards, soon = [], []
    for sec in cfg["sections"]:
        code, lc = sec["code"], sec["code"].lower()
        acc = ACCENT.get(code, "#6d4aff")
        data = datas.get(code)
        if data:
            cells = "\n".join(
                f'<span class="mc" style="--tint:{TINTS[i % len(TINTS)]}"><span class="ph">'
                f'<img src="thumbs/{lc}-{p["n"]}.jpg" alt=""></span><span class="nm">{esc(p["company"])}</span></span>'
                for i, p in enumerate(data["posts"]))
            boards.append(f'<a class="card" href="{lc}.html" style="--acc:{acc}"><span class="hd">'
                          f'<span class="sticker">{code}</span><span class="n">{len(data["posts"])} companies</span>'
                          f'<span class="go">Open board →</span></span><span class="mini">\n{cells}\n</span></a>')
        else:
            soon.append(f'<div class="card" style="--acc:{acc}"><span class="sticker">{code}</span>'
                        f'<span class="w"><b>Coming soon</b>{esc(sec["class"])}</span></div>')
    soon_html = '<div class="soon">' + "\n".join(soon) + "</div>" if soon else ""
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ladpet · {esc(cfg["short"])}</title>
{FONTS}
<style>{BASE_CSS}{INDEX_CSS}</style></head><body>
<header class="top"><div class="row"><span class="pill">GE5072 · Ladpet</span></div>
<h1 class="dsp">{esc(cfg["title"])}</h1>
<p>{esc(cfg["blurb"])} Tap a section to open its board.</p></header>
<main>
<div class="boards">
{chr(10).join(boards)}
</div>
{soon_html}
</main>
<footer>Saved from Ladpet (GE5072) · names are the nicknames students chose.</footer>
<script>{FIT_INDEX}</script>
</body></html>
"""
    (ROOT / week / "index.html").write_text(page, encoding="utf-8")


def main():
    week = sys.argv[1]
    cfg = json.loads((ROOT / week / "sections.json").read_text(encoding="utf-8"))
    datas = {}
    for sec in cfg["sections"]:
        f = ROOT / week / "data" / f"{sec['code'].lower()}.json"
        if f.exists():
            datas[sec["code"]] = json.loads(f.read_text(encoding="utf-8"))
            section_page(week, cfg, sec, datas[sec["code"]])
    index_page(week, cfg, datas)


if __name__ == "__main__":
    main()
