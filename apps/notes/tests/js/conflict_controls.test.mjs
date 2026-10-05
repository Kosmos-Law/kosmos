// A paused conflict hides every control that would change the note.
//
// enterConflict (autosave.js) pauses editing: ConflictLock refuses every
// document change, silently. The format cluster was already hidden, but
// the overflow menu's format items, Import from markdown, the Replace
// buttons and the table bar stayed visible and did nothing. They carry
// data-editing-only in editor.html; this checks the toggle, and that a
// swap to a fresh note (clearConflict) brings them back.
//
// Run: node --test apps/notes/tests/js/

import assert from "node:assert/strict";
import { test, beforeEach } from "node:test";

import { installDom, createElement } from "./dom_shim.mjs";

installDom();

const { state } = await import("../../../../static/js/notes/state.js");
const { enterConflict, clearConflict } = await import(
  "../../../../static/js/notes/autosave.js"
);

function control(attrs) {
  const el = createElement("button");
  Object.assign(el.attrs, attrs);
  document.body.appendChild(el);
  return el;
}

beforeEach(() => {
  document.body.childNodes = [];
  clearConflict();
});

test("the editing-only controls go while paused and come back after", () => {
  const importItem = control({ "data-editing-only": "" });
  const replaceAll = control({ id: "replace-all", "data-editing-only": "" });
  const readOnlyOk = control({ id: "export-btn" });

  enterConflict();
  assert.equal(state.conflict, true);
  assert.equal(importItem.style.display, "none");
  assert.equal(replaceAll.style.display, "none");
  assert.equal(readOnlyOk.style.display, undefined);

  clearConflict();
  assert.equal(state.conflict, false);
  assert.equal(importItem.style.display, "");
  assert.equal(replaceAll.style.display, "");
});

test("a swap that was never paused leaves the controls alone", () => {
  // setupToolbar decides the format cluster per note; clearConflict runs
  // on every swap and must not undo that decision
  const cluster = control({ "data-editing-only": "" });
  cluster.style.display = "none";
  clearConflict();
  assert.equal(cluster.style.display, "none");
});
