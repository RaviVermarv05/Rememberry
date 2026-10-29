/*
 * explain_mode.js — click a word pair in "Wörter durchsehen" and get a Groq explanation:
 * meaning in context, how the words differ, examples, memory tricks, a summary and a
 * multiple-choice quiz. Loaded after app.js and uses its globals (state, go, render, body,
 * playSound). Rendering only: the prompt, the Groq call, validation and
 * caching are in /api/explain (explain_routes.py).
 *
 * app.js is NOT edited. Same two small hooks as verbs_mode.js:
 *   1. it wraps render() so that, after the review list is drawn, every pair row is made
 *      clickable (data-action="ex-open") — rows are found by count, not by exact markup, so it
 *      keeps working if the list is rebuilt as a table/list — and body() to render its own
 *      view ("explain"); everything else falls through unchanged
 *   2. it listens for clicks on data-action="ex-…" elements (app.js ignores unknown actions)
 */
(function(){
  if(typeof render !== 'function' || typeof body !== 'function' || typeof go !== 'function'){
    console.warn('[explain_mode] not started: app.js must be loaded first and define render(), body() and go().');
    return;
  }

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  /* escape first, then allow only **bold** and line breaks */
  const fmt = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>');
  const LETTERS = 'ABCDEF';

  const cache = new Map();   // key -> explanation data (this page load; the server keeps a file cache too)
  let savedScroll = 0;       // where the list was, so "← Wörter" puts you back

  /* The quiz switch above the list. ON = a quiz is requested together with the explanation;
     OFF = no quiz is requested at all (fewer tokens). Remembered between visits in this browser. */
  let quizOn = true;
  try{ quizOn = localStorage.getItem('explain_quiz_on') !== '0'; }catch(_){}
  function setQuizOn(v){ quizOn = !!v; try{ localStorage.setItem('explain_quiz_on', quizOn ? '1' : '0'); }catch(_){} }
  /* is the quiz wanted for THIS pair? (switch on, or the "Quiz hinzufügen" button was pressed for it) */
  const wantQuiz = (ex) => quizOn || !!(ex && ex.quizRequested);
  const barText = () => quizOn
    ? 'An: zum Wortpaar wird auch ein Quiz erstellt.'
    : 'Aus: nur die Erklärung, kein Quiz. Das spart Tokens.';

  const style = document.createElement('style');
  style.textContent = `
  .ex-bar{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:10px 14px;margin:0 0 10px;background:var(--card);border:1px solid var(--paper-line);border-radius:var(--radius);}
  .ex-bar .setdesc{max-width:none;}
  .ex-hint{font-size:12.5px;color:var(--ink-soft);margin:0 0 10px;}
  .ex-clickable{cursor:pointer;transition:background .12s;}
  .reviewrow.ex-clickable{border-radius:6px;}
  .ex-clickable:hover,.ex-clickable:focus-visible{background:var(--gold-soft);outline:none;}
  .reviewrow.ex-clickable::after{content:'✨';margin-left:auto;padding-left:8px;opacity:.45;flex:none;}
  .reviewrow.ex-clickable:hover::after{opacity:1;}
  .ex-title{font-size:21px;margin:0 0 4px;line-height:1.3;}
  .ex-gloss{color:var(--ink-soft);font-size:14px;margin-bottom:14px;}
  .ex-chips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 16px;}
  .ex-chip{background:var(--card);border:1.5px solid var(--paper-line);color:var(--ink);border-radius:999px;padding:6px 13px;font-size:13px;}
  .ex-chip:hover{border-color:var(--navy);color:var(--navy);}
  .ex-overview{font-size:14.5px;line-height:1.55;margin:0 0 18px;}
  .ex-card{background:var(--card);border:1px solid var(--paper-line);border-left:4px solid var(--navy);border-radius:var(--radius);padding:18px;box-shadow:var(--shadow);margin-bottom:18px;scroll-margin-top:12px;}
  .ex-card h3{font-size:19px;margin:0 0 12px;display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px;}
  .ex-card h3 .ex-en{font-family:var(--sans);font-weight:400;font-size:13.5px;color:var(--ink-soft);}
  .ex-sec{margin-top:13px;font-size:14px;line-height:1.55;}
  .ex-lab{font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:var(--ink-soft);font-weight:700;margin-bottom:3px;}
  .ex-sec ul{margin:0;padding-left:19px;}
  .ex-sec li{margin:3px 0;}
  .ex-ex{display:block;}
  .ex-ex .de{font-weight:600;display:block;}
  .ex-ex .en{color:var(--ink-soft);display:block;font-size:13px;}
  .ex-trick{margin-top:14px;padding:10px 13px;border-radius:8px;background:var(--gold-soft);font-size:14px;line-height:1.5;}
  .ex-block{background:var(--card);border:1px solid var(--paper-line);border-radius:var(--radius);padding:18px;box-shadow:var(--shadow);margin-bottom:18px;scroll-margin-top:12px;}
  .ex-block h3{font-size:17px;margin:0 0 10px;}
  .ex-sum{width:100%;border-collapse:collapse;font-size:14px;margin-bottom:6px;}
  .ex-sum td{padding:8px 6px;border-bottom:1px solid var(--paper-line);vertical-align:top;}
  .ex-sum td:first-child{font-weight:600;white-space:nowrap;padding-right:14px;}
  .ex-q{padding:14px 0;border-top:1px solid var(--paper-line);}
  .ex-q:first-of-type{border-top:none;}
  .ex-qn{font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:var(--ink-soft);font-weight:700;}
  .ex-qtext{font-size:16px;line-height:1.5;margin:4px 0 10px;font-family:var(--serif);}
  .ex-opts{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
  @media (max-width:520px){.ex-opts{grid-template-columns:1fr;}}
  .ex-opt{display:flex;align-items:baseline;gap:9px;text-align:left;background:var(--paper);border:1.5px solid var(--paper-line);color:var(--ink);border-radius:8px;padding:10px 12px;font-size:14.5px;}
  .ex-opt .ex-letter{font-weight:700;color:var(--ink-soft);flex:none;}
  .ex-opt:not(:disabled):hover{border-color:var(--navy);}
  .ex-opt:disabled{cursor:default;}
  .ex-opt.right{border-color:var(--green);background:var(--green-soft);}
  .ex-opt.wrong{border-color:var(--berry);background:var(--berry-soft);}
  .ex-res{margin-top:10px;font-size:14px;line-height:1.5;}
  .ex-res .verdict{font-weight:700;}
  .ex-res .verdict.ok{color:var(--green);} .ex-res .verdict.bad{color:var(--berry);}
  .ex-res .tr{color:var(--ink-soft);font-size:13px;font-style:italic;margin:3px 0;}
  .ex-score{text-align:center;font-family:var(--serif);font-size:18px;padding:12px 0 4px;}
  .ex-foot{display:flex;gap:10px;margin-top:6px;}
  .ex-foot .primarybtn,.ex-foot .ghostbtn{flex:1;width:auto;}
  .ex-skel{display:flex;flex-direction:column;gap:12px;padding:8px 0 4px;}
  .ex-skel i{display:block;height:15px;border-radius:4px;background:linear-gradient(90deg,var(--paper-line) 25%,var(--gold-soft) 50%,var(--paper-line) 75%);background-size:200% 100%;animation:exshimmer 1.4s linear infinite;}
  .ex-skel i:nth-child(3n+2){width:88%;} .ex-skel i:nth-child(3n){width:55%;}
  @keyframes exshimmer{to{background-position:-200% 0;}}
  .ex-err{color:var(--berry);font-size:14.5px;line-height:1.5;margin-bottom:12px;}
  `;
  document.head.appendChild(style);
  console.info('[explain_mode] loaded');

  /* ---------------- hook into the existing dashboard ---------------- */
  /* After the review list is drawn, find the pair rows and make them clickable. The rows are
     found by COUNT (selector whose number of matches equals the number of pairs), so the exact
     markup of the list does not matter. */
  const ROW_SELECTORS = ['.reviewrow', '.reviewlist > *', 'table tbody tr', 'ul > li', 'ol > li'];
  let warnedNoRows = false;
  function decorateReviewList(){
    const r = state.reviewResult;
    const app = document.getElementById('app');
    if(!r || !r.entries || !app) return;
    let rows = null;
    for(const sel of ROW_SELECTORS){
      const found = app.querySelectorAll(sel);
      if(found.length === r.entries.length){ rows = Array.prototype.slice.call(found); break; }
    }
    if(!rows){
      if(!warnedNoRows){ console.warn('[explain_mode] could not find the ' + r.entries.length + ' pair rows in the review list; tried: ' + ROW_SELECTORS.join(', ')); warnedNoRows = true; }
      return;
    }
    rows.forEach((el, i) => {
      el.dataset.action = 'ex-open'; el.dataset.idx = String(i);
      el.tabIndex = 0; el.setAttribute('role', 'button'); el.title = 'KI-Erklärung anzeigen';
      el.classList.add('ex-clickable');
    });
    const holder = rows[0].closest('.reviewlist, table, ul, ol') || rows[0].parentElement;
    if(holder && holder.parentNode && !app.querySelector('.ex-bar')){
      const bar = document.createElement('div');
      bar.className = 'ex-bar';
      bar.innerHTML = `<div><div class="setlabel">✍️ Quiz mit erstellen</div><div class="setdesc" data-ex-bartext>${esc(barText())}</div></div>
        <button class="switch ${quizOn ? 'on' : ''}" role="switch" aria-checked="${quizOn}" aria-label="Quiz mit erstellen" data-action="ex-quiz-toggle"><span></span></button>`;
      holder.parentNode.insertBefore(bar, holder);
    }
    if(!app.querySelector('.ex-hint')){
      if(holder && holder.parentNode){
        const p = document.createElement('p');
        p.className = 'ex-hint';
        p.textContent = '✨ Tippe auf ein Wortpaar: AI erklärt dir Bedeutung im Kontext, Unterschiede, Beispiele und gibt dir ein Quiz.';
        holder.parentNode.insertBefore(p, holder);
      }
    }
  }

  const _origRender = render;
  render = function(){
    const out = _origRender.apply(this, arguments);
    if(state.view === 'review-list') decorateReviewList();
    return out;
  };

  const _origBody = body;
  body = function(){
    return state.view === 'explain' ? viewExplain() : _origBody();
  };

  document.addEventListener('click', (e) => {
    const el = e.target && e.target.closest ? e.target.closest('[data-action^="ex-"]') : null;
    if(!el) return;
    const a = el.dataset.action;
    if(a === 'ex-open') openPair(el);
    else if(a === 'ex-back') back();
    else if(a === 'ex-quiz-toggle'){
      setQuizOn(!quizOn);                                  // only the switch is updated: no re-render, the list stays where it is
      el.classList.toggle('on', quizOn); el.setAttribute('aria-checked', String(quizOn));
      const t = document.querySelector('[data-ex-bartext]'); if(t) t.textContent = barText();
    }
    else if(a === 'ex-quiz-show'){
      const ex = state.explain; if(!ex || !ex.data) return;
      ex.quizRequested = true;
      if(ex.data.quiz.length) keepScroll(); else fetchQuiz();
    }
    else if(a === 'ex-quiz-retry') fetchQuiz();
    else if(a === 'ex-regen') fetchExplain(true);
    else if(a === 'ex-retry') fetchExplain(false);
    else if(a === 'ex-answer') answer(parseInt(el.dataset.q, 10), parseInt(el.dataset.o, 10));
    else if(a === 'ex-quiz-reset'){ state.explain.answers = {}; keepScroll(); }
    else if(a === 'ex-jump'){ const t = document.getElementById(el.dataset.target); if(t) t.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    else if(a === 'ex-settings') go('settings', { draft: Object.assign({}, state.settings) });
  });

  document.addEventListener('keydown', (e) => {
    const t = e.target;
    if((e.key === 'Enter' || e.key === ' ') && t && t.matches && t.matches('[data-action="ex-open"]')){
      e.preventDefault();
      openPair(t);
    }
  });

  /* ---------------- open / fetch ---------------- */
  function openPair(rowEl){
    const r = state.reviewResult;
    if(!r || !r.entries) return;
    const idx = parseInt(rowEl.dataset.idx, 10);
    const entry = r.entries[idx];
    if(!entry) return;

    savedScroll = window.scrollY;
    const words = entry.german.split(', ');          // no glossary word contains a comma
    const key = words.map(w => w.toLowerCase()).join('|');
    const ex = {
      key, no: entry.no, chapter: r.chapter, german: entry.german, english: entry.english, words,
      answers: {}, error: null, data: cache.get(key) || null, loading: !cache.has(key),
      quizRequested: false, quizLoading: false, quizError: null
    };
    go('explain', { explain: ex });
    window.scrollTo(0, 0);
    if(ex.loading) fetchExplain(false);
    else if(quizOn && !ex.data.quiz.length) fetchQuiz();      // explanation is saved, only the quiz is missing
  }

  async function fetchExplain(refresh){
    const ex = state.explain;
    if(!ex) return;
    const key = ex.key;
    ex.loading = true; ex.error = null; ex.quizError = null;
    if(refresh){ ex.data = null; ex.answers = {}; cache.delete(key); }
    if(state.view === 'explain') render();
    try{
      const res = await fetch('/api/explain', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chapter: ex.chapter, german: ex.words, refresh: !!refresh, quiz: wantQuiz(ex) })
      });
      let payload = {};
      try{ payload = await res.json(); }catch(_){}
      if(!res.ok) throw Object.assign(new Error(payload.error || ('API error ' + res.status)), { code: payload.code });
      cache.set(key, payload.data);
      ex.data = payload.data; ex.answers = {}; ex.loading = false;
      if(payload.quiz_error) ex.quizError = payload.quiz_error;          // explanation is fine, only the quiz failed
      else if(wantQuiz(ex) && !ex.data.quiz.length) ex.quizError = { message: 'Das Quiz konnte nicht erstellt werden.' };
    }catch(err){
      ex.loading = false; ex.error = { message: err.message, code: err.code };
    }
    if(state.view === 'explain' && state.explain && state.explain.key === key) render();   // user may have left meanwhile
  }

  /* The explanation is already saved but has no quiz: ask for the quiz only (a small request). */
  async function fetchQuiz(){
    const ex = state.explain;
    if(!ex || !ex.data) return;
    ex.quizLoading = true; ex.quizError = null;
    if(state.view === 'explain') render();
    try{
      const res = await fetch('/api/explain', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chapter: ex.chapter, german: ex.words, quiz: true })
      });
      let payload = {};
      try{ payload = await res.json(); }catch(_){}
      if(!res.ok) throw Object.assign(new Error(payload.error || ('API error ' + res.status)), { code: payload.code });
      cache.set(ex.key, payload.data);
      ex.data = payload.data; ex.answers = {};
      if(payload.quiz_error) ex.quizError = payload.quiz_error;
    }catch(err){
      ex.quizError = { message: err.message, code: err.code };
    }
    ex.quizLoading = false;
    if(state.view === 'explain' && state.explain === ex) render();
  }

  function back(){
    go('review-list');
    window.scrollTo(0, savedScroll);
  }

  function keepScroll(){
    const y = window.scrollY;
    render();
    window.scrollTo(0, y);
  }

  function answer(q, o){
    const ex = state.explain;
    if(!ex || !ex.data || isNaN(q) || isNaN(o) || ex.answers[q] !== undefined) return;
    ex.answers[q] = o;                                // the answer is revealed by the re-render below
    const right = ex.data.quiz[q] && ex.data.quiz[q].answer === o;
    try{ playSound(right ? 'correct' : 'wrong'); }catch(_){}
    keepScroll();
  }

  /* ---------------- view ---------------- */
  const listSec = (label, items) => (items && items.length)
    ? `<div class="ex-sec"><div class="ex-lab">${label}</div><ul>${items.map(i => `<li>${fmt(i)}</li>`).join('')}</ul></div>` : '';
  const textSec = (label, text) => text ? `<div class="ex-sec"><div class="ex-lab">${label}</div>${fmt(text)}</div>` : '';

  function wordCard(w, i){
    const others = (w.other_meanings || []).length
      ? `<div class="ex-sec"><div class="ex-lab">Other meanings</div><ul>${w.other_meanings.map(m =>
          `<li><strong>${esc(m.meaning)}</strong>${m.explanation ? ' — ' + fmt(m.explanation) : ''}</li>`).join('')}</ul></div>` : '';
    const examples = (w.examples || []).length
      ? `<div class="ex-sec"><div class="ex-lab">Examples</div><ul>${w.examples.map(x =>
          `<li><span class="ex-ex"><span class="de">${esc(x.de)}</span>${x.en ? `<span class="en">${esc(x.en)}</span>` : ''}</span></li>`).join('')}</ul></div>` : '';
    return `
    <section class="ex-card" id="exw-${i}">
      <h3><span class="ex-de">${esc(w.german)}</span><span class="ex-en">${esc(w.english)}</span></h3>
      ${textSec('When to use it', w.context)}
      ${others}
      ${textSec('How it differs', w.difference)}
      ${examples}
      ${w.memory_trick ? `<div class="ex-trick">💡 <strong>Memory trick:</strong> ${fmt(w.memory_trick)}</div>` : ''}
      ${listSec('Grammar &amp; collocations', w.grammar)}
      ${listSec('Common mistakes', w.mistakes)}
    </section>`;
  }

  function summaryBlock(d){
    if(!(d.summary && d.summary.length) && !(d.how_to_choose && d.how_to_choose.length)) return '';
    const table = (d.summary || []).length
      ? `<table class="ex-sum"><tbody>${d.summary.map(s => `<tr><td>${esc(s.word)}</td><td>${fmt(s.use_when)}</td></tr>`).join('')}</tbody></table>` : '';
    return `<section class="ex-block" id="ex-sum"><h3>🧠 Memory summary</h3>${table}${listSec('How to choose', d.how_to_choose)}</section>`;
  }

  function quizBlock(ex){
    const quiz = ex.data.quiz || [];
    if(!quiz.length) return '';
    const done = Object.keys(ex.answers).length;
    const score = quiz.filter((q, i) => ex.answers[i] === q.answer).length;
    const items = quiz.map((q, qi) => {
      const picked = ex.answers[qi], answered = picked !== undefined;
      const opts = q.options.map((o, oi) => {
        const cls = answered ? (oi === q.answer ? 'right' : (oi === picked ? 'wrong' : '')) : '';
        return `<button class="ex-opt ${cls}" data-action="ex-answer" data-q="${qi}" data-o="${oi}" ${answered ? 'disabled' : ''}><span class="ex-letter">${LETTERS[oi]}</span><span>${esc(o)}</span></button>`;
      }).join('');
      let res = '';
      if(answered){
        const ok = picked === q.answer;
        res = `<div class="ex-res"><div class="verdict ${ok ? 'ok' : 'bad'}">${ok ? '✅ Richtig!' : `❌ Nicht ganz — richtig ist: ${esc(q.options[q.answer])}`}</div>
          ${q.translation ? `<div class="tr">${esc(q.translation)}</div>` : ''}${q.explanation ? `<div>${fmt(q.explanation)}</div>` : ''}</div>`;
      }
      return `<div class="ex-q"><div class="ex-qn">Frage ${qi + 1} / ${quiz.length}</div><p class="ex-qtext">${fmt(q.question)}</p><div class="ex-opts">${opts}</div>${res}</div>`;
    }).join('');
    const final = done === quiz.length
      ? `<div class="ex-score">Ergebnis: ${score} / ${quiz.length} ${score === quiz.length ? '🎉' : ''}</div>
         <div class="ex-foot"><button class="ghostbtn" data-action="ex-quiz-reset">Quiz wiederholen</button></div>` : '';
    return `<section class="ex-block" id="ex-quiz"><h3>✍️ Practice quiz</h3>
      <p class="ex-overview" style="margin-bottom:6px;color:var(--ink-soft);font-size:13px;">Wähle zuerst deine Antwort — danach siehst du die richtige Lösung und die Erklärung.</p>${items}${final}</section>`;
  }

  /* quiz part of the page: the quiz, its loading/error state, or a button to get it */
  function quizArea(ex){
    const d = ex.data, has = d.quiz.length > 0;
    if(wantQuiz(ex)){
      if(has) return quizBlock(ex);
      if(ex.quizLoading) return `<section class="ex-block" id="ex-quiz"><h3>✍️ Practice quiz</h3>
        <p class="ex-overview" style="margin:0 0 6px;">Das Quiz wird erstellt … (nur das Quiz, die Erklärung bleibt wie sie ist)</p><div class="ex-skel"><i></i><i></i><i></i></div></section>`;
      if(ex.quizError){
        const keyProblem = ex.quizError.code === 'no_key' || ex.quizError.code === 'bad_key';
        return `<section class="ex-block" id="ex-quiz"><h3>✍️ Practice quiz</h3><div class="ex-err">${esc(ex.quizError.message)}</div>
          <div class="ex-foot">${keyProblem
            ? `<button class="primarybtn" data-action="ex-settings">Zu den Einstellungen</button>`
            : `<button class="primarybtn" data-action="ex-quiz-retry">Quiz erneut versuchen</button>`}</div></section>`;
      }
    }
    return `<div class="ex-foot" style="margin:0 0 12px;"><button class="ghostbtn" data-action="ex-quiz-show">${has ? '✍️ Quiz anzeigen' : '✍️ Quiz hinzufügen'}</button></div>`
      + (has ? '' : `<p class="ex-hint" style="margin:-4px 0 14px;text-align:center;">Fragt nur das Quiz bei Groq an, die Erklärung wird nicht neu erstellt.</p>`);
  }

  function viewExplain(){
    const ex = state.explain;
    const head = `
    <div class="crumbrow"><button class="backlink" data-action="ex-back">← Wörter</button></div>
    <p class="tag" style="margin-top:-6px;">✨ ${chLabel(ex.chapter)} · Wortpaar ${ex.no}</p>
    <h2 class="ex-title">${esc(ex.german)}</h2>
    <div class="ex-gloss">${esc(ex.english)}</div>`;

    if(ex.loading){
      return head + `<div class="ex-block"><p class="ex-overview" style="margin:0 0 6px;">🍓 Groq erklärt die Wörter … das dauert etwa ${wantQuiz(ex) ? '10–30' : '5–20'} Sekunden.</p>
        <div class="ex-skel"><i></i><i></i><i></i><i></i><i></i><i></i></div></div>`;
    }
    if(ex.error){
      const keyProblem = ex.error.code === 'no_key' || ex.error.code === 'bad_key';
      return head + `<div class="ex-block"><div class="ex-err">${esc(ex.error.message)}</div>
        <div class="ex-foot">
          ${keyProblem ? `<button class="primarybtn" data-action="ex-settings">Zu den Einstellungen</button>` : `<button class="primarybtn" data-action="ex-retry">Erneut versuchen</button>`}
          <button class="ghostbtn" data-action="ex-back">← Wörter</button>
        </div></div>`;
    }
    const d = ex.data;
    if(!d) return head;
    const chips = d.words.map((w, i) => `<button class="ex-chip" data-action="ex-jump" data-target="exw-${i}">${esc(w.german)}</button>`).join('')
      + (d.summary.length || d.how_to_choose.length ? `<button class="ex-chip" data-action="ex-jump" data-target="ex-sum">🧠 Summary</button>` : '')
      + (wantQuiz(ex) && d.quiz.length ? `<button class="ex-chip" data-action="ex-jump" data-target="ex-quiz">✍️ Quiz</button>` : '');
    return head
      + (d.words.length > 1 || d.summary.length ? `<div class="ex-chips">${chips}</div>` : '')
      + (d.overview ? `<p class="ex-overview">${fmt(d.overview)}</p>` : '')
      + d.words.map(wordCard).join('')
      + summaryBlock(d)
      + quizArea(ex)
      + `<div class="ex-foot">
           <button class="ghostbtn" data-action="ex-regen">🔄 Neu erstellen</button>
           <button class="primarybtn" data-action="ex-back">← Zurück zur Liste</button>
         </div>`;
  }
})();