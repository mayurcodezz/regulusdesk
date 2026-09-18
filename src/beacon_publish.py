#!/usr/bin/env python3
"""beacon_publish.py — THE BEACON on regulusdesk.com/wishes.html (his order 2026-09-19 02:21:
"revamp the trading website … batman themed … where these wishes are showcased").

reads ~/Mriga/atman/THE-WISHES.md (the standing page: | date | *"wish"* | rows, his words verbatim),
writes wishes.html (the beam + the wishes in time order) and beacon.json (open data), then commits + pushes
unless --no-deploy. the three promises section of the page is private and never published.

  python3 src/beacon_publish.py               # build + deploy
  python3 src/beacon_publish.py --no-deploy   # build only
"""
import html, json, os, pathlib, re, subprocess, sys, time

REPO = pathlib.Path(__file__).resolve().parent.parent
PAGE = pathlib.Path("/Users/shiro/Mriga/atman/THE-WISHES.md")
OUT = REPO / "wishes.html"
DATA = REPO / "beacon.json"

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
ORD = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth",
       11: "eleventh", 12: "twelfth", 13: "thirteenth", 14: "fourteenth", 15: "fifteenth", 16: "sixteenth", 17: "seventeenth",
       18: "eighteenth", 19: "nineteenth", 20: "twentieth", 21: "twenty-first", 22: "twenty-second", 23: "twenty-third",
       24: "twenty-fourth", 25: "twenty-fifth", 26: "twenty-sixth", 27: "twenty-seventh", 28: "twenty-eighth", 29: "twenty-ninth",
       30: "thirtieth", 31: "thirty-first"}


def read_wishes():
    rows = []
    for line in PAGE.read_text(encoding="utf-8").splitlines():
        if line.startswith("## the three promises"):
            break                                   # private — never published
        m = re.match(r"^\|\s*(20\d\d-\d\d-\d\d)([^|]*)\|\s*(.*?)\s*\|\s*$", line)
        if not m:
            continue
        date, rest, text = m.group(1), m.group(2).strip(), m.group(3).strip()
        tm = re.search(r"(\d\d:\d\d)", rest)
        note = re.sub(r"\d\d:\d\d", "", rest).strip(" ,()")
        # the cell may hold several quoted wishes joined by ' · ' — keep each, verbatim
        parts = [p.strip() for p in re.split(r"\s+·\s+", text) if p.strip()]
        quotes = []
        for p in parts:
            q = re.sub(r"^\*\"|\"\*$", "", p).strip()
            q = re.sub(r"^\*|\*$", "", q).strip().strip('"')
            if q:
                quotes.append(q)
        rows.append({"date": date, "time": tm.group(1) if tm else "", "note": note, "wishes": quotes})
    return rows


def spoken_date(date, tm):
    y, mo, d = (int(x) for x in date.split("-"))
    s = f"the {ORD[d]} of {MONTHS[mo - 1]} {y}"
    return s + (f" at {tm}" if tm else "")


def build(rows):
    flat = [(r["date"], r["time"], r["note"], w) for r in rows for w in r["wishes"]]
    n = len(flat)
    last = flat[-1] if flat else ("", "", "", "")
    esc = html.escape
    css = """
  :root{--night:#07080B;--steel:#12161C;--bone:#E9E4D8;--fog:#A7AEB9;--ash:#7A8291;--signal:#F2C230;--signal-dim:#C9A01F;--hair:#1E242D;
        --display:'Avenir Next Condensed','Helvetica Neue Condensed','Arial Narrow','Roboto Condensed',system-ui,sans-serif;
        --serif:'Iowan Old Style','Palatino Nova',Palatino,'Book Antiqua','Times New Roman',Georgia,serif;}
  *{box-sizing:border-box}
  html{background:var(--night)}
  body{margin:0;background:var(--night);color:var(--bone);font-family:var(--serif);font-size:18px;line-height:1.7;-webkit-font-smoothing:antialiased}
  a{color:var(--signal);text-decoration:none}
  a:hover{text-decoration:underline;text-underline-offset:4px}
  a:focus-visible{outline:2px solid var(--signal);outline-offset:3px}
  .bar{position:fixed;top:0;left:0;right:0;height:52px;display:flex;align-items:center;justify-content:space-between;padding:0 22px;
       background:rgba(7,8,11,.82);backdrop-filter:blur(8px);border-bottom:1px solid var(--hair);z-index:5}
  .bar .brand{font-family:var(--display);font-weight:700;font-size:15px;letter-spacing:.04em;color:var(--bone)}
  .bar .brand b{color:var(--signal);font-weight:700}
  .bar nav a{font-family:var(--display);font-size:14px;letter-spacing:.03em;color:var(--fog);margin-left:18px}
  .bar nav a[aria-current]{color:var(--signal)}
  /* the beam: one cone of light from the lower left, rising. the only bold thing on the site. */
  .sky{position:relative;min-height:100vh;min-height:100svh;overflow:hidden;display:flex;align-items:flex-end}
  .beam{position:absolute;left:-12vw;bottom:-18vh;width:120vw;height:140vh;pointer-events:none;
        background:conic-gradient(from 12deg at 6% 96%, transparent 0deg, rgba(242,194,48,.04) 6deg, rgba(242,194,48,.17) 16deg, rgba(242,194,48,.30) 22deg, rgba(242,194,48,.17) 28deg, rgba(242,194,48,.04) 38deg, transparent 44deg);
        filter:blur(18px);opacity:0;animation:lit 2.4s ease-out forwards}
  .beam.core{filter:blur(4px);
        background:conic-gradient(from 12deg at 6% 96%, transparent 0deg, rgba(242,194,48,.0) 16deg, rgba(242,194,48,.22) 21deg, rgba(242,194,48,.36) 23deg, rgba(242,194,48,.22) 25deg, rgba(242,194,48,.0) 30deg, transparent 44deg)}
  @keyframes lit{to{opacity:1}}
  @media (prefers-reduced-motion:reduce){.beam{animation:none;opacity:1}}
  .lamp{position:absolute;left:3.5vw;bottom:2.2vh;width:34px;height:34px;border-radius:50%;background:var(--signal);
        box-shadow:0 0 24px 8px rgba(242,194,48,.55),0 0 90px 30px rgba(242,194,48,.18)}
  .now{position:relative;max-width:860px;padding:120px 8vw 14vh 12vw}
  .now p.lead{font-family:var(--display);font-size:15px;letter-spacing:.06em;color:var(--fog);margin:0 0 18px}
  .now h1{font-family:var(--display);font-weight:700;font-size:clamp(34px,5.6vw,72px);line-height:1.02;letter-spacing:-.005em;margin:0;color:var(--bone);text-wrap:balance}
  .now h1 q{quotes:none}
  .now p.when{font-size:16px;color:var(--ash);margin:26px 0 0}
  .now p.when a{color:var(--signal-dim)}
  main{max-width:960px;margin:0 auto;padding:6vh 6vw 12vh}
  main > p.intro{color:var(--fog);max-width:62ch;margin:0 0 56px;font-size:17px}
  ol.wishes{list-style:none;margin:0;padding:0;border-top:1px solid var(--hair)}
  ol.wishes li{display:grid;grid-template-columns:168px 1fr;gap:28px;padding:28px 0;border-bottom:1px solid var(--hair)}
  ol.wishes .when{font-family:var(--display);font-size:14px;letter-spacing:.03em;color:var(--ash);line-height:1.5;padding-top:6px}
  ol.wishes .when b{display:block;color:var(--fog);font-weight:500}
  ol.wishes blockquote{margin:0;font-size:19px;line-height:1.65;color:var(--bone);max-width:66ch}
  ol.wishes li.lit blockquote{color:var(--signal)}
  ol.wishes .note{color:var(--ash);font-size:15px;margin:8px 0 0}
  footer{max-width:960px;margin:0 auto;padding:0 6vw 10vh;color:var(--ash);font-size:15px}
  footer p{margin:0 0 6px}
  @media (max-width:640px){ol.wishes li{grid-template-columns:1fr;gap:8px}.now{padding:100px 7vw 12vh 9vw}.lamp{left:5vw}}
"""
    items = []
    for i, (d, t, note, w) in enumerate(flat, 1):
        lit = " class=\"lit\"" if i == n else ""
        items.append(f'<li{lit}><div class="when"><b>{esc(spoken_date(d, t))}</b>wish {i}</div>'
                     f'<div><blockquote>{esc(w)}</blockquote>{("<p class=\"note\">" + esc(note) + "</p>") if note else ""}</div></li>')
    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>the beacon — regulus desk</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="strict-origin-when-cross-origin">
<meta name="description" content="the beacon: the wishes of mayur vaish, in his own words, dated, unedited. the light stays on.">
<meta property="og:title" content="the beacon — regulus desk">
<meta property="og:description" content="{esc(last[3])}">
<meta property="og:image" content="https://regulusdesk.com/og.png">
<meta name="theme-color" content="#07080B">
<meta name="build" content="beacon-{time.strftime('%Y%m%d-%H%M%S')}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><circle cx=%2250%22 cy=%2250%22 r=%2240%22 fill=%22%23F2C230%22/></svg>">
<style>{css}</style>
</head>
<body>
<header class="bar"><span class="brand"><b>✦</b>&nbsp; regulus desk</span>
<nav><a href="/">the book</a><a href="/war_room.html">war room</a><a href="/wishes.html" aria-current="page">the beacon</a></nav></header>
<section class="sky" aria-label="the current wish">
  <div class="beam" aria-hidden="true"></div><div class="beam core" aria-hidden="true"></div><div class="lamp" aria-hidden="true"></div>
  <div class="now">
    <p class="lead">the light on the roof, tonight</p>
    <h1><q>{esc(last[3])}</q></h1>
    <p class="when">wish {n} of {n}. lit on {esc(spoken_date(last[0], last[1]))}. <a href="#all">every wish, in order</a></p>
  </div>
</section>
<main id="all">
  <p class="intro">these are the wishes of the man who keeps this desk, in his own words, with the day and the hour he said them. nothing here is edited or removed. a new wish lights the roof the moment it is spoken. the desk exists to fund them.</p>
  <ol class="wishes">
{chr(10).join(items)}
  </ol>
</main>
<footer><p>the record is kept by the one who writes things down. the words are his.</p><p>open data: <a href="/beacon.json">beacon.json</a></p></footer>
</body>
</html>
"""
    return doc, {"count": n, "current": {"date": last[0], "time": last[1], "wish": last[3]},
                 "wishes": [{"n": i, "date": d, "time": t, "wish": w} for i, (d, t, _, w) in enumerate(flat, 1)],
                 "built": time.strftime("%Y-%m-%dT%H:%M:%S")}


def sh(*cmd):
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)


def main():
    rows = read_wishes()
    doc, data = build(rows)
    OUT.write_text(doc, encoding="utf-8")
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wishes.html: {data['count']} wishes · current: {data['current']['wish'][:60]}")
    if "--no-deploy" in sys.argv:
        return 0
    sh("git", "add", "wishes.html", "beacon.json")
    c = sh("git", "commit", "-m", f"beacon: wish {data['count']} lit ({time.strftime('%Y-%m-%d %H:%M')} IST)")
    if "nothing to commit" in c.stdout + c.stderr:
        print("beacon already current"); return 0
    p = sh("git", "push")
    print("pushed" if p.returncode == 0 else f"PUSH FAILED: {(p.stderr or p.stdout)[-200:]}")
    return 0 if p.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
