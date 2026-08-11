#!/usr/bin/env python3
"""Erzeugt die englischen und französischen Sprachfassungen aus den deutschen Seiten.

Die deutschen Seiten im Repo-Wurzelverzeichnis sind die einzige Quelle. Dieses
Skript legt en/ und fr/ neu an und passt zusätzlich die deutschen Seiten an
(Sprachumschalter, hreflang, lang-Attribut).

Aufruf aus dem Repo-Wurzelverzeichnis, in dieser Reihenfolge:

    python3 tools/build-langs.py
    NODE_PATH=$(npm root -g) node tools/prerender.js

Der zweite Schritt rendert jede erzeugte Seite einmal vor und legt das Ergebnis
als echtes HTML in die Datei. Ohne ihn sehen Crawler ohne JavaScript nur den
Ladehinweis. Er ist nicht optional, wenn die Seiten gefunden werden sollen.

Das Skript erwartet unveränderte Exporte: Es bricht ab, wenn eine Seite schon
umgebaut wurde, statt doppelt zu patchen. Nach einem Neu-Export aus dem Editor
kann es also ohne Weiteres wieder laufen.

Beim Domainwechsel genügt es, BASE anzupassen und das Skript erneut zu starten.
"""

import json
import re
import shutil
import sys
from pathlib import Path

BASE = "https://www.orca.gmbh"

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

# Annahmestelle für das Kontaktformular: ein eigenes PHP-Skript auf dem
# Strato-Webspace (kontakt.php, liegt unter tools/ als Vorlage). Es nimmt die
# Eingaben an, schickt sie an info@orca.gmbh und bestätigt dem Absender den
# Eingang. Damit ist kein Dritter mehr beteiligt — vorher lief die Übermittlung
# über FormSubmit in den USA, ohne Auftragsverarbeitungsvertrag.
# Die Website liegt auf GitHub Pages unter www.orca.gmbh, das Skript bei Strato
# unter orca.gmbh; deshalb setzt es die nötigen CORS-Kopfzeilen.
# Warum diese Aufteilung: Das kostenlose Zertifikat des Strato-Pakets
# (SSL Basic) gilt nur für orca.gmbh und die www-Schreibweise, nicht für
# beliebige Subdomains — unter formular.orca.gmbh scheiterte schon der
# Verbindungsaufbau (ERR_SSL_VERSION_OR_CIPHER_MISMATCH). Und ein Verzeichnis
# lässt Strato einem Namen nur zuweisen, wenn dieser KEINEN eigenen A-Eintrag
# hat; www erbt ohne eigenen Eintrag aber die Adresse der Hauptdomain. Damit
# blieb für die Annahmestelle nur die Hauptdomain selbst: Sie zeigt auf den
# Webspace, und genau für sie gilt das Zertifikat. Die Website wandert dafür
# auf www, wofür GitHub sein eigenes Zertifikat ausstellt.
# Die .htaccess leitet auf orca.gmbh alles außer kontakt.php auf www um
# (tools/htaccess-www).
FORM_ENDPOINT = "https://orca.gmbh/kontakt.php"

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
# Das Kontaktformular lief zunaechst ueber FormSubmit in den USA; Betreiber und
# Anschrift liessen sich nicht verifizieren und ein Auftragsverarbeitungsvertrag
# war nicht zu bekommen. Es laeuft jetzt ueber kontakt.php auf eigenem Webspace.
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
        "Die Übermittlung läuft über unseren eigenen Webspace bei der STRATO "
        "AG, Otto-Ostrowski-Str. 7, 10249 Berlin, die uns als "
        "Auftragsverarbeiterin Server in Deutschland bereitstellt. Ein "
        "Dienstleister ausserhalb der Europäischen Union ist daran nicht "
        "beteiligt. Beim Absenden werden neben Ihren Angaben Ihre IP-Adresse "
        "und der Zeitpunkt kurzzeitig gespeichert, um Massenzusendungen zu "
        "begrenzen; diese Angaben werden nach einer Stunde gelöscht.",
        "An die von Ihnen angegebene Adresse senden wir eine automatische "
        "Eingangsbestätigung mit einer Kopie Ihrer Nachricht.",
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


# Adressen ohne .html: Jede Seite liegt als index.html in einem eigenen Ordner,
# damit der Server sie unter dem Ordnernamen ausliefert. Das ist die einzige Art
# sprechender Adressen, die ohne Servereinstellungen funktioniert — GitHub Pages
# kennt keine Umschreibungsregeln.
SLUG = {
    "index.html": "",
    "About.html": "about/",
    "Projects.html": "projects/",
    "Contact.html": "contact/",
    "Legal.html": "legal/",
}


def out_path(lang: str, page: str) -> str:
    """Ablageort im Repo, z. B. 'en/about/index.html'."""
    pref = "" if lang == "de" else f"{lang}/"
    return f"{pref}{SLUG[page]}index.html"


def link_for(lang: str, page: str) -> str:
    """Verweis innerhalb der Seite, immer von der Wurzel aus.

    Absolut und nicht relativ, weil dieselbe Vorlage künftig in
    unterschiedlichen Tiefen liegt (/about/ und /en/about/). Ein relativer Pfad
    müsste je Ablageort anders lauten und wäre eine ständige Fehlerquelle.
    """
    pref = "" if lang == "de" else f"{lang}/"
    return f"/{pref}{SLUG[page]}"


def url_for(lang: str, page: str) -> str:
    """Öffentliche Adresse einer Seite."""
    return f"{BASE}{link_for(lang, page)}"


def switch_href(from_lang: str, to_lang: str, page: str) -> str:
    """Ziel des Sprachumschalters: dieselbe Seite in der anderen Sprache."""
    return link_for(to_lang, page)


# Die Rechtstexte (Impressum, Datenschutzerklärung) liegen nur auf Deutsch vor
# und sind für eine deutsche GmbH auch die verbindliche Fassung. Die Seite gibt
# es trotzdem in jedem Sprachordner, damit Besucher ihre Navigation behalten —
# sie verweist aber per canonical auf die deutsche Fassung, damit Google die
# drei Adressen zusammenfasst statt sie als doppelten Inhalt zu behandeln.
GERMAN_ONLY = ("Legal.html",)


# Beschreibungen der acht Fahrzeuge in Englisch und Franzoesisch. Der
# Export enthaelt sie nur auf Deutsch; auf den Sprachseiten standen sie
# deshalb deutsch da. Die Zuordnung laeuft ueber die Kennung des Projekts,
# die Reihenfolge der Absaetze muss der deutschen entsprechen — das Skript
# prueft das beim Bauen. In den Texten kommen bewusst keine geraden
# Anfuehrungszeichen und keine geraden Apostrophe vor: Die Absaetze stehen
# in einfach begrenzten JS-Zeichenketten innerhalb eines JSON-Blocks.
PROJEKT_ABSAETZE = {
    "en": {
        "proj-910": [
            "After more than a year of complete restoration, the Porsche 910 rolled out at the Birkhau training ground near Kirchheim/Teck. Standing just 980 mm tall, the car looks almost delicate — yet its slender fibreglass body carries an impressive presence.",
            "Built between 1966 and 1968 as a further development of the 906, the 910 (“Carrera 10”) was reserved for the works team; only around 35 were made. Its air-cooled 2.0-litre flat-six (type 901) delivers some 220 hp at 8,000 rpm through a five-speed gearbox with limited-slip differential.",
        ],
        "proj-906": [
            "The 906 opened the era of pure lightweight racing cars in 1966. Sixty-seven examples of the Carrera 6 were built, most of them for private customers. Chassis 126 went to the Swiss collector Dr Hans Kühnis and made its debut at the 1966 Targa Florio — the race Porsche won outright.",
            "After more than five decades of racing and a serious accident at the Salzburgring in 2020, the ORCA team rebuilt the 906/126 in a full restoration, returning it precisely to its original 1966 condition.",
        ],
        "proj-550": [
            "The Porsche 550 Spyder prototype (chassis 12, 1954) was returned to its original Le Mans livery — silver, race number 39, with turquoise markings along the rear side edges.",
            "Missing original parts such as the race-number lighting were painstakingly recreated, partly by CAD scan and 3D printing. Today the car is a much-admired exhibit at the Le Mans museum — back where it first triumphed.",
        ],
        "proj-917-15": [
            "The Porsche 917 (chassis 15, 1970) took overall victory at the Daytona 24 Hours with Pedro Rodríguez and Leo Kinnunen. In Gulf colours it became a legend through the film classic “Le Mans” with Steve McQueen.",
            "After almost 50 years with various collectors, the car came to ORCA in 2020. The work took more than three years, until in January 2024 it was handed back to its owner in race-ready 1970 specification.",
        ],
        "proj-911r": [
            "This 911 R belonged to racing legend Jo Siffert. At ORCA it underwent an elaborate restoration — the paintwork faithfully restored, deliberately keeping the typical traces of age.",
            "A detailed report on the car and its restoration was the cover story of the first issue, 01/2023, of the Swiss magazine “Spirit”.",
        ],
        "proj-917-045": [
            "The cosmetic restoration of the 917/045 took place between July and September 2020. The car raced at Le Mans in 1971 with Siffert and Bell, and later went, in Martini colours, to the ACO museum in Le Mans as a permanent loan.",
            "For the special exhibition “Made for Le Mans” it was returned to its original 1971 livery — including faithfully recreated paint damage of the kind that occurs in racing.",
        ],
        "proj-917-spy": [
            "The original car from the 1971 Interserie — the third Porsche 917 rebuilt at ORCA Restoration. Another chapter in the company’s 917 history.",
        ],
        "proj-910-berg": [
            "An exceptionally rare car: one of only two surviving examples — the second is in the Porsche Museum. In 1967 it won the Mont Ventoux hill climb of the European Hill Climb Championship.",
            "Extreme lightweight construction: just 464 kg. The flat-eight is a direct descendant of the Porsche Formula 1 engine. ORCA rebuilt the heavily modified car from the ground up — stripped to the last screw — and returned it to its 1967 delivery condition.",
        ],
    },
    "fr": {
        "proj-910": [
            "Après plus d’un an de restauration intégrale, la Porsche 910 a fait sa sortie sur le terrain d’entraînement de Birkhau, près de Kirchheim/Teck. Avec seulement 980 mm de hauteur, la voiture paraît presque menue — et dégage pourtant une présence saisissante malgré sa fine carrosserie en fibre de verre.",
            "Développée de 1966 à 1968 à partir de la 906, la 910 (« Carrera 10 ») était réservée à l’équipe d’usine ; 35 exemplaires environ ont été construits. Son flat-six 2,0 litres refroidi par air (type 901) développe quelque 220 ch à 8 000 tr/min, transmis par une boîte à cinq rapports à différentiel autobloquant.",
        ],
        "proj-906": [
            "Avec la 906 s’ouvre en 1966 l’ère des voitures de course tout en légèreté. Soixante-sept Carrera 6 ont été produites, majoritairement pour des clients privés. Le châssis 126 rejoignit le collectionneur suisse Dr Hans Kühnis et fit ses débuts à la Targa Florio 1966 — la course que Porsche remporta au classement général.",
            "Après plus de cinq décennies de compétition et un grave accident au Salzburgring en 2020, l’équipe ORCA a entièrement restauré la 906/126 pour la ramener exactement dans son état d’origine de 1966.",
        ],
        "proj-550": [
            "Le prototype Porsche 550 Spyder (châssis 12, 1954) a retrouvé sa livrée d’origine du Mans — argent, numéro 39, avec des marques turquoise sur les arêtes latérales arrière.",
            "Les pièces d’origine manquantes, comme l’éclairage du numéro de course, ont été reconstituées avec soin, en partie par numérisation CAO et impression 3D. La voiture est aujourd’hui une pièce remarquée du musée du Mans — de retour sur les lieux de son premier triomphe.",
        ],
        "proj-917-15": [
            "La Porsche 917 (châssis 15, 1970) a signé la victoire au classement général des 24 Heures de Daytona avec Pedro Rodríguez et Leo Kinnunen. Aux couleurs Gulf, elle est devenue légendaire grâce au film « Le Mans » avec Steve McQueen.",
            "Après près de 50 ans passés chez différents collectionneurs, la voiture est arrivée chez ORCA en 2020. Les travaux ont duré plus de trois ans, jusqu’à sa restitution à son propriétaire en janvier 2024, dans son état d’origine de 1970, prête à courir.",
        ],
        "proj-911r": [
            "Cette 911 R appartenait à la légende de la course Jo Siffert. Chez ORCA, elle a fait l’objet d’une restauration minutieuse — peinture refaite à l’identique, en conservant volontairement les marques du temps.",
            "Un reportage détaillé sur la voiture et sa restauration a fait la une du premier numéro, 01/2023, du magazine suisse « Spirit ».",
        ],
        "proj-917-045": [
            "La restauration esthétique de la 917/045 s’est déroulée entre juillet et septembre 2020. La voiture a couru au Mans en 1971 avec Siffert et Bell, avant de rejoindre, aux couleurs Martini, le musée de l’ACO au Mans en prêt permanent.",
            "Pour l’exposition « Made for Le Mans », elle a retrouvé sa livrée d’origine de 1971 — y compris les éclats de peinture reproduits fidèlement, tels qu’ils apparaissent en course.",
        ],
        "proj-917-spy": [
            "La voiture d’origine de l’Interserie 1971 — la troisième Porsche 917 reconstruite chez ORCA Restoration. Un chapitre de plus dans l’histoire des 917 de la maison.",
        ],
        "proj-910-berg": [
            "Une voiture d’une rareté exceptionnelle : l’un des deux seuls exemplaires conservés — le second se trouve au musée Porsche. En 1967, elle remporta la course de côte du mont Ventoux, comptant pour le championnat d’Europe de la montagne.",
            "Allègement extrême : 464 kg seulement. Le flat-huit descend directement du moteur de Formule 1 Porsche. ORCA a entièrement reconstruit cette voiture jusque-là fortement modifiée — démontée jusqu’à la dernière vis — pour la ramener dans son état de livraison de 1967.",
        ],
    },
}


# Beschriftung des Laufbands im Hero für Screenreader. Vorgelesen würde sonst
# die Aneinanderreihung der Fahrzeugnamen, was als Ziel eines Verweises nichts
# aussagt.
TICKER_LABEL = {
    "de": "Alle Projekte ansehen",
    "en": "View all projects",
    "fr": "Voir tous les projets",
}

OG_IMAGE_ALT = {
    "de": "Historischer Porsche-Rennwagen auf einer Passstrasse",
    "en": "Historic Porsche race car on a mountain pass road",
    "fr": "Voiture de course Porsche historique sur une route de col",
}


def head_links(lang: str, page: str) -> str:
    """Der komplette Kopfbereich des *äusseren* Dokuments, als normales HTML.

    Das ist alles, was ohne JavaScript zu sehen ist — und damit das, worauf
    sich Crawler und Vorschauen von Messengern verlassen müssen. Beschreibung,
    og-Angaben und strukturierte Daten stehen zwar auch in der Vorlage, die
    aber erst entsteht, wenn das JS-Paket entpackt ist. Nicht jeder Abholer
    tut das.

    Bewusst nicht in den Vorlagen-Head: Dort verwaltet die helmet-Mechanik der
    Seite die Tags selbst und entfernt Fremdes wieder.
    """
    title, desc = META[page][lang]
    seite = url_for(lang, page)
    out = [
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f'<meta name="description" content="{desc}">',
        '<meta name="robots" content="index, follow">',
    ]

    if page in GERMAN_ONLY:
        # Nur ein Kanonisierungs-Hinweis, keine hreflang-Angaben: Die Seite
        # ist inhaltlich in allen Ordnern deutsch, widersprüchliche
        # Sprachsignale wären schlechter als keine.
        out.append(f'<link rel="canonical" href="{url_for("de", page)}">')
    else:
        out.append(f'<link rel="canonical" href="{seite}">')
        for other in LANGS:
            out.append(f'<link rel="alternate" hreflang="{other}" '
                       f'href="{url_for(other, page)}">')
        out.append(f'<link rel="alternate" hreflang="x-default" '
                   f'href="{url_for("de", page)}">')

    # Vorschau in Messengern und sozialen Netzen. Ohne og:image zeigen WhatsApp,
    # LinkedIn und Co. nur eine leere Fläche.
    out += [
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="ORCA Restoration GmbH">',
        f'<meta property="og:locale" content="{OG_LOCALE[lang]}">',
        f'<meta property="og:title" content="{title}">',
        f'<meta property="og:description" content="{desc}">',
        f'<meta property="og:url" content="{seite}">',
        f'<meta property="og:image" content="{BASE}/og-image.jpg">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        f'<meta property="og:image:alt" content="{OG_IMAGE_ALT[lang]}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{title}">',
        f'<meta name="twitter:description" content="{desc}">',
        f'<meta name="twitter:image" content="{BASE}/og-image.jpg">',
    ]

    # Symbol der Seite: ein schwarzes O im Serifenschnitt, passend zum
    # Schriftzug. Google zeigt es in den Ergebnissen an, es ist also nicht nur
    # Zierde. Zwei Groessen, weil Google mindestens 48 Pixel verlangt und
    # hochaufloesende Anzeigen mehr brauchen; apple-touch-icon gilt beim
    # Ablegen auf dem Startbildschirm. Eine SVG-Fassung gibt es bewusst nicht:
    # Sie muesste den Buchstaben als Pfad enthalten, sonst saehe sie je nach
    # Geraet anders aus als die PNG-Fassungen.
    out += [
        '<link rel="icon" href="/favicon.ico" sizes="16x16 32x32 48x48">',
        '<link rel="icon" href="/favicon-48.png" sizes="48x48" type="image/png">',
        '<link rel="icon" href="/favicon-192.png" sizes="192x192" type="image/png">',
        '<link rel="apple-touch-icon" href="/apple-touch-icon.png">',
        '<meta name="theme-color" content="#1b1a17">',
    ]

    # Strukturierte Daten auch ohne JavaScript. Inhaltlich dieselbe Angabe wie
    # in der Vorlage, ergänzt um das Instagram-Profil. Bewusst keine
    # Öffnungszeiten und keine Koordinaten: Beides ist nicht belegt, und
    # falsche strukturierte Daten sind schlechter als keine.
    ld = (
        '{"@context":"https://schema.org","@type":"AutoRepair",'
        '"name":"ORCA Restoration GmbH",'
        f'"description":"{SCHEMA_DESC[lang]}",'
        f'"image":"{SCHEMA_IMAGE}",'
        f'"url":"{url_for(lang, "index.html")}",'
        '"telephone":"+4970423743267","email":"info@orca.gmbh",'
        '"vatID":"DE815733570",'
        f'"logo":"{BASE}/logo-orca.png",'
        f'"sameAs":["{INSTAGRAM_URL}"],'
        '"address":{"@type":"PostalAddress",'
        '"streetAddress":"Robert-Bosch-Str. 4","postalCode":"71735",'
        '"addressLocality":"Eberdingen","addressCountry":"DE"}}'
    )
    out.append(f'<script type="application/ld+json">{ld}</script>')

    return "\n" + "\n".join(out)


def uebersetze_projekttexte(s: str, lang: str, page: str) -> str:
    """Tauscht die deutschen Fahrzeugbeschreibungen gegen die uebersetzten.

    Die Daten stehen als JS-Feld BASE_PROJECTS in der Datei. Statt die langen
    deutschen Absaetze im Skript zu wiederholen — mit allen Fallen ihrer
    Maskierung — liest die Funktion sie aus der Datei und ersetzt sie der
    Reihe nach. Stimmt die Zahl der Absaetze nicht, bricht der Bau ab: Dann
    hat sich der Export geaendert und die Uebersetzung passt nicht mehr.
    """
    anfang = s.find("const BASE_PROJECTS = [")
    ende = s.find("];", anfang)
    if anfang < 0 or ende < 0:
        raise SystemExit(f"{page} [{lang}]: BASE_PROJECTS nicht gefunden")
    block = s[anfang:ende + 2]
    neu = block

    gesehen = 0
    for teil in re.split(r"\\n  \{ id: '", block)[1:]:
        pid = teil[:teil.find("'")]
        d = teil.find("desc: [")
        if d < 0:
            raise SystemExit(f"{page} [{lang}]: {pid} ohne desc")
        absaetze = re.findall(r"'((?:[^'\\]|\\.)*)'", teil[d + 7:])
        ziel = PROJEKT_ABSAETZE[lang].get(pid)
        if ziel is None:
            raise SystemExit(f"{page} [{lang}]: keine Uebersetzung fuer {pid}")
        if len(ziel) != len(absaetze):
            raise SystemExit(
                f"{page} [{lang}]: {pid} hat {len(absaetze)} Absaetze, "
                f"uebersetzt sind {len(ziel)}")
        for deutsch, fremd in zip(absaetze, ziel):
            if neu.count("'" + deutsch + "'") != 1:
                raise SystemExit(
                    f"{page} [{lang}]: Absatz von {pid} nicht eindeutig")
            neu = neu.replace("'" + deutsch + "'", "'" + fremd + "'", 1)
            gesehen += 1

    if gesehen != sum(len(v) for v in PROJEKT_ABSAETZE[lang].values()):
        raise SystemExit(f"{page} [{lang}]: nicht alle Absaetze ersetzt")
    return s[:anfang] + neu + s[ende + 2:]


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

    # --- Pfade zu Bildern und Videos: von der Wurzel aus ------------------
    # Die Seiten liegen in unterschiedlichen Tiefen (/, /about/, /en/about/).
    # Ein relativer Pfad müsste je Ablageort anders lauten; von der Wurzel aus
    # ist er für alle gleich.
    s = s.replace("'images/", "'/images/")
    s = s.replace('src=\\"./restauration.mp4\\"', 'src=\\"/restauration.mp4\\"')

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

    # --- Laufband: Pause nur fuer Mauszeiger ------------------------------
    # Das Band haelt an, solange man mit der Maus darueber steht. Auf dem Handy
    # bleibt ein angetipptes Element aber im Zustand "ueberfahren" — nach einem
    # Tipp auf das Band (das jetzt zur Projektseite fuehrt) und dem Zurueckgehen
    # stand es still und lief nicht wieder an. Die Regel gilt deshalb nur noch
    # dort, wo es einen echten Zeiger gibt; auf Geraeten mit Finger existiert
    # sie gar nicht und kann das Band folglich nicht anhalten.
    if page == "index.html":
        sub_once(
            '  .orca-ticker:hover .orca-track '
            '{ animation-play-state: paused; }\\n',
            '  @media (hover: hover) and (pointer: fine) {\\n'
            '    .orca-ticker:hover .orca-track '
            '{ animation-play-state: paused; }\\n'
            '  }\\n',
            "Pause des Laufbands nur mit Mauszeiger")

    # --- Ueberschriften in aufsteigender Ordnung --------------------------
    # Auf "Ueber uns" folgen dem h1 drei h3, erst danach kommen h2 — eine
    # uebersprungene Stufe. Screenreader lesen die Gliederung daran ab, und
    # Lighthouse zog dafuer Punkte ab ("Heading elements are not in a
    # sequentially-descending order"). Die drei sind inhaltlich Abschnitte
    # erster Ordnung und werden zu h2. Die Schriftgroesse steht im
    # style-Attribut und bleibt unveraendert, die Darstellung also auch.
    if page == "About.html":
        alt_h3 = ('<h3 style=\\"font-family:\'Cormorant Garamond\',serif; '
                  'font-weight:400; font-size:24px; margin:0 0 10px;\\">')
        treffer = re.findall(re.escape(alt_h3) + r'(.{0,120}?)<\\u002Fh3>', s)
        if len(treffer) != 3:
            raise SystemExit(
                f"{page} [{lang}]: {len(treffer)} Ueberschriften mit 24px "
                "erwartet 3")
        s = re.sub(re.escape(alt_h3) + r'(.{0,120}?)<\\u002Fh3>',
                   lambda m: alt_h3.replace('<h3', '<h2') + m.group(1)
                   + '<\\u002Fh2>', s)

    # --- Hauptbereich auszeichnen -----------------------------------------
    # Zwischen Kopf- und Fusszeile stehen die Abschnitte ohne umgebendes
    # Element. Screenreader bieten damit keinen Sprung zum Inhalt an, und
    # Lighthouse meldete "Document does not have a main landmark". Ein <main>
    # um alles zwischen den beiden loest das, ohne die Darstellung zu
    # beruehren: Das Element hat keine eigenen Abstaende, und keine der Regeln
    # spricht direkte Kinder des Wurzelelements an.
    sub_once('<\\u002Fheader>', '<\\u002Fheader>\\n\\n  <main>',
             "Beginn des Hauptbereichs")
    sub_once('<footer style=\\"padding:56px 56px 40px;',
             '<\\u002Fmain>\\n\\n  <footer style=\\"padding:56px 56px 40px;',
             "Ende des Hauptbereichs")

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
    # Bild steht, während das Video lädt.
    #
    # Ohne Quelle im Markup: Welche Fassung geladen wird, entscheidet das
    # Skript im Ladeteil (orcaHero) anhand der Fensterbreite. Der naheliegende
    # Weg über zwei <source>-Elemente mit media-Angabe ist unbrauchbar —
    # Chromium lädt auf dem Handy dann BEIDE Dateien, also 5865 statt 1141 KB.
    # Nachgemessen mit Bereichsanfragen, wie GitHub Pages sie beantwortet.
    if page == "index.html":
        old_slot = ('<image-slot id=\\"hero-main\\" shape=\\"rect\\" '
                    'placeholder=\\"Porsche Rennwagen – Titelbild (später Video)\\" '
                    'style=\\"position:absolute; inset:0; width:100%; height:100%;\\" '
                    'src=\\"e264a4e1-5ee2-422f-9bcf-5a715b5d17b3\\"><\\u002Fimage-slot>')
        new_video = (
            '<video autoplay=\\"true\\" muted=\\"true\\" loop=\\"true\\" '
            'playsinline=\\"true\\" preload=\\"auto\\" '
            'poster=\\"/hero-poster.jpg\\" '
            'style=\\"position:absolute; inset:0; width:100%; height:100%; '
            'object-fit:cover; display:block;\\">'
            '<\\u002Fvideo>')
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

        # --- Laufband im Hero anklickbar machen ---------------------------
        # Es zeigt die Fahrzeuge und fuehrt deshalb zur Projektseite. Bewusst
        # als echter Verweis und nicht ueber einen Klick-Handler: So laesst er
        # sich mit der Tastatur erreichen, in einem neuen Tab oeffnen, und
        # Suchmaschinen folgen ihm. Die Klasse bleibt am Element, damit die
        # Regel zum Anhalten beim Ueberfahren weiter greift.
        sub_once('<div class=\\"orca-ticker\\" style=\\"position:absolute; '
                 'left:0; right:0; bottom:62px;',
                 f'<a href=\\"{link_for(lang, "Projects.html")}\\" '
                 f'aria-label=\\"{TICKER_LABEL[lang]}\\" '
                 'class=\\"orca-ticker link-fade\\" '
                 'style=\\"display:block; cursor:pointer; '
                 'position:absolute; left:0; right:0; bottom:62px;',
                 "Laufband als Verweis")
        sub_once('<\\u002Fdiv>\\n    <\\u002Fdiv>\\n\\n    '
                 '<div sc-camel-on-click=\\"{{ scrollDown }}\\"',
                 '<\\u002Fdiv>\\n    <\\u002Fa>\\n\\n    '
                 '<div sc-camel-on-click=\\"{{ scrollDown }}\\"',
                 "Abschluss des Laufbands")

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
        # Feldnamen fest und unabhaengig von der Sprache: kontakt.php erwartet
        # genau diese. Die Sprache geht als eigenes Feld mit, damit die
        # Eingangsbestaetigung in der Sprache der Website ankommt.
        'var d={name:n,email:m,fahrzeug:v,nachricht:x,sprache:L,betreff:t[8]};'
        'b.disabled=true;sag(t[5],true);'
        # Bewusst text/plain statt application/json: Ein JSON-Kopf macht die
        # Anfrage zu einer "nicht einfachen" und der Browser schickt vorher eine
        # OPTIONS-Vorabfrage. Die ist eine zusaetzliche Fehlerquelle — sperrt
        # der Server sie, kommt die eigentliche Anfrage nie an. Der Inhalt
        # bleibt JSON, kontakt.php liest den Rumpf und nicht den Kopf.
        f'fetch("{FORM_ENDPOINT}",{{method:"POST",'
        'headers:{"Content-Type":"text/plain;charset=UTF-8"},'
        'body:JSON.stringify(d)}).then(function(r){'
        'return r.text().then(function(tx){return {ok:r.ok,st:r.status,tx:tx};});'
        '}).then(function(a){'
        'var j=null;try{j=JSON.parse(a.tx);}catch(e){}'
        'if(!a.ok||!j||!j.ok)throw new Error(j&&j.fehler?j.fehler:"HTTP "+a.st);'
        'sag(t[6],true);'
        '["orca-f-name","orca-f-email","orca-f-vehicle","orca-f-message"].forEach(function(c){'
        'var el=document.querySelector("."+c);if(el)el.value="";});'
        'b.disabled=false;}).catch(function(e){'
        # Faellt der Dienst aus, geht die Anfrage nicht verloren: Der Hinweis
        # nennt die Adresse, und der Knopf wird wieder bedienbar. Der Grund
        # steht in Klammern dahinter — ohne ihn ist von aussen nicht zu
        # unterscheiden, ob der Server ablehnt, die Mail scheitert oder die
        # Verbindung gar nicht zustande kommt.
        'sag(t[7]+" ("+((e&&e.message)||"Verbindung")+")",false);'
        'b.disabled=false;});'
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
        '});'
        # Der Verweis auf die Rechtstexte im Cookie-Hinweis lautet
        # "./Legal.html" und steckt im komprimierten Paket, nicht in der
        # Vorlage — im Text ist er deshalb nicht zu ersetzen. Von /about/ aus
        # zeigte er auf /about/Legal.html und damit ins Leere. Hier wird er im
        # fertigen Baum auf die sprechende Adresse gesetzt. Der Beobachter ist
        # noetig, weil der Hinweis nach dem ersten Aufbau erscheint und die
        # Seite bei Interaktionen neu zeichnet.
        # Bewusst ueber getElementsByTagName und nicht ueber einen
        # Attributselektor: Der eingefuegte Code steht in der Datei innerhalb
        # eines mit einfachen Anfuehrungszeichen begrenzten JS-Strings. Ein
        # Selektor wie a[href$="Legal.html"] braeuchte Anfuehrungszeichen um den
        # Wert und wuerde diesen String zerreissen — genau daran ist ein erster
        # Versuch gescheitert (Unexpected identifier). Hier kommen nur doppelte
        # Anfuehrungszeichen vor.
        'var orcaLegal=function(){'
        'var L=(document.documentElement.getAttribute("lang")||"de").substring(0,2);'
        'var ziel=L==="de"?"/legal/":"/"+L+"/legal/";'
        'var a=document.getElementsByTagName("a");'
        'for(var i=0;i<a.length;i++){'
        'var h=a[i].getAttribute("href")||"";'
        'if(h.indexOf("Legal.html")>=0)a[i].setAttribute("href",ziel);}};'
        # Das Hero-Video kommt in zwei Fassungen: 1920x1078 mit 4724 KB und ein
        # Hochformat-Zuschnitt mit 1141 KB. Auf dem Handy ist von einem
        # 16:9-Bild ohnehin nur ein schmaler Streifen der Mitte zu sehen — der
        # Zuschnitt zeigt genau diesen, in voller Bildhoehe. Im Bildvergleich
        # sind beide bei 390 Pixel Breite nicht zu unterscheiden (41 dB).
        # Die Auswahl faellt hier und nicht ueber zwei <source>-Elemente mit
        # media-Angabe: Chromium laedt dabei beide Dateien.
        'var orcaHero=function(){'
        'var v=document.querySelector(".orca-hero video");'
        'if(!v||v.getAttribute("src"))return;'
        'var klein=window.matchMedia&&window.matchMedia("(max-width: 820px)").matches;'
        'v.setAttribute("src",klein?"/hero-mobile.mp4":"/hero.mp4");'
        'var w=v.play();if(w&&w.catch)w.catch(function(){});};'
        # Titel und meta-Angaben stehen nach dem Rendern im Koerper statt im
        # Kopfbereich — die Vorlage traegt sie als gewoehnliche Elemente im
        # Komponentenbaum. Ein Titel dort wirkt zwar noch, eine Beschreibung
        # aber nicht: Google liest sie nur im Kopfbereich, und Lighthouse
        # meldete deshalb "Document does not have a meta description".
        # Hier werden sie umgehaengt, wobei gleichnamige Angaben im Kopf
        # vorher entfernt werden, damit nichts doppelt steht. Die Listen sind
        # lebendig, das Umhaengen leert sie also von selbst.
        'var orcaKopf=function(){'
        'if(!document.body||!document.head)return;'
        'var t=document.body.getElementsByTagName("title");'
        'while(t.length){'
        'var a=document.head.getElementsByTagName("title");'
        'while(a.length)a[0].parentNode.removeChild(a[0]);'
        'document.head.appendChild(t[0]);}'
        'var m=document.body.getElementsByTagName("meta");'
        'while(m.length){var e=m[0];'
        'var n=e.getAttribute("name")||e.getAttribute("property")||"";'
        'var h=document.head.getElementsByTagName("meta");'
        'for(var i=h.length-1;i>=0;i--){'
        'var hn=h[i].getAttribute("name")||h[i].getAttribute("property")||"";'
        'if(n&&hn===n)h[i].parentNode.removeChild(h[i]);}'
        'document.head.appendChild(e);}};'
        'var orcaNach=function(){orcaLegal();orcaHero();orcaKopf();};'
        'orcaNach();'
        'if(window.MutationObserver){'
        'new MutationObserver(orcaNach).observe(document.documentElement,'
        '{childList:true,subtree:true});}')
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
    # Die Klappflaeche ist auf allen Seiten hell. Auf der Startseite war sie
    # zunaechst dunkel, weil die Kopfzeile dort ueber dem Video liegt und ihre
    # Schrift hell ist — im Gebrauch wirkte es aber wie zwei verschiedene Menues.
    # Deshalb einheitlich hell, und die Menuepunkte darin bekommen die dunkle
    # Schriftfarbe zugewiesen (inline stehen sie auf der Startseite hell und
    # waeren auf hellem Grund unsichtbar).
    # Bewusst als Zahlenwert und nicht als {{ bg }}/{{ line }}: Im Stylesheet
    # werden diese Platzhalter nicht ersetzt. Auf Legal.html bleiben sie sogar
    # unveraendert stehen, auf den uebrigen Seiten wird der Text erst nach dem
    # Auswerten der Regeln getauscht — die Angabe faellt in beiden Faellen
    # ersatzlos weg (dieselbe Ursache liegt hinter dem toten
    # "body { background: {{ bg }} }" im Export). In Attributen greift die
    # Ersetzung dagegen, deshalb steht {{ text }} unten am Balken. Die Werte
    # entsprechen dem Farbschema des Entwurfs; sie muessen nachgezogen werden,
    # falls sich dieses aendert.
    panel_bg = "#f6f3ee"
    panel_line = "#ddd7cc"
    panel_text = "#1b1a17"
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
        '        border-bottom: 0 !important; padding: 0 0 0 14px !important;\\n'
        f'        color: {panel_text} !important; }}\\n'
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
        '    /* Hero ueber den ganzen Bildschirm. Zwei Angaben zur Hoehe mit\\n'
        '       Absicht: dvh meint die tatsaechlich sichtbare Hoehe, vh auf dem\\n'
        '       iPhone dagegen das Fenster OHNE Adressleiste und ist damit\\n'
        '       groesser als der sichtbare Bereich. Wer dvh nicht kennt, behaelt\\n'
        '       den vh-Wert. Ein 16:9-Video wird im Hochformat bei\\n'
        '       object-fit:cover stark seitlich beschnitten — das ist der Preis\\n'
        '       fuer das bildschirmfuellende Bild und so gewollt. */\\n'
        '    /* Kein Seitenabstand am Hero: Er ist randlos, und weil er\\n'
        '       width:100% ohne border-box traegt, kaemen die 22px oben drauf —\\n'
        '       die Seite liess sich dadurch 44px seitlich verschieben. */\\n'
        '    .orca-hero { height: 100vh !important; height: 100dvh !important;\\n'
        '                 min-height: 420px !important;\\n'
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
        '  /* Beschreibung auf der Projektkachel: drei Zeilen, der Rest wird\\n'
        '     abgeschnitten. Der vollstaendige Text steht im Dokument und ist\\n'
        '     ueber die Detailansicht zu lesen. */\\n'
        '  .proj-teaser { display: -webkit-box; -webkit-box-orient: vertical;\\n'
        '                 -webkit-line-clamp: 3; line-clamp: 3;\\n'
        '                 overflow: hidden; }\\n'
        '  /* Der Hinweistext ueber der Karte stand mit 4.41:1 auf dem helleren\\n'
        '     Kasten — verlangt sind 4.5:1 fuer kleine Schrift. Etwas dunkler\\n'
        '     ergibt 6.0:1. Der Text kommt aus dem komprimierten Paket und ist\\n'
        '     im Quelltext nicht zu erreichen, deshalb ueber das style-Attribut.\\n'
        '     Beide Schreibweisen, weil die rendernde Schicht Leerzeichen in die\\n'
        '     Werte einfuegt. Betrifft genau dieses eine Element, nachgemessen\\n'
        '     ueber alle fuenf Seiten. */\\n'
        '  [style*=\\"max-width: 360px\\"],\\n'
        '  [style*=\\"max-width:360px\\"] { color: #57514c !important; }\\n'
        '  /* Mit dem Finger liess sich die Seite nicht scrollen, solange er auf\\n'
        '     einem Bild lag: Die image-slot-Elemente des Exports fangen die\\n'
        '     Beruehrung ab und unterdruecken die Standardgeste. Gemessen auf\\n'
        '     der Seite Ueber uns: Wisch auf dem Bild 0 Pixel, daneben 382.\\n'
        '     touch-action half nicht — die Angabe erlaubt eine Geste nur, sie\\n'
        '     verhindert nicht, dass ein Listener sie abbestellt. Bleibt, die\\n'
        '     Elemente fuer Zeigegeraete unsichtbar zu machen: Die Beruehrung\\n'
        '     geht dann an den Bereich darunter, und die Seite scrollt wie\\n'
        '     ueberall sonst. Klicks auf Projektkacheln funktionieren weiter,\\n'
        '     weil der Klickbereich die Kachel ist und nicht das Bild.\\n'
        '     Begrenzt auf Geraete ohne Mauszeiger, damit am Desktop das\\n'
        '     Kontextmenue auf Bildern erhalten bleibt. */\\n'
        '  @media (hover: none) and (pointer: coarse) {\\n'
        '    image-slot { pointer-events: none !important; }\\n'
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

    # --- Fahrzeugbeschreibungen uebersetzen -------------------------------
    if page == "Projects.html" and lang != "de":
        s = uebersetze_projekttexte(s, lang, page)

    # --- Projekttexte auf die Kachel holen --------------------------------
    # Die Beschreibungen der acht Fahrzeuge — zusammen 520 Woerter und der
    # inhaltlich wertvollste Text der ganzen Seite — standen nur in der
    # Detailansicht und entstanden erst beim Anklicken. Google klickt nicht,
    # also war dieser Text fuer Suchmaschinen nicht vorhanden.
    #
    # Er steht jetzt in der Kachel selbst. Sichtbar sind drei Zeilen, der Rest
    # wird abgeschnitten (line-clamp) — der uebliche Aufbau einer Kachelliste.
    # Damit ist der Text im Dokument, ohne dass die Seite zur Textwueste wird;
    # vollstaendig zu lesen ist er wie bisher in der Detailansicht.
    # Bewusst nicht versteckt (etwa ausserhalb des Bildschirms): Text, den nur
    # Suchmaschinen sehen, gilt zu Recht als Manipulation.
    if page == "Projects.html":
        sub_once(
            '        <\\u002Fdiv>\\n      <\\u002Fdiv>\\n    <\\u002Fsc-for>',
            '        <\\u002Fdiv>\\n'
            '        <div class=\\"proj-teaser\\" style=\\"font-size:14px; '
            'line-height:1.7; color:{{ textMuted }}; margin-top:10px;\\">'
            '<sc-for list=\\"{{ p.desc }}\\" as=\\"para\\">'
            '<span>{{ para }} <\\u002Fspan><\\u002Fsc-for>'
            '<\\u002Fdiv>\\n'
            '      <\\u002Fdiv>\\n    <\\u002Fsc-for>',
            "Beschreibung auf der Projektkachel")

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

    # --- Interne Verweise auf die sprechenden Adressen --------------------
    # Aus ./About.html wird /about/ (bzw. /en/about/), aus ./ und ./index.html
    # die Startseite der jeweiligen Sprache. Alle Verweise laufen von der Wurzel
    # aus, weil dieselbe Vorlage in verschiedenen Tiefen liegt.
    for ziel, slug in SLUG.items():
        if ziel == "index.html":
            continue
        muster = f'href=\\"./{ziel}\\"'
        if muster not in s:
            raise SystemExit(f"{page} [{lang}]: kein Verweis auf {ziel} gefunden")
        s = s.replace(muster, f'href=\\"{link_for(lang, ziel)}\\"')

    # Startseite: ./ und ./index.html, dazu die vom Sprachumschalter bereits
    # gesetzten absoluten Pfade nicht anfassen.
    s = re.sub(r'href=\\"\./(?:index\.html)?\\"',
               f'href=\\\\"{link_for(lang, "index.html")}\\\\"', s)

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

    pruefe_bundle(s, lang, page)
    return s


def pruefe_bundle(s: str, lang: str, page: str) -> None:
    """Stellt sicher, dass die Vorlage im Paket gültiges JSON geblieben ist.

    Die Seite liegt in einem <script type="__bundler/template"> als
    JSON-Zeichenkette und wird beim Laden mit JSON.parse gelesen. Jedes
    einfache Anführungszeichen, das in eingefügtem Text steht, zerreisst sie —
    im Browser erscheint dann nur "Error unpacking" und sonst nichts. Genau das
    ist mit einem Wort in einem CSS-Kommentar passiert. Eingefügte
    Anführungszeichen müssen als \\" geschrieben werden; diese Prüfung findet
    den Fehler beim Bauen statt erst auf der fertigen Seite.
    """
    for art in ("template", "manifest"):
        m = re.search(rf'<script type="__bundler/{art}"[^>]*>(.*?)</script>',
                      s, re.S)
        if m is None:
            raise SystemExit(f"{page} [{lang}]: Block __bundler/{art} fehlt")
        try:
            json.loads(m.group(1))
        except json.JSONDecodeError as fehler:
            stelle = m.group(1)[max(0, fehler.pos - 90):fehler.pos + 40]
            raise SystemExit(
                f"{page} [{lang}]: __bundler/{art} ist kein gueltiges JSON "
                f"mehr — {fehler.msg} an Position {fehler.pos}.\n"
                f"  Umfeld: ...{stelle}...\n"
                "  Meist ein Anfuehrungszeichen in eingefuegtem Text; "
                "es muss dort als \\\" stehen."
            ) from None


def main() -> None:
    root = Path.cwd()
    missing = [p for p in PAGES if not (root / p).exists()]
    if missing:
        raise SystemExit(f"Im aktuellen Verzeichnis fehlen: {', '.join(missing)}")

    originals = {}
    for page in PAGES:
        text = (root / page).read_text(encoding="utf-8")
        # Nach einem Lauf steht an dieser Stelle nur noch ein
        # Weiterleitungs-Stummel, denn der Inhalt liegt jetzt unter /about/ und
        # so weiter. Ohne diese Pruefung liefe das Skript in eine
        # schwerverstaendliche Fehlermeldung mitten im Umbau.
        if "__orca-boot" not in text:
            raise SystemExit(
                f"{page} ist kein Export (Kennung __orca-boot fehlt) — nach\n"
                "einem Lauf steht dort nur die Weiterleitung. Erst die Exporte\n"
                "wiederherstellen:\n"
                "  git checkout 9f13efb -- "
                + " ".join(PAGES) + "\n"
                "(oder den Stand des letzten Editor-Exports einspielen)"
            )
        if "hreflang" in text or "lang-switch\\\" style=\\\"color" in text:
            raise SystemExit(
                f"{page} wurde offenbar schon umgebaut (hreflang gefunden).\n"
                "Das Skript erwartet unveraenderte Exporte."
            )
        originals[page] = text

    # Alte Ausgabeordner weg, damit nichts Veraltetes liegen bleibt.
    for lang in LANGS:
        if lang != "de" and (root / lang).exists():
            shutil.rmtree(root / lang)
    for page in PAGES:
        ordner = SLUG[page].rstrip("/")
        if ordner and (root / ordner).exists():
            shutil.rmtree(root / ordner)

    for lang in LANGS:
        for page in PAGES:
            ziel = root / out_path(lang, page)
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_text(transform(originals[page], lang, page),
                            encoding="utf-8")
        print(f"  {lang}: " + ", ".join(
            "/" + out_path(lang, p).removesuffix("index.html") for p in PAGES))

    # --- Weiterleitungen von den alten Adressen ---------------------------
    # Die Seiten lagen bis jetzt unter /About.html. Wer einen solchen Link
    # gespeichert hat — oder wessen Suchmaschine ihn kennt — soll nicht im
    # Nichts landen. GitHub Pages kann keine echten Umleitungen (301), deshalb
    # der übliche Weg: canonical nennt das Ziel, refresh und ein Skript
    # schicken den Besucher hin.
    stummel = 0
    for lang in LANGS:
        for page in PAGES:
            if page == "index.html":
                continue
            pref = "" if lang == "de" else f"{lang}/"
            ziel_url = link_for(lang, page)
            alt = root / f"{pref}{page}"
            alt.write_text(
                "<!doctype html>\n"
                f'<html lang="{lang}">\n<head>\n<meta charset="utf-8">\n'
                f'<link rel="canonical" href="{url_for(lang, page)}">\n'
                f'<meta http-equiv="refresh" content="0; url={ziel_url}">\n'
                "<title>ORCA Restoration GmbH</title>\n</head>\n<body>\n"
                f'<p>Diese Seite liegt jetzt unter <a href="{ziel_url}">'
                f'{BASE}{ziel_url}</a>.</p>\n'
                f'<script>location.replace("{ziel_url}");</script>\n'
                "</body>\n</html>\n",
                encoding="utf-8")
            stummel += 1

    # Derselbe Stummel zusätzlich in jedem Seitenordner. Grund ist der Verweis
    # im Cookie-Hinweis: Er lautet "./Legal.html", steckt im komprimierten
    # Paket und zeigt von /about/ aus auf /about/Legal.html. Im Browser wird er
    # nach dem Aufbau korrigiert; wer kein JavaScript ausführt und ihm folgt,
    # landet so trotzdem auf einer Weiterleitung statt auf einem Fehler.
    for lang in LANGS:
        pref = "" if lang == "de" else f"{lang}/"
        vorlage = (root / f"{pref}Legal.html").read_text(encoding="utf-8")
        for page in PAGES:
            ordner = SLUG[page]
            if not ordner:
                continue
            (root / f"{pref}{ordner}Legal.html").write_text(vorlage,
                                                            encoding="utf-8")
            stummel += 1
    print(f"  {stummel} Weiterleitungen von den alten .html-Adressen")

    # --- 404-Seite --------------------------------------------------------
    # GitHub Pages liefert unter /404.html eine eigene Seite aus, wenn nichts
    # passt. Ohne diese Datei steht dort GitHubs Standardtext mit dessen Logo.
    (root / "404.html").write_text(
        "<!doctype html>\n"
        '<html lang="de">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Seite nicht gefunden – ORCA Restoration GmbH</title>\n"
        '<meta name="robots" content="noindex">\n'
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml">\n'
        '<link rel="icon" href="/favicon-48.png" sizes="48x48" type="image/png">\n'
        "<style>\n"
        "  body { margin:0; min-height:100vh; display:flex; align-items:center;\n"
        "         justify-content:center; background:#1b1a17; color:#f6f3ee;\n"
        "         font-family:'Helvetica Neue',Arial,sans-serif;\n"
        "         text-align:center; padding:32px; box-sizing:border-box; }\n"
        "  .z { font-size:64px; letter-spacing:0.04em; margin:0 0 12px;\n"
        "       font-weight:300; }\n"
        "  p { font-size:16px; line-height:1.7; color:rgba(246,243,238,0.72);\n"
        "      margin:0 0 28px; }\n"
        "  a { color:#f6f3ee; font-size:12px; letter-spacing:0.14em;\n"
        "      text-transform:uppercase; text-decoration:none;\n"
        "      border:1px solid rgba(246,243,238,0.4); padding:14px 26px;\n"
        "      display:inline-block; }\n"
        "</style>\n</head>\n<body>\n<div>\n"
        '  <p class="z">404</p>\n'
        "  <p>Diese Seite gibt es nicht mehr oder hat noch nie existiert.</p>\n"
        '  <a href="/">Zur Startseite</a>\n'
        "</div>\n</body>\n</html>\n",
        encoding="utf-8")
    print("  404.html")

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
