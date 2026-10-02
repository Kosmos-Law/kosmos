// A save's answer must only ever be applied to the note it was sent for.
//
// The editor flushes a save when the user switches notes, and the answer
// can arrive after the next note is on screen. Applied there, it stamped
// the old note's version and saved text onto the new note: the new note's
// next save then failed its version check and raised a conflict that never
// happened (which also locks the note until it is reloaded). A 409 or a
// failure arriving late did the same kind of damage to the wrong note.
//
// Run: node --test "apps/notes/tests/js/*.test.mjs"

import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import { installDom } from "./dom_shim.mjs";

installDom();

const { state } = await import("../../../../static/js/notes/state.js");
const { performAutosave, clearConflict } = await import(
  "../../../../static/js/notes/autosave.js"
);

// Each call to fetch waits here until the test answers it
let pending = [];
globalThis.fetch = (url, options) =>
  new Promise((resolve, reject) => pending.push({ url, options, resolve, reject }));

const answer = (status, body) => ({ status, json: async () => body });
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

// What a content swap does: a fresh NOTE_DATA object, a fresh editor, and
// a buffer that matches what the server sent
function openNote(id, text, updatedAt) {
  window.NOTE_DATA = { id, updatedAt, autosaveUrl: `/notes/${id}/autosave/` };
  state.editor = {
    text,
    getHTML: () => `<p>${state.editor.text}</p>`,
    setEditable() {},
  };
  state.lastSavedContent = text;
}

function type(text) {
  state.editor.text = text;
}

beforeEach(() => {
  pending = [];
  clearConflict();
  if (state.autosaveTimer) clearTimeout(state.autosaveTimer);
  state.autosaveTimer = null;
});

test("a save answered while its note is still open is applied", async () => {
  openNote(1, "first", "v1");
  type("first, edited");
  performAutosave();
  assert.equal(pending[0].url, "/notes/1/autosave/");
  assert.equal(pending[0].options.body.get("base_version"), "v1");

  pending[0].resolve(answer(200, { saved: true, updated_at: "v2" }));
  await settle();

  assert.equal(window.NOTE_DATA.updatedAt, "v2");
  assert.equal(state.lastSavedContent, "first, edited");
});

test("a save answered after a note switch leaves the new note alone", async () => {
  openNote(1, "first", "a1");
  type("first, edited");
  performAutosave(); // the flush on the way out of note 1
  openNote(2, "second", "b1");

  pending[0].resolve(answer(200, { saved: true, updated_at: "a2" }));
  await settle();

  assert.equal(window.NOTE_DATA.id, 2);
  assert.equal(window.NOTE_DATA.updatedAt, "b1");
  assert.equal(state.lastSavedContent, "second");

  // ...so note 2's next save carries note 2's own version
  type("second, edited");
  performAutosave();
  assert.equal(pending[1].url, "/notes/2/autosave/");
  assert.equal(pending[1].options.body.get("base_version"), "b1");
});

test("leaving a note and coming straight back does not count as staying", async () => {
  openNote(1, "first", "a1");
  type("first, edited");
  performAutosave();
  openNote(2, "second", "b1");
  // Back on note 1, as the server rendered it before the save landed
  openNote(1, "first", "a1");

  pending[0].resolve(answer(200, { saved: true, updated_at: "a2" }));
  await settle();

  // Not applied: this buffer holds the old text, and stamping it with the
  // new version would let its next save overwrite the one just made. The
  // stale version instead makes that next save a (true) conflict.
  assert.equal(window.NOTE_DATA.updatedAt, "a1");
  assert.equal(state.lastSavedContent, "first");
});

test("a conflict answered after a note switch does not pause the new note", async () => {
  openNote(1, "first", "a1");
  type("first, edited");
  performAutosave();
  openNote(2, "second", "b1");

  pending[0].resolve(answer(409, { saved: false, conflict: true }));
  await settle();
  assert.equal(state.conflict, false);

  // On the note it was sent for, it still does
  type("second, edited");
  performAutosave();
  pending[1].resolve(answer(409, { saved: false, conflict: true }));
  await settle();
  assert.equal(state.conflict, true);
});

test("a failure answered after a note switch is not retried on the new note", async () => {
  openNote(1, "first", "a1");
  type("first, edited");
  performAutosave();
  openNote(2, "second", "b1");

  pending[0].reject(new Error("network down"));
  await settle();
  assert.equal(state.autosaveTimer, null);

  // On the note it was sent for, a failure schedules a retry
  type("second, edited");
  performAutosave();
  pending[1].reject(new Error("network down"));
  await settle();
  assert.notEqual(state.autosaveTimer, null);
  clearTimeout(state.autosaveTimer);
});
