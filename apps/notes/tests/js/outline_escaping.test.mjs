// The outline panel lists the note's headings. Heading text is whatever
// someone typed into the note, and every user who opens the note sees its
// outline, so that text must be put on the page as text. Built with
// innerHTML, a heading reading <img src=x onerror=...> ran for each of them.
//
// Run: node --test "apps/notes/tests/js/*.test.mjs"

import assert from "node:assert/strict";
import { test } from "node:test";

import { installDom, createElement } from "./dom_shim.mjs";

const outlineList = createElement("ul");
installDom({ "outline-list": outlineList });

const { state } = await import("../../../../static/js/notes/state.js");
const { buildOutline } = await import("../../../../static/js/notes/outline.js");

// The slice of the editor that buildOutline reads: the document's heading
// nodes and the caret position
function editorWithHeadings(headings) {
  return {
    state: {
      selection: { from: 0 },
      doc: {
        descendants(visit) {
          headings.forEach(([level, text], i) =>
            visit(
              { type: { name: "heading" }, attrs: { level }, textContent: text },
              i * 10,
            ),
          );
        },
      },
    },
  };
}

test("heading text is shown as text, never parsed as markup", () => {
  const evil = '<img src=x onerror="alert(1)">';
  window.NOTE_DATA = { id: 1 };
  state.editor = editorWithHeadings([
    [2, evil],
    [3, "<script>alert(2)</script> child"],
    [2, "Plain & simple"],
  ]);

  buildOutline();

  // Nothing typed into a heading became an element
  assert.deepEqual(outlineList.querySelectorAll("img"), []);
  assert.deepEqual(outlineList.querySelectorAll("script"), []);
  // ...and nothing typed into a heading went through innerHTML at all
  for (const html of outlineList.innerHTMLWrites) {
    assert.ok(!html.includes("alert("), html);
  }

  assert.deepEqual(
    outlineList.querySelectorAll(".outline-text").map((el) => el.textContent),
    [evil, "<script>alert(2)</script> child", "Plain & simple"],
  );
});

test("the outline keeps its shape: nesting, positions, collapse state", () => {
  window.NOTE_DATA = { id: 2 };
  sessionStorage.setItem("outline-collapsed-2", JSON.stringify([0]));
  state.editor = editorWithHeadings([
    [2, "Facts"],
    [3, "Timeline"],
    [3, ""],
    [2, "Law"],
  ]);

  buildOutline();

  const top = outlineList.children;
  assert.equal(top.length, 2);
  const [facts, law] = top;
  for (const name of ["outline-item", "level-2", "has-children", "collapsed"]) {
    assert.ok(facts.classList.contains(name), name);
  }
  assert.equal(facts.dataset.pos, "0");
  assert.equal(facts.querySelectorAll(".outline-toggle").length, 1);
  assert.deepEqual(
    facts.querySelector(".outline-children").children.map((li) => [
      li.dataset.pos,
      li.querySelector(".outline-text").textContent,
    ]),
    [
      ["10", "Timeline"],
      ["20", "(empty)"],
    ],
  );
  assert.ok(law.classList.contains("level-2"));
  assert.ok(!law.classList.contains("has-children"));
  assert.equal(law.querySelectorAll(".outline-toggle-spacer").length, 1);
});

test("a note with no headings says so", () => {
  state.editor = editorWithHeadings([]);
  buildOutline();
  assert.equal(outlineList.textContent, "No headings");
});
