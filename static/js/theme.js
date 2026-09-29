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
    'M77.86 31.13Q80.55 45.22 94.64 47.90Q80.55 50.58 77.86 64.67Q75.18 50.58 ' +
    '61.09 47.90Q75.18 45.22 77.86 31.13ZM28.03 15.00Q26.69 20.25 26.69 ' +
    '48.55Q33.51 41.39 39.55 35.35Q49.50 25.40 51.40 23.16Q55.32 18.57 55.54 ' +
    '15.00H77.35Q74.11 17.57 66.72 25.28Q59.68 32.44 56.10 36.19Q52.52 39.93 ' +
    '52.19 40.27Q50.73 41.72 48.66 43.74Q46.59 45.75 44.02 48.32Q51.18 54.25 ' +
    '55.76 58.39Q72.09 73.71 79.25 85.00H59.23Q57.67 80.42 54.09 75.83Q52.52 ' +
    '73.93 49.61 70.97Q46.71 68.01 42.46 63.76Q32.73 54.14 26.69 ' +
    '50.11V70.47Q26.80 75.72 27.08 79.30Q27.36 82.88 27.92 85.00H11.36Q12.59 ' +
    '80.76 12.71 70.69Q12.71 49.89 12.71 38.37Q12.71 26.85 12.59 24.28Q12.48 ' +
    '21.71 12.20 19.41Q11.92 17.12 11.36 15.00Z';

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
