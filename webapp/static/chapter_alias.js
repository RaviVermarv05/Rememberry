/*
 * chapter_alias.js — give any chapter your own display name.
 *
 * Right-click a chapter (or long-press it on a tablet / phone) in the chapter pickers of
 * Englisch→Deutsch, Deutsch→Englisch, Wörter durchsehen and Hörvokabeln, type a name and save.
 * An empty name (or "Standard") brings back the default ("Kapitel 1", "B2.1 · Kapitel 1" ...).
 *
 * Nothing in app.js, any other mode file or any route is edited. Like timer.js this file only
 * adds itself on top, in three small ways:
 *   1. it wraps render(): after every draw it swaps the label of the chapter chips for the alias
 *   2. it wraps chLabel(): the chapter names shown in headings / search hits use the alias too
 *   3. it adds a right-click / long-press handler plus one small rename dialog
 *
 * The alias is display-only. Chapter ids, quiz / review / audio / search requests and the data
 * editor are untouched; the names live in Data/chapter_aliases.json (webapp/alias_routes.py).
 */
(function(){
  if(typeof render !== 'function' || typeof chLabel !== 'function' || typeof post !== 'function'){
    console.warn('[chapter_alias] not started: app.js must be loaded first.');
    return;
  }

  let aliases = {};          // {"3": "Reisen & Verkehr"}
  let maxLen = 40;
  let dialog = null;         // the open rename dialog, if any

  const CHIP_ACTIONS = ['toggle-chapter', 'pick-review-chapter', 'pick-audio-chapter'];
  const SAFE_REDRAW = ['loading', 'home', 'chapters', 'review-chapter', 'review-range', 'review-list',
                       'audio-chapter', 'audio-range'];

  const esc = s => String(s).replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const aliasOf = n => (Object.prototype.hasOwnProperty.call(aliases, String(n)) ? aliases[String(n)] : '');
  const infoOf = n => (state.chapters || []).find(c => c.number === n);

  /* ---------------- 1 + 2: show the alias ---------------- */
  const _origChLabel = chLabel;
  chLabel = function(n){
    const a = aliasOf(n);
    if(!a) return _origChLabel(n);
    const c = infoOf(n);
    const multi = new Set((state.chapters || []).map(x => x.level)).size > 1;
    // chLabel's result goes straight into innerHTML templates, so the alias is escaped here
    return multi && c ? `${esc(c.level)} · ${esc(a)}` : esc(a);
  };

  function chipText(el, text){
    for(const node of el.childNodes){                      // the label is the first text node;
      if(node.nodeType === 3 && node.nodeValue.trim()){    // the "(count)" span is left alone
        node.nodeValue = ` ${text} `;
        return;
      }
    }
  }

  function decorate(){
    document.querySelectorAll('[data-action]').forEach(el => {
      if(CHIP_ACTIONS.indexOf(el.dataset.action) === -1 || !el.dataset.n) return;
      el.classList.add('ch-alias-chip');
      el.title = 'Rechtsklick (oder lange drücken): Kapitel umbenennen';
      const a = aliasOf(parseInt(el.dataset.n, 10));
      if(a) chipText(el, a);
    });
  }

  const _origRender = render;
  render = function(){
    _origRender.apply(this, arguments);
    try{ decorate(); }catch(e){ console.warn('[chapter_alias]', e); }
  };

  /* ---------------- rename dialog ---------------- */
  function closeDialog(){
    if(dialog){ dialog.remove(); dialog = null; }
  }

  function openDialog(n){
    const info = infoOf(n);
    if(!info || dialog) return;
    const current = aliasOf(n);
    const root = document.createElement('div');
    root.className = 'cha-overlay';
    root.innerHTML = `
      <div class="cha-card" role="dialog" aria-modal="true" aria-label="Kapitel umbenennen">
        <h3>Kapitel umbenennen</h3>
        <p class="cha-def">Standardname: <strong>${esc(info.label)}</strong></p>
        <input class="cha-input" type="text" maxlength="${maxLen}" autocomplete="off" spellcheck="false"
               placeholder="${esc(info.short)}" aria-label="Eigener Name">
        <div class="cha-err" role="alert"></div>
        <div class="cha-row">
          <button type="button" class="cha-btn" data-cha="reset">Standard</button>
          <span class="cha-gap"></span>
          <button type="button" class="cha-btn" data-cha="cancel">Abbrechen</button>
          <button type="button" class="cha-btn cha-primary" data-cha="save">Speichern</button>
        </div>
      </div>`;
    const input = root.querySelector('.cha-input');
    const err = root.querySelector('.cha-err');
    input.value = current;
    let busy = false;

    async function commit(value){
      if(busy) return;
      busy = true; err.textContent = '';
      try{
        const r = await post('/api/chapter-aliases', { id: n, alias: value });
        aliases = r.aliases || {};
        closeDialog();
        const y = window.scrollY;
        render();
        window.scrollTo(0, y);
      }catch(e){
        err.textContent = e.message || 'Konnte nicht gespeichert werden.';
        busy = false;
      }
    }

    root.addEventListener('click', e => {
      if(e.target === root) return closeDialog();
      const b = e.target.closest('[data-cha]');
      if(!b) return;
      const what = b.dataset.cha;
      if(what === 'cancel') closeDialog();
      else if(what === 'reset') commit('');
      else if(what === 'save') commit(input.value);
    });
    root.addEventListener('keydown', e => {
      if(e.key === 'Escape'){ e.preventDefault(); closeDialog(); }
      else if(e.key === 'Enter' && e.target === input){ e.preventDefault(); commit(input.value); }
    });
    document.body.appendChild(root);
    dialog = root;
    input.focus(); input.select();
  }

  /* ---------------- right-click / long-press ---------------- */
  function chipFrom(target){
    const el = target && target.closest ? target.closest('.ch-alias-chip') : null;
    return el && el.dataset.n ? parseInt(el.dataset.n, 10) : null;
  }

  document.addEventListener('contextmenu', e => {
    const n = chipFrom(e.target);
    if(n === null) return;
    e.preventDefault();
    openDialog(n);
  });

  let pressTimer = null, pressStart = null, swallowClickUntil = 0;
  document.addEventListener('touchstart', e => {
    clearTimeout(pressTimer);
    const n = chipFrom(e.target);
    if(n === null || e.touches.length !== 1) return;
    pressStart = { x: e.touches[0].clientX, y: e.touches[0].clientY };
    pressTimer = setTimeout(() => {
      swallowClickUntil = Date.now() + 800;    // the finger lift after a long press must not toggle the chapter
      openDialog(n);
    }, 600);
  }, { passive: true });
  document.addEventListener('touchmove', e => {
    if(!pressTimer || !pressStart) return;
    const t = e.touches[0];
    if(Math.abs(t.clientX - pressStart.x) > 10 || Math.abs(t.clientY - pressStart.y) > 10) clearTimeout(pressTimer);
  }, { passive: true });
  ['touchend', 'touchcancel'].forEach(ev => document.addEventListener(ev, () => clearTimeout(pressTimer), { passive: true }));
  document.addEventListener('click', e => {
    if(Date.now() < swallowClickUntil && chipFrom(e.target) !== null){
      e.stopImmediatePropagation(); e.preventDefault();
    }
  }, true);

  /* ---------------- look ---------------- */
  const style = document.createElement('style');
  style.textContent = `
    .ch-alias-chip{-webkit-touch-callout:none;-webkit-user-select:none;user-select:none;max-width:100%;overflow-wrap:anywhere;}
    .cha-overlay{position:fixed;inset:0;z-index:9000;background:rgba(18,40,63,.45);display:flex;align-items:center;justify-content:center;padding:18px;}
    .cha-card{width:100%;max-width:380px;background:var(--card,#fffdf7);color:var(--ink,#1c2b39);border-radius:var(--radius,10px);box-shadow:var(--shadow,0 10px 24px rgba(0,0,0,.3));padding:18px 18px 14px;border:1px solid var(--paper-line,#e3d9bf);}
    .cha-card h3{font-size:18px;margin:0 0 6px;}
    .cha-def{margin:0 0 12px;font-size:13px;color:var(--ink-soft,#4a5a68);}
    .cha-input{width:100%;font:inherit;font-size:16px;padding:9px 11px;border-radius:8px;border:1px solid var(--paper-line,#e3d9bf);background:var(--paper,#f5efe0);color:var(--ink,#1c2b39);}
    .cha-input:focus{outline:2px solid var(--navy,#1b3a5c);outline-offset:1px;}
    .cha-err{min-height:18px;margin:6px 0 2px;font-size:12.5px;color:var(--berry,#a23b3b);}
    .cha-row{display:flex;align-items:center;gap:8px;margin-top:4px;}
    .cha-gap{flex:1;}
    .cha-btn{font-size:14px;padding:8px 13px;border-radius:8px;border:1px solid var(--paper-line,#e3d9bf);background:var(--card,#fffdf7);color:var(--ink,#1c2b39);}
    .cha-primary{background:var(--navy,#1b3a5c);border-color:var(--navy,#1b3a5c);color:#fff;}
  `;
  document.head.appendChild(style);

  /* ---------------- load the saved names ---------------- */
  get('/api/chapter-aliases').then(r => {
    aliases = (r && r.aliases) || {};
    if(r && r.max_length) maxLen = r.max_length;
    if(Object.keys(aliases).length && SAFE_REDRAW.indexOf(state.view) !== -1) render();
  }).catch(() => { /* no aliases available: the default names simply stay */ });
})();