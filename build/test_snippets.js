#!/usr/bin/env node
// test_snippets.js -- Prove the generated snippets load and expand.
//
// Loads the REAL HyperSnips parser and matcher from your installed extension,
// with a small fake `vscode` module, then types test cases at the end of a
// fake document and checks what would be inserted.
//
//     node build/test_snippets.js
//
// This catches the failure modes that are otherwise silent inside VS Code:
// a file that doesn't parse (every snippet dead), triggers that never match,
// wrong maths/text context, bad escaping, tabstops in the wrong order.

const fs = require('fs');
const os = require('os');
const path = require('path');
const Module = require('module');

const ROOT = path.resolve(__dirname, '..');

// ---- locate HyperSnips -------------------------------------------------------
const extDir = path.join(os.homedir(), '.vscode', 'extensions');
const hsnipsDir = fs.existsSync(extDir)
  ? fs.readdirSync(extDir).filter((d) => d.startsWith('draivin.hsnips-')).sort().pop()
  : null;
if (!hsnipsDir) {
  console.error('HyperSnips (draivin.hsnips) is not installed.');
  process.exit(2);
}
const OUT = path.join(extDir, hsnipsDir, 'out');

// ---- fake vscode -------------------------------------------------------------
class Position {
  constructor(line, character) { this.line = line; this.character = character; }
  translate(dl = 0, dc = 0) {
    if (typeof dl === 'object') { dc = dl.characterDelta || 0; dl = dl.lineDelta || 0; }
    return new Position(this.line + dl, this.character + dc);
  }
  isEqual(o) { return o.line === this.line && o.character === this.character; }
}
class Range {
  constructor(a, b, c, d) {
    if (typeof a === 'number') { this.start = new Position(a, b); this.end = new Position(c, d); }
    else { this.start = a; this.end = b; }
  }
}
function stub() {
  const fn = function () { return stub(); };
  return new Proxy(fn, { get: () => stub(), construct: () => stub(), apply: () => stub() });
}
const vscodeMock = new Proxy({
  Position,
  Range,
  SnippetString: class { constructor(v) { this.value = v; } },
  window: { activeTextEditor: null, showWarningMessage() {} },
  workspace: { getConfiguration: () => ({ get: () => undefined }), workspaceFolders: [] },
  extensions: { getExtension: () => ({ exports: { getScopeAt: () => ({ scopes: [] }) }, activate() {} }) },
}, { get: (t, k) => (k in t ? t[k] : stub()) });

const originalLoad = Module._load;
Module._load = function (request) {
  if (request === 'vscode') return vscodeMock;
  return originalLoad.apply(this, arguments);
};

const { parse } = require(path.join(OUT, 'parser.js'));
const { getCompletions } = require(path.join(OUT, 'completion.js'));

// ---- fake document -----------------------------------------------------------
function makeDoc(text, languageId) {
  const lines = text.split('\n');
  const offsetAt = (p) => {
    let o = 0;
    for (let i = 0; i < p.line; i++) o += lines[i].length + 1;
    return o + p.character;
  };
  return {
    languageId,
    // Real VS Code bumps this on every edit; the context cache keys on it.
    version: (makeDoc.version = (makeDoc.version || 0) + 1),
    uri: { toString: () => 'test://' + languageId, fsPath: '/test' },
    lineCount: lines.length,
    getText(r) { return r ? text.slice(offsetAt(r.start), offsetAt(r.end)) : text; },
    lineAt(l) { return { text: lines[typeof l === 'number' ? l : l.line] }; },
    offsetAt,
    getWordRangeAtPosition(p) {
      const line = lines[p.line];
      const w = /[A-Za-z0-9_]/;
      let s = p.character, e = p.character;
      while (s > 0 && w.test(line[s - 1])) s--;
      while (e < line.length && w.test(line[e])) e++;
      return s === e ? undefined : new Range(new Position(p.line, s), new Position(p.line, e));
    },
  };
}

// Render VS Code snippet syntax the way the editor would, marking tabstops.
function renderSnippet(s) {
  let out = '';
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (c === '\\' && i + 1 < s.length && '\\$}'.includes(s[i + 1])) { out += s[i + 1]; i++; continue; }
    if (c === '$') {
      const rest = s.slice(i);
      let m;
      if ((m = /^\$(\d+)/.exec(rest)) || (m = /^\$\{(\d+)\}/.exec(rest))) {
        out += '<' + m[1] + '>'; i += m[0].length - 1; continue;
      }
      if ((m = /^\$\{(\d+):/.exec(rest))) {
        let j = i + m[0].length, def = '';
        while (j < s.length && s[j] !== '}') {
          if (s[j] === '\\' && '\\$}'.includes(s[j + 1])) { def += s[j + 1]; j += 2; continue; }
          def += s[j]; j++;
        }
        out += '<' + m[1] + ':' + def + '>'; i = j; continue;
      }
    }
    out += c;
  }
  return out;
}

function expand(snippets, languageId, before) {
  const doc = makeDoc(before, languageId);
  const lines = before.split('\n');
  const pos = new Position(lines.length - 1, lines[lines.length - 1].length);
  vscodeMock.window.activeTextEditor = { document: doc, selection: { active: pos } };
  const res = getCompletions(doc, pos, snippets);
  if (!res || Array.isArray(res)) return null;  // an auto snippet returns one match

  const [parts, blocks] = res.snippet.generator(
    new Proxy([], { get: () => '' }), res.groups, '', 'test', {}
  );
  let raw = '';
  for (const p of parts) {
    raw += typeof p === 'string' ? p : String(blocks[p.block]).replace(/\$/g, '\\$');
  }
  return before.slice(0, doc.offsetAt(res.range.start)) + renderSnippet(raw);
}

// ---- cases -------------------------------------------------------------------
// [language, text typed (cursor at end), expected result or null = no expansion]
const CASES = [
  ['markdown', 'Some text dm', 'Some text $$\n\\begin{align}\n<1>\n\\end{align}\n$$'],
  ['markdown', 'We have $ptl', 'We have $\\partial'],
  ['markdown', 'plain words ptl', null],
  ['markdown', '$x//', '$x\\frac{<1>}{<2>}<3>'],
  ['markdown', '$@a', '$\\alpha'],
  ['markdown', '$\\alpha sr', '$\\alpha^{2}'],
  ['markdown', '$$\nptl', '$$\n\\partial'],
  ['markdown', '```\nptl', null],
  ['markdown', '$x iden3', '$x \\begin{pmatrix}\n1 & 0 & 0 \\\\\n0 & 1 & 0 \\\\\n0 & 0 & 1\n\\end{pmatrix}'],
  ['latex', 'Text $ptl', 'Text $\\partial'],
  ['latex', '\\begin{align}\nptl', '\\begin{align}\n\\partial'],
  ['latex', 'no maths ptl', null],
];

let failures = 0;
for (const lang of ['markdown', 'latex']) {
  const file = path.join(ROOT, 'hsnips', lang + '.hsnips');
  let snippets;
  try {
    // HyperSnips sorts by descending priority after parsing (extension.js);
    // Array.prototype.sort is stable, so file order breaks ties as it does there.
    snippets = parse(fs.readFileSync(file, 'utf8')).sort((a, b) => b.priority - a.priority);
    console.log('PARSE  ok    %s  (%d snippets)', path.relative(ROOT, file), snippets.length);
  } catch (e) {
    console.log('PARSE  FAIL  %s: %s', path.relative(ROOT, file), e.message);
    failures++;
    continue;
  }
  for (const [caseLang, typed, expected] of CASES) {
    if (caseLang !== lang) continue;
    let got;
    try { got = expand(snippets, lang, typed); }
    catch (e) { got = 'ERROR: ' + e.message; }
    const pass = got === expected;
    if (!pass) failures++;
    const show = (v) => (v === null ? '(no expansion)' : JSON.stringify(v));
    console.log('%s  [%s] %s', pass ? 'ok   ' : 'FAIL ', lang, JSON.stringify(typed));
    if (!pass) {
      console.log('         expected %s', show(expected));
      console.log('         got      %s', show(got));
    }
  }
}

console.log(failures ? '\n%d failure(s)' : '\nall snippet checks passed', failures);
process.exit(failures ? 1 : 0);
