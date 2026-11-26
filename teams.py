"""Teams process control, theme injection and Windows autostart."""
import json
import os
import random
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import cdp
from i18n import tr

NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW
_APPDATA = Path(os.environ.get("APPDATA", Path.home()))
CONFIG_DIR = _APPDATA / "teams-remix"
CONFIG_FILE = CONFIG_DIR / "config.json"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "TeamsRemix"
_OLD_CONFIG_DIR, _OLD_RUN_NAME = _APPDATA / "teams-theme", "TeamsTheme"  # before the app was called Teams Remix


def migrate_old_names():
    """Move %APPDATA%\\teams-theme to teams-remix and the old autostart entry to the new name, once."""
    if _OLD_CONFIG_DIR.is_dir() and not CONFIG_DIR.exists():
        shutil.move(str(_OLD_CONFIG_DIR), str(CONFIG_DIR))
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
            try:
                winreg.QueryValueEx(k, _OLD_RUN_NAME)
            except FileNotFoundError:
                return
            winreg.DeleteValue(k, _OLD_RUN_NAME)
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, _launch_command())
    except OSError:
        pass


THEMES_DIR = CONFIG_DIR / "themes"  # the user's themes, with the other personal things (not next to the app)


def migrate_themes(old_dir):
    """Themes used to live in themes\\ next to the app: move them to APPDATA once, so updating the app never
    touches them."""
    old = Path(old_dir)
    if not old.is_dir() or (THEMES_DIR.is_dir() and any(THEMES_DIR.glob("*.json"))):
        return
    THEMES_DIR.mkdir(parents=True, exist_ok=True)
    for f in old.glob("*.json"):
        shutil.copy2(f, THEMES_DIR / f.name)
    shutil.rmtree(old, ignore_errors=True)

# Housemates' movement engine (one per page; replaced when ENGINE_VERSION changes). Three ways to live:
#   live: they stay on Teams, stroll along the bottom, stop, look around; click one to cuddle it (hearts);
#         clicking the bowl sends them all to eat, then they go back to strolling.
#   bowl: clicking the bowl brings them one at a time: each walks towards where the bowl is NOW (moving the
#         bowl changes its way, never makes it jump), eats (from then on it lets go of the bowl), leaves.
#   walk: every N seconds one walks along the bottom, stops a moment, leaves.
# No percent signs in here: _JS_APPLY is filled with the % operator.
ENGINE_VERSION = 27
PETS_ENGINE_JS = r"""
if (window.__ttPetsEngine !== ENGINE_V) (function(){
  if (window.__ttPetsSetup) { try { window.__ttPetsSetup(null); } catch (e) {} }
  window.__ttPetsEngine = ENGINE_V;
  [].forEach.call(document.querySelectorAll('#tt-pets'), function(l){ l.remove(); });  // the old engine's layer
  var D = document, st = {key: null, cfg: null, layer: null, bowls: {}, actors: [], queue: [], raf: 0, timer: 0, last: 0, away: {}};
  function mk(tag, cls){ var e = D.createElement(tag); if (cls) e.className = cls; return e; }
  function layer(){ if (!st.layer || !st.layer.isConnected) { st.layer = mk('div'); st.layer.id = 'tt-pets';
      // layers: housemates < their bowls < what rains and flies (#tt-fx) < the theme button
      st.layer.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483643;overflow:hidden'; D.body.appendChild(st.layer); } return st.layer; }
  function ground(a){ return innerHeight - a.h - 4; }
  function short(){ return Math.min(innerWidth, innerHeight); }   // sizes follow the window, not fixed pixels
  function sizeBowl(b, info){ var px = Math.round(info.vmin * short() / 100); b.style.width = px + 'px'; b.style.height = px + 'px'; }
  // each housemate has its own thing (bowl, box) and eats only there
  function bowlAt(a){ var b = st.bowls[a.kind]; if (!b || !b.isConnected) return null; var r = b.getBoundingClientRect();
    // stands on the side it comes from, nose towards the bowl
    var right = a.x + a.w / 2 > r.left + r.width / 2, overlap = Math.min(18, r.width * .3);
    return {x: right ? r.right - overlap : r.left - a.w + overlap, y: r.bottom - a.h, right: right}; }
  function loop(){ if (!st.raf) st.raf = requestAnimationFrame(step); }
  function place(a){ a.el.style.transform = 'translate(' + Math.round(a.x) + 'px,' + Math.round(a.y) + 'px)'; a.el.classList.toggle('tt-flip', a.flip); }
  function cls(a, c){ ['tt-eating', 'tt-napping', 'tt-idle', 'tt-happy', 'tt-angry', 'tt-sulk', 'tt-held', 'tt-land'].forEach(function(x){ a.el.classList.toggle(x, x === c); }); }
  function pop(a, sym){ var p = mk('span', 'tt-pop'); p.textContent = sym;
    p.style.left = Math.round(a.x + (a.flip ? a.w * .15 : a.w * .7) + (Math.random() * 16 - 8)) + 'px'; p.style.top = Math.round(a.y - 6) + 'px';
    layer().appendChild(p); setTimeout(function(){ p.remove(); }, 1400); }
  function rnd(a, b){ return a + Math.random() * (b - a); }
  function stroll(a){  // somewhere new in the window, at its own pace
    a.phase = 'stroll'; cls(a, ''); a.pace = rnd(.45, .95);
    a.tx = rnd(0, Math.max(1, innerWidth - a.w)); a.ty = rnd(innerHeight * .16, ground(a)); }
  function goOut(a){  // goes for a walk outside the window; comes back later from either side
    a.phase = 'out'; cls(a, ''); a.exitX = Math.random() < .5 ? -a.w - 40 : innerWidth + 40; }
  function spawn(kind, mode, k, side){
    var s = st.cfg.sprites[kind]; if (!s) return null;
    if (mode === 'live' && st.actors.some(function(x){ return x.kind === kind; })) return null;  // never two of the same
    var u = short() / (st.cfg.ref || 640), w = Math.round(s.w * u), h = Math.round(s.h * u);
    var fromRight = side ? side === 'right' : Math.random() < .5;  // not always from the same place
    var a = {kind: kind, w: w, h: h, x: fromRight ? innerWidth + 20 + (k || 0) * 60 : -w - 20 - (k || 0) * 60, y: 0, phase: 'go', t: 0,
             mode: mode, flip: fromRight, popT: 0, k: k || 0, fromRight: fromRight};
    a.y = ground(a);
    a.el = mk('div', 'tt-pet tt-k-' + kind); a.el.style.width = w + 'px'; a.el.style.height = h + 'px';
    if (st.cfg.trail) a.el.appendChild(mk('div', 'tt-pet-trail'));
    a.inner = mk('div', 'tt-pet-in'); a.inner.style.backgroundImage = 'url("' + s.url + '")'; a.el.appendChild(a.inner);
    if (s.name) { var n = mk('div', 'tt-pet-name'); n.textContent = s.name; a.el.appendChild(n); }
    // every housemate can be cuddled (click) and picked up (drag), whatever the way it lives
    a.el.classList.add('tt-live');  // no hover tooltip
    a.el.addEventListener('pointerdown', function(e){ e.stopPropagation(); e.preventDefault();
      a.drag = {ox: e.clientX - a.x, oy: e.clientY - a.y, sx: e.clientX, sy: e.clientY, moved: false}; a.el.setPointerCapture(e.pointerId); });
    a.el.addEventListener('pointermove', function(e){ var g = a.drag; if (!g) return;
      if (!g.moved && Math.abs(e.clientX - g.sx) + Math.abs(e.clientY - g.sy) > 5) {  // picked up
        g.moved = true; a.wasEating = a.phase === 'eat'; a.forced = isCross(a); a.resume = a.phase; a.phase = 'held'; cls(a, 'tt-held');
        if (a.forced) { a.el.classList.add('tt-struggle'); pop(a, '💢'); } }  // picked up while cross: it struggles
      if (g.moved) { a.x = Math.max(-a.w / 2, Math.min(innerWidth - a.w / 2, e.clientX - g.ox)); a.y = Math.max(0, Math.min(ground(a), e.clientY - g.oy)); place(a); } });
    a.el.addEventListener('pointerup', function(e){ var g = a.drag; a.drag = null; if (!g) return; e.stopPropagation();
      a.el.classList.remove('tt-struggle');
      if (g.moved && a.forced) {  // dragged by force while cross: cross again (still 20 s at most)
        a.forced = false;
        if (st.away[a.kind]) { clearTimeout(st.away[a.kind].timer); delete st.away[a.kind]; }
        a.snub = false; a.el.classList.remove('tt-cross'); angry(a); loop(); return; }
      if (g.moved) { if (a.wasEating) angry(a); else { a.phase = 'land'; a.t = .35; cls(a, 'tt-land'); } loop(); return; }  // let go: it lands there, or is cross
      if (isCross(a)) { pop(a, '💢'); return; }  // no cuddles while cross
      if (a.phase === 'eat' || a.phase === 'held') return;
      a.resume = a.phase; a.phase = 'happy'; a.t = 1.6; a.popT = 0; cls(a, 'tt-happy'); for (var j = 0; j < 3; j++) pop(a, '❤️'); loop(); });
    layer().appendChild(a.el);
    if (mode === 'bowl') { var b = bowlAt(a); if (b) a.y = b.y; }
    else if (mode === 'walk') a.tx = innerWidth * (.25 + Math.random() * .5);
    else { a.y = rnd(innerHeight * .16, ground(a)); stroll(a); }
    st.actors.push(a); place(a); loop(); return a;
  }
  function next(){ if (st.queue.length) spawn(st.queue.shift(), 'bowl'); }
  var MAX_AWAY = 30000;  // never away for more than 30 seconds
  var CROSS_FOR = 20000;  // cross for 20 seconds at most; teasing it does not make it longer
  function awayFor(a){ return CROSS_FOR; }
  function isCross(a){ return !!a.snub || ['angry', 'sulk', 'snub', 'scoff', 'retreat'].indexOf(a.phase) >= 0; }
  function angry(a){  // its bowl taken away, or picked up, while eating: cross, a storm cloud, off it goes
    a.phase = 'angry'; a.t = 1.2; cls(a, 'tt-angry'); pop(a, '💢'); pop(a, '😠');
    if (!a.cloud) { a.cloud = mk('div', 'tt-cloud'); a.cloud.textContent = '⛈️'; a.el.appendChild(a.cloud); }
  }
  function resume(a){  // back to what it was doing after a cuddle or a fall
    var r = a.resume; a.resume = null;
    if (a.mode === 'live' && (!r || r === 'idle' || r === 'stroll' || r === 'nap' || r === 'happy' || r === 'out')) { stroll(a); return; }
    if (r === 'leave') { a.phase = 'leave'; cls(a, ''); return; }
    a.phase = 'go'; cls(a, '');  // was coming to the bowl (or passing): carries on from here
  }
  function after(a){  // what a housemate does when it has eaten (and napped)
    if (a.mode === 'live') { a.phase = 'idle'; a.t = rnd(1, 2.5); cls(a, 'tt-idle'); a.fedUntil = Date.now() + 120000; }  // fed: it stays with you
    else { a.phase = 'leave'; cls(a, '');
      // passing by: carries on to the other side; after eating: either side
      var right = a.mode === 'walk' ? !a.fromRight : Math.random() < .5; a.exitX = right ? innerWidth + 40 : -a.w - 40;
      if (a.mode === 'bowl') next(); }
  }
  function popAt(x, y, sym){ var p = mk('span', 'tt-pop'); p.textContent = sym; p.style.left = Math.round(x) + 'px'; p.style.top = Math.round(y) + 'px';
    layer().appendChild(p); setTimeout(function(){ p.remove(); }, 1400); }
  function step(ts){
    st.raf = 0; if (!st.cfg) return;  // switched off while a frame was waiting
    var dt = st.last ? Math.min(.05, (ts - st.last) / 1000) : .016; st.last = ts; var v = st.cfg.speed;
    for (var i = st.actors.length - 1; i >= 0; i--) {
      var a = st.actors[i], tx = null, ty = null, speed = v;
      if (a.phase === 'go') { var b = bowlAt(a); if (b) { tx = b.x; ty = b.y; } else if (a.mode === 'walk') { tx = a.tx; ty = a.y; } else after(a); }
      if (a.phase === 'stroll') { tx = a.tx; ty = a.ty; speed = v * (a.pace || .55); }
      if (a.phase === 'out') { tx = a.exitX; ty = a.y; speed = v * .7; }
      if (a.phase === 'held') { if (a.el.classList.contains('tt-struggle')) { a.popT -= dt; if (a.popT <= 0) { a.popT = .7; pop(a, ['💢', '😤'][Math.floor(Math.random() * 2)]); } } place(a); continue; }
      if (a.phase === 'land') { a.t -= dt; if (a.t <= 0) resume(a); place(a); continue; }
      if (a.phase === 'happy') { a.t -= dt; if (a.t <= 0) resume(a); }
      if (a.phase === 'idle') { a.t -= dt;
        if (a.t <= 0) { if (a.mode === 'live') { var r = Math.random();  // like a pet: mostly wanders, sometimes naps, sometimes goes out
            if (st.cfg.nap && r < .14) { a.phase = 'nap'; a.t = rnd(3, 6); a.popT = 0; cls(a, 'tt-napping'); }
            else if (r > .84 && !(a.fedUntil > Date.now())) goOut(a); else stroll(a); } else after(a); } }
      if (a.phase === 'eat') { a.t -= dt; a.popT -= dt;
        var nb = a.mode === 'walk' ? null : bowlAt(a);
        if (a.mode !== 'walk' && (!nb || Math.abs(nb.x - a.x) + Math.abs(nb.y - a.y) > 24)) angry(a);  // bowl taken away while eating; storm cloud over its head
        else if (st.cfg.hearts && a.popT <= 0) { a.popT = .45; pop(a, '❤️'); }
        if (a.t <= 0) { if (st.cfg.nap && a.mode !== 'live') { a.phase = 'nap'; a.t = 3; a.popT = 0; cls(a, 'tt-napping'); } else after(a); } }
      if (a.phase === 'nap') { a.t -= dt; a.popT -= dt;
        if (a.popT <= 0) { a.popT = 1; pop(a, '💤'); }
        if (a.t <= 0) { if (a.mode === 'live') stroll(a); else after(a); } }
      if (a.phase === 'snub') { tx = a.snubX; ty = a.y; speed = v * .8; }
      if (a.phase === 'scoff') { a.t -= dt; a.popT -= dt;  // cross, without turning round
        if (a.popT <= 0) { a.popT = .45; pop(a, ['💢', '😤', '🙄'][Math.floor(Math.random() * 3)]); }
        if (a.t <= 0) { a.phase = 'retreat'; cls(a, ''); } }
      if (a.phase === 'retreat') { tx = a.backX; ty = a.y; speed = v * .7; }  // backs off, still facing you
      if (a.phase === 'angry') { a.t -= dt; if (a.t <= 0) { a.phase = 'sulk'; cls(a, 'tt-sulk'); a.flip = a.x < innerWidth / 2; } }  // stomps off, still angry
      if (a.phase === 'sulk') { tx = a.flip ? -a.w - 40 : innerWidth + 40; ty = a.y; speed = v * 1.4; }
      if (a.phase === 'leave') { tx = a.exitX !== undefined ? a.exitX : innerWidth + 40; ty = a.y; }
      if (tx !== null) {
        var dx = tx - a.x, dy = ty - a.y, d = Math.sqrt(dx * dx + dy * dy);
        if (d < 3) {
          a.x = tx; a.y = ty;
          if (a.phase === 'go') { a.phase = 'eat'; a.t = a.mode === 'walk' ? 1.6 : st.cfg.eat; cls(a, 'tt-eating');  // from here it lets go of the bowl
            var fb = a.mode === 'walk' ? null : bowlAt(a); if (fb) a.flip = fb.right; }  // facing the bowl
          else if (a.phase === 'stroll') { a.phase = 'idle'; a.t = rnd(1.5, 6); cls(a, 'tt-idle'); }
          else if (a.phase === 'snub') { a.phase = 'scoff'; a.t = 1.4; a.popT = 0; cls(a, 'tt-angry');
            if (!a.cloud) { a.cloud = mk('div', 'tt-cloud'); a.cloud.textContent = '⛈️'; a.el.appendChild(a.cloud); } }
          else if (a.phase === 'retreat') {  // hidden again; if its time was up meanwhile, it comes back now
            var aw = st.away[a.kind], back = aw && aw.expired, kd = a.kind, sd = aw ? aw.side : null;
            if (aw) aw.snubbing = false; if (back) delete st.away[kd];
            a.el.remove(); st.actors.splice(i, 1); if (back) spawn(kd, 'live', 0, sd); continue; }
          else if (a.phase === 'out') {  // back after a while, from either side
            (function(kind){ st.away[kind] = {timer: setTimeout(function(){ delete st.away[kind]; if (st.cfg && st.cfg.mode === 'live') spawn(kind, 'live', 0); }, rnd(15000, MAX_AWAY))}; })(a.kind);
            a.el.remove(); st.actors.splice(i, 1); continue; }
          else if (a.phase === 'leave' || a.phase === 'sulk') {
            if (a.phase === 'sulk' && a.snub) { if (st.away[a.kind]) st.away[a.kind].snubbing = false; }  // back in hiding, still cross: the old timer goes on
            else if (a.phase === 'sulk' && a.mode === 'live') {  // waits behind the edge, then comes back from there
              (function(kind, right, info){ st.away[kind] = {side: right ? 'right' : 'left', cross: true, info: info, until: Date.now() + awayFor(a), timer: setTimeout(function(){
                if (st.actors.some(function(x){ return x.kind === kind && x.snub; })) { if (st.away[kind]) st.away[kind].expired = true; return; }  // peeking right now
                delete st.away[kind];
                if (st.cfg && st.cfg.mode === 'live') spawn(kind, 'live', 0, right ? 'right' : 'left'); }, awayFor(a))}; })(a.kind, !a.flip, {side: !a.flip ? 'right' : 'left', y: a.y, w: a.w, h: a.h}); }  // hides behind the edge, comes back by itself
            if (a.phase === 'sulk' && a.mode === 'bowl') next();
            a.el.remove(); st.actors.splice(i, 1); continue; }
        } else { var m = Math.min(d, speed * dt); a.x += dx / d * m; a.y += dy / d * m;
          if (Math.abs(dx) > 1 && a.phase !== 'snub' && a.phase !== 'retreat') a.flip = dx < 0; }  // peeking: never turns round
      }
      place(a);
    }
    if (st.actors.length) loop(); else st.last = 0;
  }
  function makeBowl(cfg, kind, k){
    var info = cfg.bowls[kind], key = 'tt-bowl-pos-' + kind;
    var b = mk('button'); b.className = 'tt-bowl'; b.type = 'button'; if (k === 0) b.id = 'tt-bowl';
    var pos = null; try { pos = JSON.parse(localStorage.getItem(key)); } catch (e) {}
    b.style.right = (pos ? pos.r : 24 + k * (Math.round(info.vmin * short() / 100) + 12)) + 'px'; b.style.bottom = (pos ? pos.b : 96) + 'px';
    var drag = null, moved = false;
    b.addEventListener('pointerdown', function(e){ drag = {x: e.clientX, y: e.clientY, r: parseFloat(b.style.right), b: parseFloat(b.style.bottom)}; moved = false; b.setPointerCapture(e.pointerId); });
    b.addEventListener('pointermove', function(e){ if (!drag) return; var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) moved = true;
      if (moved) { b.style.right = Math.max(0, Math.min(innerWidth - b.offsetWidth, drag.r - dx)) + 'px'; b.style.bottom = Math.max(0, Math.min(innerHeight - b.offsetHeight, drag.b - dy)) + 'px'; } });
    b.addEventListener('pointerup', function(){ if (drag && moved) { try { localStorage.setItem(key, JSON.stringify({r: parseFloat(b.style.right), b: parseFloat(b.style.bottom)})); } catch (e) {} } drag = null; });
    b.addEventListener('click', function(e){ if (moved) { moved = false; e.preventDefault(); return; } call(kind); });
    b.setAttribute('aria-label', info.title); b.style.backgroundImage = 'url("' + info.svg + '")';  // aria-label: screen readers only, no hover tooltip
    sizeBowl(b, info);
    D.body.appendChild(b); return b;
  }
  function teardown(){ st.actors.forEach(function(a){ a.el.remove(); }); st.actors = []; st.queue = [];
    Object.keys(st.away).forEach(function(k){ clearTimeout(st.away[k].timer); }); st.away = {};
    Object.keys(st.bowls).forEach(function(k){ st.bowls[k].remove(); }); st.bowls = {}; clearInterval(st.timer); st.timer = 0; }
  function makeBowls(cfg){ (cfg.who || []).forEach(function(kind, k){ if (cfg.bowls && cfg.bowls[kind] && (!st.bowls[kind] || !st.bowls[kind].isConnected)) st.bowls[kind] = makeBowl(cfg, kind, k); }); }
  function call(kind){  // its bowl was clicked: that one comes to eat
    if (!st.cfg) return;
    var a = st.actors.filter(function(x){ return x.kind === kind; })[0];
    if (st.cfg.mode === 'live') {
      var w = st.away[kind];
      if (!a && w && w.cross) {  // still cross: 'I do not care about your food, you offended me'
        if (w.snubbing) return; w.snubbing = true;   // just peeks in from its edge, shows it is cross, backs off
        var sa = spawn(kind, 'live', 0, w.side); if (!sa) return;
        sa.snub = true; sa.phase = 'snub'; sa.el.classList.add('tt-cross'); sa.y = Math.min(w.info.y, ground(sa)); sa.flip = w.side === 'right';  // facing you
        sa.snubX = w.side === 'right' ? innerWidth - sa.w * .45 : -sa.w * .55;          // about half of it shows
        sa.backX = w.side === 'right' ? innerWidth + 20 : -sa.w - 20; return; }
      if (!a && w) {  // out for a walk: the food brings it back to you right away
        clearTimeout(w.timer); delete st.away[kind];
        a = spawn(kind, 'live', 0, w.side); if (!a) return;
      }
      // still cross while on the screen (walking in, scoffing, stomping off): the food does not bring it
      if (a && (a.snub || ['eat', 'sulk', 'angry', 'held', 'snub', 'scoff', 'retreat'].indexOf(a.phase) >= 0)) return;
      if (a) { a.phase = 'go'; cls(a, ''); loop(); }
      return; }
    if (!a) spawn(kind, 'bowl');
  }
  // Teams window resized: everything follows the new size and stays inside (except who went out on purpose)
  var ON_SCREEN = ['stroll', 'idle', 'happy', 'nap', 'land', 'eat', 'go', 'held', 'angry'];
  function clamp(v, lo, hi){ return Math.max(lo, Math.min(hi, v)); }
  function fit(){
    if (!st.cfg) return;
    Object.keys(st.bowls).forEach(function(k){ var b = st.bowls[k], info = st.cfg.bowls && st.cfg.bowls[k]; if (!info) return;
      sizeBowl(b, info); var px = b.offsetWidth;
      b.style.right = clamp(parseFloat(b.style.right) || 0, 0, Math.max(0, innerWidth - px)) + 'px';
      b.style.bottom = clamp(parseFloat(b.style.bottom) || 0, 0, Math.max(0, innerHeight - px)) + 'px'; });
    var u = short() / (st.cfg.ref || 640);
    st.actors.forEach(function(a){ var s = st.cfg.sprites[a.kind]; if (!s) return;
      a.w = Math.round(s.w * u); a.h = Math.round(s.h * u); a.el.style.width = a.w + 'px'; a.el.style.height = a.h + 'px';
      if (ON_SCREEN.indexOf(a.phase) >= 0) { a.x = clamp(a.x, 0, Math.max(0, innerWidth - a.w)); a.y = clamp(a.y, 0, ground(a)); }
      else a.y = clamp(a.y, 0, ground(a));
      if (a.phase === 'stroll') { a.tx = clamp(a.tx, 0, Math.max(0, innerWidth - a.w)); a.ty = clamp(a.ty, innerHeight * .16, ground(a)); }
      if (a.phase === 'leave' || a.phase === 'out' || a.phase === 'sulk') a.exitX = a.exitX !== undefined && a.exitX > 0 ? innerWidth + 40 : a.exitX;
      if (a.phase === 'snub' || a.phase === 'retreat') { var right = a.snubX > innerWidth / 2 || (a.backX || 0) > 0;
        a.snubX = right ? innerWidth - a.w * .45 : -a.w * .55; a.backX = right ? innerWidth + 20 : -a.w - 20; }
      place(a); });
    loop();
  }
  var fitT = 0; window.addEventListener('resize', function(){ clearTimeout(fitT); fitT = setTimeout(fit, 80); });
  window.__ttPetsBurst = function(){
    if (!st.cfg) return;
    if (st.cfg.mode === 'walk') { spawn(st.cfg.who[Math.floor(Math.random() * st.cfg.who.length)], 'walk'); return; }
    st.cfg.who.forEach(call);  // everybody to their own bowl
  };
  window.__ttPetsSetup = function(cfg){
    if (cfg && cfg.respect && matchMedia('(prefers-reduced-motion: reduce)').matches) cfg = null;
    var key = JSON.stringify(cfg);
    // only the ones really missing: not those out for a walk, not those hiding because they are cross
    function missing(k){ return !st.actors.some(function(a){ return a.kind === k; }) && !st.away[k]; }
    if (key === st.key) {  // same housemates: just make sure their things are still on the page
      if (cfg) makeBowls(cfg);
      if (cfg && cfg.mode === 'live') cfg.who.forEach(function(k, j){ if (missing(k)) spawn(k, 'live', j); });
      return; }
    // settings changed: whoever is cross stays cross until its time is up
    var cross = {}; Object.keys(st.away).forEach(function(k){ var w = st.away[k]; if (w.cross) cross[k] = {side: w.side, info: w.info, until: w.until}; });
    teardown(); st.key = key; st.cfg = cfg;
    if (!cfg || !D.body) return;
    makeBowls(cfg);
    if (cfg.mode === 'live') cfg.who.forEach(function(k, j){
      var c = cross[k], left = c ? c.until - Date.now() : 0;
      if (c && left > 0) { st.away[k] = {side: c.side, cross: true, info: c.info, until: c.until, timer: setTimeout(function(){ delete st.away[k];
        if (st.cfg && st.cfg.mode === 'live') spawn(k, 'live', 0, c.side); }, left)}; }
      else spawn(k, 'live', j); });
    if (cfg.mode === 'walk') st.timer = setInterval(function(){ window.__ttPetsBurst(); }, cfg.every * 1000);
  };
})();
""".replace("ENGINE_V", str(ENGINE_VERSION))

# Search by nickname: a normal Teams search with one small extra group on top of Teams' own list, "Soprannomi" (in
# Teams' language), with at most 2 people whose nickname matches what is typed. Teams' list is left as it is (a person
# may be in both). A click on a nickname opens that person as a click on Teams' own result would. Keys stay Teams' own.
# Only the typed text decides the rows, so the group does not jump; any error only drops these rows. A text box without
# a Teams list gets the same rows in a small list of its own. The real name is drawn by CSS (attr()), so the nickname
# replacement, which works on text, leaves it alone.
SEARCH_VERSION = 12
SEARCH_JS = r"""
(function(){
  var V = SEARCH_V;
  if (window.__ttSearchV === V) return;
  if (window.__ttSearchOff) window.__ttSearchOff();
  window.__ttSearchV = V;
  var target = null, items = [], key = '', sec = null, float = null, obs = null, wait = 0, decided = false, since = 0, lastVal = null;
  var setVal = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  var sheet = new CSSStyleSheet();
  sheet.replaceSync('.tt-s-sec{display:flex;flex-direction:column;padding:4px 0 6px;font-family:var(--fontFamilyBase,inherit);border-bottom:1px solid var(--colorNeutralStroke2,#e0e0e0)}'
    + '.tt-s-head{padding:6px 16px 2px;font-size:12px;line-height:16px;color:var(--colorNeutralForeground3,#616161)}'
    + '.tt-s-row{all:unset;box-sizing:border-box;display:flex;align-items:center;gap:12px;min-height:48px;padding:6px 16px;cursor:pointer;color:var(--colorNeutralForeground1,#242424)}'
    + '.tt-s-row:hover{background:var(--colorNeutralBackground1Hover,#f5f5f5)}'
    + '.tt-s-av{flex:none;width:32px;height:32px;border-radius:999px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;'
    + 'background:var(--colorBrandBackground2,#ebf3fc);color:var(--colorBrandForeground2,#115ea3)}'
    + '.tt-s-txt{flex:1;min-width:0;display:flex;flex-direction:column}'
    + '.tt-s-txt b{font-size:14px;line-height:20px;font-weight:600}'
    + '.tt-s-real{font-size:12px;line-height:16px;color:var(--colorNeutralForeground3,#616161);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}'
    + '.tt-s-real::before{content:attr(data-name)}'
    + '.tt-s-sec .tt-s-clone{cursor:pointer}.tt-s-sec .tt-s-clone:hover{background:var(--colorNeutralBackground1Hover,#f5f5f5)}'
    + '#tt-search{position:fixed;z-index:2147483647;box-sizing:border-box;border-radius:8px;border:1px solid var(--colorNeutralStroke1,#d1d1d1);'
    + 'background:var(--colorNeutralBackground1,#fff);box-shadow:0 8px 24px rgba(0,0,0,.28)}'
    + '#tt-search[hidden]{display:none}');
  document.adoptedStyleSheets = document.adoptedStyleSheets.concat([sheet]);
  var norm = function(s){ return String(s).toLowerCase().normalize('NFD').replace(/\p{M}/gu, ''); };
  // nickname -> the real name to search ('Name Surname' preferred over 'Surname, Name')
  var people = function(){ var by = {}, p = window.__ttPairs || [];
    for (var i = 0; i < p.length; i++) { var real = p[i][0], nick = p[i][1];
      if (!by[nick] || (by[nick].indexOf(',') >= 0 && real.indexOf(',') < 0)) by[nick] = real; }
    return by; };
  var popupOf = function(el){ var id = el.getAttribute('aria-controls'), p = id && document.getElementById(id);
    return p && p.offsetHeight > 0 ? p : null; };
  // only what is typed decides the rows (Teams' own list is left as it is, a person may be in both): the section stays put
  var matches = function(el){ var q = norm((el.value || '').trim()); if (q.length < 2) return [];
    var by = people(), out = [];
    for (var nick in by) { var n = norm(nick), real = by[nick];
      if (norm(real) === q) return [];
      if (n.indexOf(q) === 0 || n.indexOf(' ' + q) >= 0) out.push([nick, real]); }
    // alphabetical by the original name, as Teams writes it ('Surname, Name'), like the list in the app
    var key = function(it){ var v = variants(it[0]); return v.filter(function(s){ return s.indexOf(',') >= 0; })[0] || v[0] || it[1]; };
    out.sort(function(a, b){ return key(a).localeCompare(key(b), undefined, {sensitivity: 'base'}); });
    return out.slice(0, 2); };
  // in Teams' own language: Teams in English gets 'Nicknames'
  var label = function(){ return /^it/i.test(document.documentElement.lang || navigator.language) ? 'Soprannomi' : 'Nicknames'; };
  var initials = function(name){ return name.split(/[\s,]+/).filter(Boolean).slice(0, 2).map(function(w){ return w[0].toUpperCase(); }).join(''); };
  // what a row of Teams says, with the real names (the nickname replacement keeps them in __ttOrig)
  var realText = function(root){ var it = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), t, s = '';
    while ((t = it.nextNode())) s += (t.__ttOrig !== undefined ? t.__ttOrig : t.nodeValue);
    return s; };
  var variants = function(nick){ var p = window.__ttPairs || [], out = [];
    for (var i = 0; i < p.length; i++) if (p[i][1] === nick) out.push(p[i][0]);
    return out; };
  // Teams' row for a person (the one with the magnifier on its right, whose click opens the chat), not "X in all
  // results" nor a group chat: Teams marks the person's suggestion with a user id ('8:...'). If that mark cannot be
  // read, the row's text tells it: the name followed by the person's alias in brackets.
  var isPerson = function(o){
    var fk = Object.keys(o).filter(function(k){ return k.indexOf('__reactFiber') === 0; })[0], f = fk && o[fk];
    for (var h = 0; h < 8 && f; h++, f = f.return) { var s = f.memoizedProps && f.memoizedProps.suggestion;
      if (s) return typeof s.id === 'string' && s.id.indexOf('8:') === 0; }
    return /^[^,(]+, [^,(]+ ?\(/.test(realText(o)); };
  var personRows = function(pop){ return [].filter.call(pop.querySelectorAll('[role="option"][data-tid^="AUTOSUGGEST_SUGGESTION_TOPHITS"]'), isPerson); };
  var titleOf = function(o){ var t = o.querySelector('[data-tid="AUTOSUGGEST_SUGGESTION_TITLE"]'); return t ? realText(t).trim() : ''; };
  // Rows that look exactly like Teams' own: when Teams shows the row of a person who has a nickname, a copy of it is
  // kept (photo, role, magnifier) in Teams' own storage on this PC; the nickname group then uses it, with the nickname
  // as the name. A person Teams has not shown yet gets a simple row with initials until then.
  var CK = 'tt-search-rows-v2', rows = {};
  try { rows = JSON.parse(localStorage.getItem(CK)) || {}; } catch (e) {}
  var snap = function(o){ var desc = o.querySelector('[data-tid="AUTOSUGGEST_SUGGESTION_DESCRIPTION"]'), dtext = desc ? realText(desc) : '';
    var c = o.cloneNode(true);
    c.querySelectorAll('[hidden]').forEach(function(x){ x.remove(); });
    // Teams' other two buttons (new window, contact card) stay as invisible room, so the magnifier sits where Teams has it
    c.querySelectorAll('[data-tid="AUTOSUGGEST_ACTION_POPOUTPERSONCHAT"], [data-tid="AUTOSUGGEST_ACTION_PERSONLPC"]').forEach(function(x){
      x.setAttribute('style', 'visibility:hidden;pointer-events:none'); x.setAttribute('aria-hidden', 'true'); });
    [c].concat([].slice.call(c.querySelectorAll('*'))).forEach(function(x){
      ['id', 'aria-describedby', 'aria-selected', 'data-nav', 'data-subnav', 'tabindex'].forEach(function(a){ x.removeAttribute(a); }); });
    c.removeAttribute('data-tid');
    var d = c.querySelector('[data-tid="AUTOSUGGEST_SUGGESTION_DESCRIPTION"]'); if (d) d.textContent = dtext;
    return JSON.stringify(ser(c)); };
  // Teams does not allow HTML text to become elements (Trusted Types): the copy is kept as a plain tree and rebuilt
  // element by element; event attributes are never copied.
  var ser = function(e){ if (e.nodeType === 3) return e.nodeValue; if (e.nodeType !== 1) return null;
    return {n: e.localName, s: e.namespaceURI, a: [].filter.call(e.attributes, function(x){ return !/^on/i.test(x.name); }).map(function(x){ return [x.name, x.value]; }),
            c: [].map.call(e.childNodes, ser).filter(function(x){ return x !== null; })}; };
  var des = function(j){ if (typeof j === 'string') return document.createTextNode(j);
    var e = document.createElementNS(j.s || 'http://www.w3.org/1999/xhtml', j.n);
    j.a.forEach(function(x){ if (!/^on/i.test(x[0])) e.setAttribute(x[0], x[1]); });
    j.c.forEach(function(k){ e.appendChild(des(k)); });
    return e; };
  var capture = function(pop){ var by = people(), changed = false;
    personRows(pop).forEach(function(o){ var name = titleOf(o); if (!name) return;
      for (var nick in by) if (variants(nick).indexOf(name) >= 0) { var h = snap(o); if (rows[nick] !== h) { rows[nick] = h; changed = true; } } });
    if (changed) { try { localStorage.setItem(CK, JSON.stringify(rows)); } catch (e) {} }
    return changed; };
  // A click on a nickname works like a click on that person in Teams' results, which opens the chat (the magnifier:
  // all results from that person): the real name goes in the search and, as soon as Teams lists the person, the same
  // is clicked on Teams' row. If it does not come within 5 s, the search simply stays there with the real name.
  var use = function(i, how){ var it = items[i], el = target; if (!it || !el) return;
    var vs = variants(it[0]), t0 = Date.now();
    el.focus(); setVal.call(el, it[1]); el.dispatchEvent(new Event('input', {bubbles: true}));
    try { el.setSelectionRange(it[1].length, it[1].length); } catch (e) {}
    clear();
    var look = safe(function(){
      var pop = popupOf(el), o = pop && personRows(pop).filter(function(r){ return vs.indexOf(titleOf(r)) >= 0; })[0];
      if (o) { capture(pop); var lens = how === 'lens' && o.querySelector('[data-tid="AUTOSUGGEST_ACTION_PEOPLECENTRICSEARCH"]'); (lens || o).click(); return; }
      if (Date.now() - t0 < 5000 && document.activeElement === el) setTimeout(look, 150); });
    setTimeout(look, 150); };
  var copyRow = function(it, i){ var r = null;
    try { r = rows[it[0]] ? des(JSON.parse(rows[it[0]])) : null; } catch (e) { r = null; }
    if (!r || r.nodeType !== 1 || r.getAttribute('role') !== 'option') return null;
    r.classList.add('tt-s-clone'); r.setAttribute('aria-label', it[0] + ' (' + it[1] + ')');
    var title = r.querySelector('[data-tid="AUTOSUGGEST_SUGGESTION_TITLE"]');
    if (title) { var hb = title.querySelector('b'), q = norm(((target && target.value) || '').trim()), n = it[0], at = norm(n).indexOf(q);
      title.replaceChildren();
      if (hb && q && at >= 0) { if (at) title.append(n.slice(0, at)); var b = hb.cloneNode(false); b.textContent = n.slice(at, at + q.length); title.append(b);
        if (at + q.length < n.length) title.append(n.slice(at + q.length)); }
      else title.textContent = n; }
    var img = r.querySelector('img');
    if (img) img.addEventListener('error', function(){ var av = document.createElement('span'); av.className = 'tt-s-av'; av.textContent = initials(it[1]); img.replaceWith(av); });
    var lens = r.querySelector('[data-tid="AUTOSUGGEST_ACTION_PEOPLECENTRICSEARCH"]');
    if (lens) lens.addEventListener('click', function(e){ e.stopPropagation(); use(i, 'lens'); });
    r.addEventListener('click', function(){ use(i, 'chat'); });
    return r; };
  var build = function(node){
    node.replaceChildren();
    var h = document.createElement('div'); h.className = 'tt-s-head'; h.textContent = label(); node.appendChild(h);
    items.forEach(function(it, i){
      var copy = node !== float && copyRow(it, i);
      if (copy) { node.appendChild(copy); return; }
      var b = document.createElement('button'); b.type = 'button'; b.className = 'tt-s-row'; b.tabIndex = -1;
      b.setAttribute('role', 'option'); b.setAttribute('aria-label', it[0] + ': ' + it[1]);
      var av = document.createElement('span'); av.className = 'tt-s-av'; av.setAttribute('aria-hidden', 'true'); av.textContent = initials(it[1]);
      var tx = document.createElement('span'); tx.className = 'tt-s-txt';
      var nk = document.createElement('b'); nk.textContent = it[0];
      var rl = document.createElement('span'); rl.className = 'tt-s-real'; rl.setAttribute('data-name', it[1]);
      tx.append(nk, rl); b.append(av, tx);
      b.addEventListener('click', function(){ use(i, 'chat'); });
      node.appendChild(b);
    });
  };
  var newSec = function(){ var s = document.createElement('div'); s.className = 'tt-s-sec'; s.setAttribute('role', 'group'); s.setAttribute('aria-label', label());
    s.addEventListener('mousedown', function(e){ e.preventDefault(); }); return s; };
  // where the nicknames go in Teams' own list: right before the first results, after the filter chips
  var spot = function(pop){ var list = pop.firstElementChild; if (!list) return null;
    var kids = [].filter.call(list.children, function(c){ return c !== sec; });
    var at = kids.filter(function(c){ return !c.querySelector('[data-tid="AUTOSUGGEST_GROUP_PRIMARYDOMAIN"]'); })[0] || null;
    return {list: list, before: at}; };
  var clear = function(){ items = []; key = ''; if (sec) sec.remove(); sec = null; if (float) float.hidden = true;
    if (obs) obs.disconnect(); obs = null; };
  var putBack = function(pop){ var s = sec && spot(pop);
    if (s && (sec.parentElement !== s.list || sec.nextElementSibling !== s.before)) s.list.insertBefore(sec, s.before); };
  var render = function(el){
    var pop = popupOf(el);
    target = el;
    if (!pop && el.getAttribute('aria-controls')) { clear(); return; }  // Teams' list is not open yet: never a box of our own
    if (pop) capture(pop);
    items = matches(el, pop);
    if (!items.length) { clear(); return; }
    var k = JSON.stringify(items.map(function(it){ return [it, !!rows[it[0]]]; }));
    if (pop) {
      if (float) float.hidden = true;
      if (!spot(pop)) return;
      if (!sec) sec = newSec();
      if (!sec.isConnected || k !== key) build(sec);
      putBack(pop);
      key = k;
      return;
    }
    // no list of Teams to join (another text box): a small list of its own under the box
    if (sec) { sec.remove(); sec = null; }
    if (!float || !float.isConnected) { float = newSec(); float.id = 'tt-search'; document.body.appendChild(float); }
    var cs = getComputedStyle(el);
    ['--colorNeutralBackground1', '--colorNeutralBackground1Hover', '--colorNeutralForeground1', '--colorNeutralForeground3',
     '--colorNeutralStroke1', '--colorNeutralStroke2', '--colorBrandBackground2', '--colorBrandForeground2', '--fontFamilyBase'].forEach(function(v){
      var x = cs.getPropertyValue(v); if (x) float.style.setProperty(v, x); });
    if (k !== key || float.hidden) build(float);
    key = k;
    var r = el.getBoundingClientRect(), w = Math.max(260, Math.min(r.width, 400));
    float.style.width = w + 'px'; float.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.left)) + 'px';
    float.hidden = false;
    var hh = float.offsetHeight, top = r.bottom + 4;
    if (top + hh > innerHeight - 8) top = Math.max(8, r.top - hh - 4);
    float.style.top = top + 'px';
  };
  // never break Teams: whatever goes wrong here only drops the nickname rows
  var safe = function(f){ return function(a){ try { return f(a); } catch (e) { window.__ttSearchErr = String(e && e.stack || e).slice(0, 300); try { clear(); } catch (e2) {} } }; };
  render = safe(render);
  // The rows are drawn at once; if Teams' list is not open yet, as soon as it opens (tried for 3 s).
  // When Teams redraws its list, the same rows are only put back in their place.
  var decide = function(){ clearTimeout(wait); wait = 0; if (!target || document.activeElement !== target) return;
    if (!popupOf(target) && target.getAttribute('aria-controls')) { if (Date.now() - since < 3000) later(); return; }
    watch(target); decided = true; render(target); };
  var later = function(){ clearTimeout(wait); wait = setTimeout(decide, 120); };
  var watch = function(el){ var pop = popupOf(el); if (!pop || (obs && obs.pop === pop)) return;
    if (obs) obs.disconnect();
    var grab = 0;
    obs = new MutationObserver(safe(function(ms){
      if (ms.every(function(m){ return sec && sec.contains(m.target); })) return;
      if (decided) putBack(pop);
      // a person row just shown by Teams: keep its copy, and use it at once if that person is in the group
      clearTimeout(grab); grab = setTimeout(safe(function(){ if (capture(pop) && decided && target && items.length) render(target); }), 300); }));
    obs.pop = pop; obs.observe(pop, {childList: true, subtree: true, characterData: true}); };
  var isBox = function(el){ return !!el && el.nodeName === 'INPUT' && /^(text|search)$/.test(el.type) && !el.readOnly; };
  var onInput = safe(function(e){ if (!isBox(e.target)) return;
    if (e.target === target && e.target.value === lastVal) return;  // Teams giving the focus back, same text: nothing new
    target = e.target; lastVal = e.target.value; since = Date.now(); decided = false; decide(); });
  var onKey = safe(function(e){ if (e.target === target && e.key === 'Escape') clear(); });  // keys stay Teams' own
  var onBlur = function(e){ if (e.target === target) setTimeout(function(){ if (document.activeElement !== target) { clear(); lastVal = null; } }, 150); };
  var onResize = function(){ if (items.length && target) { if (target.isConnected) render(target); else clear(); } };
  document.addEventListener('input', onInput, true); document.addEventListener('focusin', onInput, true);
  document.addEventListener('keydown', onKey, true); document.addEventListener('focusout', onBlur, true);
  window.addEventListener('resize', onResize);
  window.__ttSearchOff = function(){
    document.removeEventListener('input', onInput, true); document.removeEventListener('focusin', onInput, true);
    document.removeEventListener('keydown', onKey, true); document.removeEventListener('focusout', onBlur, true);
    window.removeEventListener('resize', onResize);
    clearTimeout(wait); clear(); if (float) float.remove(); float = null;
    document.adoptedStyleSheets = document.adoptedStyleSheets.filter(function(s){ return s !== sheet; });
    window.__ttSearchV = null; };
})();
""".replace("SEARCH_V", str(SEARCH_VERSION))
# #tt-fx: three empty, click-through elements that the theme CSS can use as extra animated layers.
# #tt-trigger: the button on Teams for the "only when I click" mode; it can be dragged, its place is remembered.
NICK_VERSION = 2  # the nickname replacement on pages already open is replaced when this changes
_JS_APPLY = PETS_ENGINE_JS + SEARCH_JS + """(function(css, ver, trig, nick, pets){
  if (window.__ttPetsSetup) window.__ttPetsSetup(pets);
  // ---- nicknames: names shown differently, display only; never inside what the user types ----
  window.__ttPairs = nick || [];
  if (window.__ttNickV !== NICK_V) {  // replaced on pages already open when this part changes
    if (window.__ttNickObs) window.__ttNickObs.disconnect();
    window.__ttNickV = NICK_V;
    // Real names stay: in what the user types, and in Teams' search (its results show the real names; the nicknames
    // have their own group on top of it).
    var skip = function(t){ var e = t.parentElement; while (e) { if (e.isContentEditable || /^(INPUT|TEXTAREA|SCRIPT|STYLE)$/.test(e.nodeName)
      || (e.id && e.id.indexOf('ms-searchux') === 0)) return true; e = e.parentElement; } return false; };
    window.__ttNickFix = function(t){
      var pairs = window.__ttPairs, cur = t.nodeValue;
      if (!pairs.length && t.__ttOrig === undefined) return;
      var ours = t.__ttOrig !== undefined && cur === t.__ttLast, orig = ours ? t.__ttOrig : cur, v = orig;
      for (var i = 0; i < pairs.length; i++) if (v.indexOf(pairs[i][0]) >= 0) v = v.split(pairs[i][0]).join(pairs[i][1]);
      if (v !== orig && skip(t)) v = orig;
      if (v === cur) { if (v === orig) delete t.__ttOrig; return; }
      if (v === orig) { delete t.__ttOrig; t.nodeValue = v; return; }  // back to the real name
      t.__ttOrig = orig; t.__ttLast = v; t.nodeValue = v;
    };
    window.__ttNickWalk = function(root){ if (!root) return; if (root.nodeType === 3) { window.__ttNickFix(root); return; }
      var it = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), n; while ((n = it.nextNode())) window.__ttNickFix(n); };
    // Light on Teams: changes are queued and handled once per frame, and a whole new piece of page is skipped at once
    // when none of the names is in its text (switching page in Teams adds thousands of nodes).
    var q = [], qT = 0;
    var has = function(txt){ var p = window.__ttPairs; for (var i = 0; i < p.length; i++) if (txt.indexOf(p[i][0]) >= 0) return true; return false; };
    var flush = function(){ qT = 0; var items = q; q = [];
      for (var i = 0; i < items.length; i++) { var n = items[i]; if (!n.isConnected) continue;
        if (n.nodeType === 3) window.__ttNickFix(n); else if (has(n.textContent || '')) window.__ttNickWalk(n); } };
    window.__ttNickObs = new MutationObserver(function(ms){ var pairs = window.__ttPairs.length;
      for (var i = 0; i < ms.length; i++) { var m = ms[i];
        if (m.type === 'characterData') { if (pairs || m.target.__ttOrig !== undefined) q.push(m.target); }
        else if (pairs) for (var j = 0; j < m.addedNodes.length; j++) q.push(m.addedNodes[j]); }
      if (q.length && !qT) qT = requestAnimationFrame(flush); });
    window.__ttNickObs.observe(document.documentElement, {subtree: true, childList: true, characterData: true});
  }
  window.__ttNickDirty = window.__ttNickDirty || window.__ttPairs.length > 0;
  window.__ttNickWalk(document.body);
  var sh = window.__ttSheet;
  if (!sh) { sh = new CSSStyleSheet(); window.__ttSheet = sh; }
  sh.replaceSync(css); sh.disabled = false;
  if (document.adoptedStyleSheets.indexOf(sh) < 0) document.adoptedStyleSheets = document.adoptedStyleSheets.concat([sh]);
  if (document.body && !document.getElementById('tt-fx')) {
    var fx = document.createElement('div'); fx.id = 'tt-fx'; fx.setAttribute('aria-hidden', 'true');
    fx.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483645;';
    for (var i = 0; i < 3; i++) fx.appendChild(document.createElement('i'));
    document.body.appendChild(fx);
  }
  var r = document.documentElement;
  window.__ttBurst = function(){
    window.__ttBowl && window.__ttBowl();
    r.classList.remove('tt-go', 'tt-dance'); void r.offsetWidth; r.classList.add('tt-go', 'tt-dance');
    clearTimeout(window.__ttDanceT); clearTimeout(window.__ttBurstT);
    window.__ttDanceT = setTimeout(function(){ r.classList.remove('tt-dance'); }, 2600);
    window.__ttBurstT = setTimeout(function(){ r.classList.remove('tt-go'); }, window.__ttBurstMs || 20000);
  };
  var b = document.getElementById('tt-trigger');
  // where the bowl is, for the animals that walk to it
  window.__ttBowl = function(){ var x = document.getElementById('tt-trigger'); if (!x) return; var q = x.getBoundingClientRect();
    r.style.setProperty('--tt-bowl-x', Math.round(q.left) + 'px'); r.style.setProperty('--tt-bowl-y', Math.round(q.top) + 'px');
    r.style.setProperty('--tt-bowl-b', Math.round(q.bottom) + 'px'); };
  if (!window.__ttBowlResize) { window.__ttBowlResize = true; window.addEventListener('resize', function(){ window.__ttBowl && window.__ttBowl(); }); }
  if (!trig) { if (b) b.remove(); r.classList.remove('tt-go'); r.style.removeProperty('--tt-bowl-x'); r.style.removeProperty('--tt-bowl-y'); }
  else if (document.body) {
    if (!b) {
      b = document.createElement('button'); b.id = 'tt-trigger'; b.type = 'button';
      var pos = null; try { pos = JSON.parse(localStorage.getItem('tt-trigger-pos')); } catch (e) {}
      b.style.right = (pos ? pos.r : 24) + 'px'; b.style.bottom = (pos ? pos.b : 96) + 'px';
      var drag = null, moved = false;
      b.addEventListener('pointerdown', function(e){ drag = {x: e.clientX, y: e.clientY, r: parseFloat(b.style.right), b: parseFloat(b.style.bottom)}; moved = false; b.setPointerCapture(e.pointerId); });
      b.addEventListener('pointermove', function(e){ if (!drag) return; var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
        if (Math.abs(dx) + Math.abs(dy) > 4) moved = true;
        if (moved) { b.style.right = Math.max(0, Math.min(innerWidth - b.offsetWidth, drag.r - dx)) + 'px'; b.style.bottom = Math.max(0, Math.min(innerHeight - b.offsetHeight, drag.b - dy)) + 'px'; window.__ttBowl(); } });
      b.addEventListener('pointerup', function(){ if (drag && moved) { try { localStorage.setItem('tt-trigger-pos', JSON.stringify({r: parseFloat(b.style.right), b: parseFloat(b.style.bottom)})); } catch (e) {} } drag = null; });
      b.addEventListener('click', function(e){ if (moved) { moved = false; e.preventDefault(); return; } window.__ttBurst(); });
      document.body.appendChild(b);
    }
    b.setAttribute('aria-label', trig.title);  // no hover tooltip
    b.textContent = trig.text; b.style.backgroundImage = trig.svg ? 'url("' + trig.svg + '")' : 'none';
    var sz = trig.size || 46; b.style.width = sz + 'px'; b.style.height = sz + 'px'; b.style.fontSize = Math.round(sz * .65) + 'px';
    window.__ttBurstMs = trig.ms;
    window.__ttBowl();
  }
  window.__ttVer = ver;
  return document.querySelectorAll('.fui-FluentProvider').length;
})(%s, %s, %s, %s, %s)""".replace("NICK_V", str(NICK_VERSION))

_JS_CHECK = """(function(ver, wantTrigger){ var sh = window.__ttSheet;
  return !!sh && !sh.disabled && window.__ttVer === ver && document.adoptedStyleSheets.indexOf(sh) >= 0
         && (!document.body || (!!document.getElementById('tt-fx') && (!wantTrigger || !!document.getElementById('tt-trigger')))); })(%s, %s)"""

_JS_REMOVE = """(function(){ if (window.__ttSheet) window.__ttSheet.disabled = true; window.__ttVer = null;
  if (window.__ttNickWalk) { window.__ttPairs = []; window.__ttNickWalk(document.body); }  // real names back
  if (window.__ttPetsSetup) window.__ttPetsSetup(null);  // housemates and their bowl go away
  if (window.__ttSearchOff) window.__ttSearchOff();  // no more nickname suggestions in the search
  ['tt-fx', 'tt-trigger'].forEach(function(id){ var x = document.getElementById(id); if (x) x.remove(); });
  var r = document.documentElement; r.classList.remove('tt-now', 'tt-dance', 'tt-reset', 'tt-go');
  ['--tt-bowl-x', '--tt-bowl-y', '--tt-bowl-b'].forEach(function(v){ r.style.removeProperty(v); }); return true; })()"""

# Test button: with the Teams button, the same as clicking it; otherwise restart every animation now.
_JS_TEST = """(function(){ var r = document.documentElement;
  if (document.getElementById('tt-trigger') && window.__ttBurst) { window.__ttBurst(); return true; }
  r.classList.remove('tt-now', 'tt-dance'); r.classList.add('tt-reset'); void r.offsetWidth;
  r.classList.remove('tt-reset'); r.classList.add('tt-now', 'tt-dance');
  setTimeout(function(){ r.classList.remove('tt-dance'); }, 2600); return true; })()"""

# Read Teams' own tokens with our sheet switched off for the duration of the read.
_JS_BASE = """(function(){
  var p = document.querySelector('.fui-FluentProvider'); if (!p) return null;
  var sh = window.__ttSheet, was = sh ? sh.disabled : true; if (sh) sh.disabled = true;
  var cs = getComputedStyle(p), o = {};
  for (var i = 0; i < cs.length; i++) { var n = cs[i]; if (n.indexOf('--') === 0) o[n] = cs.getPropertyValue(n).trim(); }
  if (sh) sh.disabled = was;
  o.__reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  return o;
})()"""

# The switch inside Teams, next to Teams' own "Collapse app bar" button at the top left: the same as "Attivo su
# Teams" in the app. It is a copy of that button (same size, colours, hover, focus, light and dark), with an icon of
# its own: a full sparkle when on, an empty crossed-out one when off, and aria-pressed; after a click a small spinner
# takes the sparkle's place and further clicks wait until the app has done it. It stays when Teams Remix is
# off (it is the way to switch it back on). The page never talks to the app: a click is only remembered here, and the
# app collects it through the same local channel it uses to colour Teams (toggle_sync, every check), then saves it
# like a click in its own window. If the app stops asking for a while (closed), the switch goes away by itself.
# Teams redraws its title bar now and then: the switch is put back in its place, never twice. Without that button
# (another layout) nothing is added.
TOGGLE_VERSION = 2
TOGGLE_ID = "tt-remix-toggle"
TOGGLE_JS = r"""
(function(){
  if (window.__ttToggleOff) { try { window.__ttToggleOff(); } catch (e) {} }
  window.__ttToggleV = TOGGLE_V;
  var D = document, ID = 'TOGGLE_ID', NS = 'http://www.w3.org/2000/svg', STALE = 12000;
  var cfg = null, asked = null, waitFor = null, waitAt = 0, shown = false, seen = 0, btn = null, hb = null, hbOpen = null, tip = null, tipT = 0, obs = null, fixT = 0;
  var WAIT = 20000;  // the app normally answers within a few seconds
  // 20x20 like Teams' icons: a big and a small sparkle; off = the same, empty, crossed out
  var BIG = 'M8.5 4.5Q9.4 10.1 15 11Q9.4 11.9 8.5 17.5Q7.6 11.9 2 11Q7.6 10.1 8.5 4.5Z';
  var SMALL = 'M15.5 1.5Q15.9 4.1 18.5 4.5Q15.9 4.9 15.5 7.5Q15.1 4.9 12.5 4.5Q15.1 4.1 15.5 1.5Z';
  function svgEl(tag, attrs){ var e = D.createElementNS(NS, tag); for (var k in attrs) e.setAttribute(k, attrs[k]); return e; }
  function icon(on){
    var s = svgEl('svg', {viewBox: '0 0 20 20', width: '1em', height: '1em', 'font-size': '20px', 'aria-hidden': 'true', focusable: 'false'});
    if (on) { s.style.color = 'var(--colorCompoundBrandForeground1, var(--colorBrandForeground1, currentColor))';
      [BIG, SMALL].forEach(function(d){ s.appendChild(svgEl('path', {d: d, fill: 'currentColor'})); }); }
    else { [BIG, SMALL].forEach(function(d){ s.appendChild(svgEl('path', {d: d, fill: 'none', stroke: 'currentColor', 'stroke-width': '1.1', 'stroke-linejoin': 'round'})); });
      s.appendChild(svgEl('path', {d: 'M2.5 2.5L17.5 17.5', stroke: 'currentColor', 'stroke-width': '1.3', 'stroke-linecap': 'round'})); }
    return s; }
  // while the app does it: a small spinner like Teams' own, in Teams' brand colour
  function spinner(){
    var s = svgEl('svg', {viewBox: '0 0 20 20', width: '1em', height: '1em', 'font-size': '20px', 'aria-hidden': 'true', focusable: 'false'});
    s.style.color = 'var(--colorCompoundBrandForeground1, var(--colorBrandForeground1, currentColor))';
    s.appendChild(svgEl('circle', {cx: '10', cy: '10', r: '6.5', fill: 'none', stroke: 'currentColor', 'stroke-width': '2', opacity: '.25'}));
    var arc = svgEl('path', {d: 'M10 3.5A6.5 6.5 0 0 1 16.5 10', fill: 'none', stroke: 'currentColor', 'stroke-width': '2', 'stroke-linecap': 'round'});
    arc.appendChild(svgEl('animateTransform', {attributeName: 'transform', type: 'rotate', from: '0 10 10', to: '360 10 10', dur: '.9s', repeatCount: 'indefinite'}));
    s.appendChild(arc);
    return s; }
  function busy(){ return asked !== null || waitFor !== null; }
  function stale(){ return !cfg || Date.now() - seen > STALE; }
  // in Teams' own language: Teams in English gets English, whatever the app's language
  function txt(k){ var all = cfg.texts || {}, l = /^it/i.test(D.documentElement.lang || navigator.language) ? all.it : all.en; return (l || all.it || {})[k] || ''; }
  function tipText(){ return !cfg ? '' : txt(busy() ? (shown ? 'tip_wait_on' : 'tip_wait_off') : (shown ? 'tip_on' : 'tip_off')); }
  // a tooltip like Teams' own (Fluent): below the button, after a short wait, in Teams' colours
  function hideTip(){ clearTimeout(tipT); tipT = 0; if (tip) tip.remove(); tip = null; if (btn) btn.removeAttribute('aria-describedby'); }
  function showTip(){ if (!btn || !btn.isConnected || !cfg) return;
    if (!tip) { tip = D.createElement('div'); tip.id = ID + '-tip'; tip.setAttribute('role', 'tooltip');
      tip.style.cssText = 'position:fixed;z-index:2147483647;pointer-events:none;box-sizing:border-box;max-width:240px;padding:4px 11px 6px;'
        + 'border-radius:var(--borderRadiusMedium,4px);border:1px solid var(--colorTransparentStroke,transparent);'
        + 'background:var(--colorNeutralBackground1,#fff);color:var(--colorNeutralForeground1,#242424);'
        + 'font-family:var(--fontFamilyBase,inherit);font-size:var(--fontSizeBase200,12px);line-height:var(--lineHeightBase200,16px);'
        + 'filter:drop-shadow(0 0 2px var(--colorNeutralShadowAmbient,rgba(0,0,0,.12))) drop-shadow(0 4px 8px var(--colorNeutralShadowKey,rgba(0,0,0,.14)))';
      var cs = getComputedStyle(btn);  // Teams' tokens live on its providers, not on the page: take them from the button
      ['--borderRadiusMedium', '--colorTransparentStroke', '--colorNeutralBackground1', '--colorNeutralForeground1', '--fontFamilyBase',
       '--fontSizeBase200', '--lineHeightBase200', '--colorNeutralShadowAmbient', '--colorNeutralShadowKey'].forEach(function(v){
        var x = cs.getPropertyValue(v); if (x) tip.style.setProperty(v, x); });
      D.body.appendChild(tip); }
    tip.textContent = tipText(); btn.setAttribute('aria-describedby', tip.id);
    var r = btn.getBoundingClientRect(), w = tip.offsetWidth;
    tip.style.left = Math.round(Math.max(4, Math.min(innerWidth - w - 4, r.left + r.width / 2 - w / 2))) + 'px';
    tip.style.top = Math.round(r.bottom + 6) + 'px'; }
  function laterTip(){ clearTimeout(tipT); tipT = setTimeout(showTip, 250); }
  function drop(){ hideTip(); [].forEach.call(D.querySelectorAll('#' + ID), function(x){ x.remove(); }); btn = null; hb = null; watch(false); }
  function paint(){ if (!btn || !cfg) return;
    var b = busy();
    btn.setAttribute('aria-label', cfg.label); btn.setAttribute('aria-pressed', String(shown)); btn.setAttribute('data-on', String(shown));
    if (b) { btn.setAttribute('aria-busy', 'true'); btn.setAttribute('aria-disabled', 'true'); btn.style.cursor = 'progress'; }
    else { btn.removeAttribute('aria-busy'); btn.removeAttribute('aria-disabled'); btn.style.cursor = ''; }
    var sp = btn.firstElementChild, key = b ? 'wait' : String(shown);
    if (sp && sp.getAttribute('data-icon') !== key) { sp.setAttribute('data-icon', key); sp.replaceChildren(b ? spinner() : icon(shown)); }
    if (tip) { tip.textContent = tipText(); showTip(); } }
  function make(from){
    var b = D.createElement('button'); b.type = 'button'; b.id = ID; b.className = from.className;
    var fsp = from.querySelector('.fui-Button__icon'), sp = D.createElement('span');
    sp.className = fsp ? fsp.className : 'fui-Button__icon'; b.appendChild(sp);
    b.addEventListener('click', function(e){ e.stopPropagation(); if (!cfg || busy()) return;  // one at a time
      asked = !shown; shown = asked; paint(); });  // the app collects it at its next check
    b.addEventListener('pointerenter', laterTip); b.addEventListener('pointerleave', hideTip);
    b.addEventListener('focus', function(){ if (b.matches(':focus-visible')) laterTip(); }); b.addEventListener('blur', hideTip);
    b.addEventListener('keydown', function(e){ if (e.key === 'Escape') hideTip(); });
    return b; }
  function ok(){ return !!btn && btn.isConnected && !!hb && hb.isConnected && btn.previousElementSibling === hb.parentElement
    && hb.getAttribute('data-appbar-expanded') === hbOpen; }
  function check(){ if (fixT || !cfg || ok()) return; fixT = setTimeout(function(){ fixT = 0; place(); }, 50); }
  function watch(on){ if (on && !obs && D.body) { obs = new MutationObserver(check); obs.observe(D.body, {childList: true, subtree: true, attributes: true, attributeFilter: ['data-appbar-expanded']}); }
    if (!on && obs) { obs.disconnect(); obs = null; } }
  // right after the cell of Teams' button, taking no room: Teams' layout does not move
  function place(){
    if (stale()) { drop(); return false; }
    var h = D.querySelector('[data-tid="hamburger-button"]'), cell = h && h.parentElement, row = cell && cell.parentElement;
    if (!h || !row || !h.offsetWidth) { drop(); return false; }  // another layout, or the button is hidden: nothing of ours
    [].forEach.call(D.querySelectorAll('#' + ID), function(x){ if (x !== btn) x.remove(); });
    if (!btn) { btn = make(h); paint(); }
    if (btn.className !== h.className) btn.className = h.className;  // Teams' own look, whatever it is now
    hb = h; hbOpen = h.getAttribute('data-appbar-expanded');
    if (btn.parentElement !== row || btn.previousElementSibling !== cell) row.insertBefore(btn, cell.nextSibling);
    var hr = h.getBoundingClientRect(), cr = cell.getBoundingClientRect(), w = h.offsetWidth;
    var ml = Math.round(4 - (cr.right - hr.right));  // 4px after Teams' button
    btn.style.margin = '0 ' + (-(w + ml)) + 'px 0 ' + ml + 'px'; btn.style.flex = 'none';
    watch(true);
    return true; }
  var beat = setInterval(function(){ if (btn && stale()) drop(); }, 3000);
  window.__ttToggleSync = function(c){
    seen = Date.now();
    var out = {asked: asked, placed: false};
    // a click goes to the app now; the spinner stays until the app says it is done (its state is the one clicked)
    if (asked !== null) { shown = waitFor = asked; waitAt = Date.now(); asked = null; }
    else if (waitFor !== null && (!c || !!c.on === waitFor || Date.now() - waitAt > WAIT)) waitFor = null;
    if (waitFor === null) shown = !!(c && c.on);
    cfg = c || null;
    if (!cfg) { drop(); return out; }
    out.placed = place(); paint();
    return out; };
  window.__ttToggleOff = function(){ clearInterval(beat); clearTimeout(fixT); cfg = null; drop();
    window.__ttToggleSync = null; window.__ttToggleV = null; };
})();
""".replace("TOGGLE_V", str(TOGGLE_VERSION)).replace("TOGGLE_ID", TOGGLE_ID)


# ---------- config ----------

def load_config():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


_CFG_LOCK = threading.Lock()


def save_config(cfg):
    with _CFG_LOCK:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


# ---------- process ----------

def teams_running():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq ms-teams.exe", "/NH", "/FO", "CSV"],
                         capture_output=True, text=True, creationflags=NO_WINDOW).stdout
    return "ms-teams.exe" in out.lower()


MIC_KEY = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"


def teams_in_call():
    """True while Teams is using the microphone (a call or a meeting, muted too: Teams keeps it open), as Windows
    records it for the privacy indicator: an entry whose last use started and has not stopped yet."""
    import winreg

    def busy(k):
        try:
            start = winreg.QueryValueEx(k, "LastUsedTimeStart")[0]
            stop = winreg.QueryValueEx(k, "LastUsedTimeStop")[0]
        except OSError:
            return False
        return bool(start) and (not stop or start > stop)

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, MIC_KEY) as root:
            names = []
            i = 0
            while True:
                try:
                    names.append(winreg.EnumKey(root, i))
                except OSError:
                    break
                i += 1
            for n in names:
                if "msteams" in n.lower():  # the new Teams (packaged app)
                    with winreg.OpenKey(root, n) as k:
                        if busy(k):
                            return True
            with winreg.OpenKey(root, "NonPackaged") as np:
                i = 0
                while True:
                    try:
                        n = winreg.EnumKey(np, i)
                    except OSError:
                        break
                    i += 1
                    if "ms-teams.exe" in n.lower():
                        with winreg.OpenKey(np, n) as k:
                            if busy(k):
                                return True
    except OSError:
        pass
    return False


def _stop_teams():
    subprocess.run(["taskkill", "/IM", "ms-teams.exe", "/F"], capture_output=True, creationflags=NO_WINDOW)
    for _ in range(40):
        if not teams_running():
            return
        time.sleep(0.25)


def _start_teams(extra_args=None):
    exe = shutil.which("ms-teams.exe") or str(Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "WindowsApps" / "ms-teams.exe")
    env = dict(os.environ)
    env.pop("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", None)
    if extra_args:
        env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = extra_args  # this child only, never global
    subprocess.Popen([exe], env=env, creationflags=NO_WINDOW, close_fds=True)


def restart_with_port(cfg, wait_s=60):
    """Restart Teams with a debug port on 127.0.0.1. Returns the port, or None if it never opened
    (in that case Teams is restarted normally: one attempt, no workarounds)."""
    port = random.randint(20000, 60000)
    _stop_teams()
    _start_teams(f"--remote-debugging-port={port}")
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if cdp.port_alive(port):
            cfg["port"] = port
            save_config(cfg)
            return port
        time.sleep(1)
    restart_normal(cfg)
    return None


def restart_normal(cfg):
    _stop_teams()
    _start_teams(None)
    cfg.pop("port", None)
    save_config(cfg)


def live_port(cfg):
    p = cfg.get("port")
    return p if cdp.port_alive(p) else None


# ---------- theme ----------

def base_tokens(port):
    for t in cdp.pages(port):
        try:
            v = cdp.evaluate(t["webSocketDebuggerUrl"], _JS_BASE)
        except (OSError, RuntimeError):
            continue
        if v:
            return v
    return None


def is_popup(target):
    """Teams' notification toasts live in their own small window."""
    return "entityType=toasts" in (target.get("url") or "")


def _for(target, css, trigger, popup_css):
    if is_popup(target):
        return (popup_css if popup_css is not None else css), None  # no button inside a notification
    return css, trigger


def name_forms(src):
    """Every way Teams may write a name. It is written 'Surname Name' ('Verdi Luna'): Teams writes people of the
    company 'Verdi, Luna' and guests 'Luna Verdi'. With two or more words any split may be the surname, so all are
    tried. 'Verdi, Luna' (with the comma) keeps working."""
    src = " ".join(src.split())
    if ", " in src:
        last, first = src.split(", ", 1)
        return [src, f"{first} {last}", f"{last} {first}"]
    words, forms = src.split(" "), [src]
    for i in range(1, len(words)):
        last, first = " ".join(words[:i]), " ".join(words[i:])
        forms += [f"{last}, {first}", f"{first} {last}"]
    return forms


# ---------- a photo for a nickname ----------
# The photo is shown on Teams instead of that person's picture, only on this PC. Teams draws every picture of a person
# (photo or initials) as an image whose address carries the name ('profilepicturev2/...?displayname=Verdi%2C%20Luna'),
# so a style rule swaps it: Teams' own pages are not touched. Group pictures (several people in one) stay as they are.
# The photos are copied into the app's folder, named by their content.
PHOTOS_DIR = CONFIG_DIR / "photos"
PHOTO_TYPES = {"jpeg": (".jpg", b"\xff\xd8\xff"), "png": (".png", b"\x89PNG"), "webp": (".webp", b"RIFF")}
PHOTO_MAX = 600 * 1024
_photo_cache = {}


def valid_photo_name(name):
    import re
    return bool(isinstance(name, str) and re.fullmatch(r"[0-9a-f]{16}\.(jpg|png|webp)", name) and (PHOTOS_DIR / name).is_file())


def save_photo(data_url):
    """'data:image/jpeg;base64,...' (made small by the app's window) -> the file name in the app's folder."""
    import base64
    import hashlib
    import re
    m = re.fullmatch(r"data:image/(jpeg|png|webp);base64,([A-Za-z0-9+/=]+)", str(data_url or ""))
    if not m:
        raise ValueError(tr("Foto non valida: usa un'immagine JPG o PNG."))
    raw = base64.b64decode(m.group(2))
    ext, magic = PHOTO_TYPES[m.group(1)]
    if len(raw) > PHOTO_MAX or not raw.startswith(magic):
        raise ValueError(tr("Foto non valida o troppo grande."))
    name = hashlib.sha1(raw).hexdigest()[:16] + ext
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    (PHOTOS_DIR / name).write_bytes(raw)
    return name


def clean_photos(items):
    """Photos no nickname uses any more are deleted (not the ones just added: their nickname is saved right after)."""
    used = {it.get("photo") for it in items or []}
    try:
        for f in PHOTOS_DIR.iterdir():
            if f.is_file() and f.name not in used and time.time() - f.stat().st_mtime > 600:
                f.unlink()
    except OSError:
        pass


def photo_css(items):
    """Style rules that show each nickname's photo instead of that person's picture on Teams."""
    import base64
    import urllib.parse
    out = []
    for it in items or []:
        name, src = it.get("photo"), " ".join(str(it.get("from", "")).split())
        if not src or not str(it.get("to", "")).strip() or not valid_photo_name(name):
            continue
        if name not in _photo_cache:  # names come from the content: a name never changes its photo
            kind = {".jpg": "jpeg", ".png": "png", ".webp": "webp"}[Path(name).suffix]
            _photo_cache[name] = f"data:image/{kind};base64," + base64.b64encode((PHOTOS_DIR / name).read_bytes()).decode()
        sel = []
        for form in name_forms(src):
            q = urllib.parse.quote(form, safe="-_.!~*'()")  # as Teams writes it in the address (encodeURIComponent)
            sel += [f'img[src*="profilepicturev2/"][src*="displayname={q}&"]', f'img[src*="profilepicturev2/"][src$="displayname={q}"]']
        out.append(",\n".join(sel) + f' {{ content: url("{_photo_cache[name]}"); object-fit: cover; }}')
    return ("\n/* nickname photos */\n" + "\n".join(out) + "\n") if out else ""


def nickname_pairs(items):
    """[{'from': 'Verdi Luna', 'to': 'Lunetta'}] -> [[how Teams writes it, nickname], ...], longest first.
    What is written exactly wins over a form worked out for another person."""
    pairs, derived = {}, {}
    for it in items or []:
        src, dst = " ".join(str(it.get("from", "")).split()), str(it.get("to", "")).strip()
        if not src or not dst or src == dst:
            continue
        pairs[src] = dst
        for f in name_forms(src)[1:]:
            derived.setdefault(f, dst)
    for f, dst in derived.items():
        pairs.setdefault(f, dst)
    return sorted(([k, v] for k, v in pairs.items()), key=lambda p: (-len(p[0]), p[0]))


def _apply_js(css, ver, trig, nick, pets):
    return _JS_APPLY % (json.dumps(css), json.dumps(ver), json.dumps(trig), json.dumps(nick or []), json.dumps(pets))


def apply_css(port, css, ver, trigger=None, popup_css=None, nick=None, pets=None):
    """trigger: theme.trigger_config(...) -> the button on Teams for the 'click' mode, or None.
    popup_css: what the notification windows get instead of `css`. nick: nickname_pairs(...), everywhere.
    pets: theme.pets_config(...) for the movement engine, main windows only."""
    done = 0
    for t in cdp.pages(port):
        c, trig = _for(t, css, trigger, popup_css)
        try:
            cdp.evaluate(t["webSocketDebuggerUrl"], _apply_js(c, ver, trig, nick, None if is_popup(t) else pets))
            done += 1
        except (OSError, RuntimeError):
            pass
    return done


def ensure_css(port, css, ver, trigger=None, popup_css=None, nick=None, pets=None):
    """Re-inject only where the theme is missing (new window, page reload, a new notification). Returns pages fixed."""
    fixed = 0
    for t in cdp.pages(port):
        c, trig = _for(t, css, trigger, popup_css)
        try:
            ok = cdp.evaluate(t["webSocketDebuggerUrl"], _JS_CHECK % (json.dumps(ver), json.dumps(bool(trig))))
            if not ok:
                cdp.evaluate(t["webSocketDebuggerUrl"], _apply_js(c, ver, trig, nick, None if is_popup(t) else pets))
                fixed += 1
        except (OSError, RuntimeError):
            pass
    return fixed


def call_pets(port):
    """'Chiamali ora': the same as clicking their bowl."""
    for t in cdp.pages(port):
        if is_popup(t):
            continue
        try:
            cdp.evaluate(t["webSocketDebuggerUrl"], "(window.__ttPetsBurst && window.__ttPetsBurst(), true)")
        except (OSError, RuntimeError):
            pass


def test_effects(port):
    done = 0
    for t in cdp.pages(port):
        try:
            cdp.evaluate(t["webSocketDebuggerUrl"], _JS_TEST)
            done += 1
        except (OSError, RuntimeError):
            pass
    return done


def remove_css(port):
    """Everything of Teams Remix goes away, except the switch in Teams (toggle_sync decides about that)."""
    for t in cdp.pages(port):
        try:
            cdp.evaluate(t["webSocketDebuggerUrl"], _JS_REMOVE)
        except (OSError, RuntimeError):
            pass


# ---------- the switch inside Teams ----------

TOGGLE_TEXTS = {"tip_on": "Teams Remix attivo: clic per spegnerlo", "tip_off": "Teams Remix spento: clic per accenderlo",
                "tip_wait_on": "Accendo Teams Remix...", "tip_wait_off": "Spengo Teams Remix..."}


def toggle_config(on):
    """What the switch in Teams shows: the app's choice, with its texts in both languages. It sits among Teams' own
    buttons, so it speaks Teams' language (like the nickname group in the search), whatever the app's language."""
    import i18n
    return {"on": bool(on), "label": "Teams Remix",
            "texts": {"it": dict(TOGGLE_TEXTS), "en": {k: i18n.EN[v] for k, v in TOGGLE_TEXTS.items()}}}


def _toggle_call(cfg):
    return ("(function(c){ return window.__ttToggleV === %d && window.__ttToggleSync ? window.__ttToggleSync(c) : '__missing'; })(%s)"
            % (TOGGLE_VERSION, json.dumps(cfg)))


def toggle_sync(port, cfg):
    """Show the switch in Teams' windows as `cfg` says (toggle_config(...); None: no switch) and collect a click on it.
    Returns True or False if it was clicked in Teams since the last time (switch on / off), else None.
    The page is only read through the local channel the app already uses: it never reaches the app by itself."""
    asked = None
    try:
        targets = cdp.pages(port)
    except (OSError, ValueError):  # Teams closing right now: nothing to show, nothing clicked
        return None
    for t in targets:
        if is_popup(t):  # no switch in a notification
            continue
        ws = t["webSocketDebuggerUrl"]
        try:
            r = cdp.evaluate(ws, _toggle_call(cfg))
            if r == "__missing":  # a new or reloaded window, or an older switch: put this one in
                if cfg is None:
                    continue
                r = cdp.evaluate(ws, TOGGLE_JS + "\n" + _toggle_call(cfg))
        except (OSError, RuntimeError):
            continue
        if isinstance(r, dict) and isinstance(r.get("asked"), bool):
            asked = r["asked"]
    return asked


# ---------- autostart ----------

def _launch_command():
    pyw = Path(sys.executable)
    if pyw.name.lower() == "python.exe":
        pyw = pyw.with_name("pythonw.exe")
    script = Path(__file__).with_name("teams_theme.pyw")
    return f'"{pyw}" "{script}" --startup'


def autostart_enabled():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, RUN_NAME)
            return True
    except OSError:
        return False


def set_autostart(on):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, _launch_command())
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass
