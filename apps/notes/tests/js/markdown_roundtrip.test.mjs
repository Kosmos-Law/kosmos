// What a note looks like after it is opened and saved again.
//
// A note is stored as markdown, turned into HTML for the editor
// (markdownToHtml), and turned back on every save (htmlToMarkdown). Text
// that the first step mangles is not only shown wrong: the next autosave
// writes the mangled version over the stored note. These cases pin down the
// text that used to be lost that way.
//
// Run: node --test apps/notes/tests/js/
// (Node 22.7 or later: the editor modules are plain .js files with ES
// module syntax and no package.json.)
//
// The round trip here goes markdown -> HTML -> markdown through a small
// stand-in DOM (dom_shim.mjs). In the browser the HTML also passes through
// the editor itself, which this does not model.

import assert from "node:assert/strict";
import { test } from "node:test";

import { installDom, createElement } from "./dom_shim.mjs";

installDom();

const { markdownToHtml, htmlToMarkdown, splitPipeRow } = await import(
  "../../../../static/js/notes/markdown.js"
);

const roundTrip = (md) => htmlToMarkdown(markdownToHtml(md));

// The text a reader would see, with every tag gone
function visibleText(html) {
  const div = createElement("div");
  div.innerHTML = html;
  return div.textContent;
}

test("text in angle brackets is shown and survives a save", () => {
  for (const md of [
    "Email <jsmith@example.com> about the hearing",
    "if x<y then stop",
    "Compare a < b and c > d",
    "See <https://example.com/order.pdf>",
    "<script>alert(1)</script>",
    '<img src=x onerror="alert(1)">',
  ]) {
    assert.equal(visibleText(markdownToHtml(md)), md);
    assert.equal(roundTrip(md), md);
  }
});

test("markup in note text reaches the editor as text, not as tags", () => {
  assert.equal(
    markdownToHtml("<b>bold?</b> & <jsmith@example.com>"),
    "<p>&lt;b&gt;bold?&lt;/b&gt; &amp; &lt;jsmith@example.com&gt;</p>",
  );
  assert.equal(
    markdownToHtml("# Heading <x>"),
    "<h1>Heading &lt;x&gt;</h1>",
  );
  assert.equal(
    markdownToHtml("- item <x>"),
    "<ul><li><p>item &lt;x&gt;</p></li></ul>",
  );
  assert.equal(
    markdownToHtml("> quoted <x>"),
    "<blockquote><p>quoted &lt;x&gt;</p></blockquote>",
  );
});

test("an ampersand and a typed entity keep their spelling", () => {
  for (const md of ["AT&T v. Smith", "Write &amp; to show an ampersand", "R&D &lt; cost"]) {
    assert.equal(visibleText(markdownToHtml(md)), md);
    assert.equal(roundTrip(md), md);
  }
});

test("underscores inside a word are not emphasis", () => {
  for (const md of [
    "Smith_Depo_Vol1.pdf",
    "See Smith_Depo_Vol1.pdf and Jones_Depo_Vol2.pdf today",
    "snake_case_name and other_thing",
    "Signed: ______ Date: ____",
    "Bates range ABC_000123 to ABC_000456",
    "a_b and __init__ty",
  ]) {
    const html = markdownToHtml(md);
    assert.ok(!/<em>|<strong>/.test(html), html);
    assert.equal(roundTrip(md), md);
  }
});

test("underscores around a word are still emphasis", () => {
  assert.equal(markdownToHtml("an _important_ point"), "<p>an <em>important</em> point</p>");
  assert.equal(markdownToHtml("a __bold__ point"), "<p>a <strong>bold</strong> point</p>");
  assert.equal(
    markdownToHtml("_see file_name.pdf_"),
    "<p><em>see file_name.pdf</em></p>",
  );
  // Saved back in the editor's own spelling, with nothing lost
  assert.equal(roundTrip("an _important_ point"), "an *important* point");
});

test("asterisk emphasis, strike and highlights are unchanged", () => {
  assert.equal(
    markdownToHtml("**bold** *italic* ***both*** ~~gone~~ ==marked== g==green=="),
    "<p><strong>bold</strong> <em>italic</em> <strong><em>both</em></strong> " +
      '<s>gone</s> <mark>marked</mark> <mark data-color="mark-green">green</mark></p>',
  );
  for (const md of ["**bold** and *italic*", "~~gone~~ and ==marked==", "g==green== r==red=="]) {
    assert.equal(roundTrip(md), md);
  }
});

test("a link keeps its address", () => {
  assert.equal(
    markdownToHtml("See [the order](https://example.com/a_b_c?x=1&y=2) today"),
    "<p>See the order (https://example.com/a_b_c?x=1&amp;y=2) today</p>",
  );
  assert.equal(
    roundTrip("See [the order](https://example.com/a_b_c?x=1&y=2) today"),
    "See the order (https://example.com/a_b_c?x=1&y=2) today",
  );
  // Text and address the same: shown once
  assert.equal(
    roundTrip("[https://example.com](https://example.com)"),
    "https://example.com",
  );
  // Once flattened, it stays put on later saves
  const once = roundTrip("[the *final* order](https://example.com/x)");
  assert.equal(once, "the *final* order (https://example.com/x)");
  assert.equal(roundTrip(once), once);
});

test("code keeps its characters", () => {
  assert.equal(
    markdownToHtml("run `a_b_c <x> & *y*` now"),
    "<p>run <code>a_b_c &lt;x&gt; &amp; *y*</code> now</p>",
  );
  for (const md of ["run `a_b_c <x> & *y*` now", "price `$1` and `$&`"]) {
    assert.equal(roundTrip(md), md);
  }
  const block = "```\nif (a < b && c_d_e) { *x* }\n```";
  assert.equal(roundTrip(block), block);
});

test("reference chips survive, label and all", () => {
  assert.equal(
    markdownToHtml("See [[doc:12|Smith_Depo_Vol1.pdf]] and [[hl:7|A & B <1>]]."),
    '<p>See <span class="note-ref" data-type="document" data-id="12">Smith_Depo_Vol1.pdf</span>' +
      ' and <span class="note-ref" data-type="highlight" data-id="7">A &amp; B &lt;1&gt;</span>.</p>',
  );
  for (const md of [
    "See [[doc:12|Smith_Depo_Vol1.pdf]] and [[hl:7|A & B <1>]].",
    "*Emphasis around [[doc:3|Order]] works*",
  ]) {
    assert.equal(roundTrip(md), md);
  }
});

test("a chip inside a table cell is one cell, not two", () => {
  assert.deepEqual(splitPipeRow("| [[doc:1|Smith Depo]] | b \\| c |"), [
    "[[doc:1|Smith Depo]]",
    "b | c",
  ]);
  assert.deepEqual(splitPipeRow("| a | b |"), ["a", "b"]);
  assert.deepEqual(splitPipeRow("| a [x] \\\\ y | |"), ["a [x] \\\\ y", ""]);
  const table = [
    "| Exhibit | Note |",
    "| --- | --- |",
    "| [[doc:1|Smith_Depo.pdf]] | <jsmith@example.com> |",
    "| b \\| c | x<y |",
  ].join("\n");
  assert.equal(roundTrip(table), table);
});

test("a whole note comes back as it went in", () => {
  const note = [
    "# Call with <opposing counsel>",
    "",
    "Reach her at <jsmith@example.com>; file is Smith_Depo_Vol1.pdf.",
    "",
    "- AT&T produced ABC_000123",
    "  - nested *point* with `code_span`",
    "",
    "1. first",
    "2. second",
    "",
    "> a quote with x<y",
    "",
    "---",
    "",
    "Signed: ______",
  ].join("\n");
  assert.equal(roundTrip(note), note);
  assert.equal(roundTrip(roundTrip(note)), note);
});
