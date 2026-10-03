// Outline panel — heading navigation and collapse for the notes editor

import { state } from "./state.js";

export function buildOutline() {
  const outlineList = document.getElementById("outline-list");
  if (!outlineList || !state.editor) return;

  const headings = [];
  state.editor.state.doc.descendants((node, pos) => {
    if (node.type.name === "heading" && node.attrs.level >= 2) {
      headings.push({
        level: node.attrs.level,
        text: node.textContent.trim(),
        pos,
      });
    }
  });

  if (headings.length === 0) {
    outlineList.innerHTML = '<li class="outline-empty">No headings</li>';

    return;
  }

  const noteId = window.NOTE_DATA ? window.NOTE_DATA.id : "default";
  const storageKey = "outline-collapsed-" + noteId;

  let collapsedItems = [];
  try {
    collapsedItems = JSON.parse(sessionStorage.getItem(storageKey)) || [];
  } catch {
    collapsedItems = [];
  }

  // Heading text is whatever someone typed into the note, so it goes in
  // through textContent, never parsed as markup
  function buildItems(items) {
    const fragment = document.createDocumentFragment();
    let i = 0;

    while (i < items.length) {
      const heading = items[i];

      const children = [];
      let j = i + 1;

      while (j < items.length && items[j].level > heading.level) {
        children.push(items[j]);
        j++;
      }

      const li = document.createElement("li");
      li.className = "outline-item level-" + heading.level;
      li.dataset.pos = heading.pos;

      const textEl = document.createElement("span");
      textEl.className = "outline-text";
      textEl.textContent = heading.text || "(empty)";

      if (children.length > 0) {
        li.classList.add("has-children");
        if (collapsedItems.includes(heading.pos)) li.classList.add("collapsed");

        const toggle = document.createElement("span");
        toggle.className = "outline-toggle";
        const chevron = document.createElement("i");
        chevron.className = "icon-chevron-down";
        toggle.appendChild(chevron);

        const childList = document.createElement("ul");
        childList.className = "outline-children";
        childList.appendChild(buildItems(children));

        li.append(toggle, textEl, childList);
      } else {
        const spacer = document.createElement("span");
        spacer.className = "outline-toggle-spacer";
        li.append(spacer, textEl);
      }

      fragment.appendChild(li);
      i = j;
    }

    return fragment;
  }

  outlineList.replaceChildren(buildItems(headings));

  outlineList.querySelectorAll(".outline-toggle").forEach((toggle) => {
    toggle.addEventListener("click", (e) => {
      e.stopPropagation();

      const item = toggle.closest(".outline-item");
      if (!item) return;

      item.classList.toggle("collapsed");

      const pos = parseInt(item.dataset.pos, 10);
      if (item.classList.contains("collapsed")) {
        if (!collapsedItems.includes(pos)) collapsedItems.push(pos);
      } else {
        collapsedItems = collapsedItems.filter((p) => p !== pos);
      }

      sessionStorage.setItem(storageKey, JSON.stringify(collapsedItems));
    });
  });

  outlineList.querySelectorAll(".outline-text").forEach((textEl) => {
    textEl.addEventListener("click", () => {
      const item = textEl.closest(".outline-item");
      if (item) scrollToHeading(parseInt(item.dataset.pos, 10));
    });
  });

  outlineList
    .querySelectorAll(".outline-item:not(.has-children)")
    .forEach((item) => {
      if (!item.querySelector(".outline-toggle")) {
        item.style.cursor = "pointer";
        item.addEventListener("click", () =>
          scrollToHeading(parseInt(item.dataset.pos, 10)),
        );
      }
    });

  updateCollapseButtonIcon();
  updateOutlineActive();
}

// Highlight the heading the cursor sits under: the last outline heading at
// or before the selection start. Runs on every selection change (cheap -
// one doc walk) and after each outline rebuild, whose fresh data-pos
// values it needs; between keystroke and debounced rebuild the positions
// can be momentarily stale, in which case no item matches and the
// highlight simply catches up on the rebuild.
export function updateOutlineActive() {
  const outlineList = document.getElementById("outline-list");
  if (!outlineList || !state.editor) return;

  const from = state.editor.state.selection.from;
  let activePos = null;
  state.editor.state.doc.descendants((node, pos) => {
    if (node.type.name === "heading" && node.attrs.level >= 2 && pos <= from) {
      activePos = pos;
    }
  });

  let activeItem = null;
  outlineList.querySelectorAll(".outline-item").forEach((item) => {
    const isActive = parseInt(item.dataset.pos, 10) === activePos;
    item.classList.toggle("active", isActive);
    if (isActive) activeItem = item;
  });

  if (activeItem) activeItem.scrollIntoView({ block: "nearest" });
}

function scrollToHeading(pos) {
  if (!state.editor) return;

  // Place the cursor in the heading (pos + 1 = inside the node): typing
  // continues there, and the selection change drives the active highlight.
  state.editor.commands.focus(pos + 1);

  const domAtPos = state.editor.view.domAtPos(pos + 1);
  if (!domAtPos || !domAtPos.node) return;

  let element = domAtPos.node;
  if (element.nodeType === Node.TEXT_NODE) element = element.parentElement;

  const heading = element.closest("h1, h2, h3, h4, h5, h6");
  if (!heading) return;

  const notePage = document.querySelector(".note-page");
  if (notePage) {
    const headingRect = heading.getBoundingClientRect();
    const containerRect = notePage.getBoundingClientRect();
    const scrollTop =
      notePage.scrollTop + (headingRect.top - containerRect.top) - 32;
    notePage.scrollTo({ top: Math.max(0, scrollTop), behavior: "smooth" });
  }
}

export function scheduleOutlineUpdate() {
  if (state.outlineTimer) clearTimeout(state.outlineTimer);

  state.outlineTimer = setTimeout(buildOutline, 500);
}

export function setupOutlineCollapseAll() {
  const btn = document.getElementById("outline-collapse-btn");
  if (!btn) return;

  btn.addEventListener("click", () => {
    const outlineList = document.getElementById("outline-list");
    if (!outlineList) return;

    const collapsibleItems = outlineList.querySelectorAll(
      ".outline-item.has-children",
    );
    if (collapsibleItems.length === 0) return;

    const allCollapsed = Array.from(collapsibleItems).every((item) =>
      item.classList.contains("collapsed"),
    );

    const noteId = window.NOTE_DATA ? window.NOTE_DATA.id : "default";
    const storageKey = "outline-collapsed-" + noteId;
    const collapsedPositions = [];

    collapsibleItems.forEach((item) => {
      if (allCollapsed) {
        item.classList.remove("collapsed");
      } else {
        item.classList.add("collapsed");
        const pos = parseInt(item.dataset.pos, 10);
        if (!isNaN(pos)) collapsedPositions.push(pos);
      }
    });

    sessionStorage.setItem(storageKey, JSON.stringify(collapsedPositions));
    updateCollapseButtonIcon();
  });
}

function updateCollapseButtonIcon() {
  const btn = document.getElementById("outline-collapse-btn");
  const outlineList = document.getElementById("outline-list");

  if (!btn || !outlineList) return;

  const icon = btn.querySelector("i");
  if (!icon) return;

  const collapsibleItems = outlineList.querySelectorAll(
    ".outline-item.has-children",
  );
  const allCollapsed =
    collapsibleItems.length > 0 &&
    Array.from(collapsibleItems).every((item) =>
      item.classList.contains("collapsed"),
    );

  icon.className = allCollapsed
    ? "icon-chevrons-up-down"
    : "icon-chevrons-down-up";
}
