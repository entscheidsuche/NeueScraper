<?php
declare(strict_types=1);

// Generierung kann bei Tageswechsel oder ersten Lauf einige Minuten dauern
// (54 Scraper × Zyte-API-Call). Standard-Limits hochsetzen.
@set_time_limit(0);
@ini_set('max_execution_time', '0');
@ignore_user_abort(true);

/**
 * generate_status.php — erzeugt docs/Status/status.json über alle Scraper.
 *
 * Aufruf:
 *   CLI: php generate_status.php
 *   Web: https://entscheidsuche.ch/generate_status.php
 *
 * Antwort: docs/Status/status.json (application/json).
 *
 * Cache-Strategie:
 *   • Pro Scraper liegt ein Detail-File docs/Status/<Spider>.json. Dieses wird
 *     nur dann neu generiert, wenn (a) eine Job-Datei jünger als das letzte
 *     <Spider>.json existiert ODER (b) das letzte <Spider>.json an einem
 *     anderen Tag generiert wurde (das 90-Tage-Vergleichsfenster wandert).
 *   • Die Sammeldatei docs/Status/status.json wird neu konsolidiert, sobald
 *     irgendein <Spider>.json neu geschrieben wurde, oder wenn status.json
 *     fehlt bzw. an einem anderen Tag generiert wurde.
 *   • Die Liste der zu prüfenden Scraper kommt aus docs/Facetten_alle.json
 *     (alle in den Kammern referenzierten Spider). Damit verschwinden ausser
 *     Betrieb genommene Scraper aus der Statusausgabe, auch wenn ihre alten
 *     Job-Dateien noch unter docs/Jobs/ liegen.
 *
 * Erwartete Verzeichnisstruktur (Skript liegt eine Ebene über docs/):
 *   docs/Facetten_alle.json
 *   docs/Jobs/<Spider>/{Job,Failed_Job}_<datestring>_<job-id>.json
 *   docs/Status/                 ← wird ggf. angelegt
 */

const FENSTER_TAGE      = 90;
const ERFOLGS_MIN_ITEMS = 5;
const HTTP_TIMEOUT      = 30;
const ZYTE_PAGE_SIZE    = 100;
const ZYTE_API_BASE     = 'https://app.zyte.com/api';

// Zyte/Scrapy-Cloud Storage-API-Key (https://app.zyte.com/account/apikey).
// Per ENV überschreibbar (ZYTE_API_KEY), sonst gilt der hartkodierte Wert.
const ZYTE_API_KEY_DEFAULT    = 'e198f1ba2fc346678c31a06d61acd908';
const ZYTE_PROJECT_ID_DEFAULT = '446973';

$ZYTE_API_KEY    = getenv('ZYTE_API_KEY')    ?: ZYTE_API_KEY_DEFAULT;
$ZYTE_PROJECT_ID = getenv('ZYTE_PROJECT_ID') ?: ZYTE_PROJECT_ID_DEFAULT;

$BASE_DIR      = __DIR__;
$JOBS_DIR      = $BASE_DIR . '/docs/Jobs';
$STATUS_DIR    = $BASE_DIR . '/docs/Status';
$STATUS_FILE   = $STATUS_DIR . '/status.json';
$FACETTEN_FILE = $BASE_DIR . '/docs/Facetten_alle.json';

// =============================================================================
// Logging und Antwort-Ausgabe (STDOUT/STDERR sind nur in CLI definiert)
// =============================================================================

/** Diagnostik: CLI → STDERR, Web → error_log (nie in den Response-Body). */
function log_msg(string $msg): void {
    if (PHP_SAPI === 'cli') {
        fwrite(STDERR, $msg);
    } else {
        error_log(rtrim($msg));
    }
}

function log_info(string $msg): void {
    log_msg('[' . date('H:i:s') . "] $msg\n");
}

/** Antwortet mit Fehler-JSON und passendem HTTP-Status, beendet das Skript. */
function fehler(int $http_code, string $message, int $exit_code = 1): void {
    if (PHP_SAPI !== 'cli') {
        http_response_code($http_code);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(['error' => $message], JSON_UNESCAPED_UNICODE) . "\n";
    } else {
        fwrite(STDERR, $message . "\n");
    }
    exit($exit_code);
}

/** Liefert den Inhalt der Status-Datei als Antwort, beendet das Skript. */
function antwort_aus_datei(string $pfad): void {
    $body = @file_get_contents($pfad);
    if ($body === false) {
        fehler(500, "Konnte $pfad nicht lesen");
    }
    if (PHP_SAPI !== 'cli') {
        header('Content-Type: application/json; charset=utf-8');
    }
    echo $body;
    if (substr($body, -1) !== "\n") echo "\n";
    exit(0);
}

// =============================================================================
// Hilfsfunktionen
// =============================================================================

/** "Job_2026-05-04_07:06:20_446973-45-2675.json" → "2026-05-04_07:06:20" */
function parse_zeit_aus_filename(string $filename): ?string {
    return preg_match('/_(\d{4}-\d{2}-\d{2}_\d{2}:\d{2}:\d{2})_/', $filename, $m) ? $m[1] : null;
}

/** "Job_..._446973-45-2675.json" → "446973/45/2675" */
function parse_jobid_aus_filename(string $filename): ?string {
    return preg_match('/_(\d+-\d+-\d+)\.json$/', $filename, $m) ? str_replace('-', '/', $m[1]) : null;
}

function http_get_json(string $url, ?string $auth_user = null, int $timeout = HTTP_TIMEOUT): ?array {
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => $timeout,
        CURLOPT_USERAGENT      => 'entscheidsuche-status-generator',
        CURLOPT_FAILONERROR    => false,
    ]);
    if ($auth_user !== null) {
        curl_setopt($ch, CURLOPT_USERPWD, $auth_user . ':');
    }
    $body = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err  = curl_error($ch);
    curl_close($ch);
    if ($code !== 200 || !is_string($body)) {
        log_info("HTTP $code für $url" . ($err ? " ($err)" : ''));
        return null;
    }
    $data = json_decode($body, true);
    return is_array($data) ? $data : null;
}

/**
 * Cached-Variante von zyte_jobs_for_spider: schreibt die Antwort in
 * Status/.zyte_<Spider>.json und liefert den Cache zurück, solange seit der
 * Cache-Generierung keine neuere Job-Datei dazugekommen ist. Damit triggert
 * der reine Tageswechsel keinen Zyte-API-Aufruf — nur neue Lauf-Dateien tun
 * das.
 */
function zyte_jobs_cached(
    string $spider, string $api_key, string $project, int $fenster_tage,
    string $jobs_dir, string $status_dir
): array {
    $cache_file      = "$status_dir/.zyte_$spider.json";
    $newest_job_zeit = neueste_jobsdatei_zeit($jobs_dir, $spider) ?? '';

    if (file_exists($cache_file)) {
        $cache = lese_json_file($cache_file);
        if (is_array($cache) && isset($cache['quelle_neueste_jobsdatei_zeit'], $cache['jobs'])) {
            $cached_zeit = (string)$cache['quelle_neueste_jobsdatei_zeit'];
            // Cache gilt, wenn keine neuere Job-Datei seit Cache-Generierung
            if ($newest_job_zeit === '' || $cached_zeit >= $newest_job_zeit) {
                return is_array($cache['jobs']) ? $cache['jobs'] : [];
            }
        }
    }

    $jobs = zyte_jobs_for_spider($spider, $api_key, $project, $fenster_tage);
    $cache_data = [
        'spider'                        => $spider,
        'cached_at'                     => gmdate('Y-m-d\TH:i:s\Z'),
        'quelle_neueste_jobsdatei_zeit' => $newest_job_zeit,
        'jobs'                          => $jobs,
    ];
    @file_put_contents(
        $cache_file,
        (string)json_encode($cache_data, JSON_UNESCAPED_UNICODE)
    );
    return $jobs;
}

/** Holt alle Zyte-Jobs eines Spiders im 90-Tage-Fenster. [job_id => record] */
function zyte_jobs_for_spider(string $spider, string $api_key, string $project, int $fenster_tage): array {
    $startts = (time() - $fenster_tage * 86400) * 1000;  // Zyte erwartet Millisekunden
    $jobs = [];
    $offset = 0;
    while (true) {
        $url = ZYTE_API_BASE . '/jobs/list.json?'
             . 'project='  . urlencode($project)
             . '&spider='  . urlencode($spider)
             . '&count='   . ZYTE_PAGE_SIZE
             . '&offset='  . $offset
             . '&startts=' . $startts
             . '&meta=state&meta=close_reason&meta=items_scraped&meta=errors_count'
             . '&meta=running_time&meta=started_time&meta=finished_time&meta=spider';
        $resp = http_get_json($url, $api_key);
        if (!is_array($resp)) break;
        $rows = $resp['jobs'] ?? (isset($resp[0]) ? $resp : []);
        if (!is_array($rows) || count($rows) === 0) break;
        foreach ($rows as $j) {
            if (isset($j['id'])) $jobs[$j['id']] = $j;
        }
        if (count($rows) < ZYTE_PAGE_SIZE) break;
        $offset += ZYTE_PAGE_SIZE;
        if ($offset > 5000) break;
    }
    return $jobs;
}

function lese_json_file(string $path): ?array {
    $body = @file_get_contents($path);
    if ($body === false) return null;
    $data = json_decode($body, true);
    return is_array($data) ? $data : null;
}

/**
 * Liest ein Job-File OHNE den `dateien`-Block — dieser kann bei großen
 * Spidern 10+ MB groß sein. Da `pipelines.py` immer in der Reihenfolge
 *   spider, job, jobtyp, time, dateien, signaturen, gesamt
 * schreibt, reicht es, den Kopf der Datei (für die Metadaten) und den
 * Schwanz (für signaturen+gesamt) zu lesen und beides zu einem gültigen
 * Mini-JSON zusammenzusetzen, das `dateien` einfach weglässt.
 *
 * Vorteil: pro File werden statt 16 MB nur ~250 KB von der Platte gelesen
 * und an json_decode übergeben.
 */
function lese_job_file_kompakt(string $pfad): ?array {
    $kopf_max = 1024;        // 1 KB für Top-Level-Metadaten reicht weit aus
    $tail_max = 256 * 1024;  // 256 KB Schwanz für signaturen+gesamt

    $fp = @fopen($pfad, 'rb');
    if ($fp === false) return null;
    $stat = @fstat($fp);
    if (!is_array($stat)) { fclose($fp); return null; }
    $size = (int)($stat['size'] ?? 0);
    if ($size === 0) { fclose($fp); return null; }

    // Kleine Files komplett lesen (Failed_Job_*, leere Läufe etc.)
    if ($size < $kopf_max + $tail_max) {
        rewind($fp);
        $body = (string)stream_get_contents($fp);
        fclose($fp);
        $data = json_decode($body, true);
        return is_array($data) ? $data : null;
    }

    // Kopf
    rewind($fp);
    $kopf = (string)fread($fp, $kopf_max);
    // Schwanz
    fseek($fp, -$tail_max, SEEK_END);
    $tail = (string)fread($fp, $tail_max);
    fclose($fp);

    // Vor dem "dateien"-Schlüssel im Kopf abschneiden — alles davor sind die
    // Metadaten {"spider": "...", "job": "...", "jobtyp": "...", "time": "..."
    $dateien_pos = strpos($kopf, '"dateien"');
    if ($dateien_pos === false) return null;
    $kopf_teil = rtrim(substr($kopf, 0, $dateien_pos), ", \t\r\n");

    // Im Schwanz den letzten "signaturen"-Schlüssel suchen — von dort bis
    // Dateiende ist das, was wir behalten wollen.
    $sig_pos = strrpos($tail, '"signaturen"');
    if ($sig_pos === false) return null;
    $tail_teil = substr($tail, $sig_pos);

    $json = $kopf_teil . ',' . $tail_teil;
    $data = json_decode($json, true);
    return is_array($data) ? $data : null;
}

function neueste_jobsdatei_zeit(string $jobs_dir, string $spider): ?string {
    $alle = glob("$jobs_dir/$spider/{Job,Failed_Job}_*.json", GLOB_BRACE) ?: [];
    $max = null;
    foreach ($alle as $p) {
        $z = parse_zeit_aus_filename(basename($p));
        if ($z !== null && ($max === null || $z > $max)) $max = $z;
    }
    return $max;
}

/**
 * Listet Job-File-Pfade aus den letzten N Tagen, sortiert nach Zeit absteigend
 * (neueste zuerst). Nur Filenames + Zeitstempel, kein File-Inhalt.
 */
function liste_job_files(string $jobs_dir, string $spider, int $fenster_tage): array {
    $cutoff_str = date('Y-m-d_H:i:s', time() - $fenster_tage * 86400);
    $alle = glob("$jobs_dir/$spider/{Job,Failed_Job}_*.json", GLOB_BRACE) ?: [];
    $files = [];
    foreach ($alle as $pfad) {
        $b = basename($pfad);
        $zeit = parse_zeit_aus_filename($b);
        if ($zeit === null || $zeit < $cutoff_str) continue;
        $files[] = [
            'pfad'      => $pfad,
            'zeit'      => $zeit,
            'name'      => $b,
            'datei'     => "Jobs/$spider/$b",
            'datei_typ' => str_starts_with($b, 'Failed_') ? 'failed' : 'job',
        ];
    }
    usort($files, fn($a, $b) => strcmp($b['zeit'], $a['zeit']));  // neueste zuerst
    return $files;
}

function lauf_datensatz(array $eintrag, array $zyte_jobs): array {
    $jd     = $eintrag['jobdata'];
    $job_id = $jd['job'] ?? parse_jobid_aus_filename(basename($eintrag['pfad']));
    $z      = ($job_id !== null && isset($zyte_jobs[$job_id])) ? $zyte_jobs[$job_id] : null;
    $jobtyp = $jd['jobtyp'] ?? null;
    $g      = $jd['gesamt'] ?? [];

    if (is_array($z) && isset($z['items_scraped'])) {
        $items = (int)$z['items_scraped'];
    } else {
        $items = (int)($g['aktuell_neu'] ?? 0) + (int)($g['aktuell_aktualisiert'] ?? 0);
    }

    // Erfolgskriterium:
    //   • Lauf-Datei kein Failed_*
    //   • Zyte-State 'finished' (oder kein Zyte-Eintrag — Fallback)
    //   • Bei Komplett-/Neu-Läufen zusätzlich: Gesamt-Bestand >= Schwelle
    //     (filtert Mini-/Test-Komplettläufe aus, die nur ein paar Items
    //      einspielen und sonst den ganzen Bestand ersetzen würden).
    //   Bei Add/Update-Läufen KEINE Item-Schwelle — ein erfolgreich
    //   beendeter Update-Lauf ist auch dann erfolgreich, wenn er
    //   nichts geändert hat (ruhiger Tag).
    $bestand = (int)($g['gesamt'] ?? 0);
    $komplett_ok = ($jobtyp === 'komplett' || $jobtyp === 'neu')
                 ? $bestand >= ERFOLGS_MIN_ITEMS
                 : true;
    $erfolgreich = $eintrag['datei_typ'] !== 'failed'
                && (!is_array($z) || ($z['state'] ?? null) === 'finished')
                && $komplett_ok;

    return [
        'zeit'         => $eintrag['zeit'],
        'job'          => $job_id,
        'jobtyp'       => $jd['jobtyp'] ?? null,
        'datei'        => $eintrag['datei'],
        'datei_typ'    => $eintrag['datei_typ'],
        'jobdata'      => $jd,
        'zyte'         => $z,
        'items_scraped'=> $items,
        'anzahl_fehler'=> is_array($z) && isset($z['errors_count']) ? (int)$z['errors_count'] : 0,
        'erfolgreich'  => $erfolgreich,
    ];
}

function lauf_block(array $l, bool $mit_signaturen): array {
    $jd = $l['jobdata'];
    $g  = $jd['gesamt'] ?? [];
    $z  = $l['zyte'] ?? null;
    $block = [
        'zeit'              => $l['zeit'],
        'job'               => $l['job'],
        'jobtyp'            => $l['jobtyp'],
        'datei'             => $l['datei'],
        'datei_typ'         => $l['datei_typ'],
        'zyte_state'        => is_array($z) ? ($z['state'] ?? null)        : null,
        'zyte_close_reason' => is_array($z) ? ($z['close_reason'] ?? null) : null,
        'zyte_runtime_sek'  => is_array($z) && isset($z['running_time']) ? (int)round(((int)$z['running_time']) / 1000) : null,
        'items_scraped'     => $l['items_scraped'],
        'anzahl_fehler'     => $l['anzahl_fehler'],
    ];
    if ($mit_signaturen) {
        $block['gesamt']                = (int)($g['gesamt'] ?? 0);
        $block['aktuell_neu']           = (int)($g['aktuell_neu'] ?? 0);
        $block['aktuell_aktualisiert']  = (int)($g['aktuell_aktualisiert'] ?? 0);
        $block['vorher_entfernt']       = (int)($g['vorher_entfernt'] ?? 0);
        $sigs = [];
        foreach (($jd['signaturen'] ?? []) as $sig => $vals) {
            $sigs[$sig] = [
                'gesamt'               => (int)($vals['gesamt'] ?? 0),
                'aktuell_neu'          => (int)($vals['aktuell_neu'] ?? 0),
                'aktuell_aktualisiert' => (int)($vals['aktuell_aktualisiert'] ?? 0),
            ];
        }
        $block['signaturen'] = $sigs;
    }
    return $block;
}

/**
 * Iteriert die Job-Files eines Spiders chronologisch absteigend, lädt jedes
 * File einzeln (ohne `dateien`-Block) und aggregiert daraus den Status.
 * Niemals mehr als ein Job-File gleichzeitig im Speicher.
 */
function generiere_spider_status(
    string $spider, string $jobs_dir, string $status_dir,
    string $api_key, string $project
): array {
    $now_iso = gmdate('Y-m-d\TH:i:s\Z');
    $files   = liste_job_files($jobs_dir, $spider, FENSTER_TAGE);  // neueste zuerst
    $zyte_jobs = zyte_jobs_cached($spider, $api_key, $project, FENSTER_TAGE, $jobs_dir, $status_dir);

    $base = [
        'spider'                            => $spider,
        'generated'                         => $now_iso,
        'quelle_neueste_jobsdatei'          => null,
        'quelle_neueste_jobsdatei_zeit'     => null,
        'letzter_lauf'                      => null,
        'letzter_erfolgreicher_lauf'        => null,
        'fehlversuche_seit_letzter_erfolg'  => 0,
        'vergleich_90_tage'                 => [
            'anzahl_erfolgreicher_laeufe' => 0,
            'gesamt_max'                  => 0,
        ],
    ];
    if (empty($files)) return $base;

    $erfolg_gefunden = false;
    $fehlversuche    = 0;
    $erfolg_anzahl   = 0;
    $gesamt_max      = 0;

    foreach ($files as $idx => $f) {
        $jd = lese_job_file_kompakt($f['pfad']);
        if ($jd === null) continue;

        $eintrag = [
            'pfad'      => $f['pfad'],
            'zeit'      => $f['zeit'],
            'datei'     => $f['datei'],
            'datei_typ' => $f['datei_typ'],
            'jobdata'   => $jd,
        ];
        $lauf = lauf_datensatz($eintrag, $zyte_jobs);

        // erstes (= neuestes) File: das ist der "letzte_lauf"
        if ($idx === 0) {
            $base['quelle_neueste_jobsdatei']      = $f['datei'];
            $base['quelle_neueste_jobsdatei_zeit'] = $f['zeit'];
            $base['letzter_lauf']                  = lauf_block($lauf, false);
        }

        if ($lauf['erfolgreich']) {
            $erfolg_anzahl++;
            $g = (int)($jd['gesamt']['gesamt'] ?? 0);
            if ($g > $gesamt_max) $gesamt_max = $g;

            // erster gefundener erfolgreicher Lauf (rückwärts gesehen) ist
            // der "letzter_erfolgreicher_lauf"
            if (!$erfolg_gefunden) {
                $erfolg_gefunden = true;
                $base['letzter_erfolgreicher_lauf']        = lauf_block($lauf, true);
                $base['fehlversuche_seit_letzter_erfolg']  = $fehlversuche;
            }
        } elseif (!$erfolg_gefunden) {
            $fehlversuche++;
        }

        unset($jd, $lauf, $eintrag);
    }

    // kein erfolgreicher Lauf im Fenster: alle Versuche als Fehlversuche zählen
    if (!$erfolg_gefunden) {
        $base['fehlversuche_seit_letzter_erfolg'] = $fehlversuche;
    }

    $base['vergleich_90_tage'] = [
        'anzahl_erfolgreicher_laeufe' => $erfolg_anzahl,
        'gesamt_max'                  => $gesamt_max,
    ];

    return $base;
}

function atomar_schreiben(string $pfad, string $inhalt): void {
    $tmp = $pfad . '.tmp.' . getmypid();
    if (file_put_contents($tmp, $inhalt) === false) {
        throw new RuntimeException("Konnte $tmp nicht schreiben");
    }
    if (!rename($tmp, $pfad)) {
        @unlink($tmp);
        throw new RuntimeException("Konnte $tmp → $pfad nicht umbenennen");
    }
}

/**
 * Ermittelt für einen einzelnen Spider, ob das pro-Spider-Cache-File noch
 * aktuell ist. Liefert true, wenn neu generiert werden muss.
 */
function muss_regeneriert_werden(string $status_file, string $jobs_dir, string $spider, string $today): bool {
    if (!file_exists($status_file)) return true;
    $alt = lese_json_file($status_file);
    if (!is_array($alt)) return true;

    $alt_quelle_zeit = $alt['quelle_neueste_jobsdatei_zeit'] ?? '';
    $alt_tag         = substr((string)($alt['generated'] ?? ''), 0, 10);
    $neu_quelle_zeit = neueste_jobsdatei_zeit($jobs_dir, $spider) ?? '';

    // Wenn der Spider gar keine Job-Dateien hat (z.B. neu eingeführt, noch nie
    // gelaufen), reicht es, wenn das Cache-File von heute ist.
    if ($neu_quelle_zeit === '') {
        return $alt_tag !== $today;
    }

    // Aktuell genau dann, wenn (a) heute generiert UND (b) keine neuere Job-Datei
    // seit der letzten Generierung dazugekommen ist.
    if ($alt_tag === $today
        && (string)$alt_quelle_zeit !== ''
        && (string)$alt_quelle_zeit >= $neu_quelle_zeit) {
        return false;
    }
    return true;
}

/** Liest aus Facetten_alle.json alle eindeutigen Spider-Namen, alphabetisch. */
function liste_spider(string $facetten_file): array {
    $facetten = lese_json_file($facetten_file);
    if (!is_array($facetten)) return [];
    $spiders = [];
    foreach ($facetten as $kanton) {
        if (!is_array($kanton)) continue;
        foreach (($kanton['gerichte'] ?? []) as $gericht) {
            if (!is_array($gericht)) continue;
            foreach (($gericht['kammern'] ?? []) as $kammer) {
                $sp = is_array($kammer) ? ($kammer['spider'] ?? null) : null;
                if (is_string($sp) && $sp !== ''
                    && preg_match('/^[A-Za-z][A-Za-z0-9_]*$/', $sp)) {
                    $spiders[$sp] = true;  // dedupe
                }
            }
        }
    }
    $namen = array_keys($spiders);
    sort($namen);
    return $namen;
}

/**
 * Konsolidiert status.json aus den <Spider>.json im Status-Verzeichnis,
 * gefiltert auf die übergebene Whitelist (= aktuell aktive Scraper).
 */
function konsolidiere_status(string $status_dir, string $status_file, array $whitelist): void {
    $aggregat = [
        'generated'    => gmdate('Y-m-d\TH:i:s\Z'),
        'spider_count' => 0,
        'spiders'      => [],
    ];
    $whitelist_set = array_flip($whitelist);
    foreach ($whitelist as $sp) {
        $pfad = "$status_dir/$sp.json";
        if (!file_exists($pfad)) continue;
        $data = lese_json_file($pfad);
        if (!is_array($data) || empty($data['spider'])) continue;
        if (!isset($whitelist_set[$data['spider']])) continue;

        $sp = $data['spider'];
        $kompakt = [];

        $ll = $data['letzter_lauf'] ?? null;
        if (is_array($ll)) {
            $kompakt['letzter_lauf'] = [
                'zeit'          => $ll['zeit'] ?? null,
                'erfolgreich'   => ($ll['datei_typ'] ?? '') !== 'failed'
                                && ($ll['zyte_state'] ?? '') === 'finished'
                                && (int)($ll['items_scraped'] ?? 0) >= ERFOLGS_MIN_ITEMS,
                'anzahl_fehler' => (int)($ll['anzahl_fehler'] ?? 0),
            ];
        }
        $le = $data['letzter_erfolgreicher_lauf'] ?? null;
        if (is_array($le)) {
            $kompakt['letzter_erfolgreicher_lauf'] = [
                'zeit'          => $le['zeit'] ?? null,
                'gesamt'        => (int)($le['gesamt'] ?? 0),
                'aktuell_neu'   => (int)($le['aktuell_neu'] ?? 0),
                'anzahl_fehler' => (int)($le['anzahl_fehler'] ?? 0),
            ];
            $sigs = [];
            foreach (($le['signaturen'] ?? []) as $sig => $v) {
                $sigs[$sig] = [
                    'gesamt'      => (int)($v['gesamt'] ?? 0),
                    'aktuell_neu' => (int)($v['aktuell_neu'] ?? 0),
                ];
            }
            $kompakt['signaturen'] = $sigs;
        }
        $kompakt['fehlversuche_seit_letzter_erfolg'] = (int)($data['fehlversuche_seit_letzter_erfolg'] ?? 0);
        $kompakt['vergleich_90_tage_gesamt_max']     = (int)($data['vergleich_90_tage']['gesamt_max'] ?? 0);

        $aggregat['spiders'][$sp] = $kompakt;
    }
    ksort($aggregat['spiders']);
    $aggregat['spider_count'] = count($aggregat['spiders']);
    atomar_schreiben(
        $status_file,
        (string)json_encode($aggregat, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT)
    );
}

// =============================================================================
// Hauptablauf
// =============================================================================

if ($ZYTE_API_KEY === '') {
    fehler(500, 'ZYTE_API_KEY fehlt', 1);
}
if (!is_file($FACETTEN_FILE)) {
    fehler(500, "Facetten-Datei fehlt: $FACETTEN_FILE", 1);
}
if (!is_dir($JOBS_DIR)) {
    fehler(500, "Jobs-Verzeichnis fehlt: $JOBS_DIR", 1);
}
if (!is_dir($STATUS_DIR) && !mkdir($STATUS_DIR, 0775, true) && !is_dir($STATUS_DIR)) {
    fehler(500, "Konnte $STATUS_DIR nicht anlegen", 1);
}

$spiders = liste_spider($FACETTEN_FILE);
if (empty($spiders)) {
    fehler(500, 'Keine Spider in Facetten gefunden', 1);
}

$today   = date('Y-m-d');
$dirty   = false;
$count_regen   = 0;
$count_skipped = 0;
$count_fehler  = 0;

foreach ($spiders as $spider) {
    $status_file = "$STATUS_DIR/$spider.json";
    if (!muss_regeneriert_werden($status_file, $JOBS_DIR, $spider, $today)) {
        $count_skipped++;
        continue;
    }
    log_info("$spider: regeneriere");
    try {
        $status = generiere_spider_status($spider, $JOBS_DIR, $STATUS_DIR, $ZYTE_API_KEY, $ZYTE_PROJECT_ID);
        atomar_schreiben(
            $status_file,
            (string)json_encode($status, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT)
        );
        $dirty = true;
        $count_regen++;
    } catch (\Throwable $e) {
        log_info("Fehler bei $spider: " . $e->getMessage());
        $count_fehler++;
    }
}

// status.json neu konsolidieren wenn dirty, oder wenn die Datei fehlt bzw.
// nicht heute geschrieben wurde (damit der Tageswechsel auch greift, wenn sich
// kein einzelner Scraper geändert hat).
$status_braucht_update = $dirty || !file_exists($STATUS_FILE);
if (!$status_braucht_update) {
    $alt = lese_json_file($STATUS_FILE);
    $alt_tag = is_array($alt) ? substr((string)($alt['generated'] ?? ''), 0, 10) : '';
    if ($alt_tag !== $today) $status_braucht_update = true;
}
if ($status_braucht_update) {
    log_info("konsolidiere status.json");
    try {
        konsolidiere_status($STATUS_DIR, $STATUS_FILE, $spiders);
    } catch (\Throwable $e) {
        log_info('Konsolidierung fehlgeschlagen: ' . $e->getMessage());
        fehler(500, 'Konsolidierung fehlgeschlagen: ' . $e->getMessage(), 1);
    }
}

log_info("fertig: $count_regen regeneriert, $count_skipped übersprungen, $count_fehler Fehler");
antwort_aus_datei($STATUS_FILE);
