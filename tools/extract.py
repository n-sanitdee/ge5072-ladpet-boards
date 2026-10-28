#!/usr/bin/env python3
"""Pull the posts out of a cleaned "Save the Ladpet" export.

    python3 tools/extract.py wk12 ca48 path/to/export.html

Writes <week>/data/<code>.json (saved time, prompt, posts) and the full photos
as <week>/img/<code>-<n>.jpg, plus <week>/thumbs/<code>-<n>.jpg (≤480 px) when
missing. Fill in each post's "company" by hand, then run tools/build.py.
An existing data file keeps its company names.
"""
import base64
import html
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    week, code, src = sys.argv[1], sys.argv[2].lower(), Path(sys.argv[3])
    s = src.read_text(encoding="utf-8")
    saved = re.search(r"<header>.*?<p>([^<·]+?)\s*·\s*\d+ posts</p>", s, re.S).group(1).strip()
    prompt = re.search(r'</header>\s*<p style="[^"]*">(.*?)</p>', s, re.S)
    prompt = [l.strip(" -") for l in html.unescape(prompt.group(1)).splitlines() if l.strip(" -")] if prompt else []
    out = ROOT / week / "data" / f"{code}.json"
    old = {p["n"]: p for p in json.loads(out.read_text(encoding="utf-8"))["posts"]} if out.exists() else {}
    (ROOT / week / "img").mkdir(exist_ok=True)
    (ROOT / week / "thumbs").mkdir(exist_ok=True)
    posts = []
    for n, body in re.findall(r'<article id="p(\d+)">(.*?)</article>', s, re.S):
        n = int(n)
        nick = html.unescape(re.search(r"<h2>(.*?)</h2>", body).group(1))
        text = re.search(r'<p class="text">(.*?)</p>', body, re.S)
        text = html.unescape(text.group(1)) if text else ""
        img = re.search(r'src="data:image/jpeg;base64,([^"]+)"', body)
        if img:
            full = ROOT / week / "img" / f"{code}-{n}.jpg"
            full.write_bytes(base64.b64decode(img.group(1)))
            thumb = ROOT / week / "thumbs" / f"{code}-{n}.jpg"
            if not thumb.exists():
                subprocess.run(["sips", "-Z", "480", "-s", "formatOptions", "80", str(full), "--out", str(thumb)],
                               check=True, capture_output=True)
        posts.append({"n": n, "nick": nick, "company": old.get(n, {}).get("company", ""),
                      "photo": bool(img), "text": text})
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"saved": saved, "prompt": prompt, "posts": posts}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"{out}: {len(posts)} posts; companies missing: {[p['n'] for p in posts if not p['company']]}")


if __name__ == "__main__":
    main()
