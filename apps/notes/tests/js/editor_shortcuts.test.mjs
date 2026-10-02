// The notes editor listens for its shortcuts on the whole page. The ones
// that change the note's text (Ctrl+D deletes a paragraph; F2 to F4 and F7
// reformat one) must act only while the caret is in that text; with focus
// in the title, the Find box or Search Notes the page calls
// handleSurfaceShortcut instead, which knows only the harmless ones.
//
// Run: node --test "apps/notes/tests/js/*.test.mjs"

import assert from "node:assert/strict";
import { test } from "node:test";

const { handleEditorShortcut, handleSurfaceShortcut } = await import(
  "../../../../static/js/editor-shortcuts.js"
);

function key(props) {
  return {
    ctrlKey: false,
    metaKey: false,
    shiftKey: false,
    altKey: false,
    code: "",
    prevented: false,
    preventDefault() {
      this.prevented = true;
    },
    ...props,
  };
}

// Records every command a shortcut runs on the editor
function fakeEditor() {
  const calls = [];
  const chain = new Proxy(
    {},
    {
      get: (_t, name) => (...args) => {
        calls.push([name, ...args]);
        return chain;
      },
    },
  );
  return { calls, chain: () => chain, isActive: () => false };
}

const TEXT_KEYS = [
  { ctrlKey: true, key: "d" },
  { ctrlKey: true, key: "Delete" },
  { key: "F2" },
  { key: "F3" },
  { key: "F4" },
  { key: "F7" },
  { ctrlKey: true, key: "1" },
  { ctrlKey: true, key: "0" },
  { ctrlKey: true, key: "7" },
  { ctrlKey: true, key: "8" },
  { altKey: true, key: "y" },
  { altKey: true, key: "c" },
  { ctrlKey: true, shiftKey: true, key: ":", code: "Semicolon" },
];

test("outside the editor's text, the text shortcuts do nothing", () => {
  const actions = {
    save: () => assert.fail("save"),
    toggleSearch: () => assert.fail("search"),
    showShortcuts: () => assert.fail("shortcuts"),
    openReferences: () => assert.fail("references"),
  };
  for (const props of TEXT_KEYS) {
    const e = key(props);
    assert.equal(handleSurfaceShortcut(e, actions), false, JSON.stringify(props));
    // Not swallowed either: the browser or the focused field gets the key
    assert.equal(e.prevented, false, JSON.stringify(props));
  }
});

test("inside the editor's text, they act on the editor", () => {
  for (const props of TEXT_KEYS.filter((p) => p.code !== "Semicolon")) {
    const editor = fakeEditor();
    const e = key(props);
    assert.equal(handleEditorShortcut(editor, e, {}), true, JSON.stringify(props));
    assert.equal(e.prevented, true);
    assert.ok(editor.calls.length > 0);
  }
  const editor = fakeEditor();
  handleEditorShortcut(editor, key({ ctrlKey: true, key: "d" }), {});
  assert.deepEqual(editor.calls, [["focus"], ["deleteNode", "paragraph"], ["run"]]);
});

test("save, search and the shortcuts dialog work from anywhere", () => {
  for (const handle of [
    (e, actions) => handleSurfaceShortcut(e, actions),
    (e, actions) => handleEditorShortcut(fakeEditor(), e, actions),
  ]) {
    const seen = [];
    const actions = {
      save: () => seen.push("save"),
      toggleSearch: () => seen.push("search"),
      showShortcuts: () => seen.push("shortcuts"),
    };
    for (const props of [
      { ctrlKey: true, key: "s" },
      { ctrlKey: true, key: "h" },
      { ctrlKey: true, shiftKey: true, key: "?" },
    ]) {
      const e = key(props);
      assert.equal(handle(e, actions), true);
      assert.equal(e.prevented, true);
    }
    assert.deepEqual(seen, ["save", "search", "shortcuts"]);
  }
});

test("a surface with no such action leaves the key to the browser", () => {
  const e = key({ ctrlKey: true, key: "s" });
  assert.equal(handleSurfaceShortcut(e, {}), false);
  assert.equal(e.prevented, false);
});
