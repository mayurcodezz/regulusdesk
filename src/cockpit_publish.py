#!/usr/bin/env python3
"""cockpit_publish.py — writes the encrypted live book to regulusdesk.com/desk (KAPIDHVAJA cockpit).

mayur's order 2026-07-08: every trade written the moment it exists — time in, contract, view, qty, entry,
mark, leg P&L, book total, envelope meter — behind a passphrase, so he never needs the broker app or telegram spam.

payload: AES-256-GCM, PBKDF2-SHA256 (200k iters). the passphrase NEVER leaves this machine; it is read from
~/.config/regulus/cockpit.pass (chmod 600). ciphertext in a public repo is acceptable for this data grade.

usage: python3 src/cockpit_publish.py [--no-deploy]
data sources: ~/Mriga/edge/whales/trade_calibration.csv (today, mode=live) + live marks via warm_client.
"""
import base64, csv, datetime, json, os, pathlib, re, subprocess, sys

REPO = pathlib.Path(__file__).resolve().parent.parent
WHALES = pathlib.Path('/Users/shiro/Mriga/edge/whales')
PASSFILE = pathlib.Path.home() / '.config/regulus/cockpit.pass'
R_UNIT = 40_000
ENVELOPE = 800_000   # mayur's ruling 2026-07-08

LANE = lambda hhmm: ('pavan' if hhmm <= '0925' else 'dawn' if '0940' <= hhmm <= '0959' else 'hunter/fresh')


def today_legs():
    today = datetime.date.today().isoformat()
    legs, marks = [], {}
    # live marks (option ltp per underlying) via the desk's own reader
    sys.path.insert(0, str(WHALES))
    try:
        os.environ.setdefault('ALL_PROXY', 'socks5h://127.0.0.1:1080')
        os.environ.setdefault('HTTPS_PROXY', 'socks5h://127.0.0.1:1080')
        from warm_client import get_client
        c = get_client()
        res = c.get_positions_for_user(segment='FNO') or {}
        for p in (res.get('positions') or []):
            sym = p['trading_symbol']
            und = re.match(r'([A-Z&]+?)26', sym)
            marks[(und.group(1) if und else sym)] = p
    except Exception as e:
        print(f'[marks] unavailable ({str(e)[:60]}) — publishing entries without live marks')
    for r in csv.DictReader(open(WHALES / 'trade_calibration.csv')):
        if r['mode'] != 'live' or not r['opened_at'].startswith(today):
            continue
        t = r['opened_at'][11:16]
        contract = (r.get('catalyst') or '').replace('LONG fast-fire ', '').replace('SHORT fast-fire ', '') or r['instrument']
        p = marks.get(r['instrument'], {})
        qty = int(float(p.get('debit_quantity') or 0)) or None
        entry = float(r['entry'] or 0)
        ltp = None
        if p:
            net = p.get('quantity') or 0
            if net:  # open at broker → mark = ltp unavailable via positions; use net_price? keep last known
                ltp = None
        # leg pnl: realized if closed, else from broker realised field when flat, else None (mark unknown here)
        pnl = float(r['realized_pnl']) if r.get('realized_pnl') else None
        legs.append({
            't': t, 'lane': LANE(t.replace(':', '')),
            'c': f"{r['instrument']} {contract}".strip()[:34],
            'v': ('short' if 'SHORT' in (r.get('direction') or r.get('catalyst') or '').upper() or 'PE' in contract else 'long'),
            'q': qty or 0, 'entry': entry, 'mark': None, 'pnl': pnl,
            'state': r['status'],
        })
    return legs


def live_marks_fill(legs):
    """fill marks + open-leg pnl from live_pnl's own computation (one authoritative source)."""
    try:
        out = subprocess.run(['/Users/shiro/krishna-yahn/.venv310/bin/python3', str(WHALES / 'live_pnl.py')],
                             capture_output=True, text=True, timeout=90,
                             env={**os.environ, 'ALL_PROXY': 'socks5h://127.0.0.1:1080',
                                  'HTTPS_PROXY': 'socks5h://127.0.0.1:1080'}).stdout
        for line in out.splitlines():
            m = re.match(r'\s+([A-Z&]+)\s+q\s*([+-]?\d+)\s+avg([\d.]+)\s+ltp([\d.None]+)\s+₹([+-][\d,]+)', line)
            if not m:
                continue
            sym, q, avg, ltp, pnl = m.groups()
            for l in legs:
                if l['c'].startswith(sym + ' ') and l['state'] == 'OPEN':
                    l['q'] = l['q'] or abs(int(q))
                    try:
                        l['mark'] = float(ltp)
                    except ValueError:
                        pass
                    l['pnl'] = float(pnl.replace(',', '').replace('−', '-'))
    except Exception as e:
        print(f'[live] mark fill skipped: {str(e)[:60]}')
    return legs


def encrypt(obj, passphrase):
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200_000).derive(passphrase.encode())
    data = AESGCM(key).encrypt(iv, json.dumps(obj).encode(), None)
    b = lambda x: base64.b64encode(x).decode()
    return {'salt': b(salt), 'iv': b(iv), 'data': b(data)}


def main():
    if not PASSFILE.exists():
        print(f'no passphrase at {PASSFILE} — create it (chmod 600) first'); return 1
    passphrase = PASSFILE.read_text().strip()
    legs = live_marks_fill(today_legs())
    deployed = 0
    for r in csv.DictReader(open(WHALES / 'trade_calibration.csv')):
        if r['mode'] == 'live' and r['status'] == 'OPEN':
            deployed += float(r['risk_rupees'] or 0)
    capital = json.load(open(WHALES / 'capital_curve.json'))['days'][-1]['capital']
    payload = {
        'asof': datetime.datetime.now().strftime('%H:%M'),
        'r_unit': R_UNIT, 'envelope': ENVELOPE, 'deployed': int(deployed), 'capital': capital,
        'legs': sorted(legs, key=lambda l: l['t']),
        'note': f'{len(legs)} trades entered today · marks as of publish time · the machine holds the pen.',
    }
    (REPO / 'desk-data.json').write_text(json.dumps(encrypt(payload, passphrase)))
    print(f"cockpit payload: {len(legs)} legs · deployed ₹{deployed:,.0f} · encrypted")
    if '--no-deploy' in sys.argv:
        return 0
    subprocess.run(['git', 'add', 'desk.html', 'desk-data.json'], cwd=REPO)
    subprocess.run(['git', 'commit', '-q', '-m', f'cockpit: {payload["asof"]} IST'], cwd=REPO)
    p = subprocess.run(['git', 'push', '-q'], cwd=REPO, capture_output=True, text=True)
    print('pushed' if p.returncode == 0 else f'push failed: {p.stderr[-200:]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
