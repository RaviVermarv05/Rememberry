/*
 * data_editor.js — add / change / delete words and verbs, written straight into
 * Data/word_list.py and Data/verb_list.py (backend: webapp/data_routes.py).
 *
 * NOT a dashboard mode: there is no card on the start page. It opens from
 *   - Einstellungen -> "Daten" -> "Vokabeln bearbeiten"
 *   - a small "✏️ Bearbeiten" link at the top of "Wörter durchsehen" and "Verben durchsehen"
 *
 * Loaded after app.js / verbs_mode.js and uses their globals (state, go, render, post).
 * No existing file is edited except index.html (script + css tag) and app.py (blueprint).
 * Same approach as verbs_mode.js: wrap a few view functions, own view name ("data-editor"),
 * own click actions (data-action="de-…") which app.js ignores.
 *
 * Rendering only. Every rule (validation, duplicates, the actual file edit) lives in
 * data_routes.py; this file just shows what the server returns and sends what you typed.
 */
(function(){
  const esc = (s) => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function D(){
    if(!state.de){
      state.de = { tab: 'words', chapter: 1, entries: [], verbs: [], filter: '', form: null,
                   loading: false, error: '', from: 'home', auto: true, flash: null, formError: '' };
    }
    return state.de;
  }

  /* ---------------- network (retries while the dev server restarts after a save) ---------------- */
  async function deApi(path, body){
    for(let attempt = 0; attempt < 4; attempt++){
      try{
        const res = await fetch(path, body === undefined ? {} : {
          method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
        });
        let data = null;
        try{ data = await res.json(); }catch(e){}
        if(!res.ok){ const err = new Error((data && data.error) || ('Fehler ' + res.status)); err.fromServer = true; throw err; }
        return data;
      }catch(e){
        if(e.fromServer) throw e;
        await new Promise(r => setTimeout(r, 700));
      }
    }
    throw new Error('Server nicht erreichbar (startet er gerade neu?). Bitte gleich nochmal versuchen.');
  }

  function toast(text){
    let el = document.getElementById('de-toast');
    if(!el){ el = document.createElement('div'); el.id = 'de-toast'; el.className = 'de-toast'; document.body.appendChild(el); }
    el.textContent = text;
    el.classList.add('show');
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove('show'), 2600);
  }

  /* ---------------- loading ---------------- */
  async function deLoad(){
    const d = D();
    d.loading = true; d.error = '';
    if(state.view === 'data-editor') render();
    try{
      if(d.tab === 'words'){
        const r = await deApi('/api/data/words/' + d.chapter);
        d.entries = r.entries; d.auto = r.auto_reload;
      }else{
        const r = await deApi('/api/data/verbs');
        d.verbs = r.entries; d.auto = r.auto_reload;
      }
    }catch(e){ d.error = e.message; }
    d.loading = false;
    if(state.view === 'data-editor') render();
  }
  window.deLoad = deLoad;   // dev_reload.js re-opens the editor after a code reload

  async function deOpen(tab, chapter, from){
    const d = D();
    if(tab) d.tab = tab;
    if(chapter) d.chapter = chapter;
    d.from = from || 'home';
    d.form = null; d.filter = ''; d.formError = ''; d.flash = null;
    go('data-editor');
    await deLoad();
  }

  async function deBack(){
    const d = D();
    try{
      if(d.from === 'settings'){ go('settings', { draft: Object.assign({}, state.settings) }); return; }
      if(d.from === 'review-list' && state.reviewResult){
        const r0 = state.reviewResult;
        const r = await deApi('/api/review', { chapter: r0.chapter,
          start: r0.range ? r0.range.start : null, end: r0.range ? r0.range.end : null });
        go('review-list', { reviewResult: r }); return;
      }
      if(d.from === 'vb-review' && state.vb){
        const v = state.vb, custom = v.rangeMode === 'custom';
        const r = await deApi('/api/verbmode/review', { start: custom ? v.start : null, end: custom ? v.end : null });
        go('vb-review', { vbReview: r }); return;
      }
    }catch(e){ /* range no longer valid after a delete -> fall through to start page */ }
    go('home');
  }

  /* ---------------- views ---------------- */
  const termText = (arr) => arr.map(esc).join(' / ');

  function matches(text, q){ return text.toLowerCase().includes(q); }

  function currentList(){
    const d = D();
    const q = d.filter.trim().toLowerCase();
    if(d.tab === 'words'){
      return d.entries.filter(e => !q || matches(e.english.join(' ') + ' ' + e.german.join(' '), q));
    }
    return d.verbs.filter(e => !q || matches([e.verb, e.meaning, e.praesens, e.praeteritum, e.perfekt].join(' '), q));
  }

  function inputRow(field, i, value, placeholder, removable){
    return `<div class="de-vrow">
      <input type="text" autocomplete="off" spellcheck="false" data-de-field="${field}" data-i="${i}" value="${esc(value)}" placeholder="${esc(placeholder)}">
      ${removable ? `<button class="de-x" data-action="de-rm" data-field="${field}" data-i="${i}" title="Entfernen">✕</button>` : ''}
    </div>`;
  }

  function formHtml(){
    const d = D(), f = d.form;
    const title = f.mode === 'new' ? 'Neuer Eintrag' : `Eintrag ${f.no} ändern`;
    let fields;
    if(d.tab === 'words'){
      fields = `
        <div class="de-flabel">Englisch <span>(mehrere Varianten möglich)</span></div>
        ${f.english.map((v, i) => inputRow('english', i, v, 'z. B. toxic', f.english.length > 1)).join('')}
        <button class="de-link" data-action="de-addvar" data-field="english">+ englische Variante</button>
        <div class="de-flabel">Deutsch <span>(Artikel mitschreiben: der / die / das)</span></div>
        ${f.german.map((v, i) => inputRow('german', i, v, 'z. B. das Insekt', f.german.length > 1)).join('')}
        <button class="de-link" data-action="de-addvar" data-field="german">+ deutsche Variante</button>`;
    }else{
      const one = (key, label, ph) => `
        <div class="de-flabel">${label}</div>
        <div class="de-vrow"><input type="text" autocomplete="off" spellcheck="false" data-de-field="${key}" value="${esc(f.fields[key])}" placeholder="${esc(ph)}"></div>`;
      fields = one('verb', 'Verb (Infinitiv)', 'z. B. angeben')
             + one('meaning', 'Bedeutung', 'z. B. to state / specify')
             + one('praesens', 'Präsens (er/sie/es)', 'z. B. gibt an')
             + one('praeteritum', 'Präteritum', 'z. B. gab an')
             + one('perfekt', 'Perfekt', 'z. B. hat angegeben  /  ist gegangen');
    }
    return `
      <div class="fieldcard de-form" id="de-form">
        <h3>${title}${d.tab === 'words' ? ` <span class="de-sub">Kapitel ${d.chapter}</span>` : ''}</h3>
        ${fields}
        <div class="de-err" id="de-err">${esc(d.formError || '')}</div>
        <div class="btnrow">
          <button class="ghostbtn" data-action="de-cancel">Abbrechen</button>
          <button class="primarybtn" data-action="de-save">Speichern</button>
        </div>
      </div>`;
  }

  function rowHtml(e){
    const d = D();
    const editing = d.form && d.form.mode === 'edit' && d.form.no === e.no;
    if(editing) return formHtml();
    const main = d.tab === 'words'
      ? `<span class="de-en">${termText(e.english)}</span><span class="de-arrow">→</span><span class="de-de">${termText(e.german)}</span>`
      : `<span class="de-de">${esc(e.verb)}</span><span class="de-arrow">·</span><span class="de-en">${esc(e.meaning)}</span>
         <div class="de-forms">${esc(e.praesens)} · ${esc(e.praeteritum)} · ${esc(e.perfekt)}</div>`;
    return `
      <div class="de-row ${d.flash === e.no ? 'de-flash' : ''}" data-no="${e.no}">
        <span class="de-no">${e.no}.</span>
        <div class="de-main">${main}</div>
        <div class="de-actions">
          <button class="de-ibtn" data-action="de-edit" data-no="${e.no}" title="Ändern">✏️</button>
          <button class="de-ibtn del" data-action="de-del" data-no="${e.no}" title="Löschen">🗑</button>
        </div>
      </div>`;
  }

  function listHtml(){
    const d = D();
    if(d.loading) return '<div class="loading-note" style="padding:30px 0;">Lade …</div>';
    if(d.error) return `<div class="de-err" style="margin:14px 0;">${esc(d.error)}</div>`;
    const list = currentList();
    if(!list.length) return '<div class="de-empty">Keine Einträge gefunden.</div>';
    return list.map(rowHtml).join('');
  }

  function countText(){
    const d = D();
    const total = d.tab === 'words' ? d.entries.length : d.verbs.length;
    const shown = currentList().length;
    const what = d.tab === 'words' ? `Kapitel ${d.chapter} · ${total} Wortpaare` : `${total} Verben`;
    return d.filter.trim() ? `${what} · ${shown} Treffer` : what;
  }

  function viewDataEditor(){
    const d = D();
    const chapterChips = d.tab !== 'words' ? '' : `
      <div class="chiprow de-chapters">${Array.from({length: 12}, (_, i) => i + 1).map(n =>
        `<button class="chip ${d.chapter === n ? 'active' : ''}" data-action="de-chapter" data-n="${n}">${n}</button>`).join('')}</div>`;
    const file = d.tab === 'words' ? 'Data/word_list.py' : 'Data/verb_list.py';
    const newBtn = (d.form && d.form.mode === 'new') ? formHtml()
      : `<button class="primarybtn" data-action="de-new">＋ Neuer Eintrag</button>`;
    return `
    <div class="crumbrow"><button class="backlink" data-action="de-back">← Zurück</button></div>
    <p class="tag" style="margin-top:-6px;">✏️ Vokabeln bearbeiten</p>
    <div class="de-tabs">
      <button class="chip ${d.tab === 'words' ? 'active' : ''}" data-action="de-tab" data-tab="words">Wörter</button>
      <button class="chip ${d.tab === 'verbs' ? 'active' : ''}" data-action="de-tab" data-tab="verbs">Verben</button>
    </div>
    ${chapterChips}
    <input type="text" class="de-filter" id="de-filter" placeholder="Suchen …" value="${esc(d.filter)}" autocomplete="off">
    <div class="de-count" id="de-count">${esc(countText())}</div>
    <div class="de-new">${d.loading || d.error ? '' : newBtn}</div>
    <div class="de-list" id="de-list">${listHtml()}</div>
    <p class="de-note">Änderungen werden direkt in <code>${file}</code> gespeichert (Sicherung in <code>Data/backups/</code>).
      ${d.auto ? 'Die App lädt die Daten danach automatisch neu.' : 'Starte die App neu, damit Quiz und Suche die Änderung sehen.'}
      Neue Einträge kommen ans Ende${d.tab === 'words' ? ' des Kapitels' : ' der Liste'}; nach dem Löschen ändern sich die Nummern.</p>`;
  }

  /* ---------------- hook into the existing app (no existing file edited) ---------------- */
  const _origBody = body;
  body = function(){
    return state.view === 'data-editor' ? viewDataEditor() : _origBody();
  };

  // Einstellungen: one "Daten" block above the Abbrechen/Speichern buttons
  const _origSettings = viewSettings;
  viewSettings = function(){
    const html = _origSettings();
    const card = `
  <div class="fieldcard">
    <h3>Daten</h3>
    <div class="setrow">
      <div><div class="setlabel">Vokabeln bearbeiten</div><div class="setdesc">Wörter und Verben hinzufügen, ändern oder löschen — direkt in word_list.py und verb_list.py.</div></div>
      <button class="ghostbtn" data-action="de-open" data-tab="words" data-from="settings">Öffnen</button>
    </div>
  </div>`;
    return html.includes('<div class="btnrow">') ? html.replace('<div class="btnrow">', card + '\n  <div class="btnrow">') : html + card;
  };

  // review screens: a small edit link next to the back button
  function withEditLink(html, tab, chapter, from){
    const open = '<div class="crumbrow">';
    const i = html.indexOf(open);
    if(i === -1) return html;
    const end = html.indexOf('</div>', i);
    const link = `<button class="backlink de-editlink" data-action="de-open" data-tab="${tab}"${chapter ? ` data-chapter="${chapter}"` : ''} data-from="${from}">✏️ Bearbeiten</button>`;
    return html.slice(0, i) + '<div class="crumbrow de-crumb">' + html.slice(i + open.length, end) + link + html.slice(end);
  }

  const _origReviewList = viewReviewList;
  viewReviewList = function(){
    const r = state.reviewResult;
    return withEditLink(_origReviewList(), 'words', r && r.chapter, 'review-list');
  };

  const _origVbReview = viewVbReview;
  viewVbReview = function(){
    return withEditLink(_origVbReview(), 'verbs', null, 'vb-review');
  };

  /* ---------------- events ---------------- */
  function findEntry(no){
    const d = D();
    return (d.tab === 'words' ? d.entries : d.verbs).find(e => e.no === no);
  }

  function focusForm(selector){
    setTimeout(() => {
      const f = document.getElementById('de-form');
      if(!f) return;
      const el = selector ? f.querySelector(selector) : f.querySelector('input');
      if(el){ el.focus(); const v = el.value; el.value = ''; el.value = v; }
      f.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }, 30);
  }

  function emptyForm(){
    const d = D();
    return d.tab === 'words'
      ? { mode: 'new', english: [''], german: [''] }
      : { mode: 'new', fields: { verb: '', meaning: '', praesens: '', praeteritum: '', perfekt: '' } };
  }

  function editForm(no){
    const d = D(), e = findEntry(no);
    if(!e) return null;
    return d.tab === 'words'
      ? { mode: 'edit', no, expected: e.english.slice(), english: e.english.slice(), german: e.german.slice() }
      : { mode: 'edit', no, expected: e.verb,
          fields: { verb: e.verb, meaning: e.meaning, praesens: e.praesens, praeteritum: e.praeteritum, perfekt: e.perfekt } };
  }

  async function deSave(){
    const d = D(), f = d.form;
    if(!f) return;
    const btn = document.querySelector('#de-form [data-action="de-save"]');
    if(btn) btn.disabled = true;
    try{
      let r;
      if(d.tab === 'words'){
        const body = { chapter: d.chapter, english: f.english, german: f.german };
        if(f.mode === 'edit'){ body.no = f.no; body.expected_english = f.expected; }
        r = await deApi('/api/data/words/' + (f.mode === 'new' ? 'add' : 'update'), body);
        d.entries = r.entries;
      }else{
        const body = Object.assign({}, f.fields);
        if(f.mode === 'edit'){ body.no = f.no; body.expected_verb = f.expected; }
        r = await deApi('/api/data/verbs/' + (f.mode === 'new' ? 'add' : 'update'), body);
        d.verbs = r.entries;
      }
      d.auto = r.auto_reload;
      d.form = null; d.formError = ''; d.flash = r.changed_no;
      render();
      toast('Gespeichert');
      const row = document.querySelector(`.de-row[data-no="${d.flash}"]`);
      if(row) row.scrollIntoView({ block: 'center', behavior: 'smooth' });
      d.flash = null;
    }catch(e){
      d.formError = e.message;
      const el = document.getElementById('de-err');
      if(el) el.textContent = e.message;
      if(btn) btn.disabled = false;
    }
  }

  async function deDelete(no){
    const d = D(), e = findEntry(no);
    if(!e) return;
    const label = d.tab === 'words' ? `${e.english.join(' / ')} → ${e.german.join(' / ')}` : `${e.verb} (${e.meaning})`;
    if(!confirm(`Eintrag ${no} wirklich löschen?\n\n${label}\n\nDie Nummern der folgenden Einträge ändern sich dadurch.`)) return;
    try{
      let r;
      if(d.tab === 'words'){
        r = await deApi('/api/data/words/delete', { chapter: d.chapter, no, expected_english: e.english });
        d.entries = r.entries;
      }else{
        r = await deApi('/api/data/verbs/delete', { no, expected_verb: e.verb });
        d.verbs = r.entries;
      }
      d.auto = r.auto_reload;
      if(d.form && d.form.mode === 'edit') d.form = null;   // numbers shifted
      render();
      toast('Gelöscht');
    }catch(err){
      alert(err.message);
      deLoad();     // show what is really in the file
    }
  }

  document.addEventListener('click', (ev) => {
    const el = ev.target.closest('[data-action^="de-"]');
    if(!el) return;
    const a = el.dataset.action, d = D();
    if(a === 'de-open') deOpen(el.dataset.tab, el.dataset.chapter ? parseInt(el.dataset.chapter, 10) : null, el.dataset.from);
    else if(a === 'de-back') deBack();
    else if(a === 'de-tab'){ d.tab = el.dataset.tab; d.form = null; d.filter = ''; d.formError = ''; deLoad(); }
    else if(a === 'de-chapter'){ d.chapter = parseInt(el.dataset.n, 10); d.form = null; d.filter = ''; d.formError = ''; deLoad(); }
    else if(a === 'de-new'){ d.form = emptyForm(); d.formError = ''; render(); focusForm(); }
    else if(a === 'de-edit'){ const f = editForm(parseInt(el.dataset.no, 10)); if(f){ d.form = f; d.formError = ''; render(); focusForm(); } }
    else if(a === 'de-cancel'){ d.form = null; d.formError = ''; render(); }
    else if(a === 'de-addvar'){
      d.form[el.dataset.field].push(''); render();
      const n = d.form[el.dataset.field].length - 1;
      focusForm(`[data-de-field="${el.dataset.field}"][data-i="${n}"]`);
    }
    else if(a === 'de-rm'){ d.form[el.dataset.field].splice(parseInt(el.dataset.i, 10), 1); render(); }
    else if(a === 'de-save') deSave();
    else if(a === 'de-del') deDelete(parseInt(el.dataset.no, 10));
  });

  document.addEventListener('input', (ev) => {
    const t = ev.target;
    if(!t || state.view !== 'data-editor') return;
    const d = D();
    if(t.id === 'de-filter'){
      d.filter = t.value;
      document.getElementById('de-list').innerHTML = listHtml();
      document.getElementById('de-count').textContent = countText();
      return;
    }
    if(t.dataset && t.dataset.deField && d.form){
      if(d.tab === 'words') d.form[t.dataset.deField][parseInt(t.dataset.i, 10)] = t.value;
      else d.form.fields[t.dataset.deField] = t.value;
      if(d.formError){ d.formError = ''; const el = document.getElementById('de-err'); if(el) el.textContent = ''; }
    }
  });

  document.addEventListener('keydown', (ev) => {
    if(state.view !== 'data-editor') return;
    const inForm = ev.target && ev.target.closest && ev.target.closest('#de-form');
    if(!inForm) return;
    if(ev.key === 'Enter'){ ev.preventDefault(); deSave(); }
    else if(ev.key === 'Escape'){ const d = D(); d.form = null; d.formError = ''; render(); }
  });
})();