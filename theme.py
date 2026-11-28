"""Theme generator: Teams' own Fluent tokens + one theme -> CSS. Pure and deterministic.

A theme is ONE set of choices; it works with Teams dark and light alike:
  neutrals (grey)               -> gradient between the darker and the lighter of background/text,
                                   so with Teams light the light colour becomes the background by itself
  brand (hue 200-275, sat>=.15) -> hue brand_hue, saturation brand_sat, same lightness
  links, text on brand          -> link / on_brand, made readable automatically when they would not be
  shadows                       -> black replaced by the glow colour
  fonts, border radius          -> font, radius multiplier
  status/palette colours        -> untouched (they carry meaning)
  background                    -> solid, gradient, moving gradient (panels made see-through by 'glass')
Effects (four blocks):
  colors_anim  off | buttons | text | all     colours that change
  fall + fall_style                           emoji that fall: snow (slow, sways) | rain | storm
  pass + pass_freq + trail                    who passes by: pizza, capybara, comet or any emoji
  jiggle                                      buttons dance on hover
Extra layers live in <div id="tt-fx"><i></i><i></i><i></i></div>, created by the injection script.
"""
from i18n import tr
import colorsys
import copy
import json
import math
import re
import urllib.parse
from pathlib import Path

MODES = ("dark", "light")
BG_MODES = ("solid", "gradient", "gradient_anim")
COLORS_ANIM = ("off", "buttons", "text", "all")
FALL_STYLES = ("snow", "rain", "storm")
PASS_FREQ = ("rare", "sometimes", "often")
PASSERS = ("pizza", "capybara", "cat", "dog", "sheep", "bull", "ghost", "robot", "truck", "dude", "comet")  # drawings; anything else in `pass` is an emoji
WALKERS = ("capybara", "cat", "dog", "sheep", "bull", "ghost", "robot", "truck", "dude")  # the "housemates": they walk on the ground and go to their thing (bowl, box)
GROUPS = ("seri", "divertenti", "miei")

DEFAULTS = {
    "background": "#14052b", "text": "#fde7ff", "brand_hue": 318, "brand_sat": 1.0, "link": "#00e5ff",
    "on_brand": "#14052b", "glow": "#ff2bd6", "font": "", "radius": 2,
    "bg_mode": "solid", "bg_colors": ["#ff4fa3", "#8f6bff", "#3fb6ff"], "glass": 35, "flow_angle": 120, "flow_seconds": 6,
    "colors_anim": "off", "fall": "", "fall_style": "snow", "pass": [], "pass_freq": "sometimes", "trail": False,
    "jiggle": False, "when": "auto", "trigger": "", "to_bowl": True, "trigger_size": 46, "group": "miei",
}
# "Teams original" as an editable starting point: black..white greys map every Teams grey to itself,
# brand hue/saturation close to Teams' violet. Unedited, Teams gets no CSS at all (exactly the original).
TEAMS_LIKE = {**DEFAULTS, "background": "#000000", "text": "#ffffff", "brand_hue": 238, "brand_sat": 0.5,
              "link": "#7f85f5", "on_brand": "#ffffff", "glow": "#000000", "font": "", "radius": 1}
TEAMS_LIKE_LIGHT = {**TEAMS_LIKE, "background": "#ffffff", "text": "#000000", "link": "#5b5fc7"}


def teams_like(mode):
    """The editable 'Teams original' for Teams' current mode."""
    return dict(TEAMS_LIKE_LIGHT if mode == "light" else TEAMS_LIKE)


def pin_css(base_tokens):
    """Teams' original look of another mode: every colour token of that mode, as it is."""
    lines = ["/* Teams original colours, pinned */", ".fui-FluentProvider, :root, body {"]
    for k in sorted(base_tokens):
        v = str(base_tokens[k]).strip()
        if k.startswith("--") and (solid_hex(v) or k.startswith("--shadow")):
            lines.append(f"  {k}: {v} !important;")
    lines.append("}")
    return "\n".join(lines) + "\n"


def native_mode(params):
    """A theme looks the same whatever mode Teams is in: dark if its background is the darker colour."""
    p = {**DEFAULTS, **params}
    return "dark" if luminance(p["background"]) <= luminance(p["text"]) else "light"
WHEN = ("auto", "click")  # effects run by themselves, or only when the button on Teams is clicked
BURST_MS = 20000          # how long one click keeps the effects going (longer than the capybara's visit)
BOWL_TURN = 6             # seconds between one animal and the next at the bowl (the first has finished eating)
KEYS = tuple(DEFAULTS)

FONTS = [
    "",  # keep Teams' font
    "'Cascadia Mono', Consolas, monospace",
    "'Comic Sans MS', 'Comic Sans', cursive",
    "Consolas, monospace",
    "'Courier New', monospace",
    "Georgia, serif",
    "'Segoe Script', cursive",
    "Impact, sans-serif",
    "'Lucida Console', monospace",
]

# Rainbow: fills behind on_brand text (pastel, readable with dark text) and text colours per mode.
RAINBOW_FILL = ("#ff6b6b", "#ffa94d", "#ffe066", "#69db7c", "#74c0fc", "#b197fc")
RAINBOW_TEXT = {"dark": RAINBOW_FILL, "light": ("#c92a2a", "#c2410c", "#8f6d00", "#2b8a3e", "#1864ab", "#6741d9")}
RAINBOW_ON_FILL = "#1a1033"
RAINBOW_FILL_TOKENS = ("--colorBrandBackground", "--colorBrandBackgroundHover", "--colorBrandBackgroundPressed",
                       "--colorBrandBackgroundSelected", "--colorCompoundBrandBackground",
                       "--colorCompoundBrandBackgroundHover", "--colorCompoundBrandBackgroundPressed",
                       "--colorTeamsBrand1", "--colorTeamsBrand1Hover", "--colorTeamsBrand1Pressed",
                       "--colorTeamsBrand1Selected")
RAINBOW_TEXT_TOKENS = ("--colorBrandForeground1", "--colorBrandForeground2", "--colorCompoundBrandForeground1",
                       "--colorCompoundBrandForeground1Hover", "--colorBrandStroke1", "--colorCompoundBrandStroke",
                       "--colorNeutralForeground2BrandSelected", "--colorNeutralForeground3BrandSelected")
TEXT_TOKENS = ("--colorNeutralForeground1", "--colorNeutralForeground2")

_HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})([0-9a-fA-F]{2})?$")
_RGBA = re.compile(r"^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(,\s*([0-9.]+))?\s*\)$")
_SHADOW_BLACK = re.compile(r"rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*([0-9.]+)\s*\)")
# colorDefault* (e.g. colorDefaultBackground7 = the chat list panel), colorTeamsBrand*, colorAvatar* are
# Teams' own families on top of Fluent: measured on Teams 26304 (26/11/2026).
_COLOR_KEYS = re.compile(r"^--(color(Neutral|Brand|Subtle|CompoundBrand|Transparent|StrokeFocus|Background|Default"
                         r"|TeamsBrand|TeamsNeutralStroke|Avatar)|backgroundCanvas|themeLoadingScreenColor)")
_RADIUS_KEYS = re.compile(r"^--borderRadius(Small|Medium|Large|XLarge|2XLarge)$")
_BRAND_TEXT = re.compile(r"^--(colorBrandForeground(1|2)|colorCompoundBrandForeground1|colorNeutralForeground[23]Brand\w*)$")
_PANEL_KEYS = re.compile(r"^--(colorNeutralBackground[1-8](Hover|Pressed|Selected)?|colorNeutralCardBackground"
                         r"(Hover|Pressed|Selected)?|colorDefaultBackground\d*|backgroundCanvas)$")


# ---------- colour helpers ----------

def parse_hex(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def luminance(hex_color):
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = parse_hex(hex_color)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def brand_preview(hue, sat=1.0, light=0.5):
    r, g, b = colorsys.hls_to_rgb((hue % 360) / 360, light, float(sat))
    return to_hex((r * 255, g * 255, b * 255))


def solid_hex(value):
    """'#rrggbb', '#rgb', '#rrggbbaa' or 'rgba(r,g,b,a)' -> '#rrggbb' (alpha ignored), else None."""
    value = (value or "").strip()
    if _HEX.match(value):
        return to_hex(parse_hex(value[:7] if len(value) >= 7 else value))
    m = _RGBA.match(value)
    return to_hex(tuple(int(m.group(i)) for i in (1, 2, 3))) if m else None


def readable(color, against, target=4.5):
    """Same hue, lightness moved away from `against` until the contrast reaches `target`."""
    if contrast(color, against) >= target:
        return color
    r, g, b = (x / 255 for x in parse_hex(color))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    step = -0.02 if luminance(against) > 0.18 else 0.02
    for _ in range(60):
        l = max(0.0, min(1.0, l + step))
        c = to_hex(tuple(x * 255 for x in colorsys.hls_to_rgb(h, l, s)))
        if contrast(c, against) >= target or l in (0.0, 1.0):
            return c
    return color


def detect_mode(base_tokens):
    bg = (base_tokens or {}).get("--colorNeutralBackground1", "")
    if not _HEX.match(bg):
        return "dark"
    return "dark" if luminance(bg[:7]) < 0.4 else "light"


def split_symbols(text):
    """Split a short string into user-visible symbols (emoji with joiners/skin tones/variation stay whole)."""
    out = []
    for ch in text or "":
        cp = ord(ch)
        glue = cp in (0x200D, 0xFE0F, 0x20E3) or 0x1F3FB <= cp <= 0x1F3FF or 0xE0020 <= cp <= 0xE007F
        if out and (glue or out[-1].endswith("‍")):
            out[-1] += ch
        elif not ch.isspace():
            out.append(ch)
    return out


# ---------- token mapping ----------

def _map_rgb(rgb, p):
    r, g, b = (c / 255 for c in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if s < 0.08 or rgb[0] == rgb[1] == rgb[2]:
        # tokens are those of the theme's own mode, so dark greys are surfaces in a dark theme, light greys in a light one
        lo, hi = sorted((p["background"], p["text"]), key=luminance)
        lo, hi = parse_hex(lo), parse_hex(hi)
        return tuple(lo[i] + (hi[i] - lo[i]) * l for i in range(3))
    if 200 <= h * 360 <= 275 and s >= 0.15:
        nr, ng, nb = colorsys.hls_to_rgb((p["brand_hue"] % 360) / 360, l, float(p["brand_sat"]))
        return (nr * 255, ng * 255, nb * 255)
    return None


def _mapped_hex(base_tokens, key, p, fallback):
    v = solid_hex(base_tokens.get(key, ""))
    if not v:
        return fallback
    m = _map_rgb(parse_hex(v), p)
    return to_hex(m) if m else v


def resolve(base_tokens, params):
    """The theme as Teams will really use it in its current mode: link and text on buttons made readable."""
    p = {**DEFAULTS, **params}
    lo = min((p["background"], p["text"]), key=luminance)
    bg1 = _mapped_hex(base_tokens, "--colorNeutralBackground1", p, p["background"])
    brand = _mapped_hex(base_tokens, "--colorBrandBackground", p, brand_preview(p["brand_hue"], p["brand_sat"]))
    fixed = {}
    link = readable(p["link"], bg1)
    if link != p["link"]:
        fixed["link"] = link
    if p["colors_anim"] in ("buttons", "text"):
        on = RAINBOW_ON_FILL
    else:
        on = p["on_brand"]
        if contrast(on, brand) < 4.5:
            on = max((on, lo, "#ffffff", "#000000"), key=lambda c: contrast(c, brand))
    if on != p["on_brand"]:
        fixed["on_brand"] = on
    return {**p, **fixed}, sorted(fixed)


def _alpha(key, alpha, p):
    """Panels become see-through when the background is a gradient."""
    if p["bg_mode"] != "solid" and _PANEL_KEYS.match(key):
        return alpha * (1 - max(0, min(85, int(p["glass"]))) / 100)
    return alpha


def _map_value(key, value, p):
    if key.startswith("--colorBrandForegroundLink"):
        return p["link"]
    if key in ("--colorNeutralForegroundOnBrand", "--colorNeutralStrokeOnBrand"):
        return p["on_brand"]
    if key.startswith("--shadow"):
        gr, gg, gb = parse_hex(p["glow"])
        return _SHADOW_BLACK.sub(lambda m: f"rgba({gr},{gg},{gb},{min(1.0, float(m.group(1)) * 1.6):.3f})", value)
    if key in ("--fontFamilyBase", "--fontFamilyNumeric"):
        return p["font"] or None
    m = re.match(r"^(\d+)px$", value)
    if _RADIUS_KEYS.match(key) and m:
        return f"{int(m.group(1)) * int(p['radius'])}px"
    if not _COLOR_KEYS.match(key):
        return None
    m = _HEX.match(value)
    if m:
        rgb, alpha = parse_hex(value[:7] if len(value) >= 7 else value), (int(m.group(2), 16) / 255 if m.group(2) else 1.0)
    else:
        m = _RGBA.match(value)
        if not m:
            return None
        rgb, alpha = tuple(int(m.group(i)) for i in (1, 2, 3)), float(m.group(5)) if m.group(5) else 1.0
    mapped = _map_rgb(rgb, p)
    a = _alpha(key, alpha, p)
    if mapped is None:
        if a == alpha:
            return None
        mapped = rgb
    if a >= 0.999:
        out = to_hex(mapped)
        if p.get("_bg1") and _BRAND_TEXT.match(key):  # mentions, selected items...: readable on the background
            out = readable(out, p["_bg1"])
        return out
    return f"rgba({round(mapped[0])}, {round(mapped[1])}, {round(mapped[2])}, {a:.2f})"


# ---------- effects: colours that change ----------

def _animated(name, groups, base_tokens, seconds):
    """@property + keyframes cycling each group of tokens through its colour list."""
    out, frames = [], []
    present = [([t for t in tokens if t in base_tokens], colors) for tokens, colors in groups]
    for tokens, _ in present:
        for t in tokens:
            out.append(f"@property {t} {{ syntax: '<color>'; inherits: true; initial-value: {base_tokens[t]}; }}")
    steps = len(groups[0][1])
    for i in range(steps + 1):
        decl = " ".join(f"{t}: {colors[i % steps]};" for tokens, colors in present for t in tokens)
        frames.append(f"  {round(100 * i / steps, 2)}% {{ {decl} }}")
    out.append(f"@keyframes {name} {{\n" + "\n".join(frames) + "\n}")
    # In steps, one colour every RAINBOW_STEP seconds: these tokens sit on the root of Teams, so every change makes
    # Teams restyle the whole window. Smooth (60 changes a second) measured 9 frames/s on Teams, off 60 (26/11/2026).
    return out, f"{name} {RAINBOW_STEP * steps}s steps({steps}, end) infinite"


RAINBOW_STEP = 3  # seconds per colour


_DISCO_CSS = """body { animation: tt-disco 5s linear infinite; }
@keyframes tt-disco { from { filter: hue-rotate(0deg) saturate(1.3); } to { filter: hue-rotate(360deg) saturate(1.3); } }"""

_JIGGLE_KEYFRAMES = """@keyframes tt-jiggle { 0%, 100% { transform: rotate(0); } 20% { transform: rotate(-6deg) scale(1.06); }
  40% { transform: rotate(5deg); } 60% { transform: rotate(-4deg); } 80% { transform: rotate(2deg); } }
@keyframes tt-spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }"""
# Only what is INSIDE the button moves: if the button itself turned, the mouse would fall off its edge, the
# hover would stop, the button would snap back under the mouse and start again (flicker, measured 26/11).
_JIGGLE_CSS = """.fui-Button:hover > *, .fui-ToggleButton:hover > *, .fui-MenuButton:hover > * { animation: tt-jiggle .45s ease-in-out; }
.fui-Avatar:hover > img, .fui-Avatar:hover > span:not([class*="badge" i]) { animation: tt-spin .7s ease-in-out; }"""


# ---------- effects: things that fall ----------

FALL = 600  # every tile height divides it, so the loop is seamless
_FALL_TILES = [  # tile w, tile h, x, y, font size, rotation
    (220, 600, 30, 80, 30, -12), (260, 300, 150, 200, 22, 10), (300, 600, 90, 420, 36, 0), (240, 200, 180, 120, 20, 18),
    (280, 300, 40, 260, 26, -20), (320, 600, 250, 500, 32, 8), (200, 150, 100, 60, 18, -6), (340, 600, 300, 300, 28, 14),
]
FALL_SECONDS = {"snow": 30, "rain": 8, "storm": 3.5}
_EMOJI_FONT = "Segoe UI Emoji, Apple Color Emoji, Noto Color Emoji, sans-serif"


def _esc(sym):
    return sym.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _emoji_tile(w, h, x, y, s, rot, sym):
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}'>"
            f"<text x='{x}' y='{y}' font-size='{s}' transform='rotate({rot} {x} {y})' font-family='{_EMOJI_FONT}'>{_esc(sym)}</text></svg>")


def _url(svg):
    return f'url("data:image/svg+xml,{urllib.parse.quote(svg)}")'


def _fall_css(symbols, style, click):
    tiles = [(_emoji_tile(*t, symbols[i % len(symbols)]), t[0], t[1]) for i, t in enumerate(_FALL_TILES)]
    sway = style == "snow"
    anim = f"tt-fall {FALL_SECONDS[style]}s linear infinite" + (", tt-sway 5s ease-in-out infinite alternate" if sway else "")
    sel = "#tt-fx > i:nth-child(1)"
    # with the button: always there but invisible, fades in for the burst
    shown = f"opacity: 0; transition: opacity .8s; }}\nhtml.tt-go {sel} {{ opacity: .92; }}" if click else "opacity: .92; }"
    return (f"{sel} {{ display: block; position: fixed; left: -40px; right: -40px; top: -{FALL}px; bottom: 0;\n"
            f"  z-index: 2147483646; pointer-events: none; background-image: {', '.join(_url(s) for s, _, _ in tiles)};\n"
            f"  background-size: {', '.join(f'{w}px {h}px' for _, w, h in tiles)}; background-repeat: repeat; will-change: transform;\n"
            f"  animation: {anim}; {shown}\n"
            f"@keyframes tt-fall {{ from {{ transform: translateY(0); }} to {{ transform: translateY({FALL}px); }} }}\n"
            "@keyframes tt-sway { from { translate: -18px 0; } to { translate: 18px 0; } }")


# ---------- effects: who passes by ----------

PIZZA_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 60 44'>"
             "<path d='M6 4 L56 22 L6 40 Z' fill='#ffd43b' stroke='#e8590c' stroke-width='2' stroke-linejoin='round'/>"
             "<rect x='1' y='2' width='9' height='40' rx='4' fill='#c97c3a' stroke='#8a4b16' stroke-width='2'/>"
             "<circle cx='16' cy='14' r='3.5' fill='#e03131'/><circle cx='15' cy='30' r='3.5' fill='#e03131'/>"
             "<circle cx='21' cy='23' r='2.5' fill='#e03131'/>"
             "<circle cx='28' cy='17' r='3' fill='#fff'/><circle cx='29' cy='17' r='1.5' fill='#000'/>"
             "<circle cx='36' cy='19.5' r='2.6' fill='#fff'/><circle cx='37' cy='19.5' r='1.3' fill='#000'/>"
             "<path d='M27 24 Q31.5 28 37 25' stroke='#000' stroke-width='1.6' fill='none' stroke-linecap='round'/>"
             "</svg>")
CAPYBARA_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 80'>"
                "<rect x='22' y='56' width='10' height='18' rx='4' fill='#7a5230'/><rect x='40' y='58' width='10' height='16' rx='4' fill='#6b4628'/>"
                "<rect x='68' y='58' width='10' height='16' rx='4' fill='#6b4628'/><rect x='84' y='56' width='10' height='18' rx='4' fill='#7a5230'/>"
                "<ellipse cx='55' cy='44' rx='42' ry='24' fill='#a8743f'/><ellipse cx='50' cy='36' rx='30' ry='10' fill='#b9844d' opacity='.6'/>"
                "<rect x='76' y='22' width='38' height='34' rx='16' fill='#a8743f'/>"
                "<rect x='98' y='33' width='20' height='21' rx='9' fill='#8a5a2f'/><circle cx='113' cy='39' r='1.7' fill='#3b2412'/>"
                "<ellipse cx='85' cy='22' rx='5' ry='4' fill='#7a5230'/>"
                "<path d='M90 35 q4 3 8 0' stroke='#1b1b1b' stroke-width='2.2' fill='none' stroke-linecap='round'/>"
                "<circle cx='94' cy='13' r='9' fill='#ff922b' stroke='#e8590c' stroke-width='1.5'/>"
                "<ellipse cx='98' cy='4.5' rx='4.5' ry='2' fill='#40c057' transform='rotate(-30 98 4.5)'/>"
                "</svg>")
# grey tabby with green eyes
CAT_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 80'>"
           "<path d='M16 46 Q2 30 12 12' stroke='#8d939a' stroke-width='7' fill='none' stroke-linecap='round'/>"
           "<rect x='26' y='56' width='9' height='18' rx='4' fill='#868c93'/><rect x='40' y='58' width='9' height='16' rx='4' fill='#737980'/>"
           "<rect x='68' y='58' width='9' height='16' rx='4' fill='#737980'/><rect x='82' y='56' width='9' height='18' rx='4' fill='#868c93'/>"
           "<ellipse cx='55' cy='46' rx='36' ry='18' fill='#9aa0a6'/>"
           "<path d='M42 30 q4 8 0 16 M54 29 q4 9 0 18 M66 31 q4 8 0 15' stroke='#6c7178' stroke-width='3' fill='none' stroke-linecap='round'/>"
           "<polygon points='80,26 83,6 94,20' fill='#9aa0a6'/><polygon points='96,19 107,6 109,26' fill='#9aa0a6'/>"
           "<polygon points='83,21 85,12 90,19' fill='#ffb3c1'/><polygon points='99,18 105,11 106,22' fill='#ffb3c1'/>"
           "<circle cx='94' cy='34' r='17' fill='#9aa0a6'/>"
           "<path d='M86 22 q2 -3 4 0 M98 21 q2 -3 4 0' stroke='#6c7178' stroke-width='2' fill='none' stroke-linecap='round'/>"
           "<ellipse cx='88' cy='32' rx='3.4' ry='4.2' fill='#40c057'/><ellipse cx='101' cy='32' rx='3.4' ry='4.2' fill='#40c057'/>"
           "<ellipse cx='88.4' cy='32' rx='1' ry='3.4' fill='#1b1b1b'/><ellipse cx='101.4' cy='32' rx='1' ry='3.4' fill='#1b1b1b'/>"
           "<circle cx='89.3' cy='30.4' r='.8' fill='#fff'/><circle cx='102.3' cy='30.4' r='.8' fill='#fff'/>"
           "<polygon points='92.5,38.5 97.5,38.5 95,41.5' fill='#ff8fab'/>"
           "<path d='M95 41.5 q-3 3 -5 1 M95 41.5 q3 3 5 1' stroke='#1b1b1b' stroke-width='1.4' fill='none' stroke-linecap='round'/>"
           "<path d='M86 39 L73 37 M86 42 L73 44 M104 39 L117 37 M104 42 L117 44' stroke='#3a3f44' stroke-width='1'/>"
           "</svg>")
DOG_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 80'>"
           "<path d='M18 40 Q6 26 14 16' stroke='#a0662d' stroke-width='7' fill='none' stroke-linecap='round'/>"
           "<rect x='26' y='54' width='10' height='20' rx='4' fill='#a0662d'/><rect x='40' y='56' width='10' height='18' rx='4' fill='#8a5525'/>"
           "<rect x='68' y='56' width='10' height='18' rx='4' fill='#8a5525'/><rect x='82' y='54' width='10' height='20' rx='4' fill='#a0662d'/>"
           "<ellipse cx='55' cy='44' rx='37' ry='19' fill='#c68642'/><ellipse cx='50' cy='51' rx='18' ry='7' fill='#e0b07a'/>"
           "<ellipse cx='94' cy='31' rx='17' ry='16' fill='#c68642'/>"
           "<ellipse cx='108' cy='38' rx='10' ry='7' fill='#e0b07a'/><circle cx='116' cy='35' r='3.2' fill='#1b1b1b'/>"
           "<ellipse cx='86' cy='33' rx='6' ry='13' fill='#7a4a1e' transform='rotate(15 86 33)'/>"
           "<circle cx='98' cy='26' r='2.7' fill='#1b1b1b'/><circle cx='99' cy='25' r='.9' fill='#fff'/>"
           "<path d='M105 44 q2 9 7 0 z' fill='#ff6b8a'/>"
           "<rect x='80' y='42' width='18' height='5' rx='2' fill='#e03131'/><circle cx='89' cy='49' r='2.5' fill='#ffd43b'/>"
           "</svg>")
SHEEP_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 80'>"
             "<g fill='#f8f9fa' stroke='#ced4da' stroke-width='1.5'>"
             "<circle cx='36' cy='46' r='12'/><circle cx='40' cy='32' r='14'/><circle cx='56' cy='26' r='15'/><circle cx='72' cy='30' r='14'/>"
             "<circle cx='82' cy='42' r='12'/><circle cx='50' cy='46' r='14'/><circle cx='68' cy='46' r='14'/><circle cx='24' cy='38' r='7'/></g>"
             "<rect x='32' y='56' width='7' height='20' rx='3' fill='#6c757d'/><rect x='45' y='58' width='7' height='18' rx='3' fill='#5a6169'/>"
             "<rect x='64' y='58' width='7' height='18' rx='3' fill='#5a6169'/><rect x='77' y='56' width='7' height='20' rx='3' fill='#6c757d'/>"
             "<rect x='32' y='73' width='7' height='3' fill='#212529'/><rect x='45' y='73' width='7' height='3' fill='#212529'/>"
             "<rect x='64' y='73' width='7' height='3' fill='#212529'/><rect x='77' y='73' width='7' height='3' fill='#212529'/>"
             "<ellipse cx='98' cy='38' rx='12' ry='14' fill='#343a40'/>"
             "<ellipse cx='87' cy='31' rx='7' ry='3.2' fill='#495057' transform='rotate(-25 87 31)'/>"
             "<ellipse cx='109' cy='31' rx='7' ry='3.2' fill='#495057' transform='rotate(25 109 31)'/>"
             "<g fill='#f8f9fa' stroke='#ced4da' stroke-width='1'><circle cx='93' cy='25' r='5'/><circle cx='99' cy='23' r='5'/><circle cx='104' cy='26' r='4.5'/></g>"
             "<circle cx='94' cy='37' r='2.6' fill='#fff'/><circle cx='103' cy='37' r='2.6' fill='#fff'/>"
             "<circle cx='94.6' cy='37.4' r='1.3' fill='#111'/><circle cx='103.6' cy='37.4' r='1.3' fill='#111'/>"
             "<path d='M95 46 q3.5 2.5 7 0' stroke='#adb5bd' stroke-width='1.4' fill='none' stroke-linecap='round'/>"
             "</svg>")
BULL_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 80'>"
            "<path d='M18 40 Q8 44 10 56' stroke='#3b2a1f' stroke-width='4' fill='none' stroke-linecap='round'/><circle cx='10' cy='58' r='3.5' fill='#111'/>"
            "<rect x='26' y='54' width='10' height='20' rx='3' fill='#3b2a1f'/><rect x='40' y='56' width='10' height='18' rx='3' fill='#2e2018'/>"
            "<rect x='68' y='56' width='10' height='18' rx='3' fill='#2e2018'/><rect x='82' y='54' width='10' height='20' rx='3' fill='#3b2a1f'/>"
            "<rect x='26' y='70' width='10' height='4' fill='#111'/><rect x='40' y='70' width='10' height='4' fill='#111'/>"
            "<rect x='68' y='70' width='10' height='4' fill='#111'/><rect x='82' y='70' width='10' height='4' fill='#111'/>"
            "<ellipse cx='55' cy='42' rx='38' ry='20' fill='#5c3d2e'/><ellipse cx='50' cy='34' rx='26' ry='8' fill='#6e4a38' opacity='.7'/>"
            "<path d='M88 28 Q80 18 86 10' stroke='#f1e3c8' stroke-width='5' fill='none' stroke-linecap='round'/>"
            "<path d='M104 26 Q113 18 108 9' stroke='#f1e3c8' stroke-width='5' fill='none' stroke-linecap='round'/>"
            "<ellipse cx='96' cy='38' rx='15' ry='14' fill='#5c3d2e'/>"
            "<ellipse cx='104' cy='47' rx='10' ry='7' fill='#c9a27e'/><circle cx='101' cy='46' r='1.5' fill='#3b2a1f'/><circle cx='107' cy='46' r='1.5' fill='#3b2a1f'/>"
            "<circle cx='104' cy='53' r='4' fill='none' stroke='#ffd43b' stroke-width='2'/>"
            "<circle cx='92' cy='34' r='2.3' fill='#111'/><circle cx='101' cy='33' r='2.3' fill='#111'/>"
            "<circle cx='92.7' cy='33.3' r='.7' fill='#fff'/><circle cx='101.7' cy='32.3' r='.7' fill='#fff'/>"
            "</svg>")
GHOST_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 90'>"
             # body with two soft little arms in the same outline: left one down, right one up waving
             "<path d='M22 82 L22 58 Q13 60 9 54 Q6 48 12 47 Q17 47 22 50 L22 40 Q22 8 50 8 Q78 8 78 40 L78 46"
             " Q84 38 89 33 Q94 29 96 34 Q97 39 92 45 Q86 52 78 56 L78 82 L70 74 L62 82 L54 74 L46 82 L38 74 L30 82 Z'"
             " fill='#f8f9fa' stroke='#ced4da' stroke-width='2' stroke-linejoin='round'/>"
             "<ellipse cx='44' cy='38' rx='5' ry='7' fill='#212529'/><ellipse cx='62' cy='38' rx='5' ry='7' fill='#212529'/>"
             "<circle cx='45.5' cy='35.5' r='1.6' fill='#fff'/><circle cx='63.5' cy='35.5' r='1.6' fill='#fff'/>"
             "<ellipse cx='53' cy='55' rx='6' ry='8' fill='#212529'/>"
             "<circle cx='36' cy='48' r='4' fill='#ffc9c9' opacity='.8'/><circle cx='70' cy='48' r='4' fill='#ffc9c9' opacity='.8'/>"
             "</svg>")
TRUCK_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 130 80'>"
             "<rect x='6' y='12' width='80' height='48' rx='5' fill='#ff922b' stroke='#e8590c' stroke-width='2'/>"
             "<rect x='14' y='22' width='64' height='8' rx='3' fill='#ffd8a8'/><rect x='14' y='36' width='40' height='6' rx='3' fill='#ffd8a8'/>"
             "<path d='M86 28 h20 q6 0 9 6 l6 12 v14 h-35 z' fill='#4dabf7' stroke='#1c7ed6' stroke-width='2' stroke-linejoin='round'/>"
             "<path d='M92 33 h13 q3 0 5 4 l3 7 h-21 z' fill='#e7f5ff'/>"
             "<rect x='118' y='52' width='8' height='6' rx='2' fill='#adb5bd'/><circle cx='121' cy='47' r='2.4' fill='#ffe066'/>"
             "<rect x='4' y='58' width='120' height='5' rx='2' fill='#495057'/>"
             "<circle cx='30' cy='64' r='10' fill='#343a40'/><circle cx='30' cy='64' r='4' fill='#adb5bd'/>"
             "<circle cx='104' cy='64' r='10' fill='#343a40'/><circle cx='104' cy='64' r='4' fill='#adb5bd'/>"
             "</svg>")
ROBOT_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 104 84'>"
             "<circle cx='30' cy='74' r='8' fill='#495057'/><circle cx='30' cy='74' r='3' fill='#adb5bd'/>"
             "<circle cx='70' cy='74' r='8' fill='#495057'/><circle cx='70' cy='74' r='3' fill='#adb5bd'/>"
             "<rect x='14' y='36' width='72' height='34' rx='8' fill='#74c0fc' stroke='#1c7ed6' stroke-width='2'/>"
             "<rect x='24' y='45' width='32' height='15' rx='3' fill='#e7f5ff'/>"
             "<circle cx='31' cy='52.5' r='2.6' fill='#ff6b6b'/><circle cx='40' cy='52.5' r='2.6' fill='#ffd43b'/><circle cx='49' cy='52.5' r='2.6' fill='#69db7c'/>"
             "<rect x='82' y='45' width='14' height='6' rx='3' fill='#1c7ed6'/>"
             "<path d='M96 44 l5 -4 M96 52 l5 4' stroke='#1c7ed6' stroke-width='3' stroke-linecap='round'/>"
             "<rect x='46' y='28' width='8' height='9' fill='#1c7ed6'/>"
             "<rect x='30' y='6' width='46' height='24' rx='7' fill='#a5d8ff' stroke='#1c7ed6' stroke-width='2'/>"
             "<rect x='39' y='11' width='31' height='13' rx='4' fill='#1b1b1b'/>"
             "<circle cx='49' cy='17.5' r='3' fill='#69db7c'/><circle cx='62' cy='17.5' r='3' fill='#69db7c'/>"
             "<line x1='53' y1='6' x2='53' y2='2' stroke='#1c7ed6' stroke-width='2'/><circle cx='53' cy='2.5' r='2.5' fill='#ff6b6b'/>"
             "</svg>")
# the Drugo: long hair, beard, dark glasses, open dressing gown on a vest, shorts, sandals; he goes for his milk
DUDE_SVG = (
            "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 90 130'>"
            "<path d='M33 92 L30 118' stroke='#d39a76' stroke-width='8' stroke-linecap='round'/>"
            "<path d='M22 121 Q30 117 38 121 L38 124 L22 124 Z' fill='#7a4b24'/>"
            "<path d='M50 92 L55 118' stroke='#eab894' stroke-width='8' stroke-linecap='round'/>"
            "<ellipse cx='59' cy='120' rx='7' ry='3' fill='#eab894'/>"
            "<path d='M47 121 Q56 116 67 121 L67 124 L47 124 Z' fill='#8b5a2b'/>"
            "<path d='M52 119 Q57 115 62 119' stroke='#6b3f1d' stroke-width='2.5' fill='none'/>"
            "<path d='M26 80 L62 80 L63 96 L49 97 L44 88 L40 97 L25 96 Z' fill='#2b2a30'/>"
            "<path d='M30 40 Q20 44 19 62 L16 102 Q28 106 42 103 L44 42 Z' fill='#946471'/>"
            "<path d='M42 42 L56 42 L58 82 L42 82 Z' fill='#f1dde2'/>"
            "<path d='M45 42 L49.5 51 L54 42 Z' fill='#d39a76'/>"
            "<path d='M43.5 43 L42.5 102' stroke='#a87482' stroke-width='1.6'/>"
            "<path d='M50 41 Q61 41 64 50 L68 100 Q62 103 57 101 L55 62 Q54 49 50 45 Z' fill='#b4808c'/>"
            "<path d='M50.5 44 Q54 50 55 62 L56.5 100' stroke='#c7979f' stroke-width='2.2' fill='none'/>"
            "<path d='M58 45 Q67 50 67 66 L68 80 Q64 83 60 81 L59 66 Q57 54 55 50 Z' fill='#c7979f'/>"
            "<ellipse cx='64.5' cy='85' rx='4.5' ry='5' fill='#eab894'/>"
            "<path d='M44 33 L54 33 L53 43 L45 43 Z' fill='#d39a76'/>"
            "<path d='M40 42 Q47 36 56 41' stroke='#c7979f' stroke-width='3.5' fill='none' stroke-linecap='round'/>"
            "<path d='M40 9 Q50 3 58 8 Q62 12 60 16 Q52 14 47 18 Q43 26 43 36 Q42 46 37 52 Q30 54 27 48 Q24 38 28 24 Q32 13 40 9 Z' fill='#6b4423'/>"
            "<path d='M31 22 Q28 34 31 46 M36 18 Q33 32 35 48' stroke='#87592f' stroke-width='1.6' fill='none' stroke-linecap='round'/>"
            "<ellipse cx='51' cy='23' rx='10.5' ry='12.5' fill='#eab894'/>"
            "<path d='M60 20 Q64 24 61 27' fill='#eab894' stroke='#d39a76' stroke-width='1'/>"
            "<path d='M41 12 Q50 6 60 13 Q55 12 50 14 Q46 17 45 24 Q44 32 46 40 Q41 36 40 26 Z' fill='#6b4423'/>"
            "<path d='M44 25 Q44 39 52 41 Q60 41 61 31 Q58 33 55 32 Q50 31 47 27 Z' fill='#6b4423'/>"
            "<path d='M53 30 Q57 28 61 30' stroke='#6b4423' stroke-width='2.2' fill='none' stroke-linecap='round'/>"
            "<path d='M45 19 L53 19' stroke='#1b1b1b' stroke-width='1.6'/>"
            "<rect x='52' y='16.5' width='9' height='6' rx='2.5' fill='#1b1b1b'/>"
            "<rect x='53.5' y='17.5' width='3' height='1.6' rx='.8' fill='#6b6b6b'/>"
            "</svg>")
COMET_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 30 30'>"
             "<circle cx='15' cy='15' r='13' fill='rgba(255,255,255,.35)'/><circle cx='15' cy='15' r='8' fill='#fff'/></svg>")

_BANDS = ", ".join(f"{c} {round(100 * i / 6, 2)}% {round(100 * (i + 1) / 6, 2)}%" for i, c in enumerate(RAINBOW_FILL))
PASS_SLOTS = ("#tt-fx > i:nth-child(2)", "#tt-fx > i:nth-child(3)", "body::after")
PASS_CYCLE = {"rare": 45, "sometimes": 22, "often": 10}
_LANES = ("40%", "64%", "24%")


def _passer(kind):
    """(head svg, head w, head h, walks)"""
    if kind == "pizza":
        return PIZZA_SVG, 64, 48, False
    if kind == "capybara":
        return CAPYBARA_SVG, 120, 80, True
    if kind == "cat":
        return CAT_SVG, 108, 72, True
    if kind == "dog":
        return DOG_SVG, 114, 76, True
    if kind == "sheep":
        return SHEEP_SVG, 118, 78, True
    if kind == "bull":
        return BULL_SVG, 120, 80, True
    if kind == "ghost":
        return GHOST_SVG, 90, 82, True
    if kind == "robot":
        return ROBOT_SVG, 104, 84, True
    if kind == "truck":
        return TRUCK_SVG, 136, 84, True
    if kind == "dude":
        return DUDE_SVG, 68, 98, True
    if kind == "comet":
        return COMET_SVG, 26, 26, False
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='48' height='48'><text x='2' y='40' font-size='40' "
            f"font-family='{_EMOJI_FONT}'>{_esc(kind)}</text></svg>"), 48, 48, False


_FOOD = {
    "capybara": ("<circle cx='22' cy='20' r='8' fill='#ff922b' stroke='#e8590c' stroke-width='1.5'/>"
                 "<circle cx='42' cy='19' r='8' fill='#ff922b' stroke='#e8590c' stroke-width='1.5'/>"
                 "<circle cx='32' cy='13' r='8' fill='#ffa94d' stroke='#e8590c' stroke-width='1.5'/>"
                 "<ellipse cx='35' cy='5' rx='4' ry='1.8' fill='#40c057' transform='rotate(-25 35 5)'/>"),
    "cat": ("<ellipse cx='30' cy='18' rx='14' ry='6' fill='#74c0fc' stroke='#1c7ed6' stroke-width='1.5'/>"
            "<polygon points='44,18 54,11 54,25' fill='#74c0fc' stroke='#1c7ed6' stroke-width='1.5' stroke-linejoin='round'/>"
            "<circle cx='22' cy='17' r='1.6' fill='#1b1b1b'/>"),
    "sheep": ("<path d='M14 24 C12 14 16 10 15 4 M20 24 C20 12 25 10 24 2 M27 24 C26 14 31 12 31 5 M34 24 C35 12 39 11 39 3'"
              " stroke='#2f9e44' stroke-width='3' fill='none' stroke-linecap='round'/>"
              "<path d='M41 24 C42 13 46 12 47 4 M48 24 C48 15 52 12 54 6' stroke='#40c057' stroke-width='3' fill='none' stroke-linecap='round'/>"
              "<circle cx='23' cy='6' r='2.6' fill='#fff' stroke='#ffd43b' stroke-width='1.4'/>"),
    "dog": ("<g transform='rotate(-12 32 16)'><rect x='18' y='13' width='28' height='7' rx='3' fill='#fff' stroke='#adb5bd' stroke-width='1.2'/>"
            "<circle cx='17' cy='12' r='4.5' fill='#fff' stroke='#adb5bd' stroke-width='1.2'/><circle cx='17' cy='21' r='4.5' fill='#fff' stroke='#adb5bd' stroke-width='1.2'/>"
            "<circle cx='47' cy='12' r='4.5' fill='#fff' stroke='#adb5bd' stroke-width='1.2'/><circle cx='47' cy='21' r='4.5' fill='#fff' stroke='#adb5bd' stroke-width='1.2'/></g>"),
}
_BOWL_LABEL = {"capybara": "Call the capybara", "cat": "Call the cat", "dog": "Call the dog", "sheep": "Call the sheep",
               "bull": "Call the bull", "ghost": "Call the ghost", "robot": "Call the robot", "truck": "Call the truck",
               "dude": "Call the Dude"}
CABLE_BOX_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 52'>"
                 "<path d='M18 24 C12 10 26 8 21 1' stroke='#ff6b6b' stroke-width='3.5' fill='none' stroke-linecap='round'/>"
                 "<path d='M32 24 C34 8 43 12 40 2' stroke='#ffd43b' stroke-width='3.5' fill='none' stroke-linecap='round'/>"
                 "<path d='M45 24 C51 12 55 17 59 7' stroke='#69db7c' stroke-width='3.5' fill='none' stroke-linecap='round'/>"
                 "<rect x='18' y='0' width='6' height='4' rx='1' fill='#495057'/><rect x='37' y='0' width='6' height='4' rx='1' fill='#495057'/>"
                 "<rect x='56' y='4' width='6' height='4' rx='1' fill='#495057'/>"
                 "<polygon points='6,22 13,13 25,22' fill='#d9a066' stroke='#8a5a2f' stroke-width='1.5' stroke-linejoin='round'/>"
                 "<polygon points='58,22 51,13 39,22' fill='#d9a066' stroke='#8a5a2f' stroke-width='1.5' stroke-linejoin='round'/>"
                 "<rect x='6' y='22' width='52' height='28' rx='2' fill='#c8945a' stroke='#8a5a2f' stroke-width='2'/>"
                 "<rect x='28' y='22' width='8' height='28' fill='#e9c48f'/></svg>")


HAY_BALE_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 52'>"
                "<path d='M12 18 l-3 -8 M20 17 l-1 -9 M30 17 l2 -10 M40 17 l3 -9 M50 18 l4 -7' stroke='#e0b84c' stroke-width='2.5' stroke-linecap='round'/>"
                "<rect x='6' y='16' width='52' height='32' rx='7' fill='#e9c46a' stroke='#c9a227' stroke-width='2'/>"
                "<path d='M12 24 h40 M12 32 h40 M12 40 h40' stroke='#d4a93c' stroke-width='1.5'/>"
                "<rect x='18' y='16' width='4' height='32' fill='#b5651d'/><rect x='42' y='16' width='4' height='32' fill='#b5651d'/></svg>")
PUMPKIN_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 52'>"
               "<path d='M32 12 q2 -8 8 -9' stroke='#2b8a3e' stroke-width='3.5' fill='none' stroke-linecap='round'/>"
               "<ellipse cx='20' cy='31' rx='14' ry='17' fill='#f76707'/><ellipse cx='44' cy='31' rx='14' ry='17' fill='#f76707'/>"
               "<ellipse cx='32' cy='31' rx='14' ry='19' fill='#fd7e14' stroke='#e8590c' stroke-width='1.5'/>"
               "<polygon points='22,26 27,22 28,29' fill='#2b2b2b'/><polygon points='42,26 37,22 36,29' fill='#2b2b2b'/>"
               "<path d='M20 36 q12 10 24 0 l-4 1 l-2 3 l-3 -3 l-3 3 l-3 -3 l-3 3 l-2 -3 z' fill='#2b2b2b'/></svg>")


# the Drugo's thing: a carton of milk
MILK_SVG = (
            "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 52'>"
            "<polygon points='20,14 30,4 44,4 34,14' fill='#e9ecef' stroke='#adb5bd' stroke-width='1.2' stroke-linejoin='round'/>"
            "<polygon points='34,14 44,4 48,14' fill='#dee2e6' stroke='#adb5bd' stroke-width='1.2' stroke-linejoin='round'/>"
            "<rect x='28' y='1' width='12' height='4' rx='1' fill='#f8f9fa' stroke='#adb5bd' stroke-width='1'/>"
            "<rect x='20' y='14' width='14' height='36' fill='#fff' stroke='#adb5bd' stroke-width='1.2'/>"
            "<polygon points='34,14 48,14 48,48 34,50' fill='#e9ecef' stroke='#adb5bd' stroke-width='1.2' stroke-linejoin='round'/>"
            "<rect x='20' y='26' width='14' height='11' fill='#4dabf7'/>"
            "<polygon points='34,26 48,26 48,36 34,37' fill='#339af0'/>"
            "<path d='M27 29 q-3 4 0 6 q3 -2 0 -6 z' fill='#fff'/>"
            "</svg>")


PARCEL_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 52'>"
              "<polygon points='10,16 20,8 56,8 46,16' fill='#d9a066' stroke='#8a5a2f' stroke-width='1.5' stroke-linejoin='round'/>"
              "<polygon points='46,16 56,8 56,40 46,48' fill='#b07a44' stroke='#8a5a2f' stroke-width='1.5' stroke-linejoin='round'/>"
              "<rect x='10' y='16' width='36' height='32' fill='#c8945a' stroke='#8a5a2f' stroke-width='1.5'/>"
              "<rect x='25' y='16' width='6' height='32' fill='#e9c48f'/><polygon points='31,8 37,8 27,16 21,16' fill='#e9c48f'/>"
              "<rect x='13' y='34' width='10' height='8' rx='1' fill='#fff' stroke='#adb5bd' stroke-width='.8'/>"
              "<path d='M15 37 h6 M15 39.5 h4' stroke='#868e96' stroke-width='1'/></svg>")


def bowl_svg(animal):
    """The housemate's thing: a bowl with its food, the box of cables for the robot, hay for the bull,
    a pumpkin for the ghost, a parcel for the truck, milk for the Drugo."""
    if animal == "truck":
        return PARCEL_SVG
    if animal == "dude":
        return MILK_SVG
    if animal == "robot":
        return CABLE_BOX_SVG
    if animal == "bull":
        return HAY_BALE_SVG
    if animal == "ghost":
        return PUMPKIN_SVG
    return ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 52'>" + _FOOD.get(animal, _FOOD["capybara"]) +
            "<path d='M4 24 Q32 64 60 24 Z' fill='#4dabf7' stroke='#1c7ed6' stroke-width='2' stroke-linejoin='round'/>"
            "<ellipse cx='32' cy='24' rx='28' ry='4' fill='#74c0fc' stroke='#1c7ed6' stroke-width='2'/></svg>")


BOWL_SVG = bowl_svg("capybara")


def walkers_of(p):
    return [x for x in passers_of(p) if x in WALKERS]


def trigger_config(p):
    """What the injection script draws on Teams for the 'click' mode, or None."""
    p = {**DEFAULTS, **p}
    if p["when"] != "click" or not has_burst(p):
        return None
    sym = (split_symbols(p["trigger"]) or [""])[0]
    walkers = walkers_of(p)
    if not sym:
        sym = "bowl" if walkers else "🎉"
    if sym == "bowl":
        animal = walkers[0] if walkers else "capybara"
        ms = BURST_MS + (BOWL_TURN * 1000 * (len(walkers) - 1) if p["to_bowl"] else 0)  # the last one must finish eating
        return {"svg": "data:image/svg+xml," + urllib.parse.quote(bowl_svg(animal)), "text": "", "title": tr(_BOWL_LABEL[animal]),
                "ms": ms, "size": trigger_size(p)}
    return {"svg": "", "text": sym, "title": tr("Start the effects"), "ms": BURST_MS, "size": trigger_size(p)}


def trigger_size(p):
    return max(36, min(160, int({**DEFAULTS, **p}["trigger_size"])))


def _pass_css(passers, freq, trail, click, to_bowl=False, slots=PASS_SLOTS, go="tt-go", prefix="tt-pass"):
    """to_bowl (with the bowl): walkers go where the bowl is (--tt-bowl-x/b, set by the injection script from
    the bowl's place), stop to eat, then leave, one at a time. `go` is the class the click puts on <html>."""
    out = []
    n = len(passers)
    queue, bowl_delay = 0, 0
    for i, kind in enumerate(passers):
        sel = slots[i]
        svg, w, h, walks = _passer(kind)
        cross = 11 if walks else 3.4
        cycle = max(PASS_CYCLE[freq], cross + 3)
        if click:  # one trip per click, staggered
            cycle = cross + 4 if walks else cross + 0.5
        trail_w = 240 if trail else 0
        width, travel = w + trail_w, f"calc(100vw + {w + trail_w + 80}px)"
        bg = [f"{_url(svg)} right center / {w}px {h}px no-repeat"]
        if trail:
            bg.append(f"linear-gradient(180deg, {_BANDS}) left center / {trail_w + 8}px {max(12, round(h * .55))}px no-repeat")
        mask = ("-webkit-mask-image: linear-gradient(90deg, transparent, #000 45%); mask-image: linear-gradient(90deg, transparent, #000 45%);"
                if trail else "")
        bowl = walks and click and to_bowl
        if bowl:
            cross, cycle = 13, 17
            where = f"top: calc(var(--tt-bowl-b, calc(100vh - 94px)) - {h}px);"  # feet on the bowl's bottom, any size
        else:
            where = "bottom: 4px;" if walks else f"top: {'16%' if kind == 'comet' else _LANES[i % 3]};"
        end = round(100 * cross / cycle, 2)
        name = f"{prefix}{i}"
        if walks:
            if bowl:  # nose against the bowl (the walker starts at left: -(width + 20)px); one at a time
                stop = "calc(var(--tt-bowl-x, calc(100vw - 100px)) + 30px)"
                bowl_delay = queue * BOWL_TURN
                queue += 1
                a, b = round(end * .4, 2), round(end * .75, 2)
            else:  # walks along the bottom, stops a moment, then leaves
                stop = f"calc(100vw - {w + trail_w + 150}px)"
                a, b = round(end * .45, 2), round(end * .7, 2)
            frames = (f"  0% {{ opacity: 1; transform: translateX(0); }}\n  {a}% {{ transform: translateX({stop}); }}\n"
                      f"  {b}% {{ transform: translateX({stop}); }}\n  {end}% {{ opacity: 1; transform: translateX({travel}); }}\n"
                      f"  {end + 0.1}%, 100% {{ opacity: 0; transform: translateX({travel}); }}")
            anim = f"{name} {cycle}s linear infinite, tt-bob .5s ease-in-out infinite alternate"
        else:
            q = [round(end * k / 4, 2) for k in range(1, 4)]
            frames = (f"  0% {{ opacity: 1; transform: translate(0, 0) rotate(0deg); }}\n"
                      f"  {q[0]}% {{ transform: translate(calc({travel} * .25), -14px) rotate(-7deg); }}\n"
                      f"  {q[1]}% {{ transform: translate(calc({travel} * .5), 10px) rotate(6deg); }}\n"
                      f"  {q[2]}% {{ transform: translate(calc({travel} * .75), -12px) rotate(-6deg); }}\n"
                      f"  {end}% {{ opacity: 1; transform: translate({travel}, 0) rotate(0deg); }}\n"
                      f"  {end + 0.1}%, 100% {{ opacity: 0; transform: translate({travel}, 0); }}")
            anim = f"{name} {cycle}s linear infinite"
        delay = round(2 + cycle * i / n, 2)
        box = (f"{sel} {{ content: \"\"; display: block; position: fixed; {where} left: -{width + 20}px; width: {width}px; height: {h}px;\n"
               f"  z-index: 2147483647; pointer-events: none; opacity: 0; background: {', '.join(bg)};\n"
               f"  {mask} filter: drop-shadow(0 3px 4px rgba(0,0,0,.35));")
        if click:  # nothing until the button is pressed; then one trip each, one after the other
            start = bowl_delay if bowl else round(i * 1.6, 1)
            out.append(f"{box} }}\nhtml.{go} {sel} {{ animation: {anim.replace(' infinite,', ' 1,', 1) if walks else anim.replace(' infinite', ' 1')};"
                       f" animation-delay: {start}s; }}\n@keyframes {name} {{\n{frames}\n}}")
        else:
            out.append(f"{box} animation: {anim}; animation-delay: {delay}s; }}\n@keyframes {name} {{\n{frames}\n}}\n"
                       f"html.tt-now {sel} {{ animation-delay: {round(i * 1.6, 1)}s !important; }}")
    out.append("@keyframes tt-bob { from { translate: 0 0; rotate: -1.5deg; } to { translate: 0 -4px; rotate: 1.5deg; } }")
    return out


# ---------- background + test + reduced motion ----------

def _bg_css(p):
    cols = [c for c in p["bg_colors"] if _HEX.match(c)][:3] or list(DEFAULTS["bg_colors"])
    angle = int(p["flow_angle"]) % 360
    css = ["body, #app, [data-tid='app-layout'] { background: transparent !important; }"]
    if p["bg_mode"] == "gradient":
        css.insert(0, f"html {{ background: linear-gradient({angle}deg, {', '.join(cols + cols[:1])}) fixed !important; }}")
        return css
    # Flowing: a big square layer under everything, turned to the chosen direction, with colour bands that
    # repeat every PERIOD; it slides by exactly one PERIOD per cycle, so the loop never jumps. A soft light
    # band ("the wave") rides on top with half the period.
    period = "60vmax"
    n = len(cols)
    stops = ", ".join(f"{c} calc({period} * {i / n:.4f})" for i, c in enumerate(cols)) + f", {cols[0]} {period}"
    sheen = f"rgba(255,255,255,0) 0, rgba(255,255,255,.22) calc({period} / 4), rgba(255,255,255,0) calc({period} / 2)"
    seconds = max(2, min(30, int(p["flow_seconds"])))
    css.insert(0, f"html {{ background: {cols[0]} !important; }}")
    css.append(f"html::before {{ content: \"\"; position: fixed; z-index: -1; pointer-events: none; width: 300vmax; height: 300vmax;\n"
               f"  left: calc(50% - 150vmax); top: calc(50% - 150vmax);\n"
               f"  background: repeating-linear-gradient(90deg, {sheen}), repeating-linear-gradient(90deg, {stops});\n"
               f"  transform: rotate({angle - 90}deg); will-change: transform; animation: tt-flow {seconds}s linear infinite; }}\n"
               f"@keyframes tt-flow {{ from {{ transform: rotate({angle - 90}deg) translateX(0); }}"
               f" to {{ transform: rotate({angle - 90}deg) translateX(-{period}); }} }}")
    return css


_TRIGGER_CSS = """#tt-trigger, .tt-bowl { position: fixed; z-index: 2147483647; width: 46px; height: 46px; border-radius: 50%; border: 0; padding: 0;
  background: transparent center / 88% 88% no-repeat; font-size: 30px; line-height: 1; cursor: pointer; opacity: .9;
  filter: drop-shadow(0 2px 4px rgba(0,0,0,.4)); transition: transform .15s, opacity .15s; touch-action: none; }
.tt-bowl { z-index: 2147483644; }
#tt-trigger:hover, .tt-bowl:hover { opacity: 1; transform: scale(1.12) rotate(-6deg); }
#tt-trigger:active, .tt-bowl:active { transform: scale(.92); }
#tt-trigger:focus-visible, .tt-bowl:focus-visible { outline: 2px solid #fff; outline-offset: 2px; }"""

_FX_SELECTORS = "html, html::before, body, body::after, #tt-fx > i"
# Test button: restart every running effect now, make the buttons dance once.
_TEST_CSS = """html.tt-reset body::after, html.tt-reset #tt-fx > i { animation: none !important; }
html.tt-dance .fui-Button, html.tt-dance .fui-ToggleButton, html.tt-dance .fui-MenuButton { animation: tt-jiggle .45s ease-in-out 3 !important; }
html.tt-dance .fui-Avatar { animation: tt-spin .7s ease-in-out 2 !important; }"""
_REDUCED = (f"@media (prefers-reduced-motion: reduce) {{ {_FX_SELECTORS}, .fui-Button, .fui-ToggleButton, .fui-MenuButton, .fui-Avatar "
            "{ animation: none !important; } body::after, #tt-fx > i { display: none !important; } }")


def passers_of(p):
    """Who flies by in a THEME (pizza, comet, emoji). The housemates are not part of themes: see pets_css."""
    out = []
    for x in p.get("pass") or []:
        x = str(x).strip()
        if x in WALKERS:
            continue
        if x in PASSERS or split_symbols(x):
            out.append(x if x in PASSERS else split_symbols(x)[0])
    return out[:3]


# ---------- housemates: independent of the theme ----------

# Sensible defaults: walk, eat (little hearts show it), leave; nap, trail, names are off until chosen.
PET_WHEN = ("live", "click", "auto")  # live on Teams (default) | come when their thing is clicked | pass by now and then
# Sizes follow the Teams window (its short side), not fixed pixels: Windows scaling and window size change a lot.
PET_BOWL_VMIN = {"s": 7, "m": 10, "l": 15, "xl": 22}  # bowl side, % of the window short side
PET_REF = 640  # sprites are drawn for a 640 px short side; the engine scales them to the real window
PETS_DEFAULTS = {"who": [], "when": "live", "freq": "sometimes", "bowl": "m",
                 "trail": False, "hearts": True, "nap": False, "scale": "m", "speed": "normal", "names": {}}
PET_SCALE = {"s": .7, "m": 1.0, "l": 1.4}
PET_SPEED_X = {"slow": .6, "normal": 1.0, "fast": 1.8}


def clean_pets(pets):
    p = {**PETS_DEFAULTS, **(pets or {})}
    who = []
    for x in p["who"] or []:
        if x in WALKERS and x not in who:
            who.append(x)
    names = {k: str(v).strip()[:24] for k, v in (p.get("names") or {}).items() if k in WALKERS and str(v).strip()}
    return {"who": who[:4], "when": p["when"] if p["when"] in PET_WHEN else "live",
            "freq": p["freq"] if p["freq"] in PASS_FREQ else "sometimes", "bowl": p["bowl"] if p["bowl"] in PET_BOWL_VMIN else "m",
            "trail": bool(p["trail"]), "hearts": bool(p["hearts"]), "nap": bool(p["nap"]),
            "scale": p["scale"] if p["scale"] in PET_SCALE else "m", "speed": p["speed"] if p["speed"] in PET_SPEED_X else "normal",
            "names": names}


def pets_trigger(pets):
    """Their thing on Teams (the bowl, the box of cables) for the click mode, or None."""
    p = clean_pets(pets)
    if not p["who"] or p["when"] == "auto":
        return None
    first = p["who"][0]
    return {"svg": "data:image/svg+xml," + urllib.parse.quote(bowl_svg(first)), "text": "", "title": tr(_BOWL_LABEL[first]),
            "ms": BURST_MS + BOWL_TURN * 1000 * (len(p["who"]) - 1), "vmin": PET_BOWL_VMIN[p["bowl"]]}


PET_SPEED = 150     # px per second
PET_EAT = 3.2       # seconds at the bowl
PET_EVERY = {"rare": 45, "sometimes": 22, "often": 10}  # by themselves: one visit every N seconds

_PETS_CSS = """#tt-pets .tt-pet { position: absolute; left: 0; top: 0; will-change: transform; }
#tt-pets .tt-pet-in { width: 100%; height: 100%; background: center / contain no-repeat; filter: drop-shadow(0 3px 4px rgba(0,0,0,.35));
  animation: tt-pet-walk .5s ease-in-out infinite alternate; }
#tt-pets .tt-k-ghost .tt-pet-in { opacity: .88; animation: tt-pet-float 1.4s ease-in-out infinite alternate; }  /* the ghost floats */
#tt-pets .tt-k-truck .tt-pet-in { animation: tt-pet-rumble .18s ease-in-out infinite alternate; }  /* a truck rumbles on its wheels */
@keyframes tt-pet-rumble { from { translate: 0 0; } to { translate: 0 -2px; } }
@keyframes tt-pet-float { from { translate: 0 0; rotate: -2deg; } to { translate: 0 -10px; rotate: 2deg; } }
#tt-pets .tt-eating .tt-pet-in { animation: tt-pet-eat .4s ease-in-out infinite alternate; }
#tt-pets .tt-napping .tt-pet-in { animation: tt-pet-nap 1.6s ease-in-out infinite alternate; }
#tt-pets .tt-live { pointer-events: auto; cursor: grab; touch-action: none; }
#tt-pets .tt-struggle .tt-pet-in { animation: tt-pet-angry .08s linear infinite alternate; filter: drop-shadow(0 0 6px rgba(255,60,60,.8)); }
#tt-pets .tt-held { cursor: grabbing; z-index: 1; }
#tt-pets .tt-held .tt-pet-in { animation: tt-pet-dangle .45s ease-in-out infinite alternate; transform-origin: 50% 0; }
@keyframes tt-pet-dangle { from { rotate: -8deg; } to { rotate: 8deg; } }
#tt-pets .tt-land .tt-pet-in { animation: tt-pet-land .35s ease-out; }
@keyframes tt-pet-land { 0% { scale: 1.08 .85; } 60% { scale: .95 1.06; } 100% { scale: 1 1; } }
#tt-pets .tt-angry .tt-pet-in { animation: tt-pet-angry .09s linear infinite alternate; filter: drop-shadow(0 0 6px rgba(255,60,60,.8)); }
@keyframes tt-pet-angry { from { translate: -3px 0; rotate: -3deg; } to { translate: 3px 0; rotate: 3deg; } }
#tt-pets .tt-sulk .tt-pet-in { animation: tt-pet-stomp .2s ease-in-out infinite alternate; filter: drop-shadow(0 0 5px rgba(255,60,60,.7)); }
@keyframes tt-pet-stomp { from { translate: 0 0; rotate: -4deg; } to { translate: 0 -5px; rotate: 4deg; } }
#tt-pets .tt-cloud { position: absolute; bottom: 100%; left: 50%; translate: -50% 0; font-size: 28px; line-height: 1; pointer-events: none;
  animation: tt-cloud .35s ease-in-out infinite alternate; }
#tt-pets .tt-pet:has(.tt-pet-name) .tt-cloud { bottom: calc(100% + 22px); }
@keyframes tt-cloud { from { translate: -50% 0; filter: brightness(1); } to { translate: -50% -4px; filter: brightness(1.6) drop-shadow(0 0 6px #ffe066); } }
#tt-pets .tt-idle .tt-pet-in { animation: tt-pet-idle 2.4s ease-in-out infinite alternate; }
#tt-pets .tt-happy .tt-pet-in { animation: tt-pet-happy .28s ease-in-out infinite alternate; }
@keyframes tt-pet-idle { from { rotate: 0deg; } to { rotate: 2deg; } }
@keyframes tt-pet-happy { from { translate: 0 0; } to { translate: 0 -12px; rotate: -4deg; } }
@keyframes tt-pet-walk { from { translate: 0 0; rotate: -1.5deg; } to { translate: 0 -4px; rotate: 1.5deg; } }
@keyframes tt-pet-eat { from { translate: 0 0; rotate: 0deg; } to { translate: 0 3px; rotate: 5deg; } }
@keyframes tt-pet-nap { from { scale: 1 1; } to { scale: 1.03 .95; } }
#tt-pets .tt-flip .tt-pet-in { scale: -1 1; }
#tt-pets .tt-flip.tt-napping .tt-pet-in { animation: none; }
#tt-pets .tt-pet-trail { position: absolute; right: 92%; top: 38%; height: 26%; width: 170px; pointer-events: none;
  background: linear-gradient(180deg, """ + ", ".join(f"{c} {round(100 * i / 6, 2)}% {round(100 * (i + 1) / 6, 2)}%" for i, c in enumerate(RAINBOW_FILL)) + """);
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 70%); mask-image: linear-gradient(90deg, transparent, #000 70%); }
#tt-pets .tt-flip .tt-pet-trail { right: auto; left: 92%; -webkit-mask-image: linear-gradient(270deg, transparent, #000 70%); mask-image: linear-gradient(270deg, transparent, #000 70%); }
#tt-pets .tt-eating .tt-pet-trail, #tt-pets .tt-napping .tt-pet-trail { opacity: 0; transition: opacity .4s; }
#tt-pets .tt-pet-name { position: absolute; bottom: 100%; left: 50%; translate: -50% -4px; white-space: nowrap; font: 600 12px/1.2 "Segoe UI", sans-serif;
  color: #1b1b1f; background: rgba(255,255,255,.92); border-radius: 999px; padding: 2px 8px; box-shadow: 0 1px 3px rgba(0,0,0,.3); }
#tt-pets .tt-pop { position: absolute; font-size: 18px; pointer-events: none; animation: tt-pet-pop 1.3s ease-out forwards; }
@keyframes tt-pet-pop { from { opacity: 1; translate: 0 0; scale: .7; } to { opacity: 0; translate: 6px -46px; scale: 1.15; } }"""


def pets_config(pets, respect_reduced_motion=False):
    """What the movement engine in Teams needs (teams.PETS_ENGINE_JS), or None when nobody lives there.
    The engine walks each housemate towards where the bowl is NOW, every frame: moving the bowl changes
    their way, never makes them jump."""
    p = clean_pets(pets)
    if not p["who"]:
        return None
    sprites = {}
    k_scale = PET_SCALE[p["scale"]]
    for k in p["who"]:
        svg, w, h, _ = _passer(k)
        sprites[k] = {"url": "data:image/svg+xml," + urllib.parse.quote(svg), "w": round(w * k_scale), "h": round(h * k_scale),
                      "name": p["names"].get(k, "")}
    return {"who": p["who"], "mode": {"live": "live", "click": "bowl", "auto": "walk"}[p["when"]], "every": PET_EVERY[p["freq"]],
            "speed": round(PET_SPEED * PET_SPEED_X[p["speed"]]), "eat": PET_EAT, "sprites": sprites, "bowls": pets_bowls(p),
            "trail": p["trail"], "hearts": p["hearts"], "nap": p["nap"], "ref": PET_REF, "respect": bool(respect_reduced_motion)}


def pets_bowls(pets):
    """Each housemate has its own thing on Teams: {kind: {svg, title, size}}; none when they only pass by."""
    p = clean_pets(pets)
    if not p["who"] or p["when"] == "auto":
        return {}
    return {k: {"svg": "data:image/svg+xml," + urllib.parse.quote(bowl_svg(k)), "title": tr(_BOWL_LABEL[k]), "vmin": PET_BOWL_VMIN[p["bowl"]]}
            for k in p["who"]}

def pets_css(pets, respect_reduced_motion=False):
    """Static styles of the housemates and of their bowl; the movement itself is done by the engine."""
    if not clean_pets(pets)["who"]:
        return ""
    lines = [_PETS_CSS, _TRIGGER_CSS]
    if respect_reduced_motion:
        lines.append("@media (prefers-reduced-motion: reduce) { #tt-pets .tt-pet-in { animation: none !important; } }")
    return "\n".join(lines) + "\n"


def for_popups(p):
    """The same theme for Teams' small windows (the notification toasts): colours only. The toast window is a
    plain rectangle around a rounded card, so a window background, see-through panels or effects would show
    as a bigger rectangle under the card."""
    return {**DEFAULTS, **p, "bg_mode": "solid", "colors_anim": "off", "fall": "", "pass": [], "jiggle": False, "when": "auto"}


def has_burst(p):
    """Something the Teams button can set off: who passes by, things that fall, dancing buttons."""
    p = {**DEFAULTS, **p}
    return bool(passers_of(p)) or bool(split_symbols(p["fall"])) or bool(p["jiggle"])


def has_effects(p):
    p = {**DEFAULTS, **p}
    return (p["colors_anim"] != "off" or bool(split_symbols(p["fall"])) or bool(passers_of(p)) or p["jiggle"]
            or p["bg_mode"] == "gradient_anim")


def generate(base_tokens, params, name="theme", respect_reduced_motion=False, pin_all=False):
    """base_tokens: Teams' own tokens for the theme's native mode (native_mode); params: the theme.
    pin_all=True when Teams is in the other mode: every colour token is written, the unmapped ones too
    (status colours, palette), so the result is identical whatever mode Teams is in.
    Effects are chosen explicitly, so they run even when the system asks for reduced motion
    (corporate PCs often report it); respect_reduced_motion=True stops them in that case."""
    mode = detect_mode(base_tokens)
    p, _ = resolve(base_tokens, params)
    p["_bg1"] = _mapped_hex(base_tokens, "--colorNeutralBackground1", p, p["background"])
    anim_mode =p["colors_anim"] if p["colors_anim"] in COLORS_ANIM else "off"
    animated = set()
    if anim_mode in ("buttons", "text"):
        animated |= set(RAINBOW_FILL_TOKENS + RAINBOW_TEXT_TOKENS)
    if anim_mode == "text":
        animated |= set(TEXT_TOKENS)
    lines = [f"/* Teams theme '{name}' ({mode}) - generated by teams-theme from Teams' own tokens */",
             ".fui-FluentProvider, :root, body {"]
    still = []
    for key in sorted(base_tokens):
        if not key.startswith("--"):
            continue
        value = base_tokens[key].strip()
        new = _map_value(key, value, p)
        if not (new and new != value):
            if not (pin_all and (solid_hex(value) or key.startswith("--shadow"))):
                continue
            new = new or value
        if key in animated:  # !important would beat the animation
            still.append((key, new))
        else:
            lines.append(f"  {key}: {new} !important;")
    lines.append("}")
    if p["font"]:
        lines.append(f"body, .fui-FluentProvider {{ font-family: {p['font']} !important; }}")
    if p["bg_mode"] != "solid":
        lines += _bg_css(p)

    if anim_mode in ("buttons", "text"):
        groups = [(RAINBOW_FILL_TOKENS, RAINBOW_FILL), (RAINBOW_TEXT_TOKENS, RAINBOW_TEXT[mode])]
        if anim_mode == "text":
            groups.append((TEXT_TOKENS, RAINBOW_TEXT[mode]))
        css, a = _animated("tt-rainbow", groups, base_tokens, 9)
        lines += css
        lines.append(f".fui-FluentProvider {{ animation: {a}; }}")
        if still and respect_reduced_motion:
            lines.append("@media (prefers-reduced-motion: reduce) {\n  .fui-FluentProvider { animation: none !important; "
                         + " ".join(f"{k}: {v} !important;" for k, v in still) + " }\n}")
    elif anim_mode == "all":
        lines.append(_DISCO_CSS)

    click = trigger_config(p) is not None
    lines.append(_JIGGLE_KEYFRAMES)
    if p["jiggle"]:
        lines.append(_JIGGLE_CSS)
    syms = split_symbols(p["fall"])[:8]
    if syms:
        lines.append(_fall_css(syms, p["fall_style"] if p["fall_style"] in FALL_STYLES else "snow", click))
    who = passers_of(p)
    if who:
        lines += _pass_css(who, p["pass_freq"] if p["pass_freq"] in PASS_FREQ else "sometimes", bool(p["trail"]), click,
                           bool(p["to_bowl"]) and (trigger_config(p) or {}).get("svg", "") != "")
    if click:
        lines.append(_TRIGGER_CSS)
    lines.append(_TEST_CSS)
    if respect_reduced_motion:
        lines.append(_REDUCED)
    return "\n".join(lines) + "\n"


# ---------- preview helpers ----------

def declarations(css):
    """{token: value} of the static `--x: v !important;` lines of a generated CSS."""
    out = {}
    for line in css.splitlines():
        line = line.strip()
        if line.startswith("--") and line.endswith("!important;"):
            k, v = line[:-len("!important;")].rstrip().rstrip(";").split(":", 1)
            out[k.strip()] = v.strip()
    return out


def readability(base_tokens, params, css):
    """Contrast checks on the colours Teams will really use: [(label, ratio, fixed_automatically)]."""
    mode = detect_mode(base_tokens)
    p, fixed = resolve(base_tokens, params)
    d = {**{k: v for k, v in base_tokens.items() if k.startswith("--")}, **declarations(css)}

    def c(k):
        return solid_hex(d.get(k))
    bg1, bg2 = c("--colorNeutralBackground1"), c("--colorNeutralBackground2")
    rows = []

    def add(label, a, b, auto=False):
        if a and b:
            rows.append((label, round(contrast(a, b), 1), auto))
    if p["colors_anim"] == "text":
        for col in RAINBOW_TEXT[mode]:
            add(tr("Rainbow text {col}", col=col), col, bg1)
    else:
        add(tr("Text on the background"), c("--colorNeutralForeground1"), bg1)
        add(tr("Secondary text"), c("--colorNeutralForeground2"), bg2)
    add(tr("Links on the background"), p["link"], bg1, "link" in fixed)
    if p["colors_anim"] in ("buttons", "text"):
        for col in RAINBOW_FILL:
            add(tr("Text on the {col} button", col=col), p["on_brand"], col, "on_brand" in fixed)
    else:
        brand = c("--colorBrandBackground") or brand_preview(p["brand_hue"], p["brand_sat"])
        add(tr("Text in coloured buttons"), p["on_brand"], brand, "on_brand" in fixed)
        add(tr("Mentions on the background"), c("--colorBrandForeground1"), bg1)
    return rows


def light_from_dark(dark_tokens):
    """Fallback light tokens until Teams has been seen in light mode: greys get their lightness mirrored."""
    out = {}
    for k, v in dark_tokens.items():
        hexv = solid_hex(v)
        if not hexv or not _COLOR_KEYS.match(k):
            out[k] = v
            continue
        r, g, b = (x / 255 for x in parse_hex(hexv))
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        if s < 0.08:
            nr, ng, nb = colorsys.hls_to_rgb(h, 1 - l, s)
            mapped = to_hex((nr * 255, ng * 255, nb * 255))
            m = _RGBA.match(v)
            out[k] = f"rgba({', '.join(str(x) for x in parse_hex(mapped))}, {m.group(5)})" if m and m.group(5) else mapped
        else:
            out[k] = v
    out.update({"--colorBrandBackground": "#5b5fc7", "--colorBrandBackground2": "#e8ebfa",
                "--colorBrandForeground1": "#5b5fc7", "--colorBrandForegroundLink": "#5b5fc7"})
    return out


# ---------- files ----------

def migrate(data):
    """Any older format -> the current flat theme. Keeps the user's choices (the dark variant wins)."""
    if "dark" not in data:
        return {**DEFAULTS, **{k: v for k, v in data.items() if k in KEYS}}
    if isinstance(data["dark"], str):  # first format: {'dark': '#..', 'light': '#..', ...}
        rest = {k: v for k, v in data.items() if k in KEYS}
        return {**DEFAULTS, **rest, "background": data["dark"], "text": data["light"]}
    v = data["dark"]
    fx = set(v.get("effects") or [])
    out = {**DEFAULTS, **{k: v[k] for k in KEYS if k in v}}
    out["colors_anim"] = "all" if "disco" in fx else "text" if "rainbow_text" in fx else "buttons" if "rainbow" in fx else "off"
    fall = (v.get("rain") or "") if "rain" in fx else ""
    fall += ("🌸" if "flowers" in fx else "") + ("⭐" if "stars" in fx else "")
    out["fall"] = "".join(split_symbols(fall)[:8])
    out["fall_style"] = {1: "snow", 2: "rain", 3: "storm"}.get(int(v.get("rain_speed", 2)), "rain") if "rain" in fx else "snow"
    out["pass"] = [k for k in ("pizza", "capybara", "comet") if k in fx]
    out["jiggle"] = "jiggle" in fx
    return out


def load_themes(folder):
    out = {}
    for f in sorted(Path(folder).glob("*.json")):
        out[f.stem] = migrate(json.loads(f.read_text(encoding="utf-8")))
    return out


def save_theme(folder, name, params):
    Path(folder).mkdir(parents=True, exist_ok=True)
    keep = {k: copy.deepcopy(params.get(k, DEFAULTS[k])) for k in KEYS}
    (Path(folder) / f"{name}.json").write_text(json.dumps(keep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
