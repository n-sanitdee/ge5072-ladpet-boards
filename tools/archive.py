#!/usr/bin/env python3
"""Save Ladpet walls as boards, then delete walls that are 3 hours old.

    python3 tools/archive.py            # run by .github/workflows/archive.yml every 10 minutes
    python3 tools/archive.py --dry-run  # show what it would do; writes and deletes nothing

A wall is saved when the host pressed Finish, closed joining, or the wall is
2½ hours old (just before it would expire), as long as its posts are showing
(a live wall, or revealed) and at least one group has posted. Walls named in a
<week>/sections.json "wall" field (e.g. BS11's 109114) are saved too.

Where it goes: a wall named in a sections.json goes to that folder; wk12-company
goes to wk12/; every other activity to a folder named after its preset
(wk13-spot9/, …); a custom wall to wall-<title>/. A new folder gets a
sections.json with all six sections. A section's data file is only ever
replaced by the same wall, so hand-made boards (CA48, EC30) are never touched;
company names typed by hand into a data file are kept.

Signs in to Firebase as a throw-away anonymous user over REST (the public web
config, no secrets) and deletes that user at the end. Deleting a wall needs it
to be 3 h old (database.rules.json); a wall is only deleted after it was saved
(or had nothing to save). The Ladpet app's own clean-up waits 6 h.
"""
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageOps

import build

ROOT = Path(__file__).resolve().parent.parent
API_KEY = "AIzaSyByVi2sCLbz9FF8561o9d8bUxaXfpoKi0A"
DB = "https://ge5072-live-quiz-default-rtdb.asia-southeast1.firebasedatabase.app"
TH = timezone(timedelta(hours=7))
STALE = 3 * 3600 * 1000
SAVE_AFTER = int(2.5 * 3600 * 1000)
DRY = "--dry-run" in sys.argv

# Class times (Mew, 28 Oct 2026): weekday 0 = Monday
TIMETABLE = [("CA48", 0, "11:30"), ("EC30", 0, "15:20"), ("BS11", 2, "08:30"),
             ("TS66", 2, "11:30"), ("CA50", 3, "11:30"), ("AC21", 3, "15:20")]
SECTIONS = {c for c, _, _ in TIMETABLE}

# Copied from ge5072-class-wall src/lib/presets.ts: preset → (week, activity, title, noun, singular)
PRESETS = {
    "wk12-company": ("Week 12", "Brainstorm", "Your Company", "companies", "company"),
    "wk13-spot9": ("Week 13", "Think-Pair-Share", "Spot the Nine Mistakes", "pairs", "pair"),
    "wk13-profile": ("Week 13", "Brainstorm", "Map Your Company Profile", "companies", "company"),
    "wk14-chart": ("Week 14", "Think-Pair-Share", "Describe a Chart", "pairs", "pair"),
    "wk14-changed": ("Week 14", "Brainstorm", "What Changed in Your Company?", "companies", "company"),
}
FOLDER = {"wk12-company": "wk12"}


# ── Firebase over REST ──────────────────────────────────────────
def http(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"null")


class Fb:
    def __init__(self):
        r = http("POST", f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}", {"returnSecureToken": True})
        self.token = r["idToken"]

    def get(self, path, **q):
        q = {k: json.dumps(v) if isinstance(v, str) else v for k, v in q.items()}
        return http("GET", f"{DB}/{path}.json?" + urllib.parse.urlencode({**q, "auth": self.token}))

    def delete_walls(self, codes):
        body = {}
        for c in codes:
            body[f"walls/{c}"] = None
            body[f"wallIndex/{c}"] = None
        http("PATCH", f"{DB}/.json?auth={self.token}", body)

    def close(self):
        try:
            http("POST", f"https://identitytoolkit.googleapis.com/v1/accounts:delete?key={API_KEY}", {"idToken": self.token})
        except Exception as e:  # noqa: BLE001
            print("could not delete the temporary user:", e)


# ── posts → board data ──────────────────────────────────────────
FULL_NAME = re.compile(r"(?:[A-Za-z]+ [A-Za-z]+|[฀-๿]+ [฀-๿]+)")


def drop_name_list(text):
    """The boards are public: drop a list of students' full names (2+ 'First Last' lines) opening the post."""
    lines = text.split("\n")
    i = 0
    while i < len(lines) and FULL_NAME.fullmatch(lines[i].strip()):
        i += 1
    return "\n".join(lines[i:]).strip() if i >= 2 else text


def post_text(p):
    if (p.get("text") or "").strip():
        return drop_name_list(p["text"].replace(" ", "\n").strip())
    fields = p.get("fields") or {}
    keys = sorted((k for k in fields if re.fullmatch(r"f\d+", k)), key=lambda k: int(k[1:]))
    return "\n".join(fields[k].strip() for k in keys if fields[k].strip())


def guess_company(text, team):
    """The company's name from the post ("Company: X", "Our company is called X", a short first line), else the group name."""
    m = re.search(r"(?im)^\W*company(?:\s*name)?\s*[:：]\s*(.+?)\s*$", text) or \
        re.search(r"(?i)\bour (?:company|store|shop|brand) is called ([^.\n]{2,40}?)[.\n]", text + "\n")
    if m:
        return m.group(1).strip(" *\"“”")
    first = text.split("\n", 1)[0].strip(" *#\"“”")
    if first and len(first) <= 40 and not re.match(r"^\d+[.)]", first) and not first.endswith((".", ":")):
        return first
    return team


def save_jpeg(data_url, full, thumb):
    raw = __import__("base64").b64decode(data_url.split(",", 1)[1])
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    big = im.copy()
    big.thumbnail((1400, 1400))
    big.save(full, "JPEG", quality=82, optimize=True)
    small = im.copy()
    small.thumbnail((480, 480))
    small.save(thumb, "JPEG", quality=80, optimize=True)


# ── folders ─────────────────────────────────────────────────────
def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "wall"


def linked_walls():
    out = {}
    for f in ROOT.glob("*/sections.json"):
        for sec in json.loads(f.read_text(encoding="utf-8"))["sections"]:
            if sec.get("wall"):
                out[sec["wall"]] = (f.parent.name, sec["code"])
    return out


def new_folder_cfg(pub, created):
    week, activity, title, noun, one = PRESETS.get(pub["preset"], ("", "Class wall", pub.get("title") or "Class wall", "posts", "post"))
    monday = (created - timedelta(days=created.weekday())).replace(hour=0, minute=0)
    full = f"{week} {activity}: {title}" if week else title
    secs = []
    for code, wd, hm in sorted(TIMETABLE, key=lambda t: t[0]):
        d = monday + timedelta(days=wd)
        secs.append({"code": code, "class": f"{d:%a} {d.day} {d:%b} · {hm}"})
    return {
        "title": full,
        "short": f"{week} {activity}".strip() or title,
        "activity": title,
        "blurb": f"Posts from the class {activity.lower()} sessions, week of {monday.day} {monday:%B %Y}.",
        "noun": noun,
        "one": one,
        "sections": secs,
    }


# ── one wall ────────────────────────────────────────────────────
def archive(fb, code, pub, created_ms, linked):
    created = datetime.fromtimestamp(created_ms / 1000, TH)
    section = pub.get("section")
    if code in linked:
        folder, section = linked[code]
    elif section not in SECTIONS:
        print(f"  {code}: section {section!r} is not a class — skipped")
        return "skip"
    elif pub["preset"] == "custom":
        folder = "wall-" + slug(pub.get("title") or code)
    else:
        folder = FOLDER.get(pub["preset"], pub["preset"])
    lc = section.lower()
    d = ROOT / folder
    cfg_file = d / "sections.json"
    cfg = json.loads(cfg_file.read_text(encoding="utf-8")) if cfg_file.exists() else new_folder_cfg(pub, created)
    data_file = d / "data" / f"{lc}.json"
    old = json.loads(data_file.read_text(encoding="utf-8")) if data_file.exists() else None
    if old and old.get("wall") != code:
        print(f"  {code}: {folder}/{lc} already has a board from {old.get('wall') or 'a saved export'} — left alone")
        return "skip"

    teams = fb.get(f"walls/{code}/teams") or {}
    posts = fb.get(f"walls/{code}/posts") or {}
    done = sorted(((tid, p) for tid, p in posts.items() if p.get("done") and tid in teams), key=lambda kv: kv[1].get("at", 0))
    if not done:
        print(f"  {code}: nobody has posted — nothing to save")
        return "empty"

    olds = {p.get("id"): p for p in (old or {}).get("posts", [])}
    next_n = max([p["n"] for p in olds.values()] + [0]) + 1
    out, changed = [], old is None
    for tid, p in done:
        o = olds.get(tid)
        if o:
            n = o["n"]
        else:
            n, next_n = next_n, next_n + 1
        text = post_text(p)
        team = teams[tid].get("name", "")
        row = {"n": n, "id": tid, "at": p.get("at", 0), "nick": team,
               "company": o["company"] if o and o.get("company") else guess_company(text, team) if cfg.get("noun", "companies") == "companies" else team,
               "photo": bool(p.get("photo")), "text": text}
        if row["photo"]:
            full, thumb = d / "img" / f"{lc}-{n}.jpg", d / "thumbs" / f"{lc}-{n}.jpg"
            if not o or o.get("at") != row["at"] or not full.exists():
                url = fb.get(f"walls/{code}/photos/{tid}")
                if url and not DRY:
                    full.parent.mkdir(parents=True, exist_ok=True)
                    thumb.parent.mkdir(parents=True, exist_ok=True)
                    save_jpeg(url, full, thumb)
                row["photo"] = bool(url)
        if o != row:
            changed = True
        out.append(row)
    out.sort(key=lambda r: r["n"])
    if not changed and len(out) == len(olds):
        print(f"  {code}: {folder}/{lc} up to date ({len(out)} posts)")
        return "same"

    last = max(r["at"] for r in out) / 1000
    saved = datetime.fromtimestamp(last, TH)
    prompt = [l.strip() for l in (pub.get("prompt") or "").splitlines() if l.strip()]
    print(f"  {code}: saving {len(out)} posts to {folder}/{lc}")
    if DRY:
        return "saved"
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text(json.dumps({"wall": code, "saved": f"{saved:%A}, {saved.day} {saved:%B %Y} at {saved:%H:%M}",
                                     "prompt": prompt, "posts": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    for sec in cfg["sections"]:
        if sec["code"] == section:
            sec["wall"] = code
    cfg_file.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    build.build(folder)
    return "saved"


def main():
    fb = Fb()
    try:
        now = int(time.time() * 1000)
        index = fb.get("wallIndex", orderBy="createdAt", limitToFirst=100) or {}
        linked = linked_walls()
        codes = {c: v.get("createdAt", 0) for c, v in index.items()}
        for c in linked:
            codes.setdefault(c, None)
        deletable = []
        for code, created_ms in sorted(codes.items()):
            pub = fb.get(f"walls/{code}/pub")
            if not pub:
                continue
            if created_ms is None:
                created_ms = (fb.get(f"walls/{code}/meta") or {}).get("createdAt", now)
            age = now - created_ms
            showing = pub.get("live") or pub.get("revealed")
            due = pub.get("ended") or pub.get("locked") or age >= SAVE_AFTER or code in linked
            state = ("ended" if pub.get("ended") else "joining closed" if pub.get("locked") else "open") + f", {age / 3600000:.1f} h"
            print(f"{code} {pub.get('section')} {pub.get('preset')} ({state})")
            result = "wait"
            if due and showing:
                try:
                    result = archive(fb, code, pub, created_ms, linked)
                except Exception as e:  # noqa: BLE001 — keep the wall; try again next run
                    print(f"  {code}: FAILED, kept for the next run: {e!r}")
                    result = "failed"
            elif due:
                print("  posts still hidden (not revealed) — not saved")
                result = "hidden"
            if code in index and age >= STALE + 60_000 and result in ("saved", "same", "empty", "skip", "hidden"):
                deletable.append(code)
        if deletable:
            print("deleting 3-hour-old walls:", ", ".join(deletable))
            if not DRY:
                fb.delete_walls(deletable)
    finally:
        fb.close()


if __name__ == "__main__":
    main()
