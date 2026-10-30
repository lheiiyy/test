// Shared helpers for the screens: a tiny CommonJS loader so the same src/ files run in the
// browser and in node, the mock api, the role switcher and small DOM helpers.
(function () {
  const FILES = ['schema', 'repository/transport', 'repository/base', 'repository/index',
    'services/access', 'services/audit', 'services/trips', 'api'];
  const registry = {};
  const base = (document.currentScript.src.replace(/\/web\/app\.js.*$/, '/'));

  window.require = function (p) {
    const key = p.replace(/^(\.\.?\/)+/, '').replace(/\.js$/, '');
    const hit = registry[key] || registry[key + '/index'];
    if (!hit) throw new Error('module not loaded: ' + p);
    return hit;
  };
  function load(i, done) {
    if (i === FILES.length) return done();
    window.module = { exports: {} };
    const s = document.createElement('script');
    s.src = base + FILES[i] + '.js';
    s.onload = () => { registry[FILES[i]] = window.module.exports; load(i + 1, done); };
    s.onerror = () => { window.TM.fatal('Could not load ' + FILES[i] + '.js'); };
    document.head.appendChild(s);
  }

  const $ = (sel, root) => (root || document).querySelector(sel);
  function el(tag, attrs, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === 'class') n.className = v; else if (k.startsWith('on')) n.addEventListener(k.slice(2), v); else n.setAttribute(k, v);
    }
    for (const k of kids.flat()) n.append(k instanceof Node ? k : document.createTextNode(k == null ? '' : k));
    return n;
  }
  function message(text, kind) {
    const box = $('#messages');
    box.replaceChildren(text ? el('div', { class: 'msg ' + (kind || ''), role: kind === 'error' ? 'alert' : 'status' }, text) : '');
  }

  // Role switcher for the mock user; the choice is saved with the mock state.
  function roleSwitcher(api, onChange) {
    const select = el('select', { id: 'role-switch' }, api.users().map((u) =>
      el('option', { value: u.id }, `${u.role}: ${u.name}`)));
    select.value = api.currentUser().id;
    select.addEventListener('change', () => { api.setUser(select.value); api.save(); onChange(); });
    return el('div', { class: 'field small' }, el('label', { for: 'role-switch' }, 'Acting as (mock user)'), select);
  }

  window.TM = {
    $, el, message, roleSwitcher,
    fatal(text) { document.body.prepend(el('div', { class: 'msg error', role: 'alert' }, text)); },
    // Calls fn(api) once the modules are loaded; the mock user starts as the first seed user.
    // The mock state and acting user survive page changes in sessionStorage; reset() clears them.
    start(fn) {
      load(0, () => {
        let saved = null;
        try { saved = JSON.parse(sessionStorage.getItem('tm-mock')); } catch (e) { saved = null; }
        const api = window.require('api').createApi('mock', {
          seed: saved ? saved.state : window.TM_SEED,
          userId: saved ? saved.userId : window.TM_SEED.users[0].id,
        });
        api.save = () => {
          try { sessionStorage.setItem('tm-mock', JSON.stringify({ state: api.exportState(), userId: api.currentUser().id })); } catch (e) { /* storage blocked: state lasts for this page only */ }
        };
        api.reset = () => { try { sessionStorage.removeItem('tm-mock'); } catch (e) { /* ignore */ } };
        fn(api);
      });
    },
  };
})();
