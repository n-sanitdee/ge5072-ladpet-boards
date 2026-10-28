#!/usr/bin/env python3
"""Rebuild a week's boards: the section index and one page per section.

    python3 tools/build.py wk12

Reads <week>/sections.json (sections + class times) and <week>/data/<code>.json
(posts, made by tools/extract.py). A section with no data file shows on the
index as "coming soon". Photos: <week>/img/<code>-<n>.jpg, thumbnails in thumbs/.

Every page fits one screen. A section page opens as a grid of company tiles
(photo + the start of the profile); tapping one presents that company (#p<n>):
photo on the left, the whole profile on the right, ◀ ▶ / arrow keys / a
clicker to move between companies.
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
        out.append('<div class="sec">')
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
        out.append("</div>")
    return "".join(out)


# ---------- section page ----------

SECTION_CSS = """
html,body{height:100%;overflow:hidden}
body{display:flex;flex-direction:column;height:100dvh}
html.full header.top,html.tiles .bar,html.tiles #slides,html.full #tiles{display:none}
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
.co .by span,.slide .by span{background:var(--tint);border:1.5px solid var(--ink);border-radius:999px;padding:0 .5em;color:var(--ink)}
.co .det{flex:1;min-height:0;overflow:hidden;line-height:1.38;-webkit-mask-image:linear-gradient(#000 62%,transparent);mask-image:linear-gradient(#000 62%,transparent)}
.co .det p{margin:0 0 3px}
.co .det b{color:var(--acc);font-weight:800}
.co .det .tg,.slide .tg{font-style:italic;font-weight:700}
.co .more{flex:none;align-self:flex-end;font-weight:800;font-size:.92em;color:var(--acc)}
.grid.tight .co .more,.grid.tight .co .det b{display:none}
.grid.tight .co .by{margin:2px 0 3px}
.co.pic .det{flex:none;color:var(--muted);font-weight:700;-webkit-mask-image:none;mask-image:none}
@media (max-width:560px){#tiles{padding:10px 12px 12px;gap:8px}.grid{gap:10px}}

.bar{flex:none;display:flex;align-items:center;gap:10px;padding:8px 14px;background:var(--acc);color:#fff;border-bottom:3px solid var(--ink)}
.bar .ttl{font-weight:600;font-size:17px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.bar .ttl .sticker{font-size:15px;margin-right:6px}
.bar .sp{flex:1}
.bar button,.bar a.pill{font:inherit;cursor:pointer}
.bar button{background:#fff;color:var(--ink);border:2px solid var(--ink);border-radius:999px;font-weight:800;font-size:14px;padding:2px 12px;line-height:1.4}
.bar button:hover{background:#ffd34d}
.bar button:disabled{opacity:.4;cursor:default;background:#fff}
.bar .count{font-weight:800;font-size:14px;min-width:3.6em;text-align:center}
#slides{flex:1;min-height:0;padding:16px 20px 20px;width:100%;max-width:1840px;margin:0 auto}
.slide{display:none;height:100%;gap:22px;grid-template-columns:minmax(0,1fr) minmax(0,1.12fr);grid-template-rows:minmax(0,1fr)}
.slide.on{display:grid;animation:slidein .35s ease-out}
.slide.nopic{grid-template-columns:minmax(0,1fr)}
.slide.pic{grid-template-columns:minmax(0,1.7fr) minmax(0,1fr)}
@keyframes slidein{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.slide .photo{position:relative;background:var(--tint);overflow:hidden;min-height:0}
.slide .photo img{position:absolute;inset:16px;width:calc(100% - 32px);height:calc(100% - 32px);object-fit:contain;border-radius:12px}
.slide .txt{min-height:0;overflow:hidden;padding:1.1em 1.4em;font-size:var(--f,18px);line-height:1.45}
.slide.scroll .txt{overflow:auto}
.slide h2{margin:0;font-size:2em;font-weight:600;line-height:1.1}
.slide .by{margin:.35em 0 .5em;font-weight:800;font-size:.85em;color:var(--muted)}
.slide h3{margin:.7em 0 .1em;font-size:1em;font-weight:800;color:var(--acc);display:flex;gap:.35em;align-items:baseline}
.slide p{margin:.12em 0}.slide ul{margin:.12em 0;padding-left:1.3em}
.slide .body.c2{columns:2;column-gap:1.8em}
.slide .body.c2 .sec{break-inside:avoid}
.slide .none{color:var(--muted);font-weight:700;margin-top:.8em}
@media (max-width:700px) and (orientation:portrait){
  #slides{padding:10px 12px 12px}
  .slide,.slide.pic{grid-template-columns:minmax(0,1fr);grid-template-rows:minmax(0,38%) minmax(0,1fr);gap:12px}
  .slide.pic{grid-template-rows:minmax(0,1fr) auto}
  .slide .photo img{inset:8px;width:calc(100% - 16px);height:calc(100% - 16px)}
  .bar{padding:6px 10px;gap:6px}.bar .ttl,.bar .fs{display:none}.bar button{padding:2px 10px}
}
@media (prefers-reduced-motion:reduce){.slide.on{animation:none}a.co,a.card{transition:none}}
"""

SECTION_JS = """
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
var slides=[].slice.call(document.querySelectorAll('.slide')),cur=-1;
// Largest text size at which the whole profile fits its card, in one or two text columns
// (whichever reads bigger); scroll only if even the smallest size won't fit
function fitSlide(s){
  var t=s.querySelector('.txt'),b=s.querySelector('.body'),best={f:0,c2:false};
  s.classList.remove('scroll');
  [false,true].forEach(function(c2){
    if(c2&&t.clientWidth<620)return;
    b.classList.toggle('c2',c2);
    var lo=12,hi=34;
    while(hi-lo>0.5){var m=(lo+hi)/2;t.style.setProperty('--f',m+'px');if(t.scrollHeight>t.clientHeight+1)hi=m;else lo=m;}
    if(lo>best.f+1)best={f:lo,c2:c2}; // two columns only when clearly bigger
  });
  b.classList.toggle('c2',best.c2);
  t.style.setProperty('--f',best.f+'px');
  if(t.scrollHeight>t.clientHeight+1)s.classList.add('scroll');
}
function show(i){
  slides.forEach(function(s,k){s.classList.toggle('on',k==i);});
  cur=i;fitSlide(slides[i]);
  document.querySelector('.count').textContent=(i+1)+' / '+slides.length;
  document.querySelector('.prev').disabled=i==0;
  document.querySelector('.next').disabled=i==slides.length-1;
}
// Tile view by default; #p<n> presents that company
function view(){
  var m=/^#(p\\d+)$/.exec(location.hash),i=m?slides.findIndex(function(s){return s.id==m[1];}):-1,r=document.documentElement;
  r.className=i<0?'tiles':'full';
  if(i<0){cur=-1;fitTiles();}else show(i);
}
function go(d){
  var i=cur+d;if(cur<0||i<0||i>=slides.length)return;
  history.replaceState(null,'','#'+slides[i].id);show(i);
}
document.querySelector('.prev').onclick=function(){go(-1);};
document.querySelector('.next').onclick=function(){go(1);};
var fsb=document.querySelector('.fs');
if(document.fullscreenEnabled)fsb.onclick=function(){document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();};
else fsb.style.display='none';
document.addEventListener('fullscreenchange',function(){fsb.textContent=document.fullscreenElement?'Exit full screen':'Full screen';});
addEventListener('keydown',function(e){
  if(cur<0||e.altKey||e.ctrlKey||e.metaKey)return;
  if(['ArrowRight','PageDown',' '].indexOf(e.key)>=0){go(1);e.preventDefault();}
  else if(['ArrowLeft','PageUp'].indexOf(e.key)>=0){go(-1);e.preventDefault();}
  else if(e.key=='Escape'&&!document.fullscreenElement)location.hash='';
});
view();addEventListener('hashchange',view);
addEventListener('resize',function(){cur<0?fitTiles():fitSlide(slides[cur]);});
if(document.fonts)document.fonts.ready.then(function(){cur<0?fitTiles():fitSlide(slides[cur]);});
"""


def section_page(week, cfg, sec, data):
    code, lc = sec["code"], sec["code"].lower()
    posts = data["posts"]
    tiles, slides = [], []
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
            f'<span class="det">{det}</span><span class="more">Present ▶</span></span></a>')
        photo = (f'<div class="photo card"><img src="img/{lc}-{p["n"]}.jpg" alt="{esc(p["company"])}" loading="lazy"></div>'
                 if p["photo"] else "")
        body = full_html(tagline, secs) if has_text else '<p class="none">The details are in the picture.</p>'
        kind = "" if p["photo"] and has_text else (" pic" if p["photo"] else " nopic")
        slides.append(
            f'<article class="slide{kind}" id="p{p["n"]}" style="--tint:{tint}">{photo}<div class="txt card">'
            f'<h2 class="dsp">{esc(p["company"])}</h2><div class="by">by <span>{esc(p["nick"])}</span></div>'
            f'<div class="body">{body}</div></div></article>')
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
<section id="tiles"><div class="hint">Tap a company to <b>present</b> it to the class.</div><div class="grid">
{chr(10).join(tiles)}
</div></section>
<nav class="bar"><a class="pill" href="#">← All companies</a><span class="ttl dsp"><span class="sticker">{code}</span>{esc(cfg["activity"])}</span>
<span class="sp"></span><button class="prev" aria-label="Previous company">◀</button><span class="count"></span>
<button class="next" aria-label="Next company">▶</button><button class="fs">Full screen</button></nav>
<section id="slides">
{chr(10).join(slides)}
</section>
<script>{SECTION_JS}</script>
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
