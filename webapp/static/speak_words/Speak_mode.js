/*
 * speak_mode.js — small speaker button on every word-pair row in "Wörter durchsehen".
 * It appears when you hover the row (instead of the ✨ hint) and reads the German
 * word(s) of that pair aloud, one after the other, slightly slowed down.
 *
 * Additive only. app.js, explain_mode.js, pagination.js and the Flask API are NOT edited.
 *   - it wraps render(): after the list is drawn it adds a button to each row (rows are
 *     matched by count against state.reviewResult.entries, same idea as explain_mode.js,
 *     so it works with the 30-per-page ribbon too);
 *   - clicks on the button are caught in the capture phase, so the row's own click
 *     (opening the AI explanation) does NOT fire when you press the speaker;
 *   - the German audio comes from /api/speak (speak_routes.py, gTTS lang=de, the same engine as the
 *     audio mode), so the pronunciation is real German on every device; each word is cached after
 *     the first time. If that is not reachable, it falls back to a German voice of the browser
 *     (speechSynthesis) when the device has one.
 * Load after app.js and explain_mode.js.
 */
(function(){
  if(typeof render !== 'function' || typeof state === 'undefined'){
    console.warn('[speak_mode] not started: app.js must be loaded first.');
    return;
  }

  const synth = window.speechSynthesis || null;
  let token = 0;          // bumps on every stop/start, so stale callbacks do nothing
  let timer = null;
  let activeBtn = null;
  let audio = null;       // the <audio> that is playing right now

  function germanVoice(){
    if(!synth) return null;
    const v = synth.getVoices() || [];
    return v.find(x => /^de[-_]DE/i.test(x.lang)) || v.find(x => /^de/i.test(x.lang)) || null;
  }
  if(synth){ try{ synth.getVoices(); synth.addEventListener && synth.addEventListener('voiceschanged', () => synth.getVoices()); }catch(_){} }

  let toastEl = null, toastTimer = null;
  function toast(msg){
    if(!toastEl){ toastEl = document.createElement('div'); toastEl.className = 'sp-toast'; document.body.appendChild(toastEl); }
    toastEl.textContent = msg; toastEl.style.display = 'block';
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastEl.style.display = 'none'; }, 3500);
  }

  function stop(){
    token++;
    clearTimeout(timer);
    if(audio){ try{ audio.onended = audio.onerror = null; audio.pause(); }catch(_){} audio = null; }
    try{ if(synth) synth.cancel(); }catch(_){}
    if(activeBtn){
      activeBtn.classList.remove('speaking');
      const row = activeBtn.closest('.reviewrow'); if(row) row.classList.remove('sp-on');
      activeBtn = null;
    }
  }

  /* one word from the server (gTTS, German); done(true) when it finished, done(false) if it could not play */
  function playServer(word, done){
    let finished = false;
    const fin = (ok) => { if(!finished){ finished = true; done(ok); } };
    const a = new Audio('/api/speak?text=' + encodeURIComponent(word));
    audio = a;
    a.onended = () => fin(true);
    a.onerror = () => fin(false);
    const p = a.play();
    if(p && p.catch) p.catch(() => fin(false));
  }

  /* fallback: a German voice of the browser, only if the device has one */
  function playBrowser(word, done){
    const voice = germanVoice();
    if(!synth || !voice){ done(false); return; }
    const u = new SpeechSynthesisUtterance(word);
    u.lang = 'de-DE'; u.voice = voice; u.rate = 0.85;
    u.onend = () => done(true);
    u.onerror = () => done(false);
    synth.speak(u);
  }

  function speak(words, btn){
    stop();
    const my = token;
    activeBtn = btn; btn.classList.add('speaking');
    const row = btn.closest('.reviewrow'); if(row) row.classList.add('sp-on');   // keeps the speaker visible while it talks

    let i = 0;
    const next = () => {
      if(my !== token) return;
      if(i >= words.length){ stop(); return; }
      const word = words[i++];
      playServer(word, (ok) => {
        if(my !== token) return;
        if(ok){ timer = setTimeout(next, 450); return; }          // short pause between the words
        playBrowser(word, (ok2) => {
          if(my !== token) return;
          if(ok2){ timer = setTimeout(next, 450); return; }
          toast('Aussprache nicht erreichbar. Läuft der Server mit Internet und ist gTTS installiert?');
          stop();
        });
      });
    };
    timer = setTimeout(next, 0);
  }

  /* ---------------- hook into the existing dashboard ---------------- */
  function decorateRows(){
    const r = state.reviewResult;
    const app = document.getElementById('app');
    if(!r || !Array.isArray(r.entries) || !app) return;
    const rows = app.querySelectorAll('.reviewrow');
    if(rows.length !== r.entries.length) return;       // not the list we expect: leave it alone
    rows.forEach((row, i) => {
      if(row.querySelector('.sp-btn')) return;
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'sp-btn';
      b.dataset.action = 'sp-speak'; b.dataset.idx = String(i);
      b.title = 'Aussprache anhören'; b.setAttribute('aria-label', 'Aussprache anhören');
      b.textContent = '🔊';
      row.appendChild(b);
      row.classList.add('sp-has');
    });
  }

  const _origRender = render;
  render = function(){
    stop();                                            // a re-render (page change, leaving the list) ends any speech
    const out = _origRender.apply(this, arguments);
    if(state.view === 'review-list') decorateRows();
    return out;
  };

  /* capture phase: runs before the row's own click handlers, so the AI explanation is not opened */
  document.addEventListener('click', (e) => {
    const b = e.target && e.target.closest ? e.target.closest('[data-action="sp-speak"]') : null;
    if(!b) return;
    e.stopPropagation(); e.preventDefault();
    if(b.classList.contains('speaking')){ stop(); return; }   // second click = stop
    const r = state.reviewResult;
    const entry = r && r.entries ? r.entries[parseInt(b.dataset.idx, 10)] : null;
    if(!entry) return;
    const words = String(entry.german).split(',').map(s => s.trim()).filter(Boolean);
    if(words.length) speak(words, b);
  }, true);
})();