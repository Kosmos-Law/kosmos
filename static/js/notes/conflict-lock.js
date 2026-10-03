// The editor half of a paused conflict (autosave.js enterConflict).
//
// setEditable(false) only stops typing; TipTap still applies programmatic
// commands (format buttons, table bar, replace, import) to a non-editable
// editor. ConflictLock refuses every change to the document while the
// conflict stands, whichever path it comes by.
//
// Its own module so autosave.js stays free of the editor bundle (which
// needs a real browser to load) and can be tested under Node.

import { Extension, Plugin, PluginKey } from "../vendor/tiptap.bundle.js";

import { state } from "./state.js";

export const ConflictLock = Extension.create({
  name: "conflictLock",

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey("conflictLock"),
        filterTransaction: (tr) => !(state.conflict && tr.docChanged),
      }),
    ];
  },
});
