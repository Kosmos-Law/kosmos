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
    'M74.86 31.13Q77.55 45.22 91.64 47.90Q77.55 50.58 74.86 64.67Q72.18 50.58 ' +
    '58.09 47.90Q72.18 45.22 74.86 31.13ZM25.03 15.00Q23.69 20.25 23.69 ' +
    '48.55Q30.51 41.39 36.55 35.35Q46.50 25.40 48.40 23.16Q52.32 18.57 52.54 ' +
    '15.00H74.35Q71.11 17.57 63.72 25.28Q56.68 32.44 53.10 36.19Q49.52 39.93 ' +
    '49.19 40.27Q47.73 41.72 45.66 43.74Q43.59 45.75 41.02 48.32Q48.18 54.25 ' +
    '52.76 58.39Q69.09 73.71 76.25 85.00H56.23Q54.67 80.42 51.09 75.83Q49.52 ' +
    '73.93 46.61 70.97Q43.71 68.01 39.46 63.76Q29.73 54.14 23.69 ' +
    '50.11V70.47Q23.80 75.72 24.08 79.30Q24.36 82.88 24.92 85.00H8.36Q9.59 ' +
    '80.76 9.71 70.69Q9.71 49.89 9.71 38.37Q9.71 26.85 9.59 24.28Q9.48 21.71 ' +
    '9.20 19.41Q8.92 17.12 8.36 15.00Z';

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
