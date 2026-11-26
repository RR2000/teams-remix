// Runs the switch of teams.TOGGLE_JS on a tiny fake page (node only, no browser): the test passes the script path
// as argv[2] and reads one JSON line of results. Only what the switch uses is faked.
'use strict';
const fs = require('fs');

class El {
  constructor(tag) { this.tagName = tag; this.children = []; this.attrs = {}; this.parent = null; this.id = ''; this.className = '';
    this.listeners = {}; this.style = { setProperty() {} }; this.textContent = ''; }
  get parentElement() { return this.parent; }
  get isConnected() { let e = this; while (e.parent) e = e.parent; return e === root; }
  get previousElementSibling() { if (!this.parent) return null; const i = this.parent.children.indexOf(this); return i > 0 ? this.parent.children[i - 1] : null; }
  get nextSibling() { if (!this.parent) return null; return this.parent.children[this.parent.children.indexOf(this) + 1] || null; }
  get firstElementChild() { return this.children[0] || null; }
  get offsetWidth() { return this.attrs.hidden !== undefined ? 0 : 32; }
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
  getBoundingClientRect() { return { left: 0, right: 32, top: 0, bottom: 30, width: 32, height: 30 }; }
  all() { return this.children.reduce((a, c) => a.concat([c], c.all()), []); }
  querySelector(sel) { return this.all().filter((e) => match(e, sel))[0] || null; }
}
function match(e, sel) {
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

// Teams' title bar: [cell [Collapse app bar]] [back/forward]
const bar = body.appendChild(new El('div')), cell = bar.appendChild(new El('div')), nav = bar.appendChild(new El('div'));
const hb = cell.appendChild(new El('button')); hb.setAttribute('data-tid', 'hamburger-button'); hb.className = 'fui-Button teams-look';
const icon = hb.appendChild(new El('span')); icon.className = 'fui-Button__icon';

eval(fs.readFileSync(process.argv[2], 'utf8'));
const texts = { it: { tip_on: 'acceso', tip_off: 'spento', tip_wait_on: 'accendo', tip_wait_off: 'spengo' },
                en: { tip_on: 'on', tip_off: 'off', tip_wait_on: 'switching on', tip_wait_off: 'switching off' } };
const cfg = (on) => ({ on, label: 'Teams Remix', texts });
const ours = () => document.querySelectorAll('#tt-remix-toggle');
const out = {};
let r = window.__ttToggleSync(cfg(true));
const b = ours()[0];
out.placed = r.placed; out.count = ours().length; out.nextToTeams = b.previousElementSibling === cell && b.nextSibling === nav;
out.sameLook = b.className === hb.className; out.pressed = b.getAttribute('aria-pressed'); out.label = b.getAttribute('aria-label');
window.__ttToggleSync(cfg(true));
const stray = new El('button'); stray.id = 'tt-remix-toggle'; bar.appendChild(stray);  // a copy left by an older script
window.__ttToggleSync(cfg(true));
out.countAfterRepeats = ours().length;
b.remove(); window.__ttToggleSync(cfg(true));                                          // Teams redrew its title bar
out.countAfterRedraw = ours().length;
b.fire('click');
out.busyAfterClick = b.getAttribute('aria-busy'); out.iconAfterClick = b.firstElementChild.getAttribute('data-icon');
out.pressedAfterClick = b.getAttribute('aria-pressed');
b.fire('click');                                                                        // a second click while waiting
r = window.__ttToggleSync(cfg(true)); out.asked = r.asked;                              // the app collects the click
out.busyWhileAppWorks = b.getAttribute('aria-busy');
b.fire('click');
r = window.__ttToggleSync(cfg(true)); out.askedWhileBusy = r.asked;
r = window.__ttToggleSync(cfg(false));                                                  // the app has switched off
out.busyAfterApp = b.getAttribute('aria-busy'); out.pressedAfterApp = b.getAttribute('aria-pressed');
out.iconAfterApp = b.firstElementChild.getAttribute('data-icon');
b.fire('pointerenter');
setTimeout(() => {
  const tip = document.querySelector('#tt-remix-toggle-tip'); out.tipEn = tip && tip.textContent;
  b.fire('pointerleave'); document.documentElement.lang = 'it-it'; b.fire('pointerenter');
  setTimeout(() => {
    const t2 = document.querySelector('#tt-remix-toggle-tip'); out.tipIt = t2 && t2.textContent; b.fire('pointerleave');
    window.__ttToggleSync(null); out.countHidden = ours().length;                        // in a call: no switch
    hb.remove(); r = window.__ttToggleSync(cfg(true));                                    // a layout without that button
    out.placedWithout = r.placed; out.countWithout = ours().length;
    window.__ttToggleOff();
    console.log(JSON.stringify(out));
  }, 300);
}, 300);
