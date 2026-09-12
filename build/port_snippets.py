#!/usr/bin/env python3
"""
port_snippets.py -- Convert Obsidian Latex Suite snippets into VS Code HyperSnips.

Reads the Latex Suite plugin's data.json (whose `snippets` field is JS source,
not JSON) and writes:

    hsnips/latex.hsnips                  for .tex files
    hsnips/markdown.hsnips               for .md files
    .vscode/latex-visual.code-snippets   the ${VISUAL} (wrap-selection) ones

Re-run after adding snippets in Obsidian; --install also copies them into
HyperSnips' own folder so they work in any VS Code window:

    python build/port_snippets.py --install
    node build/test_snippets.js          # proves they parse and expand

What HyperSnips actually requires (read from its parser, not assumed):

  * Trigger is bare (snippet dm "desc" A) or a regex in backticks
    (snippet `re` "desc" A). A double-quoted trigger registers the quotes as
    part of the trigger, so it never fires.
  * Flags: A auto, i in-word, w word-boundary, b line-start, M multiline.
    With neither i nor w, the whole token before the cursor must EQUAL the
    trigger; Latex Suite expands mid-token by default, so that maps to i.
  * Body text is VS Code snippet syntax, where \\ $ } are special.
  * ``code`` blocks: HyperSnips' parser does not look for endsnippet while
    inside one, so an unbalanced delimiter (e.g. two blocks written back to
    back, which makes four backticks) silently swallows every later snippet.
    Adjacent JS pieces are therefore merged into a single block.
  * $0 is the FINAL cursor position. Latex Suite uses $0 as the FIRST stop,
    so every tabstop is renumbered +1.

Latex Suite option flags:

    m  maths only      t/n  text only      c  code only
    A  auto-expand     r    regex trigger  w  word boundary
"""

import json
import os
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

DEFAULT_DATA_JSON = (
    ROOT.parent / "HMC" / ".obsidian" / "plugins" / "obsidian-latex-suite" / "data.json"
)
BACKUP_DIR = HERE / "backup-original-global-hsnips"


# --------------------------------------------------------------------------
# Scanner for the JS object-literal array that Latex Suite stores as a string
# --------------------------------------------------------------------------

class Scanner:
    def __init__(self, src):
        self.s = src
        self.i = 0
        self.n = len(src)

    def peek(self, k=0):
        j = self.i + k
        return self.s[j] if j < self.n else ""

    def skip_ws_and_comments(self):
        while self.i < self.n:
            c = self.s[self.i]
            if c in " \t\r\n":
                self.i += 1
            elif c == "/" and self.peek(1) == "/":
                while self.i < self.n and self.s[self.i] != "\n":
                    self.i += 1
            elif c == "/" and self.peek(1) == "*":
                self.i += 2
                while self.i < self.n and not (
                    self.s[self.i] == "*" and self.peek(1) == "/"
                ):
                    self.i += 1
                self.i += 2
            else:
                return

    def read_string(self):
        """Read a JS string literal, returning its decoded value."""
        quote = self.s[self.i]
        self.i += 1
        out = []
        mapping = {
            "n": "\n", "t": "\t", "r": "\r", "b": "\b",
            "f": "\f", "v": "\v", "0": "\0",
            "\\": "\\", "'": "'", '"': '"', "`": "`", "/": "/",
        }
        while self.i < self.n:
            c = self.s[self.i]
            if c == "\\":
                nxt = self.peek(1)
                if nxt == "u":
                    hexs = self.s[self.i + 2 : self.i + 6]
                    try:
                        out.append(chr(int(hexs, 16)))
                        self.i += 6
                        continue
                    except ValueError:
                        pass
                if nxt in mapping:
                    out.append(mapping[nxt])
                    self.i += 2
                    continue
                # Unknown escape: keep the backslash AND the char, which is
                # what a Latex Suite user writing "\ " actually meant.
                out.append("\\")
                out.append(nxt)
                self.i += 2
                continue
            if c == quote:
                self.i += 1
                return "".join(out)
            out.append(c)
            self.i += 1
        raise ValueError("unterminated string")

    def read_regex(self):
        """Read a JS regex literal, returning (pattern, flags)."""
        self.i += 1
        pat = []
        in_class = False
        while self.i < self.n:
            c = self.s[self.i]
            if c == "\\":
                pat.append(c)
                pat.append(self.peek(1))
                self.i += 2
                continue
            if c == "[":
                in_class = True
            elif c == "]":
                in_class = False
            elif c == "/" and not in_class:
                self.i += 1
                flags = []
                while self.i < self.n and self.s[self.i].isalpha():
                    flags.append(self.s[self.i])
                    self.i += 1
                return "".join(pat), "".join(flags)
            pat.append(c)
            self.i += 1
        raise ValueError("unterminated regex")

    def read_bare(self):
        """Read a bare token (number, true/false, identifier)."""
        start = self.i
        while self.i < self.n and self.s[self.i] not in ",}\n":
            self.i += 1
        return self.s[start : self.i].strip()

    def read_function(self):
        """
        Read a JS function value, e.g.  (match) => { ... }

        Latex Suite lets `replacement` be a function. It is consumed as raw
        source (balancing brackets, skipping strings) so the rest of the array
        keeps parsing; these are hand-ported in manual_snippets.hsnips.
        """
        start = self.i
        depth = 0
        while self.i < self.n:
            c = self.s[self.i]
            if c in "\"'`":
                quote = c
                self.i += 1
                while self.i < self.n:
                    if self.s[self.i] == "\\":
                        self.i += 2
                        continue
                    if self.s[self.i] == quote:
                        self.i += 1
                        break
                    self.i += 1
                continue
            if c == "/" and self.peek(1) == "/":
                while self.i < self.n and self.s[self.i] != "\n":
                    self.i += 1
                continue
            if c in "({[":
                depth += 1
            elif c in ")]":
                depth -= 1
            elif c == "}":
                if depth == 0:
                    break  # the enclosing object's closing brace
                depth -= 1
            elif c == "," and depth == 0:
                break
            self.i += 1
        return self.s[start : self.i].strip()

    def read_object(self):
        """Read a {...} object literal into a dict."""
        self.i += 1
        obj = {}
        while True:
            self.skip_ws_and_comments()
            if self.i >= self.n:
                raise ValueError("unterminated object")
            if self.s[self.i] == "}":
                self.i += 1
                return obj
            if self.s[self.i] == ",":
                self.i += 1
                continue
            if self.s[self.i] in "\"'":
                key = self.read_string()
            else:
                start = self.i
                while self.i < self.n and (
                    self.s[self.i].isalnum() or self.s[self.i] in "_$"
                ):
                    self.i += 1
                key = self.s[start : self.i]
            self.skip_ws_and_comments()
            if self.i < self.n and self.s[self.i] == ":":
                self.i += 1
            self.skip_ws_and_comments()
            c = self.s[self.i]
            if c in "\"'":
                obj[key] = self.read_string()
            elif c == "/":
                pat, flags = self.read_regex()
                obj[key] = {"__regex__": pat, "flags": flags}
            elif c == "[":
                depth = 0
                start = self.i
                while self.i < self.n:
                    if self.s[self.i] == "[":
                        depth += 1
                    elif self.s[self.i] == "]":
                        depth -= 1
                        if depth == 0:
                            self.i += 1
                            break
                    self.i += 1
                obj[key] = self.s[start : self.i]
            elif c == "(" or self.s.startswith("function", self.i):
                obj[key] = {"__function__": self.read_function()}
            else:
                obj[key] = self.read_bare()

    def read_array_of_objects(self):
        out = []
        self.skip_ws_and_comments()
        if self.i < self.n and self.s[self.i] == "[":
            self.i += 1
        while self.i < self.n:
            self.skip_ws_and_comments()
            if self.i >= self.n:
                break
            c = self.s[self.i]
            if c == "]":
                break
            if c == ",":
                self.i += 1
                continue
            if c == "{":
                out.append(self.read_object())
                continue
            self.i += 1
        return out


# --------------------------------------------------------------------------
# Snippet variables (${GREEK} etc.)
# --------------------------------------------------------------------------

def load_snippet_variables(raw):
    if not raw or not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    sc = Scanner(raw)
    sc.skip_ws_and_comments()
    if sc.i < sc.n and sc.s[sc.i] == "{":
        return sc.read_object()
    return {}


# Latex Suite ships these defaults. A vault that overrides snippetVariables
# only stores the ones it changed, so anything still referenced falls back here.
BUILTIN_VARIABLES = {
    "${GREEK}": (
        "alpha|beta|gamma|Gamma|delta|Delta|epsilon|varepsilon|zeta|eta|theta|"
        "vartheta|Theta|iota|kappa|lambda|Lambda|mu|nu|xi|Xi|omicron|pi|Pi|rho|"
        "varrho|sigma|Sigma|tau|upsilon|Upsilon|phi|varphi|Phi|chi|psi|Psi|omega|Omega"
    ),
    "${SYMBOL}": (
        "parallel|perp|partial|nabla|hbar|ell|infty|oplus|ominus|otimes|oslash|"
        "square|star|dagger|vee|wedge|subseteq|subset|supseteq|supset|emptyset|"
        "exists|nexists|forall|implies|impliedby|iff|setminus|neg|lor|land|"
        "bigcup|bigcap|cdot|times|simeq|approx|ll|gg|equiv|sim|propto|neq"
    ),
    "${SHORT_SYMBOL}": "to|pm|mp",
    "${MORE_SYMBOLS}": "leq|geq|mapsto|circ|bullet|cup|cap|in|notin|subset|supset",
}

VARIABLE_REF_RE = re.compile(r"\$\{[A-Z_]+\}")


def expand_variables(pattern, variables, unresolved=None):
    """Substitute ${GREEK}-style variables into a regex trigger."""
    for name, value in variables.items():
        if name in pattern:
            pattern = pattern.replace(name, "(?:" + value + ")")
    for name, value in BUILTIN_VARIABLES.items():
        if name in pattern:
            pattern = pattern.replace(name, "(?:" + value + ")")
    leftover = VARIABLE_REF_RE.findall(pattern)
    if leftover and unresolved is not None:
        unresolved.update(leftover)
    return pattern


# --------------------------------------------------------------------------
# Replacement -> snippet body
# --------------------------------------------------------------------------

TABSTOP_RE = re.compile(r"\$(\d+)|\$\{(\d+)(?::((?:[^{}]|\{[^{}]*\})*))?\}")
CAPTURE_RE = re.compile(r"\[\[(\d+)\]\]")
BARE_TRIGGER_RE = re.compile(r"^[^\s`]+$")
BACKTICK_JS = '"\\x60"'


def snippet_escape(text):
    """Literal text -> VS Code snippet syntax, where \\ $ and } are special."""
    return text.replace("\\", "\\\\").replace("$", "\\$").replace("}", "\\}")


def to_segments(repl, is_regex, visual_token=None):
    """
    Split a Latex Suite replacement into pieces:

        ("text", s)  literal text, still unescaped
        ("raw",  s)  already snippet syntax (tabstops, $TM_SELECTED_TEXT)
        ("js",   e)  a JavaScript expression (regex capture, backtick)
    """
    segs, buf = [], []

    def flush():
        if buf:
            segs.append(("text", "".join(buf)))
            buf.clear()

    i, n = 0, len(repl)
    while i < n:
        if visual_token and repl.startswith("${VISUAL}", i):
            flush()
            segs.append(("raw", visual_token))
            i += len("${VISUAL}")
            continue

        if is_regex and repl.startswith("[[", i):
            m = CAPTURE_RE.match(repl, i)
            if m:
                flush()
                # Latex Suite [[0]] is the first group; JS m[1] is.
                segs.append(("js", "m[%d]" % (int(m.group(1)) + 1)))
                i = m.end()
                continue

        if repl[i] == "$":
            m = TABSTOP_RE.match(repl, i)
            if m:
                flush()
                bare = m.group(1) is not None
                number = int(m.group(1) if bare else m.group(2)) + 1  # $0 first -> $1
                default = m.group(3)
                if default is not None:
                    segs.append(("raw", "${%d:%s}" % (number, snippet_escape(default))))
                elif bare:
                    segs.append(("raw", "$%d" % number))
                else:
                    segs.append(("raw", "${%d}" % number))
                i = m.end()
                continue

        if repl[i] == "`":
            flush()
            segs.append(("js", BACKTICK_JS))
            i += 1
            continue

        buf.append(repl[i])
        i += 1

    flush()
    return segs


def segments_to_hsnips(segs):
    """Body for an .hsnips file. Consecutive JS pieces share ONE code block."""
    out, js_run = [], []

    def flush_js():
        if js_run:
            out.append("``rv = lit(%s)``" % " + ".join(js_run))
            js_run.clear()

    for kind, value in segs:
        if kind == "js":
            js_run.append(value)
            continue
        flush_js()
        out.append(snippet_escape(value) if kind == "text" else value)
    flush_js()
    return "".join(out)


def segments_to_vscode(segs):
    """Body for a .code-snippets file (no JavaScript available there)."""
    out = []
    for kind, value in segs:
        if kind == "text":
            out.append(snippet_escape(value))
        elif kind == "raw":
            out.append(value)
        elif value == BACKTICK_JS:
            out.append("`")
    return "".join(out)


# --------------------------------------------------------------------------
# Emit .hsnips
# --------------------------------------------------------------------------

GLOBAL_BLOCK = r'''global
// ---- Context detection ---------------------------------------------------
// HyperSnips only hands a context filter the grammar scopes, and markdown's
// $...$ has no dependable maths scope. So "am I in maths / code?" is decided
// by reading the document text up to the cursor, as Latex Suite does.
const vscode = require('vscode');

const MATH_ENVS = new Set(['equation', 'equation*', 'align', 'align*', 'gather',
  'gather*', 'multline', 'multline*', 'flalign', 'flalign*', 'alignat', 'alignat*',
  'eqnarray', 'eqnarray*', 'math', 'displaymath']);
const CODE_ENVS = new Set(['verbatim', 'verbatim*', 'Verbatim', 'lstlisting',
  'minted', 'comment']);
const TEXT_GROUP = /^\\(?:text|textrm|textit|textbf|textsf|texttt|mbox|intertext)\s*\{/;

function scanContext(text, languageId) {
  const isTex = languageId === 'latex' || languageId === 'tex';
  let inline = false, display = false, envDepth = 0, codeEnv = 0;
  let fence = false, inlineCode = false;
  let braces = [], textDepth = 0;
  const lines = text.split('\n');

  for (let li = 0; li < lines.length; li++) {
    const line = lines[li];
    const last = li === lines.length - 1;

    if (!isTex) {
      if (/^\s*(```|~~~)/.test(line)) {
        fence = !fence;
        continue;
      }
      if (fence) continue;
      if (!display && line.trim() === '') inline = false;
    }

    for (let i = 0; i < line.length; i++) {
      const c = line[i];

      if (!isTex && inlineCode) {
        if (c === '`') inlineCode = false;
        continue;
      }

      if (c === '\\') {
        const rest = line.slice(i);
        let m;
        if (isTex && (m = /^\\begin\{([^}]*)\}/.exec(rest))) {
          if (CODE_ENVS.has(m[1])) codeEnv++;
          else if (!codeEnv && MATH_ENVS.has(m[1])) envDepth++;
          i += m[0].length - 1;
          continue;
        }
        if (isTex && (m = /^\\end\{([^}]*)\}/.exec(rest))) {
          if (CODE_ENVS.has(m[1])) codeEnv = Math.max(0, codeEnv - 1);
          else if (!codeEnv && MATH_ENVS.has(m[1])) envDepth = Math.max(0, envDepth - 1);
          i += m[0].length - 1;
          continue;
        }
        if (isTex && codeEnv) { i++; continue; }
        if (isTex && (rest.startsWith('\\(') || rest.startsWith('\\['))) { display = true; i++; continue; }
        if (isTex && (rest.startsWith('\\)') || rest.startsWith('\\]'))) { display = false; i++; continue; }
        if ((m = TEXT_GROUP.exec(rest)) && (inline || display || envDepth)) {
          braces.push(true);
          textDepth++;
          i += m[0].length - 1;
          continue;
        }
        i++;  // escaped character, e.g. \$ or \{
        continue;
      }

      if (isTex && codeEnv) continue;
      if (isTex && c === '%') break;  // comment runs to end of line
      if (!isTex && c === '`') { inlineCode = true; continue; }

      if (c === '{') { braces.push(false); continue; }
      if (c === '}') { if (braces.pop()) textDepth--; continue; }

      if (c === '$') {
        if (line[i + 1] === '$') { display = !display; inline = false; i++; }
        else if (!display) inline = !inline;
        if (!inline && !display && !envDepth) { braces = []; textDepth = 0; }
      }
    }

    if (!isTex && inlineCode && !last) inlineCode = false;  // `code` never spans lines
  }

  const code = isTex ? codeEnv > 0 : (fence || inlineCode);
  const inMaths = (inline || display || envDepth > 0) && textDepth === 0;
  return { math: inMaths && !code, code };
}

let lastKey = null, lastState = { math: false, code: false };
function contextState() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return { math: false, code: false };
  const doc = editor.document;
  const pos = editor.selection.active;
  const key = doc.uri.toString() + '|' + doc.version + '|' + pos.line + '|' + pos.character;
  if (key !== lastKey) {
    lastKey = key;
    const before = doc.getText(new vscode.Range(new vscode.Position(0, 0), pos));
    lastState = scanContext(before, doc.languageId);
  }
  return lastState;
}

function math(context) { return contextState().math; }
function code(context) { return contextState().code; }

// Text produced by JavaScript still goes through VS Code's snippet parser,
// where \ and } are special. (HyperSnips escapes $ itself.)
function lit(s) { return String(s).replace(/[\\}]/g, (c) => '\\' + c); }
endglobal
'''

HEADER = """# ==========================================================================
#  %s -- generated from Sorin's Obsidian Latex Suite snippets
#
#  DO NOT EDIT BY HAND: edit snippets in Obsidian, then run
#      python build/port_snippets.py --install
#  Put hand-written snippets in build/manual_snippets.hsnips instead.
# ==========================================================================

"""


def emit(snippets, variables, path, stats, manual=""):
    lines = [HEADER % path.name, GLOBAL_BLOCK]
    current_section = None

    for sn in snippets:
        trig = sn.get("trigger")
        repl = sn.get("replacement")
        if trig is None or repl is None:
            stats["skipped_incomplete"] += 1
            continue

        if isinstance(repl, dict) and "__function__" in repl:
            stats["function_snippets"].append(
                trig["__regex__"] if isinstance(trig, dict) else trig
            )
            continue

        if isinstance(repl, str) and "${VISUAL}" in repl:
            stats["visual_snippets"].append(sn)
            continue

        opts = sn.get("options", "") or ""
        if isinstance(opts, dict):
            opts = ""
        opts = opts.strip().strip('"').strip("'")

        section = sn.get("__section__")
        if section and section != current_section:
            lines.append("# ---- %s %s\n" % (section, "-" * max(4, 60 - len(section))))
            current_section = section

        is_regex = isinstance(trig, dict) or "r" in opts
        pattern = trig["__regex__"] if isinstance(trig, dict) else trig

        if is_regex:
            pattern = expand_variables(pattern, variables, stats["unresolved_vars"])
            trigger_field = "`%s`" % pattern.replace("`", "\\x60")
            bare = False
        elif BARE_TRIGGER_RE.match(pattern):
            trigger_field = pattern
            bare = True
        else:
            # Spaces or backticks can't be a bare trigger: use an exact regex.
            trigger_field = "`%s`" % re.escape(pattern).replace("`", "\\x60")
            bare = False

        flags = "A" if "A" in opts else ""
        if bare:
            flags += "w" if "w" in opts else "i"

        if "m" in opts:
            context = "math(context)"
        elif "t" in opts or "n" in opts:
            context = "!math(context) && !code(context)"
        elif "c" in opts:
            context = "code(context)"
        else:
            context = None

        desc = sn.get("description") or ("regex" if is_regex else pattern)
        desc = re.sub(r"\s+", " ", str(desc)).replace('"', "'").strip() or "snippet"

        priority = sn.get("priority")
        try:
            priority = int(priority) if priority not in (None, "") else 0
        except (TypeError, ValueError):
            priority = 0

        if priority:
            lines.append("priority %d" % priority)
        if context:
            lines.append("context %s" % context)
        header = 'snippet %s "%s"' % (trigger_field, desc)
        if flags:
            header += " " + flags
        lines.append(header)
        lines.append(segments_to_hsnips(to_segments(repl, is_regex)))
        lines.append("endsnippet")
        lines.append("")
        stats["emitted"] += 1

    if manual:
        lines.append("# ---- hand-ported (build/manual_snippets.hsnips) " + "-" * 20 + "\n")
        lines.append(manual)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------
# ${VISUAL} snippets -> VS Code surround-with snippets
# --------------------------------------------------------------------------

VISUAL_NAMES = {
    "U": "underbrace", "B": "underset", "C": "cancel", "K": "cancelto",
    "S": "sqrt", "(": "parens", "[": "brackets", "{": "braces",
}


def emit_visual_snippets(visual, path):
    """
    Latex Suite's ${VISUAL} wraps the selection. HyperSnips can't; VS Code's
    own engine can, via $TM_SELECTED_TEXT and editor.action.surroundWith
    (Ctrl+Alt+S in keybindings-to-copy.json).
    """
    payload = {}
    for sn in visual:
        trig = sn["trigger"] if isinstance(sn["trigger"], str) else "regex"
        name = VISUAL_NAMES.get(trig, "wrap-" + trig)
        segs = to_segments(sn["replacement"], False, visual_token="$TM_SELECTED_TEXT")
        payload["Surround: %s" % name] = {
            "scope": "latex,markdown",
            "prefix": "surround-%s" % name,
            "body": [segments_to_vscode(segs)],
            "description": "Wrap selection: %s (Latex Suite '%s')" % (name, trig),
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(payload)


# --------------------------------------------------------------------------
# Install into HyperSnips' own folder
# --------------------------------------------------------------------------

def global_hsnips_dir():
    """Where HyperSnips looks when hsnips.hsnipsPath is not set."""
    if os.name == "nt":
        base = os.environ.get("APPDATA")
        if not base:
            return None
        user = Path(base) / "Code" / "User"
    elif sys.platform == "darwin":
        user = Path.home() / "Library" / "Application Support" / "Code" / "User"
    else:
        user = Path.home() / ".config" / "Code" / "User"
    return user / "globalStorage" / "draivin.hsnips" / "hsnips"


def install_globally():
    dest = global_hsnips_dir()
    if dest is None:
        print("Could not work out the VS Code user folder; skipping install.")
        return
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("latex.hsnips", "markdown.hsnips"):
        target = dest / name
        if target.exists():
            backup = BACKUP_DIR / name
            if not backup.exists():
                BACKUP_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                print("Backed up your existing %s -> %s" % (name, backup))
        shutil.copy2(ROOT / "hsnips" / name, target)
    print("Installed  %s" % dest)


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

def attach_sections(raw_src, snippets):
    """Best-effort: tag each snippet with the nearest preceding // comment."""
    section = None
    idx = 0
    for line in raw_src.split("\n"):
        stripped = line.strip()
        if stripped.startswith("//") and not stripped.startswith("//{"):
            candidate = stripped.lstrip("/").strip().rstrip(":").strip()
            if candidate and len(candidate) < 40:
                section = candidate
            continue
        if "trigger:" in line and not stripped.startswith("//"):
            if idx < len(snippets):
                snippets[idx]["__section__"] = section
                idx += 1
    return snippets


def main():
    argv = [a for a in sys.argv[1:] if a != "--install"]
    do_install = "--install" in sys.argv
    data_json = Path(argv[0]) if argv else DEFAULT_DATA_JSON
    if not data_json.exists():
        sys.exit("Could not find Latex Suite data.json at:\n  %s" % data_json)

    data = json.loads(data_json.read_text(encoding="utf-8"))
    raw_snippets = data.get("snippets", "")
    variables = load_snippet_variables(data.get("snippetVariables", ""))

    snippets = attach_sections(raw_snippets, Scanner(raw_snippets).read_array_of_objects())

    manual_path = HERE / "manual_snippets.hsnips"
    manual = manual_path.read_text(encoding="utf-8") if manual_path.exists() else ""

    def fresh():
        return {"emitted": 0, "skipped_incomplete": 0, "function_snippets": [],
                "visual_snippets": [], "unresolved_vars": set()}

    tex = fresh()
    emit(snippets, variables, ROOT / "hsnips" / "latex.hsnips", tex, manual)
    md = fresh()
    emit(snippets, variables, ROOT / "hsnips" / "markdown.hsnips", md, manual)
    n_visual = emit_visual_snippets(tex["visual_snippets"],
                                    ROOT / ".vscode" / "latex-visual.code-snippets")

    print("Parsed    %d snippets from %s" % (len(snippets), data_json.name))
    print("Wrote     hsnips/latex.hsnips                  (%d)" % tex["emitted"])
    print("Wrote     hsnips/markdown.hsnips               (%d)" % md["emitted"])
    print("Wrote     .vscode/latex-visual.code-snippets   (%d surround-with)" % n_visual)
    if manual:
        print("Appended  build/manual_snippets.hsnips")
    if tex["function_snippets"]:
        print("Function snippets (hand-ported): %s" % ", ".join(tex["function_snippets"]))
    if tex["unresolved_vars"]:
        print("WARNING unresolved variables: %s" % ", ".join(sorted(tex["unresolved_vars"])))
    if tex["skipped_incomplete"]:
        print("Skipped   %d malformed entries" % tex["skipped_incomplete"])

    if do_install:
        install_globally()
    print("\nVerify with:  node build/test_snippets.js")


if __name__ == "__main__":
    main()
