<?php
declare(strict_types=1);

/**
 * abgleich.php — Abgleich ES ↔ Dateisystem ↔ Jobs-Datei pro Scraper.
 *
 * Vergleicht für jeden Scraper drei Quellen:
 *   - ES-Index       (via _searchV2.php, Prefix-Query auf attachment.content_url,
 *                     Pagination mit search_after)
 *   - Dateisystem    (docs/<Spider>/, direkter Verzeichniszugriff)
 *   - Jobs-Datei     (docs/Jobs/<Spider>/last, Fallback: neueste Job_*.json)
 *
 * Berichtsabschnitte:
 *   a) In der Jobs-Datei (Status != nicht_mehr_da), aber nicht in ES
 *   b) In ES, aber JSON bzw. HTML/PDF fehlt im Dateisystem
 *   c) In der Jobs-Datei als "kaputt" markiert
 *   d) In der Jobs-Datei (Status weder kaputt noch nicht_mehr_da), aber nicht in ES
 *
 * Aufruf:
 *   Web: https://entscheidsuche.ch/abgleich.php                  (alle Scraper)
 *        https://entscheidsuche.ch/abgleich.php?spider=VD_Omni   (ein Scraper)
 *   CLI: php abgleich.php                > abgleich.html
 *        php abgleich.php VD_Omni        > abgleich.html
 *
 * Ausgabe: HTML mit einer ausklappbaren Summenzeile pro Scraper. Die Seite
 * wird fortlaufend ausgegeben (flush pro Scraper), damit bei einem Lauf über
 * alle Scraper sofort Ergebnisse sichtbar sind. Es werden keine Dateien
 * geschrieben.
 */

@set_time_limit(0);
@ini_set('max_execution_time', '0');
@ini_set('memory_limit', '2048M');
@ignore_user_abort(true);

const ES_URL       = 'https://entscheidsuche.ch/_searchV2.php';
const DOCS_URL     = 'https://entscheidsuche.ch/docs/';
const HTTP_TIMEOUT = 120;
const ES_PAGE_SIZE = 5000;

$BASE_DIR = __DIR__;
$DOCS_DIR = $BASE_DIR . '/docs';
$JOBS_DIR = $DOCS_DIR . '/Jobs';

// ---------------------------------------------------------------------------
// Parameter
// ---------------------------------------------------------------------------

$spider_wunsch = '';
if (PHP_SAPI === 'cli') {
    $spider_wunsch = trim($_SERVER['argv'][1] ?? '');
} else {
    $spider_wunsch = trim((string)($_REQUEST['spider'] ?? ''));
}
if ($spider_wunsch === 'alle') {
    $spider_wunsch = '';
}
if ($spider_wunsch !== '' && !preg_match('/^[A-Za-z0-9_]+$/', $spider_wunsch)) {
    http_response_code(400);
    exit("Ungültiger Spider-Name\n");
}

// ---------------------------------------------------------------------------
// Datenbeschaffung
// ---------------------------------------------------------------------------

/** Liste der Scraper = Unterverzeichnisse von docs/Jobs. */
function spider_liste(string $jobs_dir): array {
    $liste = [];
    foreach (scandir($jobs_dir) ?: [] as $name) {
        if ($name === '.' || $name === '..' || $name === 'trash') {
            continue;
        }
        if (is_dir("$jobs_dir/$name")) {
            $liste[] = $name;
        }
    }
    sort($liste, SORT_STRING);
    return $liste;
}

/**
 * Letzte Jobs-Datei eines Scrapers laden.
 * Bevorzugt docs/Jobs/<Spider>/last, sonst neueste Job_*.json.
 * Liefert [job-Metadaten, dateien-Map (ohne Spider-Prefix), Dateiname] oder Fehlertext.
 */
function lade_jobs_datei(string $jobs_dir, string $spider): array {
    $verzeichnis = "$jobs_dir/$spider";
    $pfad = "$verzeichnis/last";
    $anzeige = 'last';
    if (!is_file($pfad)) {
        $kandidaten = glob("$verzeichnis/Job_*.json") ?: [];
        if (!$kandidaten) {
            return [null, null, null, "keine Jobs-Datei in $verzeichnis"];
        }
        sort($kandidaten, SORT_STRING);
        $pfad = end($kandidaten);
        $anzeige = basename($pfad);
    }
    $raw = @file_get_contents($pfad);
    if ($raw === false) {
        return [null, null, null, "Jobs-Datei nicht lesbar: $pfad"];
    }
    $job = json_decode($raw, true);
    unset($raw);
    if (!is_array($job)) {
        return [null, null, null, "Jobs-Datei kein gültiges JSON: $pfad"];
    }
    $dateien = [];
    $prefix = $spider . '/';
    $plen = strlen($prefix);
    foreach (($job['dateien'] ?? []) as $key => $eintrag) {
        $name = strncmp($key, $prefix, $plen) === 0 ? substr($key, $plen) : $key;
        $dateien[$name] = $eintrag;
    }
    unset($job['dateien']);
    return [$job, $dateien, $anzeige, null];
}

/** Dateinamen im docs/<Spider>/-Verzeichnis (nur Dateien). */
function lade_dateisystem(string $docs_dir, string $spider): ?array {
    $verzeichnis = "$docs_dir/$spider";
    if (!is_dir($verzeichnis)) {
        return null;
    }
    $namen = [];
    foreach (scandir($verzeichnis) ?: [] as $name) {
        if ($name === '.' || $name === '..') {
            continue;
        }
        if (is_file("$verzeichnis/$name")) {
            $namen[$name] = true;
        }
    }
    return $namen;
}

/** POST an ES; liefert dekodiertes JSON oder null. */
function es_anfrage(array $payload): ?array {
    for ($versuch = 1; $versuch <= 3; $versuch++) {
        $ch = curl_init(ES_URL);
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => json_encode($payload),
            CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => HTTP_TIMEOUT,
        ]);
        $antwort = curl_exec($ch);
        curl_close($ch);
        if (is_string($antwort)) {
            $daten = json_decode($antwort, true);
            if (is_array($daten) && isset($daten['hits']['hits'])) {
                return $daten;
            }
        }
        sleep(2 * $versuch);
    }
    return null;
}

/**
 * Alle ES-Dokumente eines Scrapers: id -> content_url.
 * Liefert null bei ES-Fehler.
 */
function lade_es_dokumente(string $spider): ?array {
    $dokumente = [];
    $search_after = null;
    while (true) {
        $payload = [
            'size'    => ES_PAGE_SIZE,
            '_source' => ['attachment.content_url'],
            'query'   => ['prefix' => ['attachment.content_url' => DOCS_URL . $spider . '/']],
            'sort'    => [['id' => 'asc']],
        ];
        if ($search_after !== null) {
            $payload['search_after'] = $search_after;
        }
        $antwort = es_anfrage($payload);
        if ($antwort === null) {
            return null;
        }
        $hits = $antwort['hits']['hits'];
        if (!$hits) {
            break;
        }
        foreach ($hits as $hit) {
            $dokumente[$hit['_id']] = $hit['_source']['attachment']['content_url'] ?? '';
        }
        $search_after = end($hits)['sort'];
        if (count($hits) < ES_PAGE_SIZE) {
            break;
        }
    }
    return $dokumente;
}

// ---------------------------------------------------------------------------
// Abgleich
// ---------------------------------------------------------------------------

/** Dateiname ohne Endung. */
function basis_id(string $dateiname): string {
    return preg_replace('/\.[A-Za-z0-9]+$/', '', $dateiname);
}

/** Abgleich für einen Scraper; liefert Ergebnis-Array (oder ['fehler' => ...]). */
function abgleich(string $docs_dir, string $jobs_dir, string $spider): array {
    [$job_meta, $jobs_dateien, $jobs_name, $fehler] = lade_jobs_datei($jobs_dir, $spider);
    if ($fehler !== null) {
        return ['fehler' => $fehler];
    }
    $fs_dateien = lade_dateisystem($docs_dir, $spider);
    if ($fs_dateien === null) {
        return ['fehler' => "Verzeichnis docs/$spider fehlt"];
    }
    $es_doks = lade_es_dokumente($spider);
    if ($es_doks === null) {
        return ['fehler' => 'ES-Abfrage fehlgeschlagen'];
    }

    // Jobs-Dateien nach Dokument gruppieren: basis_id -> [dateiname => status]
    $jobs_doks = [];
    foreach ($jobs_dateien as $name => $eintrag) {
        $jobs_doks[basis_id($name)][$name] = (string)($eintrag['status'] ?? '');
    }
    ksort($jobs_doks, SORT_STRING);

    $a = [];
    $d = [];
    foreach ($jobs_doks as $doc_id => $dateien) {
        if (isset($es_doks[$doc_id])) {
            continue;
        }
        $status_menge = array_unique(array_values($dateien));
        $ohne_nmd = array_diff($status_menge, ['nicht_mehr_da']);
        if ($ohne_nmd) {
            $a[] = ['id' => $doc_id, 'dateien' => $dateien];
        }
        if (!array_intersect($status_menge, ['kaputt', 'nicht_mehr_da'])) {
            $d[] = ['id' => $doc_id, 'dateien' => $dateien];
        }
    }

    $b = [];
    ksort($es_doks, SORT_STRING);
    foreach ($es_doks as $doc_id => $content_url) {
        $inhalt_datei = $content_url !== '' ? basename($content_url) : '';
        $fehlt = [];
        if (!isset($fs_dateien[$doc_id . '.json'])) {
            $fehlt[] = $doc_id . '.json';
        }
        if ($inhalt_datei === '') {
            $fehlt[] = '(keine content_url in ES)';
        } elseif (!isset($fs_dateien[$inhalt_datei])) {
            $fehlt[] = $inhalt_datei;
        }
        if ($fehlt) {
            $b[] = ['id' => $doc_id, 'fehlt' => $fehlt];
        }
    }

    $c = [];
    ksort($jobs_dateien, SORT_STRING);
    foreach ($jobs_dateien as $name => $eintrag) {
        if (($eintrag['status'] ?? '') === 'kaputt') {
            $c[] = ['datei' => $name, 'eintrag' => $eintrag];
        }
    }

    return [
        'job'    => [
            'datei'  => $jobs_name,
            'job'    => $job_meta['job'] ?? null,
            'jobtyp' => $job_meta['jobtyp'] ?? null,
            'time'   => $job_meta['time'] ?? null,
        ],
        'anzahl' => [
            'es'              => count($es_doks),
            'dateisystem'     => count($fs_dateien),
            'jobs_dateien'    => count($jobs_dateien),
            'jobs_dokumente'  => count($jobs_doks),
        ],
        'a' => $a,
        'b' => $b,
        'c' => $c,
        'd' => $d,
    ];
}

// ---------------------------------------------------------------------------
// HTML-Ausgabe
// ---------------------------------------------------------------------------

function h(string $s): string {
    return htmlspecialchars($s, ENT_QUOTES, 'UTF-8');
}

/** Eine Ergebnisliste als <ul> (oder Hinweis "keine"). */
function html_liste(array $zeilen, callable $formatiere): string {
    if (!$zeilen) {
        return '<p class="leer">keine</p>';
    }
    $out = '<ul>';
    foreach ($zeilen as $zeile) {
        $out .= '<li>' . $formatiere($zeile) . '</li>';
    }
    return $out . '</ul>';
}

/** Ausklappbarer Eintrag für einen Scraper. */
function html_scraper(string $spider, array $ergebnis): string {
    if (isset($ergebnis['fehler'])) {
        return '<details class="scraper fehler"><summary><span class="name">' . h($spider)
            . '</span><span class="badge rot">Fehler</span></summary><p>'
            . h($ergebnis['fehler']) . '</p></details>';
    }

    $n = $ergebnis['anzahl'];
    $j = $ergebnis['job'];
    $summen = '';
    $auffaellig = false;
    foreach (['a', 'b', 'c', 'd'] as $s) {
        $anzahl = count($ergebnis[$s]);
        $klasse = $anzahl > 0 ? 'rot' : 'gruen';
        $auffaellig = $auffaellig || $anzahl > 0;
        $summen .= '<span class="badge ' . $klasse . '">' . $s . ': ' . $anzahl . '</span>';
    }

    $status_zeile = function (array $z): string {
        $teile = [];
        foreach ($z['dateien'] as $datei => $status) {
            $teile[] = h($datei) . ': <em>' . h($status) . '</em>';
        }
        return '<code>' . h($z['id']) . '</code> — ' . implode(', ', $teile);
    };

    $inhalt =
        '<table class="zahlen">'
        . '<tr><td>ES-Dokumente</td><td>' . $n['es'] . '</td></tr>'
        . '<tr><td>Dateien im Dateisystem</td><td>' . $n['dateisystem'] . '</td></tr>'
        . '<tr><td>Dateien in Jobs-Datei</td><td>' . $n['jobs_dateien'] . '</td></tr>'
        . '<tr><td>Dokumente in Jobs-Datei</td><td>' . $n['jobs_dokumente'] . '</td></tr>'
        . '</table>'
        . '<p class="jobinfo">Jobs-Datei: ' . h((string)$j['datei'])
        . ' — Job ' . h((string)$j['job']) . ' (' . h((string)$j['jobtyp']) . ', ' . h((string)$j['time']) . ')</p>'
        . '<h3>a) In Jobs-Datei (nicht „nicht_mehr_da“), aber nicht in ES: ' . count($ergebnis['a']) . '</h3>'
        . html_liste($ergebnis['a'], $status_zeile)
        . '<h3>b) In ES, aber Datei(en) fehlen im Dateisystem: ' . count($ergebnis['b']) . '</h3>'
        . html_liste($ergebnis['b'], function (array $z): string {
            return '<code>' . h($z['id']) . '</code> — fehlt: ' . h(implode(', ', $z['fehlt']));
        })
        . '<h3>c) In Jobs-Datei als „kaputt“ markiert: ' . count($ergebnis['c']) . '</h3>'
        . html_liste($ergebnis['c'], function (array $z): string {
            return '<code>' . h($z['datei']) . '</code> — '
                . h(json_encode($z['eintrag'], JSON_UNESCAPED_UNICODE));
        })
        . '<h3>d) In Jobs-Datei (weder „kaputt“ noch „nicht_mehr_da“), aber nicht in ES: ' . count($ergebnis['d']) . '</h3>'
        . html_liste($ergebnis['d'], $status_zeile);

    return '<details class="scraper' . ($auffaellig ? ' auffaellig' : '') . '">'
        . '<summary><span class="name">' . h($spider) . '</span>' . $summen
        . '<span class="klein">' . $n['es'] . ' Dok.</span></summary>'
        . $inhalt . '</details>';
}

// ---------------------------------------------------------------------------
// Hauptprogramm (streamt die Seite Scraper für Scraper)
// ---------------------------------------------------------------------------

if (!is_dir($JOBS_DIR)) {
    http_response_code(500);
    exit("Jobs-Verzeichnis fehlt: $JOBS_DIR\n");
}

$spiders = $spider_wunsch !== '' ? [$spider_wunsch] : spider_liste($JOBS_DIR);
if ($spider_wunsch !== '' && !is_dir("$JOBS_DIR/$spider_wunsch")) {
    http_response_code(404);
    exit("Unbekannter Spider: $spider_wunsch\n");
}

if (PHP_SAPI !== 'cli') {
    header('Content-Type: text/html; charset=utf-8');
    header('X-Accel-Buffering: no');
}
while (ob_get_level() > 0) {
    ob_end_flush();
}

echo '<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">'
    . '<meta name="viewport" content="width=device-width, initial-scale=1">'
    . '<title>Abgleich ES / Dateisystem / Jobs</title><style>'
    . 'body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;'
    . 'margin:2rem auto;max-width:70rem;padding:0 1rem;color:#1a1a2e;background:#fafafa}'
    . 'h1{font-size:1.5rem}h3{font-size:1rem;margin:1rem 0 .3rem}'
    . '.kopf{color:#555;margin-bottom:1.5rem}'
    . 'details.scraper{background:#fff;border:1px solid #ddd;border-radius:6px;'
    . 'margin:.4rem 0;padding:.2rem .8rem}'
    . 'details.scraper[open]{padding-bottom:.8rem}'
    . 'details.auffaellig{border-color:#e0a800}'
    . 'details.fehler{border-color:#d9534f}'
    . 'summary{cursor:pointer;padding:.4rem 0;display:flex;align-items:center;'
    . 'gap:.5rem;flex-wrap:wrap}'
    . 'summary .name{font-weight:600;min-width:11rem}'
    . '.badge{font-size:.8rem;padding:.1rem .5rem;border-radius:.8rem;color:#fff}'
    . '.badge.gruen{background:#5a9e6f}.badge.rot{background:#d9534f}'
    . '.klein{font-size:.8rem;color:#888;margin-left:auto}'
    . 'table.zahlen{border-collapse:collapse;margin:.5rem 0}'
    . 'table.zahlen td{border:1px solid #ddd;padding:.2rem .6rem}'
    . 'table.zahlen td:last-child{text-align:right}'
    . '.jobinfo{color:#777;font-size:.85rem}'
    . '.leer{color:#5a9e6f;margin:.2rem 0}'
    . 'ul{margin:.2rem 0}li{margin:.15rem 0;word-break:break-all}'
    . 'code{background:#f0f0f5;padding:.05rem .3rem;border-radius:3px}'
    . '</style></head><body>'
    . '<h1>Abgleich ES ↔ Dateisystem ↔ Jobs-Dateien</h1>'
    . '<p class="kopf">Stand: ' . h(date('d.m.Y H:i')) . ' — '
    . count($spiders) . ' Scraper'
    . ($spider_wunsch !== '' ? '' : ' — einzelner Aufruf mit ?spider=&lt;Name&gt;')
    . '</p>' . "\n";
flush();

foreach ($spiders as $spider) {
    $ergebnis = abgleich($DOCS_DIR, $JOBS_DIR, $spider);
    echo html_scraper($spider, $ergebnis) . "\n";
    flush();
}

echo '<p class="kopf">Fertig: ' . h(date('d.m.Y H:i:s')) . '</p></body></html>' . "\n";
