#!/usr/bin/env python3
"""publish.py — THE SELF-WRITING BOOK's press (regulus-publish skill, mayur's order 2026-07-07).

assembles regulusdesk.com from src/template-body.html, commits, pushes, kicks the pages build,
then polls the LIVE domain (cache-busted) until the fingerprint appears — the ritual is not done
until the site itself proves it changed (fable-mode gate 4: fetch it back and grep).

usage:
  python3 src/publish.py                     # fingerprint = newest day label in the data array
  python3 src/publish.py --expect "8 jul"    # explicit fingerprint
  python3 src/publish.py --no-deploy         # assemble only (local check)
exit 0 = live-verified · 1 = failed (reason printed)
"""
import re, sys, subprocess, time, pathlib, random

REPO = pathlib.Path(__file__).resolve().parent.parent
SRC  = REPO / "src" / "template-body.html"
OUT  = REPO / "index.html"
URL  = "https://regulusdesk.com"

META = """<meta name="description" content="regulus desk — a private systematic derivatives desk in india. a transparent book: the war log, the proving ground, lessons and mistakes — every result in R, reconciled to broker records.">
<meta property="og:title" content="regulus desk — the transparent book">
<meta property="og:description" content="the war log, the proving ground, the ledger of mistakes — every result broker-reconciled, in R.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://regulusdesk.com">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🦁</text></svg>">
"""

def sh(*cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO), **kw)

def assemble() -> str:
    src = SRC.read_text()
    head, body = src.split("</style>", 1)
    head += "</style>"
    html = ("<!doctype html>\n<html lang=\"en\">\n<head>\n"
            + head.replace("<style>", META + "<style>")
            + "\n</head>\n<body>\n" + body.strip() + "\n</body>\n</html>\n")
    OUT.write_text(html)
    return html

def newest_day(html: str) -> str:
    days = re.findall(r"\{d:'([^']+)'", html)
    if not days:
        raise SystemExit("no data array found — template broken")
    return days[-1]

def main() -> int:
    expect = None
    args = sys.argv[1:]
    if "--expect" in args:
        expect = args[args.index("--expect") + 1]
    html = assemble()
    fp = expect or newest_day(html)
    print(f"assembled {len(html):,} bytes · fingerprint: '{fp}'")
    if "--no-deploy" in args:
        return 0
    # commit + push (append-only history; nothing force-pushed, law viii)
    sh("git", "add", "-A")
    c = sh("git", "commit", "-m", f"publish: {time.strftime('%Y-%m-%d %H:%M')} IST — the book updated ({fp})")
    if "nothing to commit" in c.stdout + c.stderr:
        print("no changes to publish — site already current")
    p = sh("git", "push")
    if p.returncode != 0:
        print("PUSH FAILED:", (p.stderr or p.stdout)[-300:]); return 1
    sh("gh", "api", "repos/mayurcodezz/regulusdesk/pages/builds", "-X", "POST")
    # verify LIVE (the gate): poll cache-busted until fingerprint serves
    deadline = time.time() + 15 * 60
    while time.time() < deadline:
        r = sh("curl", "-s", "-m", "15", f"{URL}?v={random.randint(1,10**9)}")
        if fp in r.stdout:
            print(f"✅ LIVE-VERIFIED: '{fp}' serving on {URL}")
            return 0
        st = sh("gh", "api", "repos/mayurcodezz/regulusdesk/pages/builds/latest", "--jq", ".status")
        if "errored" in st.stdout:
            # one automatic unstick: empty commit re-kick (the known stuck-build failure)
            sh("git", "commit", "--allow-empty", "-m", "kick stuck pages build")
            sh("git", "push")
            sh("gh", "api", "repos/mayurcodezz/regulusdesk/pages/builds", "-X", "POST")
        time.sleep(30)
    print("❌ NOT LIVE after 15 min — check gh pages build"); return 1

if __name__ == "__main__":
    sys.exit(main())
