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


INSTAGRAM_URL = "https://www.instagram.com/orca.restoration/"

# Instagram-Glyphe als eingebettetes SVG — kein externer Abruf, und die Farbe
# erbt über currentColor die des umgebenden Links. Sämtliche Darstellung läuft
# über style statt über Attribute wie stroke-width: Attribute mit Bindestrich
# verwirft die rendernde Schicht der Seite teilweise (dasselbe Verhalten wie
# beim muted-Attribut der Videos).
INSTA_ICON = (
    '<svg viewBox=\\"0 0 24 24\\" width=\\"14\\" height=\\"14\\" '
    'style=\\"vertical-align:-2px; margin-right:6px; fill:none; '
    'stroke:currentColor; stroke-width:1.9\\">'
    '<rect x=\\"3\\" y=\\"3\\" width=\\"18\\" height=\\"18\\" rx=\\"5\\"><\\u002Frect>'
    '<circle cx=\\"12\\" cy=\\"12\\" r=\\"4\\"><\\u002Fcircle>'
    '<circle cx=\\"17.2\\" cy=\\"6.8\\" r=\\"1.15\\" '
    'style=\\"fill:currentColor; stroke:none\\"><\\u002Fcircle>'
    '<\\u002Fsvg>'
)


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
        # Strasse unter den WCAG-Mindestkontrast von 3:1 — ursprünglich bei
        # 9,1 Prozent der Pixel. Mit 0.42 an der 60-Prozent-Marke bleibt über
        # alle Einzelbilder kein Pixel darunter. Werte von 0.32 bis 0.38
        # liessen einen Restanteil von 0,07 bis 0,001 Prozent stehen; die
        # zusätzliche Abdunklung bis 0.42 beträgt nur rund einen Prozentpunkt.
        old_grad = ('background:linear-gradient(180deg, rgba(10,9,7,0.45) 0%, '
                    'rgba(10,9,7,0.05) 32%, rgba(10,9,7,0.15) 60%, '
                    'rgba(10,9,7,0.78) 100%)')
        new_grad = ('background:linear-gradient(180deg, rgba(10,9,7,0.45) 0%, '
                    'rgba(10,9,7,0.05) 32%, rgba(10,9,7,0.42) 60%, '
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

    # --- Handy: Responsive-Regeln ersetzen --------------------------------
    old_media = (
        '@media (max-width: 820px) {\\n'
        '    header { padding: 16px 22px !important; flex-wrap: wrap !important; gap: 10px 18px !important; }\\n'
        '    nav { gap: 14px !important; font-size: 10px !important; }\\n'
        '    section { padding-left: 22px !important; padding-right: 22px !important; }\\n'
        '    footer { padding-left: 22px !important; padding-right: 22px !important; gap: 14px 26px !important; }\\n'
        '    [style*=\\"grid-template-columns\\"] { grid-template-columns: 1fr !important; }\\n'
        '    [style*=\\"repeat(4\\"] { grid-template-columns: 1fr 1fr !important; }\\n'
        '    [style*=\\"repeat(5\\"] { grid-template-columns: 1fr 1fr !important; }\\n'
        '    [style*=\\"left:56px\\"] { left: 22px !important; right: 22px !important; }\\n'
        '    h1 { white-space: normal !important; }\\n'
        '    #orca-cookie-banner { padding: 16px 18px !important; }\\n'
        '  }')
    new_media = (
        '@media (max-width: 820px) {\\n'
        '    header { padding: 16px 22px !important; flex-wrap: wrap !important; gap: 10px 18px !important; }\\n'
        '    /* flex-shrink muss mit aufgehoben werden: Die Navigation traegt\\n'
        '       inline flex-shrink:0 und behielt dadurch ihre volle Breite,\\n'
        '       obwohl Umbruch erlaubt war — auf 360px lief sie 27px hinaus. */\\n'
        '    nav { gap: 12px 14px !important; font-size: 10px !important;\\n'
        '          flex-wrap: wrap !important; white-space: normal !important;\\n'
        '          flex-shrink: 1 !important; min-width: 0 !important; }\\n'
        '    section { padding-left: 22px !important; padding-right: 22px !important; }\\n'
        '    footer { padding-left: 22px !important; padding-right: 22px !important; gap: 14px 26px !important; }\\n'
        '    /* Alle Raster einspaltig. minmax(0,1fr) statt 1fr, weil 1fr fuer\\n'
        '       minmax(auto,1fr) steht und die Spalte damit nicht unter die\\n'
        '       Mindestbreite ihres Inhalts schrumpfen kann. Genau daran liefen\\n'
        '       die Portraits der Fuehrungskraefte 470px breit in ein 346px\\n'
        '       schmales Raster, und die Kennzahlen landeten in zwei ungleichen\\n'
        '       Spalten statt mittig. */\\n'
        '    [style*=\\"grid-template-columns\\"] { grid-template-columns: minmax(0, 1fr) !important; }\\n'
        '    /* Inhalte in einspaltigen Rastern mittig und nie breiter als die Zelle. */\\n'
        '    image-slot, video, img { max-width: 100% !important; }\\n'
        '    /* Hero: Text und Schaltflaeche an den Seitenrand. */\\n'
        '    .orca-hero-text { left: 22px !important; right: 22px !important; }\\n'
        '    /* Hero flacher. Ein 16:9-Video wird in einem hochformatigen Fenster\\n'
        '       bei object-fit:cover stark seitlich beschnitten — bei 100vh gehen\\n'
        '       rund drei Viertel der Bildbreite verloren. Flacher heisst mehr\\n'
        '       sichtbare Breite und weniger Videowand. */\\n'
        '    /* Kein Seitenabstand am Hero: Er ist randlos, und weil er\\n'
        '       width:100% ohne border-box traegt, kaemen die 22px oben drauf —\\n'
        '       die Seite liess sich dadurch 44px seitlich verschieben. */\\n'
        '    .orca-hero { height: 74vh !important; min-height: 500px !important;\\n'
        '                 padding-left: 0 !important; padding-right: 0 !important; }\\n'
        '    /* Innenabstand des Kennzahlen-Rasters zuruecknehmen, sonst bleiben\\n'
        '       von 346px nur 234px fuer den Inhalt. */\\n'
        '    .orca-stats { padding-left: 0 !important; padding-right: 0 !important; }\\n'
        '    /* Detailansicht der Projekte. Einspaltig stehen Bild und Text\\n'
        '       untereinander und werden zusammen hoeher als der Dialog. Der\\n'
        '       hatte overflow:hidden, die Textspalte zugleich eine eigene\\n'
        '       Scrollflaeche mit max-height:86vh — der Text war dadurch\\n'
        '       abgeschnitten und nicht erreichbar. Jetzt scrollt der Dialog\\n'
        '       als Ganzes, und die Textspalte gibt ihre Scrollflaeche ab. */\\n'
        '    .orca-modal-overlay { padding: 14px !important; align-items: flex-start !important; }\\n'
        '    .orca-modal { max-height: calc(100vh - 28px) !important;\\n'
        '                  overflow-y: auto !important;\\n'
        '                  -webkit-overflow-scrolling: touch !important; }\\n'
        '    .orca-modal-media { min-height: 210px !important; }\\n'
        '    .orca-modal-text { padding: 26px 22px 34px !important;\\n'
        '                       overflow-y: visible !important; max-height: none !important; }\\n'
        '    /* Schliessen bleibt sichtbar, statt beim Scrollen wegzuwandern. */\\n'
        '    .orca-modal-close { position: fixed !important; top: 22px !important;\\n'
        '                        right: 22px !important; z-index: 2 !important; }\\n'
        '    h1 { white-space: normal !important; }\\n'
        '    #orca-cookie-banner { padding: 16px 18px !important; }\\n'
        '  }')
    sub_once(old_media, new_media, "Responsive-Regeln")

    # Klassen an die vier Bausteine der Projekt-Detailansicht.
    if page == "Projects.html":
        sub_once('<div sc-camel-on-click=\\"{{ closeProject }}\\" '
                 'style=\\"position:fixed; inset:0; z-index:60;',
                 '<div sc-camel-on-click=\\"{{ closeProject }}\\" '
                 'class=\\"orca-modal-overlay\\" '
                 'style=\\"position:fixed; inset:0; z-index:60;',
                 "Klasse am Dialog-Hintergrund")
        sub_once('<div sc-camel-on-click=\\"{{ stop }}\\" '
                 'style=\\"position:relative; width:100%; max-width:1080px;',
                 '<div sc-camel-on-click=\\"{{ stop }}\\" class=\\"orca-modal\\" '
                 'style=\\"position:relative; width:100%; max-width:1080px;',
                 "Klasse am Dialog")
        sub_once('<div style=\\"position:relative; min-height:340px; '
                 'background:{{ line }};\\">',
                 '<div class=\\"orca-modal-media\\" style=\\"position:relative; '
                 'min-height:340px; background:{{ line }};\\">',
                 "Klasse am Medienblock")
        sub_once('<div style=\\"padding:48px 44px; overflow-y:auto; '
                 'max-height:86vh;\\">',
                 '<div class=\\"orca-modal-text\\" style=\\"padding:48px 44px; '
                 'overflow-y:auto; max-height:86vh;\\">',
                 "Klasse am Textblock")
        sub_once('border-radius:50%;\\" class=\\"link-fade\\"',
                 'border-radius:50%;\\" class=\\"link-fade orca-modal-close\\"',
                 "Klasse an der Schliess-Schaltflaeche")

    # Klassen fuer die beiden Hero-Elemente, damit die Regeln oben nicht auf
    # Zeichenketten im style-Attribut angewiesen sind: Die rendernde Schicht
    # schreibt diese um ("left: 56px" mit Leerzeichen), wodurch der bisherige
    # Selektor [style*="left:56px"] nie gegriffen hat.
    if page == "index.html":
        sub_once('<section style=\\"position:relative; width:100%; height:100vh; '
                 'min-height:600px; overflow:hidden; background:#14130f;\\">',
                 '<section class=\\"orca-hero\\" style=\\"position:relative; '
                 'width:100%; height:100vh; min-height:600px; overflow:hidden; '
                 'background:#14130f;\\">',
                 "Klasse am Hero-Abschnitt")
        sub_once('<div style=\\"position:absolute; left:56px; right:56px; '
                 'bottom:158px; max-width:720px;\\">',
                 '<div class=\\"orca-hero-text\\" style=\\"position:absolute; '
                 'left:56px; right:56px; bottom:158px; max-width:720px;\\">',
                 "Klasse am Hero-Text")
        sub_once('<div style=\\"max-width:1200px; margin:0 auto; '
                 'padding:70px 56px; box-sizing:border-box; display:grid; '
                 'grid-template-columns:repeat(4,minmax(0,1fr)); gap:32px;\\">',
                 '<div class=\\"orca-stats\\" style=\\"max-width:1200px; '
                 'margin:0 auto; padding:70px 56px; box-sizing:border-box; '
                 'display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); '
                 'gap:32px;\\">',
                 "Klasse am Kennzahlen-Raster")

    # --- Instagram im Footer jeder Seite ----------------------------------
    old_foot = ('<a href=\\"mailto:info@orca.gmbh\\" class=\\"link-fade\\" '
                'style=\\"color:{{ accent }};\\" style-hover=\\"color:{{ text }}\\">'
                'info@orca.gmbh<\\u002Fa><\\u002Fdiv>')
    new_foot = ('<a href=\\"mailto:info@orca.gmbh\\" class=\\"link-fade\\" '
                'style=\\"color:{{ accent }};\\" style-hover=\\"color:{{ text }}\\">'
                'info@orca.gmbh<\\u002Fa> · '
                f'<a href=\\"{INSTAGRAM_URL}\\" target=\\"_blank\\" '
                'rel=\\"noopener noreferrer\\" class=\\"link-fade\\" '
                'style=\\"color:{{ accent }};\\" style-hover=\\"color:{{ text }}\\">'
                f'{INSTA_ICON}Instagram<\\u002Fa><\\u002Fdiv>')
    sub_once(old_foot, new_foot, "Instagram im Footer")

    # --- Instagram zusätzlich in den Kontaktblock --------------------------
    # Dort sucht man Kontaktwege, also gehört das Profil dorthin. Angehängt
    # nach den Öffnungszeiten, im gleichen Aufbau wie die übrigen Einträge.
    # "Instagram" braucht keine Übersetzung.
    if page == "Contact.html":
        old_hours = ('<div style=\\"font-size:15px; line-height:1.7; '
                     'color:{{ textMuted }};\\">{{ t.hoursValue }}<\\u002Fdiv>\\n'
                     '      <\\u002Fdiv>')
        new_hours = (old_hours +
                     '\\n      <div>\\n'
                     '        <div style=\\"font-size:11px; letter-spacing:0.14em; '
                     'text-transform:uppercase; color:{{ accent }}; '
                     'margin-bottom:8px;\\">Instagram<\\u002Fdiv>\\n'
                     f'        <a href=\\"{INSTAGRAM_URL}\\" target=\\"_blank\\" '
                     'rel=\\"noopener noreferrer\\" style=\\"font-size:15px; '
                     'color:{{ text }};\\" style-hover=\\"color:{{ accent }}\\">'
                     f'{INSTA_ICON}@orca.restoration<\\u002Fa>\\n'
                     '      <\\u002Fdiv>')
        sub_once(old_hours, new_hours, "Instagram im Kontaktblock")

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
