"""English and Italian for what the app says (messages, errors, labels on Teams).

Texts are written in English in the code and passed through tr(); IT holds the Italian for each one. A text missing
from IT simply stays in English, so nothing ever breaks. The window of the app has its own table (ui/index.html).
"""
LANGS = ("it", "en")
_lang = "en"


def windows_lang():
    """'it' if Windows speaks Italian, else 'en'."""
    try:
        import ctypes
        return "it" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x10 else "en"
    except (AttributeError, OSError):
        return "en"


def resolve(pref):
    """The language to use for a choice: 'it', 'en', or 'auto' (whatever Windows speaks)."""
    return pref if pref in LANGS else windows_lang()


def set_lang(pref):
    global _lang
    _lang = resolve(pref)


def lang():
    return _lang


def tr(text, **kw):
    s = IT.get(text, text) if _lang == "it" else text
    return s.format(**kw) if kw else s


IT = {
    # worker: what happens on Teams
    "Something went wrong ({e}). Try again in a moment.": "Qualcosa non ha funzionato ({e}). Riprova tra poco.",
    "You're in a call: Teams is back to normal. Everything comes back by itself when the call ends.": "Sei in call: Teams e' normale. A call finita torna tutto da solo.",
    "Call over: Teams Remix is on again.": "Call finita: Teams Remix e' di nuovo attivo.",
    "Couldn't switch Teams Remix on: Teams was reopened as normal. Try again in a moment.": "Non sono riuscito ad accendere Teams Remix: Teams e' stato riaperto normale. Riprova tra poco.",
    "Teams is loading...": "Teams si sta caricando...",
    "Done! Teams Remix is on (theme '{name}').": "Fatto! Teams Remix e' attivo (tema '{name}').",
    "Teams is taking a while to load: Teams Remix shows up by itself as soon as it's ready.": "Teams ci mette un po' a caricarsi: Teams Remix arriva da solo appena e' pronto.",
    "A Teams window had reloaded: everything is back.": "Una finestra di Teams si era ricaricata: ho rimesso tutto.",
    "Teams just opened: reopening it to switch Teams Remix on...": "Teams si e' appena aperto: lo riapro per accendere Teams Remix...",
    "You're in a call: Teams Remix switches on by itself when the call ends.": "Sei in call: Teams Remix si accende da solo a call finita.",
    "Teams is still loading: Teams Remix shows up by itself.": "Teams si sta ancora caricando: Teams Remix arriva da solo.",
    "Reopening Teams to switch Teams Remix on (a few seconds)...": "Riapro Teams per accendere Teams Remix (pochi secondi)...",
    "Opening Teams and switching Teams Remix on...": "Apro Teams e accendo Teams Remix...",
    "Teams' original theme has no effects: pick another theme.": "Il tema originale di Teams non ha effetti: scegli un altro tema.",
    "Effects started on Teams: look at the Teams window!": "Effetti partiti su Teams: guarda la finestra di Teams!",
    "'{name}' has no effects: switch some on in the Effects tab.": "'{name}' non ha effetti: accendine qualcuno nella scheda Effetti.",
    "Housemates called: look at Teams!": "Coinquilini chiamati: guarda Teams!",
    "Pick at least one housemate first.": "Scegli prima almeno un coinquilino.",
    "Teams Remix off: Teams is as it was. Theme, housemates and nicknames stay saved.": "Teams Remix spento: Teams e' com'era. Tema, coinquilini e soprannomi restano salvati.",
    "Reopening Teams as it was...": "Riapro Teams com'era...",
    "Teams reopened as it was, without Teams Remix.": "Teams riaperto com'era, senza Teams Remix.",
    "Waiting for Teams to start...": "Aspetto che parta Teams...",
    "Switching Teams Remix on...": "Accendo Teams Remix...",
    "Switching Teams Remix off...": "Spengo Teams Remix...",
    "Starting the effects...": "Faccio partire gli effetti...",
    "Calling the housemates...": "Chiamo i coinquilini...",
    # errors shown in the app
    "Invalid colour in {k}: {v}": "Colore non valido in {k}: {v}",
    "Invalid value for {k}: {v}": "Valore non valido per {k}: {v}",
    "The gradient takes 2 or 3 #rrggbb colours.": "Il gradiente vuole 2 o 3 colori #rrggbb.",
    "Invalid name: letters, digits, spaces, - and _, at most 40 characters.": "Nome non valido: lettere, numeri, spazi, - e _, massimo 40 caratteri.",
    "There is already a theme '{name}'.": "Esiste gia' un tema '{name}'.",
    "Teams' original theme can't be changed: create a theme of your own.": "Il tema originale di Teams non si modifica: crea un tema tuo.",
    "Theme '{name}' not found.": "Tema '{name}' non trovato.",
    "'{name}' is not one of the app's themes: there is no original to restore.": "'{name}' non e' un tema dell'app: non c'e' un originale da ripristinare.",
    "Invalid name.": "Nome non valido.",
    "It's the last theme: create another one before deleting it.": "E' l'ultimo tema: creane un altro prima di eliminarlo.",
    "Invalid mode.": "Modalita' non valida.",
    "Invalid photo: use a JPG or PNG picture.": "Foto non valida: usa un'immagine JPG o PNG.",
    "Invalid or too large photo.": "Foto non valida o troppo grande.",
    # updates
    "There is no update to install.": "Non c'è nessun aggiornamento da fare.",
    "Update failed ({e}). Nothing changed: try again later.": "Aggiornamento non riuscito ({e}). Niente è cambiato: riprova piu' tardi.",
    # on Teams (screen readers) and in the readability checks
    "Call the capybara": "Chiama il capibara", "Call the cat": "Chiama il gatto", "Call the dog": "Chiama il cane",
    "Call the sheep": "Chiama la pecora", "Call the bull": "Chiama il toro", "Call the ghost": "Chiama il fantasma",
    "Call the robot": "Chiama il robot", "Call the truck": "Chiama il camion", "Call the Dude": "Chiama il Drugo",
    "Start the effects": "Fai partire gli effetti",
    "Teams Remix is on: click to switch it off": "Teams Remix attivo: clic per spegnerlo",
    "Teams Remix is off: click to switch it on": "Teams Remix spento: clic per accenderlo",
    "Themes and effects": "Temi ed effetti", "Housemates": "Coinquilini", "Nicknames": "Soprannomi",
    "Themes and effects are on: click to switch them off": "Temi ed effetti attivi: clic per spegnerli",
    "Themes and effects are off: click to switch them on": "Temi ed effetti spenti: clic per accenderli",
    "Switching themes and effects on...": "Accendo temi ed effetti...",
    "Switching themes and effects off...": "Spengo temi ed effetti...",
    "Housemates are on: click to switch them off": "Coinquilini attivi: clic per spegnerli",
    "Housemates are off: click to switch them on": "Coinquilini spenti: clic per accenderli",
    "Switching the housemates on...": "Accendo i coinquilini...",
    "Switching the housemates off...": "Spengo i coinquilini...",
    "Nicknames are on: click to switch them off": "Soprannomi attivi: clic per spegnerli",
    "Nicknames are off: click to switch them on": "Soprannomi spenti: clic per accenderli",
    "Switching the nicknames on...": "Accendo i soprannomi...",
    "Switching the nicknames off...": "Spengo i soprannomi...",
    "{what}: on in Teams.": "{what}: accesi su Teams.",
    "{what}: off in Teams.": "{what}: spenti su Teams.",
    "Themes and effects are off: switch them on at the top.": "Temi ed effetti sono spenti: accendili in alto.",
    "The housemates are off: switch them on at the top.": "I coinquilini sono spenti: accendili in alto.",
    "Rainbow text {col}": "Testo arcobaleno {col}",
    "Text on the background": "Testo sullo sfondo",
    "Secondary text": "Testo secondario",
    "Links on the background": "Link sullo sfondo",
    "Text on the {col} button": "Scritte sul pulsante {col}",
    "Text in coloured buttons": "Scritte nei pulsanti colorati",
    "Mentions on the background": "Menzioni sullo sfondo",
}
