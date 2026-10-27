// A very small DOM for running the notes editor's plain modules under Node,
// which has none. It covers only what markdown.js, outline.js and
// autosave.js touch.
//
// The HTML parser is deliberately browser-like about one thing: any
// "<name ...>" is a tag, known or not. That is what makes unescaped note
// text dangerous (a "<jsmith@example.com>" becomes an empty unknown
// element and its text is gone; an "<img onerror=...>" becomes an element),
// so tests built on this shim fail when text reaches innerHTML unescaped.

const VOID_TAGS = new Set(["br", "hr", "img", "input"]);

const ENTITIES = { amp: "&", lt: "<", gt: ">", quot: '"', "#39": "'" };

function decodeEntities(text) {
  return text.replace(/&(amp|lt|gt|quot|#39);/g, (_m, name) => ENTITIES[name]);
}

class TextNode {
  constructor(text) {
    this.nodeType = 3;
    this.textContent = text;
    this.parentElement = null;
  }
}

function matchesSimple(el, selector) {
  // "tag", ".a", ".a.b", ".a:not(.b)", "[data-x]" (attribute present)
  const not = /:not\(\.([\w-]+)\)/.exec(selector);
  if (not && el.classList.contains(not[1])) return false;
  const bare = selector.replace(/:not\([^)]*\)/, "");
  const tag = /^[a-z0-9]+/i.exec(bare);
  if (tag && el.tagName.toLowerCase() !== tag[0].toLowerCase()) return false;
  const attrs = [...bare.matchAll(/\[([\w-]+)\]/g)].map((m) => m[1]);
  if (!attrs.every((a) => a in el.attrs)) return false;
  const classes = [...bare.matchAll(/\.([\w-]+)/g)].map((m) => m[1]);
  return classes.every((c) => el.classList.contains(c));
}

class ClassList {
  constructor(el) {
    this.el = el;
  }
  get names() {
    return (this.el.attrs.class || "").split(/\s+/).filter(Boolean);
  }
  contains(name) {
    return this.names.includes(name);
  }
  add(name) {
    if (!this.contains(name)) this.el.attrs.class = [...this.names, name].join(" ");
  }
  remove(name) {
    this.el.attrs.class = this.names.filter((n) => n !== name).join(" ");
  }
  toggle(name, force) {
    const on = force === undefined ? !this.contains(name) : force;
    if (on) this.add(name);
    else this.remove(name);
    return on;
  }
  [Symbol.iterator]() {
    return this.names[Symbol.iterator]();
  }
}

class Element {
  constructor(tag, attrs = {}) {
    this.nodeType = 1;
    this.tagName = tag.toUpperCase();
    this.attrs = attrs;
    this.childNodes = [];
    this.parentElement = null;
    this.classList = new ClassList(this);
    this.innerHTMLWrites = []; // every string assigned to innerHTML
    const el = this;
    this.dataset = new Proxy(
      {},
      {
        get: (_t, key) => el.attrs["data-" + String(key)],
        set: (_t, key, value) => {
          el.attrs["data-" + String(key)] = String(value);
          return true;
        },
      },
    );
    this.style = {
      get textAlign() {
        const m = /text-align:\s*([a-z]+)/.exec(el.attrs.style || "");
        return m ? m[1] : "";
      },
    };
  }

  get className() {
    return this.attrs.class || "";
  }
  set className(value) {
    this.attrs.class = value;
  }

  get children() {
    return this.childNodes.filter((n) => n.nodeType === 1);
  }

  get textContent() {
    return this.childNodes.map((n) => n.textContent).join("");
  }
  set textContent(value) {
    this.childNodes = [];
    this.appendChild(new TextNode(String(value)));
  }

  set innerHTML(html) {
    this.innerHTMLWrites.push(html);
    this.childNodes = [];
    parseInto(this, html);
  }

  getAttribute(name) {
    return name in this.attrs ? this.attrs[name] : null;
  }

  appendChild(node) {
    if (node instanceof Fragment) {
      node.childNodes.splice(0).forEach((child) => this.appendChild(child));
      return node;
    }
    node.parentElement = this;
    this.childNodes.push(node);
    return node;
  }
  append(...nodes) {
    nodes.forEach((n) => this.appendChild(n));
  }
  replaceChildren(...nodes) {
    this.childNodes = [];
    this.append(...nodes);
  }

  get descendants() {
    return this.children.flatMap((c) => [c, ...c.descendants]);
  }
  querySelectorAll(selector) {
    return this.descendants.filter((el) => matchesSimple(el, selector));
  }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }
  closest(selector) {
    let el = this;
    while (el && !matchesSimple(el, selector)) el = el.parentElement;
    return el;
  }

  // Tables
  get rows() {
    return this.querySelectorAll("tr");
  }
  get cells() {
    return this.children.filter((c) => /^(TD|TH)$/.test(c.tagName));
  }

  addEventListener() {}
  dispatchEvent(event) {
    this.dispatched = [...(this.dispatched || []), event.type];
    return true;
  }
  scrollIntoView() {}
}

class Fragment extends Element {
  constructor() {
    super("#fragment");
  }
}

const TAG = /<(\/?)([a-zA-Z][^\s>/]*)([^>]*)>/g;
const ATTR = /([^\s=/]+)(?:=(?:"([^"]*)"|'([^']*)'|([^\s"'>]+)))?/g;

function parseInto(root, html) {
  let current = root;
  let last = 0;
  const text = (chunk) => {
    if (chunk) current.appendChild(new TextNode(decodeEntities(chunk)));
  };
  for (const m of html.matchAll(TAG)) {
    text(html.slice(last, m.index));
    last = m.index + m[0].length;
    const [, closing, name, rawAttrs] = m;
    if (closing) {
      // Close up to the nearest open element of that name, if there is one
      let el = current;
      while (el !== root && el.tagName !== name.toUpperCase()) el = el.parentElement;
      if (el !== root) current = el.parentElement;
      continue;
    }
    const attrs = {};
    for (const a of rawAttrs.matchAll(ATTR)) {
      attrs[a[1]] = decodeEntities(a[2] ?? a[3] ?? a[4] ?? "");
    }
    const el = current.appendChild(new Element(name, attrs));
    if (!VOID_TAGS.has(name.toLowerCase())) current = el;
  }
  text(html.slice(last));
}

// Installs the globals the editor modules expect. `elements` maps an id to
// the element getElementById should return.
export function installDom(elements = {}) {
  const store = new Map();
  globalThis.Node = { TEXT_NODE: 3, ELEMENT_NODE: 1 };
  const body = new Element("body");
  globalThis.document = {
    body,
    createElement: (tag) => new Element(tag),
    createDocumentFragment: () => new Fragment(),
    getElementById: (id) => elements[id] || null,
    querySelector: (selector) => body.querySelector(selector),
    querySelectorAll: (selector) => body.querySelectorAll(selector),
  };
  globalThis.window = globalThis;
  globalThis.addEventListener = () => {}; // window.addEventListener
  globalThis.sessionStorage = {
    getItem: (key) => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
  };
}

export function createElement(tag) {
  return new Element(tag);
}
