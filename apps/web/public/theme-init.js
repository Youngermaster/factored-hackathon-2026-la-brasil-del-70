// Sets <html data-theme> before first paint so the page never flashes the wrong theme. It is an external classic
// script (no inline code) so the strict CSP holds. It reads the same preference record as
// src/shared/lib/preferences.ts; the theme is a per-viewer convenience, never session data.
(function () {
  var theme = 'system';
  try {
    var stored = JSON.parse(window.localStorage.getItem('bank-agent.preferences.v1') || '{}');
    if (stored && (stored.theme === 'light' || stored.theme === 'dark')) {
      theme = stored.theme;
    }
  } catch (error) {
    theme = 'system';
  }
  if (theme === 'system') {
    var dark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    theme = dark ? 'dark' : 'light';
  }
  document.documentElement.setAttribute('data-theme', theme);
})();
