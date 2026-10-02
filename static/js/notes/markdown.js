// Markdown - HTML conversion for the notes editor

import { escapeHtml } from "./state.js";

// Reference chips are stored as [[doc:12|label]] / [[hl:34|label]].
const REF_TOKEN = /\[\[(doc|hl):(\d+)\|([^\]]+)\]\]/g;
const REF_TYPES = { doc: "document", hl: "highlight" };

// A letter, digit or underscore: what an underscore must NOT touch on its
// outer side to count as emphasis (see formatInline).
const WORD = "[\\p{L}\\p{N}_]";
// Underscore emphasis, CommonMark-style: the run opens after a non-word
// character and closes before one, and its inside neither starts nor ends
// with a space or another underscore. So Smith_Depo_Vol1.pdf,
// snake_case_names and blanks like "Signed: ______" stay literal text.
const underscoreRun = (marks) =>
  new RegExp(
    `(?<!${WORD})${marks}(?=[^\\s_])(.+?)(?<=[^\\s_])${marks}(?!${WORD})`,
    "gu",
  );
const UNDERSCORE_BOLD_ITALIC = underscoreRun("___");
const UNDERSCORE_BOLD = underscoreRun("__");
const UNDERSCORE_ITALIC = underscoreRun("_");

// One line of stored markdown -> editor HTML.
//
// The stored text is plain text plus markdown marks: nothing in it is HTML.
// So everything is escaped before the marks are turned into tags;
// otherwise "<jsmith@example.com>" or "x<y" reads as a tag and the editor
// silently drops it, and the next save writes the note back without it.
// Pieces that must come through exactly (code spans, reference chips, link
// addresses) are lifted out first and put back last, so neither the
// escaping nor the emphasis rules can touch them.
function formatInline(text) {
  // NUL marks the held pieces below; stored text never contains one
  // (the database refuses it), so drop any that arrive by paste
  text = text.replace(/\x00/g, "");
  const held = [];
  const hold = (html) => {
    held.push(html);
    return "\x00" + (held.length - 1) + "\x00";
  };

  text = text.replace(/`([^`]+)`/g, (_m, code) =>
    hold("<code>" + escapeHtml(code) + "</code>"),
  );

  text = text.replace(REF_TOKEN, (_m, kind, id, label) =>
    hold(
      '<span class="note-ref" data-type="' +
        REF_TYPES[kind] +
        '" data-id="' +
        id +
        '">' +
        escapeHtml(label) +
        "</span>",
    ),
  );

  // The editor has no link mark, so a markdown link can't stay a link; it
  // becomes its text followed by the address in parentheses, which keeps
  // the address when the note is saved again.
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, label, address) =>
    label === address
      ? hold(escapeHtml(address))
      : label + " (" + hold(escapeHtml(address)) + ")",
  );

  text = escapeHtml(text)
    .replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>")
    .replace(UNDERSCORE_BOLD_ITALIC, "<strong><em>$1</em></strong>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(UNDERSCORE_BOLD, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(UNDERSCORE_ITALIC, "<em>$1</em>")
    .replace(/~~(.+?)~~/g, "<s>$1</s>")
    .replace(/g==(.+?)==/g, '<mark data-color="mark-green">$1</mark>')
    .replace(/r==(.+?)==/g, '<mark data-color="mark-red">$1</mark>')
    .replace(/p==(.+?)==/g, '<mark data-color="mark-purple">$1</mark>')
    .replace(/o==(.+?)==/g, '<mark data-color="mark-orange">$1</mark>')
    .replace(/c==(.+?)==/g, '<mark data-color="mark-citation">$1</mark>')
    .replace(/a==(.+?)==/g, '<mark data-color="mark-gray">$1</mark>')
    .replace(/==(.+?)==/g, "<mark>$1</mark>");

  // Last held first: a held piece can contain an earlier one (a code span
  // inside a chip's label), never a later one. The function form keeps a
  // "$" in the held text from being read as a replacement pattern.
  for (let i = held.length - 1; i >= 0; i--) {
    text = text.replaceAll("\x00" + i + "\x00", () => held[i]);
  }
  return text;
}

// GFM pipe tables. Rows must carry outer pipes (| a | b |) — that's what
// every table the AI emits and every hand-typed table looks like, and it
// keeps prose containing stray pipes from parsing as a table. Column
// alignment colons are accepted but not preserved (the editor's table
// has no per-column alignment to store them in).
export function isPipeRow(line) {
  return line.length > 1 && line.startsWith("|") && line.indexOf("|", 1) !== -1;
}

export function isTableSeparator(line) {
  return /^\|(\s*:?-+:?\s*\|)+\s*$/.test(line);
}

// Column alignment lives in the separator row's colons (:-- / :-: / --:).
// null means "no explicit alignment" and round-trips as plain dashes.
export function separatorAligns(line) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((seg) => {
      const s = seg.trim();
      const left = s.startsWith(":");
      const right = s.endsWith(":");
      if (left && right) return "center";
      if (right) return "right";
      if (left) return "left";
      return null;
    });
}

const ALIGN_DASHES = { left: ":--", center: ":-:", right: "--:" };

export function alignsToSeparator(aligns) {
  return (
    "| " + aligns.map((a) => ALIGN_DASHES[a] || "---").join(" | ") + " |"
  );
}

// Cells split on unescaped pipes. A reference token carries a pipe of its
// own ([[doc:1|label]]) which is syntax, not a cell boundary (the save
// side leaves it unescaped for the same reason).
export function splitPipeRow(line) {
  const inner = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  const cells = [""];
  const piece = /\[\[(?:doc|hl):\d+\|[^\]]+\]\]|\\\||\||[^|\\[]+|[\\[]/g;
  for (const [part] of inner.matchAll(piece)) {
    if (part === "|") cells.push("");
    else cells[cells.length - 1] += part === "\\|" ? "|" : part;
  }
  return cells.map((c) => c.trim());
}

export function buildTableHtml(header, rows, aligns) {
  const width = Math.max(header.length, ...rows.map((r) => r.length), 1);
  const cell = (tag, content, align) =>
    "<" +
    tag +
    (align ? ' style="text-align: ' + align + '"' : "") +
    "><p>" +
    formatInline(content || "") +
    "</p></" +
    tag +
    ">";
  const row = (tag, cells) => {
    let html = "<tr>";
    for (let c = 0; c < width; c++) {
      html += cell(tag, cells[c], aligns ? aligns[c] : null);
    }
    return html + "</tr>";
  };
  return (
    "<table><tbody>" +
    row("th", header) +
    rows.map((r) => row("td", r)).join("") +
    "</tbody></table>"
  );
}

function buildBlockquote(lines, minDepth) {
  let html = "<blockquote>";
  let j = 0;
  while (j < lines.length) {
    if (lines[j].depth === minDepth) {
      html += "<p>" + lines[j].content + "</p>";
      j++;
    } else if (lines[j].depth > minDepth) {
      const nested = [];
      while (j < lines.length && lines[j].depth > minDepth) {
        nested.push(lines[j]);
        j++;
      }
      html += buildBlockquote(nested, minDepth + 1);
    } else {
      break;
    }
  }
  return html + "</blockquote>";
}

export function markdownToHtml(md) {
  if (!md) return "<p></p>";

  const lines = md.split(/\r?\n/);
  const parsed = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      parsed.push({ type: "blank" });
      continue;
    }

    // Fenced code blocks
    const codeBlockMatch = trimmed.match(/^```(\w*)$/);
    if (codeBlockMatch) {
      const lang = codeBlockMatch[1] || null;
      const codeLines = [];
      i++;

      while (i < lines.length && !lines[i].trim().match(/^```$/)) {
        codeLines.push(lines[i]);
        i++;
      }
      parsed.push({
        type: "codeblock",
        content: escapeHtml(codeLines.join("\n")),
        lang,
      });
      continue;
    }

    // Horizontal rules
    if (/^[-*_]{3,}$/.test(trimmed) && !/^[-*] /.test(trimmed)) {
      parsed.push({ type: "hr" });
      continue;
    }

    // Headers
    const headerMatch = trimmed.match(/^(#{1,5}) (.+)$/);
    if (headerMatch) {
      parsed.push({
        type: "header",
        level: headerMatch[1].length,
        content: formatInline(headerMatch[2]),
      });
      continue;
    }

    // Blockquotes (supports nesting)
    if (trimmed.startsWith("> ") || trimmed === ">") {
      let bqDepth = 0;
      let bqRest = trimmed;
      while (bqRest.startsWith("> ") || bqRest === ">") {
        bqDepth++;
        bqRest = bqRest.startsWith("> ") ? bqRest.substring(2) : "";
      }
      parsed.push({
        type: "blockquote",
        depth: bqDepth,
        content: formatInline(bqRest),
      });
      continue;
    }

    // Unordered list items
    const ulMatch = line.replace(/\r$/, "").match(/^([ \t]*)[-*] (.*)$/);
    if (ulMatch) {
      const depth = Math.floor(ulMatch[1].replace(/\t/g, "  ").length / 2);
      parsed.push({
        type: "li",
        listType: "ul",
        depth,
        content: formatInline(ulMatch[2] || ""),
      });
      continue;
    }

    // Ordered list items
    const olMatch = line.replace(/\r$/, "").match(/^([ \t]*)(\d+)\. (.*)$/);
    if (olMatch) {
      const depth = Math.floor(olMatch[1].replace(/\t/g, "  ").length / 2);
      parsed.push({
        type: "li",
        listType: "ol",
        depth,
        content: formatInline(olMatch[3] || ""),
      });
      continue;
    }

    // Tables: a pipe row followed by a separator row starts one; body rows
    // run until the first non-pipe line (which the outer loop re-reads).
    if (
      isPipeRow(trimmed) &&
      i + 1 < lines.length &&
      isTableSeparator(lines[i + 1].trim())
    ) {
      const header = splitPipeRow(trimmed);
      const aligns = separatorAligns(lines[i + 1].trim());
      const rows = [];
      i += 2;
      while (i < lines.length && isPipeRow(lines[i].trim())) {
        rows.push(splitPipeRow(lines[i].trim()));
        i++;
      }
      i--;
      parsed.push({ type: "table", header, aligns, rows });
      continue;
    }

    // Regular paragraph
    parsed.push({ type: "paragraph", content: formatInline(trimmed) });
  }

  // Build HTML
  const result = [];
  let i = 0;

  function buildList(startIndex, minDepth) {
    let idx = startIndex;
    const items = [];

    while (
      idx < parsed.length &&
      parsed[idx].type === "li" &&
      parsed[idx].depth >= minDepth
    ) {
      if (parsed[idx].depth > minDepth) break;

      const item = parsed[idx];
      let liContent = "<li><p>" + item.content + "</p>";
      idx++;

      if (
        idx < parsed.length &&
        parsed[idx].type === "li" &&
        parsed[idx].depth > minDepth
      ) {
        const nested = buildList(idx, parsed[idx].depth);
        liContent += nested.html;
        idx = nested.endIndex;
      }

      liContent += "</li>";
      items.push({ html: liContent, listType: item.listType });
    }

    if (items.length === 0) return { html: "", endIndex: idx };

    const tag = items[0].listType;
    return {
      html:
        "<" +
        tag +
        ">" +
        items.map((it) => it.html).join("") +
        "</" +
        tag +
        ">",
      endIndex: idx,
    };
  }

  while (i < parsed.length) {
    const item = parsed[i];

    if (item.type === "blank") {
      i++;
      continue;
    }

    if (item.type === "header") {
      result.push(
        "<h" + item.level + ">" + item.content + "</h" + item.level + ">",
      );
      i++;
      continue;
    }

    if (item.type === "blockquote") {
      const bqLines = [];
      while (i < parsed.length && parsed[i].type === "blockquote") {
        bqLines.push(parsed[i]);
        i++;
      }
      result.push(buildBlockquote(bqLines, 1));
      continue;
    }

    if (item.type === "codeblock") {
      const langAttr = item.lang ? ' class="language-' + item.lang + '"' : "";
      result.push(
        "<pre><code" + langAttr + ">" + item.content + "</code></pre>",
      );
      i++;
      continue;
    }

    if (item.type === "hr") {
      result.push("<hr>");
      i++;
      continue;
    }

    if (item.type === "paragraph") {
      result.push("<p>" + item.content + "</p>");
      i++;
      continue;
    }

    if (item.type === "table") {
      result.push(buildTableHtml(item.header, item.rows, item.aligns));
      i++;
      continue;
    }

    if (item.type === "li") {
      const listResult = buildList(i, item.depth);
      result.push(listResult.html);
      i = listResult.endIndex;
      continue;
    }

    i++;
  }

  return result.join("") || "<p></p>";
}

const HIGHLIGHT_PREFIXES = {
  "mark-green": "g==",
  "mark-red": "r==",
  "mark-purple": "p==",
  "mark-orange": "o==",
  "mark-citation": "c==",
  "mark-gray": "a==",
};

export function htmlToMarkdown(html) {
  const tempDiv = document.createElement("div");
  tempDiv.innerHTML = html;

  function processNode(node, listDepth, listType, listIndex) {
    if (node.nodeType === Node.TEXT_NODE) return node.textContent;
    if (node.nodeType !== Node.ELEMENT_NODE) return "";

    const tag = node.tagName.toLowerCase();

    function getChildren() {
      return Array.from(node.childNodes)
        .map((child) => processNode(child, listDepth, null, 0))
        .join("");
    }

    // Headings (h1-h5)
    const headingLevel = /^h([1-5])$/.exec(tag);
    if (headingLevel) {
      return (
        "#".repeat(parseInt(headingLevel[1])) + " " + getChildren() + "\n\n"
      );
    }

    switch (tag) {
      case "p":
        return listDepth > 0 ? getChildren() : getChildren() + "\n\n";
      case "strong":
        return "**" + getChildren() + "**";
      case "em":
        return "*" + getChildren() + "*";
      case "s":
        return "~~" + getChildren() + "~~";
      case "mark": {
        const color = node.dataset.color || "";
        for (const [cls, prefix] of Object.entries(HIGHLIGHT_PREFIXES)) {
          if (node.classList.contains(cls) || color === cls) {
            return prefix + getChildren() + "==";
          }
        }
        return "==" + getChildren() + "==";
      }
      case "code":
        if (
          node.parentElement &&
          node.parentElement.tagName.toLowerCase() === "pre"
        ) {
          return node.textContent;
        }
        return "`" + node.textContent + "`";
      case "pre": {
        let lang = "";
        const codeEl = node.querySelector("code");
        if (codeEl) {
          const langClass = Array.from(codeEl.classList).find((c) =>
            c.startsWith("language-"),
          );
          if (langClass) lang = langClass.replace("language-", "");
        }
        return "```" + lang + "\n" + getChildren() + "\n```\n\n";
      }
      case "hr":
        return "---\n\n";
      case "blockquote":
        return (
          getChildren()
            .trim()
            .split("\n")
            .map((line) => "> " + line)
            .join("\n") + "\n\n"
        );
      case "ul":
      case "ol": {
        let result = "";
        let idx = 1;
        Array.from(node.children).forEach((child) => {
          if (child.tagName.toLowerCase() === "li") {
            result += processNode(child, listDepth + 1, tag, idx);
            idx++;
          }
        });
        return listDepth === 0 ? result + "\n" : result;
      }
      case "li": {
        const indent = "  ".repeat(listDepth - 1);
        const prefix = listType === "ol" ? listIndex + ". " : "- ";

        let textContent = "";
        let nestedLists = "";

        Array.from(node.childNodes).forEach((child) => {
          if (child.nodeType === Node.ELEMENT_NODE) {
            const childTag = child.tagName.toLowerCase();
            if (childTag === "ul" || childTag === "ol") {
              nestedLists += processNode(child, listDepth, null, 0);
            } else {
              textContent += processNode(child, listDepth, null, 0);
            }
          } else {
            textContent += processNode(child, listDepth, null, 0);
          }
        });

        return indent + prefix + textContent.trim() + "\n" + nestedLists;
      }
      case "table": {
        // Pipe syntax can't express merged cells or block content, so cells
        // flatten to one line of inline markdown and literal pipes escape.
        const cellText = (cell) =>
          Array.from(cell.childNodes)
            .map((child) => processNode(child, 0, null, 0))
            .join("")
            .replace(/\s*\n\s*/g, " ")
            .trim()
            // Escape literal pipes, but not the one inside a reference
            // token ([[doc:1|label]]) — that pipe is syntax the loader's
            // ref regex must still match.
            .replace(/\[\[(?:doc|hl):\d+\|[^\]]+\]\]|\|/g, (m) =>
              m === "|" ? "\\|" : m,
            );
        const grid = Array.from(node.rows).map((tr) =>
          Array.from(tr.cells).map(cellText),
        );
        if (!grid.length) return "";
        const width = Math.max(...grid.map((r) => r.length));
        const line = (cells) => {
          const padded = cells.concat(Array(width - cells.length).fill(""));
          return "| " + padded.join(" | ") + " |";
        };
        // Column alignment reads off the header row's text-align styles
        // and becomes the separator's colons
        const headerCells = Array.from(node.rows[0].cells);
        const aligns = Array.from({ length: width }, (_, c) => {
          const cellEl = headerCells[c];
          return (cellEl && cellEl.style.textAlign) || null;
        });
        const separator = alignsToSeparator(aligns);
        const [head, ...body] = grid;
        return [line(head), separator, ...body.map(line)].join("\n") + "\n\n";
      }
      case "br":
        return "\n";
      case "span":
        if (
          node.classList.contains("note-ref") ||
          node.getAttribute("data-type")
        ) {
          const refType = node.getAttribute("data-type");
          const refId = node.getAttribute("data-id");
          const label = node.textContent || getChildren();
          if (refType === "document")
            return "[[doc:" + refId + "|" + label + "]]";
          if (refType === "highlight")
            return "[[hl:" + refId + "|" + label + "]]";
        }
        // Highlights render as span.note-hl (highlight-mark.js) — same
        // colored syntax the <mark> case below covers for legacy HTML.
        if (node.classList.contains("note-hl")) {
          const color = node.dataset.color || "";
          return (HIGHLIGHT_PREFIXES[color] || "==") + getChildren() + "==";
        }
        return getChildren();
      default:
        return getChildren();
    }
  }

  return processNode(tempDiv, 0, null, 0)
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
