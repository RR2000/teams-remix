// Runs the switches of teams.TOGGLE_JS on a tiny fake page (node only, no browser): the test passes the script path
// and the texts as argv[2] and argv[3], and reads one JSON line of results. Only what the switches use is faked.
'use strict';
const fs = require('fs');

class El {
  constructor(tag) { this.tagName = tag; this.children = []; this.attrs = {}; this.parent = null; this.id = ''; this.className = '';
    this.listeners = {}; this.style = { setProperty() {} }; this.textContent = ''; this.rect = null; }
  get parentElement() { return this.parent; }
  get isConnected() { let e = this; while (e.parent) e = e.parent; return e === root; }
  get previousElementSibling() { if (!this.parent) return null; const i = this.parent.children.indexOf(this); return i > 0 ? this.parent.children[i - 1] : null; }
  get nextElementSibling() { if (!this.parent) return null; return this.parent.children[this.parent.children.indexOf(this) + 1] || null; }
  get nextSibling() { return this.nextElementSibling; }
  get firstElementChild() { return this.children[0] || null; }
  get offsetWidth() { return 32; }
  appendChild(c) { c.remove(); c.parent = this; this.children.push(c); return c; }
  insertBefore(c, ref) { c.remove(); c.parent = this; const i = ref ? this.children.indexOf(ref) : -1;
    if (i < 0) this.children.push(c); else this.children.splice(i, 0, c); return c; }
  remove() { if (this.parent) { this.parent.children.splice(this.parent.children.indexOf(this), 1); this.parent = null; } }
  replaceChildren(...k) { this.children.slice().forEach((c) => c.remove()); k.forEach((c) => this.appendChild(c)); }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  removeAttribute(k) { delete this.attrs[k]; }
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
  fire(t) { (this.listeners[t] || []).forEach((f) => f({ stopPropagation() {}, key: '' })); }
  matches() { return false; }
  getBoundingClientRect() { return this.rect || { left: 0, right: 32, top: 0, bottom: 30, width: 32, height: 30 }; }
  all() { return this.children.reduce((a, c) => a.concat([c], c.all()), []); }
  querySelector(sel) { return this.all().filter((e) => match(e, sel))[0] || null; }
}
function match(e, sel) {
  if (sel.indexOf(',') >= 0) return sel.split(',').some((s) => match(e, s.trim()));
  if (sel[0] === '#') return e.id === sel.slice(1);
  if (sel[0] === '.') return e.className.split(' ').indexOf(sel.slice(1)) >= 0;
  const m = /^\[([\w-]+)="([^"]*)"\]$/.exec(sel); return !!m && e.getAttribute(m[1]) === m[2];
}
const root = new El('html'), body = root.appendChild(new El('body'));
global.document = { body, documentElement: { lang: 'en-us' }, createElement: (t) => new El(t), createElementNS: (ns, t) => new El(t),
  querySelector: (s) => root.querySelector(s), querySelectorAll: (s) => root.all().filter((e) => match(e, s)) };
global.window = global; global.innerWidth = 1200;
Object.defineProperty(global, 'navigator', { value: { language: 'it-IT' }, configurable: true });  // newer node has its own
global.getComputedStyle = () => ({ getPropertyValue: () => '' });
global.MutationObserver = class { observe() {} disconnect() {} };

// Teams' title bar as measured: [cell 0-68 [Collapse app bar 18-50]] ... [back/forward from 308]
const bar = body.appendChild(new El('div')), cell = bar.appendChild(new El('div')), nav = bar.appendChild(new El('div'));
cell.rect = { left: 0, right: 68, top: 0, bottom: 30, width: 68, height: 30 };
nav.rect = { left: 308, right: 372, top: 0, bottom: 30, width: 64, height: 30 };
const hb = cell.appendChild(new El('button')); hb.setAttribute('data-tid', 'hamburger-button'); hb.className = 'fui-Button teams-look';
hb.rect = { left: 18, right: 50, top: 8, bottom: 38, width: 32, height: 30 };
const icon = hb.appendChild(new El('span')); icon.className = 'fui-Button__icon';

eval(fs.readFileSync(process.argv[2], 'utf8'));
const texts = JSON.parse(process.argv[3]);
const KEYS = ['all', 'themes', 'pets', 'nicknames'];
const cfg = (on, sec) => ({ on, sections: Object.assign({ themes: true, pets: true, nicknames: true }, sec || {}), texts });
const boxes = () => document.querySelectorAll('#tt-remix-toggle-box');
const btn = (k) => document.querySelector(k === 'all' ? '#tt-remix-toggle' : '#tt-remix-toggle-' + k);
const visible = () => KEYS.filter((k) => btn(k) && btn(k).style.display !== 'none');
const out = {};
let r = window.__ttToggleSync(cfg(true, { pets: false }));
const box = boxes()[0];
out.placed = r.placed; out.boxes = boxes().length; out.buttons = box.children.length;
out.nextToTeams = box.previousElementSibling === cell && box.nextSibling === nav; out.noRoomTaken = box.style.margin;
out.sameLook = KEYS.every((k) => btn(k).className === hb.className && btn(k).style.margin === '0'); out.visible = visible();
out.pressed = KEYS.map((k) => btn(k).getAttribute('aria-pressed')); out.labels = KEYS.map((k) => btn(k).getAttribute('aria-label'));
window.__ttToggleSync(cfg(true, { pets: false }));
const stray = new El('div'); stray.id = 'tt-remix-toggle-box'; bar.appendChild(stray);  // a copy left by an older script
window.__ttToggleSync(cfg(true, { pets: false }));
out.boxesAfterRepeats = boxes().length;
box.remove(); window.__ttToggleSync(cfg(true, { pets: false }));                      // Teams redrew its title bar
out.boxesAfterRedraw = boxes().length;
btn('themes').fire('click');
out.busyAfterClick = btn('themes').getAttribute('aria-busy'); out.iconAfterClick = btn('themes').firstElementChild.getAttribute('data-icon');
out.lockedOthers = btn('pets').getAttribute('aria-disabled');
btn('pets').fire('click');                                                             // another click while waiting
r = window.__ttToggleSync(cfg(true, { pets: false })); out.asked = r.asked;            // the app collects the click
btn('all').fire('click');
r = window.__ttToggleSync(cfg(true, { pets: false })); out.askedWhileBusy = r.asked;
window.__ttToggleSync(cfg(true, { pets: false, themes: false }));                      // the app has done it
out.busyAfterApp = btn('themes').getAttribute('aria-busy'); out.pressedAfterApp = btn('themes').getAttribute('aria-pressed');
out.iconAfterApp = btn('themes').firstElementChild.getAttribute('data-icon');
window.__ttToggleSync(cfg(false));
out.visibleWithAllOff = visible();
btn('all').fire('pointerenter');
setTimeout(() => {
  const tip = document.querySelector('#tt-remix-toggle-tip'); out.tipEn = tip && tip.textContent;
  btn('all').fire('pointerleave'); document.documentElement.lang = 'it-it'; btn('all').fire('pointerenter');
  setTimeout(() => {
    const t2 = document.querySelector('#tt-remix-toggle-tip'); out.tipIt = t2 && t2.textContent; btn('all').fire('pointerleave');
    nav.rect = { left: 150, right: 214, top: 0, bottom: 30, width: 64, height: 30 };  // a narrow window
    window.__ttToggleSync(cfg(true)); out.visibleNoRoom = visible();
    window.__ttToggleSync(null); out.countHidden = boxes().length;                     // in a call: no switches
    hb.remove(); r = window.__ttToggleSync(cfg(true));                                  // a layout without that button
    out.placedWithout = r.placed; out.countWithout = boxes().length;
    window.__ttToggleOff();
    console.log(JSON.stringify(out));
  }, 300);
}, 300);
