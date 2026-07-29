/**
 * Rendert jede erzeugte Seite einmal vor und legt das Ergebnis als echtes HTML
 * in die Datei.
 *
 * Warum: Der Inhalt der Seiten entsteht erst, wenn der Browser ein rund 690 KB
 * grosses Paket entpackt und die Vorlage zusammensetzt. Ohne JavaScript sind
 * nur 34 Zeichen zu sehen ("ORCA RESTORATION GmbH Unpacking..."). Google
 * fuehrt JavaScript aus und findet die Texte, aber verzoegert und weniger
 * verlaesslich als bei fertigem HTML; Bing, LinkedIn und die meisten
 * KI-Abholer tun es gar nicht.
 *
 * Wie: Der vorgerenderte Baum wird an den Anfang des Body gestellt, die
 * Stilbloecke der fertigen Seite in den Kopf. Das Ladeskript ersetzt beim
 * Aufruf ohnehin das gesamte Dokument — fuer Besucher aendert sich also
 * nichts, ausser dass sie statt "Unpacking..." sofort die Seite sehen.
 *
 * Bilder aus dem Paket tragen im fertigen Baum eine blob-Adresse, die nur im
 * laufenden Browser gilt. Solche Verweise werden im vorgerenderten Teil
 * entfernt, damit dort keine toten Bilder stehen; der Alt-Text bleibt als
 * Beschriftung erhalten.
 *
 * Aufruf aus dem Repo-Wurzelverzeichnis, nach build-langs.py:
 *   NODE_PATH=$(npm root -g) node tools/prerender.js
 */

const fs = require('fs');
const path = require('path');
const http = require('http');
const { chromium } = require('playwright');

const WURZEL = process.cwd();
const PORT = 8123;
const MARKE = '<!-- orca-prerender -->';

const TYPEN = {
  '.html': 'text/html; charset=utf-8', '.jpg': 'image/jpeg', '.png': 'image/png',
  '.svg': 'image/svg+xml', '.mp4': 'video/mp4', '.xml': 'application/xml',
  '.txt': 'text/plain; charset=utf-8', '.webp': 'image/webp',
};

function server() {
  return http.createServer((req, res) => {
    let p = decodeURIComponent(req.url.split('?')[0]);
    if (p.endsWith('/')) p += 'index.html';
    const datei = path.join(WURZEL, p);
    if (!datei.startsWith(WURZEL) || !fs.existsSync(datei) || fs.statSync(datei).isDirectory()) {
      res.writeHead(404); res.end('not found'); return;
    }
    res.writeHead(200, { 'Content-Type': TYPEN[path.extname(datei)] || 'application/octet-stream' });
    fs.createReadStream(datei).pipe(res);
  });
}

function seiten() {
  const out = [];
  for (const l of ['', 'en/', 'fr/']) {
    for (const s of ['', 'about/', 'projects/', 'contact/', 'legal/']) out.push(l + s);
  }
  return out;
}

(async () => {
  const srv = server();
  await new Promise(r => srv.listen(PORT, r));
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const seite = await browser.newPage({ viewport: { width: 1280, height: 900 } });

  let fertig = 0;
  for (const s of seiten()) {
    const url = `http://127.0.0.1:${PORT}/${s}`;
    await seite.goto(url, { waitUntil: 'load' });
    await seite.waitForFunction(() => document.body.innerText.length > 400, null, { timeout: 15000 });
    await seite.waitForTimeout(700);

    const teile = await seite.evaluate(() => {
      // Bilder mit blob-Adresse verlieren ihren Verweis: Die Adresse gilt nur
      // im laufenden Browser und waere in der Datei ein toter Link.
      document.querySelectorAll('img[src^="blob:"]').forEach(i => i.removeAttribute('src'));
      document.querySelectorAll('[style*="blob:"]').forEach(e => {
        e.setAttribute('style', e.getAttribute('style').replace(/url\(["']?blob:[^)]*\)/g, 'none'));
      });
      // Videos brauchen im vorgerenderten Teil nicht zu laden.
      document.querySelectorAll('video').forEach(v => { v.removeAttribute('autoplay'); v.setAttribute('preload', 'none'); });

      // Die Schriften liegen als Daten in den @font-face-Regeln und machen
      // allein 1058 KB aus. Im Vorabbau sind sie ueberfluessig: Er ist nur
      // kurz zu sehen, und sobald das Paket entpackt ist, bringt die Seite
      // ihre Schriften selbst mit. Ersatzschriften genuegen dafuer.
      const stile = [...document.querySelectorAll('style')]
        .map(e => e.textContent)
        .join('\n')
        .replace(/@font-face\s*\{[^}]*\}/g, '');

      // Stil- und Skriptbloecke aus dem Koerper nehmen: Die Stile stehen schon
      // oben im Kopf, die Skripte gehoeren zum laufenden Programm und haben im
      // Vorabbau nichts zu suchen.
      const kopie = document.body.cloneNode(true);
      kopie.querySelectorAll('style, script, link[rel=stylesheet]').forEach(e => e.remove());

      return { stile, koerper: kopie.innerHTML };
    });

    const datei = path.join(WURZEL, s, 'index.html');
    let text = fs.readFileSync(datei, 'utf8');
    if (text.includes(MARKE)) { console.error(`  ${s || '/'}: enthaelt schon einen Vorabbau`); process.exitCode = 1; continue; }

    // Stile in den Kopf, damit der vorgerenderte Teil aussieht wie die Seite
    // und nicht als unformatierter Text aufblitzt.
    //
    // Dazu eine Regel nur fuer den Fall ohne JavaScript: Das aeussere Dokument
    // ist als zentrierter Ladebildschirm angelegt (dunkelgruener Grund, ein
    // Schriftzug in der Mitte). Ohne diese Umkehrung laege der vorgerenderte
    // Inhalt zwar im Dokument, waere aber hinter dem Ladebildschirm nicht zu
    // sehen. Mit JavaScript aendert die Regel nichts, weil das Ladeskript
    // das gesamte Dokument ohnehin ersetzt.
    text = text.replace('</head>',
      `<style>${teile.stile}</style>\n`
      + '<noscript><style>\n'
      + '  body { display: block !important; background: #f6f3ee !important;\n'
      + '         min-height: 0 !important; }\n'
      + '  #__bundler_thumbnail, #__bundler_loading { display: none !important; }\n'
      + '</style></noscript>\n</head>');
    // Inhalt an den Anfang des Body. Das Ladeskript ersetzt gleich darauf das
    // gesamte Dokument, deshalb stoert er dort nicht.
    text = text.replace(/<body([^>]*)>/,
      (m, attr) => `<body${attr}>\n${MARKE}\n<div id="orca-prerender">\n${teile.koerper}\n</div>\n${MARKE}`);

    fs.writeFileSync(datei, text);
    fertig++;
    const kb = Math.round(Buffer.byteLength(text) / 1024);
    console.log(`  ${(s || '/').padEnd(16)} vorgerendert  (${kb} KB)`);
  }

  await browser.close();
  srv.close();
  console.log(`  ${fertig} Seiten vorgerendert`);
})();
