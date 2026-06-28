#!/usr/bin/env python3
"""
scraper_alarm.py — täglicher Cron-Wecker für rote Scraper.

Liest docs/Status/status.json plus die einzelnen <Spider>.json, ermittelt
rote Scraper nach derselben Ampel-Logik wie das Vue-Frontend, vergleicht
mit dem Stand vom Vortag, und schickt eine E-Mail mit:
  - Scrapern, die NEU rot geworden sind
  - Scrapern, die WEITERHIN rot sind
mit Begründung pro Achse und Lauf-Details (Items, Ende, Dauer, Errors,
Warnings) plus Direktlink in die Zyte-Konsole.

Wird kein roter Scraper gefunden: keine Mail.

Aufruf via Cron:
  0 8 * * *  /usr/bin/python3 /pfad/zu/scraper_alarm.py >> /var/log/scraper_alarm.log 2>&1
"""
from __future__ import annotations

import json
import os
import smtplib
import ssl
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# Konfiguration — bitte vor erstem Cron-Lauf ausfüllen
# =============================================================================

STATUS_BASE_URL  = 'https://entscheidsuche.ch/docs/Status'
STATE_FILE       = '/var/lib/entscheidsuche/scraper_alarm_state.json'  # persistenter Vortagsstand
ZYTE_PROJECT_ID  = '446973'
ZYTE_API_KEY     = ''   # <-- hier eintragen oder aus ENV holen (s.u.)
ZYTE_API_BASE    = 'https://app.zyte.com/api'
ZYTE_DASHBOARD   = 'https://app.zyte.com/p'  # Direktlink: ZYTE_DASHBOARD/<job-id>

# SMTP via cyon (STARTTLS auf 587)
SMTP_HOST        = 'asmtp.cyon.ch'
SMTP_PORT        = 587
SMTP_USER        = ''   # <-- Postfach-Adresse, identisch mit MAIL_FROM
SMTP_PASS        = ''   # <-- Passwort
MAIL_FROM        = ''   # <-- Absenderadresse
MAIL_TO          = ['']  # <-- eine oder mehrere Empfängeradressen

# ENV-Overrides (nützlich, um Secrets nicht im Source zu haben):
ZYTE_API_KEY = os.getenv('ZYTE_API_KEY', ZYTE_API_KEY)
SMTP_USER    = os.getenv('SMTP_USER',    SMTP_USER)
SMTP_PASS    = os.getenv('SMTP_PASS',    SMTP_PASS)
MAIL_FROM    = os.getenv('MAIL_FROM',    MAIL_FROM)
_to_env      = os.getenv('MAIL_TO')
if _to_env:
    MAIL_TO = [a.strip() for a in _to_env.split(',') if a.strip()]


# =============================================================================
# Ampel-Logik (Spiegel der TS-Funktion in entscheidsuche-vue/src/util/status.ts)
# =============================================================================

ORDER = {'green': 0, 'yellow': 1, 'orange': 2, 'red': 3}


def parse_lauf_zeit(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d_%H:%M:%S').replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def tage_zeit(zeit: Optional[str]) -> Optional[float]:
    dt = parse_lauf_zeit(zeit)
    if not dt:
        return None
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0


def ampel_zeit(letzter_erfolg: Optional[str], fehlversuche: int) -> str:
    a = tage_zeit(letzter_erfolg)
    if a is None:
        return 'red'
    if a < 2:  return 'green'
    if a < 4:  return 'yellow'
    if a < 32 and fehlversuche <= 3:
        return 'yellow'
    if a < 10: return 'orange'
    return 'red'


def ampel_bestand(gesamt: int, max_: int) -> Optional[str]:
    if max_ <= 0:
        return None
    r = gesamt / max_
    if r >= 1.0:  return 'green'
    if r > 0.95:  return 'yellow'
    if r > 0.90:  return 'orange'
    return 'red'


def ampel_fehler(n: int) -> str:
    if n == 0: return 'green'
    if n <= 2: return 'yellow'
    return 'orange'


def spider_ampel(s: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    """Liefert (Gesamt-Farbe, Liste der Achsen mit Werten + Farbe)."""
    e = s.get('letzter_erfolgreicher_lauf')
    if not e:
        return 'red', [{'achse': 'zeit', 'color': 'red', 'wert': None}]
    fehlv = int(s.get('fehlversuche_seit_letzter_erfolg', 0) or 0)
    achsen: List[Dict[str, Any]] = []
    farben: List[str] = []

    az = ampel_zeit(e.get('zeit'), fehlv)
    farben.append(az)
    a_t = tage_zeit(e.get('zeit'))
    achsen.append({'achse': 'zeit', 'color': az,
                   'wert': int(a_t) if a_t is not None else None})

    af = ampel_fehler(int(e.get('anzahl_fehler', 0) or 0))
    farben.append(af)
    achsen.append({'achse': 'fehler', 'color': af,
                   'wert': int(e.get('anzahl_fehler', 0) or 0)})

    max_ = int(s.get('vergleich_90_tage_gesamt_max', 0) or 0)
    ab = ampel_bestand(int(e.get('gesamt', 0) or 0), max_)
    if ab:
        farben.append(ab)
        prozent = round(int(e.get('gesamt', 0)) / max_ * 100) if max_ else None
        achsen.append({'achse': 'bestand', 'color': ab, 'wert': prozent})

    color = max(farben, key=lambda c: ORDER[c])
    return color, achsen


# =============================================================================
# HTTP-Helfer
# =============================================================================

def http_get_json(url: str, auth_user: Optional[str] = None,
                  timeout: int = 30) -> Optional[Any]:
    req = urllib.request.Request(url, headers={'User-Agent': 'scraper-alarm'})
    if auth_user:
        import base64
        token = base64.b64encode((auth_user + ':').encode()).decode()
        req.add_header('Authorization', f'Basic {token}')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as e:
        log(f'HTTP-Fehler {url}: {e}')
        return None


# =============================================================================
# Zyte-API-Aufrufe für Lauf-Details
# =============================================================================

def zyte_job_meta(job_id: str) -> Dict[str, Any]:
    """Holt Metadaten und Stats eines einzelnen Zyte-Jobs."""
    if not ZYTE_API_KEY or not job_id:
        return {}
    url = (f'{ZYTE_API_BASE}/jobs/list.json'
           f'?project={ZYTE_PROJECT_ID}&job={job_id}'
           f'&meta=state&meta=close_reason&meta=items_scraped'
           f'&meta=errors_count&meta=warnings_count'
           f'&meta=started_time&meta=finished_time&meta=running_time'
           f'&meta=spider')
    data = http_get_json(url, auth_user=ZYTE_API_KEY)
    if not isinstance(data, dict):
        return {}
    rows = data.get('jobs') or []
    return rows[0] if rows else {}


# =============================================================================
# Status laden, Ampel auswerten
# =============================================================================

def lade_status() -> Dict[str, Any]:
    data = http_get_json(f'{STATUS_BASE_URL}/status.json')
    return data if isinstance(data, dict) else {}


def lade_spider_detail(spider: str) -> Dict[str, Any]:
    data = http_get_json(f'{STATUS_BASE_URL}/{spider}.json')
    return data if isinstance(data, dict) else {}


def ermittle_rote(status: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Liefert {spider: achsen_liste} für alle Spider, deren Gesamt-Ampel rot ist."""
    rote: Dict[str, List[Dict[str, Any]]] = {}
    for name, s in (status.get('spiders') or {}).items():
        color, achsen = spider_ampel(s)
        if color == 'red':
            rote[name] = achsen
    return rote


# =============================================================================
# State-Persistenz (Vortagsvergleich)
# =============================================================================

def lade_state() -> Dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return {'datum': '', 'rote_spider': []}
    try:
        with open(STATE_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {'datum': '', 'rote_spider': []}


def speichere_state(rote: List[str]) -> None:
    state = {
        'datum':       datetime.now().strftime('%Y-%m-%d'),
        'aktualisiert':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'rote_spider': sorted(rote),
    }
    os.makedirs(os.path.dirname(STATE_FILE) or '.', exist_ok=True)
    tmp = STATE_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


# =============================================================================
# Mail-Aufbau
# =============================================================================

def beschreibe_grund(g: Dict[str, Any]) -> Optional[str]:
    if g['color'] not in ('orange', 'red'):
        return None
    achse = g['achse']
    if achse == 'zeit':
        if g['wert'] is None:
            return '  • Zeit: kein erfolgreicher Lauf in den letzten 90 Tagen'
        return f"  • Zeit: letzter erfolgreicher Lauf vor {g['wert']} Tagen"
    if achse == 'bestand':
        return f"  • Bestand: {g['wert']} % des 90-Tage-Maximums"
    if achse == 'fehler':
        return f"  • Fehler: {g['wert']} Einzelfehler im letzten erfolgreichen Lauf"
    return None


def fmt_dauer_sek(sek: Optional[int]) -> str:
    if not sek:
        return '–'
    h, rem = divmod(int(sek), 3600)
    m, s   = divmod(rem, 60)
    if h:
        return f'{h}h {m:02d}m {s:02d}s'
    if m:
        return f'{m}m {s:02d}s'
    return f'{s}s'


def fmt_lauf_details(spider: str, ll: Optional[Dict[str, Any]],
                     zyte: Dict[str, Any]) -> str:
    """Letzte-Lauf-Block für die Mail."""
    if not ll:
        return '  Letzter Lauf: (kein Lauf bekannt)'
    out = ['  Letzter Lauf:']
    job = ll.get('job') or zyte.get('id') or ''
    items   = zyte.get('items_scraped',   ll.get('items_scraped'))
    errors  = zyte.get('errors_count',    ll.get('anzahl_fehler'))
    warns   = zyte.get('warnings_count')
    runtime = (zyte.get('running_time') or 0) // 1000 if zyte.get('running_time') else ll.get('zyte_runtime_sek')
    started = zyte.get('started_time')
    finished = zyte.get('finished_time') or ll.get('zeit')
    state    = zyte.get('state') or ll.get('zyte_state')
    close    = zyte.get('close_reason') or ll.get('zyte_close_reason')

    def iso(ms: Any) -> str:
        if not ms:
            return '–'
        try:
            return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc) \
                .strftime('%Y-%m-%d %H:%M:%S UTC')
        except Exception:
            return str(ms)

    out.append(f'    Job:      {job}')
    out.append(f'    Status:   {state or "?"} ({close or "?"})')
    out.append(f'    Items:    {items if items is not None else "?"}')
    out.append(f'    Errors:   {errors if errors is not None else "?"}')
    if warns is not None:
        out.append(f'    Warnings: {warns}')
    out.append(f'    Start:    {iso(started)}')
    out.append(f'    Ende:     {finished if isinstance(finished, str) and "_" in finished else iso(finished)}')
    out.append(f'    Dauer:    {fmt_dauer_sek(runtime)}')
    if job:
        out.append(f'    Zyte:     {ZYTE_DASHBOARD}/{job}')
    return '\n'.join(out)


def baue_mail(neu: List[str], weiter: List[str],
              details: Dict[str, Tuple[List[Dict[str, Any]],
                                       Optional[Dict[str, Any]],
                                       Dict[str, Any]]]
              ) -> Tuple[str, str]:
    teile = []
    if neu:
        teile.append(f'neu: {", ".join(neu)}')
    if weiter:
        teile.append(f'weiterhin: {", ".join(weiter)}')
    betreff = 'Scraper Alarm ' + '  '.join(teile)

    body: List[str] = []
    if neu:
        body.append('=== Neu rot geworden ===')
        for sp in neu:
            achsen, ll, zyte = details[sp]
            body.append('')
            body.append(f'Scraper {sp} rot geworden wegen:')
            for g in achsen:
                d = beschreibe_grund(g)
                if d: body.append(d)
            body.append(fmt_lauf_details(sp, ll, zyte))
    if weiter:
        if body: body.append('')
        body.append('=== Weiterhin rot ===')
        for sp in weiter:
            achsen, ll, zyte = details[sp]
            body.append('')
            body.append(f'Scraper {sp} weiterhin rot wegen:')
            for g in achsen:
                d = beschreibe_grund(g)
                if d: body.append(d)
            body.append(fmt_lauf_details(sp, ll, zyte))

    body.append('')
    body.append('—')
    body.append('Statusseite: https://entscheidsuche.ch/status?view=scrapers')
    return betreff, '\n'.join(body)


def sende_mail(betreff: str, body: str) -> None:
    if not (SMTP_USER and SMTP_PASS and MAIL_FROM and MAIL_TO and MAIL_TO[0]):
        log('SMTP nicht konfiguriert — Mail wird nicht gesendet.')
        log('--- Betreff ---'); log(betreff)
        log('--- Body ---');    log(body)
        return
    msg = EmailMessage()
    msg['Subject'] = betreff
    msg['From']    = MAIL_FROM
    msg['To']      = ', '.join(MAIL_TO)
    msg.set_content(body)
    ctx = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
        s.ehlo()
        s.starttls(context=ctx)
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)
    log(f'Mail versendet: {betreff}')


# =============================================================================
# Logging
# =============================================================================

def log(msg: str) -> None:
    sys.stderr.write(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}\n')


# =============================================================================
# Hauptablauf
# =============================================================================

def main() -> int:
    status = lade_status()
    if not status:
        log('status.json nicht ladbar — abbrechen')
        return 1

    rote_jetzt = ermittle_rote(status)        # {spider: [achsen]}
    rote_set   = set(rote_jetzt.keys())
    state      = lade_state()
    rote_vortag = set(state.get('rote_spider') or [])

    # State immer fortschreiben, auch wenn keine Mail gesendet wird
    speichere_state(sorted(rote_set))

    if not rote_set:
        log('Keine roten Scraper.')
        return 0

    neu    = sorted(rote_set - rote_vortag)
    weiter = sorted(rote_set & rote_vortag)

    # Pro rotem Spider: Detail-File und Zyte-Stats laden
    details: Dict[str, Tuple[List[Dict[str, Any]],
                             Optional[Dict[str, Any]],
                             Dict[str, Any]]] = {}
    for sp in (neu + weiter):
        d = lade_spider_detail(sp)
        ll = d.get('letzter_lauf')
        zyte = {}
        job_id = (ll or {}).get('job', '') if ll else ''
        if job_id:
            zyte = zyte_job_meta(job_id)
        details[sp] = (rote_jetzt[sp], ll, zyte)

    betreff, body = baue_mail(neu, weiter, details)
    sende_mail(betreff, body)
    return 0


if __name__ == '__main__':
    sys.exit(main())
