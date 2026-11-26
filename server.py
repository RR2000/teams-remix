"""Local UI server (127.0.0.1 only, secret token) + theme store + app window."""
import copy
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import urllib.request
import winreg
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import i18n
import teams
import theme
from i18n import tr

HERE = Path(__file__).resolve().parent
THEMES = teams.THEMES_DIR  # the user's themes, in APPDATA
OLD_THEMES = HERE / "themes"  # where they were before: moved once at start
THEMES_DEFAULT = HERE / "themes-default"  # the themes shipped with the app: the first ones, and "Ripristina originale"
UI = HERE / "ui" / "index.html"
ASSETS = HERE / "assets"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,39}$")
HEX6 = re.compile(r"^#[0-9a-fA-F]{6}$")
DEFAULT = "Originale di Teams"  # built in: Teams' own colours, the debug channel stays open


def clean_theme(params):
    """Validate and normalise one theme coming from the UI."""
    c = {**theme.DEFAULTS, **{k: v for k, v in (params or {}).items() if k in theme.KEYS}}
    for k in ("background", "text", "glow", "link", "on_brand"):
        if not HEX6.match(str(c[k])):
            raise ValueError(tr("Colore non valido in {k}: {v}", k=k, v=c[k]))
    c["brand_hue"] = int(c["brand_hue"]) % 360
    c["brand_sat"] = max(0.0, min(1.0, float(c["brand_sat"])))
    c["radius"] = max(1, min(6, int(c["radius"])))
    c["font"] = str(c["font"])[:120]
    for k, allowed in (("bg_mode", theme.BG_MODES), ("colors_anim", theme.COLORS_ANIM), ("fall_style", theme.FALL_STYLES),
                       ("pass_freq", theme.PASS_FREQ), ("when", theme.WHEN), ("group", theme.GROUPS)):
        if c[k] not in allowed:
            raise ValueError(tr("Valore non valido per {k}: {v}", k=k, v=c[k]))
    cols = [str(x) for x in (c["bg_colors"] or [])][:3]
    if len(cols) < 2 or not all(HEX6.match(x) for x in cols):
        raise ValueError(tr("Il gradiente vuole 2 o 3 colori #rrggbb."))
    c["bg_colors"] = cols
    c["glass"] = max(0, min(85, int(c["glass"])))
    c["flow_angle"] = int(c["flow_angle"]) % 360
    c["flow_seconds"] = max(2, min(30, int(c["flow_seconds"])))
    c["fall"] = "".join(theme.split_symbols(str(c["fall"]))[:8])
    c["pass"] = theme.passers_of(c)
    c["trigger"] = "".join(theme.split_symbols(str(c["trigger"]))[:1]) if c["trigger"] != "bowl" else "bowl"
    c["trail"], c["jiggle"], c["to_bowl"] = bool(c["trail"]), bool(c["jiggle"]), bool(c["to_bowl"])
    c["trigger_size"] = theme.trigger_size(c)
    return c


class ThemeStore:
    """Saved themes (files) + unsaved drafts (memory). Teams always shows the draft of the selected theme."""

    def __init__(self, folder, cfg, defaults_folder=None):
        self.folder = Path(folder)
        self.cfg = cfg
        self.lock = threading.Lock()
        self.defaults = theme.load_themes(defaults_folder) if defaults_folder and Path(defaults_folder).is_dir() else {}
        self.folder.mkdir(parents=True, exist_ok=True)
        if not any(self.folder.glob("*.json")):  # first run: start from the shipped themes
            for n, v in self.defaults.items():
                theme.save_theme(self.folder, n, v)
        self.themes = theme.load_themes(self.folder)
        self.drafts = {}
        if not self.themes:
            self.themes = {"synthwave": dict(theme.DEFAULTS)}
            theme.save_theme(self.folder, "synthwave", self.themes["synthwave"])
        if self.cfg.get("theme") != DEFAULT and self.cfg.get("theme") not in self.themes:
            self.cfg["theme"] = "synthwave" if "synthwave" in self.themes else sorted(self.themes)[0]

    # ---------- reads ----------
    def current(self):
        """(name, theme); theme is None for an unedited 'Originale di Teams' (Teams gets no CSS)."""
        with self.lock:
            n = self.cfg["theme"]
            if n == DEFAULT:
                return n, copy.deepcopy(self.drafts.get(DEFAULT))
            return n, copy.deepcopy(self.drafts.get(n) or self.themes[n])

    def listing(self):
        with self.lock:
            return {"selected": self.cfg["theme"], "default": DEFAULT, "default_theme": dict(theme.TEAMS_LIKE),
                    "themes": copy.deepcopy(self.themes), "drafts": copy.deepcopy(self.drafts),
                    "builtin": sorted(n for n in self.defaults if n in self.themes),
                    "changed": sorted(n for n in self.defaults if n in self.themes and self.themes[n] != self.defaults[n])}

    # ---------- helpers ----------
    def _check_new(self, name):
        if not NAME_RE.match(name or ""):
            raise ValueError(tr("Nome non valido: lettere, numeri, spazi, - e _, massimo 40 caratteri."))
        if name.lower() == DEFAULT.lower() or any(n.lower() == name.lower() for n in self.themes):
            raise ValueError(tr("Esiste gia' un tema '{name}'.", name=name))

    def _editable(self, name):
        if name == DEFAULT:
            raise ValueError(tr("Il tema originale di Teams non si modifica: crea un tema tuo."))
        if name not in self.themes:
            raise ValueError(tr("Tema '{name}' non trovato.", name=name))

    def _select(self, name):
        self.cfg["theme"] = name
        teams.save_config(self.cfg)

    # ---------- writes ----------
    def select(self, name):
        with self.lock:
            if name != DEFAULT and name not in self.themes:
                raise ValueError(tr("Tema '{name}' non trovato.", name=name))
            self._select(name)

    def edit(self, name, variants):
        """Unsaved change: Teams shows it, the file does not change.
        'Originale di Teams' can be edited too: saving it means creating a new theme (create(..., source=DEFAULT))."""
        with self.lock:
            clean = clean_theme(variants)
            if name == DEFAULT:
                if any(clean == {**theme.teams_like(m), "group": clean["group"]} for m in theme.MODES):
                    self.drafts.pop(DEFAULT, None)
                else:
                    self.drafts[DEFAULT] = clean
                return
            self._editable(name)
            if clean == self.themes[name]:
                self.drafts.pop(name, None)
            else:
                self.drafts[name] = clean

    def save(self, name):
        with self.lock:
            self._editable(name)
            if name in self.drafts:
                self.themes[name] = self.drafts.pop(name)
                theme.save_theme(self.folder, name, self.themes[name])

    def discard(self, name):
        with self.lock:
            if name != DEFAULT:
                self._editable(name)
            self.drafts.pop(name, None)

    def reset(self, name):
        with self.lock:
            self._editable(name)
            if name not in self.defaults:
                raise ValueError(tr("'{name}' non e' un tema dell'app: non c'e' un originale da ripristinare.", name=name))
            self.themes[name] = copy.deepcopy(self.defaults[name])
            self.drafts.pop(name, None)
            theme.save_theme(self.folder, name, self.themes[name])

    def create(self, name, source=None, variants=None):
        with self.lock:
            self._check_new(name)
            if variants is not None:
                base = clean_theme(variants)
            elif source == DEFAULT:
                base = copy.deepcopy(self.drafts.get(DEFAULT) or theme.TEAMS_LIKE)
            elif source in self.themes:
                base = copy.deepcopy(self.drafts.get(source) or self.themes[source])
            else:  # "Nuovo" starts from Teams' own look (the UI sends the one for Teams' current mode)
                base = dict(theme.TEAMS_LIKE)
            base["group"] = "miei"
            if source == DEFAULT:
                self.drafts.pop(DEFAULT, None)  # the edited original became this theme
            self.themes[name] = base
            theme.save_theme(self.folder, name, base)
            self._select(name)

    def rename(self, old, new):
        with self.lock:
            self._editable(old)
            if new.lower() != old.lower():
                self._check_new(new)
            elif not NAME_RE.match(new):
                raise ValueError(tr("Nome non valido."))
            self.themes[new] = self.themes.pop(old)
            if old in self.drafts:
                self.drafts[new] = self.drafts.pop(old)
            theme.save_theme(self.folder, new, self.themes[new])
            if new != old:
                (self.folder / f"{old}.json").unlink(missing_ok=True)
            if self.cfg["theme"] == old:
                self._select(new)

    def delete(self, name):
        with self.lock:
            self._editable(name)
            if len(self.themes) == 1:
                raise ValueError(tr("E' l'ultimo tema: creane un altro prima di eliminarlo."))
            del self.themes[name]
            self.drafts.pop(name, None)
            (self.folder / f"{name}.json").unlink(missing_ok=True)
            if self.cfg["theme"] == name:
                self._select(DEFAULT)


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _ok_origin(self):
            host = self.headers.get("Host", "")
            return host in (f"127.0.0.1:{app.port}", f"localhost:{app.port}")

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self._ok_origin():
                return self._send(403, {"error": "host"})
            static = {"/icon.svg": ("icon.svg", "image/svg+xml"), "/favicon.ico": ("icon.ico", "image/x-icon"),
                      "/icon-512.png": ("icon-512.png", "image/png")}
            if self.path in static:  # static, harmless: no token needed
                name, ctype = static[self.path]
                return self._send(200, (ASSETS / name).read_bytes(), ctype)
            if self.path.startswith("/photo/"):  # a nickname's photo for the app's window (an <img> cannot send the header)
                name, _, query = self.path[len("/photo/"):].partition("?")
                if f"t={app.token}" not in query:
                    return self._send(403, {"error": "token"})
                if not teams.valid_photo_name(name):
                    return self._send(404, {"error": "not found"})
                ctype = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}[Path(name).suffix]
                return self._send(200, (teams.PHOTOS_DIR / name).read_bytes(), ctype)
            if self.path.split("?")[0] == "/":
                if f"t={app.token}" not in self.path:
                    return self._send(403, {"error": "token"})
                html = UI.read_text(encoding="utf-8").replace("__TOKEN__", app.token)
                return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            if self.headers.get("X-Token") != app.token:
                return self._send(403, {"error": "token"})
            if self.path == "/api/state":
                return self._send(200, app.state())
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._ok_origin() or self.headers.get("X-Token") != app.token:
                return self._send(403, {"error": "token"})
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
                if self.path == "/api/preview":
                    return self._send(200, app.preview(body))
                if self.path == "/api/pets-preview":
                    return self._send(200, app.pets_preview(body))
                res = app.handle(self.path, body)
                return self._send(200, res if res is not None else app.state())
            except (ValueError, KeyError, TypeError) as e:
                return self._send(400, {"error": str(e)})
            except OSError as e:
                return self._send(500, {"error": str(e)})

    return Handler


class AppServer:
    def __init__(self, cfg):
        self.cfg = cfg
        i18n.set_lang(cfg.get("lang"))  # 'it', 'en' or 'auto' (Windows' language)
        self.store = ThemeStore(THEMES, cfg, THEMES_DEFAULT)
        from worker import Worker
        self.worker = Worker(self.store, cfg)
        self.token = secrets.token_urlsafe(24)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self))
        self.port = self.httpd.server_address[1]
        cfg["ui_port"], cfg["ui_token"] = self.port, self.token
        teams.save_config(cfg)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/?t={self.token}"

    def state(self):
        snap = self.worker.snapshot()
        dmode = self.worker.default_mode(snap.get("mode"))
        return {"teams": snap, "autostart": teams.autostart_enabled(),
                "lang": i18n.lang(), "lang_pref": self.cfg.get("lang") if self.cfg.get("lang") in i18n.LANGS else "auto",
                "respect_reduced_motion": bool(self.cfg.get("respect_reduced_motion")),
                "off_in_call": bool(self.cfg.get("off_in_call")), **self.store.listing(),
                "default_mode": dmode, "default_mode_real": self.worker.base_is_real(dmode),
                "nicknames": list(self.cfg.get("nicknames") or []),
                "pets": theme.clean_pets(self.cfg.get("pets")),
                "default_theme": theme.teams_like(dmode)}

    def preview(self, body):
        """The exact CSS Teams would get for this theme in this mode, on Teams' real tokens, plus readability."""
        params = clean_theme(body.get("theme") or {})
        mode = theme.native_mode(params)  # same look whatever mode Teams is in
        base = self.worker.base_for(mode)
        css = theme.generate(base, params, "anteprima", bool(self.cfg.get("respect_reduced_motion")))
        base_css = ":root, .fui-FluentProvider {\n" + "\n".join(f"  {k}: {v};" for k, v in sorted(base.items())) + "\n}\n"
        return {"css": css, "base_css": base_css, "checks": theme.readability(base, params, css),
                "trigger": theme.trigger_config(params), "real_tokens": self.worker.base_is_real(mode),
                # the unedited original: the mock already carries that mode's own tokens, so no theme CSS at all
                "default_css": ""}

    def pets_preview(self, body):
        """The housemates over the theme in use: the same CSS and the same movement engine Teams gets."""
        respect = bool(self.cfg.get("respect_reduced_motion"))
        name, params = self.store.current()
        if params is None:
            mode = self.worker.default_mode()
            base, css = self.worker.base_for(mode), ""
        else:
            mode = theme.native_mode(params)
            base = self.worker.base_for(mode)
            css = theme.generate(base, params, name, respect)
        pets = body.get("pets")
        base_css = ":root, .fui-FluentProvider {\n" + "\n".join(f"  {k}: {v};" for k, v in sorted(base.items())) + "\n}\n"
        return {"base_css": base_css, "css": css + theme.pets_css(pets, respect), "engine": teams.PETS_ENGINE_JS,
                "cfg": theme.pets_config(pets, respect)}

    def handle(self, path, body):
        w = self.worker
        if path == "/api/select":
            self.store.select(body["name"])
        elif path == "/api/edit":
            self.store.edit(body["name"], body["variants"])
        elif path == "/api/save":
            self.store.save(body["name"])
        elif path == "/api/discard":
            self.store.discard(body["name"])
        elif path == "/api/reset":
            self.store.reset(body["name"])
        elif path == "/api/create":
            self.store.create(body["name"].strip(), body.get("from"), body.get("variants"))
        elif path == "/api/rename":
            self.store.rename(body["old"], body["new"].strip())
        elif path == "/api/delete":
            self.store.delete(body["name"])
        elif path == "/api/action":
            kinds = {"on": "Accendo Teams Remix...", "off": "Spengo Teams Remix...", "normal": "Riapro Teams com'era...",
                     "fxtest": "Faccio partire gli effetti...", "pets": "Chiamo i coinquilini..."}
            if body["kind"] not in kinds:
                raise ValueError("unknown action")
            if body["kind"] in ("on", "off"):  # the choice counts at once, so the switches never jump back
                w._want(body["kind"] == "on")
            w.submit(body["kind"], tr(kinds[body["kind"]]))
            return
        elif path == "/api/autostart":
            teams.set_autostart(bool(body["on"]))
            return
        elif path == "/api/pets":
            self.cfg["pets"] = theme.clean_pets(body.get("pets"))
            teams.save_config(self.cfg)
        elif path == "/api/nicknames":
            items = []
            for it in (body.get("items") or [])[:200]:
                src, dst = str(it.get("from", ""))[:80], str(it.get("to", ""))[:80]
                item = {"from": src, "to": dst}
                if teams.valid_photo_name(it.get("photo")):
                    item["photo"] = it["photo"]
                items.append(item)
            self.cfg["nicknames"] = items
            teams.save_config(self.cfg)
            teams.clean_photos(items)
        elif path == "/api/nick-photo":  # the file is kept; the nickname points to it with the next save
            return {"photo": teams.save_photo(body.get("data"))}
        elif path == "/api/default-mode":
            if body.get("mode") not in theme.MODES:
                raise ValueError(tr("Modalita' non valida."))
            self.cfg["default_mode"] = body["mode"]
            teams.save_config(self.cfg)
            self.store.discard(DEFAULT)  # a new starting point: the old edits of the original no longer apply
        elif path == "/api/reduced-motion":
            self.cfg["respect_reduced_motion"] = bool(body["on"])
            teams.save_config(self.cfg)
        elif path == "/api/lang":
            pref = body.get("lang")
            self.cfg["lang"] = pref if pref in i18n.LANGS else "auto"
            teams.save_config(self.cfg)
            i18n.set_lang(self.cfg["lang"])
            self.worker.submit("apply")  # the labels on Teams follow
        elif path == "/api/off-in-call":
            self.cfg["off_in_call"] = bool(body["on"])
            teams.save_config(self.cfg)
            self.worker.submit("tick")  # takes effect at once, also in the middle of a call
        elif path == "/api/quit":
            threading.Timer(0.3, self.httpd.shutdown).start()
            return
        else:
            raise ValueError("unknown endpoint")
        w.submit("apply")  # whatever changed, Teams follows

    def serve(self, startup=False):
        self.worker.start()
        self.worker.submit("startup" if startup else "tick")
        self.httpd.serve_forever()


def _edge():
    for key in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(key, r"Software\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe") as k:
                p = winreg.QueryValue(k, None)
                if p and os.path.exists(p):
                    return p
        except OSError:
            pass
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if os.path.exists(p):
            return p
    return shutil.which("msedge")


def open_window(url):
    edge = _edge()
    if edge:
        subprocess.Popen([edge, f"--app={url}", "--window-size=1240,860"], creationflags=teams.NO_WINDOW)
    else:
        import webbrowser
        webbrowser.open(url)


def existing_instance(cfg):
    """URL of an already running instance, or None."""
    port, token = cfg.get("ui_port"), cfg.get("ui_token")
    if not port or not token:
        return None
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/state", headers={"X-Token": token})
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=1.5) as r:
            if r.status == 200:
                return f"http://127.0.0.1:{port}/?t={token}"
    except OSError:
        pass
    return None
