#!/usr/bin/env python3
"""Erzeugt die englischen und französischen Sprachfassungen aus den deutschen Seiten.

Die deutschen Seiten im Repo-Wurzelverzeichnis sind die einzige Quelle. Dieses
Skript legt en/ und fr/ neu an und passt zusätzlich die deutschen Seiten an
(Sprachumschalter, hreflang, lang-Attribut).

Aufruf aus dem Repo-Wurzelverzeichnis:

    python3 tools/build-langs.py

Das Skript erwartet unveränderte Exporte: Es bricht ab, wenn eine Seite schon
umgebaut wurde, statt doppelt zu patchen. Nach einem Neu-Export aus dem Editor
kann es also ohne Weiteres wieder laufen.

Beim Domainwechsel genügt es, BASE anzupassen und das Skript erneut zu starten.
"""

import re
import shutil
import sys
from pathlib import Path

BASE = "https://orca-restoration.com"
LANGS = ("de", "en", "fr")
PAGES = ("index.html", "About.html", "Projects.html", "Contact.html", "Legal.html")

OG_LOCALE = {"de": "de_DE", "en": "en_GB", "fr": "fr_FR"}

# Bild für JSON-LD und Vorschau. Das ursprüngliche hero.jpg existierte nicht.
SCHEMA_IMAGE = f"{BASE}/images/porsche-917-15.jpg"

# Kurzbeschreibung im JSON-LD-Block, je Sprache.
SCHEMA_DESC = {
    "de": "Spezialist für die originalgetreue Restauration historischer "
          "Porsche-Rennsportprototypen.",
    "en": "Specialists in the faithful restoration of historic Porsche "
          "racing prototypes.",
    "fr": "Spécialiste de la restauration fidèle de prototypes de course "
          "Porsche historiques.",
}

# Titel und Meta-Beschreibung je Seite und Sprache. Die deutschen Werte müssen
# exakt dem Export entsprechen, sie dienen als Suchmuster.
META = {
    "index.html": {
        "de": ("ORCA Restoration GmbH – Restauration historischer Porsche-Rennwagen",
               "Spezialist für die originalgetreue Restauration historischer "
               "Porsche-Rennsportprototypen. 3D-Messtechnik, einzigartige Datenbank, "
               "über 15 Jahre Erfahrung in Eberdingen."),
        "en": ("ORCA Restoration GmbH – Restoration of Historic Porsche Race Cars",
               "Specialists in the faithful restoration of historic Porsche racing "
               "prototypes. 3D measurement technology, a unique database and over "
               "15 years of experience in Eberdingen, Germany."),
        "fr": ("ORCA Restoration GmbH – Restauration de Porsche de course historiques",
               "Spécialiste de la restauration fidèle de prototypes de course Porsche "
               "historiques. Métrologie 3D, base de données unique, plus de 15 ans "
               "d'expérience à Eberdingen, en Allemagne."),
    },
    "About.html": {
        "de": ("Über uns – ORCA Restoration GmbH | Handwerk &amp; Präzision",
               "Unser Team vereint traditionelles Handwerk mit modernster "
               "3D-Technologie zur Rekonstruktion historischer Porsche-Fahrzeuge. "
               "Lernen Sie die Menschen hinter ORCA kennen."),
        "en": ("About Us – ORCA Restoration GmbH | Craftsmanship &amp; Precision",
               "Our team combines traditional craftsmanship with state-of-the-art 3D "
               "technology to reconstruct historic Porsche vehicles. Meet the people "
               "behind ORCA."),
        "fr": ("À propos – ORCA Restoration GmbH | Savoir-faire et précision",
               "Notre équipe associe l'artisanat traditionnel aux technologies 3D les "
               "plus modernes pour reconstruire des Porsche historiques. Découvrez "
               "les personnes derrière ORCA."),
    },
    "Projects.html": {
        "de": ("Projekte – Restaurierte Porsche-Rennwagen | ORCA Restoration",
               "Ausgewählte Restaurationen: Porsche 910, 906 Carrera 6, 550 Spyder, "
               "917 und 911 R – originalgetreu wiederhergestellt von ORCA "
               "Restoration GmbH."),
        "en": ("Projects – Restored Porsche Race Cars | ORCA Restoration",
               "Selected restorations: Porsche 910, 906 Carrera 6, 550 Spyder, 917 "
               "and 911 R – faithfully rebuilt by ORCA Restoration GmbH."),
        "fr": ("Projets – Porsche de course restaurées | ORCA Restoration",
               "Restaurations sélectionnées : Porsche 910, 906 Carrera 6, 550 Spyder, "
               "917 et 911 R – reconstruites fidèlement par ORCA Restoration GmbH."),
    },
    "Contact.html": {
        "de": ("Kontakt – ORCA Restoration GmbH, Eberdingen",
               "Sprechen Sie mit uns über Ihr Restaurationsprojekt. "
               "Robert-Bosch-Str. 4, 71735 Eberdingen. Telefon 07042 374 32 67, "
               "info@orca.gmbh."),
        "en": ("Contact – ORCA Restoration GmbH, Eberdingen",
               "Talk to us about your restoration project. Robert-Bosch-Str. 4, "
               "71735 Eberdingen, Germany. Phone +49 7042 374 32 67, "
               "info@orca.gmbh."),
        "fr": ("Contact – ORCA Restoration GmbH, Eberdingen",
               "Parlons de votre projet de restauration. Robert-Bosch-Str. 4, "
               "71735 Eberdingen, Allemagne. Téléphone +49 7042 374 32 67, "
               "info@orca.gmbh."),
    },
    "Legal.html": {
        "de": ("Impressum &amp; Datenschutz – ORCA Restoration GmbH",
               "Impressum und Datenschutzerklärung der ORCA Restoration GmbH, "
               "Robert-Bosch-Str. 4, 71735 Eberdingen."),
        "en": ("Legal Notice &amp; Privacy Policy – ORCA Restoration GmbH",
               "Legal notice and privacy policy of ORCA Restoration GmbH, "
               "Robert-Bosch-Str. 4, 71735 Eberdingen, Germany."),
        "fr": ("Mentions légales et confidentialité – ORCA Restoration GmbH",
               "Mentions légales et politique de confidentialité d'ORCA Restoration "
               "GmbH, Robert-Bosch-Str. 4, 71735 Eberdingen, Allemagne."),
    },
}


def url_for(lang: str, page: str) -> str:
    """Öffentliche Adresse einer Seite. Die Startseite läuft über den Ordner."""
    prefix = "" if lang == "de" else f"/{lang}"
    if page == "index.html":
        return f"{BASE}{prefix}/"
    return f"{BASE}{prefix}/{page}"


def switch_href(from_lang: str, to_lang: str, page: str) -> str:
    """Relativer Pfad vom Sprachumschalter zur Zielsprache derselben Seite."""
    if from_lang == to_lang:
        return f"./{page}"
    if from_lang == "de":
        return f"./{to_lang}/{page}"
    if to_lang == "de":
        return f"../{page}"
    return f"../{to_lang}/{page}"


# Die Rechtstexte (Impressum, Datenschutzerklärung) liegen nur auf Deutsch vor
# und sind für eine deutsche GmbH auch die verbindliche Fassung. Die Seite gibt
# es trotzdem in jedem Sprachordner, damit Besucher ihre Navigation behalten —
# sie verweist aber per canonical auf die deutsche Fassung, damit Google die
# drei Adressen zusammenfasst statt sie als doppelten Inhalt zu behandeln.
GERMAN_ONLY = ("Legal.html",)


def head_links(lang: str, page: str) -> str:
    """canonical und hreflang für den *äusseren* Head, als normales HTML.

    Nicht in den Vorlagen-Head: dort verwaltet die helmet-Mechanik der Seite
    die Tags selbst und entfernt Fremdes wieder. Der äussere Head ist zudem
    das, was Crawler ohne JavaScript sofort sehen.
    """
    if page in GERMAN_ONLY:
        # Nur ein Kanonisierungs-Hinweis, keine hreflang-Angaben: Die Seite
        # ist inhaltlich in allen Ordnern deutsch, widersprüchliche
        # Sprachsignale wären schlechter als keine.
        return f'\n<link rel="canonical" href="{url_for("de", page)}">'

    out = [f'<link rel="canonical" href="{url_for(lang, page)}">']
    for other in LANGS:
        out.append(f'<link rel="alternate" hreflang="{other}" '
                   f'href="{url_for(other, page)}">')
    out.append(f'<link rel="alternate" hreflang="x-default" '
               f'href="{url_for("de", page)}">')
    return "\n" + "\n".join(out)


def transform(src: str, lang: str, page: str) -> str:
    """Baut aus einer deutschen Seite die Fassung für die gewünschte Sprache."""
    s = src
    de_title, de_desc = META[page]["de"]
    title, desc = META[page][lang]

    def sub_once(old: str, new: str, what: str) -> None:
        nonlocal s
        n = s.count(old)
        if n != 1:
            raise SystemExit(
                f"{page} [{lang}]: {what} — {n} Treffer erwartet 1.\n"
                f"  Gesucht: {old[:110]}"
            )
        s = s.replace(old, new, 1)

    # --- Sprachzustand der Komponente -------------------------------------
    if lang != "de":
        sub_once("state = { lang: 'de'", f"state = {{ lang: '{lang}'",
                 "Sprachzustand")

    # --- Bildpfade: aus einem Unterordner liegt images/ eine Ebene höher ---
    if lang != "de":
        s = s.replace("'images/", "'../images/")
        # Dasselbe für das Video im Wurzelverzeichnis.
        s = s.replace('src=\\"./restauration.mp4\\"',
                      'src=\\"../restauration.mp4\\"')

    # --- Sprachumschalter: aus Klick-Handlern werden echte Links ----------
    # Die Farbvariable heisst je Seite anders (langDeLight auf der Startseite
    # mit dunklem Header, langDeColor auf den Unterseiten), daher per Muster.
    for code, target in (("De", "de"), ("En", "en"), ("Fr", "fr")):
        pattern = (
            r'<span sc-camel-on-click=\\"\{\{ setLang' + code + r' \}\}\\" '
            r'class=\\"lang-switch\\" style=\\"cursor:pointer; '
            r'color:\{\{ (lang' + code + r'\w+) \}\};\\">'
            + target.upper() + r'<\\u002Fspan>'
        )
        found = re.findall(pattern, s)
        if len(found) != 1:
            raise SystemExit(
                f"{page} [{lang}]: Sprachumschalter {target.upper()} — "
                f"{len(found)} Treffer erwartet 1."
            )
        colour_var = found[0]
        new = (f'<a href=\\"{switch_href(lang, target, page)}\\" '
               f'class=\\"lang-switch\\" style=\\"'
               f'color:{{{{ {colour_var} }}}};\\">{target.upper()}'
               f'<\\u002Fa>')
        s = re.sub(pattern, lambda _m, n=new: n, s, count=1)

    # --- Hero: Standbild durch Video ersetzen ------------------------------
    # hero.mp4 ist die gedrehte Fassung des Hochformat-Clips (die Aufnahme lag
    # um 90 Grad gekippt in der Datei). Poster sorgt dafür, dass sofort ein
    # Bild steht, während die 5 MB laden.
    if page == "index.html":
        old_slot = ('<image-slot id=\\"hero-main\\" shape=\\"rect\\" '
                    'placeholder=\\"Porsche Rennwagen – Titelbild (später Video)\\" '
                    'style=\\"position:absolute; inset:0; width:100%; height:100%;\\" '
                    'src=\\"e264a4e1-5ee2-422f-9bcf-5a715b5d17b3\\"><\\u002Fimage-slot>')
        pre = "../" if lang != "de" else "./"
        new_video = (
            f'<video autoplay=\\"true\\" muted=\\"true\\" loop=\\"true\\" '
            f'playsinline=\\"true\\" preload=\\"auto\\" '
            f'poster=\\"{pre}hero-poster.jpg\\" '
            f'style=\\"position:absolute; inset:0; width:100%; height:100%; '
            f'object-fit:cover; display:block;\\">'
            f'<source src=\\"{pre}hero.mp4\\" type=\\"video/mp4\\">'
            f'<\\u002Fvideo>')
        sub_once(old_slot, new_video, "Hero-Bildplatz")

        # Der Verlauf über dem Hero war für ein ruhiges Standbild ausgelegt.
        # Über dem Video fiel die Überschrift bei hellem Himmel und heller
        # Strasse teils unter den WCAG-Mindestkontrast von 3:1 (9,1 % der
        # Pixel). Mit 0.32 an der 60-Prozent-Marke bleibt kein Pixel darunter,
        # das Bild wird dabei nur rund 5 Prozentpunkte stärker abgedunkelt.
        old_grad = ('background:linear-gradient(180deg, rgba(10,9,7,0.45) 0%, '
                    'rgba(10,9,7,0.05) 32%, rgba(10,9,7,0.15) 60%, '
                    'rgba(10,9,7,0.78) 100%)')
        new_grad = ('background:linear-gradient(180deg, rgba(10,9,7,0.45) 0%, '
                    'rgba(10,9,7,0.05) 32%, rgba(10,9,7,0.32) 60%, '
                    'rgba(10,9,7,0.82) 100%)')
        sub_once(old_grad, new_grad, "Hero-Verlauf")

    # Hinweis: Hier stand kurzzeitig ein Listener, der bei der
    # Systemeinstellung "Bewegung reduzieren" beide Videos anhielt. Er ist
    # entfernt worden, weil er die Videos für alle stillstehen liess, die
    # diese Einstellung gesetzt haben — auch für den Betreiber selbst. Falls
    # das Thema wieder aufgegriffen wird, gehört die Entscheidung dem
    # Besucher: eine sichtbare Schaltfläche zum Anhalten statt automatisch
    # unterdrücktem Abspielen.

    # --- Video im Abschnitt "Restauration in Bewegung" --------------------
    # Der 16:9-Rahmen des Entwurfs bleibt unverändert: restauration.mp4 wurde
    # auf 720x404 zugeschnitten (die Instagram-Fassung hatte oben und unten je
    # 437 Zeilen schwarzen Rand im Bild) und füllt ihn damit passend aus.
    if page == "index.html":
        # Autoplay verlangt muted, sonst blockiert der Browser. controls bleibt
        # bewusst erhalten: Der Clip läuft in Schleife, und automatisch
        # bewegte Inhalte brauchen eine Möglichkeit zum Anhalten.
        # Die Attributwerte müssen "true" lauten — ein leerer Wert gilt der
        # rendernden Schicht als falsch und das Attribut entfällt.
        # poster verwies auf eine Datei, die es nicht gibt.
        old_vid = ('<video controls=\\"\\" playsinline=\\"\\" preload=\\"metadata\\" '
                   'poster=\\"./restauration-poster.jpg\\"')
        new_vid = ('<video controls=\\"true\\" autoplay=\\"true\\" muted=\\"true\\" '
                   'loop=\\"true\\" playsinline=\\"true\\" preload=\\"auto\\"')
        sub_once(old_vid, new_vid, "video-Tag")

    # --- Startseiten-Links auf die Ordnerform bringen ---------------------
    # Logo, "Start" in der Navigation und der Sprachumschalter zeigten auf
    # ./index.html. Der Server liefert die Startseite auch unter dem Ordner
    # aus, dann steht in der Adresszeile nur die Domain statt .../index.html.
    s = re.sub(r'href=\\"((?:\.\./|\./)(?:en/|fr/)?)index\.html\\"',
               r'href=\\"\1\\"', s)

    # --- Kopfbereich der Vorlage -----------------------------------------
    sub_once(f"<title>{de_title}<\\u002Ftitle>",
             f"<title>{title}<\\u002Ftitle>",
             "Titel im Template")
    sub_once(f'<meta name=\\"description\\" content=\\"{de_desc}\\">',
             f'<meta name=\\"description\\" content=\\"{desc}\\">',
             "Meta-Beschreibung")
    sub_once(f'<meta property=\\"og:title\\" content=\\"{de_title}\\">',
             f'<meta property=\\"og:title\\" content=\\"{title}\\">',
             "og:title")
    sub_once(f'<meta property=\\"og:description\\" content=\\"{de_desc}\\">',
             f'<meta property=\\"og:description\\" content=\\"{desc}\\">',
             "og:description")
    sub_once('<meta property=\\"og:locale\\" content=\\"de_DE\\">',
             f'<meta property=\\"og:locale\\" content=\\"{OG_LOCALE[lang]}\\">',
             "og:locale")

    # --- JSON-LD: Adresse und Beschreibung je Sprache --------------------
    sub_once(f'\\"description\\":\\"{SCHEMA_DESC["de"]}\\"',
             f'\\"description\\":\\"{SCHEMA_DESC[lang]}\\"',
             "JSON-LD description")
    sub_once(f'\\"image\\":\\"{BASE}/hero.jpg\\"',
             f'\\"image\\":\\"{SCHEMA_IMAGE}\\"',
             "JSON-LD image")
    sub_once(f'\\"url\\":\\"{BASE}/\\"',
             f'\\"url\\":\\"{url_for(lang, page)}\\"',
             "JSON-LD url")

    # --- lang-Attribut: im ausgelieferten HTML und in der Vorlage ---------
    # Zwei Vorkommen mit UNTERSCHIEDLICHEM Escaping: Das erste ist echtes HTML
    # des ausgelieferten Dokuments und braucht normale Anfuehrungszeichen. Das
    # zweite steckt in der Vorlage, die als JavaScript-String in der Datei
    # liegt — dort muessen die Anfuehrungszeichen escaped sein, sonst bricht
    # der String und die Seite rendert nicht mehr.
    if s.count("<html>") != 2:
        raise SystemExit(f"{page} [{lang}]: {s.count('<html>')} <html>-Tags, "
                         "erwartet 2 (aeusseres Dokument + Vorlage)")
    first = s.index("<html>")
    s = s[:first] + f'<html lang="{lang}">' + s[first + len("<html>"):]
    second = s.index("<html>")
    s = s[:second] + f'<html lang=\\"{lang}\\">' + s[second + len("<html>"):]

    # --- Aeusseres Dokument: Titel plus canonical/hreflang ----------------
    # Das ist, was Crawler ohne JavaScript sofort lesen.
    sub_once(f"<title>{de_title}</title>",
             f"<title>{title}</title>{head_links(lang, page)}",
             "Titel des aeusseren Dokuments")

    return s


def main() -> None:
    root = Path.cwd()
    missing = [p for p in PAGES if not (root / p).exists()]
    if missing:
        raise SystemExit(f"Im aktuellen Verzeichnis fehlen: {', '.join(missing)}")

    originals = {}
    for page in PAGES:
        text = (root / page).read_text(encoding="utf-8")
        if "hreflang" in text or "lang-switch\\\" style=\\\"color" in text:
            raise SystemExit(
                f"{page} wurde offenbar schon umgebaut (hreflang gefunden).\n"
                "Das Skript erwartet unveraenderte Exporte."
            )
        originals[page] = text

    for lang in LANGS:
        target_dir = root if lang == "de" else root / lang
        if lang != "de":
            if target_dir.exists():
                shutil.rmtree(target_dir)
            target_dir.mkdir()
        for page in PAGES:
            out = transform(originals[page], lang, page)
            (target_dir / page).write_text(out, encoding="utf-8")
        print(f"  {lang}: {len(PAGES)} Seiten -> "
              f"{target_dir.relative_to(root) if lang != 'de' else '.'}")

    # --- sitemap.xml ------------------------------------------------------
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
             ' xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    # Die hreflang-Angaben laufen bewusst über die Sitemap: Im Vorlagen-Head
    # würde die helmet-Mechanik der Seite sie wieder entfernen, und die Sitemap
    # ist für hreflang ein von Google offiziell unterstützter Weg.
    count = 0
    for lang in LANGS:
        for page in PAGES:
            # Nur-deutsche Seiten (Rechtstexte) stehen einmal in der Sitemap.
            if page in GERMAN_ONLY and lang != "de":
                continue
            lines.append("  <url>")
            lines.append(f"    <loc>{url_for(lang, page)}</loc>")
            count += 1
            if page not in GERMAN_ONLY:
                for other in LANGS:
                    lines.append(
                        f'    <xhtml:link rel="alternate" hreflang="{other}" '
                        f'href="{url_for(other, page)}"/>'
                    )
                lines.append(
                    f'    <xhtml:link rel="alternate" hreflang="x-default" '
                    f'href="{url_for("de", page)}"/>'
                )
            lines.append("  </url>")
    lines.append("</urlset>")
    (root / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  sitemap.xml: {count} Adressen")

    (root / "robots.txt").write_text(
        "User-agent: *\n"
        "Allow: /\n"
        f"\nSitemap: {BASE}/sitemap.xml\n",
        encoding="utf-8",
    )
    print("  robots.txt")


if __name__ == "__main__":
    sys.exit(main())
