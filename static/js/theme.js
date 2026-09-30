(function () {
  var STORAGE_KEY = 'theme';
  var media = window.matchMedia('(prefers-color-scheme: dark)');

  // Legacy: retired themes map to their nearest survivor — sky, kosmos,
  // latte, and everforest-light to light (Matcha); kosmos-dark and mocha
  // to dark (Gruvbox). oxford was renamed basic.
  var LEGACY = {
    sky: 'light',
    kosmos: 'light',
    latte: 'light',
    'everforest-light': 'light',
    'kosmos-dark': 'dark',
    mocha: 'dark',
    oxford: 'basic',
  };
  var stored = localStorage.getItem(STORAGE_KEY);
  if (LEGACY[stored]) {
    localStorage.setItem(STORAGE_KEY, LEGACY[stored]);
  }

  function resolve(setting) {
    if (setting === 'auto') {
      return media.matches ? 'dark' : 'light';
    }
    return setting;
  }

  // Sparkle + kappa paths from static/images/kosmos-mark.svg (100x100
  // viewBox), joined into one d.
  var MARK_PATH =
    'M79.50 32.65Q81.94 45.46 94.75 47.90Q81.94 50.34 79.50 63.15Q77.06 50.34 ' +
    '64.25 47.90Q77.06 45.46 79.50 32.65ZM29.66 15.00Q28.32 20.25 28.32 ' +
    '48.55Q35.14 41.39 41.18 35.35Q51.14 25.40 53.04 23.16Q56.95 18.57 57.18 ' +
    '15.00H78.98Q75.74 17.57 68.36 25.28Q61.31 32.44 57.73 36.19Q54.16 39.93 ' +
    '53.82 40.27Q52.37 41.72 50.30 43.74Q48.23 45.75 45.66 48.32Q52.81 54.25 ' +
    '57.40 58.39Q73.73 73.71 80.89 85.00H60.87Q59.30 80.42 55.72 75.83Q54.16 ' +
    '73.93 51.25 70.97Q48.34 68.01 44.09 63.76Q34.36 54.14 28.32 ' +
    '50.11V70.47Q28.43 75.72 28.71 79.30Q28.99 82.88 29.55 85.00H13.00Q14.23 ' +
    '80.76 14.34 70.69Q14.34 49.89 14.34 38.37Q14.34 26.85 14.23 24.28Q14.12 ' +
    '21.71 13.84 19.41Q13.56 17.12 13.00 15.00Z';

  // Lucide "sparkles" (stroked), the AI chat windows' favicon.
  var SPARKLES_PATHS =
    '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 ' +
    '0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 ' +
    '0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 ' +
    '14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>' +
    '<path d="M20 3v4"/><path d="M22 5h-4"/><path d="M4 17v2"/><path d="M5 18H3"/>';

  // The favicon is its own document: it can see prefers-color-scheme but not
  // data-theme or the page's tokens. So themed icons are repainted here from
  // the resolved theme and handed over as a data URI. Only icons marked
  // data-favicon opt in: "brand" is the Kosmos mark (ground = --brand-ink,
  // what the sidebar mark wears; glyph = --background-body) and "ai" is the
  // sparkles the AI chat windows carry, stroked in --brand-ink. The dev mark
  // and the other per-app icons (notes, viewer) keep their fixed colours.
  function faviconSvg(kind, ink, ground) {
    if (kind === 'brand') {
      return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">' +
        '<rect width="100" height="100" rx="18" style="fill:' + ink + '"/>' +
        '<path d="' + MARK_PATH + '" style="fill:' + ground + '"/></svg>'
      );
    }
    if (kind === 'ai') {
      return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" ' +
        'fill="none" stroke-width="2" stroke-linecap="round" ' +
        'stroke-linejoin="round" style="stroke:' + ink + '">' +
        SPARKLES_PATHS + '</svg>'
      );
    }
    return null;
  }

  function paintFavicon() {
    var link = document.querySelector('link[rel="icon"][data-favicon]');
    if (!link) return;
    var style = getComputedStyle(document.documentElement);
    var ink = style.getPropertyValue('--brand-ink').trim();
    var ground = style.getPropertyValue('--background-body').trim();
    if (!ink || !ground) return;
    var svg = faviconSvg(link.getAttribute('data-favicon'), ink, ground);
    if (!svg) return;
    link.setAttribute('href', 'data:image/svg+xml,' + encodeURIComponent(svg));
  }

  function apply(setting) {
    document.documentElement.setAttribute('data-theme', resolve(setting));
    paintFavicon();
  }

  function current() {
    return localStorage.getItem(STORAGE_KEY) || 'auto';
  }

  window.setTheme = function (setting) {
    localStorage.setItem(STORAGE_KEY, setting);
    apply(setting);
  };

  window.getThemeSetting = current;

  // Reflect the stored setting onto the settings-page radios. Runs on load and
  // after every htmx swap, since the settings content arrives via a boosted
  // swap where an inline script would not reliably re-run.
  function syncRadios() {
    var input = document.querySelector(
      '.theme-options input[value="' + current() + '"]'
    );
    if (input) input.checked = true;
  }

  syncRadios();
  paintFavicon();
  document.body.addEventListener('htmx:afterSwap', syncRadios);

  media.addEventListener('change', function () {
    if (current() === 'auto') {
      apply('auto');
    }
  });
})();
