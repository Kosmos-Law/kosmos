// Autosave, save status, and multi-tab conflict handling for the editor
//
// Every save carries base_version — the exact updated_at string this tab
// last received — and the server 409s if anyone saved since (another tab,
// another person, or the AI). A 409 (or a broadcast save landing while
// we're dirty) pauses editing behind a banner until the user reloads; a
// clean tab just reloads silently.
//
// A save that fails outright (network down, server error) is retried a
// few times on its own, so text typed just before the user stops typing
// isn't left unsaved until the next keystroke.

import { state, getCSRFToken } from "./state.js";
import { htmlToMarkdown } from "./markdown.js";
import { broadcast } from "./broadcast.js";
import { openLaunchNote } from "./file-tree.js";

export function getMarkdownContent() {
  if (!state.editor) return "";

  return htmlToMarkdown(state.editor.getHTML());
}

// Clean = the buffer matches what this tab last saved (during the swap
// gap state.editor is null and this correctly reports clean)
export function isClean() {
  return getMarkdownContent() === state.lastSavedContent;
}

const RETRY_DELAY_MS = 5000;
const MAX_RETRIES = 3;
let retries = 0;

export function scheduleAutosave() {
  if (window.NOTE_DATA && window.NOTE_DATA.readOnly) return;
  if (state.conflict) return;
  if (state.autosaveTimer) clearTimeout(state.autosaveTimer);
  updateSaveStatus("unsaved");

  retries = 0; // a fresh edit gets a fresh run of retries
  state.autosaveTimer = setTimeout(performAutosave, 2000);
}

// After a failed save: try again shortly, a bounded number of times, each
// wait longer than the last. The timer is the autosave timer, so an edit
// or a note switch in the meantime replaces it.
function scheduleRetry() {
  updateSaveStatus("unsaved");
  if (state.conflict || retries >= MAX_RETRIES) return;
  retries++;
  if (state.autosaveTimer) clearTimeout(state.autosaveTimer);
  state.autosaveTimer = setTimeout(performAutosave, RETRY_DELAY_MS * retries);
}

export function performAutosave() {
  if (state.conflict) return;
  const content = getMarkdownContent();

  if (content === state.lastSavedContent) {
    updateSaveStatus("saved");

    return;
  }

  updateSaveStatus("saving");
  // The note this save belongs to. Every content swap (a note switch, a
  // reload of the same note) installs a fresh NOTE_DATA object, so if it
  // is no longer this one when the response arrives, the answer is about
  // a buffer the user has left: applying it would stamp the old note's
  // version and saved text onto the note now open (whose next save then
  // 409s into a false conflict), or pause, retry or bail out of a note
  // the response says nothing about. Identity rather than id, so leaving
  // a note and coming straight back does not count as never having left.
  const sentFor = window.NOTE_DATA;
  const stale = () => window.NOTE_DATA !== sentFor;

  const formData = new FormData();
  formData.append("content", content);
  formData.append("base_version", window.NOTE_DATA.updatedAt || "");

  fetch(window.NOTE_DATA.autosaveUrl, {
    method: "POST",
    headers: { "X-CSRFToken": getCSRFToken() },
    body: formData,
  })
    .then((r) => {
      if (r.status === 409) {
        if (!stale()) enterConflict();
        return null;
      }
      if (r.status === 404) {
        // The note was deleted from another tab (e.g. a folder-cascade
        // delete, which has no per-note broadcast); land on launch like
        // a direct delete would
        if (!stale()) openLaunchNote();
        return null;
      }
      return r.json();
    })
    .then((data) => {
      if (!data || !data.saved) return;
      // The save happened whichever note this tab shows now, so sibling
      // tabs hear of it either way, under the id of the note it was for
      broadcast({
        type: "note-saved",
        noteId: sentFor.id,
        updatedAt: data.updated_at,
      });
      if (stale()) return;
      retries = 0;
      state.lastSavedContent = content;
      window.NOTE_DATA.updatedAt = data.updated_at;
      updateSaveStatus("saved");
      document.body.dispatchEvent(new Event("noteSaved"));
    })
    .catch(() => {
      if (!stale()) scheduleRetry();
    });
}

// ─── Conflict state ──────────────────────────────────────────────────────────

// The banner says editing is paused, so it has to be: nothing typed past
// this point could be saved, and "Reload latest" would throw it away. The
// text stays selectable, so what was typed before the conflict can still
// be copied out. Everything locked here lives in the content partial or is
// reset by initEditor, so the reload's swap restores it. Changes that do
// not come from typing are refused by ConflictLock (conflict-lock.js).
export function enterConflict() {
  if (state.conflict) return;
  state.conflict = true;
  if (state.autosaveTimer) clearTimeout(state.autosaveTimer);
  if (state.editor) state.editor.setEditable(false);
  const title = document.getElementById("note-title");
  if (title) title.readOnly = true;
  setEditingControlsHidden(true);
  const banner = document.getElementById("note-conflict-banner");
  if (banner) banner.hidden = false;
  updateSaveStatus("conflict");
}

export function clearConflict() {
  const wasPaused = state.conflict;
  state.conflict = false;
  const banner = document.getElementById("note-conflict-banner");
  if (banner) banner.hidden = true;
  if (wasPaused) setEditingControlsHidden(false);
}

// Dead buttons would mislead: every control that would change the note
// (the format cluster and its overflow menu items, Import, Replace, the
// table bar: data-editing-only in editor.html) goes while the banner is
// up, since ConflictLock refuses what they do without a word. They live
// in the toolbar, which survives the reload's swap, so clearConflict
// brings them back (setupToolbar then re-decides the cluster). Inline
// display, because the overflow items are shown by container queries.
function setEditingControlsHidden(hidden) {
  document.querySelectorAll("[data-editing-only]").forEach((el) => {
    el.style.display = hidden ? "none" : "";
  });
}

// The banner's message again, for a control reached while paused anyway
// (an Import dialog that was open when the conflict arrived, Enter in a
// Replace box). toasts.js is a classic script: Toast is a global binding,
// absent under the Node tests.
export function notifyPaused() {
  if (typeof Toast === "undefined") return;
  Toast.warning(
    "This note was changed somewhere else (another tab, another person or the AI). Reload latest to continue.",
    "Editing is paused",
  );
}

// Re-fetch the open note through the normal swap pipeline (editor
// rebuild + fresh NOTE_DATA); ?sync=1 keeps background reloads out of
// the recency trail
export function reloadNoteContent() {
  window.htmx.ajax(
    "GET",
    `${window.NOTE_DATA.contentPartialUrl}?sync=1`,
    { target: "#note-editor-container", swap: "innerHTML" },
  );
}

function updateSaveStatus(status) {
  const btn = document.getElementById("save-status-btn");
  if (!btn) return;

  const icon = btn.querySelector("i");
  if (!icon) return;

  if (status === "conflict") {
    icon.className = "icon-triangle-alert";
    btn.classList.add("active");
    btn.title = "This note was changed somewhere else. Reload to continue.";
    return;
  }

  // Same disk glyph either way — the .active urgent tint signals unsaved
  icon.className = "icon-save";
  if (status === "saved") {
    btn.classList.remove("active");
    btn.title = "Saved";
  } else {
    btn.classList.add("active");
    btn.title = status === "saving" ? "Saving..." : "Unsaved changes";
  }
}

// ─── Unload flush ────────────────────────────────────────────────────────────

// Closing a tab inside the 2s debounce window would lose the edit;
// keepalive lets the request outlive the page (sendBeacon can't carry
// the CSRF header). base_version keeps a closing stale tab from
// stomping newer work. Bodies over ~64KB may be dropped by the browser;
// the regular debounced saves make that loss window tiny.
window.addEventListener("pagehide", () => {
  if (state.conflict || !state.editor) return;
  if (window.NOTE_DATA && window.NOTE_DATA.readOnly) return;
  const content = getMarkdownContent();
  if (content === state.lastSavedContent) return;
  const formData = new FormData();
  formData.append("content", content);
  formData.append("base_version", window.NOTE_DATA.updatedAt || "");
  fetch(window.NOTE_DATA.autosaveUrl, {
    method: "POST",
    headers: { "X-CSRFToken": getCSRFToken() },
    body: formData,
    keepalive: true,
  });
});
