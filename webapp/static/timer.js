/*
 * timer.js — a stopwatch for the quiz modes: Englisch→Deutsch, Deutsch→Englisch, Kontext-Modus
 * and Verben (üben). Loaded after app.js / context_mode.js / verbs_mode.js and uses their globals
 * (state, render, viewSettings, saveSettings, post). Rendering only, like the other mode files.
 *
 * Nothing in app.js, context_mode.js, verbs_mode.js or any quiz route is edited. This file adds
 * itself in three small ways:
 *   1. it wraps render(): after every draw it looks at state.view to start / stop the stopwatch,
 *      shows a small ⏱ pill while a quiz is running, and adds "Zeit" to the results card
 *   2. it wraps viewSettings() to add one "Timer" switch (same switch markup / same
 *      "toggle-setting" action the other switches use) and saveSettings() to also save it
 *   3. nothing else: answers, attempts, scoring and results are not touched
 *
 * The stopwatch starts when the first question of a round appears and stops when the results
 * screen appears (the time shown on it is the final time). Leaving a round without finishing
 * (e.g. Beenden) just discards it. The switch lives in Einstellungen → Timer
 * (Settings.timer_enabled, saved in settings.json like the other settings).
 */
(function(){
  if(typeof render !== 'function' || typeof viewSettings !== 'function' || typeof saveSettings !== 'function'){
    console.warn('[timer] not started: app.js must be loaded first.');
    return;
  }

  /* ---------------- stopwatch state ---------------- */
  let t0 = null;      // Date.now() when the round started
  let finalMs = null; // set when the results screen appears
  let sid = null;     // state.sessionId of the running round

  const QUIZ_VIEWS = ['quiz', 'vb-practice', 'history'];   // history = "Bisherige Wörter" inside a quiz
  const RESULT_VIEWS = ['results', 'vb-results'];

  const enabled = () => !!(state.settings && state.settings.timer);

  function sync(){
    const v = state.view;
    if(QUIZ_VIEWS.indexOf(v) !== -1){
      if(t0 === null || finalMs !== null || (v !== 'history' && state.sessionId !== sid)){
        t0 = Date.now(); finalMs = null; sid = state.sessionId;   // a new round
      }
    }else if(RESULT_VIEWS.indexOf(v) !== -1){
      if(t0 !== null && finalMs === null) finalMs = Date.now() - t0;
    }else{
      t0 = null; finalMs = null; sid = null;                      // left the round / other screen
    }
  }

  function fmt(ms){
    const s = Math.max(0, Math.floor(ms / 1000));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    const p = (n) => String(n).padStart(2, '0');
    return h ? `${h}:${p(m)}:${p(sec)}` : `${p(m)}:${p(sec)}`;
  }

  /* ---------------- look ---------------- */
  const style = document.createElement('style');
  style.textContent = `
    #rb-timer{position:fixed;top:12px;right:14px;z-index:50;display:none;font-size:12.5px;font-weight:600;
      font-variant-numeric:tabular-nums;color:var(--ink-soft,#556);background:var(--card,#fff);
      border:1px solid var(--paper-line,#ddd);padding:4px 11px;border-radius:999px;box-shadow:0 1px 4px rgba(0,0,0,.08);}
    .rb-time{margin-top:10px;font-size:14px;font-weight:600;color:var(--navy,#1b2a49);font-variant-numeric:tabular-nums;}
  `;
  document.head.appendChild(style);

  function pill(){
    let el = document.getElementById('rb-timer');
    if(!el){ el = document.createElement('div'); el.id = 'rb-timer'; document.body.appendChild(el); }
    return el;
  }

  function decorate(){
    const el = pill();
    const running = enabled() && t0 !== null && finalMs === null && QUIZ_VIEWS.indexOf(state.view) !== -1;
    el.style.display = running ? 'block' : 'none';
    if(running) el.textContent = '⏱ ' + fmt(Date.now() - t0);

    if(enabled() && finalMs !== null && RESULT_VIEWS.indexOf(state.view) !== -1){
      const sub = document.querySelector('#app .resultcard .sub');
      if(sub && !document.querySelector('#app .rb-time')){
        const line = document.createElement('div');
        line.className = 'rb-time';
        line.textContent = '⏱ Zeit: ' + fmt(finalMs);
        sub.insertAdjacentElement('afterend', line);
      }
    }
  }

  setInterval(() => {
    const el = document.getElementById('rb-timer');
    if(el && el.style.display !== 'none' && t0 !== null && finalMs === null) el.textContent = '⏱ ' + fmt(Date.now() - t0);
  }, 250);

  /* ---------------- hook into the existing dashboard ---------------- */
  const _origRender = render;
  render = function(){
    sync();
    _origRender();
    decorate();
  };

  const _origViewSettings = viewSettings;
  viewSettings = function(){
    const html = _origViewSettings();
    const d = state.draft || {};
    const card = `
  <div class="fieldcard">
    <h3>Timer</h3>
    <div class="setrow">
      <div><div class="setlabel">Zeit stoppen</div><div class="setdesc">Eine Stoppuhr läuft während der Übung (Englisch→Deutsch, Deutsch→Englisch, Kontext, Verben); am Ende siehst du die Endzeit.</div></div>
      <button class="switch ${d.timer ? 'on' : ''}" data-action="toggle-setting" data-key="timer" role="switch" aria-checked="${!!d.timer}"><span></span></button>
    </div>
  </div>
  `;
    const i = html.lastIndexOf('<div class="btnrow">');
    return i === -1 ? html : html.slice(0, i) + card + html.slice(i);
  };

  const _origSaveSettings = saveSettings;
  saveSettings = async function(){
    const d = state.draft;
    try{
      if(d && typeof d.timer === 'boolean') await post('/api/settings', { timer: d.timer });
    }catch(e){ /* the normal save below still runs */ }
    return _origSaveSettings();
  };
})();