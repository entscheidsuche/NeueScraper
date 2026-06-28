#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
konsolidiere.py — Konsolidierungslauf für entscheidsuche.ch.

Manueller Reparatur-Lauf, wenn sich der Job-File-Stand und der ES-Index
auseinandergelaufen sind (z. B. wegen überlappender oder fehlerhafter
Spider-Läufe). Kein automatischer Pipeline-Bestandteil.

Phase 1 — Analyse (immer):
    Vergleicht die letzte Jobs-Datei eines Spiders mit dem ES-Index und
    erzeugt ein Analyse-JSON mit:
      a) Dokumente in ES,                aber nicht in der letzten Jobs-Datei
      b) Dokumente in der Jobs-Datei,    aber nicht in ES
      c) jüngere `nicht_mehr_da`,        aber in ES (=> ES-Delete fällig)
      d) jüngere `nicht_mehr_da`,        aber nicht in ES (=> bereits weg)
    Plus Anzahlen
      - Bestand der letzten Jobs-Datei
      - Bestand im ES-Index
      - Konsolidiert ohne (c)+(d)
      - Konsolidiert mit  (c)+(d)
    Plus die jeweiligen Dokument-Listen (ES-_ids).

Phase 2 — Konsolidierung (nur bei --konsolidiere ...):
    --konsolidiere ohne_nicht_mehr_da
        Bestand = (letzte Jobs-Datei ohne nicht_mehr_da)
                ∪ (ES-Treffer, die nicht in der Jobs-Datei sind, also a)
        Alle nicht_mehr_da-Einträge bleiben draussen.
    --konsolidiere mit_nicht_mehr_da
        Wie oben, plus die jüngeren nicht_mehr_da-Einträge — aber nur, wenn
        sie weniger als 3 % des Konsolidierungs-Bestands ausmachen. Sonst
        gilt der zugrunde liegende Lauf als unsicher: das Script schreibt
        eine Fehlermeldung, übernimmt KEINE nicht_mehr_da-Einträge und
        beendet sich mit Exit-Code 2.

    Bei Erfolg:
      - Konsolidiertes Job-File wird geschrieben (jobtyp = "konsolidiert").
      - Mit --push wird das File als Update-Request an den Indexer gesendet
        (Default: https://entscheidsuche.pansoft.de).

Aufruf-Beispiele:
    # nur Analyse (per HTTPS — funktioniert remote)
    python konsolidiere.py --spider CH_BGer

    # Analyse in Datei
    python konsolidiere.py --spider CH_BGer --analyse-out ch_bger.json

    # Konsolidierung ohne nicht_mehr_da, Datei schreiben, NICHT pushen
    python konsolidiere.py --spider CH_BGer \\
        --konsolidiere ohne_nicht_mehr_da \\
        --consolidated-out konsolidiert.json

    # Konsolidierung mit nicht_mehr_da inkl. ES-Push
    python konsolidiere.py --spider CH_BGer \\
        --konsolidiere mit_nicht_mehr_da \\
        --consolidated-out konsolidiert.json --push

    # Lokale Job-Files (auf dem Webserver)
    python konsolidiere.py --spider CH_BGer \\
        --jobs-quelle local --jobs-dir /var/www/entscheidsuche/docs/Jobs
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_LESE_JOB_URL = "https://entscheidsuche.ch/lese_job.php"
DEFAULT_ES_URL = "https://entscheidsuche.ch/_searchV2.php"
DEFAULT_INDEXER_URL = "https://entscheidsuche.pansoft.de"
DEFAULT_ES_SPIDER_FELD = "Spider"
ES_PAGE_SIZE = 5000
NICHT_MEHR_DA_LIMIT = 0.03  # 3 %
HTTP_TIMEOUT_LADEN = 120
HTTP_TIMEOUT_INDEXER = 3600


# ---------------------------------------------------------------------------
# Logging (alle Diagnostik nach STDERR; STDOUT bleibt für JSON frei)
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    sys.stderr.write(msg.rstrip() + "\n")
    sys.stderr.flush()


# ---------------------------------------------------------------------------
# Job-File laden
# ---------------------------------------------------------------------------

def lade_letzten_job_https(spider: str, lese_job_url: str) -> Dict[str, Any]:
    """Holt die jüngste Job_*.json über lese_job.php."""
    url = lese_job_url + "?" + urllib.parse.urlencode({"spider": spider})
    log(f"GET {url}")
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_LADEN) as resp:
        body = resp.read()
    daten = json.loads(body.decode("utf-8"))
    if daten.get("job") == "nojob":
        raise SystemExit(f"Keine Job_*.json für Spider {spider!r} gefunden.")
    return daten


def lade_letzten_job_lokal(jobs_dir: Path, spider: str) -> Dict[str, Any]:
    """Lädt das letzte Job_*.json aus jobs_dir/<spider>/."""
    pfad = jobs_dir / spider
    if not pfad.is_dir():
        raise SystemExit(f"Spider-Verzeichnis nicht gefunden: {pfad}")
    kandidaten = sorted(p for p in pfad.iterdir()
                        if p.is_file() and p.name.startswith("Job_")
                        and p.suffix == ".json")
    if not kandidaten:
        raise SystemExit(f"Keine Job_*.json in {pfad}.")
    letzte = kandidaten[-1]
    log(f"Lokal: {letzte}")
    return json.loads(letzte.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Job-File auswerten
# ---------------------------------------------------------------------------

def es_id_aus_jobkey(key: str) -> Optional[str]:
    """\"CH_BGer/CH_BGer_011_..._2024-12-31.json\" → \"CH_BGer_011_..._2024-12-31\".

    Liefert None für Nicht-.json-Schlüssel (HTML/PDF-Files), die in ES
    keinen eigenen Eintrag haben.
    """
    if not key.endswith(".json"):
        return None
    base = key[: -len(".json")]
    return base.split("/", 1)[1] if "/" in base else base


def klassifiziere_job(job: Dict[str, Any]) -> Tuple[
        Dict[str, Dict[str, Any]],   # bestand:    es_id -> eintrag
        Dict[str, Dict[str, Any]],   # nicht_da_jung: es_id -> eintrag
        Dict[str, Dict[str, Any]],   # nicht_da_alt:  es_id -> eintrag
]:
    """Trennt die `dateien` des letzten Jobs in drei Kategorien.

    - bestand        : status != "nicht_mehr_da"
    - nicht_da_jung  : status == "nicht_mehr_da" UND ohne 'quelle'
                       (in diesem Lauf neu getombstoned)
    - nicht_da_alt   : status == "nicht_mehr_da" UND mit 'quelle'
                       (Tombstone aus früheren Läufen)
    """
    bestand: Dict[str, Dict[str, Any]] = {}
    nicht_da_jung: Dict[str, Dict[str, Any]] = {}
    nicht_da_alt: Dict[str, Dict[str, Any]] = {}
    for key, eintrag in (job.get("dateien") or {}).items():
        eid = es_id_aus_jobkey(key)
        if eid is None:
            continue
        status = (eintrag or {}).get("status")
        if status == "nicht_mehr_da":
            if "quelle" in eintrag:
                nicht_da_alt[eid] = {"_jobkey": key, **eintrag}
            else:
                nicht_da_jung[eid] = {"_jobkey": key, **eintrag}
        else:
            bestand[eid] = {"_jobkey": key, **eintrag}
    return bestand, nicht_da_jung, nicht_da_alt


# ---------------------------------------------------------------------------
# ES-Bestand laden
# ---------------------------------------------------------------------------

def lade_es_bestand(
    spider: str, es_url: str, spider_feld: str
) -> Dict[str, Dict[str, Any]]:
    """Liefert dict ES-_id → {scrapedate, hierarchy, ...}."""
    bestand: Dict[str, Dict[str, Any]] = {}
    suche_after: Optional[List[Any]] = None
    seite = 0
    while True:
        body: Dict[str, Any] = {
            "size": ES_PAGE_SIZE,
            "_source": ["scrapedate", "hierarchy", "Datum", "Signatur"],
            "query": {"term": {spider_feld: spider}},
            "sort": [{"_id": "asc"}],
            "track_total_hits": False,
        }
        if suche_after is not None:
            body["search_after"] = suche_after
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            es_url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_LADEN) as resp:
            antwort = json.loads(resp.read().decode("utf-8"))
        hits = (antwort.get("hits") or {}).get("hits") or []
        seite += 1
        log(f"ES Seite {seite}: {len(hits)} Treffer (kumuliert {len(bestand) + len(hits)})")
        if not hits:
            break
        for hit in hits:
            eid = hit.get("_id")
            if not eid:
                continue
            bestand[eid] = hit.get("_source") or {}
        if len(hits) < ES_PAGE_SIZE:
            break
        suche_after = hits[-1].get("sort")
        if not suche_after:
            break
    return bestand


# ---------------------------------------------------------------------------
# Analyse
# ---------------------------------------------------------------------------

def analyse(
    spider: str,
    job: Dict[str, Any],
    es: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    bestand, nd_jung, nd_alt = klassifiziere_job(job)

    es_ids: Set[str] = set(es.keys())
    job_ids: Set[str] = set(bestand) | set(nd_jung) | set(nd_alt)

    a = sorted(es_ids - job_ids)                  # ES, nicht im Job
    b = sorted(set(bestand) - es_ids)             # Job-Bestand, nicht in ES
    c = sorted(set(nd_jung) & es_ids)             # jung-tombstoned, aber in ES
    d = sorted(set(nd_jung) - es_ids)             # jung-tombstoned, nicht in ES

    # Konsolidierte Bestände
    konsolidiert_ohne = (set(bestand) | set(a))                # ohne (c)+(d)
    konsolidiert_mit  = konsolidiert_ohne                       # (c)+(d) sind Tombstones
    # Bei "mit_nicht_mehr_da" gehen die jungen Tombstones zwar in den Push,
    # zählen aber nicht zum lebenden Bestand. Wir zeigen aber zusätzlich die
    # Tombstone-Anzahl an.
    n_konsol_ohne = len(konsolidiert_ohne)
    n_konsol_mit  = len(konsolidiert_ohne)  # = lebender Bestand identisch
    n_tombstones_jung = len(nd_jung)

    # 3-%-Regel (für mit_nicht_mehr_da)
    grundgesamtheit = n_konsol_ohne if n_konsol_ohne > 0 else 1
    nd_anteil = n_tombstones_jung / grundgesamtheit
    nd_uebernehmen = nd_anteil < NICHT_MEHR_DA_LIMIT

    return {
        "spider": spider,
        "generiert": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "letzter_job": {
            "job":        job.get("job"),
            "jobtyp":     job.get("jobtyp"),
            "start_time": job.get("start_time"),
            "time":       job.get("time"),
        },
        "anzahlen": {
            "letzter_lauf_bestand":         len(bestand),
            "letzter_lauf_nicht_mehr_da_jung": n_tombstones_jung,
            "letzter_lauf_nicht_mehr_da_alt":  len(nd_alt),
            "es_index":                     len(es),
            "a_in_es_nicht_in_job":         len(a),
            "b_in_job_nicht_in_es":         len(b),
            "c_jung_nichtmehrda_in_es":     len(c),
            "d_jung_nichtmehrda_nicht_in_es": len(d),
            "konsolidiert_ohne_nichtmehrda": n_konsol_ohne,
            "konsolidiert_mit_nichtmehrda":  n_konsol_mit,
        },
        "nicht_mehr_da_regel": {
            "anteil":              nd_anteil,
            "schwelle":            NICHT_MEHR_DA_LIMIT,
            "uebernehmen":         nd_uebernehmen,
            "bemerkung": (
                "Anteil < 3 % → Tombstones übernommen."
                if nd_uebernehmen else
                "Anteil ≥ 3 % → Lauf gilt als unsicher, "
                "Tombstones werden bei mit_nicht_mehr_da NICHT übernommen."
            ),
        },
        "listen": {
            "a_in_es_nicht_in_job":         a,
            "b_in_job_nicht_in_es":         b,
            "c_jung_nichtmehrda_in_es":     c,
            "d_jung_nichtmehrda_nicht_in_es": d,
        },
    }


# ---------------------------------------------------------------------------
# Konsolidiertes Job-File bauen
# ---------------------------------------------------------------------------

def baue_konsolidierten_jobfile(
    spider: str,
    job: Dict[str, Any],
    es: Dict[str, Dict[str, Any]],
    analyse_data: Dict[str, Any],
    modus: str,
) -> Optional[Dict[str, Any]]:
    """Erzeugt ein neues Job-File aus letztem Job + ES-Diff.

    Liefert None, wenn der Modus mit_nicht_mehr_da die 3-%-Schwelle reisst.
    """
    bestand, nd_jung, nd_alt = klassifiziere_job(job)

    nd_uebernehmen_3p = analyse_data["nicht_mehr_da_regel"]["uebernehmen"]
    if modus == "mit_nicht_mehr_da" and not nd_uebernehmen_3p:
        log(
            "FEHLER: nicht_mehr_da-Anteil ≥ 3 %. "
            "mit_nicht_mehr_da-Konsolidierung wird abgelehnt."
        )
        return None

    # 1) Bestand übernehmen (1:1 mit Original-Jobkey).
    dateien: Dict[str, Dict[str, Any]] = {}
    for eid, eintrag in bestand.items():
        key = eintrag.pop("_jobkey")
        dateien[key] = eintrag

    # 2) Alte Tombstones immer mitnehmen (sonst löscht der Indexer alten
    #    nicht_mehr_da-Stand und versucht ggf. Re-Index aus dem Storage).
    for eid, eintrag in nd_alt.items():
        key = eintrag.pop("_jobkey")
        dateien[key] = eintrag

    # 3) Junge Tombstones nur bei mit_nicht_mehr_da übernehmen.
    if modus == "mit_nicht_mehr_da":
        for eid, eintrag in nd_jung.items():
            key = eintrag.pop("_jobkey")
            dateien[key] = eintrag

    # 4) Dokumente, die in ES, aber nicht im letzten Job sind (a):
    #    als Pseudo-Eintrag mit quelle="Konsolidierung-<spider>-<ts>"
    #    aufnehmen, damit der Indexer sie NICHT löscht. Status "identisch"
    #    signalisiert "kein Re-Index nötig".
    quelle_marker = f"konsolidierung-{spider}-{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
    for eid in analyse_data["listen"]["a_in_es_nicht_in_job"]:
        quelle = es.get(eid, {})
        # Pfad rekonstruieren: <Spider>/<eid>.json
        key = f"{spider}/{eid}.json"
        eintrag: Dict[str, Any] = {
            "status": "identisch",
            "quelle": quelle_marker,
        }
        sd = quelle.get("scrapedate")
        if sd:
            eintrag["scrapedate"] = sd
        dateien[key] = eintrag

    # 5) Aggregate (signaturen, gesamt) neu rechnen.
    signaturen: Dict[str, Dict[str, int]] = {}
    gesamt: Dict[str, int] = {"gesamt": 0}
    for key, eintrag in dateien.items():
        if not key.endswith(".json"):
            continue
        eid = es_id_aus_jobkey(key)
        if eid is None:
            continue
        # Signatur = die ersten 3 Underscore-getrennten Tokens des _id.
        teile = eid.split("_")
        sig = "_".join(teile[:3]) if len(teile) >= 3 else eid
        sd = signaturen.setdefault(sig, {"gesamt": 0})
        if (eintrag or {}).get("status") != "nicht_mehr_da":
            sd["gesamt"] += 1
            gesamt["gesamt"] += 1

    jetzt = datetime.now(timezone.utc)
    konsolidiert = {
        "spider":     spider,
        "job":        f"konsolidiert/{jetzt.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "jobtyp":     "konsolidiert",
        "start_time": jetzt.strftime("%Y-%m-%d_%H:%M:%S"),
        "time":       jetzt.strftime("%Y-%m-%d_%H:%M:%S"),
        "dateien":    dateien,
        "signaturen": signaturen,
        "gesamt":     gesamt,
        "konsolidierung": {
            "modus":             modus,
            "vorgaenger_job":    job.get("job"),
            "quelle_marker":     quelle_marker,
            "ergaenzt_aus_es":   len(analyse_data["listen"]["a_in_es_nicht_in_job"]),
            "junge_tombstones_uebernommen":
                modus == "mit_nicht_mehr_da",
            "anzahlen": analyse_data["anzahlen"],
        },
    }
    return konsolidiert


# ---------------------------------------------------------------------------
# Push an Indexer
# ---------------------------------------------------------------------------

def push_indexer(konsolidiert: Dict[str, Any], indexer_url: str) -> Tuple[int, str]:
    body = json.dumps(konsolidiert).encode("utf-8")
    log(f"POST {indexer_url} (Body {len(body):,} Bytes)")
    req = urllib.request.Request(
        indexer_url, data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_INDEXER) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return resp.status, text
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="replace")
        # 504 wird genau wie im pipelines.py-Push als Erfolg gewertet.
        if e.code == 504 or "504 Gateway Time-out" in text:
            log("Indexer 504 → Anfrage akzeptiert, läuft asynchron weiter.")
            return 504, text
        return e.code, text


# ---------------------------------------------------------------------------
# Hilfsfunktion zum Schreiben
# ---------------------------------------------------------------------------

def schreibe_json(daten: Any, ziel: str) -> None:
    text = json.dumps(daten, ensure_ascii=False, indent=2)
    if ziel == "-":
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
        sys.stdout.flush()
    else:
        Path(ziel).write_text(text, encoding="utf-8")
        log(f"Geschrieben: {ziel}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_argv(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="konsolidiere.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )
    p.add_argument("--spider", required=True, help="Spider-Name (z. B. CH_BGer)")

    # Quelle der Jobs-Datei
    p.add_argument("--jobs-quelle", choices=["https", "local"], default="https",
                   help="Wie wird die Jobs-Datei geholt (Default: https).")
    p.add_argument("--jobs-dir", type=Path,
                   help="Lokales Jobs-Verzeichnis (bei --jobs-quelle local).")
    p.add_argument("--lese-job-url", default=DEFAULT_LESE_JOB_URL,
                   help=f"URL für lese_job.php (Default: {DEFAULT_LESE_JOB_URL}).")

    # ES
    p.add_argument("--es-url", default=DEFAULT_ES_URL,
                   help=f"_searchV2.php-Endpoint (Default: {DEFAULT_ES_URL}).")
    p.add_argument("--es-spider-feld", default=DEFAULT_ES_SPIDER_FELD,
                   help=f"ES-Feldname für den Spider (Default: {DEFAULT_ES_SPIDER_FELD}).")

    # Modus
    p.add_argument("--konsolidiere",
                   choices=["none", "ohne_nicht_mehr_da", "mit_nicht_mehr_da"],
                   default="none",
                   help="Konsolidierungs-Modus (Default: none → nur Analyse).")

    # Ausgaben
    p.add_argument("--analyse-out", default="-",
                   help="Pfad für Analyse-JSON oder \"-\" für stdout (Default: -).")
    p.add_argument("--consolidated-out",
                   help="Pfad für konsolidierten Job-File (Pflicht bei --konsolidiere).")

    # Push
    p.add_argument("--push", action="store_true",
                   help="Konsolidierten Job-File an Indexer senden.")
    p.add_argument("--indexer-url", default=DEFAULT_INDEXER_URL,
                   help=f"Indexer-Endpoint (Default: {DEFAULT_INDEXER_URL}).")

    p.add_argument("--trocken", action="store_true",
                   help="Keine Schreib- oder Push-Aktionen. Analyse trotzdem.")

    args = p.parse_args(argv)

    if args.jobs_quelle == "local" and not args.jobs_dir:
        p.error("--jobs-dir ist bei --jobs-quelle local Pflicht.")
    if args.konsolidiere != "none" and not args.consolidated_out and not args.trocken:
        p.error("--consolidated-out ist bei --konsolidiere Pflicht "
                "(oder --trocken setzen).")
    if args.push and args.konsolidiere == "none":
        p.error("--push setzt --konsolidiere voraus.")

    return args


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_argv(list(argv) if argv is not None else sys.argv[1:])

    # Job laden
    if args.jobs_quelle == "https":
        job = lade_letzten_job_https(args.spider, args.lese_job_url)
    else:
        job = lade_letzten_job_lokal(args.jobs_dir, args.spider)

    log(f"Job geladen: spider={job.get('spider')!r}, "
        f"job={job.get('job')!r}, jobtyp={job.get('jobtyp')!r}, "
        f"time={job.get('time')!r}")

    # ES laden
    es = lade_es_bestand(args.spider, args.es_url, args.es_spider_feld)
    log(f"ES-Bestand: {len(es)} Dokumente.")

    # Analyse
    analyse_data = analyse(args.spider, job, es)

    # Analyse ausgeben
    schreibe_json(analyse_data, args.analyse_out if not args.trocken else "-")

    # Optional: Konsolidieren
    if args.konsolidiere == "none":
        return 0

    konsolidiert = baue_konsolidierten_jobfile(
        args.spider, job, es, analyse_data, args.konsolidiere
    )
    if konsolidiert is None:
        # 3-%-Regel verletzt → Exit 2
        return 2

    if args.trocken:
        log("Trockenlauf — Konsolidierter Job-File wird NICHT geschrieben.")
    else:
        schreibe_json(konsolidiert, args.consolidated_out)

    if args.push and not args.trocken:
        status, text = push_indexer(konsolidiert, args.indexer_url)
        log(f"Indexer-Antwort: HTTP {status}")
        if status >= 300 and status != 504:
            log(text[:1000])
            return 3
    elif args.push and args.trocken:
        log("Trockenlauf — kein Push.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
