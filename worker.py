"""Background worker: the only thread that talks to Teams. Keeps the selected theme applied.

The user only says 'on' or 'off'. 'on' does whatever is needed: apply if Teams can take it,
otherwise reopen Teams so that it can. Texts are for everybody, not for developers.
"""
import hashlib
import json
import queue
import threading
import time
from pathlib import Path

import teams
import theme
from i18n import tr

COLLAPSE = ("tick", "apply")
BASE_EVERY = 20  # seconds between two reads of Teams' own colours


class Worker(threading.Thread):
    def __init__(self, store, cfg):
        super().__init__(daemon=True)
        self.store = store  # ThemeStore: .current() -> (name, variants)
        self.cfg = cfg
        self.base_cache = {}  # mode -> Teams' own tokens, as last read from Teams
        self._live_base, self._live_base_at, self._live_base_port = None, 0.0, None
        self.jobs = queue.Queue()
        self.lock = threading.Lock()
        self.applied_ver = None
        self._was_running = None
        self._in_call = False  # "Teams normale durante le call": paused while Teams uses the microphone
        self._asked = None  # a click on the switch inside Teams, not handled yet (True: on, False: off)
        self.state = {"running": False, "ready": False, "on": bool(cfg.get("theme_on")), "active": False,
                      "mode": None, "busy": "", "msg": "", "msg_at": "", "call": False}

    # ---------- shared state ----------
    @property
    def want_on(self):
        return bool(self.cfg.get("theme_on"))

    def _want(self, on):
        self.cfg["theme_on"] = on
        teams.save_config(self.cfg)
        self._set(on=on)

    def _set(self, **kw):
        with self.lock:
            self.state.update(kw)

    def say(self, msg):
        self._set(msg=msg, msg_at=time.strftime("%H:%M"))

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def submit(self, kind, busy=""):
        if busy:
            self._set(busy=busy)
        self.jobs.put(kind)

    # ---------- Teams' own tokens, for the preview ----------
    def _remember(self, mode, base):
        if self.base_cache.get(mode) != base:
            self.base_cache[mode] = dict(base)
            try:
                teams.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                (teams.CONFIG_DIR / f"base-{mode}.json").write_text(json.dumps(base, sort_keys=True), encoding="utf-8")
            except OSError:
                pass

    def default_mode(self, teams_mode=None):
        """Light or dark for 'Originale di Teams': the user's choice, else Teams' own mode."""
        m = self.cfg.get("default_mode")
        return m if m in theme.MODES else (teams_mode or self.snapshot().get("mode") or "dark")

    def base_is_real(self, mode):
        return mode in self.base_cache or (teams.CONFIG_DIR / f"base-{mode}.json").exists()

    def base_for(self, mode):
        """Real tokens if Teams was ever seen in this mode, else the shipped dark tokens (mirrored for light)."""
        if mode in self.base_cache:
            return dict(self.base_cache[mode])
        f = teams.CONFIG_DIR / f"base-{mode}.json"
        try:
            self.base_cache[mode] = json.loads(f.read_text(encoding="utf-8"))
            return dict(self.base_cache[mode])
        except (OSError, ValueError):
            pass
        shipped = json.loads((Path(__file__).resolve().parent / "assets" / "base-dark.json").read_text(encoding="utf-8"))
        return shipped if mode == "dark" else theme.light_from_dark(shipped)

    # ---------- loop ----------
    def run(self):
        while True:
            try:
                job = self.jobs.get(timeout=1.5)  # a notification shows for a few seconds: catch it quickly
            except queue.Empty:
                job = "tick"
            while job in COLLAPSE:  # collapse bursts (slider drags) into one pass
                try:
                    nxt = self.jobs.get_nowait()
                except queue.Empty:
                    break
                if nxt not in COLLAPSE:
                    self.jobs.put(nxt)
                    break
                job = "apply" if "apply" in (job, nxt) else "tick"
            try:
                getattr(self, "do_" + job)()
            except Exception as e:  # keep the worker alive, show the error
                self.say(tr("Qualcosa non ha funzionato ({e}). Riprova tra poco.", e=e))
            self._refresh()

    def _refresh(self):
        try:
            port = teams.live_port(self.cfg)
            running = True if port else teams.teams_running()
        except Exception:
            port, running = None, False
        self._set(running=running, ready=bool(port), active=self.want_on and bool(port) and self.applied_ver is not None,
                  busy="")

    # ---------- the switch inside Teams ----------
    def _show_toggle(self, port, hidden=False):
        """The switch in Teams shows the same choice as "Attivo su Teams" in the app; a click on it is kept for
        do_tick. Hidden while Teams has to be normal for a call: nothing of Teams Remix during a call."""
        asked = teams.toggle_sync(port, None if hidden else teams.toggle_config(self.want_on))
        if asked is not None:
            self._asked = asked

    def _toggle_now(self):
        """After a switch on or off: the switch in Teams follows at once, not at the next check."""
        port = teams.live_port(self.cfg)
        if port:
            self._show_toggle(port, bool(self.cfg.get("off_in_call")) and teams.teams_in_call())

    # ---------- core ----------
    def _call_pause(self, port):
        """With the option on, Teams goes back to normal while it uses the microphone (a call, a meeting) and
        everything comes back by itself afterwards. Teams is never reopened for this. True while paused."""
        in_call = bool(self.cfg.get("off_in_call")) and teams.teams_in_call()
        if in_call and not self._in_call:
            self._in_call = True
            teams.remove_css(port)
            self.applied_ver = None
            self._set(call=True)
            self.say(tr("Sei in call: Teams e' normale. A call finita torna tutto da solo."))
        elif not in_call and self._in_call:
            self._in_call = False
            self._set(call=False)
            if self.want_on and self._sync(port, force=True):
                self.say(tr("Call finita: Teams Remix e' di nuovo attivo."))
        return self._in_call

    def _sync(self, port, force=False):
        """Generate the CSS for Teams' current mode and the current theme; apply where needed."""
        if self._in_call:  # paused for a call: nothing goes on Teams until it ends
            return None
        # Reading Teams' own colours switches our sheet off and on: Teams restyles the whole window twice.
        # So they are read again only every BASE_EVERY seconds (or when asked), not at every check.
        now = time.time()
        if force or not self._live_base or now - self._live_base_at > BASE_EVERY or self._live_base_port != port:
            fresh = teams.base_tokens(port)
            if not fresh:
                return None
            self._live_base, self._live_base_at, self._live_base_port = dict(fresh), now, port
        base = dict(self._live_base)
        reduced = bool(base.pop("__reduced", False))
        mode = theme.detect_mode(base)
        self._remember(mode, base)
        name, params = self.store.current()
        respect = bool(self.cfg.get("respect_reduced_motion"))
        # 'Originale di Teams': an empty sheet = Teams' own colours, the channel stays open for the next theme.
        if params is None:
            # 'Originale di Teams' unedited: nothing in Teams' own mode, the original colours of the other mode if chosen
            want = self.default_mode(mode)
            css = "/* Teams default */\n" if want == mode else theme.pin_css(self.base_for(want))
            trig = None
        else:
            # the theme looks the same whatever mode Teams is in: generate on the tokens of the theme's own mode
            native = theme.native_mode(params)
            gbase = base if native == mode else self.base_for(native)
            css = theme.generate(gbase, params, name, respect, pin_all=native != mode)
            trig = theme.trigger_config(params)
        # notification toasts: colours only (see theme.for_popups)
        popup_css = css if params is None else theme.generate(gbase, theme.for_popups(params), name, respect, pin_all=native != mode)
        nick = teams.nickname_pairs(self.cfg.get("nicknames"))
        # housemates: whatever the theme, also with Teams' original look
        pets = theme.pets_config(self.cfg.get("pets"), respect)
        css = css + theme.pets_css(self.cfg.get("pets"), respect)
        # nickname photos instead of those people's pictures, also in the notifications
        photos = teams.photo_css(self.cfg.get("nicknames"))
        css, popup_css = css + photos, popup_css + photos
        self._set(reduced=reduced, mode=mode)
        ver = hashlib.sha1((css + popup_css + json.dumps(trig) + json.dumps(nick) + json.dumps(pets)).encode()).hexdigest()[:12]
        if force or ver != self.applied_ver:
            teams.apply_css(port, css, ver, trig, popup_css, nick, pets)
            self.applied_ver = ver
            return "applied"
        return "fixed" if teams.ensure_css(port, css, ver, trig, popup_css, nick, pets) else "same"

    def _reopen_with_theme(self, why):
        self._set(busy=why)
        port = teams.restart_with_port(self.cfg)
        if not port:
            self.say(tr("Non sono riuscito ad accendere Teams Remix: Teams e' stato riaperto normale. Riprova tra poco."))
            return
        self._set(busy=tr("Teams si sta caricando..."))
        for _ in range(60):
            if teams.base_tokens(port):
                break
            time.sleep(1)
        self.applied_ver = None
        if self._sync(port, force=True):
            name, _ = self.store.current()
            self.say(tr("Fatto! Teams Remix e' attivo (tema '{name}').", name=name))
        else:
            self.say(tr("Teams ci mette un po' a caricarsi: Teams Remix arriva da solo appena e' pronto."))

    # ---------- jobs ----------
    def do_tick(self):
        port = teams.live_port(self.cfg)
        running = True if port else teams.teams_running()
        just_started = running and self._was_running is False
        self._was_running = running
        if port:
            hidden = bool(self.cfg.get("off_in_call")) and teams.teams_in_call()
            self._show_toggle(port, hidden)
            asked, self._asked = self._asked, None
            if asked is not None and not hidden and asked != self.want_on:
                # clicked in Teams: exactly as if "Attivo su Teams" had been switched in the app (same file, same steps)
                (self.do_on if asked else self.do_off)()
                return
            if self.want_on:
                if self._call_pause(port):
                    return
                r = self._sync(port)
                if r == "fixed":
                    self.say(tr("Una finestra di Teams si era ricaricata: ho rimesso tutto."))
            elif time.time() - self._live_base_at > BASE_EVERY:  # off: just keep knowing Teams' mode, rarely
                base = teams.base_tokens(port)
                self._live_base_at = time.time()
                if base:
                    reduced = bool(base.pop("__reduced", False))
                    mode = theme.detect_mode(base)
                    self._remember(mode, base)
                    self._set(reduced=reduced, mode=mode)
        elif running and just_started and self.want_on:
            # Teams was just opened by hand, without the theme: nobody is in a call yet, reopen it now.
            time.sleep(5)
            self._reopen_with_theme(tr("Teams si e' appena aperto: lo riapro per accendere Teams Remix..."))

    def do_on(self):
        self._want(True)
        port = teams.live_port(self.cfg)
        if self.cfg.get("off_in_call") and teams.teams_in_call():  # never reopen Teams, never colour it, during a call
            if port:
                self._call_pause(port)
            self.say(tr("Sei in call: Teams Remix si accende da solo a call finita."))
            return
        if port:
            self.applied_ver = None
            r = self._sync(port, force=True)
            name, _ = self.store.current()
            self.say(tr("Fatto! Teams Remix e' attivo (tema '{name}').", name=name) if r else tr("Teams si sta ancora caricando: Teams Remix arriva da solo."))
            self._toggle_now()
        elif teams.teams_running():
            self._reopen_with_theme(tr("Riapro Teams per accendere Teams Remix (pochi secondi)..."))
        else:
            self._reopen_with_theme(tr("Apro Teams e accendo Teams Remix..."))

    def do_apply(self):
        """Theme edited or another theme chosen: refresh it on Teams if the theme is on."""
        port = teams.live_port(self.cfg)
        if port and self.want_on:
            self._sync(port)

    def do_fxtest(self):
        if not self.want_on or not teams.live_port(self.cfg):
            self.do_on()
        port = teams.live_port(self.cfg)
        if not port:
            return
        self._sync(port)
        teams.test_effects(port)
        name, params = self.store.current()
        if params is None:
            self.say(tr("Il tema originale di Teams non ha effetti: scegli un altro tema."))
        elif theme.has_effects(params):
            self.say(tr("Effetti partiti su Teams: guarda la finestra di Teams!"))
        else:
            self.say(tr("'{name}' non ha effetti: accendine qualcuno nella scheda Effetti.", name=name))

    def do_pets(self):
        """'Chiamali ora' from the app."""
        if not self.want_on or not teams.live_port(self.cfg):
            self.do_on()
        port = teams.live_port(self.cfg)
        if port:
            self._sync(port)
            teams.call_pets(port)
            self.say(tr("Coinquilini chiamati: guarda Teams!") if (self.cfg.get("pets") or {}).get("who") else tr("Scegli prima almeno un coinquilino."))

    def do_off(self):
        self._want(False)
        port = teams.live_port(self.cfg)
        self.applied_ver = None
        self._in_call = False
        self._set(call=False)
        if port:
            teams.remove_css(port)  # the switch in Teams stays: it is the way to switch back on
        self.say(tr("Teams Remix spento: Teams e' com'era. Tema, coinquilini e soprannomi restano salvati."))
        self._toggle_now()

    def do_normal(self):
        self._want(False)
        self.applied_ver = None
        self._set(busy=tr("Riapro Teams com'era..."))
        teams.restart_normal(self.cfg)
        self.say(tr("Teams riaperto com'era, senza Teams Remix."))

    def do_startup(self):
        if not self.want_on:
            return
        self._set(busy=tr("Aspetto che parta Teams..."))
        for _ in range(120):
            if teams.teams_running():
                break
            time.sleep(1)
        self._was_running = True
        if teams.live_port(self.cfg):
            self.do_on()
        else:
            time.sleep(5)  # let Teams finish its own start before reopening it
            self._reopen_with_theme(tr("Accendo Teams Remix..."))
