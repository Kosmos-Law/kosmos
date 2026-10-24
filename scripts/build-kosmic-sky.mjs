#!/usr/bin/env node
// Builds the Kosmic theme's sky from the landing page's Sky.astro, so the
// app and kosmos.law share one night: the same aurora, star field, stars
// and constellations, drawn from the same seeds.
//
//   node --experimental-strip-types scripts/build-kosmic-sky.mjs [Sky.astro]
//
// (default: ../kosmos/src/components/Sky.astro). Writes
//   static/images/kosmic/aurora-{1,2,3}.svg  the aurora's three sheets
//   static/images/kosmic/field.svg           the repeating star-field tile
//   templates/components/kosmic-sky.html     the markup base.html includes
//   static/css/kosmic-stars.css              each star's twinkle
//   static/js/kosmic-aurora.js               the live aurora: the component's
//                                            WebGL shader and the script that
//                                            drives it, types stripped
// The rest of the animation lives in static/css/kosmic.css, ported by hand.
// Rerun this after the landing page's sky changes; needs Node 22.13+.
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { stripTypeScriptTypes } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const repo = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = resolve(process.argv[2] || join(repo, "../kosmos/src/components/Sky.astro"));

// The component's frontmatter is plain TypeScript; Node runs it once the
// types are stripped, and it hands back what the markup is built from.
const component = readFileSync(source, "utf8");
const frontmatter = component.split(/^---$/m)[1];
const work = mkdtempSync(join(tmpdir(), "kosmic-sky-"));
const module = join(work, "sky.ts");
writeFileSync(
  module,
  frontmatter +
    "\nexport { sheets, tileUrl, stars, constellations, nodeTwinkle, glint, glintDefs, skyDust };\n",
);
const { sheets, tileUrl, stars, constellations, nodeTwinkle, glint, glintDefs, skyDust } =
  await import(pathToFileURL(module).href);
rmSync(work, { recursive: true });

// svgUrl() wraps an encoded SVG in url("data:…"); unwrap it to a file.
const unwrap = (url) =>
  decodeURIComponent(url.replace(/^url\("data:image\/svg\+xml,/, "").replace(/"\)$/, ""));

const images = join(repo, "static/images/kosmic");
mkdirSync(images, { recursive: true });
sheets.forEach((url, i) => writeFileSync(join(images, `aurora-${i + 1}.svg`), unwrap(url) + "\n"));
writeFileSync(join(images, "field.svg"), unwrap(tileUrl) + "\n");

/* The app's own additions. The landing page keeps its sky to the top of
   the screen, round the hero; the app's sky fills the window, so it gets
   a constellation in the lower half too. Libra sits low and central,
   plotted from its stars' real positions (east to the left, as seen):
   Zubeneschamali (0, the green-tinged one), Zubenelgenubi (1), Gamma (2),
   Brachium (3, an M giant, so amber like Betelgeuse) and Upsilon (4). */
const appConstellations = [
  {
    name: "libra",
    color: "#d8dee9",
    nodeColors: { 0: "#8fbcbb", 3: "#ebcb8b" },
    nodeRadii: { 0: 1.9, 1: 1.8 },
    lineOpacity: 0.12,
    nodeR: 1.5,
    points: [
      [49.6, 70.0],
      [53.2, 75.9],
      [47.0, 74.9],
      [51.4, 84.3],
      [46.8, 86.8],
    ],
    edges: [
      [0, 1],
      [0, 2],
      [1, 2],
      [1, 3],
      [2, 4],
    ],
  },
];

// A star is drawn as a glint: a halo in its colour, a core near white,
// and on the brightest four faint spikes. Each colour's gradients are
// defined once. The ids are the component's own ("h" or "s" and the
// hex); in the app they share a page with everything else, so they take
// the kosmic- prefix.
const prefixIds = (svg) => svg.replace(/(id="|url\(#)([hs][0-9a-f]{6})/g, "$1kosmic-$2");
const allConstellations = [...constellations, ...appConstellations];
const defs = prefixIds(
  glintDefs([
    ...stars.map((s) => s.fill),
    ...allConstellations.flatMap((c) => c.points.map((_, i) => c.nodeColors?.[i] ?? c.color)),
  ]),
);

// Stars carry their opacity as an SVG attribute; their twinkles go to a
// generated stylesheet, one class each, since the templates take no
// inline styles. A glint is placed by percentages in a nested svg, as
// the landing page does: a nested svg can be, where a transform cannot.
const lines = [];
const rules = [];
const twinkling = (animation) => {
  const name = `kosmic-twinkle-${rules.length + 1}`;
  rules.push(`.${name} {\n  animation: ${animation};\n}`);
  return ` ${name}`;
};
const placed = (cx, cy, r, fill, opacity, twinkle) =>
  `      <svg class="kosmic-star${twinkle ? twinkling(twinkle) : ""}" x="${cx}%" y="${cy}%" overflow="visible" opacity="${opacity}">` +
  prefixIds(glint(r, fill)) +
  `</svg>`;

lines.push(`      ${defs}`);
lines.push(`      <g class="kosmic-dust">`);
for (const d of skyDust) {
  lines.push(
    `      <circle cx="${d.x}%" cy="${d.y}%" r="${d.r}" fill="${d.fill}" opacity="${d.o}" />`,
  );
}
lines.push("      </g>");
for (const c of allConstellations) {
  lines.push(`      <g class="kosmic-${c.name}">`);
  for (const [a, b] of c.edges) {
    const [x1, y1] = c.points[a];
    const [x2, y2] = c.points[b];
    lines.push(
      `      <line x1="${x1}%" y1="${y1}%" x2="${x2}%" y2="${y2}%" stroke="${c.color}" stroke-width="1" opacity="${c.lineOpacity}" />`,
    );
  }
  c.points.forEach(([cx, cy], i) => {
    lines.push(
      placed(cx, cy, c.nodeRadii?.[i] ?? c.nodeR, c.nodeColors?.[i] ?? c.color, 0.85, nodeTwinkle(i)),
    );
  });
  lines.push("      </g>");
}
for (const s of stars) {
  const twinkle = s.twinkle && `twinkle ${s.twinkle[0]}s ease-in-out ${s.twinkle[1]}s infinite`;
  lines.push(placed(s.cx, s.cy, s.r, s.fill, s.opacity, twinkle));
}

writeFileSync(
  join(repo, "static/css/kosmic-stars.css"),
  `/* GENERATED by scripts/build-kosmic-sky.mjs from the landing page's
   Sky.astro: each star's twinkle (the keyframes are in kosmic.css).
   Rerun the script rather than editing here. */
${rules.join("\n\n")}
`,
);

// The live display. The component's <script> is TypeScript and a module;
// the app loads it with a plain <script src>, so the types come off and
// an arrow function keeps its names to itself. It finds its root by the
// data-aurora attribute, which the markup below carries too, and draws
// only while that root has a size, so under the other themes, where the
// sky is display: none, it makes no WebGL context and costs nothing. The
// canvas is empty by nature; djLint is told so.
const script = component.match(/<script>([\s\S]*?)<\/script>/)[1];
writeFileSync(
  join(repo, "static/js/kosmic-aurora.js"),
  `/* GENERATED by scripts/build-kosmic-sky.mjs from the landing page's
   Sky.astro: the live aurora, a WebGL shader drawn on the canvas in
   components/kosmic-sky.html. The drawn sheets behind it stand in
   until it runs and wherever it cannot. Rerun the script rather than
   editing here. */
(() => {
${stripTypeScriptTypes(script).replace(/[ \t]+$/gm, "")}
})();
`,
);

const template = `{% comment %}
  The Kosmic theme's night sky, behind the whole app. GENERATED by
  scripts/build-kosmic-sky.mjs from the landing page's Sky.astro; rerun it
  rather than editing here. Hidden unless data-theme is kosmic, so its
  images are never fetched under the other themes (kosmic.css). The
  aurora is drawn live on the canvas by js/kosmic-aurora.js where there
  is WebGL; the sheets are the fallback.
{% endcomment %}
<div class="kosmic-sky" aria-hidden="true">
  <div class="kosmic-aurora" data-aurora>
${sheets.map((_, i) => `    <span class="kosmic-sheet-${i + 1}"></span>`).join("\n")}
    {# djlint:off H020 #}
    <canvas></canvas>
    {# djlint:on #}
  </div>
  <div class="kosmic-field"></div>
  <div class="kosmic-stars">
    <div class="kosmic-glow"></div>
    <div class="kosmic-galaxy"></div>
    <svg class="kosmic-starfield" width="100%" height="100%">
${lines.join("\n")}
    </svg>
    <span class="kosmic-shooting-star ltr"></span>
    <span class="kosmic-shooting-star rtl"></span>
    <span class="kosmic-shooting-star low"></span>
  </div>
</div>
`;
writeFileSync(join(repo, "templates/components/kosmic-sky.html"), template);
console.log(`Built the Kosmic sky from ${source}`);
