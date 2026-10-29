/*
 * verbs_mode.js — mode 7 (verbs) for the dashboard. Loaded after app.js and uses
 * its globals (state, go, get, post, playSound). Same rule as app.js: rendering
 * only; clue choice, answer checking, scoring and the mistake list come from
 * /api/verbmode/* (verbs_routes.py).
 *
 * app.js is NOT edited. This file adds itself in two small ways:
 *   1. it wraps viewHome() to append one more mode card, and body() to render
 *      its own views (all view names start with "vb-"); everything else falls
 *      through to the original functions unchanged
 *   2. it listens for clicks on data-action="vb-…" elements (app.js ignores
 *      actions it doesn't know)
 */
const vbEsc = (s) => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

/* ---------------- hook into the existing dashboard ---------------- */
const _vbOrigViewHome = viewHome;
viewHome = function(){
  const html = _vbOrigViewHome();
  const card = `
    <button class="modecard" data-action="vb-open">
      <div class="label">🔤 Verben</div>
      <div class="desc">Verben durchsehen oder üben: Bedeutung, Präsens, Präteritum und Perfekt.</div>
    </button>`;
  return html.replace(/<\/div>\s*$/, card + '\n  </div>');
};

const _vbOrigBody = body;
body = function(){
  switch(state.view){
    case 'vb-setup': return viewVbSetup();
    case 'vb-review': return viewVbReview();
    case 'vb-practice': return viewVbPractice();
    case 'vb-results': return viewVbResults();
    default: return _vbOrigBody();
  }
};

document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-action^="vb-"]');
  if(!el) return;
  const a = el.dataset.action;
  if(a === 'vb-open') vbOpen();
  else if(a === 'vb-choice'){ state.vb.choice = el.dataset.choice; render(); }
  else if(a === 'vb-hard'){ state.vb.hard = el.dataset.hard === '1'; render(); }
  else if(a === 'vb-range-mode'){ state.vb.rangeMode = el.dataset.mode; render(); }
  else if(a === 'vb-go') vbGo();
  else if(a === 'vb-submit') vbSubmit();
  else if(a === 'vb-continue') vbNext();
  else if(a === 'vb-quit') vbQuit();
});

document.addEventListener('keydown', (e) => {
  if(e.key === 'Enter' && e.target && e.target.id === 'vbans') vbSubmit();
});

/* ---------------- setup: review or practice + range (like handle_verb_mode) ---------------- */
async function vbOpen(){
  if(!state.vb) state.vb = { choice: 'practice', rangeMode: 'all', hard: false };
  try{
    const { verbs } = await get('/api/verbs');   // existing endpoint, only used for the count
    state.vb.total = verbs.length;
  }catch(e){ alert(e.message); return; }
  // new random tip every time the mode is opened (kept in state so clicking
  // the options on the setup screen does not change it)
  try{
    const last = state.vb.tipIndex;
    const t = await get('/api/verbmode/tip' + (last != null ? '?last=' + last : ''));
    state.vb.tip = t.tip; state.vb.tipIndex = t.index;
  }catch(e){ state.vb.tip = null; }
  go('vb-setup');
}

function viewVbSetup(){
  const v = state.vb, total = v.total;
  return `
  <div class="crumbrow"><button class="backlink" data-action="go" data-view="home">← Start</button></div>
  <p class="tag" style="margin-top:-6px;">🔤 Verben</p>
  ${v.tip ? `<div class="vbtip"><span class="vbtip-icon">💡</span><span>${vbEsc(v.tip)}</span></div>` : ''}
  <h2 style="font-size:20px;margin-bottom:14px;">Was möchtest du tun?</h2>
  <div class="fieldcard">
    <div class="radiorow">
      <label class="radioopt ${v.choice==='review'?'active':''}" data-action="vb-choice" data-choice="review">Verben durchsehen</label>
      <label class="radioopt ${v.choice==='practice'?'active':''}" data-action="vb-choice" data-choice="practice">Verben üben</label>
    </div>
  </div>
  ${v.choice==='practice' ? `<div class="fieldcard">
    <h3>Schwierigkeit</h3>
    <div class="radiorow">
      <label class="radioopt ${!v.hard?'active':''}" data-action="vb-hard" data-hard="0">Leicht</label>
      <label class="radioopt ${v.hard?'active':''}" data-action="vb-hard" data-hard="1">Schwer</label>
    </div>
    <div class="setdesc" style="margin-top:8px;">${v.hard ? 'Die Fragen aller Verben werden gemischt – nie zweimal hintereinander dasselbe Verb.' : 'Ein Verb nach dem anderen, alle vier Fragen hintereinander.'}</div>
  </div>` : ''}
  <div class="fieldcard">
    <h3>${total} Verben verfügbar</h3>
    <div class="radiorow">
      <label class="radioopt ${v.rangeMode==='all'?'active':''}" data-action="vb-range-mode" data-mode="all">Alle Verben</label>
      <label class="radioopt ${v.rangeMode==='custom'?'active':''}" data-action="vb-range-mode" data-mode="custom">Bestimmten Bereich wählen</label>
    </div>
    ${v.rangeMode==='custom' ? `
    <div class="rangeinputs">
      <div><label>Von</label><input type="number" id="vbstart" min="1" max="${total}" value="${v.start||1}"></div>
      <div><label>Bis</label><input type="number" id="vbend" min="1" max="${total}" value="${v.end||total}"></div>
    </div>` : ''}
  </div>
  <button class="primarybtn" data-action="vb-go">${v.choice==='review' ? 'Anzeigen' : "Los geht's"}</button>`;
}

async function vbGo(){
  const v = state.vb;
  let start = null, end = null;
  if(v.rangeMode === 'custom'){
    start = parseInt(document.getElementById('vbstart').value, 10);
    end = parseInt(document.getElementById('vbend').value, 10);
    if(!start || !end || start < 1 || end < start){ alert('Bitte einen gültigen Bereich eingeben.'); return; }
    v.start = start; v.end = end;
  }
  try{
    if(v.choice === 'review'){
      const r = await post('/api/verbmode/review', { start, end });
      go('vb-review', { vbReview: r });
    }else{
      const s = await post('/api/verbmode/start', { start, end, hard: !!v.hard });
      state.sessionId = s.session_id;
      go('vb-practice', { vbQ: { loading: true } });
      vbNext();
    }
  }catch(e){ alert(e.message); }
}

/* ---------------- review (list, same data review() prints) ---------------- */

function viewVbReview() {
  const r = state.vbReview;
  const note = r.range
    ? `📝 Bereich ${r.range.start}–${r.range.end}`
    : `Alle ${r.total} Verben`;

  // verbs that form the Perfekt with "sein" ("ist gegangen", "ist/hat ausgezogen") are shown in red
  const takesSein = (e) => /^ist[\s/]/i.test((e.perfekt || '').trim());

  const rows = r.entries.map(e => `
    <tr class="${e.no % 10 === 0 ? 'group-end' : ''}${takesSein(e) ? ' vb-sein' : ''}">
      <td>${e.no}. ${vbEsc(e.verb)}</td>
      <td>${vbEsc(e.meaning)}</td>
      <td>${vbEsc(e['präsens'])}</td>
      <td>${vbEsc(e['präteritum'])}</td>
      <td>${vbEsc(e.perfekt)}</td>
    </tr>
  `).join('');

  return `
    <div class="crumbrow">
      <button class="backlink" data-action="vb-open">← Umfang</button>
    </div>

    <p class="tag" style="margin-top:-6px;">
      🔤 Verben · ${note}
    </p>

    <h2 style="font-size:20px;margin-bottom:14px;">
      Verben
    </h2>

    <div class="vbtable-wrap">
      <table class="vbtable">
        <thead>
          <tr>
            <th>Verbs</th>
            <th>Meaning</th>
            <th>Präsens</th>
            <th>Präteritum</th>
            <th>Perfekt</th>
          </tr>
        </thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
    </div>

    <button class="ghostbtn"
      style="margin-top:16px;"
      data-action="go"
      data-view="home">
      Fertig
    </button>
  `;
}


/* ---------------- practice ---------------- */
function viewVbPractice(){
  const q = state.vbQ, fb = q.feedback;
  if(q.loading) return `
    <div class="crumbrow"><button class="backlink" data-action="vb-quit">← Beenden</button></div>
    <div class="loading-note">🍓 Lade Verb …</div>`;
  const { completed, total } = q.progress;
  let action = '', feedback = '';
  if(!q.locked){
    action = `
      <div class="answerrow"><input id="vbans" type="text" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="${vbEsc(q.question.label)} …"><button data-action="vb-submit">Prüfen</button></div>
      <div class="attemptsline">Falsche Versuche: ${q.wrong_guesses||0}/${q.trials}</div>
      <div class="attemptsline">Tippe „q“, um zu beenden.</div>`;
  }
  if(fb){
    const correctLine = fb.correct_answer ? `<div class="vbcorrect">⚠️ Correct answer: <strong>${vbEsc(fb.correct_answer)}</strong></div>` : '';
    const done = fb.verb_complete ? `<div class="vbdone">✓ Verb abgeschlossen!</div>` : '';
    feedback = `<div class="feedback ${fb.kind}"><div class="msg">${vbEsc(fb.message)}</div>${correctLine}${done}</div>
      ${fb.retry ? '' : `<div class="continuewrap show"><button class="primarybtn" id="vbcont" data-action="vb-continue">${fb.verb_complete ? 'Nächstes Verb' : 'Weiter'}</button></div>`}`;
  }
  return `
  <div class="crumbrow"><button class="backlink" data-action="vb-quit">← Beenden</button></div>
  <p class="tag" style="margin-top:-6px;">🔤 Verben · Üben</p>
  <div class="progresswrap"><div class="progresstrack"><div class="progressfill" style="width:${Math.round(completed / total * 100)}%"></div></div>
    <span class="scorepill">${q.hard ? `Frage ${q.question_number} / ${total}` : `Verb ${q.verb_number} / ${total}`}</span></div>
  <div class="flashcard">
    <div class="kicker">Hinweis · ${vbEsc(q.clue.label)}</div>
    <div class="prompt">${vbEsc(q.clue.value)}</div>
    <div class="vbask">${q.hard ? 'Gesucht' : `Frage ${q.question.number} von ${q.question.of}`}: <strong>${vbEsc(q.question.label)}</strong></div>
    ${action}${feedback}
  </div>`;
}

function vbFocus(){
  const cont = document.getElementById('vbcont');
  if(cont) cont.focus(); else { const a = document.getElementById('vbans'); if(a) a.focus(); }
}

async function vbNext(){
  let d;
  try{ d = await post('/api/verbmode/next', { session_id: state.sessionId }); }
  catch(e){ alert(e.message); go('home'); return; }
  if(d.done){ go('vb-results', { vbResult: d }); return; }
  go('vb-practice', { vbQ: Object.assign({}, d, { feedback: null, locked: false }) });
  vbFocus();
}

async function vbSubmit(){
  const q = state.vbQ, input = document.getElementById('vbans');
  if(state.answerInFlight || !input || q.locked) return;
  state.answerInFlight = true;
  const answer = input.value; input.value = '';
  try{
    const d = await post('/api/verbmode/answer', { session_id: state.sessionId, answer });
    if(d.result === 'quit'){ state.answerInFlight = false; go('home'); return; }
    if(d.result === 'duplicate'){ state.answerInFlight = false; return vbNext(); }
    playSound(d.result === 'correct' ? 'correct' : 'wrong');
    if(d.result === 'retry'){          // wrong, but Versuche pro Wort allows another try: stay on this question
      q.wrong_guesses = d.wrong_guesses; q.trials = d.trials;
      q.feedback = { kind: 'wrong', retry: true, message: `${d.message} · Falsche Versuche: ${d.wrong_guesses}/${d.trials}` };
      q.locked = false;
    }else{
      q.feedback = { kind: d.result, message: d.message, correct_answer: d.correct_answer, verb_complete: d.verb_complete };
      q.locked = true;
    }
  }catch(e){ q.feedback = { kind: 'wrong', message: e.message }; }
  finally{ state.answerInFlight = false; }
  render(); vbFocus();
}

async function vbQuit(){
  try{ await post('/api/verbmode/quit', { session_id: state.sessionId }); }catch(e){}
  go('home');
}

/* ---------------- results ---------------- */
function viewVbResults(){
  const r = state.vbResult;
  const mistakes = r.perfect ? `<div class="msg">🎉 Perfekt! Keine Fehler!</div>` : `
    <div class="practicelist"><h4>Deine Fehler</h4>
      ${r.mistakes.map((m, i) => `
        <div class="row vbmistake">
          <div><strong>${i + 1}. ${vbEsc(m.verb)}</strong> · ${vbEsc(m.question)}</div>
          <div class="vbyours">Deine Antwort: ${m.your_answer ? vbEsc(m.your_answer) : '—'}</div>
          <div>Richtig: <strong>${vbEsc(m.correct_answer)}</strong></div>
        </div>`).join('')}
    </div>`;
  return `
  <div class="resultcard">
    <div class="big">${r.accuracy}%</div>
    <div class="sub">${r.correct} richtig · ${r.wrong} falsch</div>
    ${mistakes}
    <div class="btnrow" style="margin-top:24px;">
      <button class="primarybtn" data-action="vb-open">Neue Runde</button>
      <button class="ghostbtn" data-action="go" data-view="home">Zur Startseite</button>
    </div>
  </div>`;
}