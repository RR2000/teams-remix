import json
import os
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import theme  # noqa: E402

# Real values read from Teams (dark theme, 26/11/2026).
BASE = {
    "--colorNeutralBackground1": "#292929",
    "--colorNeutralForeground1": "#ffffff",
    "--colorNeutralForeground2": "#d6d6d6",
    "--colorNeutralBackground2": "#242424",
    "--colorBrandBackground": "#4f52b2",
    "--colorBrandForeground1": "#7f85f5",
    "--colorBrandForegroundLink": "#7f85f5",
    "--colorNeutralForegroundOnBrand": "#ffffff",
    "--colorNeutralBackgroundAlpha": "rgba(26,26,26,0.50)",
    "--colorNeutralBackground7": "#00000000",
    "--colorDefaultBackground7": "#1A1A1A",
    "--colorTeamsBrand1": "#7f85f5",
    "--colorPaletteRedBackground3": "#d13438",
    "--colorStatusSuccessForeground1": "#54b054",
    "--shadow8": "0 0 2px rgba(0,0,0,0.24), 0 4px 8px rgba(0,0,0,0.28)",
    "--borderRadiusMedium": "4px",
    "--borderRadiusCircular": "10000px",
    "--fontFamilyBase": "\"Segoe UI\", sans-serif",
    "--spacingHorizontalM": "12px",
}
LIGHT_BASE = {**BASE, "--colorNeutralBackground1": "#ffffff", "--colorNeutralForeground1": "#242424",
              "--colorNeutralBackground2": "#fafafa", "--colorNeutralForeground2": "#424242",
              "--colorBrandBackground": "#5b5fc7", "--colorPaletteRedBackground3": "#c50f1f"}
D = theme.DEFAULTS
decl = theme.declarations


class MappingTest(unittest.TestCase):
    def setUp(self):
        self.css = theme.generate(BASE, {**D, "radius": 3, "font": "'Cascadia Mono', Consolas, monospace"}, "synthwave")
        self.d = decl(self.css)

    def test_same_as_prototype_measured_on_teams(self):
        self.assertEqual(self.d["--colorNeutralBackground1"], "#39294d")
        self.assertEqual(self.d["--colorNeutralForeground1"], "#fde7ff")
        self.assertEqual(self.d["--colorBrandBackground"], "#ff02b3")
        self.assertEqual(self.d["--colorBrandForegroundLink"], "#00e5ff")
        self.assertEqual(self.d["--colorNeutralForegroundOnBrand"], "#14052b")

    def test_teams_families_and_status_colours(self):
        self.assertIn("--colorDefaultBackground7", self.d)       # the chat list panel
        self.assertEqual(self.d["--colorTeamsBrand1"][:3], "#ff")
        self.assertNotIn("--colorPaletteRedBackground3", self.d)  # meaning kept
        self.assertNotIn("--colorStatusSuccessForeground1", self.d)

    def test_alpha_radius_font_shadow(self):
        self.assertTrue(self.d["--colorNeutralBackgroundAlpha"].endswith(", 0.50)"))
        self.assertTrue(self.d["--colorNeutralBackground7"].endswith(", 0.00)"))
        self.assertEqual(self.d["--borderRadiusMedium"], "12px")
        self.assertNotIn("--borderRadiusCircular", self.d)
        self.assertIn("Cascadia Mono", self.d["--fontFamilyBase"])
        self.assertIn("rgba(255,43,214,0.384)", self.d["--shadow8"])
        self.assertNotIn("--fontFamilyBase", decl(theme.generate(BASE, dict(D))))

    def test_deterministic(self):
        self.assertEqual(theme.generate(BASE, dict(D)), theme.generate(dict(reversed(list(BASE.items()))), dict(D)))

    def test_unreadable_link_and_button_text_fixed(self):
        p, fixed = theme.resolve(BASE, {**D, "link": "#3a2a50", "on_brand": "#ff02b3"})
        self.assertEqual(sorted(fixed), ["link", "on_brand"])
        self.assertGreaterEqual(theme.contrast(p["link"], "#39294d"), 4.5)


class SameLookTest(unittest.TestCase):
    def test_native_mode(self):
        self.assertEqual(theme.native_mode(D), "dark")
        self.assertEqual(theme.native_mode({**D, "background": "#fff0fb", "text": "#2a0a3d"}), "light")

    def test_pin_all_writes_status_colours_too(self):
        css = theme.generate(BASE, dict(D), pin_all=True)
        d = decl(css)
        self.assertEqual(d["--colorPaletteRedBackground3"], "#d13438")  # the dark mode's own value, pinned
        self.assertNotIn("--spacingHorizontalM", d)                      # only colours and shadows
        self.assertIn("--colorNeutralBackground1", d)

    def test_pin_css_is_the_original_of_that_mode(self):
        d = decl(theme.pin_css(LIGHT_BASE))
        self.assertEqual(d["--colorNeutralBackground1"], "#ffffff")
        self.assertNotIn("--borderRadiusMedium", d)


class EffectsTest(unittest.TestCase):
    def test_no_effects_nothing_running(self):
        css = theme.generate(BASE, dict(D))
        self.assertNotIn("infinite", css)
        self.assertFalse(theme.has_effects(D))

    def test_colors_anim(self):
        css = theme.generate(BASE, {**D, "colors_anim": "buttons"})
        self.assertIn("@property --colorBrandBackground", css)
        self.assertIn(f"steps(6, end)", css)  # in steps: smooth animation of root tokens made Teams run at 9 frames/s
        self.assertNotIn("--colorBrandBackground", decl(css))   # animated, not frozen by !important
        self.assertNotIn("prefers-reduced-motion", css)
        self.assertIn("prefers-reduced-motion", theme.generate(BASE, {**D, "colors_anim": "buttons"}, respect_reduced_motion=True))
        self.assertIn("@property --colorNeutralForeground1", theme.generate(BASE, {**D, "colors_anim": "text"}))
        self.assertIn("tt-disco", theme.generate(BASE, {**D, "colors_anim": "all"}))
        p, _ = theme.resolve(BASE, {**D, "colors_anim": "buttons"})
        for c in theme.RAINBOW_FILL:
            self.assertGreaterEqual(theme.contrast(p["on_brand"], c), 4.5, c)

    def test_fall(self):
        css = theme.generate(BASE, {**D, "fall": "🌸👍🏽x", "fall_style": "storm"})
        self.assertIn("#tt-fx > i:nth-child(1) {", css)
        self.assertIn("tt-fall 3.5s", css)
        self.assertIn(urllib.parse.quote("👍🏽"), css)
        self.assertIn("tt-sway", theme.generate(BASE, {**D, "fall": "❄️", "fall_style": "snow"}))
        for t in theme._FALL_TILES:
            self.assertEqual(theme.FALL % t[1], 0, t)

    def test_pass(self):
        css = theme.generate(BASE, {**D, "pass": ["pizza", "capybara", "🦄", "comet"], "pass_freq": "often", "trail": True})
        for slot in theme.PASS_SLOTS:
            self.assertIn(slot + " {", css)
        # the housemates are not part of themes any more: they have their own section
        self.assertEqual(theme.passers_of({"pass": ["pizza", "capybara", "🦄", "comet"]}), ["pizza", "🦄", "comet"])
        self.assertIn("linear-gradient(180deg", css)
        self.assertNotIn("linear-gradient(180deg", theme.generate(BASE, {**D, "pass": ["pizza"]}))  # trail off by default
    def test_jiggle_and_test_rules(self):
        css = theme.generate(BASE, {**D, "jiggle": True})
        self.assertIn(".fui-Button:hover", css)
        self.assertIn("html.tt-dance .fui-Button", theme.generate(BASE, dict(D)))


class ClickModeTest(unittest.TestCase):
    def test_nothing_runs_until_the_click(self):
        p = {**D, "when": "click", "pass": ["pizza"], "fall": "🍊"}
        css = theme.generate(BASE, p)
        self.assertIn("html.tt-go #tt-fx > i:nth-child(2) {", css)
        self.assertIn("html.tt-go #tt-fx > i:nth-child(1) { opacity: .92; }", css)
        self.assertNotIn(" infinite; animation-delay", css)
        self.assertIn("#tt-trigger", css)

    def test_theme_button(self):
        self.assertEqual(theme.trigger_config({**D, "when": "click", "fall": "❄️"})["text"], "🎉")
        self.assertEqual(theme.trigger_config({**D, "when": "click", "fall": "❄️", "trigger": "🦆"})["text"], "🦆")
        self.assertEqual(theme.trigger_config({**D, "when": "click", "pass": ["capybara"], "fall": "❄️"})["text"], "🎉")  # no bowl in themes
        self.assertIsNone(theme.trigger_config({**D, "when": "click"}))  # no effects, no button
        self.assertIsNone(theme.trigger_config({**D, "when": "auto", "fall": "❄️"}))


class HousematesTest(unittest.TestCase):
    def test_sensible_defaults(self):
        p = theme.clean_pets({"who": ["cat"]})
        self.assertEqual((p["trail"], p["hearts"], p["nap"], p["scale"], p["speed"], p["names"]), (False, True, False, "m", "normal", {}))
        self.assertIsNone(theme.pets_config({"who": []}))
        self.assertEqual(theme.pets_css({"who": []}), "")

    def test_each_one_has_its_thing(self):
        for animal, mark in (("cat", "1c7ed6"), ("dog", "adb5bd"), ("capybara", "ff922b"), ("robot", "8a5a2f")):
            b = theme.pets_trigger({"who": [animal]})
            self.assertIn(mark, urllib.parse.unquote(b["svg"]), animal)
        self.assertEqual(theme.pets_trigger({"who": ["robot"]})["title"], "Call the robot")
        things = {k: theme.pets_bowls({"who": [k]})[k]["svg"] for k in theme.WALKERS}  # every housemate has its own thing
        self.assertEqual(sorted(things), sorted(["capybara", "cat", "dog", "sheep", "bull", "ghost", "robot", "truck", "dude"]))
        self.assertEqual(len(set(things.values())), len(things))
        for k in theme.WALKERS:
            self.assertTrue(theme._passer(k)[3], k)  # they all walk (the ghost floats, the truck drives)
        self.assertIsNone(theme.pets_trigger({"who": ["cat"], "when": "auto"}))
        bowls = theme.pets_bowls({"who": ["cat", "robot"]})  # one each, different
        self.assertEqual(sorted(bowls), ["cat", "robot"])
        self.assertNotEqual(bowls["cat"]["svg"], bowls["robot"]["svg"])
        self.assertEqual(theme.pets_bowls({"who": ["cat"], "when": "auto"}), {})

    def test_config_for_the_engine(self):
        cfg = theme.pets_config({"who": ["capybara", "dog", "nope"], "when": "click", "bowl": "xl", "scale": "l", "speed": "fast",
                                 "trail": True, "names": {"dog": "Fido", "x": "y"}})
        self.assertEqual(cfg["who"], ["capybara", "dog"])
        self.assertEqual(cfg["mode"], "bowl")
        self.assertEqual(cfg["bowls"]["dog"]["vmin"], theme.PET_BOWL_VMIN["xl"])  # follows the window, not pixels
        self.assertEqual(cfg["ref"], theme.PET_REF)
        self.assertEqual(theme.pets_config({"who": ["cat"]})["mode"], "live")  # living on Teams is the default
        self.assertEqual(cfg["sprites"]["capybara"]["w"], round(120 * 1.4))
        self.assertEqual(cfg["sprites"]["dog"]["name"], "Fido")
        self.assertEqual(cfg["speed"], round(theme.PET_SPEED * 1.8))
        self.assertTrue(cfg["trail"])
        self.assertEqual(theme.pets_config({"who": ["cat"], "when": "auto", "freq": "often"})["every"], theme.PET_EVERY["often"])

    def test_search_by_nickname(self):
        import teams
        js = teams.SEARCH_JS
        self.assertIn(js, teams._JS_APPLY)                    # goes to Teams with everything else
        self.assertIn("__ttSearchOff", teams._JS_REMOVE)      # and goes away when the app is switched off
        self.assertIn('attr(data-name)', js)                  # real name drawn by CSS: the nickname replacement leaves it
        self.assertIn("window.__ttPairs", js)                 # same nicknames as on screen
        self.assertIn("AUTOSUGGEST_GROUP_PRIMARYDOMAIN", js)  # inside Teams' own list, after the filter chips
        self.assertIn("out.slice(0, 2)", js)                  # at most 2 people in the nickname group
        self.assertIn("AUTOSUGGEST_SUGGESTION_TOPHITS", js)  # a click opens the person like Teams' own result
        self.assertNotIn("'Tab'", js)                         # keys stay Teams' own
        self.assertNotIn("innerHTML", js)                     # Teams forbids HTML text (Trusted Types): rows are built element by element
        self.assertIn("AUTOSUGGEST_ACTION_PEOPLECENTRICSEARCH", js)  # the magnifier does what Teams' magnifier does
        self.assertIn("never break Teams", js)                # errors only drop the nickname rows
        self.assertNotIn("SEARCH_V", js)
        self.assertNotIn("%", js)                             # it goes through %-formatting with the rest
        self.assertNotIn("setVal.call(el, it[1])", js.split("var use")[0])  # the box is written only when a name is chosen

    def test_engine_follows_the_bowl_and_lets_go_when_eating(self):
        import teams
        js = teams.PETS_ENGINE_JS
        self.assertIn("bowlAt(a)", js)          # every frame towards where the bowl is now
        self.assertIn("lets go of the bowl", js)  # once eating it does not follow any more
        self.assertIn("angry", js)                # bowl taken away while eating
        self.assertIn("storm cloud", js)          # ...and leaves angry, with a storm cloud over its head
        self.assertIn("comes back later", js)     # living ones come back
        self.assertIn("call(kind)", js)           # each bowl calls its own housemate
        self.assertIn("picked up", js)            # housemates can be dragged...
        self.assertIn("it lands there, or is cross", js)  # ...and land where let go (cross if it was eating)
        self.assertIn("goes for a walk outside", js)  # a living pet goes out and comes back
        self.assertIn("not always from the same place", js)
        self.assertIn("still cross", js)           # called with the bowl while cross: it peeks out, glares, does not come
        self.assertIn("facing the bowl", js)       # eats with its nose towards the bowl, from either side
        self.assertIn("the food brings it back", js)  # the bowl calls it back when it is only out for a walk
        self.assertIn("you offended me", js)
        self.assertIn("just peeks in from its edge, shows it is cross, backs off", js)  # slides in, no popping out of nowhere
        self.assertIn("never turns round", js)
        self.assertIn("picked up while cross: it struggles", js)
        self.assertIn("teasing it does not make it longer", js)
        self.assertIn("MAX_AWAY = 30000", js)  # never away for more than 30 seconds
        self.assertIn("no cuddles while cross", js)
        self.assertIn("never two of the same", js)
        self.assertIn("Teams window resized: everything follows the new size", js)
        self.assertNotRegex(js + teams._JS_APPLY, r"\.title\s*=")  # no hover tooltips on Teams
        for line in (js + teams._JS_APPLY).splitlines():  # no code swallowed by a // comment (the bowls once lost their drawing)
            if "//" in line and "://" not in line:
                self.assertNotRegex(line.split("//", 1)[1], r"\b[a-z]\.style\.|\w+\(.*\);", line.strip())
        self.assertIn("b.style.backgroundImage = 'url(\"' + info.svg", js)
        self.assertIn("still cross while on the screen", js)  # a second click during the scene does not bring it
        self.assertIn("whoever is cross stays cross", js)     # changing settings does not make it forgive
        self.assertIn("not those hiding because they are cross", js)  # the keeper does not bring it back
        self.assertIn("it stays with you", js)        # after eating it does not go out for a while
        self.assertNotIn("%", js)                 # _JS_APPLY is filled with the % operator
        self.assertIn("__ttPetsSetup(pets)", teams._JS_APPLY)
        self.assertIn("__ttPetsSetup(null)", teams._JS_REMOVE)

    def test_injected_script_is_valid_javascript(self):
        import shutil, subprocess, teams
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        js = teams._apply_js("", "v", theme.trigger_config({**D, "when": "click", "fall": "x"}), [["a", "b"]],
                             theme.pets_config({"who": ["cat", "robot"], "when": "live", "trail": True, "names": {"cat": "Micio"}}))
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(js + "\n" + teams._JS_REMOVE + "\n" + teams._JS_TEST + "\n" + teams._JS_BASE + "\n")
        try:
            r = subprocess.run([node, "--check", f.name], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
        finally:
            os.unlink(f.name)

    def test_styles(self):
        css = theme.pets_css({"who": ["cat"]})
        self.assertIn("#tt-pets .tt-pet", css)
        self.assertIn(".tt-bowl", css)
        self.assertIn("tt-pet-angry", css)
        self.assertIn("tt-pet-trail", css)

class PopupTest(unittest.TestCase):
    def test_notification_gets_colours_only(self):
        p = {**D, "bg_mode": "gradient_anim", "glass": 50, "fall": "❄️", "pass": ["pizza"], "jiggle": True, "colors_anim": "all"}
        css = theme.generate(BASE, theme.for_popups(p))
        self.assertNotIn("html::before", css)
        self.assertNotIn("#tt-fx > i:nth-child", css)
        self.assertNotIn("tt-disco", css)
        self.assertTrue(decl(css)["--colorNeutralBackground1"].startswith("#"))  # opaque card
        self.assertEqual(decl(css)["--colorNeutralBackground1"], "#39294d")       # same colours as the theme

    def test_toast_window_is_recognised(self):
        import teams
        toast = {"url": "about:blank?entityType=toasts&windowId=x"}
        self.assertEqual(teams._for(toast, "MAIN", {"x": 1}, "POPUP"), ("POPUP", None))
        self.assertEqual(teams._for({"url": "https://teams.microsoft.com/v2/"}, "MAIN", {"x": 1}, "POPUP"), ("MAIN", {"x": 1}))


class NicknameTest(unittest.TestCase):
    def test_pairs(self):
        import teams
        pairs = teams.nickname_pairs([{"from": "Verdi, Luna", "to": "Lunetta"}, {"from": "Anna", "to": "Annina"},
                                      {"from": "  ", "to": "x"}, {"from": "Same", "to": "Same"}])
        self.assertEqual(pairs, [["Verdi, Luna", "Lunetta"], ["Luna Verdi", "Lunetta"], ["Verdi Luna", "Lunetta"], ["Anna", "Annina"]])
        # written 'Surname Name', without the comma: Teams' 'Surname, Name' (company) and 'Name Surname' (guests) too
        got = dict(teams.nickname_pairs([{"from": "Bianchi Marco", "to": "Il Bianco"}]))
        self.assertEqual(got, {"Bianchi Marco": "Il Bianco", "Bianchi, Marco": "Il Bianco", "Marco Bianchi": "Il Bianco"})
        # what is written exactly wins over a form worked out for somebody else
        got = dict(teams.nickname_pairs([{"from": "Rossi Anna", "to": "A"}, {"from": "Anna Rossi", "to": "B"}]))
        self.assertEqual((got["Rossi Anna"], got["Anna Rossi"]), ("A", "B"))

    def test_script_never_touches_what_the_user_types(self):
        import teams
        self.assertIn("isContentEditable", teams._JS_APPLY)
        self.assertIn("TEXTAREA", teams._JS_APPLY)
        self.assertIn("window.__ttPairs = []", teams._JS_REMOVE)  # names come back when switched off

    def test_photo_instead_of_the_picture(self):
        import base64
        import teams
        old = teams.PHOTOS_DIR
        teams.PHOTOS_DIR = Path(tempfile.mkdtemp()) / "photos"
        try:
            name = teams.save_photo("data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff" + b"x" * 50).decode())
            self.assertTrue(teams.valid_photo_name(name))                      # copied into the app's folder
            css = teams.photo_css([{"from": "Verdi Luna", "to": "Lunetta", "photo": name}])
            self.assertIn('displayname=Verdi%2C%20Luna&', css)                 # company people: 'Surname, Name'
            self.assertIn('displayname=Luna%20Verdi"', css)                    # guests: 'Name Surname'
            self.assertIn('content: url("data:image/jpeg;base64,', css)
            self.assertNotIn("usersInfo", css)                                 # group pictures stay as they are
            with self.assertRaises(ValueError):
                teams.save_photo("data:image/svg+xml;base64,PHN2Zz4=")         # pictures only, no drawings with code
            with self.assertRaises(ValueError):
                teams.save_photo("data:image/png;base64," + base64.b64encode(b"not a png").decode())
            self.assertEqual(teams.photo_css([{"from": "X Y", "to": "Z", "photo": "../../evil.jpg"}]), "")
            teams.clean_photos([])                                             # just added: kept for its save
            self.assertTrue((teams.PHOTOS_DIR / name).exists())
        finally:
            teams.PHOTOS_DIR = old

    def test_real_names_in_teams_search(self):
        import teams
        self.assertIn("e.id.indexOf('ms-searchux') === 0", teams._JS_APPLY)  # Teams' search results keep the real names
        self.assertIn("back to the real name", teams._JS_APPLY)              # and those already changed come back
        self.assertNotIn("NICK_V)", teams._JS_APPLY)                         # the version is filled in


class LanguagesTest(unittest.TestCase):
    """English in the code, Italian in a table: every text that goes through the table has its Italian."""

    def test_python_texts_have_italian(self):
        import re
        import i18n
        missing = []
        for f in ("worker.py", "server.py", "teams.py", "theme.py"):
            src = (ROOT / f).read_text(encoding="utf-8")
            for m in re.finditer(r'\btr\("((?:[^"\\]|\\.)*)"', src):
                key = json.loads('"' + m.group(1) + '"')
                if key not in i18n.IT:
                    missing.append((f, key))
            for label in re.findall(r'"(Call the [^"]+)"', src):  # the bowl labels are translated where they are used
                if label not in i18n.IT:
                    missing.append((f, label))
        self.assertEqual(missing, [])

    def test_window_texts_have_italian(self):
        import re
        html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
        table = html[html.index("const IT = {"):html.index("};", html.index("const IT = {"))]
        it = {json.loads('"' + k + '"') for k in re.findall(r'"((?:[^"\\]|\\.)*)":\s*"', table)}
        used = {json.loads('"' + k + '"') for k in re.findall(r'\bt\("((?:[^"\\]|\\.)*)"', html)}
        self.assertEqual(sorted(used - it), [])

    def test_switch_language(self):
        import i18n
        try:
            i18n.set_lang("it")
            self.assertEqual(i18n.tr("Done! Teams Remix is on (theme '{name}').", name="notte"), "Fatto! Teams Remix e' attivo (tema 'notte').")
            self.assertEqual(theme.pets_trigger({"who": ["robot"]})["title"], "Chiama il robot")  # labels on Teams follow
            self.assertEqual(i18n.tr("not in the table"), "not in the table")                    # missing: stays English
        finally:
            i18n.set_lang("en")
        self.assertEqual(i18n.resolve("auto"), i18n.windows_lang())


class UpdaterTest(unittest.TestCase):
    """New releases from GitHub, installed in place of the app's files only."""

    def make_zip(self, files):
        import io
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for n, data in files.items():
                z.writestr(n, data)
        return buf.getvalue()

    def release(self, version):
        import updater
        return self.make_zip({**{n: f"new {n}" for n in updater.NEEDED}, "VERSION": version + "\n", "i18n.py": "new"})

    def test_versions_are_dates(self):
        import updater
        self.assertTrue(updater.newer("v2026.11.27", "2026.11.26"))
        self.assertTrue(updater.newer("2026.11.26.2", "2026.11.26"))   # the second release of the day
        self.assertTrue(updater.newer("2026.12.1", "2026.11.30"))      # numbers, not text: 12 > 11
        self.assertFalse(updater.newer("2026.11.26", "2026.11.26"))
        self.assertFalse(updater.newer("2026.11.26", None))            # a copy without version is never offered one
        self.assertFalse(updater.newer("nonsense", "2026.11.26"))

    def test_install_replaces_the_app_and_keeps_the_old_one(self):
        import updater
        tmp = Path(tempfile.mkdtemp())
        app, backup = tmp / "app", tmp / "backup"
        for n in updater.NEEDED:
            (app / n).parent.mkdir(parents=True, exist_ok=True)
            (app / n).write_text(f"old {n}", encoding="utf-8")
        (app / "VERSION").write_text("2026.11.26\n", encoding="utf-8")
        self.assertEqual(updater.install(self.release("2026.11.27"), app, backup), "2026.11.27")
        self.assertEqual((app / "server.py").read_text(encoding="utf-8"), "new server.py")
        self.assertEqual((app / "VERSION").read_text(encoding="utf-8").strip(), "2026.11.27")
        self.assertEqual((backup / "2026.11.26" / "server.py").read_text(encoding="utf-8"), "old server.py")  # can go back
        saved = updater.BACKUP_DIR
        updater.BACKUP_DIR = tmp / "elsewhere"   # the backup folder is read when installing, not when loading
        try:
            updater.install(self.release("2026.11.28"), app)
        finally:
            updater.BACKUP_DIR = saved
        self.assertTrue((tmp / "elsewhere" / "2026.11.27" / "server.py").exists())

    def test_refuses_what_is_not_a_release(self):
        import updater
        tmp = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError):
            updater.install(self.make_zip({"VERSION": "2026.11.27", "x.py": ""}), tmp, tmp / "b")      # not the app
        with self.assertRaises(ValueError):
            updater.install(self.make_zip({**{n: "" for n in updater.NEEDED}, "VERSION": "2026.11.27",
                                           "../evil.py": ""}), tmp, tmp / "b")                       # outside the folder
        with self.assertRaises(ValueError):
            updater.download_and_install("https://example.com/teams-remix.zip")                       # only from the repo

    def test_release_zip_has_the_version_and_only_the_app(self):
        import zipfile
        sys.path.insert(0, str(ROOT / "tools"))
        import package
        out = Path(tempfile.mkdtemp()) / "r.zip"
        package.build("2026.11.27", out)
        names = zipfile.ZipFile(out).namelist()
        self.assertIn("VERSION", names)
        self.assertIn("teams_theme.pyw", names)
        self.assertIn("LICENSE", names)
        self.assertFalse([n for n in names if n.startswith(("tests/", "tools/", ".github/"))])


class ThemesFolderTest(unittest.TestCase):
    def test_own_themes_move_to_appdata_once(self):
        import teams
        tmp = Path(tempfile.mkdtemp())
        old, saved = tmp / "app" / "themes", teams.THEMES_DIR
        old.mkdir(parents=True)
        (old / "mio.json").write_text("{}", encoding="utf-8")
        teams.THEMES_DIR = tmp / "appdata" / "themes"
        try:
            teams.migrate_themes(old)
            self.assertTrue((teams.THEMES_DIR / "mio.json").exists())  # with the other personal things
            self.assertFalse(old.exists())                              # nothing of yours next to the app
            (teams.THEMES_DIR / "mio.json").write_text('{"x": 1}', encoding="utf-8")
            old.mkdir(); (old / "mio.json").write_text("{}", encoding="utf-8")
            teams.migrate_themes(old)                                   # once: what is in APPDATA wins
            self.assertEqual((teams.THEMES_DIR / "mio.json").read_text(encoding="utf-8"), '{"x": 1}')
        finally:
            teams.THEMES_DIR = saved


class CallTest(unittest.TestCase):
    """'During calls, normal Teams': everything off while Teams uses the microphone, back by itself after."""

    def setUp(self):
        import teams
        import worker
        self.teams, self.worker = teams, worker
        self.saved = teams.teams_in_call, teams.remove_css, teams.restart_with_port
        self.removed, self.reopened, self.call = [], [], [True]
        teams.teams_in_call = lambda: self.call[0]
        teams.remove_css = lambda port: self.removed.append(port)
        teams.restart_with_port = lambda cfg: self.reopened.append(1)

    def tearDown(self):
        self.teams.teams_in_call, self.teams.remove_css, self.teams.restart_with_port = self.saved

    def make(self, option):
        w = self.worker.Worker(store=None, cfg={"theme_on": True, "off_in_call": option})
        w._synced = []
        w._sync = lambda port, force=False, _orig=w._sync: (w._synced.append(force), None if w._in_call else "applied")[1]
        return w

    def test_paused_during_a_call_and_back_after(self):
        w = self.make(True)
        self.assertTrue(w._call_pause(9))
        self.assertEqual(self.removed, [9])                 # Teams goes back to normal at once
        self.assertTrue(w.snapshot()["call"])
        self.assertTrue(w._call_pause(9))
        self.assertEqual(self.removed, [9])                 # only once
        self.call[0] = False
        self.assertFalse(w._call_pause(9))
        self.assertEqual(w._synced, [True])                  # everything back by itself
        self.assertFalse(w.snapshot()["call"])

    def test_option_off_changes_nothing(self):
        w = self.make(False)
        self.assertFalse(w._call_pause(9))
        self.assertEqual(self.removed, [])

    def test_switching_on_in_a_call_never_reopens_teams(self):
        w = self.make(True)
        self.teams.live_port, saved = (lambda cfg: None), self.teams.live_port
        save = self.teams.save_config
        self.teams.save_config = lambda cfg: None
        try:
            w.do_on()
        finally:
            self.teams.live_port, self.teams.save_config = saved, save
        self.assertEqual(self.reopened, [])
        self.assertIn("call", w.snapshot()["msg"])


class TeamsSwitchTest(unittest.TestCase):
    """The switches inside Teams, next to 'Collapse app bar': 'On in Teams' and, under it, themes (with effects),
    housemates and nicknames, the same choices as in the app."""

    def setUp(self):
        import teams
        import worker
        self.teams, self.worker = teams, worker
        names = ("toggle_sync", "live_port", "remove_css", "save_config", "teams_in_call", "teams_running", "base_tokens")
        self.saved = {n: getattr(teams, n) for n in names}
        self.shown, self.clicks, self.removed, self.saves, self.call = [], [], [], [], [False]

        def toggle_sync(port, cfg):
            self.shown.append(cfg)
            return self.clicks.pop(0) if self.clicks else None
        teams.toggle_sync = toggle_sync
        teams.live_port = lambda cfg: 9
        teams.remove_css = lambda port: self.removed.append(port)
        teams.save_config = lambda cfg: self.saves.append(json.loads(json.dumps(cfg)))
        teams.teams_in_call = lambda: self.call[0]
        teams.teams_running = lambda: True
        teams.base_tokens = lambda port: None

    def tearDown(self):
        for n, f in self.saved.items():
            setattr(self.teams, n, f)

    def make(self, on, option=False, sections=None):
        class Store:
            def current(self):
                return "notte", None
        cfg = {"theme_on": on, "off_in_call": option}
        if sections is not None:
            cfg["sections"] = sections
        w = self.worker.Worker(store=Store(), cfg=cfg)
        w._synced = []
        w._sync = lambda port, force=False: (w._synced.append(dict(self.teams.sections_of(w.cfg))), None if w._in_call else "applied")[1]
        return w

    @staticmethod
    def click(what, on):
        return {"what": what, "on": on}

    def test_what_the_switches_say_in_both_languages(self):
        cfg = self.teams.toggle_config(True, {"pets": False})
        self.assertEqual(cfg["on"], True)
        self.assertEqual(cfg["sections"], {"themes": True, "pets": False, "nicknames": True})
        it, en = cfg["texts"]["it"], cfg["texts"]["en"]
        self.assertEqual(sorted(it), sorted(en))
        for k, v in it.items():                                 # every text has its English
            if v != "Teams Remix":
                self.assertNotEqual(en[k], v, k)
        for k in ("all",) + self.teams.SECTIONS:
            for kind in ("label_", "tip_on_", "tip_off_", "wait_on_", "wait_off_"):
                self.assertIn(kind + k, it)
        self.assertEqual(en["tip_off_all"], "Teams Remix is off: click to switch it on")
        self.assertEqual(en["label_pets"], "Housemates")
        self.assertIs(self.teams.toggle_config(0)["on"], False)
        self.assertIn("documentElement.lang", self.teams.TOGGLE_JS)  # Teams' language picks, like the search group

    def test_older_settings_have_everything_on(self):
        self.assertEqual(self.teams.sections_of({}), {"themes": True, "pets": True, "nicknames": True})
        self.assertEqual(self.teams.sections_of({"sections": "rotto"}), {"themes": True, "pets": True, "nicknames": True})
        self.assertEqual(self.teams.sections_of({"sections": {"nicknames": False, "x": 1}}),
                         {"themes": True, "pets": True, "nicknames": False})

    def test_click_in_teams_switches_off_like_the_app(self):
        w = self.make(True)
        self.clicks.append(self.click("all", False))
        w.do_tick()
        self.assertFalse(w.cfg["theme_on"])                   # the same choice the app saves
        self.assertFalse(self.saves[-1]["theme_on"])          # saved in the same file
        self.assertFalse(w.snapshot()["on"])                  # "On in Teams" in the app follows
        self.assertEqual(self.removed, [9])                   # Teams Remix goes away from Teams...
        self.assertEqual(self.shown[-1]["on"], False)         # ...the sparkle stays, showing off

    def test_click_in_teams_switches_back_on(self):
        w = self.make(False)
        self.clicks.append(self.click("all", True))
        w.do_tick()
        self.assertTrue(w.cfg["theme_on"])
        self.assertTrue(w.snapshot()["on"])
        self.assertEqual(self.shown[-1]["on"], True)
        self.assertIn("notte", w.snapshot()["msg"])           # the app says what happened, as for its own switch

    def test_same_state_clicked_twice_changes_nothing(self):
        w = self.make(True)
        self.clicks.append(self.click("all", True))           # on, off, on again before the app looked
        w.do_tick()
        self.assertTrue(w.cfg["theme_on"])
        self.assertEqual((self.removed, self.saves), ([], []))

    def test_a_part_switched_in_teams(self):
        w = self.make(True)
        self.clicks.append(self.click("pets", False))
        w.do_tick()
        self.assertEqual(self.saves[-1]["sections"], {"themes": True, "pets": False, "nicknames": True})
        self.assertTrue(w.cfg["theme_on"])                    # the rest stays on
        self.assertEqual(w._synced[-1]["pets"], False)        # Teams follows at once
        self.assertEqual(self.shown[-1]["sections"]["pets"], False)
        self.assertIn("Housemates", w.snapshot()["msg"])

    def test_a_part_clicked_while_all_is_off_does_nothing(self):
        w = self.make(False)
        self.clicks.append(self.click("themes", False))
        w.do_tick()
        self.assertEqual(self.saves, [])

    def test_change_from_the_app_shows_in_teams(self):
        w = self.make(True)
        w.do_tick()
        self.assertEqual(self.shown[-1]["on"], True)
        w.set_section("nicknames", False)                    # a part switched off in the app
        w.do_tick()
        self.assertEqual(self.shown[-1]["sections"]["nicknames"], False)
        w._want(False)                                        # "On in Teams" switched off in the app
        w.do_off()
        self.assertEqual(self.shown[-1]["on"], False)         # at once, not at the next check
        with self.assertRaises(ValueError):
            w.set_section("rotto", True)

    def test_parts_off_leave_teams_without_them(self):
        """What _sync sends to Teams with a part off: no theme, no housemates, no nicknames (nor their photos)."""
        import server
        teams, sent = self.teams, []
        saved = teams.apply_css, teams.ensure_css, teams.base_tokens
        teams.apply_css = lambda port, css, ver, trig=None, popup=None, nick=None, pets=None: sent.append((css, trig, popup, nick, pets))
        teams.ensure_css = lambda *a, **k: 0
        teams.base_tokens = lambda port: dict(BASE)
        tmp = Path(tempfile.mkdtemp())
        try:
            cfg = {"theme": "synthwave", "theme_on": True, "pets": {"who": ["cat"], "when": "live"},
                   "nicknames": [{"from": "Verdi Luna", "to": "Lunetta"}]}
            store = server.ThemeStore(tmp / "themes", cfg, ROOT / "themes-default")
            w = self.worker.Worker(store, cfg)
            w._remember = lambda mode, base: None
            w._sync(9, force=True)
            css, trig, popup, nick, pets = sent[-1]
            self.assertIn("#tt-pets", css)
            self.assertTrue(nick and pets)
            self.assertIn("--colorNeutralBackground1", css)
            cfg["sections"] = {"themes": False, "pets": False, "nicknames": False}
            w._sync(9, force=True)
            css, trig, popup, nick, pets = sent[-1]
            self.assertNotIn("--colorNeutralBackground1", css)   # Teams' own colours
            self.assertNotIn("#tt-pets", css)
            self.assertEqual((trig, nick, pets), (None, [], None))
            cfg["sections"] = {"themes": True, "pets": False, "nicknames": True}
            w._sync(9, force=True)
            css, trig, popup, nick, pets = sent[-1]
            self.assertIn("--colorNeutralBackground1", css)
            self.assertEqual(pets, None)
            self.assertTrue(nick)
        finally:
            teams.apply_css, teams.ensure_css, teams.base_tokens = saved

    def test_hidden_during_a_call_and_a_late_click_ignored(self):
        w = self.make(True, option=True)
        self.call[0] = True
        self.clicks.append(self.click("all", False))
        w.do_tick()
        self.assertIsNone(self.shown[-1])                     # Teams normal in a call: no switch either
        self.assertTrue(w.cfg["theme_on"])                    # the click just before the call does not count
        self.assertEqual(self.removed, [9])                   # paused as before
        self.call[0] = False
        w.do_tick()
        self.assertEqual(self.shown[-1]["on"], True)          # back after the call

    def test_option_off_keeps_the_switch_in_a_call(self):
        w = self.make(True, option=False)
        self.call[0] = True
        w.do_tick()
        self.assertEqual(self.shown[-1]["on"], True)

    def test_the_page_answer_is_checked(self):
        import cdp
        teams = self.teams
        teams.toggle_sync = self.saved["toggle_sync"]
        saved = cdp.pages, cdp.evaluate
        answers = []
        cdp.pages = lambda port: [{"webSocketDebuggerUrl": "ws", "url": "https://teams"}]
        cdp.evaluate = lambda ws, js: answers.pop(0)
        try:
            for bad in ({"asked": True}, {"asked": {"what": "rm -rf", "on": True}}, {"asked": {"what": "pets", "on": "yes"}}, "x"):
                answers.append(bad)
                self.assertIsNone(teams.toggle_sync(9, teams.toggle_config(True)))
            answers.append({"asked": {"what": "nicknames", "on": False, "extra": 1}})
            self.assertEqual(teams.toggle_sync(9, teams.toggle_config(True)), {"what": "nicknames", "on": False})
        finally:
            cdp.pages, cdp.evaluate = saved

    def test_script(self):
        js = self.teams.TOGGLE_JS
        self.assertIn('[data-tid="hamburger-button"]', js)  # next to Teams' own "Collapse app bar"
        self.assertIn("aria-pressed", js)                      # the state is not only a colour
        self.assertNotIn("innerHTML", js)                      # Teams refuses HTML text (Trusted Types)
        self.assertIn("if (x !== box) x.remove()", js)         # never two
        self.assertIn("another layout", js)                    # no button of Teams: nothing of ours
        self.assertIn("if (!cfg || busy()) return", js)        # after a click, the next one waits for the app
        self.assertIn("spinner()", js)                         # a spinner instead of the icon meanwhile
        self.assertIn("aria-busy", js)
        self.assertIn("never over back/forward", js)
        self.assertNotIn(self.teams.TOGGLE_ID, self.teams._JS_REMOVE)  # switching off leaves the switch
        self.assertNotIn("TOGGLE_V", js)
        self.assertIn('"on": false', self.teams._toggle_call(self.teams.toggle_config(False)))
        self.assertIn("(null)", self.teams._toggle_call(None))

    def test_script_is_valid_javascript(self):
        import shutil, subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        js = self.teams.TOGGLE_JS + ";" + self.teams._toggle_call(self.teams.toggle_config(True))
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(js + ";")
        try:
            r = subprocess.run([node, "--check", f.name], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
        finally:
            os.unlink(f.name)

    def test_switches_on_a_page(self):
        """The real script on a small fake page: their place, never two, the three only with all on, the spinner,
        one click at a time, Teams' language, no room = only the sparkle."""
        import shutil, subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(self.teams.TOGGLE_JS)
        texts = self.teams.toggle_config(True)["texts"]
        try:
            r = subprocess.run([node, str(ROOT / "tests" / "toggle_fake_dom.js"), f.name, json.dumps(texts)],
                               capture_output=True, text=True, timeout=30, encoding="utf-8")
        finally:
            os.unlink(f.name)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(out, {
            "placed": True, "boxes": 1, "buttons": 4, "nextToTeams": True, "noRoomTaken": "0 14px 0 -14px",
            "sameLook": True, "visible": ["all", "themes", "pets", "nicknames"],
            "pressed": ["true", "true", "false", "true"], "labels": ["Teams Remix", "Themes and effects", "Housemates", "Nicknames"],
            "boxesAfterRepeats": 1, "boxesAfterRedraw": 1,                     # never two, back after a redraw
            "busyAfterClick": "true", "iconAfterClick": "wait", "lockedOthers": "true",  # spinner, the others wait
            "asked": {"what": "themes", "on": False}, "askedWhileBusy": None,
            "busyAfterApp": None, "pressedAfterApp": "false", "iconAfterApp": "false",
            "visibleWithAllOff": ["all"],                                       # the three only with all on
            "tipEn": "Teams Remix is off: click to switch it on", "tipIt": "Teams Remix spento: clic per accenderlo",
            "visibleNoRoom": ["all"],                                           # back/forward too close: sparkle only
            "countHidden": 0, "placedWithout": False, "countWithout": 0})


class OneWindowTest(unittest.TestCase):
    """One window of the app: a second start shows the open one, a window whose app is gone closes itself."""

    def setUp(self):
        import server
        self.server = server
        self.saved = {n: getattr(server, n) for n in ("app_windows", "_close", "_front", "open_window")}
        self.closed, self.fronted, self.opened, self.wins = [], [], [], []
        server.app_windows = lambda: list(self.wins)
        server._close = self.closed.append
        server._front = self.fronted.append
        server.open_window = self.opened.append

    def tearDown(self):
        for n, f in self.saved.items():
            setattr(self.server, n, f)

    def test_the_app_tells_its_window_when_it_closes(self):
        import threading, urllib.request
        from http.server import ThreadingHTTPServer

        class App:
            token, closing = "tok", threading.Event()
        app = App()
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), self.server.make_handler(app))
        app.port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        saved, self.server.ALIVE_WAIT = self.server.ALIVE_WAIT, 0.2
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def alive(token="tok"):
            req = urllib.request.Request(f"http://127.0.0.1:{app.port}/api/alive", headers={"X-Token": token})
            with op.open(req, timeout=5) as r:
                return json.loads(r.read().decode())
        try:
            self.assertEqual(alive(), {"bye": False})           # still here: the window asks again
            app.closing.set()
            self.assertEqual(alive(), {"bye": True})            # closing: the window closes itself
            with self.assertRaises(urllib.error.HTTPError):
                alive("wrong")                                  # the token, as for everything else
        finally:
            self.server.ALIVE_WAIT = saved
            httpd.shutdown()
            httpd.server_close()

    def test_only_the_apps_own_windows(self):
        wins = [(1, "msedge.exe", "Teams Remix"), (2, "MSEDGE.EXE", "Teams Remix (can't be reached)"),
                (3, "msedge.exe", "Teams Remix - Personal - Microsoft Edge"),   # a normal Edge window
                (4, "notepad.exe", "Teams Remix"), (5, "msedge.exe", "Inbox"),
                (6, "msedge.exe", "Teams Remix (non raggiungibile)")]
        self.assertEqual(self.server.pick_app_windows(wins),
                         [(1, "Teams Remix"), (2, "Teams Remix (can't be reached)"), (6, "Teams Remix (non raggiungibile)")])

    def test_second_start_shows_the_open_window(self):
        self.wins = [(7, "Teams Remix (non raggiungibile)"), (8, "Teams Remix")]
        self.server.show_window("http://127.0.0.1:1/?t=x")
        self.assertEqual((self.fronted, self.opened, self.closed), ([8], [], [7]))

    def test_no_window_open_one(self):
        self.server.show_window("u")
        self.assertEqual((self.fronted, self.opened), ([], ["u"]))

    def test_fresh_start_closes_the_leftovers(self):
        self.wins = [(7, "Teams Remix (non raggiungibile)"), (8, "Teams Remix")]  # no app running: both are left over
        self.server.close_dead_windows()
        self.assertEqual(self.closed, [7, 8])

    def test_the_window_closes_itself_with_the_titles_the_start_knows(self):
        import re
        html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(re.search(r"<title>(.*?)</title>", html).group(1), self.server.APP_TITLE)
        self.assertIn('document.title = "Teams Remix (" + t("can\'t be reached") + ")"', html)
        self.assertIn('"can\'t be reached": "non raggiungibile"', html)
        self.assertEqual(self.server.DEAD_TITLES, ("Teams Remix (non raggiungibile)", "Teams Remix (can't be reached)"))
        self.assertIn("++FAILS >= 3) closeWindow()", html)      # a few seconds without the app, not one slow answer
        self.assertIn("window.close()", html)
        self.assertIn('api("/api/alive")', html)                 # also when Edge slows the window's timers down
        self.assertIn("watchApp();", html)
        start = (ROOT / "teams_theme.pyw").read_text(encoding="utf-8")
        self.assertIn("server.show_window(running)", start)
        self.assertIn("server.close_dead_windows()", start)


class JiggleTest(unittest.TestCase):
    def test_only_the_inside_moves(self):
        css = theme.generate(BASE, {**D, "jiggle": True})
        self.assertIn(".fui-Button:hover > *", css)
        self.assertNotIn(".fui-Button:hover {", css)


class BackgroundTest(unittest.TestCase):
    def test_gradient_with_direction(self):
        css = theme.generate(BASE, {**D, "bg_mode": "gradient", "glass": 40, "flow_angle": 45})
        self.assertIn("linear-gradient(45deg", css)
        self.assertTrue(decl(css)["--colorNeutralBackground1"].endswith(", 0.60)"))
        self.assertTrue(decl(css)["--colorDefaultBackground7"].endswith(", 0.60)"))

    def test_flowing_gradient_loops_by_one_period(self):
        css = theme.generate(BASE, {**D, "bg_mode": "gradient_anim", "flow_angle": 30, "flow_seconds": 4})
        self.assertIn("html::before {", css)
        self.assertIn("tt-flow 4s linear infinite", css)
        self.assertIn("rotate(-60deg) translateX(-60vmax)", css)

    def test_glass_is_capped(self):
        d = decl(theme.generate(BASE, {**D, "bg_mode": "gradient", "glass": 100}))
        self.assertTrue(d["--colorNeutralBackground1"].endswith(", 0.15)"))


class PreviewTest(unittest.TestCase):
    def test_readability(self):
        rows = {r[0]: r for r in theme.readability(BASE, dict(D), theme.generate(BASE, dict(D)))}
        self.assertGreater(rows["Text on the background"][1], 7)
        p = {**D, "colors_anim": "text"}
        rows = theme.readability(BASE, p, theme.generate(BASE, p))
        self.assertEqual(sum(r[0].startswith("Text on the #") and r[0].endswith(" button") for r in rows), 6)
        self.assertEqual(sum(r[0].startswith("Rainbow text") for r in rows), 6)

    def test_light_fallback_is_light(self):
        light = theme.light_from_dark(json.loads((ROOT / "assets" / "base-dark.json").read_text(encoding="utf-8")))
        self.assertEqual(theme.detect_mode(light), "light")


class FilesTest(unittest.TestCase):
    def test_migrations_keep_the_choices(self):
        old2 = {"dark": {"background": "#000000", "text": "#ffffff", "effects": ["rainbow", "flowers", "rain", "pizza", "jiggle"],
                         "rain": "💸", "rain_speed": 3, "bg_mode": "gradient"}, "light": {}}
        m = theme.migrate(old2)
        self.assertEqual((m["colors_anim"], m["fall"], m["fall_style"], m["pass"], m["jiggle"], m["bg_mode"]),
                         ("buttons", "💸🌸", "storm", ["pizza"], True, "gradient"))
        m = theme.migrate({"dark": "#111111", "light": "#eeeeee", "brand_hue": 10})
        self.assertEqual((m["background"], m["text"], m["brand_hue"]), ("#111111", "#eeeeee", 10))

    def test_shipped_themes(self):
        themes = theme.load_themes(ROOT / "themes-default")
        self.assertEqual(sorted(themes), ["arcobaleno", "bosco", "capibara", "carta", "discoteca", "grafite", "notte", "prato", "synthwave"])
        for name, p in themes.items():
            self.assertIn(p["group"], ("seri", "divertenti"), name)
            base = BASE if theme.native_mode(p) == "dark" else LIGHT_BASE
            for label, ratio, _ in theme.readability(base, p, theme.generate(base, p)):
                self.assertGreaterEqual(ratio, 4.5, f"{name}: {label}")
        for n in ("notte", "grafite", "carta", "bosco"):
            self.assertFalse(theme.has_effects(themes[n]), n)
        self.assertEqual(themes["capibara"]["when"], "click")

    def test_save_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            src = theme.load_themes(ROOT / "themes-default")["arcobaleno"]
            theme.save_theme(d, "x", src)
            self.assertEqual(theme.load_themes(d)["x"], src)


class StoreTest(unittest.TestCase):
    def setUp(self):
        import server
        self.server = server
        server.teams.save_config = lambda cfg: None
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = {}
        self.store = server.ThemeStore(self.tmp.name, self.cfg, ROOT / "themes-default")

    def tearDown(self):
        self.tmp.cleanup()

    def theme_of(self, name):
        return json.loads(json.dumps(self.store.listing()["themes"][name]))

    def test_first_run_copies_shipped_themes(self):
        self.assertEqual(sorted(self.store.themes), sorted(p.stem for p in (ROOT / "themes-default").glob("*.json")))

    def test_edit_is_a_draft_until_saved_then_reset(self):
        v = self.theme_of("carta"); v["text"] = "#ffffff"
        self.store.edit("carta", v)
        self.assertNotEqual(json.loads(Path(self.tmp.name, "carta.json").read_text(encoding="utf-8"))["text"], "#ffffff")
        self.store.select("carta")
        self.assertEqual(self.store.current()[1]["text"], "#ffffff")
        self.store.save("carta")
        self.assertEqual(json.loads(Path(self.tmp.name, "carta.json").read_text(encoding="utf-8"))["text"], "#ffffff")
        self.assertIn("carta", self.store.listing()["changed"])
        self.store.reset("carta")
        self.assertNotIn("carta", self.store.listing()["changed"])

    def test_back_to_saved_values_drops_the_draft(self):
        v = self.theme_of("bosco"); orig = json.loads(json.dumps(v)); v["glass"] = 70
        self.store.edit("bosco", v)
        self.assertIn("bosco", self.store.listing()["drafts"])
        self.store.edit("bosco", orig)
        self.assertNotIn("bosco", self.store.listing()["drafts"])

    def test_original_is_editable_and_saving_creates_a_new_theme(self):
        DEF = self.server.DEFAULT
        self.store.select(DEF)
        self.assertIsNone(self.store.current()[1])                 # unedited: Teams gets nothing
        self.store.edit(DEF, theme.teams_like("light"))             # unchanged starting point: still no draft
        self.assertIsNone(self.store.current()[1])
        self.store.edit(DEF, {**theme.TEAMS_LIKE, "fall": "❄️"})
        self.assertEqual(self.store.current()[1]["fall"], "❄️")    # edited: Teams shows it
        self.assertRaises(ValueError, lambda: self.store.save(DEF))
        self.store.create("mio", source=DEF)
        self.assertEqual((self.store.current()[0], self.store.current()[1]["fall"], self.store.current()[1]["group"]), ("mio", "❄️", "miei"))
        self.assertNotIn(DEF, self.store.listing()["drafts"])
        for fn in (lambda: self.store.delete(DEF), lambda: self.store.rename(DEF, "x"), lambda: self.store.reset("mio")):
            self.assertRaises(ValueError, fn)

    def test_duplicate_of_a_builtin_goes_to_mine(self):
        self.store.create("copia", variants=self.theme_of("discoteca"))
        self.assertEqual(self.store.current()[1]["group"], "miei")
        self.assertEqual(self.store.current()[1]["fall"], self.theme_of("discoteca")["fall"])

    def test_bad_input_rejected(self):
        v = self.theme_of("carta"); v["background"] = "red"
        self.assertRaises(ValueError, lambda: self.store.edit("carta", v))
        v = self.theme_of("carta"); v["when"] = "sometimes"
        self.assertRaises(ValueError, lambda: self.store.edit("carta", v))
        self.assertRaises(ValueError, lambda: self.store.create("../x"))
        self.assertRaises(ValueError, lambda: self.store.create("CARTA"))


class SymbolsTest(unittest.TestCase):
    def test_split(self):
        self.assertEqual(theme.split_symbols("💸 🍕🦄"), ["💸", "🍕", "🦄"])
        self.assertEqual(theme.split_symbols("👨‍👩‍👧ab"), ["👨‍👩‍👧", "a", "b"])
        self.assertEqual(theme.split_symbols("❤️👍🏽"), ["❤️", "👍🏽"])


if __name__ == "__main__":
    unittest.main()
