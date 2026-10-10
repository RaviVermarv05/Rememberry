/*
 * apikeys.js — adds an "API-Schlüssel" card to the Settings page. Loaded after app.js and
 * uses its globals (state, render, get, post, viewSettings, go). app.js itself is not edited:
 * this file wraps viewSettings() to insert the card above the Abbrechen/Speichern buttons.
 *
 * Rendering only. Whether a key is set, validation, and writing the .env file all happen in
 * /api/settings/keys (apikeys_routes.py). The browser never receives a saved key back, only
 * "set / not set" and the last 4 characters.
 *
 * Saving a key is its own action (button inside the card, applies immediately). It does not
 * depend on the page's "Speichern" button for the other settings.
 */
(function(){
  if(typeof viewSettings !== 'function' || typeof render !== 'function') return;

  const esc = (s) => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  /* styles live here so index.html only needs the one <script> line */
  const style = document.createElement('style');
  style.textContent = `
  .ak-note{font-size:12px;color:var(--ink-soft);margin:0 0 4px;}
  .ak-row{padding:12px 0;border-top:1px solid var(--paper-line);}
  .ak-note + .ak-row{border-top:none;}
  .ak-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;}
  .ak-used{font-size:12px;color:var(--ink-soft);margin-top:2px;}
  .ak-status{font-size:12.5px;font-weight:600;white-space:nowrap;}
  .ak-status.ok{color:var(--green);}
  .ak-status.missing{color:var(--berry);}
  .ak-edit{margin-top:10px;}
  .ak-input{width:100%;padding:12px 14px;font-size:15px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;border:1.5px solid var(--paper-line);border-radius:8px;background:var(--paper);color:var(--ink);}
  .ak-input:focus{outline:none;border-color:var(--navy);}
  .ak-btns{display:flex;gap:10px;margin-top:10px;}
  .ak-btns .primarybtn{flex:2;width:auto;padding:11px 18px;}
  .ak-btns .ghostbtn{flex:1;}
  .ak-change{margin-top:10px;}
  .ak-msg{margin-top:8px;font-size:12.5px;}
  .ak-msg.ok{color:var(--green);}
  .ak-msg.err{color:var(--berry);}
  .ak-help{display:inline-block;margin-top:8px;font-size:12px;color:var(--navy);}
  `;
  document.head.appendChild(style);

  let status = null;        // null = not loaded yet, otherwise the list from GET /api/settings/keys
  let loading = false;
  let loadError = '';
  const draft = {};         // text typed but not saved yet (survives re-renders, e.g. toggling a switch)
  const editing = {};       // key name -> true while "Schlüssel ändern" is open
  const msg = {};           // key name -> {kind: 'ok'|'err', text}
  const saving = {};

  function clearAll(){
    status = null; loading = false; loadError = '';
    [draft, editing, msg, saving].forEach(o => Object.keys(o).forEach(k => delete o[k]));
  }

  async function load(){
    if(loading) return;
    loading = true; loadError = '';
    try{
      status = (await get('/api/settings/keys')).keys;
    }catch(e){
      loadError = e.message; status = [];
    }
    loading = false;
    if(state.view === 'settings') render();
  }

  function rowHtml(k){
    const open = !k.set || editing[k.name];
    const busy = !!saving[k.name];
    const m = msg[k.name];
    const badge = k.set
      ? `<span class="ak-status ok">✅ gesetzt · ${esc(k.masked)}</span>`
      : `<span class="ak-status missing">⚠️ nicht gesetzt</span>`;
    const controls = open ? `
      <div class="ak-edit">
        <input type="password" class="ak-input" data-keyname="${k.name}" value="${esc(draft[k.name] || '')}"
               placeholder="${esc(k.placeholder)}" autocomplete="off" autocapitalize="off" spellcheck="false"
               aria-label="${esc(k.label)} API-Schlüssel" ${busy ? 'disabled' : ''}>
        <div class="ak-btns">
          <button class="primarybtn" data-apikey-action="save" data-keyname="${k.name}" ${busy ? 'disabled' : ''}>${busy ? 'Speichere …' : 'Schlüssel speichern'}</button>
          ${k.set ? `<button class="ghostbtn" data-apikey-action="cancel" data-keyname="${k.name}" ${busy ? 'disabled' : ''}>Abbrechen</button>` : ''}
        </div>
      </div>` : `<button class="ghostbtn ak-change" data-apikey-action="edit" data-keyname="${k.name}">Schlüssel ändern</button>`;
    return `
    <div class="ak-row">
      <div class="ak-head">
        <div><div class="setlabel">${esc(k.label)}</div><div class="ak-used">${esc(k.used_for)}</div></div>
        ${badge}
      </div>
      ${controls}
      ${m ? `<div class="ak-msg ${m.kind}">${esc(m.text)}</div>` : ''}
      ${!k.set ? `<a class="ak-help" href="${esc(k.help_url)}" target="_blank" rel="noopener noreferrer">Schlüssel erstellen ↗</a>` : ''}
    </div>`;
  }

  function cardHtml(){
    let inner;
    if(status === null) inner = `<p class="ak-note">Lade …</p>`;
    else if(loadError) inner = `<p class="ak-note" style="color:var(--berry)">Konnte den Status nicht laden: ${esc(loadError)}</p>`;
    else inner = `<p class="ak-note">Wird in der Datei .env gespeichert und gilt sofort. Ein gespeicherter Schlüssel wird nie wieder angezeigt.</p>` + status.map(rowHtml).join('');
    return `<div class="fieldcard apikeys"><h3>API-Schlüssel</h3>${inner}</div>`;
  }

  /* put the card into the existing Settings page, just above the Abbrechen / Speichern row */
  const originalViewSettings = viewSettings;
  viewSettings = function(){
    const html = originalViewSettings.apply(this, arguments);
    if(status === null && !loading) load();
    const i = html.lastIndexOf('<div class="btnrow">');
    const card = cardHtml();
    return i === -1 ? html + card : html.slice(0, i) + card + html.slice(i);
  };

  /* every time the Settings page is opened, re-check the status and forget old messages */
  if(typeof go === 'function'){
    const originalGo = go;
    go = function(view){
      if(view === 'settings') clearAll();
      return originalGo.apply(this, arguments);
    };
  }

  async function save(name){
    if(saving[name]) return;
    const input = document.querySelector(`.ak-input[data-keyname="${name}"]`);
    const value = (input ? input.value : (draft[name] || '')).trim();
    draft[name] = value;
    if(!value){
      msg[name] = { kind: 'err', text: 'Bitte einen Schlüssel eingeben.' };
      render();
      return;
    }
    saving[name] = true; delete msg[name];
    render();
    try{
      const r = await post('/api/settings/keys', { name, value });
      status = r.keys;
      delete draft[name];          // don't keep the secret in memory once it's saved
      editing[name] = false;
      msg[name] = r.persisted
        ? { kind: 'ok', text: 'Gespeichert — gilt sofort.' }
        : { kind: 'ok', text: 'Gilt bis zum Neustart (die .env-Datei konnte nicht geschrieben werden).' };
    }catch(e){
      msg[name] = { kind: 'err', text: e.message };
    }
    saving[name] = false;
    if(state.view === 'settings') render();
  }

  document.addEventListener('input', (e) => {
    const t = e.target;
    if(!t || !t.classList || !t.classList.contains('ak-input')) return;
    draft[t.dataset.keyname] = t.value;
    if(msg[t.dataset.keyname]){            // typing again -> drop the old message without a re-render
      delete msg[t.dataset.keyname];
      const el = t.closest('.ak-row') && t.closest('.ak-row').querySelector('.ak-msg');
      if(el) el.remove();
    }
  });

  document.addEventListener('keydown', (e) => {
    const t = e.target;
    if(e.key === 'Enter' && t && t.classList && t.classList.contains('ak-input')){
      e.preventDefault();
      save(t.dataset.keyname);
    }
  });

  document.addEventListener('click', (e) => {
    const btn = e.target && e.target.closest ? e.target.closest('[data-apikey-action]') : null;
    if(!btn) return;
    const name = btn.dataset.keyname, action = btn.dataset.apikeyAction;
    if(action === 'save') save(name);
    else if(action === 'edit'){ editing[name] = true; delete msg[name]; render();
      const i = document.querySelector(`.ak-input[data-keyname="${name}"]`); if(i) i.focus(); }
    else if(action === 'cancel'){ editing[name] = false; delete draft[name]; delete msg[name]; render(); }
  });
})();