/*
 * ipad_mode.js — makes the typing quizzes work on an iPad / tablet (tablets only: on a phone or a
 * normal computer this file does nothing at all).
 *
 * The problem: after every answer the page redraws and the <input> you were typing in is replaced
 * by a new one. iOS only opens the keyboard from a real tap — a focus() that happens after the
 * server answered is ignored — so the keyboard went away after every word.
 *
 * The fix (nothing in app.js / context_mode.js / verbs_mode.js is edited):
 *   - One invisible "keeper" input is never removed from the page. Once the keyboard is open in a
 *     quiz it stays attached to the keeper, so redrawing the page cannot close it. What you type
 *     is mirrored live into the visible answer bar (it gets the blue "active" border), Return
 *     submits it (or presses "Weiter" when that is what is on screen), and the next card's bar
 *     simply shows the new text. The very first tap (on "Los geht's" or on the bar) opens the keyboard.
 *   - While the keeper has the keyboard, focus() calls from the app on buttons / answer bars are
 *     ignored, because on iOS they would close the keyboard (the app does them for desktop users).
 *   - Answer bars get autocapitalize / autocorrect off and a "Go" return key.
 *   - Safety net for the automatic "next word" (+ a guard so one card is never skipped twice).
 *   - Auto-advance: a correct answer in Verben üben and in Kontext moves on to the next question /
 *     verb / word by itself after a second. After a wrong (revealed) answer nothing moves on its
 *     own: you tap "Weiter" / "Nächstes Wort" when you are ready. (Englisch<->Deutsch already did this.)
 *
 * Debug: open the app with  ?ipaddebug=1  at the end of the address to see a small log at the
 * bottom of the screen.
 */
(function(){
  if(typeof render !== 'function' || typeof state === 'undefined'){
    console.warn('[ipad_mode] not started: app.js must be loaded first.');
    return;
  }
  /* tablets only: a touch screen, shorter side >= 600 px, and a finger-first device (iPad, Android tablet).
     Phones (shorter side < 600), computers and touch-screen laptops (mouse / trackpad first) keep the
     normal behaviour. iPadOS pretends to be a Mac in Safari, hence the platform check. */
  const touchPoints = navigator.maxTouchPoints || 0;
  const iPad = /iPad/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && touchPoints > 1);
  const coarse = !!(window.matchMedia && window.matchMedia('(pointer:coarse)').matches);
  const isTablet = touchPoints > 0 && Math.min(screen.width, screen.height) >= 600 && (iPad || coarse);
  const debugOn = /[?&]ipaddebug/.test(location.search);
  if(isTablet) document.documentElement.classList.add('is-tablet');   // the CSS files switch on this class
  if(!isTablet && !debugOn) return;                        // phone / laptop: nothing changes

  const IDS = ['ans', 'vbans'];                            // quiz modes + Kontext  |  Verben üben
  const VIEWS = ['quiz', 'vb-practice'];
  const START_ACTIONS = ['start-round'];                   // tap that opens the keyboard for the first card
  const SUBMIT_ACTIONS = ['submit-answer', 'vb-submit'];

  /* ---------------- tiny on-screen log (only with ?ipaddebug) ---------------- */
  let logEl = null; const lines = [];
  function dbg(msg){
    if(!debugOn) return;
    if(!logEl){
      logEl = document.createElement('div');
      logEl.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:9999;max-height:34vh;overflow:hidden;' +
        'background:rgba(0,0,0,.78);color:#9f9;font:11px/1.35 monospace;padding:4px 8px;pointer-events:none;white-space:pre-wrap;';
      document.body.appendChild(logEl);
    }
    lines.push(msg); if(lines.length > 14) lines.shift();
    logEl.textContent = lines.join('\n');
  }
  const idOf = (el) => !el ? 'none' : (el.id || el.tagName.toLowerCase());

  /* ---------------- the keeper ---------------- */
  const keeper = document.createElement('input');
  keeper.type = 'text'; keeper.id = 'kb-keeper'; keeper.tabIndex = -1;
  keeper.setAttribute('aria-hidden', 'true');
  keeper.setAttribute('autocomplete', 'off'); keeper.setAttribute('autocapitalize', 'off');
  keeper.setAttribute('autocorrect', 'off'); keeper.setAttribute('spellcheck', 'false');
  keeper.setAttribute('enterkeyhint', 'go');
  keeper.style.cssText = 'position:fixed;top:0;left:0;width:2px;height:2px;opacity:.01;border:0;padding:0;margin:0;' +
    'font-size:16px;color:transparent;background:transparent;caret-color:transparent;outline:none;';
  document.body.appendChild(keeper);

  let wantKb = false;                                      // true while you are typing in a quiz
  const answerInput = () => IDS.map(id => document.getElementById(id)).find(Boolean) || null;
  const keeperActive = () => document.activeElement === keeper;
  const inQuiz = () => VIEWS.indexOf(state.view) !== -1;

  function live(on){                                       // the answer bar looks focused while the keeper types for it
    const a = answerInput();
    if(a) a.style.borderColor = on ? 'var(--navy, #1f3a5f)' : '';
  }
  const rawFocus = HTMLElement.prototype.focus;
  function hold(why){                                      // only called inside a tap / key press
    if(!keeperActive()) rawFocus.call(keeper, { preventScroll: true });
    live(true);
    dbg('hold(' + why + ') -> active=' + idOf(document.activeElement));
    setTimeout(() => {                                     // never leave the keyboard stuck on a screen without a field
      if(keeperActive() && !inQuiz()){ keeper.blur(); wantKb = false; }
    }, 3500);
  }
  function release(){
    wantKb = false; keeper.value = '';
    if(keeperActive()) keeper.blur();
  }

  /* the app calls el.focus() on buttons / answer bars after each answer (good on a computer);
     on iOS that would pull the keyboard away from the keeper, so those calls are skipped */
  HTMLElement.prototype.focus = function(){
    if(wantKb && keeperActive() && this !== keeper && inQuiz() && this.closest && this.closest('#app')){
      dbg('ignored app focus() on ' + idOf(this));
      return;
    }
    return rawFocus.apply(this, arguments);
  };

  /* ---------------- events ---------------- */
  document.addEventListener('focusin', (e) => {
    if(e.target && IDS.indexOf(e.target.id) !== -1){ wantKb = true; keeper.value = ''; live(false); }
    dbg('focusin ' + idOf(e.target));
  }, true);
  keeper.addEventListener('focusout', (e) => {
    if(!e.relatedTarget){ wantKb = false; live(false); }   // keyboard was hidden by the user
    dbg('keeper focusout, related=' + idOf(e.relatedTarget));
  });

  document.addEventListener('keydown', (e) => {            // Return in the real answer bar: hand the keyboard to the keeper
    if(wantKb && e.key === 'Enter' && e.target && IDS.indexOf(e.target.id) !== -1) hold('Enter');
  }, true);

  document.addEventListener('click', (e) => {
    const el = e.target && e.target.closest ? e.target.closest('[data-action]') : null;
    if(!el) return;
    const act = el.dataset.action;
    if(START_ACTIONS.indexOf(act) !== -1){ wantKb = true; hold(act); }
    else if(wantKb && SUBMIT_ACTIONS.indexOf(act) !== -1){
      const a = answerInput(); if(a && keeperActive()) a.value = keeper.value;
      setTimeout(() => { keeper.value = ''; }, 0);         // the app has read the text by then
    }
  }, true);

  keeper.addEventListener('input', () => {                 // what you type goes live into the answer bar
    const a = answerInput();
    if(a) a.value = keeper.value;
  });
  keeper.addEventListener('keydown', (e) => {
    if(e.key !== 'Enter') return;
    e.preventDefault();
    const a = answerInput();
    if(a){                                                 // Return = submit, exactly like Return in the bar
      a.value = keeper.value; keeper.value = '';
      a.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true }));
      return;
    }
    const btn = document.querySelector('#vbcont, #cont, .continuewrap.show button');   // no bar on screen: Return = Weiter
    if(btn){ keeper.value = ''; btn.click(); }
  });

  /* ---------------- answer-bar attributes ---------------- */
  function tune(){
    IDS.forEach(id => {
      const a = document.getElementById(id);
      if(!a) return;
      a.setAttribute('autocapitalize', 'off'); a.setAttribute('autocorrect', 'off');
      a.setAttribute('spellcheck', 'false'); a.setAttribute('enterkeyhint', 'go');
    });
  }

  /* ---------------- next-word safety net (+ never advance one card twice) ---------------- */
  if(typeof nextWord === 'function'){
    const _next = nextWord;
    let last = null;
    nextWord = function(){
      if(state.mode === 'context') return _next.apply(this, arguments);
      const k = { sid: state.sessionId, q: state.quiz };
      if(last && last.sid === k.sid && last.q === k.q) return Promise.resolve();   // this card already moved on
      last = k;
      const p = _next.apply(this, arguments);
      Promise.resolve(p).catch(() => { if(last === k) last = null; });             // failed request: allow a retry
      return p;
    };
  }
  const armed = new WeakSet();
  function watchdog(){
    const q = state.quiz;
    if(state.view !== 'quiz' || state.mode === 'context' || !q || armed.has(q)) return;
    if(q.locked && q.feedback && q.feedback.type === 'correct' && !q.showContinue){
      armed.add(q);
      setTimeout(() => {
        if(state.view === 'quiz' && state.quiz === q && q.locked && typeof nextWord === 'function') nextWord();
      }, 2500);
    }
  }

  /* ---------------- correct answer -> next one by itself (Verben üben, Kontext) ---------------- */
  const AUTO_NEXT_MS = 1000;                               // long enough to see the green feedback and hear the sound
  const autoArmed = new WeakSet();
  if(typeof vbNext === 'function'){                        // never ask the server for the next verb twice
    const _vbNext = vbNext;
    let busy = false;
    vbNext = function(){
      if(busy) return Promise.resolve();
      busy = true;
      return Promise.resolve(_vbNext.apply(this, arguments)).finally(() => { busy = false; });
    };
  }
  function autoNext(){
    const vq = state.vbQ;                                  // Verben üben
    if(state.view === 'vb-practice' && vq && vq.locked && vq.feedback && vq.feedback.kind === 'correct'
       && !vq.feedback.retry && !autoArmed.has(vq.feedback)){
      const fb = vq.feedback; autoArmed.add(fb);
      setTimeout(() => {
        if(state.view === 'vb-practice' && state.vbQ === vq && vq.locked && vq.feedback === fb && typeof vbNext === 'function') vbNext();
      }, AUTO_NEXT_MS);
    }
    const cq = state.quiz;                                 // Kontext
    if(state.view === 'quiz' && state.mode === 'context' && cq && cq.locked && cq.feedback
       && cq.feedback.kind === 'correct' && !autoArmed.has(cq.feedback)){
      const fb = cq.feedback; autoArmed.add(fb);
      setTimeout(() => {
        if(state.view === 'quiz' && state.mode === 'context' && state.quiz === cq && cq.locked && cq.feedback === fb && typeof ctxNext === 'function') ctxNext();
      }, AUTO_NEXT_MS);
    }
  }

  /* ---------------- after every redraw ---------------- */
  const _render = render;
  render = function(){
    const out = _render.apply(this, arguments);
    if(!inQuiz()){ release(); return out; }                // left the quiz: let the keyboard go
    tune();
    watchdog();
    autoNext();
    const a = answerInput();
    if(wantKb && keeperActive()){
      if(a) a.value = keeper.value;                        // new card: show what was typed in the meantime (usually nothing)
      live(true);
    }
    dbg('render ' + state.view + ' bar=' + (a ? 'yes' : 'no') + ' keeper=' + (keeperActive() ? 'on' : 'off') + ' want=' + wantKb);
    return out;
  };

  dbg('ipad_mode ready · tablet=' + isTablet + ' · touch=' + (navigator.maxTouchPoints || 0) + ' · screen=' + screen.width + 'x' + screen.height);
})();