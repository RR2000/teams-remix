"""Italian and English for what the app says (messages, errors, labels on Teams).

Texts are written in Italian in the code and passed through tr(); EN holds the English for each one. A text missing
from EN simply stays in Italian, so nothing ever breaks. The window of the app has its own table (ui/index.html).
"""
LANGS = ("it", "en")
_lang = "it"


def windows_lang():
    """'it' if Windows speaks Italian, else 'en'."""
    try:
        import ctypes
        return "it" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x10 else "en"
    except (AttributeError, OSError):
        return "it"


def resolve(pref):
    """The language to use for a choice: 'it', 'en', or 'auto' (whatever Windows speaks)."""
    return pref if pref in LANGS else windows_lang()


def set_lang(pref):
    global _lang
    _lang = resolve(pref)


def lang():
    return _lang


def tr(text, **kw):
    s = EN.get(text, text) if _lang == "en" else text
    return s.format(**kw) if kw else s


EN = {
    # worker: what happens on Teams
    "Qualcosa non ha funzionato ({e}). Riprova tra poco.": "Something went wrong ({e}). Try again in a moment.",
    "Sei in call: Teams e' normale. A call finita torna tutto da solo.": "You're in a call: Teams is back to normal. Everything comes back by itself when the call ends.",
    "Call finita: Teams Remix e' di nuovo attivo.": "Call over: Teams Remix is on again.",
    "Non sono riuscito ad accendere Teams Remix: Teams e' stato riaperto normale. Riprova tra poco.": "Couldn't switch Teams Remix on: Teams was reopened as normal. Try again in a moment.",
    "Teams si sta caricando...": "Teams is loading...",
    "Fatto! Teams Remix e' attivo (tema '{name}').": "Done! Teams Remix is on (theme '{name}').",
    "Teams ci mette un po' a caricarsi: Teams Remix arriva da solo appena e' pronto.": "Teams is taking a while to load: Teams Remix shows up by itself as soon as it's ready.",
    "Una finestra di Teams si era ricaricata: ho rimesso tutto.": "A Teams window had reloaded: everything is back.",
    "Teams si e' appena aperto: lo riapro per accendere Teams Remix...": "Teams just opened: reopening it to switch Teams Remix on...",
    "Sei in call: Teams Remix si accende da solo a call finita.": "You're in a call: Teams Remix switches on by itself when the call ends.",
    "Teams si sta ancora caricando: Teams Remix arriva da solo.": "Teams is still loading: Teams Remix shows up by itself.",
    "Riapro Teams per accendere Teams Remix (pochi secondi)...": "Reopening Teams to switch Teams Remix on (a few seconds)...",
    "Apro Teams e accendo Teams Remix...": "Opening Teams and switching Teams Remix on...",
    "Il tema originale di Teams non ha effetti: scegli un altro tema.": "Teams' original theme has no effects: pick another theme.",
    "Effetti partiti su Teams: guarda la finestra di Teams!": "Effects started on Teams: look at the Teams window!",
    "'{name}' non ha effetti: accendine qualcuno nella scheda Effetti.": "'{name}' has no effects: switch some on in the Effects tab.",
    "Coinquilini chiamati: guarda Teams!": "Housemates called: look at Teams!",
    "Scegli prima almeno un coinquilino.": "Pick at least one housemate first.",
    "Teams Remix spento: Teams e' com'era. Tema, coinquilini e soprannomi restano salvati.": "Teams Remix off: Teams is as it was. Theme, housemates and nicknames stay saved.",
    "Riapro Teams com'era...": "Reopening Teams as it was...",
    "Teams riaperto com'era, senza Teams Remix.": "Teams reopened as it was, without Teams Remix.",
    "Aspetto che parta Teams...": "Waiting for Teams to start...",
    "Accendo Teams Remix...": "Switching Teams Remix on...",
    "Spengo Teams Remix...": "Switching Teams Remix off...",
    "Faccio partire gli effetti...": "Starting the effects...",
    "Chiamo i coinquilini...": "Calling the housemates...",
    # errors shown in the app
    "Colore non valido in {k}: {v}": "Invalid colour in {k}: {v}",
    "Valore non valido per {k}: {v}": "Invalid value for {k}: {v}",
    "Il gradiente vuole 2 o 3 colori #rrggbb.": "The gradient takes 2 or 3 #rrggbb colours.",
    "Nome non valido: lettere, numeri, spazi, - e _, massimo 40 caratteri.": "Invalid name: letters, digits, spaces, - and _, at most 40 characters.",
    "Esiste gia' un tema '{name}'.": "There is already a theme '{name}'.",
    "Il tema originale di Teams non si modifica: crea un tema tuo.": "Teams' original theme can't be changed: create a theme of your own.",
    "Tema '{name}' non trovato.": "Theme '{name}' not found.",
    "'{name}' non e' un tema dell'app: non c'e' un originale da ripristinare.": "'{name}' is not one of the app's themes: there is no original to restore.",
    "Nome non valido.": "Invalid name.",
    "E' l'ultimo tema: creane un altro prima di eliminarlo.": "It's the last theme: create another one before deleting it.",
    "Modalita' non valida.": "Invalid mode.",
    "Foto non valida: usa un'immagine JPG o PNG.": "Invalid photo: use a JPG or PNG picture.",
    "Foto non valida o troppo grande.": "Invalid or too large photo.",
    # updates
    "Non c'è nessun aggiornamento da fare.": "There is no update to install.",
    "Aggiornamento non riuscito ({e}). Niente è cambiato: riprova piu' tardi.": "Update failed ({e}). Nothing changed: try again later.",
    # on Teams (screen readers) and in the readability checks
    "Chiama il capibara": "Call the capybara", "Chiama il gatto": "Call the cat", "Chiama il cane": "Call the dog",
    "Chiama la pecora": "Call the sheep", "Chiama il toro": "Call the bull", "Chiama il fantasma": "Call the ghost",
    "Chiama il robot": "Call the robot", "Chiama il camion": "Call the truck", "Chiama il Drugo": "Call the Dude",
    "Fai partire gli effetti": "Start the effects",
    "Testo arcobaleno {col}": "Rainbow text {col}",
    "Testo sullo sfondo": "Text on the background",
    "Testo secondario": "Secondary text",
    "Link sullo sfondo": "Links on the background",
    "Scritte sul pulsante {col}": "Text on the {col} button",
    "Scritte nei pulsanti colorati": "Text in coloured buttons",
    "Menzioni sullo sfondo": "Mentions on the background",
}
