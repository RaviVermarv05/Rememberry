/*
 * context_mode.js — mode 6 for the dashboard. Loaded after app.js and uses its
 * globals (state, go, render, post, playSound, focusAnswerInput). Same rule as
 * app.js: rendering only; clues, answer checking, trials and scoring come from
 * /api/context/* (context_routes.py).
 */
const ctxEsc = (s) => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function ctxClue(q){
  if(q.loading) return `<div class="clue-skeleton" aria-label="Hinweis wird erstellt"><i></i><i></i><i></i></div>`;
  if(!q.hintOk) return `<p class="clue">Der Hinweis konnte nicht erstellt werden.</p>`;
  return `<p class="clue">${ctxEsc(q.hint).replace(/_{3,}/g, '<span class="blank"></span>')}</p>`;
}

function viewQuizContext(){
  const q = state.quiz, fb = q.feedback;
  const { completed, total } = q.progress || { completed: 0, total: 1 };
  let action = '', tools = '', feedback = '';

  if(!q.loading && !q.hintOk){
    action = `<div class="btnrow"><button class="ghostbtn" data-action="ctx-retry">Erneut versuchen</button>
              <button class="ghostbtn" data-action="ctx-skip">Wort überspringen</button></div>`;
  } else if(!q.loading && !q.locked){
    action = `<div class="answerrow"><input id="ans" type="text" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="Deutsches Wort …"><button data-action="submit-answer">Prüfen</button></div>
              <div class="attemptsline">Versuch ${q.wrong + 1} von ${q.trials}</div>`;
    tools = `<div class="cluetools"><button class="backlink" data-action="ctx-retry">Anderer Hinweis</button><button class="backlink" data-action="ctx-giveup">Ich weiß es nicht</button></div>`;
  }
  if(fb){
    const word = fb.word ? `<p class="revealword">${ctxEsc(fb.word)}<small>${ctxEsc(fb.english)}</small></p>` : '';
    feedback = `<div class="feedback ${fb.kind}"><div class="msg">${ctxEsc(fb.message)}</div>${word}</div>
      <div class="continuewrap ${q.locked ? 'show' : ''}"><button class="primarybtn" id="cont" data-action="continue-round">Nächstes Wort</button></div>`;
  }
  return `
  <div class="crumbrow"><button class="backlink" data-action="go" data-view="home">← Start</button></div>
  <p class="tag" style="margin-top:-6px;">${modeLabel()}</p>
  <div class="progresswrap"><div class="progresstrack"><div class="progressfill" style="width:${Math.round(completed / total * 100)}%"></div></div>
    <span class="scorepill">${completed} / ${total}</span></div>
  <div class="flashcard">
    <div class="kicker">Welches deutsche Wort wird beschrieben?</div>
    ${ctxClue(q)}${action}${tools}${feedback}
  </div>`;
}

function ctxFocus(){
  const done = document.getElementById('cont');
  if(done && state.quiz.locked) done.focus(); else focusAnswerInput();
}

async function ctxNext(retry){
  go('quiz', { quiz: Object.assign({}, state.quiz, { loading: true, feedback: null, locked: false }) });
  let d;
  try{ d = await post('/api/context/next', { session_id: state.sessionId, retry: !!retry }); }
  catch(e){ d = { hint_ok: false, hint: null, progress: state.quiz.progress, wrong: 0, trials: 1 }; }
  if(d.done){ go('results', { result: d }); return; }
  go('quiz', { quiz: { loading: false, hint: d.hint, hintOk: d.hint_ok, progress: d.progress,
                       wrong: d.wrong, trials: d.trials, feedback: null, locked: false } });
  ctxFocus();
}

async function ctxSubmit(){
  const q = state.quiz, input = document.getElementById('ans');
  if(state.answerInFlight || !input || q.locked) return;
  state.answerInFlight = true;
  const answer = input.value; input.value = '';
  try{
    const d = await post('/api/context/answer', { session_id: state.sessionId, answer });
    if(d.result === 'duplicate'){ state.answerInFlight = false; return ctxNext(); }
    playSound(d.result === 'correct' ? 'correct' : 'wrong');
    if(d.result === 'wrong') q.wrong = d.wrong;
    q.feedback = { kind: d.result, message: d.message, word: d.word, english: d.english };
    q.locked = d.result !== 'wrong';
  }catch(e){ q.feedback = { kind: 'wrong', message: e.message }; }
  finally{ state.answerInFlight = false; }
  render(); ctxFocus();
}

async function ctxFinish(kind){
  try{
    const d = await post('/api/context/finish', { session_id: state.sessionId, kind });
    if(kind === 'skip') return ctxNext();
    playSound('wrong');
    state.quiz.feedback = { kind: 'revealed', message: d.message, word: d.word, english: d.english };
    state.quiz.locked = true;
  }catch(e){ state.quiz.feedback = { kind: 'wrong', message: e.message }; }
  render(); ctxFocus();
}

function viewContextResults(){
  const r = state.result;
  const missed = r.missed.length ? `
    <div class="practicelist"><h4>Zum Wiederholen</h4>
      ${r.missed.map(m => `<div class="row missedrow"><span>${ctxEsc(m.de)}</span><span>${ctxEsc(m.en)}</span></div>`).join('')}
    </div>` : '';
  return `
  <div class="resultcard">
    <div class="big">${r.rate}%</div>
    <div class="sub">${r.correct} von ${r.total} richtig · ${r.first_try} im ersten Versuch${r.skipped ? ` · ${r.skipped} übersprungen` : ''}</div>
    ${missed}
  </div>
  <div class="btnrow" style="margin-top:16px">
    <button class="primarybtn" data-action="start-flow" data-mode="context">Neue Runde</button>
    <button class="ghostbtn" data-action="go" data-view="home">Zur Übersicht</button>
  </div>`;
}