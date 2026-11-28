# Teams Remix

Themes, animated effects, housemates and nicknames for the **new Teams** on Windows.
It only changes how *you* see Teams, on your PC: nothing changes for anybody else.

[Italiano più sotto](#italiano) · The app speaks English and Italian (Options > Language, or like Windows).

## What it does
- **Themes**: colours, font, a solid, gradient or flowing-gradient background. Serious themes and silly ones;
  you edit them live and see them in Teams at once. A theme looks the same with Teams in light and dark mode.
- **Effects**: changing colours, things raining down, flyers crossing the screen (pizza, comet, any emoji),
  dancing buttons. They start by themselves or with a button in Teams.
- **Housemates**: a capybara, cat, dog, sheep, bull, ghost, robot, truck and the Dude live in your Teams.
  Each has its own thing (bowl, box of cables, milk...): click it and they come to eat. You can cuddle them and
  drag them around, and if you take the bowl away while they eat, they get offended.
- **Nicknames**: see any name the way you like, everywhere in Teams. Add a photo and it replaces that person's
  picture. Teams' search gets a small nickname section on top: one click opens the chat.
- **Options**: start with Windows, respect "reduce animations", and **normal Teams during calls**
  (everything disappears by itself while you're in a call and comes back afterwards; Teams doesn't reopen,
  the call doesn't drop).

## What you need
- Windows 10/11 with the new Teams.
- [Python 3.13](https://www.python.org/downloads/) from python.org. No other dependency.

## Install
1. Download `teams-remix.zip` from the latest [release](https://github.com/RR2000/teams-remix/releases/latest) and unpack it anywhere.
2. Double-click `teams_theme.pyw`. To keep it handy: right-click the file >
   **Show more options > Send to > Desktop (create shortcut)**.
3. Switch on **On in Teams** at the top right. The first time, Teams closes and reopens by itself
   (a few seconds): do it when you're not in a call.

**Switch in Teams**: once it's on, Teams itself has a small sparkle button at the top left, next to
"Collapse app bar": a click switches Teams Remix off or back on, the same as **On in Teams** in the app (the two always
agree). Full sparkle = on, empty crossed-out sparkle = off. It goes away during calls with "normal Teams during calls",
and when the app is closed.

**One part at a time**: with **On in Teams** on, **Themes and effects**, **Housemates** and **Nicknames** (with their
group in the search) can be switched off and on one by one, under the main switch in the app and with three more
buttons next to the sparkle in Teams (palette, paw, tag). They are all on unless you switch them off.

**Updates**: when a new version is out, the app says so at the top; **Update** installs it with one click (Teams doesn't
close, your themes and nicknames stay). Every change pushed here becomes a release by itself, numbered by date
(`2026.11.26`, `2026.11.26.2`...). A copy made with `git clone` updates with `git pull` instead.

## How it works
To colour Teams, the app reopens it with a WebView2 control channel listening only on `127.0.0.1`
(for the Teams process only, no global setting). Through it the app reads Teams' colours and adds a style sheet and a
small script for effects, housemates and nicknames. Nothing is changed on disk: once the channel is closed, Teams is
as it was.

While the channel is open, another program on your PC could read what's in Teams:
**Options > Reopen Teams as it was** closes it.

Nothing is sent anywhere. Everything that is yours (themes, nicknames, photos, settings, Teams' colours seen on the
PC) lives in `%APPDATA%\teams-remix\`, so updating the app never touches it.
`themes-default\` holds the app's themes: the first ones you get, and the ones "Restore original" goes back to.

## For tinkerers
- Tests: `python -B -m unittest discover -s tests` (the release workflow runs them too: no green, no release)
- Release zip by hand: `python tools/package.py <version> teams-remix.zip`
- Icon: `python tools/make_icon.py` (needs Pillow, only there).
- `theme.py` makes the CSS (deterministic), `teams.py` talks to Teams, `worker.py` keeps it up to date,
  `server.py` + `ui/index.html` are the app's window, `i18n.py` and the table in `ui/index.html` hold the Italian.
  Texts are written in English in the code; a text with no Italian simply shows in English.

A personal project, not affiliated with Microsoft. Teams is a trademark of Microsoft.

License: MIT (see [LICENSE](LICENSE)).

---

## Italiano

Temi, effetti animati, coinquilini e soprannomi per il **Teams nuovo** su Windows.
Cambia solo come vedi Teams tu, sul tuo PC: per gli altri non cambia niente.

### Cosa fa
- **Temi**: colori, font, sfondo a tinta unita, gradiente o gradiente che scorre. Temi seri e temi ignoranti;
  si modificano dal vivo e si vedono subito su Teams. Un tema è uguale con Teams chiaro e scuro.
- **Effetti**: colori che cambiano, cose che piovono, chi passa sullo schermo (pizza, cometa, un'emoji),
  pulsanti ballerini. Partono da soli o con un bottone su Teams.
- **Coinquilini**: capibara, gatto, cane, pecora, toro, fantasma, robot, camion e il Drugo vivono su Teams.
  Ognuno ha la sua cosa (ciotola, scatola di cavi, latte...): la clicchi e vengono a mangiare. Si accarezzano,
  si spostano, e se gli togli la ciotola mentre mangiano si offendono.
- **Soprannomi**: vedi un nome come vuoi tu, ovunque su Teams. Si può aggiungere una foto, che prende il posto
  dell'immagine di quella persona. Nella ricerca di Teams compare in cima una sezione con i soprannomi:
  un clic apre la chat.
- **Opzioni**: lingua, avvio con Windows, rispetto di "riduci animazioni", e **durante le call Teams normale**
  (tutto sparisce da solo quando sei in call e torna dopo; Teams non si riapre, la call non cade).

### Cosa serve
- Windows 10/11 con il Teams nuovo.
- [Python 3.13](https://www.python.org/downloads/) installato da python.org. Nessun'altra dipendenza.

### Installazione
1. Scarica `teams-remix.zip` dall'ultima [release](https://github.com/RR2000/teams-remix/releases/latest) ed estrailo dove vuoi.
2. Apri `teams_theme.pyw` con un doppio clic. Per averlo a portata di mano: tasto destro sul file >
   **Mostra altre opzioni > Invia a > Desktop (crea collegamento)**.
3. Accendi **Attivo su Teams** in alto a destra. La prima volta Teams si chiude e si riapre da solo
   (pochi secondi): fallo quando non sei in call.

**Interruttore su Teams**: una volta acceso, Teams stesso ha un pulsantino con una scintilla in alto a sinistra,
accanto al pulsante che comprime la barra delle app: un clic spegne o riaccende Teams Remix, come **Attivo su Teams** nell'app (i due
vanno sempre d'accordo). Scintilla piena = attivo, scintilla vuota e barrata = spento. Sparisce durante le call con
"durante le call Teams normale", e quando l'app è chiusa.

**Una parte alla volta**: con **Attivo su Teams** acceso, **Temi ed effetti**, **Coinquilini** e **Soprannomi** (con la
loro sezione nella ricerca) si spengono e si riaccendono uno per uno, sotto l'interruttore principale nell'app e con tre
pulsanti in più accanto alla scintilla su Teams (tavolozza, zampa, etichetta). Sono tutti accesi finché non li spegni.

**Aggiornamenti**: quando esce una versione nuova l'app lo dice in alto; **Aggiorna** la installa con un clic (Teams non
si chiude, temi e soprannomi restano). Ogni modifica caricata qui diventa da sola una release, numerata con la data
(`2026.11.26`, `2026.11.26.2`...). Una copia fatta con `git clone` si aggiorna invece con `git pull`.

### Come funziona
Per poter colorare Teams, l'app lo riapre con un canale di controllo di WebView2 aperto solo su `127.0.0.1`
(solo per il processo di Teams, nessuna impostazione globale). Da lì legge i colori di Teams e ci mette un foglio
di stile e un piccolo script per effetti, coinquilini e soprannomi. Teams non viene modificato su disco:
chiuso il canale, Teams torna com'era.

Finché il canale è aperto, un altro programma sul tuo PC potrebbe leggere cosa c'è in Teams:
**Opzioni > Riapri Teams com'era** lo chiude.

Niente viene mandato da nessuna parte. Tutto quello che è tuo (temi, soprannomi, foto, impostazioni, colori di
Teams visti sul PC) sta in `%APPDATA%\teams-remix\`, quindi aggiornare l'app non lo tocca.
`themes-default\` sono i temi dell'app: i primi che trovi, e quelli di "Ripristina originale".

Progetto personale, non collegato a Microsoft. Teams è un marchio di Microsoft.

Licenza: MIT (vedi [LICENSE](LICENSE)).
