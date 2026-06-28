#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyse_diskrepanzen.py — Befundungs-Wrapper um konsolidiere.py.

Für jeden angegebenen Spider:
  1) Lädt die letzte Jobs-Datei (per HTTPS oder lokal) und den ES-Bestand
     für den Spider.
  2) Klassifiziert in a) ES-only, b) Job-only, c) junge Tombstones in ES,
     d) junge Tombstones nicht in ES.
  3) Berechnet Verteilung nach Signatur, EDatum-Jahr (aus _id) und
     scrapedate (aus ES) für die Mengen a/b — die beiden, in denen sich
     systematische Ursachen normalerweise zeigen.
  4) Schreibt einen Markdown-Befund mit
        a) Was sind die Unterschiede,
        b) Wodurch sind diese vermutlich entstanden,
        c) Wie kann ich es beheben.
  5) Optional: Detail-JSON neben dem Befund.

Aufruf:
    # Einzelner Spider (Befund auf stdout)
    python analyse_diskrepanzen.py CH_BGer

    # Mehrere Spider, Befunde in einer Datei sammeln
    python analyse_diskrepanzen.py --out befund.md CH_BGer GE_Gerichte

    # Vordefinierte Stichprobenliste
    python analyse_diskrepanzen.py --liste --out befund.md

    # Lokal statt HTTPS (auf dem Webserver, alt_*-Dateien werden mitgeprüft)
    python analyse_diskrepanzen.py --jobs-quelle local \\
        --jobs-dir /var/www/entscheidsuche/docs/Jobs CH_BGer

Optional pro Spider Detail-JSON dazu:
    --detail-dir DIR    schreibt DIR/<Spider>.analyse.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# konsolidiere.py liegt im selben Verzeichnis
HIER = Path(__file__).resolve().parent
if str(HIER) not in sys.path:
    sys.path.insert(0, str(HIER))

import konsolidiere  # noqa: E402

# ---------------------------------------------------------------------------
# Standardstichprobe
# ---------------------------------------------------------------------------

STANDARD_LISTE = [
    "AR_Gerichte",
    "CH_BGer",
    "CH_BVGer",
    "GE_Gerichte",
    "GR_Gerichte",
    "NE_Omni",
    "SH_OG",
    "VF_FindInfo",
    "VD_Omni",
    "ZH_Obergericht",
    "ZH_Sozialversicherungsgericht",
]

# ---------------------------------------------------------------------------
# Logging (STDERR)
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    sys.stderr.write(msg.rstrip() + "\n")
    sys.stderr.flush()


# ---------------------------------------------------------------------------
# Heuristiken
# ---------------------------------------------------------------------------

RE_EDATUM = re.compile(r"_(\d{4})-(\d{2})-(\d{2})(?:_|$)")
RE_SIGNATUR_PFX = re.compile(r"^([^_]+_[^_]+_[^_]+)")


def edatum_jahr(eid: str) -> Optional[str]:
    """Liest das letzte YYYY-MM-DD aus der ES-_id und liefert das Jahr.

    Filenames enden i.d.R. mit `_<Signatur>_<Num>_<EDatum>`; das EDatum
    ist als YYYY-MM-DD codiert (oder "nodate" → wir liefern None).
    """
    treffer = list(RE_EDATUM.finditer(eid))
    if not treffer:
        return None
    return treffer[-1].group(1)


def signatur(eid: str) -> Optional[str]:
    """Liest die Signatur (z. B. CH_BGer_011) aus der ES-_id."""
    m = RE_SIGNATUR_PFX.match(eid)
    return m.group(1) if m else None


def verteilungen(ids: List[str], es: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Heuristische Verteilungen über eine Menge von _ids."""
    sig_counter: Counter[str] = Counter()
    jahr_counter: Counter[str] = Counter()
    scrape_counter: Counter[str] = Counter()
    for eid in ids:
        sig = signatur(eid)
        if sig:
            sig_counter[sig] += 1
        j = edatum_jahr(eid)
        if j:
            jahr_counter[j] += 1
        sd = (es.get(eid) or {}).get("scrapedate")
        if isinstance(sd, str) and len(sd) >= 7:
            scrape_counter[sd[:7]] += 1  # Monat
    return {
        "top_signaturen": sig_counter.most_common(8),
        "jahr_histogramm": sorted(jahr_counter.items()),
        "scrape_monat_histogramm": sorted(scrape_counter.items()),
        "anzahl": len(ids),
    }


def fmt_histogramm(paare: List[Tuple[str, int]], breite: int = 20) -> str:
    """Kompaktes Textbalken-Histogramm."""
    if not paare:
        return "(keine Daten)"
    max_v = max(v for _, v in paare)
    if max_v == 0:
        return "(alle 0)"
    zeilen = []
    for label, v in paare:
        n = int(round(v / max_v * breite))
        zeilen.append(f"  {label:>7}  {'█' * n:<{breite}}  {v}")
    return "\n".join(zeilen)


def fmt_top(paare: List[Tuple[str, int]]) -> str:
    if not paare:
        return "(keine)"
    return "\n".join(f"  {l:<32} {v}" for l, v in paare)


# ---------------------------------------------------------------------------
# Befundkern
# ---------------------------------------------------------------------------

def schlussfolgerungen(
    analyse_data: Dict[str, Any],
    verteilung_a: Dict[str, Any],
    verteilung_b: Dict[str, Any],
    job: Dict[str, Any],
) -> Tuple[List[str], List[str]]:
    """Liefert (ursachen, empfehlungen) als Listen lesbarer Sätze."""
    z = analyse_data["anzahlen"]
    a = z["a_in_es_nicht_in_job"]
    b = z["b_in_job_nicht_in_es"]
    c = z["c_jung_nichtmehrda_in_es"]
    d = z["d_jung_nichtmehrda_nicht_in_es"]
    bestand = z["letzter_lauf_bestand"]
    es_n = z["es_index"]
    nd_anteil = analyse_data["nicht_mehr_da_regel"]["anteil"]
    nd_uebernehmen = analyse_data["nicht_mehr_da_regel"]["uebernehmen"]

    ursachen: List[str] = []
    empfehlungen: List[str] = []

    # ---- Mengen-Verhältnis-Heuristiken ----------------------------------
    if a == 0 and b == 0 and c == 0 and d == 0:
        ursachen.append("Job-Datei und ES-Index sind deckungsgleich. Keine Diskrepanz erkennbar.")
        empfehlungen.append("Keine Aktion nötig.")
        return ursachen, empfehlungen

    if a > 0 and a > 5 * max(b, 1):
        # ES hat deutlich mehr als der Job. Klassischer "verlorener Vorgänger"-Fall.
        ursachen.append(
            f"ES kennt {a} Dokumente, die in der letzten Jobs-Datei fehlen — gegenüber "
            f"nur {b} umgekehrt. Typisches Muster, wenn ein Spider-Lauf einen "
            f"unvollständigen Vorgängerstand übernommen hat (z. B. alt_Job-, "
            f"Failed_Job- oder versehentlich nicht mehr gefiltertem File) und "
            f"seitdem auf einem kleineren Bestand fortschreibt."
        )
        # Konzentriert sich (a) auf einen schmalen Jahresbereich?
        jahre = verteilung_a["jahr_histogramm"]
        if jahre:
            werte = [v for _, v in jahre]
            spanne = max(werte) - min(werte)
            anteil_max = max(werte) / max(sum(werte), 1)
            if anteil_max > 0.6:
                top_jahre = sorted(jahre, key=lambda p: -p[1])[:3]
                top_str = ", ".join(f"{j} ({v})" for j, v in top_jahre)
                ursachen.append(
                    f"Die fehlenden Dokumente konzentrieren sich auf wenige Jahrgänge "
                    f"({top_str}). Das spricht für einen einmaligen Bestandsbruch — "
                    f"nicht für laufenden Datenverlust."
                )
        empfehlungen.append(
            f"Konsolidierung empfohlen: konsolidiere.py --spider <X> "
            f"--konsolidiere ohne_nicht_mehr_da --push. Damit übernimmt der "
            f"Job-File die {a} ES-Dokumente wieder als Bestand und der Indexer "
            f"behält den ES-Stand."
        )

    elif b > 0 and b > 5 * max(a, 1):
        ursachen.append(
            f"Job-Datei kennt {b} Dokumente, die in ES fehlen — gegenüber nur "
            f"{a} umgekehrt. Typische Ursache: der Indexer hat einzelne Pushs "
            f"abgelehnt oder ist nicht durchgelaufen."
        )
        empfehlungen.append(
            f"Konsolidierungslauf mit Push (--push) sendet die {b} im Job "
            f"vorhandenen Dokumente erneut an den Indexer."
        )

    elif a > 0 or b > 0:
        ursachen.append(
            f"Beidseitige Diskrepanz: {a} nur in ES, {b} nur im Job. "
            f"Vermutlich Mischung aus einzelnen Indexer-Fehlern und vereinzelten "
            f"Spider-Aussetzern. Nicht systematisch."
        )
        empfehlungen.append(
            "Konsolidierungslauf zusammen mit Push korrigiert beide Seiten in einem Schritt."
        )

    # ---- Tombstones -----------------------------------------------------
    if c > 0:
        if not nd_uebernehmen:
            ursachen.append(
                f"{c} junge `nicht_mehr_da`-Einträge wären in ES weiterhin auffindbar. "
                f"Da der Anteil junger Tombstones jedoch {nd_anteil:.1%} beträgt (≥ 3 %), "
                f"ist nicht auszuschliessen, dass diese Tombstones aus einem "
                f"unvollständigen Lauf stammen."
            )
            empfehlungen.append(
                "Vor der Konsolidierung den Spider erneut komplett laufen lassen; "
                "erst wenn die Anzahl junger Tombstones unter 3 % liegt, "
                "mit_nicht_mehr_da pushen."
            )
        else:
            ursachen.append(
                f"{c} junge `nicht_mehr_da`-Einträge sind in ES noch enthalten. "
                f"Anteil {nd_anteil:.1%} (< 3 %) ist plausibel — sieht nach "
                f"regulären Wegfällen aus, die der Indexer noch nicht "
                f"verarbeitet hat."
            )
            empfehlungen.append(
                "konsolidiere.py --konsolidiere mit_nicht_mehr_da --push "
                "räumt den ES-Index auf."
            )
    if d > 0:
        ursachen.append(
            f"{d} junge Tombstones sind in ES bereits weg. Das ist erwartet, "
            f"keine Aktion nötig."
        )

    # ---- Job-Metadaten als Indikatoren ----------------------------------
    jobtyp = (job.get("jobtyp") or "?").lower()
    if jobtyp in ("unvollständig", "neu"):
        ursachen.append(
            f"Der letzte Lauf hat jobtyp = {jobtyp!r}. Bei "
            f"`unvollständig` hat der Spider weniger als 95 % seines "
            f"Vorgängerstandes gesehen; bei `neu` läuft er ohne Vorgänger. "
            f"Beides erklärt Diskrepanzen direkt."
        )
        empfehlungen.append(
            "Spider in stabiler Umgebung neu durchlaufen lassen, "
            "bevor konsolidiert wird."
        )
    if not job.get("start_time"):
        ursachen.append(
            "Job-File hat noch kein `start_time`-Feld (Pipelines-Version vor "
            "der Konsolidierungs-Erweiterung). Für künftige Konsolidierungen "
            "die neue pipelines.py deployen."
        )

    return ursachen, empfehlungen


# ---------------------------------------------------------------------------
# Markdown-Befund pro Spider
# ---------------------------------------------------------------------------

def markdown_befund(
    spider: str,
    analyse_data: Dict[str, Any],
    job: Dict[str, Any],
    es: Dict[str, Dict[str, Any]],
) -> str:
    z = analyse_data["anzahlen"]
    listen = analyse_data["listen"]
    diff = z["es_index"] - z["letzter_lauf_bestand"]

    a_ids = listen["a_in_es_nicht_in_job"]
    b_ids = listen["b_in_job_nicht_in_es"]

    va = verteilungen(a_ids, es)
    vb = verteilungen(b_ids, es)

    ursachen, empfehlungen = schlussfolgerungen(analyse_data, va, vb, job)

    zeilen: List[str] = []
    zeilen.append(f"# {spider}")
    zeilen.append("")
    zeilen.append(
        f"_Letzter Job_: {job.get('job','?')!r}, "
        f"jobtyp = {job.get('jobtyp','?')!r}, "
        f"time = {job.get('time','?')!r}"
    )
    if job.get("start_time"):
        zeilen.append(f"_start_time_: {job['start_time']}")
    zeilen.append("")

    zeilen.append("## a) Unterschiede")
    zeilen.append("")
    zeilen.append("| Kennzahl                              | Wert       |")
    zeilen.append("|---------------------------------------|-----------:|")
    zeilen.append(f"| Bestand letzter Job                   | {z['letzter_lauf_bestand']:>10} |")
    zeilen.append(f"| nicht_mehr_da (jung)                  | {z['letzter_lauf_nicht_mehr_da_jung']:>10} |")
    zeilen.append(f"| nicht_mehr_da (alt)                   | {z['letzter_lauf_nicht_mehr_da_alt']:>10} |")
    zeilen.append(f"| ES-Index                              | {z['es_index']:>10} |")
    zeilen.append(f"| ES − Job (Differenz)                  | {diff:>+10} |")
    zeilen.append(f"| (a) in ES, nicht im Job               | {z['a_in_es_nicht_in_job']:>10} |")
    zeilen.append(f"| (b) im Job, nicht in ES               | {z['b_in_job_nicht_in_es']:>10} |")
    zeilen.append(f"| (c) jung tombstoned, in ES            | {z['c_jung_nichtmehrda_in_es']:>10} |")
    zeilen.append(f"| (d) jung tombstoned, nicht in ES      | {z['d_jung_nichtmehrda_nicht_in_es']:>10} |")
    zeilen.append(f"| 3-%-Regel                             | "
                  f"{analyse_data['nicht_mehr_da_regel']['anteil']:.2%}"
                  f" ({'übernehmen' if analyse_data['nicht_mehr_da_regel']['uebernehmen'] else 'NICHT übernehmen'}) |")
    zeilen.append("")

    if a_ids:
        zeilen.append("### Verteilung der (a)-Menge (ES-only)")
        zeilen.append("")
        zeilen.append("Top-Signaturen:")
        zeilen.append("```")
        zeilen.append(fmt_top(va["top_signaturen"]))
        zeilen.append("```")
        zeilen.append("EDatum-Jahre (aus _id):")
        zeilen.append("```")
        zeilen.append(fmt_histogramm(va["jahr_histogramm"]))
        zeilen.append("```")
        if va["scrape_monat_histogramm"]:
            zeilen.append("scrapedate-Monate (aus ES):")
            zeilen.append("```")
            zeilen.append(fmt_histogramm(va["scrape_monat_histogramm"]))
            zeilen.append("```")
        zeilen.append("Beispiel-IDs (max. 10):")
        zeilen.append("```")
        for x in a_ids[:10]:
            zeilen.append(f"  {x}")
        zeilen.append("```")
        zeilen.append("")

    if b_ids:
        zeilen.append("### Verteilung der (b)-Menge (Job-only)")
        zeilen.append("")
        zeilen.append("Top-Signaturen:")
        zeilen.append("```")
        zeilen.append(fmt_top(vb["top_signaturen"]))
        zeilen.append("```")
        zeilen.append("EDatum-Jahre (aus _id):")
        zeilen.append("```")
        zeilen.append(fmt_histogramm(vb["jahr_histogramm"]))
        zeilen.append("```")
        zeilen.append("Beispiel-IDs (max. 10):")
        zeilen.append("```")
        for x in b_ids[:10]:
            zeilen.append(f"  {x}")
        zeilen.append("```")
        zeilen.append("")

    zeilen.append("## b) Vermutete Ursachen")
    zeilen.append("")
    if ursachen:
        for u in ursachen:
            zeilen.append(f"- {u}")
    else:
        zeilen.append("- (keine auffälligen Muster)")
    zeilen.append("")

    zeilen.append("## c) Empfohlene Behebung")
    zeilen.append("")
    if empfehlungen:
        for e in empfehlungen:
            zeilen.append(f"- {e}")
    else:
        zeilen.append("- Keine Aktion nötig.")
    zeilen.append("")

    return "\n".join(zeilen)


# ---------------------------------------------------------------------------
# Orchestrierung pro Spider
# ---------------------------------------------------------------------------

def analysiere_einen(
    spider: str,
    quelle: str,
    jobs_dir: Optional[Path],
    lese_job_url: str,
    es_url: str,
    es_feld: str,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Dict[str, Any]]]:
    if quelle == "https":
        job = konsolidiere.lade_letzten_job_https(spider, lese_job_url)
    else:
        job = konsolidiere.lade_letzten_job_lokal(jobs_dir, spider)  # type: ignore[arg-type]
    es = konsolidiere.lade_es_bestand(spider, es_url, es_feld)
    analyse = konsolidiere.analyse(spider, job, es)
    return analyse, job, es


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_argv(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="analyse_diskrepanzen.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )
    p.add_argument("spiders", nargs="*",
                   help="Spider-Namen. Mit --liste die Standardstichprobe nehmen.")
    p.add_argument("--liste", action="store_true",
                   help="Standardstichprobe (11 Scraper) verwenden.")
    p.add_argument("--jobs-quelle", choices=["https", "local"], default="https")
    p.add_argument("--jobs-dir", type=Path,
                   help="Lokales Jobs-Verzeichnis (bei --jobs-quelle local).")
    p.add_argument("--lese-job-url", default=konsolidiere.DEFAULT_LESE_JOB_URL)
    p.add_argument("--es-url", default=konsolidiere.DEFAULT_ES_URL)
    p.add_argument("--es-spider-feld", default=konsolidiere.DEFAULT_ES_SPIDER_FELD)
    p.add_argument("--out",
                   help="Zieldatei für gesammelte Markdown-Befunde "
                        "(default: stdout).")
    p.add_argument("--detail-dir", type=Path,
                   help="Falls gesetzt: pro Spider <DIR>/<Spider>.analyse.json schreiben.")
    p.add_argument("--weiter-bei-fehler", action="store_true",
                   help="Bei Fehler in einem Spider trotzdem mit den übrigen weitermachen.")
    args = p.parse_args(argv)
    if args.liste and args.spiders:
        p.error("--liste und Spider-Argumente schliessen sich aus.")
    if not args.liste and not args.spiders:
        p.error("Mindestens einen Spider angeben oder --liste setzen.")
    if args.jobs_quelle == "local" and not args.jobs_dir:
        p.error("--jobs-dir Pflicht bei --jobs-quelle local.")
    return args


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_argv(list(argv) if argv is not None else sys.argv[1:])
    spiders = STANDARD_LISTE if args.liste else args.spiders

    if args.detail_dir:
        args.detail_dir.mkdir(parents=True, exist_ok=True)

    sammler: List[str] = []
    fehler: List[Tuple[str, str]] = []
    for spider in spiders:
        log(f"--- {spider} ---")
        try:
            analyse_data, job, es = analysiere_einen(
                spider,
                args.jobs_quelle,
                args.jobs_dir,
                args.lese_job_url,
                args.es_url,
                args.es_spider_feld,
            )
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            log(f"FEHLER bei {spider}: {msg}")
            fehler.append((spider, msg))
            if args.weiter_bei_fehler:
                continue
            return 1

        if args.detail_dir:
            ziel = args.detail_dir / f"{spider}.analyse.json"
            ziel.write_text(
                json.dumps(analyse_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log(f"Detail-JSON: {ziel}")

        md = markdown_befund(spider, analyse_data, job, es)
        sammler.append(md)

    if fehler:
        sammler.append("# Fehler")
        sammler.append("")
        for s, m in fehler:
            sammler.append(f"- {s}: {m}")
        sammler.append("")

    text = "\n\n---\n\n".join(sammler) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        log(f"Befund: {args.out}")
    else:
        sys.stdout.write(text)
        sys.stdout.flush()
    return 0 if not fehler else 1


if __name__ == "__main__":
    sys.exit(main())
