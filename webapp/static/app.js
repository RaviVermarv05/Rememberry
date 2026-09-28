/*
 * app.js — rendering + event wiring ONLY.
 *
 * This file never decides whether an answer is right or wrong, never counts
 * trials, never classifies an error, and never generates the German/English
 * feedback text. Every one of those decisions comes back from the Flask API
 * (app.py), which calls the real logics.py / error_classifier.py /
 * messages.py / main_settings.py. app.js just calls fetch() and puts
 * whatever the API returned onto the screen.
 */
const API = ''; // same-origin; Flask serves this file from /static

async function api(path, opts){
  const res = await fetch(API + path, opts);
  if(!res.ok) throw new Error('API error ' + res.status);
  return res.json();
}
const get = (path) => api(path);
const post = (path, body) => api(path, {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(body || {})
});

let state = { view: 'loading' };

/* Same two sounds the CLI uses; volume/enable come from Settings via /api/settings. */
const SOUNDS = {
  correct: new Audio('/sound/correct-156911.mp3'),
  wrong: new Audio('/sound/error-010-206498.mp3')
};
function playSound(kind){
  const s = state.settings;
  if(!s || !s.sound_enable) return;
  const a = SOUNDS[kind];
  a.volume = Math.max(0, Math.min(1, s.volume));
  a.currentTime = 0;
  a.play().catch(() => {});
}

function go(view, extra){
  state = Object.assign({}, state, { view }, extra || {});
  render();
}

async function boot(){
  try{
    const [{ chapters }, settings] = await Promise.all([
      get('/api/chapters'), get('/api/settings')
    ]);
    go('home', { chapters, settings });
  }catch(e){
    document.getElementById('app').innerHTML =
      `<div class="loading-note">⚠️ Konnte die API nicht erreichen.<br><span style="font-size:12px">${e.message} — läuft <code>python app.py</code>?</span></div>`;
  }
}

function render(){
  const app = document.getElementById('app');
  app.innerHTML = header() + body();
  wireEvents();
}

function modeLabel(){
  return state.mode === 'ger_eng' ? '🇩🇪→🇬🇧 Deutsch → Englisch' : '🇬🇧→🇩🇪 Englisch → Deutsch';
}

function header(){
  return `<div class="topbar"><div class="brand"><span class="mark">🍓</span><h1>Rememberry</h1></div></div>`;
}

function body(){
  switch(state.view){
    case 'home': return viewHome();
    case 'chapters': return viewChapters();
    case 'range': return viewRange();
    case 'quiz': return viewQuiz();
    case 'history': return viewHistory();
    case 'results': return viewResults();
    default: return '';
  }
}

/* ---------------- home ---------------- */
function viewHome(){
  const total = state.chapters.reduce((s,c)=>s+c.count,0);
  return `
  <p class="tag">Netzwerk B1 · Vokabeltrainer</p>
  <div class="modegrid">
    <button class="modecard" data-action="start-flow" data-mode="eng_ger">
      <div class="label">🇬🇧→🇩🇪 Englisch → Deutsch</div>
      <div class="desc">Tippe das deutsche Wort, Artikel inklusive. ${total} Vokabeln über ${state.chapters.length} Kapitel.</div>
    </button>
    <button class="modecard" data-action="start-flow" data-mode="ger_eng">
      <div class="label">🇩🇪→🇬🇧 Deutsch → Englisch</div>
      <div class="desc">Tippe das passende englische Wort. ${total} Vokabeln über ${state.chapters.length} Kapitel.</div>
    </button>
  </div>`;
}

/* ---------------- chapter select ---------------- */
function viewChapters(){
  if(!state.selected) state.selected = new Set(state.chapters.map(c=>c.number));
  const allOn = state.selected.size === state.chapters.length;
  const chips = state.chapters.map(c => `
    <button class="chip ${state.selected.has(c.number)?'active':''}" data-action="toggle-chapter" data-n="${c.number}">
      Kapitel ${c.number} <span class="n">${c.count}</span>
    </button>`).join('');
  return `
  <div class="crumbrow"><button class="backlink" data-action="go" data-view="home">← Start</button></div>
  <p class="tag" style="margin-top:-6px;">${modeLabel()}</p>
  <h2 style="font-size:20px;margin-bottom:14px;">Kapitel wählen</h2>
  <div class="chiprow">
    <button class="chip ${allOn?'active':''}" data-action="toggle-all-chapters">Alle Kapitel</button>
    ${chips}
  </div>
  <button class="primarybtn" ${state.selected.size===0?'disabled':''} data-action="go" data-view="range">Weiter</button>`;
}

/* ---------------- range select ---------------- */
function viewRange(){
  if(state.rangeMode === undefined) state.rangeMode = 'all';
  const total = state.chapters.filter(c=>state.selected.has(c.number)).reduce((s,c)=>s+c.count,0);
  return `
  <div class="crumbrow"><button class="backlink" data-action="go" data-view="chapters">← Kapitel</button></div>
  <p class="tag" style="margin-top:-6px;">${modeLabel()}</p>
  <h2 style="font-size:20px;margin-bottom:14px;">Umfang wählen</h2>
  <div class="fieldcard">
    <h3>${total} Wortpaare verfügbar</h3>
    <div class="radiorow">
      <label class="radioopt ${state.rangeMode==='all'?'active':''}" data-action="set-range-mode" data-mode="all">Alle Wörter üben</label>
      <label class="radioopt ${state.rangeMode==='custom'?'active':''}" data-action="set-range-mode" data-mode="custom">Bestimmten Bereich wählen</label>
    </div>
    ${state.rangeMode==='custom' ? `
    <div class="rangeinputs">
      <div><label>Von</label><input type="number" id="rstart" min="1" max="${total}" value="${state.start||1}"></div>
      <div><label>Bis</label><input type="number" id="rend" min="1" max="${total}" value="${state.end||total}"></div>
    </div>` : ''}
  </div>
  <button class="primarybtn" data-action="start-round">Los geht's</button>`;
}

/* ---------------- quiz ---------------- */
function viewQuiz(){
  return state.mode === 'ger_eng' ? viewQuizGerEng() : viewQuizEngGer();
}

/* Englisch -> Deutsch: fill one slot per German synonym, article follow-up */
function viewQuizEngGer(){
  const q = state.quiz;
  const pct = q.progress ? Math.round((q.progress.completed / q.progress.total) * 100) : 0;
  const slots = (q.slots || []).map(s =>
    `<span class="slot ${s.status}">${s.status==='pending' ? '?' : s.text}</span>`).join('');

  let inputArea;
  if(q.awaitingArticle){
    inputArea = `
      <div class="articlerow">
        <span>${q.articlePrompt}</span>
        <button class="artbtn" data-action="submit-article" data-art="der">der</button>
        <button class="artbtn" data-action="submit-article" data-art="die">die</button>
        <button class="artbtn" data-action="submit-article" data-art="das">das</button>
      </div>`;
  } else if(!q.locked){
    inputArea = `
      <div class="answerrow">
        <input type="text" id="ans" placeholder="deutsches Wort…" autocomplete="off">
        <button data-action="submit-answer">✓</button>
      </div>
      <div class="attemptsline">Falsche Versuche: ${q.wrongGuesses||0}/${state.settings.trials}</div>`;
  } else {
    inputArea = `<div class="attemptsline">Falsche Versuche: ${q.wrongGuesses||0}/${state.settings.trials}</div>`;
  }

  return `
  <div class="crumbrow" style="display:flex;justify-content:space-between;">
    <button class="backlink" data-action="go" data-view="home">← Beenden</button>
    ${q.progress && q.progress.completed > 0 ? `<button class="backlink" data-action="show-history">📜 Bisherige Wörter</button>` : ''}
  </div>
  <div class="progresswrap">
    <div class="progresstrack"><div class="progressfill" style="width:${pct}%"></div></div>
    <div class="scorepill">${q.progress ? q.progress.completed : 0}/${q.progress ? q.progress.total : 0}</div>
  </div>
  <div class="flashcard">
    <div class="kicker">${q.intro || ''}</div>
    <div class="prompt">${q.displayEng || ''}</div>
    <div class="slotrow">${slots}</div>
    ${inputArea}
    <div class="feedback ${q.feedback ? q.feedback.type : ''}">${q.feedback ? q.feedback.msg : ''}</div>
    <div class="continuewrap ${q.showContinue ? 'show' : ''}">
      <button class="primarybtn" data-action="continue-round">Weiter →</button>
    </div>
  </div>`;
}

/* Deutsch -> Englisch: one English answer clears the whole card (no slots,
   no article follow-up) — mirrors quiz_ger_eng() in main.py exactly. */
function viewQuizGerEng(){
  const q = state.quiz;
  const pct = q.progress ? Math.round((q.progress.completed / q.progress.total) * 100) : 0;

  let inputArea;
  if(!q.locked){
    inputArea = `
      <div class="answerrow">
        <input type="text" id="ans" placeholder="English word…" autocomplete="off">
        <button data-action="submit-answer">✓</button>
      </div>
      <div class="attemptsline">Falsche Versuche: ${q.wrongGuesses||0}/${state.settings.trials}</div>`;
  } else {
    inputArea = `<div class="attemptsline">Falsche Versuche: ${q.wrongGuesses||0}/${state.settings.trials}</div>`;
  }

  return `
  <div class="crumbrow" style="display:flex;justify-content:space-between;">
    <button class="backlink" data-action="go" data-view="home">← Beenden</button>
    ${q.progress && q.progress.completed > 0 ? `<button class="backlink" data-action="show-history">📜 Bisherige Wörter</button>` : ''}
  </div>
  <div class="progresswrap">
    <div class="progresstrack"><div class="progressfill" style="width:${pct}%"></div></div>
    <div class="scorepill">${q.progress ? q.progress.completed : 0}/${q.progress ? q.progress.total : 0}</div>
  </div>
  <div class="flashcard">
    <div class="kicker">${q.intro || ''}</div>
    <div class="prompt">${q.displayDe || ''}</div>
    ${inputArea}
    <div class="feedback ${q.feedback ? q.feedback.type : ''}">${q.feedback ? q.feedback.msg : ''}</div>
    ${q.attemptsMessage ? `<div class="attemptsline">${q.attemptsMessage}</div>` : ''}
    <div class="continuewrap ${q.showContinue ? 'show' : ''}">
      <button class="primarybtn" data-action="continue-round">Weiter →</button>
    </div>
  </div>`;
}

/* ---------------- history (review already-completed words) ---------------- */
function viewHistory(){
  const items = state.history || [];
  return `
  <div class="crumbrow"><button class="backlink" data-action="back-to-quiz">← Zurück zur Übung</button></div>
  <h2 style="font-size:20px;margin-bottom:4px;">Bisherige Wörter</h2>
  <p style="font-size:13px;color:var(--ink-soft);margin:4px 0 14px;">${items.length} bereits bearbeitet</p>
  <div class="fieldcard" style="padding:6px 16px;">
    ${items.length ? items.map(it => `
      <div class="row" style="display:flex;justify-content:space-between;gap:12px;align-items:baseline;">
        <span><strong style="font-family:var(--serif);color:var(--navy);">${it.de.join(', ')}</strong> — ${it.en}</span>
        <span style="font-size:11.5px;font-weight:600;color:${it.missed ? 'var(--berry)' : 'var(--green)'};white-space:nowrap;">${it.missed ? 'zum Üben' : '✓ richtig'}</span>
      </div>`).join('') : '<div class="row">Noch keine Wörter bearbeitet.</div>'}
  </div>`;
}

/* ---------------- results ---------------- */
function viewResults(){
  const r = state.result;
  const ERROR_LABELS = {
    no_answer: 'keine Antwort', missing_noun: 'nur Artikel eingegeben', wrong_article: 'falscher Artikel',
    wrong_translation: 'falsche Übersetzung', spelling_error: 'Tippfehler', missing_article: 'Artikel fehlt',
    unclassified: 'nicht klassifiziert'
  };
  return `
  <div class="resultcard">
    <div class="msg" style="margin-top:0">${r.congrats_msg}</div>
    <div class="sub">${r.result_line}</div>
    ${r.all_complete ? `<div class="msg">${r.all_complete}</div>` : ''}
    ${r.practice_words && r.practice_words.length ? `
      <div class="practicelist">
        <h4>${r.practice_head || ''}</h4>
        ${r.practice_words.filter(w=>w.trim()).map(w=>`<div class="row">• ${w}</div>`).join('')}
      </div>` : ''}
    ${r.error_summary && r.error_summary.length ? `
      <div class="practicelist">
        <h4>🧩 Fehlermuster</h4>
        ${r.error_summary.map(g => `
          <div class="row" style="font-weight:600;">${ERROR_LABELS[g.error_type] || g.error_type} (${g.count}×)</div>
          ${g.words.map(w => `<div class="row" style="padding-left:14px;font-size:13px;">• ${w.word}${w.count>1?` (${w.count}×)`:''}</div>`).join('')}
        `).join('')}
      </div>` : ''}
    <div class="btnrow" style="margin-top:24px;">
      <button class="ghostbtn" data-action="go" data-view="home">Zur Startseite</button>
    </div>
  </div>`;
}

/* ---------------- actions: everything below just calls the API and re-renders ---------------- */

function apiPath(name){
  // Same endpoint shapes, different route prefix per direction —
  // /api/round/* for Englisch->Deutsch, /api/round2/* for Deutsch->Englisch.
  const prefix = state.mode === 'ger_eng' ? '/api/round2' : '/api/round';
  return `${prefix}/${name}`;
}

async function startRound(){
  let start = null, end = null;
  if(state.rangeMode === 'custom'){
    start = parseInt(document.getElementById('rstart').value, 10);
    end = parseInt(document.getElementById('rend').value, 10);
    if(!start || !end || start < 1 || end < start){ alert('Bitte einen gültigen Bereich eingeben.'); return; }
  }
  const { session_id, total_words } = await post(apiPath('start'), {
    chapters: [...state.selected], start, end
  });
  state.sessionId = session_id;
  await nextWord();
}

async function nextWord(){
  const data = await post(apiPath('next'), { session_id: state.sessionId });
  if(data.done){
    go('results', { result: data });
    return;
  }
  if(state.mode === 'ger_eng'){
    go('quiz', {
      quiz: {
        displayDe: data.display_de, intro: data.intro, progress: data.progress,
        wrongGuesses: 0, locked: false, feedback: null, showContinue: false, attemptsMessage: null
      }
    });
  } else {
    go('quiz', {
      quiz: {
        displayEng: data.display_eng, intro: data.intro, progress: data.progress,
        slots: Array.from({length: data.word_count}, () => ({status:'pending', text:'?'})),
        wrongGuesses: 0, awaitingArticle: false, locked: false, feedback: null, showContinue: false
      }
    });
  }
  focusAnswerInput();
}

async function submitAnswer(){
  const input = document.getElementById('ans');
  const answer = input.value;
  input.value = '';
  const data = await post(apiPath('answer'), { session_id: state.sessionId, answer });
  const q = state.quiz;

  if(state.mode === 'ger_eng'){
    if(data.result === 'correct'){
      playSound('correct');
      q.feedback = { type: 'correct', msg: data.message };
      q.locked = true;
      setTimeout(nextWord, 750);
    } else if(data.result === 'wrong'){
      playSound('wrong');
      q.feedback = { type: 'wrong', msg: data.message };
      q.attemptsMessage = data.attempts_message;
      q.wrongGuesses = data.wrong_guesses;
    } else if(data.result === 'revealed'){
      playSound('wrong');
      // Mode 2: the answer to reveal is the ENGLISH term(s), like main.py's `print(f"- {display_eng}")`
      q.feedback = { type: 'revealed', msg: `${data.incorrect_head} ${data.correct_head} ${data.display_eng}` };
      q.attemptsMessage = null;
      q.wrongGuesses = data.wrong_guesses;
      q.locked = true;
      q.showContinue = true;
    }
    render();
    focusAnswerInput();
    return;
  }

  if(data.result === 'needs_article'){
    playSound('correct');
    q.feedback = { type: 'correct', msg: data.message };
    q.awaitingArticle = true;
    q.articlePrompt = data.prompt;
  } else if(data.result === 'correct'){
    playSound('correct');
    q.feedback = { type: 'correct', msg: data.message };
    fillSlot(q, data.word, 'done');
    if(data.round_complete){
      q.locked = true;
      setTimeout(nextWord, 750);
    }
  } else if(data.result === 'wrong'){
    playSound('wrong');
    q.feedback = { type: 'wrong', msg: `${data.message} · Falsche Versuche: ${data.wrong_guesses}/${data.trials}` };
    q.wrongGuesses = data.wrong_guesses;
  } else if(data.result === 'revealed'){
    playSound('wrong');
    (data.words || []).forEach(w => fillSlot(q, w, 'failed'));
    q.feedback = { type: 'revealed', msg: `${data.incorrect_head} ${data.correct_head} ${(data.words||[]).join(', ')}` };
    q.wrongGuesses = data.wrong_guesses;
    q.locked = true;
    q.showContinue = true;
  }
  render();
  focusAnswerInput();
}

async function submitArticle(article){
  // Article follow-up only exists in Englisch -> Deutsch mode.
  const q = state.quiz;
  const data = await post('/api/round/article', { session_id: state.sessionId, article });
  q.awaitingArticle = false;
  playSound(data.result === 'correct' ? 'correct' : 'wrong');
  q.feedback = { type: data.result === 'correct' ? 'correct' : 'wrong', msg: data.message };
  // we don't get the exact word text back separately here beyond the message,
  // so mark the still-pending slot using the message content the API already formatted
  const pendingIdx = q.slots.findIndex(s => s.status === 'pending');
  if(pendingIdx !== -1) q.slots[pendingIdx] = { status: data.result === 'correct' ? 'done' : 'failed', text: extractWordFromMessage(data.message) };

  if(data.round_complete){
    q.locked = true;
    setTimeout(nextWord, 750);
  }
  render();
}

function extractWordFromMessage(msg){
  // both artikel_ist_richtig/artikel_ist_falsch end with ": <word>"
  const idx = msg.lastIndexOf(':');
  return idx !== -1 ? msg.slice(idx+1).trim() : msg;
}

function fillSlot(q, text, status){
  const idx = q.slots.findIndex(s => s.status === 'pending');
  if(idx !== -1) q.slots[idx] = { status, text };
}

function focusAnswerInput(){
  const el = document.getElementById('ans');
  if(el) el.focus();
}

/* ---------------- event delegation ---------------- */
function wireEvents(){
  document.querySelectorAll('[data-action]').forEach(el => {
    el.addEventListener('click', onAction);
  });
  const ans = document.getElementById('ans');
  if(ans) ans.addEventListener('keydown', e => { if(e.key === 'Enter') submitAnswer(); });
}

function onAction(e){
  const el = e.currentTarget;
  const action = el.dataset.action;
  if(action === 'go') go(el.dataset.view);
  else if(action === 'start-flow') go('chapters', { mode: el.dataset.mode, selected: null, rangeMode: undefined });
  else if(action === 'toggle-chapter'){
    const n = parseInt(el.dataset.n, 10);
    if(state.selected.has(n)) state.selected.delete(n); else state.selected.add(n);
    render();
  }
  else if(action === 'toggle-all-chapters'){
    state.selected = state.selected.size === state.chapters.length ? new Set() : new Set(state.chapters.map(c=>c.number));
    render();
  }
  else if(action === 'set-range-mode'){ state.rangeMode = el.dataset.mode; render(); }
  else if(action === 'start-round') startRound();
  else if(action === 'submit-answer') submitAnswer();
  else if(action === 'submit-article') submitArticle(el.dataset.art);
  else if(action === 'continue-round'){
    if(state.quiz.locked) nextWord();
  }
  else if(action === 'show-history') showHistory();
  else if(action === 'back-to-quiz') go('quiz');
}

async function showHistory(){
  const data = await post(apiPath('history'), { session_id: state.sessionId });
  go('history', { history: data.history });
}

boot();