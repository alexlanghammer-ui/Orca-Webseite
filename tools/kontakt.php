<?php
/**
 * Nimmt das Kontaktformular der ORCA-Website an und schickt es als E-Mail.
 *
 * Liegt auf dem Strato-Webspace unter formular.orca.gmbh/kontakt.php.
 * Die Website selbst laeuft auf GitHub Pages, deshalb die CORS-Kopfzeilen:
 * Ohne sie verwirft der Browser die Antwort, weil sie von einem anderen
 * Rechnernamen kommt.
 */

// --- Einstellungen -------------------------------------------------------
// Empfaenger. Hier landen die Anfragen. Das Postfach muss es geben, sonst
// kommt die Mail als unzustellbar zurueck.
const EMPFAENGER = 'info@orca.gmbh';

// Absender. Diese Adresse muss angelegt sein, und der Mailversand der Domain
// muss bei Strato liegen — sonst passt der SPF-Eintrag nicht zum sendenden
// Server und viele Empfaenger sortieren die Mail als gefaelscht aus. Liegt die
// Mail von orca.gmbh woanders, hier eine Adresse einer Domain eintragen, deren
// Mail bei Strato liegt.
const ABSENDER = 'formular@orca.gmbh';

// Von diesen Adressen darf das Formular kommen.
const ERLAUBTE_HERKUNFT = [
    'https://orca.gmbh',
    'https://www.orca.gmbh',
];

// Eingangsbestaetigung an den Absender. Auf false setzen, um sie abzuschalten.
const BESTAETIGUNG = true;

// Hoechstzahl Absendungen pro Stunde und IP-Adresse. Das begrenzt den Schaden,
// falls jemand das Formular benutzt, um ueber die Bestaetigungsmail fremde
// Postfaecher mit eigenem Text zu beschicken.
const MAX_PRO_STUNDE = 5;

// --- CORS ----------------------------------------------------------------
$herkunft = $_SERVER['HTTP_ORIGIN'] ?? '';
$erlaubt = $herkunft === '' || in_array($herkunft, ERLAUBTE_HERKUNFT, true);
if ($herkunft !== '' && $erlaubt) {
    header('Access-Control-Allow-Origin: ' . $herkunft);
    header('Vary: Origin');
}
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
header('Content-Type: application/json; charset=utf-8');

// Der Browser fragt bei JSON vorab per OPTIONS nach, ob er senden darf.
if (($_SERVER['REQUEST_METHOD'] ?? '') === 'OPTIONS') {
    http_response_code(204);
    exit;
}

function ende(int $code, array $daten): void
{
    http_response_code($code);
    echo json_encode($daten, JSON_UNESCAPED_UNICODE);
    exit;
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    ende(405, ['ok' => false, 'fehler' => 'Nur POST.']);
}

// Eine fremde Website wird abgewiesen, bevor etwas verschickt wird. Das haelt
// nur Missbrauch aus dem Browser auf: Wer direkt mit einem Programm anfragt,
// setzt gar keine Herkunft oder eine beliebige. Gegen Massenzusendungen
// wirken deshalb der Honigtopf und die Pruefung der Eingaben, nicht dies.
if (!$erlaubt) {
    ende(403, ['ok' => false, 'fehler' => 'Herkunft nicht zugelassen.']);
}

// --- Eingaben ------------------------------------------------------------
// Das Formular schickt JSON; Formularkodierung wird zusaetzlich angenommen,
// damit ein Test mit curl ohne Umstaende funktioniert.
$roh = file_get_contents('php://input');
$daten = [];
if ($roh !== '' && $roh[0] === '{') {
    $daten = json_decode($roh, true) ?: [];
} else {
    $daten = $_POST;
}

$feld = static function (string $name) use ($daten): string {
    $wert = $daten[$name] ?? '';
    if (!is_string($wert)) {
        return '';
    }
    // Zeilenumbrueche aus einzeiligen Angaben entfernen: Sie liessen sich
    // sonst benutzen, um eigene Kopfzeilen in die Mail zu schmuggeln.
    return trim(preg_replace('/[\r\n]+/', ' ', $wert));
};

// Honigtopf: Ein Feld, das nur automatische Ausfueller bedienen. Ist es
// gefuellt, wird nichts verschickt — nach aussen sieht es nach Erfolg aus,
// damit der Absender nicht merkt, woran es lag.
if ($feld('_gotcha') !== '' || $feld('honeypot') !== '') {
    ende(200, ['ok' => true]);
}

$name     = mb_substr($feld('name'), 0, 120);
$email    = mb_substr($feld('email'), 0, 160);
$fahrzeug = mb_substr($feld('fahrzeug'), 0, 160);
$betreff  = mb_substr($feld('betreff'), 0, 160);

$nachricht = $daten['nachricht'] ?? '';
$nachricht = is_string($nachricht) ? trim($nachricht) : '';
$nachricht = mb_substr($nachricht, 0, 5000);

// Sprache der Website, fuer die Eingangsbestaetigung. Nur die drei bekannten
// Werte werden uebernommen, alles andere gilt als Deutsch.
$sprache = $feld('sprache');
if (!in_array($sprache, ['de', 'en', 'fr'], true)) {
    $sprache = 'de';
}

if ($email === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
    ende(400, ['ok' => false, 'fehler' => 'E-Mail fehlt oder ist unvollstaendig.']);
}
if ($nachricht === '') {
    ende(400, ['ok' => false, 'fehler' => 'Nachricht fehlt.']);
}

/**
 * Begrenzt die Absendungen je IP-Adresse auf MAX_PRO_STUNDE.
 *
 * Die Zeitstempel liegen in einer Datei im temporaeren Verzeichnis. Laesst sich
 * die Datei nicht lesen oder schreiben, gilt die Anfrage als erlaubt: Eine
 * verlorene Anfrage waere schlimmer als eine ungebremste.
 */
function drossel_frei(): bool
{
    $datei = sys_get_temp_dir() . '/orca-formular-'
           . md5($_SERVER['REMOTE_ADDR'] ?? 'unbekannt');
    $jetzt = time();

    $stempel = [];
    if (is_readable($datei)) {
        $inhalt = (string) @file_get_contents($datei);
        foreach (explode("\n", $inhalt) as $zeile) {
            $zahl = (int) $zeile;
            if ($zahl > $jetzt - 3600) {
                $stempel[] = $zahl;
            }
        }
    }

    if (count($stempel) >= MAX_PRO_STUNDE) {
        return false;
    }

    $stempel[] = $jetzt;
    @file_put_contents($datei, implode("\n", $stempel), LOCK_EX);
    return true;
}

if (!drossel_frei()) {
    ende(429, ['ok' => false, 'fehler' => 'Zu viele Anfragen. Bitte spaeter erneut.']);
}

// --- Mail zusammensetzen -------------------------------------------------
$titel = $betreff !== '' ? $betreff : 'Anfrage über die Website';
if ($fahrzeug !== '') {
    $titel .= ' – ' . $fahrzeug;
}

$text = "Neue Anfrage über das Kontaktformular\n\n"
      . 'Name:      ' . ($name !== '' ? $name : '(keine Angabe)') . "\n"
      . 'E-Mail:    ' . $email . "\n"
      . 'Fahrzeug:  ' . ($fahrzeug !== '' ? $fahrzeug : '(keine Angabe)') . "\n"
      . 'Gesendet:  ' . date('d.m.Y H:i') . "\n\n"
      . "Nachricht:\n" . $nachricht . "\n";

$kopf = [
    'From: ORCA Website <' . ABSENDER . '>',
    // Bewusst nur die Adresse ohne vorangestellten Namen: Ein Name aus dem
    // Formular kann Zeichen enthalten, die in einem Adressfeld eine Bedeutung
    // haben (<, >, :, Anfuehrungszeichen). Der Name steht im Text der Mail.
    'Reply-To: ' . $email,
    'Content-Type: text/plain; charset=UTF-8',
    'Content-Transfer-Encoding: 8bit',
    'MIME-Version: 1.0',
];

// Umlaute im Betreff muessen kodiert werden, sonst kommen sie als Fragezeichen an.
$betreffKodiert = '=?UTF-8?B?' . base64_encode($titel) . '?=';

// Der fuenfte Parameter setzt den Umschlag-Absender, was gegen das Landen im
// Spam-Ordner hilft. Manche Hoster verbieten ihn — dann ohne ihn versuchen,
// statt die Anfrage verloren zu geben.
$erfolg = @mail(EMPFAENGER, $betreffKodiert, $text, implode("\r\n", $kopf),
                '-f' . ABSENDER);
if (!$erfolg) {
    $erfolg = @mail(EMPFAENGER, $betreffKodiert, $text, implode("\r\n", $kopf));
}

if (!$erfolg) {
    ende(500, ['ok' => false, 'fehler' => 'Versand fehlgeschlagen.']);
}

// --- Eingangsbestaetigung an den Absender --------------------------------
// Erst nach dem erfolgreichen Versand an uns: Ohne unsere Mail gibt es nichts
// zu bestaetigen. Ein Fehlschlag hier laesst die Antwort unberuehrt — die
// Anfrage ist angekommen, das ist das Entscheidende.
if (BESTAETIGUNG) {
    $texte = [
        'de' => [
            'Ihre Anfrage bei ORCA Restoration',
            $name !== '' ? 'Guten Tag ' . $name . ',' : 'Guten Tag,',
            'vielen Dank für Ihre Nachricht. Sie ist bei uns eingegangen, und '
            . 'wir melden uns in Kürze bei Ihnen.',
            'Ihre Nachricht im Wortlaut:',
            'Diese Bestätigung wurde automatisch erzeugt. Sie können auf diese '
            . 'E-Mail antworten, sie erreicht uns direkt.',
        ],
        'en' => [
            'Your enquiry to ORCA Restoration',
            $name !== '' ? 'Dear ' . $name . ',' : 'Hello,',
            'thank you for your message. We have received it and will get back '
            . 'to you shortly.',
            'Your message:',
            'This confirmation was generated automatically. You can reply to '
            . 'this email; it reaches us directly.',
        ],
        'fr' => [
            'Votre demande auprès d’ORCA Restoration',
            $name !== '' ? 'Bonjour ' . $name . ',' : 'Bonjour,',
            'merci pour votre message. Nous l’avons bien reçu et reviendrons '
            . 'vers vous dans les plus brefs délais.',
            'Votre message :',
            'Cette confirmation a été générée automatiquement. Vous pouvez '
            . 'répondre à cet e-mail, il nous parvient directement.',
        ],
    ];
    $t = $texte[$sprache];

    $btext = $t[1] . "\n\n" . $t[2] . "\n\n"
           . $t[3] . "\n"
           . str_repeat('-', 40) . "\n"
           . $nachricht . "\n"
           . str_repeat('-', 40) . "\n\n"
           . $t[4] . "\n\n"
           . "ORCA Restoration GmbH\n"
           . "Robert-Bosch-Str. 4, 71735 Eberdingen\n"
           . "Telefon 07042 374 32 67\n"
           . EMPFAENGER . "\n";

    $bkopf = [
        'From: ORCA Restoration GmbH <' . ABSENDER . '>',
        // Antworten auf die Bestaetigung sollen bei uns landen, nicht bei der
        // unbeaufsichtigten Absenderadresse des Formulars.
        'Reply-To: ' . EMPFAENGER,
        'Content-Type: text/plain; charset=UTF-8',
        'Content-Transfer-Encoding: 8bit',
        'MIME-Version: 1.0',
        // Automatische Antworten sollen darauf nicht wieder antworten.
        'Auto-Submitted: auto-replied',
    ];

    $bbetreff = '=?UTF-8?B?' . base64_encode($t[0]) . '?=';

    if (!@mail($email, $bbetreff, $btext, implode("\r\n", $bkopf),
               '-f' . ABSENDER)) {
        @mail($email, $bbetreff, $btext, implode("\r\n", $bkopf));
    }
}

ende(200, ['ok' => true]);
