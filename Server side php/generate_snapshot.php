<?php
declare(strict_types=1);

/**
 * generate_snapshot.php — schreibt einen Tagesschnappschuss des ES-Bestands.
 *
 * Aufruf:
 *   CLI (Cron, empfohlen):
 *     php /var/www/entscheidsuche/generate_snapshot.php
 *
 *   Web (Notfall / Debug):
 *     https://entscheidsuche.ch/generate_snapshot.php
 *
 * Output:
 *   docs/Snapshots/<YYYY-MM-DD>.json
 *
 *   {
 *     "generated": "2026-06-18T03:00:42Z",
 *     "datum": "2026-06-18",
 *     "total_alle": 1234567,
 *     "total": {
 *       "CH":          200000,
 *       "CH/CH_BGer":  150000,
 *       ...
 *     }
 *   }
 *
 * Konzept:
 *   • Idempotent pro Tag: existiert <YYYY-MM-DD>.json bereits, wird nichts
 *     geschrieben (Antwort: HTTP 200, "skipped: file exists"). Erzwingen mit
 *     ?force=1 (Web) bzw. --force (CLI).
 *   • Aufräumen: Snapshots älter als FENSTER_TAGE+PUFFER Tage werden
 *     gelöscht (Default: 400 Tage).
 *   • Cron-Empfehlung: 1× pro Tag, z. B. 03:30 lokal:
 *       30 3 * * *  /usr/bin/php /var/www/entscheidsuche/generate_snapshot.php
 *
 *   Bei Skripten unter Cron stets vollen PHP-Pfad verwenden und stderr in
 *   ein Logfile umlenken.
 */

// Bei grossem Index kann eine ES-Antwort > 30 s dauern.
@set_time_limit(0);
@ini_set('max_execution_time', '0');
@ignore_user_abort(true);

const ES_URL            = 'https://entscheidsuche.ch/_searchV2.php';
const HTTP_TIMEOUT      = 60;
const FENSTER_TAGE      = 400;             // ~ein Jahr + Puffer
const FACETTEN_SIZE     = 2000;            // erwartete Anzahl distincter hierarchy-Werte
const SNAPSHOT_DIR_REL  = 'docs/Snapshots';

$BASE_DIR     = __DIR__;
$SNAPSHOT_DIR = $BASE_DIR . '/' . SNAPSHOT_DIR_REL;

// ---------------------------------------------------------------------------
// Ausgabe-Helfer (CLI → STDERR, Web → error_log; nie in den Response-Body).
// ---------------------------------------------------------------------------

function log_msg(string $msg): void {
    if (PHP_SAPI === 'cli') {
        fwrite(STDERR, $msg);
    } else {
        error_log(rtrim($msg));
    }
}
function log_info(string $msg): void { log_msg('[' . date('H:i:s') . "] $msg\n"); }

function ende(int $http_code, array $body, int $exit_code = 0): void {
    if (PHP_SAPI === 'cli') {
        // CLI: JSON auf stdout (für Cron-Logs), Exit-Code als Status
        echo json_encode($body, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT) . "\n";
    } else {
        http_response_code($http_code);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode($body, JSON_UNESCAPED_UNICODE) . "\n";
    }
    exit($exit_code);
}

// ---------------------------------------------------------------------------
// Parameter
// ---------------------------------------------------------------------------

$force = false;
if (PHP_SAPI === 'cli') {
    $argv_local = $_SERVER['argv'] ?? [];
    foreach ($argv_local as $arg) {
        if ($arg === '--force' || $arg === '-f') $force = true;
    }
} else {
    $force = !empty($_REQUEST['force']);
}

// ---------------------------------------------------------------------------
// Snapshot-Verzeichnis sicherstellen
// ---------------------------------------------------------------------------

if (!is_dir($SNAPSHOT_DIR)) {
    if (!@mkdir($SNAPSHOT_DIR, 0775, true) && !is_dir($SNAPSHOT_DIR)) {
        ende(500, ['error' => "Kann $SNAPSHOT_DIR nicht anlegen"], 1);
    }
}

// ---------------------------------------------------------------------------
// Tagesdatei
// ---------------------------------------------------------------------------

$datum   = gmdate('Y-m-d');                 // UTC-Tag, damit überall konsistent
$dateifn = "$SNAPSHOT_DIR/$datum.json";

/**
 * Index aus den vorhandenen <YYYY-MM-DD>.json-Dateien neu generieren.
 * Wird sowohl im Normalfall als auch beim Skip-Pfad aufgerufen.
 */
function index_neu_schreiben(string $snapshot_dir): int {
    $alle = [];
    foreach (glob($snapshot_dir . '/*.json') ?: [] as $pfad) {
        $name = basename($pfad);
        if (preg_match('/^(\d{4}-\d{2}-\d{2})\.json$/', $name, $m)) {
            $alle[] = $m[1];
        }
    }
    sort($alle);
    $indexFile = $snapshot_dir . '/index.json';
    $indexTmp  = $indexFile . '.tmp.' . getmypid();
    $indexData = [
        'generated' => gmdate('Y-m-d\TH:i:s\Z'),
        'count'     => count($alle),
        'dates'     => $alle,
    ];
    @file_put_contents(
        $indexTmp,
        (string)json_encode($indexData, JSON_UNESCAPED_UNICODE)
    );
    @rename($indexTmp, $indexFile);
    return count($alle);
}

if (file_exists($dateifn) && !$force) {
    // Auch im Skip-Pfad den Index aktualisieren — sonst bliebe er nach einem
    // Erstdeploy (Snapshot heute schon da, aber index.json noch leer) auf
    // dem Stand vom vorigen Lauf.
    $n = index_neu_schreiben($SNAPSHOT_DIR);
    ende(200, [
        'status'        => 'skipped',
        'grund'         => 'snapshot existiert bereits',
        'datei'         => SNAPSHOT_DIR_REL . "/$datum.json",
        'index_dateien' => $n,
    ], 0);
}

// ---------------------------------------------------------------------------
// ES-Abfrage
// ---------------------------------------------------------------------------

$query = [
    'size'             => 0,
    'track_total_hits' => true,
    'query'            => ['match_all' => (object)[]],
    'aggs'             => [
        'total' => [
            'terms' => [
                'field' => 'hierarchy',
                'size'  => FACETTEN_SIZE,
            ],
        ],
    ],
];

$payload = json_encode($query, JSON_UNESCAPED_UNICODE | JSON_FORCE_OBJECT);
$ch = curl_init(ES_URL);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST           => true,
    CURLOPT_POSTFIELDS     => $payload,
    CURLOPT_TIMEOUT        => HTTP_TIMEOUT,
    CURLOPT_USERAGENT      => 'entscheidsuche-snapshot-generator',
    CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
]);
$body = curl_exec($ch);
$code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$err  = curl_error($ch);
curl_close($ch);

if ($code !== 200 || !is_string($body)) {
    log_info("ES-Anfrage HTTP $code" . ($err ? " ($err)" : ''));
    ende(502, [
        'error'  => "Elasticsearch-Anfrage fehlgeschlagen (HTTP $code)",
        'detail' => $err ?: substr((string)$body, 0, 400),
    ], 2);
}

$resp = json_decode($body, true);
if (!is_array($resp) || !isset($resp['aggregations']['total']['buckets'])) {
    ende(502, [
        'error' => 'ES-Antwort ohne aggregations.total.buckets',
        'body'  => substr($body, 0, 400),
    ], 2);
}

$buckets = $resp['aggregations']['total']['buckets'];
$total   = [];
foreach ($buckets as $b) {
    if (!isset($b['key']) || !is_string($b['key'])) continue;
    $total[$b['key']] = (int)$b['doc_count'];
}

$total_alle = isset($resp['hits']['total']['value'])
    ? (int)$resp['hits']['total']['value']
    : array_sum($total);

if ($total_alle === 0) {
    // Wenn ES leer antwortet, lieber NICHT speichern — sonst würde ein Ausfall
    // beim nächsten Tag als "Bestand auf 0 gesunken" interpretiert.
    ende(503, [
        'error'      => 'ES liefert 0 Dokumente — kein Snapshot geschrieben',
        'total_alle' => 0,
    ], 3);
}

// ---------------------------------------------------------------------------
// Schreiben (atomar)
// ---------------------------------------------------------------------------

$snapshot = [
    'generated'  => gmdate('Y-m-d\TH:i:s\Z'),
    'datum'      => $datum,
    'total_alle' => $total_alle,
    'total'      => $total,
];
$tmp = $dateifn . '.tmp.' . getmypid();
$ok  = @file_put_contents(
    $tmp,
    (string)json_encode($snapshot, JSON_UNESCAPED_UNICODE)
);
if ($ok === false) {
    ende(500, ['error' => "Kann $tmp nicht schreiben"], 4);
}
if (!@rename($tmp, $dateifn)) {
    @unlink($tmp);
    ende(500, ['error' => "Kann $dateifn nicht umbenennen"], 4);
}

// ---------------------------------------------------------------------------
// Aufräumen — Snapshots älter als FENSTER_TAGE löschen
// ---------------------------------------------------------------------------

$geloescht = [];
$grenze    = strtotime("-" . FENSTER_TAGE . " days");
foreach (glob($SNAPSHOT_DIR . '/*.json') ?: [] as $pfad) {
    $name = basename($pfad);
    if (!preg_match('/^(\d{4}-\d{2}-\d{2})\.json$/', $name, $m)) continue;
    $ts = strtotime($m[1]);
    if ($ts !== false && $ts < $grenze) {
        if (@unlink($pfad)) $geloescht[] = $name;
    }
}

// ---------------------------------------------------------------------------
// Index aktualisieren — Liste aller vorhandenen Snapshot-Datumswerte.
// Das Frontend wählt anhand der vorhandenen Datumswerte dynamisch 1–4 Slots
// aus (gestern, vor einer Woche, vor einem Monat, vor einem Jahr — jeweils
// gefallbackt auf den nächstkleineren verfügbaren Tag).
// ---------------------------------------------------------------------------

$index_n = index_neu_schreiben($SNAPSHOT_DIR);

// ---------------------------------------------------------------------------
// Antwort
// ---------------------------------------------------------------------------

ende(200, [
    'status'              => 'ok',
    'datei'               => SNAPSHOT_DIR_REL . "/$datum.json",
    'datum'               => $datum,
    'total_alle'          => $total_alle,
    'anzahl_hierarchien'  => count($total),
    'aufgeraeumt'         => $geloescht,
    'index_dateien'       => $index_n,
], 0);
