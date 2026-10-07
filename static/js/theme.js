(function () {
  var STORAGE_KEY = 'theme';
  var media = window.matchMedia('(prefers-color-scheme: dark)');

  // Legacy: retired themes map to their nearest survivor — sky, kosmos,
  // latte, and everforest-light to light (Matcha); kosmos-dark and mocha
  // to dark (Gruvbox). oxford was renamed basic, matcha-mist matcha-lavender.
  var LEGACY = {
    sky: 'light',
    kosmos: 'light',
    latte: 'light',
    'everforest-light': 'light',
    'kosmos-dark': 'dark',
    mocha: 'dark',
    oxford: 'basic',
    'matcha-mist': 'matcha-lavender',
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
    'M76.87 31.10Q79.61 45.49 94.00 48.23Q79.61 50.97 76.87 65.36Q74.13 50.97 ' +
    '59.74 48.23Q74.13 45.49 76.87 31.10ZM28.06 20.46Q26.93 24.89 26.93 ' +
    '48.77Q32.69 42.73 37.78 37.64Q46.19 29.24 47.79 27.35Q51.09 23.48 51.28 ' +
    '20.46H69.69Q66.95 22.63 60.72 29.14Q54.77 35.18 51.75 38.34Q48.73 41.51 ' +
    '48.45 41.79Q47.22 43.02 45.48 44.71Q43.73 46.41 41.56 48.58Q47.60 53.59 ' +
    '51.47 57.08Q65.25 70.01 71.29 79.54H54.40Q53.08 75.67 50.05 71.80Q48.73 ' +
    '70.20 46.28 67.70Q43.83 65.20 40.24 61.61Q32.03 53.49 26.93 ' +
    '50.09V67.27Q27.03 71.71 27.26 74.73Q27.50 77.75 27.97 79.54H14.00Q15.04 ' +
    '75.96 15.13 67.46Q15.13 49.91 15.13 40.18Q15.13 30.46 15.04 28.29Q14.94 ' +
    '26.12 14.71 24.19Q14.47 22.25 14.00 20.46Z';

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
  // data-favicon opt in: "brand" is the Kosmos mark (ground = the brand
  // gradient the sidebar mark wears, --brand-grad-from to --brand-grad-to on
  // the diagonal; glyph = --background-body), "brand-dev" is the same mark
  // for dev tabs (the dev red leads the gradient in place of the brand ink,
  // so the tab still reads red first; the far end stays the theme's) and
  // "ai" is the sparkles the AI chat windows carry, stroked in --brand-ink.
  // The other per-app icons (notes, viewer) keep their fixed colours.
  function faviconSvg(kind, ink, ground, from, to) {
    if (kind === 'brand') {
      return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">' +
        '<linearGradient id="g" x1="0" y1="0" x2="1" y2="1">' +
        '<stop offset="0.15" style="stop-color:' + from + '"/>' +
        '<stop offset="0.85" style="stop-color:' + to + '"/>' +
        '</linearGradient>' +
        '<rect width="100" height="100" rx="18" fill="url(#g)"/>' +
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
    // A stylesheet that predates the gradient tokens paints the flat ink.
    var from = style.getPropertyValue('--brand-grad-from').trim() || ink;
    var to = style.getPropertyValue('--brand-grad-to').trim() || ink;
    var kind = link.getAttribute('data-favicon');
    if (kind === 'brand-dev') {
      // The red baked into kosmos-mark-dev.svg, the unpainted fallback.
      kind = 'brand';
      from = style.getPropertyValue('--nord11').trim() || from;
    }
    var svg = faviconSvg(kind, ink, ground, from, to);
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

  // Kosmic's sky can be stilled, per device like the theme. The inline
  // script in base.html sets data-sky-motion before first paint; this keeps
  // it in step and backs the Appearance dropdown.
  var SKY_MOTION_KEY = 'sky-motion';

  function skyMotion() {
    return localStorage.getItem(SKY_MOTION_KEY) === 'off' ? 'off' : 'on';
  }

  window.setSkyMotion = function (value) {
    localStorage.setItem(SKY_MOTION_KEY, value);
    document.documentElement.setAttribute('data-sky-motion', skyMotion());
  };

  document.documentElement.setAttribute('data-sky-motion', skyMotion());

  // Matcha Lavender's wash runs high (the default) or low, per device the
  // same way.
  var MIST_INTENSITY_KEY = 'mist-intensity';

  function mistIntensity() {
    return localStorage.getItem(MIST_INTENSITY_KEY) === 'low' ? 'low' : 'high';
  }

  window.setMistIntensity = function (value) {
    localStorage.setItem(MIST_INTENSITY_KEY, value);
    document.documentElement.setAttribute('data-mist-intensity', mistIntensity());
  };

  document.documentElement.setAttribute('data-mist-intensity', mistIntensity());

  // Reflect the stored setting onto the settings-page radios. Runs on load and
  // after every htmx swap, since the settings content arrives via a boosted
  // swap where an inline script would not reliably re-run.
  function syncRadios() {
    var input = document.querySelector(
      '.theme-options input[value="' + current() + '"]'
    );
    if (input) input.checked = true;
    var sky = document.getElementById('sky-motion');
    if (sky) sky.value = skyMotion();
    var mist = document.getElementById('mist-intensity');
    if (mist) mist.value = mistIntensity();
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
