/*
 * dev_reload.js — development live-reload. Replaces the small inline poller that
 * used to sit in index.html. Loaded last; it only reads/refreshes state, it does
 * not change any mode's logic. Harmless outside debug mode (the stamp endpoint
 * answers 404 and the polling stops).
 *
 * Polls /api/dev/stamp once a second and reacts to two kinds of change:
 *
 *  1. The server restarted (you saved a .py file, e.g. Data/word_list.py).
 *     -> NO page reload. The data behind the screen you are looking at is fetched
 *        again and that screen is redrawn in place (same view, same scroll position):
 *        "Wörter durchsehen" list, "Verben durchsehen" table, Wortsuche result,
 *        verb setup, chapter counts on the start page / chapter picker.
 *        Screens that depend on a running server session (quiz round, verb practice,
 *        history) cannot survive a restart; they are left as they are and a short
 *        notice is shown instead of sending you away.
 *
 *  2. A file in webapp/static changed (.js / .css / .html).
 *     -> The code itself changed, so the page has to reload. Before it does, the
 *        screen you were on is remembered (sessionStorage) and opened again after
 *        the reload, with its data re-fetched, instead of dropping you on the start page.
 */
(function(){
  const KEY = 'rememberry-dev-nav';
  const RESTORABLE = ['review-chapter', 'review-range', 'review-list', 'search', 'vb-setup', 'vb-review', 'data-editor'];
  const REDRAW = ['home', 'chapters', 'review-list', 'search', 'vb-setup', 'vb-review'];
  const SESSION_VIEW = /^(quiz|history|vb-practice|ctx|context)/;
  const NAV_KEYS = ['reviewChapter', 'reviewRangeMode', 'reviewStart', 'reviewEnd',
                    'reviewResult', 'searchQuery', 'searchResult', 'vb', 'vbReview', 'de'];

  /* ---------- small notice ---------- */
  function toast(text){
    let el = document.getElementById('dev-reload-toast');
    if(!el){
      el = document.createElement('div');
      el.id = 'dev-reload-toast';
      el.style.cssText = 'position:fixed;left:50%;bottom:22px;transform:translateX(-50%);max-width:90vw;' +
        'padding:9px 16px;border-radius:999px;background:#333;color:#fff;font:13px system-ui,sans-serif;' +
        'z-index:99999;opacity:0;transition:opacity .25s;pointer-events:none;text-align:center;';
      document.body.appendChild(el);
    }
    el.textContent = text;
    el.style.opacity = '0.95';
    clearTimeout(el._t);
    el._t = setTimeout(() => { el.style.opacity = '0'; }, 4000);
  }

  /* ---------- re-fetch the data behind the current screen and redraw it ---------- */
  async function refreshData(){
    const view = state.view;
    const y = window.scrollY;
    try{
      const patch = {};
      const ch = await get('/api/chapters');
      patch.chapters = ch.chapters || ch;
      if(ch.stats) patch.stats = ch.stats;          // totals line on the home screen

      if(view === 'review-list' && state.reviewResult){
        const r0 = state.reviewResult;
        patch.reviewResult = await post('/api/review', {
          chapter: r0.chapter,
          start: r0.range ? r0.range.start : null,
          end: r0.range ? r0.range.end : null
        });
      }else if(view === 'vb-review'){
        const v = state.vb || {};
        const custom = v.rangeMode === 'custom';
        patch.vbReview = await post('/api/verbmode/review', {
          start: custom ? v.start : null,
          end: custom ? v.end : null
        });
      }else if(view === 'vb-setup' && state.vb){
        const { verbs } = await get('/api/verbs');
        state.vb.total = verbs.length;
      }else if(view === 'search' && state.searchResult && !state.searchResult.online && state.searchQuery){
        patch.searchResult = await post('/api/search', { query: state.searchQuery });
      }

      if(state.view !== view) return;               // user moved on while we were fetching
      state = Object.assign({}, state, patch);
      if(REDRAW.includes(view)){
        render();
        window.scrollTo(0, y);
        toast('Daten aktualisiert');
      }
    }catch(e){
      console.warn('[dev-reload] refresh failed:', e);
      toast('Aktualisierung nicht möglich: ' + e.message);
    }
  }

  /* ---------- remember / reopen the current screen across a full reload ---------- */
  function saveNav(){
    if(!RESTORABLE.includes(state.view)) return;
    const snap = { view: state.view, y: window.scrollY };
    NAV_KEYS.forEach(k => { if(state[k] !== undefined) snap[k] = state[k]; });
    try{ sessionStorage.setItem(KEY, JSON.stringify(snap)); }catch(e){}
  }

  function restoreNav(){
    let snap = null;
    try{ snap = JSON.parse(sessionStorage.getItem(KEY) || 'null'); sessionStorage.removeItem(KEY); }catch(e){}
    if(!snap || !RESTORABLE.includes(snap.view)) return;
    let tries = 0;
    const wait = setInterval(() => {
      tries++;
      if(state && state.view === 'home' && state.chapters){        // app.js finished its boot
        clearInterval(wait);
        const extras = {};
        NAV_KEYS.forEach(k => { if(snap[k] !== undefined) extras[k] = snap[k]; });
        go(snap.view, extras);
        if(snap.view === 'data-editor' && typeof deLoad === 'function'){ deLoad(); return; }   // editor reads the files itself
        refreshData().then(() => window.scrollTo(0, snap.y || 0));
      }else if(tries > 100){ clearInterval(wait); }                 // give up after ~5 s
    }, 50);
  }

  /* ---------- poll ---------- */
  let last = null;
  async function poll(){
    try{
      const r = await fetch('/api/dev/stamp', { cache: 'no-store' });
      if(r.status === 404) return;                                  // not in debug mode: stop
      const s = await r.json();
      if(last !== null){
        if(s.static !== last.static){                               // front-end code changed
          saveNav();
          setTimeout(() => location.reload(), 150);
          return;
        }
        if(s.boot !== last.boot){                                   // server restarted (python / data edit)
          last = s;
          if(SESSION_VIEW.test(state.view)){
            toast('Server neu gestartet – laufende Runde wurde zurückgesetzt');
          }else{
            await refreshData();
          }
        }
      }
      last = s;
    }catch(e){ /* server restarting: keep trying */ }
    setTimeout(poll, 1000);
  }

  restoreNav();
  poll();
})();