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

BASE = "https://orca.gmbh"

# Die Adresse, die im Export selbst steht. Sie dient nur als Suchmuster und
# darf nicht mitgeaendert werden, wenn BASE auf eine neue Domain zeigt —
# sonst findet das Skript die Stellen im Export nicht mehr.
EXPORT_BASE = "https://orca-restoration.com"
LANGS = ("de", "en", "fr")
PAGES = ("index.html", "About.html", "Projects.html", "Contact.html", "Legal.html")

OG_LOCALE = {"de": "de_DE", "en": "en_GB", "fr": "fr_FR"}

# Beschriftung der Menue-Schaltflaeche fuer Screenreader.
MENU_LABEL = {"de": "Menü", "en": "Menu", "fr": "Menu"}

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

# Annahmestelle für das Kontaktformular. FormSubmit braucht keine Anmeldung:
# Die erste Absendung löst eine Bestätigungsmail an die Adresse aus, erst nach
# einem Klick darauf werden Nachrichten weitergeleitet. Nach der Freischaltung
# lässt sich hier die dort angezeigte Kennung statt der Adresse eintragen, dann
# steht die Mailadresse nicht mehr im Quelltext und wird nicht abgegriffen.
# Ein Wechsel des Anbieters betrifft nur diese eine Zeile.
FORM_ENDPOINT = "https://formsubmit.co/ajax/info@orca.gmbh"

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


# Datenschutzerklärung. Jede Aussage hier ist am fertigen Stand nachgemessen:
# ohne Zustimmung stellt keine der fünf Seiten eine Verbindung nach draussen her
# (Schriften liegen eingebettet vor), die Karte lädt erst nach Zustimmung, und
# die Entscheidung liegt im lokalen Speicher unter orca-cookie-consent.
# Bewusst keine Angabe erfundener Firmendaten: Betreiber und Anschrift von
# FormSubmit liessen sich nicht verifizieren, daher nur Dienst und Sitzland.
DATENSCHUTZ = [
    ("Verantwortlicher", [
        "Verantwortlich für die Datenverarbeitung auf dieser Website ist die "
        "ORCA Restoration GmbH, Robert-Bosch-Str. 4, 71735 Eberdingen, "
        "Telefon 07042 374 32 67, E-Mail info@orca.gmbh.",
    ]),
    ("Hosting und Server-Logdateien", [
        "Diese Website wird bei GitHub Pages gehostet, einem Dienst der "
        "GitHub, Inc. mit Sitz in den USA. Beim Aufruf der Seiten erfasst der "
        "Server automatisch Zugriffsdaten, darunter die IP-Adresse, Datum und "
        "Uhrzeit des Zugriffs, die aufgerufene Seite sowie Angaben zu Browser "
        "und Betriebssystem.",
        "Diese Verarbeitung ist technisch erforderlich, um die Website "
        "bereitzustellen und ihren Betrieb abzusichern. Rechtsgrundlage ist "
        "Art. 6 Abs. 1 lit. f DSGVO. Eine Übermittlung in die USA ist dabei "
        "nicht ausgeschlossen.",
    ]),
    ("Keine Analyse- und Trackingdienste", [
        "Diese Website verwendet keine Analyse-, Werbe- oder Trackingdienste. "
        "Es werden keine Cookies zu Analysezwecken gesetzt und keine Profile "
        "gebildet.",
        "Schriftarten und alle weiteren Gestaltungselemente sind lokal "
        "eingebunden. Beim Aufruf der Seiten wird deshalb keine Verbindung zu "
        "externen Anbietern hergestellt — mit Ausnahme der Karte auf der "
        "Kontaktseite, die ausschliesslich nach Ihrer Zustimmung geladen wird.",
    ]),
    ("Speicherung Ihrer Entscheidung über externe Inhalte", [
        "Ihre Entscheidung über externe Inhalte speichern wir im lokalen "
        "Speicher Ihres Browsers unter der Bezeichnung „orca-cookie-consent“. "
        "Vermerkt wird allein, ob Sie zugestimmt oder abgelehnt haben; "
        "personenbezogene Daten werden dabei nicht übertragen.",
        "Der Eintrag ist erforderlich, damit Ihre Auswahl beim nächsten Besuch "
        "erhalten bleibt. Sie können ihn jederzeit über die Einstellungen "
        "Ihres Browsers löschen; danach werden Sie erneut gefragt.",
    ]),
    ("Google Maps", [
        "Auf der Kontaktseite binden wir eine Karte von Google Maps ein. Die "
        "Karte wird erst geladen, nachdem Sie ausdrücklich zugestimmt haben. "
        "Vorher wird keine Verbindung zu Google hergestellt.",
        "Mit Ihrer Zustimmung werden Ihre IP-Adresse und weitere "
        "Verbindungsdaten an Google übermittelt. Anbieter für Nutzer im "
        "Europäischen Wirtschaftsraum ist die Google Ireland Limited, Dublin, "
        "Irland; eine Übermittlung in die USA ist dabei möglich. "
        "Rechtsgrundlage ist Ihre Einwilligung nach Art. 6 Abs. 1 lit. a "
        "DSGVO. Sie können die Einwilligung jederzeit widerrufen, indem Sie "
        "den gespeicherten Eintrag in Ihrem Browser löschen.",
    ]),
    ("Kontaktformular", [
        "Wenn Sie das Kontaktformular nutzen, verarbeiten wir die von Ihnen "
        "eingegebenen Angaben: Name, E-Mail-Adresse, Fahrzeug und Ihre "
        "Nachricht. Diese Daten dienen ausschliesslich der Bearbeitung Ihrer "
        "Anfrage. E-Mail-Adresse und Nachricht sind erforderlich, damit wir "
        "antworten können; Name und Fahrzeug sind freiwillig.",
        "Rechtsgrundlage ist Art. 6 Abs. 1 lit. b DSGVO, soweit Ihre Anfrage "
        "der Vorbereitung eines Vertrags dient, im Übrigen Art. 6 Abs. 1 "
        "lit. f DSGVO.",
        "Für die Übermittlung nutzen wir den Dienst FormSubmit "
        "(formsubmit.co), einen Anbieter mit Sitz in den USA. Ihre Eingaben "
        "werden dort verarbeitet und an unsere E-Mail-Adresse weitergeleitet; "
        "damit ist eine Übermittlung in die USA verbunden. Wenn Sie das "
        "vermeiden möchten, erreichen Sie uns jederzeit direkt per E-Mail an "
        "info@orca.gmbh oder telefonisch.",
        "Wir speichern Ihre Anfrage, bis sie abschliessend bearbeitet ist, und "
        "löschen sie anschliessend, soweit keine gesetzlichen "
        "Aufbewahrungsfristen entgegenstehen.",
    ]),
    ("Ihre Rechte", [
        "Sie haben das Recht auf Auskunft über die zu Ihrer Person "
        "gespeicherten Daten, auf Berichtigung unrichtiger Daten, auf Löschung "
        "und auf Einschränkung der Verarbeitung. Ausserdem können Sie der "
        "Verarbeitung widersprechen und die Übertragung Ihrer Daten in einem "
        "gängigen Format verlangen. Eine erteilte Einwilligung können Sie "
        "jederzeit widerrufen.",
        "Wenden Sie sich dazu an die oben genannten Kontaktdaten. Unabhängig "
        "davon steht Ihnen ein Beschwerderecht bei einer Aufsichtsbehörde zu. "
        "Für uns zuständig ist der Landesbeauftragte für den Datenschutz und "
        "die Informationsfreiheit Baden-Württemberg.",
    ]),
    ("Keine automatisierte Entscheidungsfindung", [
        "Eine automatisierte Entscheidungsfindung einschliesslich Profiling "
        "findet nicht statt.",
    ]),
]


def datenschutz_markup() -> str:
    """Erzeugt die Abschnitte im Escaping und Stil der gebauten Seite."""
    h3 = ('<h3 style=\\"font-family:\'Cormorant Garamond\',serif; '
          'font-weight:400; font-size:22px; margin:34px 0 12px;\\">')
    p = ('<p style=\\"font-size:15px; line-height:1.8; color:{{ textMuted }}; '
         'margin:0 0 16px;\\">')
    teile = []
    for titel, absaetze in DATENSCHUTZ:
        teile.append(f'{h3}{titel}<\\u002Fh3>')
        for a in absaetze:
            teile.append(f'{p}{a}<\\u002Fp>')
    return '\\n    ' + '\\n    '.join(teile)


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
        # Die aktuelle Sprache wird markiert, damit sie sich nicht nur durch
        # Transparenz von den anderen abhebt — bei 10px Schrift kaum zu sehen.
        klasse = "lang-switch is-active" if target == lang else "lang-switch"
        new = (f'<a href=\\"{switch_href(lang, target, page)}\\" '
               f'class=\\"{klasse}\\" style=\\"'
               f'color:{{{{ {colour_var} }}}};\\">{target.upper()}'
               f'<\\u002Fa>')
        s = re.sub(pattern, lambda _m, n=new: n, s, count=1)

    # --- Handy: Menuepunkte in ein Burger-Menue --------------------------
    # Vorher standen vier Menuepunkte und drei Sprachkuerzel gemeinsam in der
    # Kopfzeile. Auf dem Handy brach das in zwei Reihen um und wirkte gedraengt;
    # im Franzoesischen wurde daraus sogar eine zweite Spalte. Die Punkte
    # wandern deshalb in ein aufklappbares Menue, die Sprachen bleiben sichtbar
    # und werden groesser.
    #
    # Dazu bekommen die vier Punkte einen gemeinsamen Rahmen (aus dem auf dem
    # Handy die Klappflaeche wird), der Sprachblock eine Klasse und die
    # Navigation eine Schaltflaeche. Auf dem Desktop aendert sich nichts: Der
    # Rahmen traegt dieselben Flex-Angaben wie die Navigation, die Schaltflaeche
    # steht auf display:none.
    nav_open = re.search(
        r'<nav style=\\"display:flex; align-items:center; gap:24px;[^"]*\\">', s)
    if nav_open is None:
        raise SystemExit(f"{page} [{lang}]: Navigation nicht gefunden")
    sub_once(nav_open.group(0),
             nav_open.group(0) + '\\n      <div class=\\"orca-navlinks\\" '
             'style=\\"display:flex; align-items:center; gap:24px;\\">',
             "Rahmen um die Menuepunkte")

    lang_box = re.search(
        r'<div style=\\"display:flex; align-items:center; gap:8px; '
        r'border-left:1px solid ([^;]+); padding-left:20px; '
        r'flex-shrink:0;\\">', s)
    if lang_box is None:
        raise SystemExit(f"{page} [{lang}]: Sprachblock nicht gefunden")
    sub_once(lang_box.group(0),
             '<\\u002Fdiv>\\n      '
             + lang_box.group(0).replace('<div style=',
                                         '<div class=\\"orca-langs\\" style=', 1),
             "Klasse am Sprachblock")

    # Die Balken liegen als drei leere Elemente in der Schaltflaeche und erben
    # ueber currentColor die Schriftfarbe der Kopfzeile — auf der Startseite
    # hell ueber dem Video, auf den Unterseiten dunkel auf hellem Grund.
    burger_colour = "#f8f5ef" if page == "index.html" else "{{ text }}"
    bar = ('<span style=\\"display:block; width:22px; height:2px; '
           'background:currentColor;\\"><\\u002Fspan>')
    sub_once('<\\u002Fnav>',
             '  <button type=\\"button\\" class=\\"orca-burger\\" '
             f'aria-label=\\"{MENU_LABEL[lang]}\\" aria-expanded=\\"false\\" '
             'style=\\"display:none; flex-direction:column; '
             'justify-content:center; align-items:center; gap:5px; '
             'width:40px; height:40px; padding:0; margin:0; border:0; '
             f'background:none; color:{burger_colour}; cursor:pointer; '
             'flex-shrink:0;\\">'
             + bar * 3 +
             '<\\u002Fbutton>\\n    <\\u002Fnav>',
             "Menue-Schaltflaeche")

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

    # --- Datenschutzerklaerung ausbauen ------------------------------------
    # Die bisherige Fassung nannte nur allgemeine Grundsaetze und ein
    # Auskunftsrecht. Nicht erwaehnt waren Hosting, die Karte auf der
    # Kontaktseite, die Speicherung der Zustimmung und das Kontaktformular —
    # also gerade die Verarbeitungen, die tatsaechlich stattfinden. Der
    # bisherige Abschnitt zu den Rechten geht im neuen Abschnitt "Ihre Rechte"
    # auf und wird deshalb ersetzt.
    if page == "Legal.html":
        alt = ('<h3 style=\\"font-family:\'Cormorant Garamond\',serif; '
               'font-weight:400; font-size:22px; margin:34px 0 12px;\\">'
               'Recht auf Auskunft, Löschung, Sperrung<\\u002Fh3>\\n'
               '    <p style=\\"font-size:15px; line-height:1.8; '
               'color:{{ textMuted }}; margin:0 0 16px;\\">Sie haben jederzeit '
               'das Recht auf unentgeltliche Auskunft über Ihre gespeicherten '
               'personenbezogenen Daten, deren Herkunft und Empfänger und den '
               'Zweck der Datenverarbeitung sowie ein Recht auf Berichtigung, '
               'Sperrung oder Löschung dieser Daten. Hierzu sowie zu weiteren '
               'Fragen zum Thema personenbezogene Daten können Sie sich '
               'jederzeit unter der im Impressum angegebenen Adresse an uns '
               'wenden.<\\u002Fp>')
        sub_once(alt, datenschutz_markup().strip('\\n '), "Datenschutzerklärung")

    if page == "About.html":
        sub_once('<div style=\\"display:grid; '
                 'grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:48px; '
                 'max-width:820px; margin:0 auto;\\">',
                 '<div class=\\"orca-leads\\" style=\\"display:grid; '
                 'grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:48px; '
                 'max-width:820px; margin:0 auto;\\">',
                 "Klasse am Raster der Geschaeftsfuehrung")

    # --- Kontaktformular funktionsfaehig machen ---------------------------
    # Das Formular war reine Attrappe: kein <form>, keine name-Attribute, der
    # Knopf ist type="button" ohne Handler. Wer etwas eintippte und auf Senden
    # klickte, loeste nichts aus — die Anfrage war verloren.
    # Geloest ueber eine vorbefuellte E-Mail: kein Drittanbieter, damit keine
    # Datenweitergabe und kein Eintrag in der Datenschutzerklaerung noetig.
    # Der Listener haengt am Dokument, damit er unabhaengig davon greift, wann
    # der Knopf gerendert wird. Zeilenumbrueche ueber fromCharCode, um
    # Escaping ueber die drei Ebenen hinweg zu vermeiden.
    old_boot = 'h.classList.add("__orca-boot");'
    new_boot = (
        'h.classList.add("__orca-boot");'
        'document.addEventListener("click",function(ev){'
        'var b=ev.target&&ev.target.closest?ev.target.closest(".orca-send"):null;'
        'if(!b)return;ev.preventDefault();'
        'var g=function(c){var el=document.querySelector("."+c);'
        'return el&&el.value?el.value.trim():"";};'
        'var W={'
        'de:["Name","E-Mail","Fahrzeug","Nachricht","Bitte E-Mail und Nachricht angeben.",'
        '"Wird gesendet \\u2026","Vielen Dank, Ihre Nachricht ist unterwegs.",'
        '"Senden nicht m\\u00f6glich. Bitte schreiben Sie an info@orca.gmbh.",'
        '"Anfrage \\u00fcber die Website"],'
        'en:["Name","Email","Vehicle","Message","Please provide your email and a message.",'
        '"Sending \\u2026","Thank you, your message is on its way.",'
        '"Sending failed. Please write to info@orca.gmbh.",'
        '"Enquiry via the website"],'
        'fr:["Nom","E-mail","V\\u00e9hicule","Message",'
        '"Merci d\\u2019indiquer votre e-mail et un message.",'
        '"Envoi \\u2026","Merci, votre message est en route.",'
        '"\\u00c9chec de l\\u2019envoi. Merci d\\u2019\\u00e9crire \\u00e0 info@orca.gmbh.",'
        '"Demande via le site"]};'
        'var L=(document.documentElement.getAttribute("lang")||"de").substring(0,2);'
        'var t=W[L]||W.de;'
        'var st=document.querySelector(".orca-status");'
        'var sag=function(s,ok){if(!st)return;st.textContent=s;'
        'st.style.color=ok===false?"#7a2331":"";};'
        'var n=g("orca-f-name"),m=g("orca-f-email"),v=g("orca-f-vehicle"),x=g("orca-f-message");'
        'if(!m||!x){sag(t[4],false);'
        'var f=document.querySelector(m?".orca-f-message":".orca-f-email");if(f)f.focus();return;}'
        'var hp=document.querySelector(".orca-f-hp");'
        'if(hp&&hp.value){return;}'
        'var d={};d[t[0]]=n;d[t[1]]=m;d[t[2]]=v;d[t[3]]=x;'
        'd._subject=t[8]+(v?" \\u2013 "+v:"");d._captcha="false";d._template="table";'
        'b.disabled=true;sag(t[5],true);'
        f'fetch("{FORM_ENDPOINT}",{{method:"POST",'
        'headers:{"Content-Type":"application/json","Accept":"application/json"},'
        'body:JSON.stringify(d)}).then(function(r){'
        'if(!r.ok)throw new Error("HTTP "+r.status);return r.json();}).then(function(){'
        'sag(t[6],true);'
        '["orca-f-name","orca-f-email","orca-f-vehicle","orca-f-message"].forEach(function(c){'
        'var el=document.querySelector("."+c);if(el)el.value="";});'
        'b.disabled=false;}).catch(function(){'
        # Faellt der Dienst aus, geht die Anfrage nicht verloren: Der Hinweis
        # nennt die Adresse, und der Knopf wird wieder bedienbar.
        'sag(t[7],false);b.disabled=false;});'
        '},true);'
        # Burger-Menue: Ein Klick auf die Schaltflaeche klappt die Menuepunkte
        # auf, ein Klick daneben schliesst sie wieder. Der Listener haengt am
        # Dokument, damit er unabhaengig vom Zeitpunkt des Renderns greift.
        'document.addEventListener("click",function(ev){'
        'var nv=document.querySelector("nav");if(!nv)return;'
        'var t=ev.target;if(!t||!t.closest)return;'
        'var b=t.closest(".orca-burger");'
        'if(b){ev.preventDefault();'
        'var o=nv.classList.toggle("orca-open");'
        'b.setAttribute("aria-expanded",o?"true":"false");return;}'
        'if(nv.classList.contains("orca-open")&&!t.closest("nav")){'
        'nv.classList.remove("orca-open");'
        'var s=nv.querySelector(".orca-burger");'
        'if(s)s.setAttribute("aria-expanded","false");}'
        '},true);'
        'document.addEventListener("keydown",function(ev){'
        'if(ev.key!=="Escape")return;'
        'var nv=document.querySelector("nav");'
        'if(!nv||!nv.classList.contains("orca-open"))return;'
        'nv.classList.remove("orca-open");'
        'var s=nv.querySelector(".orca-burger");'
        'if(s){s.setAttribute("aria-expanded","false");s.focus();}'
        '});')
    sub_once(old_boot, new_boot, "Kontaktformular verdrahten")

    if page == "Contact.html":
        for cls, feld in (('type=\\"text\\" placeholder=\\"{{ t.fName }}\\"', 'orca-f-name'),
                          ('type=\\"email\\" placeholder=\\"{{ t.fEmail }}\\"', 'orca-f-email'),
                          ('type=\\"text\\" placeholder=\\"{{ t.fVehicle }}\\"', 'orca-f-vehicle')):
            sub_once(f'<input class=\\"field\\" {cls}>',
                     f'<input class=\\"field {feld}\\" {cls}>',
                     f"Klasse am Feld {feld}")
        sub_once('<textarea class=\\"field\\" rows=\\"4\\" '
                 'placeholder=\\"{{ t.fMessage }}\\"',
                 '<textarea class=\\"field orca-f-message\\" rows=\\"4\\" '
                 'placeholder=\\"{{ t.fMessage }}\\"',
                 "Klasse am Nachrichtenfeld")
        # Honigtopf gegen Spam: Ein für Menschen unsichtbares Feld, das nur
        # automatische Ausfüller bedienen. Ist es gefüllt, wird nicht gesendet.
        sub_once('<button type=\\"button\\" style=\\"margin-top:10px;',
                 '<input class=\\"orca-f-hp\\" type=\\"text\\" tabindex=\\"-1\\" '
                 'autocomplete=\\"off\\" aria-hidden=\\"true\\" '
                 'style=\\"position:absolute; left:-9999px; width:1px; height:1px; '
                 'opacity:0;\\">\\n      '
                 '<button type=\\"button\\" class=\\"orca-send\\" '
                 'style=\\"margin-top:10px;',
                 "Honigtopf und Klasse am Senden-Knopf")
        # Rueckmeldung unter dem Knopf, damit der Absender weiss, was passiert.
        sub_once('{{ t.fSend }}<\\u002Fbutton>',
                 '{{ t.fSend }}<\\u002Fbutton>\\n      '
                 '<div class=\\"orca-status\\" role=\\"status\\" '
                 'style=\\"font-size:14px; line-height:1.6; min-height:22px; '
                 'color:{{ textMuted }};\\"><\\u002Fdiv>',
                 "Statusmeldung unter dem Knopf")

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
    # Klappflaeche und Trennlinien richten sich nach der Kopfzeile: Auf der
    # Startseite liegt sie ueber dem Video und ist dunkel, auf den Unterseiten
    # hell wie der Seitenhintergrund.
    # Bewusst als Zahlenwert und nicht als {{ bg }}/{{ line }}: Im Stylesheet
    # werden diese Platzhalter nicht ersetzt. Auf Legal.html bleiben sie sogar
    # unveraendert stehen, auf den uebrigen Seiten wird der Text erst nach dem
    # Auswerten der Regeln getauscht — die Angabe faellt in beiden Faellen
    # ersatzlos weg (dieselbe Ursache liegt hinter dem toten
    # "body { background: {{ bg }} }" im Export). In Attributen greift die
    # Ersetzung dagegen, deshalb steht {{ text }} unten am Balken. Die Werte
    # entsprechen dem Farbschema des Entwurfs; sie muessen nachgezogen werden,
    # falls sich dieses aendert.
    panel_bg = "rgba(10,9,7,0.96)" if page == "index.html" else "#f6f3ee"
    panel_line = ("rgba(248,245,239,0.18)" if page == "index.html"
                  else "#ddd7cc")
    new_media = (
        '@media (max-width: 820px) {\\n'
        '    /* Kopfzeile bleibt einzeilig: Logo links, Sprachen und\\n'
        '       Menue-Schaltflaeche rechts. Der Umbruch von vorher entfaellt,\\n'
        '       weil die Menuepunkte in die Klappflaeche gewandert sind. */\\n'
        '    header { padding: 14px 22px !important; flex-wrap: nowrap !important;\\n'
        '             gap: 14px !important; }\\n'
        '    /* Bezugspunkt fuer die Klappflaeche. Bewusst ohne !important: Die\\n'
        '       Kopfzeile der Startseite traegt inline position:absolute und\\n'
        '       liegt dadurch weiter ueber dem Video — mit !important wuerde\\n'
        '       sie in den Textfluss zurueckfallen und den Hero nach unten\\n'
        '       schieben. Ein Bezugspunkt ist sie als absolute ohnehin. */\\n'
        '    header { position: relative; }\\n'
        '    /* Der Firmenname darf schrumpfen und umbrechen, damit rechts\\n'
        '       genug Platz bleibt; inline stand dort nowrap und\\n'
        '       flex-shrink:0. */\\n'
        '    header > a.logo-link { font-size: 14px !important;\\n'
        '                          white-space: normal !important;\\n'
        '                          line-height: 1.25 !important;\\n'
        '                          flex-shrink: 1 !important;\\n'
        '                          min-width: 0 !important; }\\n'
        '    nav { gap: 8px !important; flex-wrap: nowrap !important;\\n'
        '          flex-shrink: 0 !important; }\\n'
        '    .orca-navlinks { display: none !important; }\\n'
        '    .orca-burger { display: flex !important; }\\n'
        '    /* Ohne die Menuepunkte daneben trennt der Strich nichts mehr. */\\n'
        '    .orca-langs { gap: 2px !important; border-left: 0 !important;\\n'
        '                  padding-left: 0 !important; }\\n'
        '    /* Aufgeklappt: volle Breite unter der Kopfzeile. */\\n'
        f'    nav.orca-open .orca-navlinks {{ display: flex !important;\\n'
        '                                   flex-direction: column !important;\\n'
        '                                   align-items: stretch !important;\\n'
        '                                   gap: 0 !important;\\n'
        '                                   position: absolute;\\n'
        '                                   top: 100%; left: 0; right: 0;\\n'
        '                                   z-index: 30;\\n'
        f'                                   background: {panel_bg};\\n'
        f'                                   border-top: 1px solid {panel_line};\\n'
        f'                                   border-bottom: 1px solid {panel_line};\\n'
        '                                   padding: 6px 22px 12px;\\n'
        '                                   box-sizing: border-box; }\\n'
        '    nav.orca-open .orca-navlinks a.nav-link {\\n'
        '        min-height: 50px !important; font-size: 12px !important;\\n'
        '        border-bottom: 0 !important; padding: 0 0 0 14px !important; }\\n'
        '    /* Die aktuelle Seite ist im Export durch border-bottom im\\n'
        '       style-Attribut markiert. Untereinander wirkt eine Unterkante\\n'
        '       wie eine Trennlinie, deshalb wandert die Markierung an die\\n'
        '       linke Seite. Der Selektor greift auf den Namen der\\n'
        '       Eigenschaft zu, den die rendernde Schicht unveraendert\\n'
        '       uebernimmt — anders als den Wert, in den sie Leerzeichen\\n'
        '       einfuegt. */\\n'
        '    nav.orca-open .orca-navlinks a.nav-link[style*=\\"border-bottom\\"] {\\n'
        '        border-left: 2px solid currentColor !important;\\n'
        '        padding-left: 12px !important; }\\n'
        '    section { padding-left: 22px !important; padding-right: 22px !important; }\\n'
        '    footer { padding-left: 22px !important; padding-right: 22px !important; gap: 14px 26px !important; }\\n'
        '    /* Alle mehrspaltigen Raster untereinander. Bewusst als Flex-Spalte\\n'
        '       und nicht als einspaltiges Raster: Die Zeilenhoehe wurde dort\\n'
        '       allein aus dem Bild abgeleitet, Name und Rolle darunter zaehlten\\n'
        '       nicht mit und ragten 70px in die naechste Zeile — die Rolle des\\n'
        '       ersten Geschaeftsfuehrers verschwand hinter dem zweiten Bild.\\n'
        '       Zugleich wurde aspect-ratio gegen die alte, breitere Spalte\\n'
        '       aufgeloest, wodurch die Bilder 265 statt 195px hoch waren. Als\\n'
        '       Flex-Spalte stimmen beide Werte, und gap bleibt erhalten — bei\\n'
        '       display:block waeren die Abstaende verloren gegangen. */\\n'
        '    [style*=\\"grid-template-columns\\"] { display: flex !important; flex-direction: column !important; }\\n'
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
        '    /* Gescrollt wird die Flaeche hinter dem Dialog, nicht der Dialog\\n'
        '       selbst. Damit entfaellt jede Hoehenangabe in vh — und genau\\n'
        '       daran scheiterte der erste Versuch: Auf dem iPhone meint 100vh\\n'
        '       das Fenster ohne Adressleiste, ist also groesser als das\\n'
        '       tatsaechlich Sichtbare. Der Dialog passte rechnerisch in seine\\n'
        '       Begrenzung, hatte deshalb nichts zu scrollen, ragte aber unter\\n'
        '       die Browserleiste. Die Hintergrundflaeche ist position:fixed und\\n'
        '       damit immer genau so hoch wie der sichtbare Bereich. */\\n'
        '    .orca-modal-overlay { padding: 14px !important; align-items: flex-start !important;\\n'
        '                          overflow-y: auto !important;\\n'
        '                          -webkit-overflow-scrolling: touch !important; }\\n'
        '    .orca-modal { max-height: none !important; overflow: visible !important; }\\n'
        '    .orca-modal-media { min-height: 210px !important; }\\n'
        '    .orca-modal-text { padding: 26px 22px 34px !important;\\n'
        '                       overflow-y: visible !important; max-height: none !important; }\\n'
        '    /* Schliessen bleibt sichtbar, statt beim Scrollen wegzuwandern. */\\n'
        '    .orca-modal-close { position: fixed !important; top: 22px !important;\\n'
        '                        right: 22px !important; z-index: 2 !important; }\\n'
        '    /* Antippflaechen. Die Sprachumschalter waren 15x14 Pixel gross —\\n'
        '       empfohlen sind mindestens 44x44 Punkte, darunter trifft man sie\\n'
        '       mit dem Finger nicht verlaesslich. 40x40 plus Abstand kommt dem\\n'
        '       nahe und laesst neben dem Firmennamen noch Platz; die Schrift\\n'
        '       waechst von 10 auf 14 Pixel. */\\n'
        '    nav a.lang-switch { min-width: 40px !important; min-height: 40px !important;\\n'
        '                        display: inline-flex !important;\\n'
        '                        align-items: center !important;\\n'
        '                        justify-content: center !important;\\n'
        '                        font-size: 14px !important; }\\n'
        '    nav a.nav-link { display: inline-flex !important;\\n'
        '                     align-items: center !important; }\\n'
        '    /* Die Schraegstriche zwischen den Sprachen entfallen: Mit 40px\\n'
        '       breiten Feldern sind die Kuerzel ohnehin klar getrennt, und die\\n'
        '       Striche wirkten zwischen den groesseren Flaechen verloren. */\\n'
        '    nav a.lang-switch + span { display: none !important; }\\n'
        '    /* Die Markierung der aktuellen Sprache sitzt am Text und nicht am\\n'
        '       unteren Rand der 40 Pixel hohen Antippflaeche — dort stand sie\\n'
        '       13 Pixel unter der Schrift und wirkte losgeloest. */\\n'
        '    a.lang-switch.is-active { border-bottom: 0 !important;\\n'
        '                              padding-bottom: 0 !important;\\n'
        '                              text-decoration: underline !important;\\n'
        '                              text-underline-offset: 5px !important; }\\n'
        '    h1 { white-space: normal !important; }\\n'
        '    #orca-cookie-banner { padding: 16px 18px !important; }\\n'
        '  }\\n'
        '  /* Die aktive Sprache wird unterstrichen wie der aktive Menuepunkt.\\n'
        '     Vorher unterschied sie sich nur durch Transparenz, was bei dieser\\n'
        '     Schriftgroesse kaum zu erkennen ist. */\\n'
        '  a.lang-switch.is-active { border-bottom: 1px solid currentColor;\\n'
        '                            padding-bottom: 2px; }\\n'
        '  /* Reserve fuer die Kopfzeile im mittleren Bereich. Die franzoesische\\n'
        '     Navigation ist mit 440px die breiteste (deutsch 431, englisch 411),\\n'
        '     bei 821px Fensterbreite blieben ihr nur 15px Reserve. Das genuegt,\\n'
        '     damit sie umbricht, solange die Schrift noch laedt und die\\n'
        '     Ersatzschrift breiter ausfaellt. Mit kleinerem Abstand sind es\\n'
        '     rund 40px, und alle drei Sprachen verhalten sich gleich. */\\n'
        '  @media (min-width: 821px) and (max-width: 1080px) {\\n'
        '    header { padding-left: 32px !important; padding-right: 32px !important; }\\n'
        '    nav { gap: 16px !important; }\\n'
        '  }\\n'
        '  /* Geschaeftsfuehrung: Die Rasterzeile wurde allein aus dem Bild\\n'
        '     abgeleitet, Name und Rolle darunter zaehlten nicht mit und ragten\\n'
        '     70px heraus — auf dem Handy hinter das naechste Bild, auf dem\\n'
        '     Desktop in den Abstand darunter. Mit align-items:start wird die\\n'
        '     Zelle nicht mehr auf die falsch berechnete Zeilenhoehe gedehnt,\\n'
        '     sondern richtet sich nach ihrem Inhalt; das Bild loest dadurch\\n'
        '     auch sein Seitenverhaeltnis korrekt auf (217 statt 287px).\\n'
        '     Bewusst nur hier und nicht fuer alle Raster: andere richten ihren\\n'
        '     Inhalt absichtlich mittig aus. */\\n'
        '  .orca-leads { align-items: start; }\\n'
        '  @media (max-width: 820px) {\\n'
        '    /* Als Flex-Spalte muessen die Zellen wieder volle Breite haben. */\\n'
        '    .orca-leads { align-items: stretch !important; }\\n'
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
    sub_once(f'\\"image\\":\\"{EXPORT_BASE}/hero.jpg\\"',
             f'\\"image\\":\\"{SCHEMA_IMAGE}\\"',
             "JSON-LD image")
    sub_once(f'\\"url\\":\\"{EXPORT_BASE}/\\"',
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
