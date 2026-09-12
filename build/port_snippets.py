#!/usr/bin/env python3
"""
port_snippets.py -- Convert Obsidian Latex Suite snippets into VS Code HyperSnips.

Reads the Latex Suite plugin's data.json (whose `snippets` field is JS-ish
source, not JSON) and emits:

    hsnips/latex.hsnips      for .tex files
    hsnips/markdown.hsnips   for .md files

Re-run this any time you add snippets in Obsidian:

    python build/port_snippets.py

Latex Suite option flags and how they map:

    m  math mode only          -> context math(context)
    n  non-math (text) only    -> context !math(context)
    t  text mode only          -> context !math(context)
    c  code blocks only        -> context code(context)
    A  expand automatically    -> HyperSnips A flag
    r  trigger is a regex      -> HyperSnips /regex/ trigger
    w  word boundary required  -> HyperSnips w flag
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

        Latex Suite lets `replacement` be a function. We consume it as raw
        source (balancing brackets, skipping strings) so the rest of the
        array keeps parsing; these get reported and hand-ported instead.
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
                    break  # this is the enclosing object's closing brace
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


# Latex Suite ships these defaults. If a vault overrides snippetVariables it
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
# Body conversion: Latex Suite replacement -> HyperSnips body
# --------------------------------------------------------------------------

TABSTOP_RE = re.compile(r"\$(\d+)|\$\{(\d+)(?::((?:[^{}]|\{[^{}]*\})*))?\}")
CAPTURE_RE = re.compile(r"\[\[(\d+)\]\]")


def _append_interpolation(out, js_expr):
    """
    Append a ``rv = ...`` interpolation, folding any literal backslashes that
    immediately precede it into the JavaScript itself.

    This matters: a LaTeX replacement like "\\[[0]]" would otherwise emit
    \\``rv = m[1]``, and HyperSnips reads \\` as an escaped literal backtick,
    which silently destroys the interpolation (and every Greek-letter snippet
    with it).
    """
    backslashes = 0
    while out and out[-1] == "\\":
        out.pop()
        backslashes += 1
    if backslashes:
        out.append('``rv = "%s" + (%s)``' % ("\\\\" * backslashes, js_expr))
    else:
        out.append("``rv = %s``" % js_expr)


def convert_body(repl, is_regex=False):
    """
    Convert a Latex Suite replacement into a HyperSnips body.

      backticks   -> escaped (HyperSnips runs ``...`` as JavaScript)
      bare $      -> escaped (so $$...$$ math delimiters survive)
      $0 / ${1:x} -> left intact (identical TextMate syntax)
      [[0]]       -> ``rv = m[1]`` capture-group interpolation
    """
    out = []
    i = 0
    n = len(repl)
    while i < n:
        c = repl[i]

        if c == "`":
            out.append("\\`")
            i += 1
            continue

        if is_regex and repl.startswith("[[", i):
            m = CAPTURE_RE.match(repl, i)
            if m:
                grp = int(m.group(1)) + 1  # Latex Suite 0-based -> JS m[] 1-based
                _append_interpolation(out, "m[%d]" % grp)
                i = m.end()
                continue

        if c == "$":
            m = TABSTOP_RE.match(repl, i)
            if m:
                out.append(m.group(0))
                i = m.end()
                continue
            out.append("\\$")
            i += 1
            continue

        out.append(c)
        i += 1

    return "".join(out)


def escape_trigger(trigger):
    return '"%s"' % trigger.replace("\\", "\\\\").replace('"', '\\"')


# --------------------------------------------------------------------------
# Emit
# --------------------------------------------------------------------------

PREAMBLE_TEX = r'''# ==========================================================================
#  latex.hsnips -- ported from Sorin's Obsidian Latex Suite snippets
#
#  DO NOT EDIT BY HAND if you want to keep syncing from Obsidian:
#  edit snippets in Obsidian, then re-run  python build/port_snippets.py
#
#  Flags:  A = expand automatically (no Tab)   w = word boundary
# ==========================================================================

global
// True when the cursor sits inside math in a .tex file.
function math(context) {
    return context.scopes.some(s =>
        s.startsWith("meta.math") ||
        s.startsWith("string.other.math") ||
        s.includes("math.block") ||
        s.includes("math.inline")
    )
}
// True inside a verbatim / code environment.
function code(context) {
    return context.scopes.some(s =>
        s.includes("markup.raw") ||
        s.includes("environment.verbatim") ||
        s.includes("source.python") ||
        s.includes("source.cpp")
    )
}
endglobal

'''

PREAMBLE_MD = r'''# ==========================================================================
#  markdown.hsnips -- ported from Sorin's Obsidian Latex Suite snippets
#
#  DO NOT EDIT BY HAND if you want to keep syncing from Obsidian:
#  edit snippets in Obsidian, then re-run  python build/port_snippets.py
#
#  Same snippets as latex.hsnips, but the math detector understands the
#  $...$ / $$...$$ spans that VS Code's markdown grammar marks up.
# ==========================================================================

global
// True when the cursor sits inside $...$ or $$...$$ in a .md file.
function math(context) {
    return context.scopes.some(s =>
        s.includes("math") ||
        s.startsWith("meta.embedded.math")
    )
}
function code(context) {
    return context.scopes.some(s =>
        s.includes("markup.raw") ||
        s.includes("markup.fenced_code") ||
        s.startsWith("meta.embedded.block")
    )
}
endglobal

'''


def emit(snippets, variables, preamble, path, stats, manual=""):
    lines = [preamble]
    current_section = None

    for sn in snippets:
        trig = sn.get("trigger")
        repl = sn.get("replacement")
        if trig is None or repl is None:
            stats["skipped_incomplete"] += 1
            continue

        # Latex Suite allows `replacement` to be a JS function. HyperSnips can
        # express these too, but not mechanically -- they are hand-ported in
        # build/manual_snippets.hsnips and appended below.
        if isinstance(repl, dict) and "__function__" in repl:
            stats["function_snippets"].append(
                trig["__regex__"] if isinstance(trig, dict) else trig
            )
            continue

        # ${VISUAL} wraps a selection. HyperSnips has no equivalent, so these
        # are emitted as native VS Code surround-with snippets instead.
        if "${VISUAL}" in repl:
            stats["visual_snippets"].append(sn)
            continue

        opts = sn.get("options", "") or ""
        if isinstance(opts, dict):
            opts = ""
        opts = opts.strip().strip('"').strip("'")

        priority = sn.get("priority")

        section = sn.get("__section__")
        if section and section != current_section:
            pad = "-" * max(4, 60 - len(section))
            lines.append("\n# ---- %s %s\n" % (section, pad))
            current_section = section

        is_regex = "r" in opts or isinstance(trig, dict)

        if isinstance(trig, dict):
            pattern = trig["__regex__"]
            is_regex = True
        else:
            pattern = trig

        if is_regex:
            pattern = expand_variables(pattern, variables, stats["unresolved_vars"])
            if not pattern.endswith("$"):
                pattern = pattern + "$"
            trigger_field = "/%s/" % pattern
            desc = "regex"
        else:
            trigger_field = escape_trigger(pattern)
            desc = pattern[:40].replace('"', "'")

        flags = ""
        if "A" in opts:
            flags += "A"
        if "w" in opts:
            flags += "w"
        if "i" in opts:
            flags += "i"

        ctx = None
        if "m" in opts:
            ctx = "math(context)"
        elif "n" in opts or "t" in opts:
            ctx = "!math(context)"
        elif "c" in opts:
            ctx = "code(context)"

        body = convert_body(repl, is_regex=is_regex)

        if priority not in (None, "", "0"):
            try:
                lines.append("priority %d" % int(priority))
            except (TypeError, ValueError):
                pass
        if ctx:
            lines.append("context %s" % ctx)

        lines.append('snippet %s "%s" %s' % (trigger_field, desc, flags))
        lines.append(body)
        lines.append("endsnippet")
        lines.append("")
        stats["emitted"] += 1

    if manual:
        lines.append("\n# ---- hand-ported snippets (build/manual_snippets.hsnips) ----\n")
        lines.append(manual)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------
# ${VISUAL} snippets -> native VS Code "surround with" snippets
# --------------------------------------------------------------------------

def emit_visual_snippets(visual, path):
    """
    Latex Suite's ${VISUAL} wraps the current selection. HyperSnips cannot do
    this, but VS Code's own snippet engine can via $TM_SELECTED_TEXT, driven by
    the `editor.action.surroundWith` command (bound to Ctrl+Alt+S in
    keybindings.json). Select an expression, hit the key, pick the wrapper.
    """
    out = {}
    for sn in visual:
        trig = sn["trigger"]
        repl = sn["replacement"]
        body = repl.replace("${VISUAL}", "$TM_SELECTED_TEXT")
        name = {
            "U": "underbrace", "B": "underset", "C": "cancel",
            "K": "cancelto", "S": "sqrt",
            "(": "parens", "[": "brackets", "{": "braces",
        }.get(trig, "wrap-" + trig)
        out["Surround: %s" % name] = {
            "prefix": "surround-%s" % name,
            "body": [body],
            "description": "Wrap selection: %s (was Latex Suite '%s')" % (name, trig),
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "//": "Generated by build/port_snippets.py -- Latex Suite ${VISUAL} snippets."
              " Select text, press Ctrl+Alt+S, choose one.",
    }
    payload.update(out)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(out)


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


def global_hsnips_dir():
    """
    HyperSnips' own snippets folder.

    The workspace sets hsnips.hsnipsPath, but that setting is read verbatim --
    it does not expand ${workspaceFolder} in every version. Installing a copy
    here means the snippets load no matter what, from any folder.
    """
    if os.name == "nt":
        base = os.environ.get("APPDATA")
        if not base:
            return None
        return Path(base) / "Code" / "User" / "hsnips"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Code" / "User" / "hsnips"
    return Path.home() / ".config" / "Code" / "User" / "hsnips"


def install_globally():
    dest = global_hsnips_dir()
    if dest is None:
        print("Could not work out the VS Code user folder; skipping install.")
        return
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("latex.hsnips", "markdown.hsnips"):
        src = ROOT / "hsnips" / name
        if src.exists():
            shutil.copy2(src, dest / name)
    print("Installed  %s" % dest)


def main():
    argv = [a for a in sys.argv[1:] if a != "--install"]
    do_install = "--install" in sys.argv
    data_json = Path(argv[0]) if argv else DEFAULT_DATA_JSON
    if not data_json.exists():
        sys.exit("Could not find Latex Suite data.json at:\n  %s" % data_json)

    data = json.loads(data_json.read_text(encoding="utf-8"))
    raw_snippets = data.get("snippets", "")
    variables = load_snippet_variables(data.get("snippetVariables", ""))

    snippets = Scanner(raw_snippets).read_array_of_objects()
    snippets = attach_sections(raw_snippets, snippets)

    manual_path = HERE / "manual_snippets.hsnips"
    manual = manual_path.read_text(encoding="utf-8") if manual_path.exists() else ""

    def fresh():
        return {
            "emitted": 0,
            "skipped_incomplete": 0,
            "function_snippets": [],
            "visual_snippets": [],
            "unresolved_vars": set(),
        }

    tex_stats = fresh()
    emit(snippets, variables, PREAMBLE_TEX,
         ROOT / "hsnips" / "latex.hsnips", tex_stats, manual)

    md_stats = fresh()
    emit(snippets, variables, PREAMBLE_MD,
         ROOT / "hsnips" / "markdown.hsnips", md_stats, manual)

    n_visual = emit_visual_snippets(
        tex_stats["visual_snippets"],
        ROOT / ".vscode" / "latex-visual.code-snippets",
    )

    print("Parsed    %d snippets from %s" % (len(snippets), data_json.name))
    print("Variables %s" % (", ".join(variables) if variables else "none"))
    print("Wrote     hsnips/latex.hsnips                  (%d snippets)" % tex_stats["emitted"])
    print("Wrote     hsnips/markdown.hsnips               (%d snippets)" % md_stats["emitted"])
    print("Wrote     .vscode/latex-visual.code-snippets   (%d surround-with)" % n_visual)
    if manual:
        print("Appended  build/manual_snippets.hsnips")
    if tex_stats["function_snippets"]:
        print("\nFunction snippets (hand-ported in build/manual_snippets.hsnips):")
        for t in tex_stats["function_snippets"]:
            print("    %s" % t)
    if tex_stats["unresolved_vars"]:
        print("\nWARNING unresolved snippet variables: %s"
              % ", ".join(sorted(tex_stats["unresolved_vars"])))
    if tex_stats["skipped_incomplete"]:
        print("\nSkipped   %d malformed entries" % tex_stats["skipped_incomplete"])

    if do_install:
        print()
        install_globally()


if __name__ == "__main__":
    main()
