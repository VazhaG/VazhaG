// SPEC-0004 REQ-006: the page's look before its first drawing, so it never flashes in the other one — the visitor's
// choice if this phone keeps one, else the phone's own light or dark setting. A small script from our own site, run in
// <head> (the page's CSP stays as it is); the main script (js/app.js) runs the switch afterwards.
(() => {
  let kept = null;
  try {
    kept = localStorage.getItem('fuel-map.theme');
  } catch {
    // a private window or a blocked storage: the phone's setting
  }
  const dark = kept === 'dark' || (kept !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
})();
