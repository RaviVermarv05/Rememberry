/*
 * pagination.js — page ribbon (30 entries per page + "Alle anzeigen") for the two
 * long list views:
 *   - Verben durchsehen        (view 'vb-review',   state.vbReview.entries)
 *   - Wörter durchsehen        (view 'review-list', state.reviewResult.entries)
 *
 * Additive only. app.js, verbs_mode.js and the Flask API are NOT edited. This file
 * wraps viewReviewList() and viewVbReview(): it hands the ORIGINAL view function a
 * sliced copy of the entries (original numbering e.no is kept), then inserts the
 * ribbon just above the "Fertig" button. If a list has 30 entries or fewer, the
 * original output is returned untouched (no ribbon).
 * Load after app.js and verbs_mode.js.
 */
const PG_SIZE = 30;

/* one pagination state per list; resets automatically whenever a new result is loaded */
const pgStore = {};
function pgGet(key, ref){
  let s = pgStore[key];
  if(!s || s.ref !== ref){ s = pgStore[key] = { ref, page: 1, all: false }; }
  return s;
}

function pgRibbon(key, s, total){
  const pages = Math.ceil(total / PG_SIZE);
  const btn = (label, attrs, cls='') =>
    `<button type="button" class="${cls}" data-action="pg-${attrs.act}" data-key="${key}"${attrs.p ? ` data-page="${attrs.p}"` : ''}${attrs.dis ? ' disabled' : ''}>${label}</button>`;

  if(s.all){
    return `<div class="pgribbon">
      ${btn('Seiten anzeigen', {act:'paged'}, 'pgall')}
      <div class="pginfo">Alle ${total} Einträge werden angezeigt</div>
    </div>`;
  }

  // page numbers: always first + last, window around the current page, "…" for gaps
  const nums = [];
  for(let p = 1; p <= pages; p++){
    if(p === 1 || p === pages || Math.abs(p - s.page) <= 1) nums.push(p);
    else if(nums[nums.length - 1] !== '…') nums.push('…');
  }
  const numHtml = nums.map(p => p === '…'
    ? '<span class="pgdots">…</span>'
    : btn(p, {act:'page', p}, p === s.page ? 'active' : '')).join('');

  const from = (s.page - 1) * PG_SIZE + 1, to = Math.min(s.page * PG_SIZE, total);
  return `<div class="pgribbon">
    ${btn('‹', {act:'page', p:s.page - 1, dis:s.page <= 1})}
    ${numHtml}
    ${btn('›', {act:'page', p:s.page + 1, dis:s.page >= pages})}
    <span class="pgsep"></span>
    ${btn('Alle anzeigen', {act:'all'}, 'pgall')}
    <div class="pginfo">${from}–${to} von ${total}</div>
  </div>`;
}

/* run the original view with a sliced entries list, then add the ribbon.
   persist=true (Wörter durchsehen): the sliced result STAYS in state while the page is shown, so
   other add-ons that read state.reviewResult.entries after rendering (the AI explain mode finds the
   rows by count and opens entries by row index) see exactly what is on screen. The full list is kept
   on the result as __pgFull and is re-sliced on every render. */
function pgWrap(origFn, key, getResult, setResult, persist){
  return function(){
    const cur = getResult();
    const full = (cur && cur.__pgFull) || cur;
    if(!full || !Array.isArray(full.entries) || full.entries.length <= PG_SIZE) return origFn();

    const s = pgGet(key, full);
    const pages = Math.ceil(full.entries.length / PG_SIZE);
    if(s.page > pages) s.page = pages;
    if(s.page < 1) s.page = 1;

    const shown = s.all ? full.entries : full.entries.slice((s.page - 1) * PG_SIZE, s.page * PG_SIZE);
    const sliced = Object.assign({}, full, { entries: shown });   // everything else (total, range, chapter) unchanged
    if(persist) sliced.__pgFull = full;
    setResult(sliced);
    let html;
    try{ html = origFn(); }
    finally{ if(!persist) setResult(full); }                      // verbs: restore the full result right away

    const ribbon = pgRibbon(key, s, full.entries.length);
    const at = html.lastIndexOf('<button class="ghostbtn"');      // the "Fertig" button
    return at === -1 ? html + ribbon : html.slice(0, at) + ribbon + html.slice(at);
  };
}

/* Wörter durchsehen */
const _pgOrigReviewList = viewReviewList;
viewReviewList = pgWrap(_pgOrigReviewList, 'words',
  () => state.reviewResult, (v) => { state.reviewResult = v; }, true);

/* Verben durchsehen */
const _pgOrigVbReview = viewVbReview;
viewVbReview = pgWrap(_pgOrigVbReview, 'verbs',
  () => state.vbReview, (v) => { state.vbReview = v; });

/* ribbon clicks (document-level delegation, same pattern as verbs_mode.js) */
document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-action^="pg-"]');
  if(!el || el.disabled) return;
  const key = el.dataset.key;
  const r = key === 'verbs' ? state.vbReview : state.reviewResult;
  if(!r) return;
  const s = pgGet(key, r.__pgFull || r);
  const a = el.dataset.action;
  if(a === 'pg-page'){ s.page = parseInt(el.dataset.page, 10) || 1; s.all = false; }
  else if(a === 'pg-all'){ s.all = true; }
  else if(a === 'pg-paged'){ s.all = false; }
  else return;
  render();
  window.scrollTo({ top: 0, behavior: 'smooth' });
});