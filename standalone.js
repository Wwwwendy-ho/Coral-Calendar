/* Coral Calendar on GitHub Pages.
 *
 * Inside Claude, the calendar saves plans, results and logs to the artifact's online database
 * through window.claude.use(...). That doesn't exist on GitHub Pages, so this file provides the
 * same small interface and saves everything in this browser (localStorage) instead.
 *
 * - Nothing is shared between devices, and nothing typed here goes back to the Claude version.
 * - Clearing website data in the browser's settings erases what was saved here.
 * - Claude-only features (AI summaries, chart explanations, note tidying) say they aren't available.
 * - Inside Claude (window.claude already exists) this file does nothing.
 */
(function () {
  if (window.claude) return;
  window.__standalone = true;

  // Start in the sunlit (light) look, as the Claude version is set up. Without a saved choice the page
  // follows the device's dark mode. Light mode / Dark mode in the More menu still switches it.
  try { if (localStorage.getItem('tide-theme') === null) localStorage.setItem('tide-theme', 'light'); } catch (e) {}

  // Same prefix as the earlier GitHub version, so anything already saved on a device carries over.
  var LS = 'tide-db:';
  var docSubs = {}, colSubs = {};

  function get(p) {
    try { var v = localStorage.getItem(LS + p); return v ? JSON.parse(v) : undefined; }
    catch (e) { return undefined; }
  }
  function put(p, d) {
    try { localStorage.setItem(LS + p, JSON.stringify(d)); }
    catch (e) { console.error('[Coral Calendar] could not save in this browser', e); throw e; }
  }
  function drop(p) { try { localStorage.removeItem(LS + p); } catch (e) {} }
  function parent(p) { return p.slice(0, p.lastIndexOf('/')); }

  // Lesson plans and schedule settings copied from the Claude version (settings-seed.js). A device
  // takes each one when it doesn't have it, still has the copy it was last given, or had it from the
  // earlier GitHub version; a change made on this device is kept. Her records are never included.
  (function applySeed() {
    var seed = window.TIDE_SEED;
    if (!seed || !seed.docs) return;
    var META = LS + '__seed';
    var meta = {};
    try { meta = JSON.parse(localStorage.getItem(META) || '{}'); } catch (e) {}
    if (meta.version === seed.version) return;
    var given = meta.docs || {};
    var next = {};
    Object.keys(seed.docs).forEach(function (p) {
      var cur = get(p), s = seed.docs[p], key = JSON.stringify(s);
      var untouched = cur === undefined || given[p] === undefined || JSON.stringify(cur) === given[p];
      if (untouched) {
        var d = JSON.parse(key);
        if (cur && cur.consent && p === 'config/main') d.consent = cur.consent; // keep this device's record
        try { put(p, d); } catch (e) { return; }
        next[p] = JSON.stringify(d);
      } else {
        next[p] = given[p];
      }
    });
    try { localStorage.setItem(META, JSON.stringify({ version: seed.version, docs: next })); } catch (e) {}
  })();

  function docSnap(p) {
    var v = get(p);
    return { id: p.slice(p.lastIndexOf('/') + 1), exists: v !== undefined, data: function () { return v; } };
  }
  function colSnap(c) {
    var docs = [], pre = LS + c + '/';
    try {
      for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (k && k.indexOf(pre) === 0) {
          var id = k.slice(pre.length);
          if (id.indexOf('/') < 0) docs.push(docSnap(c + '/' + id));
        }
      }
    } catch (e) {}
    return { docs: docs, size: docs.length, empty: !docs.length, forEach: function (f) { docs.forEach(f); } };
  }
  function changed(p) {
    (docSubs[p] || []).forEach(function (f) { f(docSnap(p)); });
    var c = parent(p);
    (colSubs[c] || []).forEach(function (f) { f(colSnap(c)); });
  }
  function listen(map, key, cb, snap) {
    (map[key] = map[key] || []).push(cb);
    setTimeout(function () { cb(snap()); }, 0);
    return function () { map[key] = (map[key] || []).filter(function (x) { return x !== cb; }); };
  }

  var db = {
    doc: function (p) {
      return {
        id: p.slice(p.lastIndexOf('/') + 1),
        get: function () { return Promise.resolve(docSnap(p)); },
        set: function (d) { put(p, d); changed(p); return Promise.resolve(); },
        update: function (d) {
          var cur = get(p);
          if (cur === undefined) return Promise.reject(new Error('No document to update: ' + p));
          var next = Object.assign({}, cur);
          Object.keys(d).forEach(function (k) { next[k] = d[k]; });
          put(p, next); changed(p); return Promise.resolve();
        },
        delete: function () { drop(p); changed(p); return Promise.resolve(); },
        onSnapshot: function (cb) { return listen(docSubs, p, cb, function () { return docSnap(p); }); }
      };
    },
    collection: function (c) {
      return {
        get: function () { return Promise.resolve(colSnap(c)); },
        onSnapshot: function (cb) { return listen(colSubs, c, cb, function () { return colSnap(c); }); }
      };
    }
  };

  var downloads = {
    save: function (o) {
      var blob = o.data instanceof Blob ? o.data : new Blob([o.data], { type: 'application/pdf' });
      var u = URL.createObjectURL(blob), a = document.createElement('a');
      a.href = u; a.download = o.filename; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(u); }, 60000);
      return Promise.resolve();
    }
  };

  // Whoever opens this copy is working on their own device's data, so they can edit it.
  var user = {
    isOwner: function () { return Promise.resolve(true); },
    canEdit: function () { return Promise.resolve(true); }
  };

  window.claude = {
    use: function (n) {
      return Promise.resolve(n === 'db' ? db : n === 'downloads' ? downloads : n === 'user' ? user : null);
    }
  };
})();
