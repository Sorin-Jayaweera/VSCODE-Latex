#!/usr/bin/env python3
"""
md2tex.py -- Convert an Obsidian markdown note into a hmcnote LaTeX document.

Written for the markdown Sorin's vault actually contains, which is why it is
not pandoc: it understands Obsidian embeds (![[Pasted image ....png]]),
wikilinks ([[Note|alias]]), callouts (> [!note] Title), and <br> inside table
cells, none of which pandoc handles without extra filters.

Usage:
    python build/md2tex.py NOTE.md [-o OUT.tex] [--dark|--light] [--body-only]

The hard part of any markdown-to-LaTeX converter is not the block structure,
it is making sure LaTeX special characters get escaped in prose but NOT inside
maths or code. That is done by lifting every math span and code span out into
placeholders first, escaping what remains, then putting them back.
"""

import argparse
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Placeholder machinery
# ---------------------------------------------------------------------------

# Private-use codepoints: cannot collide with anything in a real note.
PH_OPEN = "\ue000"
PH_CLOSE = "\ue001"


class Vault:
    """Collects protected spans so they survive text escaping."""

    def __init__(self):
        self.items = []

    def stash(self, text):
        self.items.append(text)
        return "%s%d%s" % (PH_OPEN, len(self.items) - 1, PH_CLOSE)

    def restore(self, text):
        def sub(m):
            return self.items[int(m.group(1))]

        pattern = re.compile(re.escape(PH_OPEN) + r"(\d+)" + re.escape(PH_CLOSE))
        # Repeat: a restored span can itself contain a placeholder.
        for _ in range(10):
            new = pattern.sub(sub, text)
            if new == text:
                break
            text = new
        return text


# ---------------------------------------------------------------------------
# Escaping
# ---------------------------------------------------------------------------

LATEX_ESCAPES = [
    ("\\", r"\textbackslash{}"),
    ("&", r"\&"),
    ("%", r"\%"),
    ("$", r"\$"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
]


def escape_text(s):
    for a, b in LATEX_ESCAPES:
        s = s.replace(a, b)
    return s


# ---------------------------------------------------------------------------
# Inline conversion
# ---------------------------------------------------------------------------

MATH_DISPLAY_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
MATH_INLINE_RE = re.compile(r"(?<!\$)\$(?!\$)((?:\\.|[^$\\])+?)\$(?!\$)", re.DOTALL)
CODE_INLINE_RE = re.compile(r"`([^`\n]+)`")

EMBED_RE = re.compile(r"!\[\[([^\]|]+?)(?:\|([^\]]*))?\]\]")
WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\]|]+?)(?:\|([^\]]*))?\]\]")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
BOLDALT_RE = re.compile(r"__(.+?)__", re.DOTALL)
ITALIC_RE = re.compile(r"(?<![\w*])\*([^*\n]+?)\*(?![\w*])")
STRIKE_RE = re.compile(r"~~(.+?)~~", re.DOTALL)
HIGHLIGHT_RE = re.compile(r"==(.+?)==", re.DOTALL)

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".pdf", ".gif", ".bmp", ".svg", ".webp"}


# Environments that are already a display on their own. Wrapping these in
# \[ ... \] is a LaTeX error, even though MathJax tolerates $$\begin{align}$$.
SELF_DISPLAY_ENVS = (
    "align", "align*", "gather", "gather*", "equation", "equation*",
    "multline", "multline*", "eqnarray", "eqnarray*",
    "flalign", "flalign*", "alignat", "alignat*",
)

SELF_DISPLAY_RE = re.compile(
    r"^\s*\\begin\{(" + "|".join(re.escape(e) for e in SELF_DISPLAY_ENVS) + r")\}"
)
ANY_SELF_DISPLAY_RE = re.compile(
    r"\\begin\{(" + "|".join(re.escape(e) for e in SELF_DISPLAY_ENVS) + r")\}"
)

# Nestable equivalents, for when one of the above turns up *inside* other
# maths. \[ \begin{align} ... \] is "Erroneous nesting of equation structures";
# \[ \begin{aligned} ... \] is fine and looks the same.
NESTABLE = {
    "align": "aligned", "align*": "aligned",
    "flalign": "aligned", "flalign*": "aligned",
    "alignat": "aligned", "alignat*": "aligned",
    "eqnarray": "aligned", "eqnarray*": "aligned",
    "gather": "gathered", "gather*": "gathered",
    "multline": "multlined", "multline*": "multlined",
    "equation": "aligned", "equation*": "aligned",
}


def _make_nestable(body):
    def begin(m):
        return "\\begin{%s}" % NESTABLE.get(m.group(1), "aligned")

    def end(m):
        return "\\end{%s}" % NESTABLE.get(m.group(1), "aligned")

    body = ANY_SELF_DISPLAY_RE.sub(begin, body)
    body = re.compile(
        r"\\end\{(" + "|".join(re.escape(e) for e in SELF_DISPLAY_ENVS) + r")\}"
    ).sub(end, body)
    return body


def wrap_display(body):
    r"""
    Turn the inside of a $$...$$ into valid display maths.

    Three things LaTeX cares about and MathJax does not:
      * $$\begin{align}...\end{align}$$ must NOT get an extra \[ \]
      * \begin{align} nested inside other maths is an error -- it has to
        become \begin{aligned}
      * a blank line inside display maths is an error, so they are dropped
    """
    lines = [l for l in body.strip().split("\n") if l.strip()]
    body = "\n".join(lines)
    if not body:
        return ""

    # A row break directly before \right, e.g. "\end{pmatrix} \\ \right)",
    # is ignored by MathJax but ends the align row in LaTeX, stranding the
    # \left and killing the build. Dropping it renders identically.
    body = re.sub(r"\\\\\s*(\\right\b)", r"\1", body)

    m = SELF_DISPLAY_RE.match(body)
    if m and body.rstrip().endswith("\\end{%s}" % m.group(1)):
        # The whole block IS the display environment: leave it alone.
        return body

    if ANY_SELF_DISPLAY_RE.search(body):
        body = _make_nestable(body)

    return "\\[\n%s\n\\]" % body


def protect_math_and_code(text, vault):
    """Lift maths and inline code out of the text before escaping."""

    def keep_display(m):
        return vault.stash(wrap_display(m.group(1)))

    def keep_inline(m):
        return vault.stash("$%s$" % m.group(1))

    def keep_code(m):
        body = m.group(1)
        return vault.stash("\\texttt{%s}" % escape_verb(body))

    text = MATH_DISPLAY_RE.sub(keep_display, text)
    text = MATH_INLINE_RE.sub(keep_inline, text)
    text = CODE_INLINE_RE.sub(keep_code, text)
    return text


def escape_verb(s):
    """Escape for \\texttt{} -- like escape_text but keeps it monospace-safe."""
    out = escape_text(s)
    return out.replace("-", "-\\/")  # avoid ligature-y hyphen runs


def convert_embed(m, ctx):
    """![[file.png|300]] -> \\embed[...]{file.png}, or a note transclusion."""
    target = m.group(1).strip()
    size = (m.group(2) or "").strip()
    ext = Path(target).suffix.lower()

    if ext in IMAGE_EXT:
        resolved = ctx.resolve_asset(target)
        width = "0.8\\linewidth"
        if size.isdigit():
            # Obsidian sizes are pixels; map onto a fraction of the text width.
            frac = min(1.0, max(0.15, int(size) / 700.0))
            width = "%.2f\\linewidth" % frac
        if resolved is None:
            ctx.missing_assets.add(target)
            return "\\textit{[missing image: %s]}" % escape_text(target)
        return "\n\\embed[%s]{%s}\n" % (width, resolved)

    # Transcluded note: we cannot inline it, so mark it.
    return "\\textit{[embed: %s]}" % escape_text(target)


def convert_inline(text, ctx, vault):
    """Protect maths, then convert. For single-line contexts."""
    text = protect_math_and_code(text, vault)
    return convert_protected(text, ctx, vault)


def convert_protected(text, ctx, vault):
    """
    Everything after maths and code have already been lifted out.

    Kept separate from convert_inline so a paragraph can be protected as a
    whole -- a $$...$$ block spans several lines, so protecting line by line
    would never match it -- and only then split into lines for line breaks.
    """
    # Embeds and links become LaTeX before escaping, and are stashed so their
    # backslashes are not mangled.
    text = EMBED_RE.sub(lambda m: vault.stash(convert_embed(m, ctx)), text)

    def wikilink(m):
        target, alias = m.group(1).strip(), (m.group(2) or "").strip()
        label = alias or target
        # No cross-document links in the PDF; render as emphasised text so the
        # reference is still visible.
        return vault.stash("\\textit{%s}" % escape_text(label))

    text = WIKILINK_RE.sub(wikilink, text)

    def image(m):
        alt, src = m.group(1), m.group(2).split(" ")[0]
        resolved = ctx.resolve_asset(src)
        if resolved is None:
            if src.startswith("http"):
                return vault.stash("\\textit{[remote image]}")
            ctx.missing_assets.add(src)
            return vault.stash("\\textit{[missing image: %s]}" % escape_text(src))
        return vault.stash("\n\\embed{%s}\n" % resolved)

    text = IMAGE_RE.sub(image, text)

    def link(m):
        label, url = m.group(1), m.group(2)
        return vault.stash(
            "\\href{%s}{%s}" % (url.replace("%", "\\%"), escape_text(label))
        )

    text = LINK_RE.sub(link, text)

    # Now it is safe to escape whatever prose is left.
    text = escape_text(text)

    # Emphasis, applied after escaping (the markers are not LaTeX specials).
    text = BOLD_RE.sub(lambda m: "\\textbf{%s}" % m.group(1), text)
    text = BOLDALT_RE.sub(lambda m: "\\textbf{%s}" % m.group(1), text)
    text = STRIKE_RE.sub(lambda m: "\\mdstrike{%s}" % m.group(1), text)
    text = HIGHLIGHT_RE.sub(lambda m: "\\mdhl{%s}" % m.group(1), text)
    text = ITALIC_RE.sub(lambda m: "\\textit{%s}" % m.group(1), text)

    return vault.restore(text)


# ---------------------------------------------------------------------------
# Block-level conversion
# ---------------------------------------------------------------------------

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
FENCE_RE = re.compile(r"^\s*(```+|~~~+)\s*(\w+)?\s*$")
HRULE_RE = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")
ULIST_RE = re.compile(r"^(\s*)[-*+]\s+(.*)$")
OLIST_RE = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
TASK_RE = re.compile(r"^(\s*)[-*+]\s+\[([ xX])\]\s+(.*)$")
QUOTE_RE = re.compile(r"^\s*>\s?(.*)$")
CALLOUT_RE = re.compile(r"^\s*\[!(\w+)\]([+-]?)\s*(.*)$")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")

SECTIONS = ["section", "subsection", "subsubsection", "paragraph", "subparagraph"]

CALLOUT_MAP = {
    "note": "note", "info": "note", "abstract": "note", "summary": "note",
    "tip": "tip", "hint": "tip", "success": "tip", "check": "tip", "done": "tip",
    "warning": "warning", "caution": "warning", "attention": "warning",
    "danger": "important", "error": "important", "bug": "important",
    "failure": "important", "fail": "important", "missing": "important",
    "important": "important",
    "example": "example", "quote": "example", "cite": "example",
    "question": "note", "help": "note", "faq": "note", "todo": "note",
}


class Context:
    """Where the note lives, so image paths can be resolved."""

    def __init__(self, source, vault_root=None, out_dir=None):
        self.source = Path(source).resolve()
        self.dir = self.source.parent
        self.vault_root = Path(vault_root).resolve() if vault_root else self.dir
        # Image paths in the .tex must be relative to wherever the .tex lands,
        # which is not always next to the .md.
        self.out_dir = Path(out_dir).resolve() if out_dir else self.dir
        self.missing_assets = set()
        self._index = None

    def _build_index(self):
        """Obsidian resolves an embed by filename anywhere in the vault."""
        self._index = {}
        for p in self.vault_root.rglob("*"):
            if p.is_file() and p.suffix.lower() in IMAGE_EXT:
                self._index.setdefault(p.name, p)

    def resolve_asset(self, name):
        name = name.strip()
        if name.startswith(("http://", "https://")):
            return None
        direct = self.dir / name
        if direct.exists():
            return self._rel(direct)
        for sub in ("images", "attachments", "Attachments", "assets"):
            cand = self.dir / sub / name
            if cand.exists():
                return self._rel(cand)
        if self._index is None:
            self._build_index()
        hit = self._index.get(Path(name).name)
        if hit:
            return self._rel(hit)
        return None

    def _rel(self, path):
        try:
            rel = os.path.relpath(path, self.out_dir)
        except ValueError:
            rel = str(path)
        return rel.replace("\\", "/")


def split_table_row(line):
    """Split a markdown table row, honouring \\| escapes."""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    cells, cur, i = [], [], 0
    while i < len(line):
        c = line[i]
        if c == "\\" and i + 1 < len(line) and line[i + 1] == "|":
            cur.append("|")
            i += 2
            continue
        if c == "|":
            cells.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    cells.append("".join(cur))
    return [c.strip() for c in cells]


class Converter:
    def __init__(self, ctx, line_breaks=True, auto_offset=True):
        self.ctx = ctx
        self.out = []
        self.heading_offset = 0
        # Obsidian's "Strict line breaks" is off by default, so a single
        # newline is a visible line break in reading view. Match that.
        self.line_breaks = line_breaks
        self.auto_offset = auto_offset

    def inline(self, text):
        return convert_inline(text, self.ctx, Vault())

    @staticmethod
    def _split_display_delimiters(lines):
        r"""
        Put every $$ on a line of its own before block parsing.

        Notes write display maths in several shapes:

            write $$            $$              $$ x = 1 $$
            x = 1               x = 1
            $$ so we know       $$

        The block parser pairs $$ lines up in order, so a $$ at the END of a
        text line ("write $$") used to be missed, the pairing drifted by one,
        and every later block came out inverted -- maths escaped as text,
        prose typeset as maths, ![[images]] swallowed. Normalising first makes
        the pairing global and shape-independent.

        Code fences, list items and table rows are left alone; $$...$$ there
        is handled inline.
        """
        out = []
        in_fence = False
        quote_re = re.compile(r"^(\s*(?:>\s?)+)")
        for line in lines:
            if FENCE_RE.match(line):
                in_fence = not in_fence
                out.append(line)
                continue
            if (
                in_fence
                or "$$" not in line
                or ULIST_RE.match(line)
                or OLIST_RE.match(line)
                or line.lstrip().startswith("|")
            ):
                out.append(line)
                continue

            qm = quote_re.match(line)
            prefix = qm.group(1) if qm else ""
            body = line[len(prefix):]
            if body.strip() == "$$":
                out.append(line)
                continue

            parts = body.split("$$")
            for k, part in enumerate(parts):
                if part.strip():
                    out.append(prefix + part)
                if k < len(parts) - 1:
                    out.append(prefix + "$$")
        return out

    def convert(self, text):
        lines = self._split_display_delimiters(text.split("\n"))

        # Notes usually start at "##" because the H1 is the filename. Shift the
        # shallowest heading present up to \section so numbering reads 1, 1.1,
        # rather than 0.1, 0.1.1.
        if self.auto_offset:
            levels = [len(m.group(1))
                      for m in (HEADING_RE.match(l) for l in lines) if m]
            if levels:
                self.heading_offset = -(min(levels) - 1)

        self.lines = lines
        self.i = 0
        while self.i < len(lines):
            line = lines[self.i]

            if self._try_fence():
                continue
            if self._try_display_math():
                continue
            if self._try_table():
                continue
            if self._try_heading():
                continue
            if self._try_hrule():
                continue
            if self._try_quote():
                continue
            if self._try_list():
                continue
            self._paragraph()
        return "\n".join(self.out)

    # -- blocks ------------------------------------------------------------

    def _try_fence(self):
        m = FENCE_RE.match(self.lines[self.i])
        if not m:
            return False
        fence = m.group(1)
        lang = m.group(2) or ""
        self.i += 1
        body = []
        while self.i < len(self.lines):
            if self.lines[self.i].strip().startswith(fence[0] * len(fence)):
                self.i += 1
                break
            body.append(self.lines[self.i])
            self.i += 1
        self.out.append("\\begin{codebox}")
        self.out.append("\\begin{Verbatim}[breaklines=true,fontsize=\\small]")
        self.out.extend(body)
        self.out.append("\\end{Verbatim}")
        self.out.append("\\end{codebox}")
        self.out.append("")
        if lang:
            pass  # language recorded but not syntax-highlighted
        return True

    def _try_display_math(self):
        """
        A $$ block that starts its own line.

        Handled here as well as inline so that a blank line inside the maths
        does not end the paragraph and split the block in half.
        """
        line = self.lines[self.i]
        stripped = line.strip()
        if not stripped.startswith("$$"):
            return False

        # $$ ... $$ all on one line
        rest = stripped[2:]
        if rest.rstrip().endswith("$$") and len(rest.rstrip()) >= 2:
            body = rest.rstrip()[:-2]
            self.i += 1
            out = wrap_display(body)
            if out:
                self.out.append(out)
                self.out.append("")
            return True

        body = []
        if rest.strip():
            body.append(rest)
        self.i += 1
        while self.i < len(self.lines):
            cur = self.lines[self.i]
            if "$$" in cur:
                before = cur.split("$$", 1)[0]
                if before.strip():
                    body.append(before)
                self.i += 1
                break
            body.append(cur)
            self.i += 1

        out = wrap_display("\n".join(body))
        if out:
            self.out.append(out)
            self.out.append("")
        return True

    def _try_heading(self):
        m = HEADING_RE.match(self.lines[self.i])
        if not m:
            return False
        level = len(m.group(1)) - 1 + self.heading_offset
        level = max(0, min(level, len(SECTIONS) - 1))
        title = self.inline(m.group(2).strip())

        # Heading text is also copied into the PDF bookmarks, where
        # unicode-math symbols such as \sigma are illegal: "Improper alphabetic
        # constant", and no PDF at all. Give hyperref a plain-text version.
        def bookmark_safe(mm):
            maths = mm.group(1)
            plain = re.sub(r"\\([A-Za-z]+)", r"\1", maths)
            plain = re.sub(r"[{}^_\\$]", "", plain).strip() or "maths"
            return "\\texorpdfstring{$%s$}{%s}" % (maths, plain)

        title = re.sub(r"(?<!\\)\$([^$]+)\$", bookmark_safe, title)
        self.out.append("")
        self.out.append("\\%s{%s}" % (SECTIONS[level], title))
        self.out.append("")
        self.i += 1
        return True

    def _try_hrule(self):
        if not HRULE_RE.match(self.lines[self.i]):
            return False
        self.out.append("\\vspace{0.6em}\\hrule\\vspace{0.6em}")
        self.out.append("")
        self.i += 1
        return True

    def _try_quote(self):
        if not QUOTE_RE.match(self.lines[self.i]):
            return False
        body = []
        while self.i < len(self.lines) and QUOTE_RE.match(self.lines[self.i]):
            body.append(QUOTE_RE.match(self.lines[self.i]).group(1))
            self.i += 1

        # Obsidian callout?
        if body:
            cm = CALLOUT_RE.match(body[0])
            if cm:
                kind = CALLOUT_MAP.get(cm.group(1).lower(), "note")
                title = cm.group(3).strip() or cm.group(1).capitalize()
                inner = Converter(self.ctx, self.line_breaks, auto_offset=False)
                inner.heading_offset = self.heading_offset + 1
                self.out.append("\\begin{%s}[%s]" % (kind, self.inline(title)))
                self.out.append(inner.convert("\n".join(body[1:])))
                self.out.append("\\end{%s}" % kind)
                self.out.append("")
                return True

        inner = Converter(self.ctx, self.line_breaks, auto_offset=False)
        inner.heading_offset = self.heading_offset + 1
        self.out.append("\\begin{quote}")
        self.out.append(inner.convert("\n".join(body)))
        self.out.append("\\end{quote}")
        self.out.append("")
        return True

    def _try_list(self):
        if not (ULIST_RE.match(self.lines[self.i]) or OLIST_RE.match(self.lines[self.i])):
            return False
        # Start at the first item's own indentation: a list whose first bullet
        # is indented used to open \begin{itemize}\begin{itemize} with no
        # \item in between, which LaTeX rejects ("perhaps a missing \item").
        self._emit_list(base_indent=self._indent_of(self.lines[self.i]))
        return True

    def _indent_of(self, line):
        return len(line) - len(line.lstrip())

    def _emit_list(self, base_indent):
        first = self.lines[self.i]
        ordered = bool(OLIST_RE.match(first))
        env = "enumerate" if ordered else "itemize"
        self.out.append("\\begin{%s}" % env)

        while self.i < len(self.lines):
            line = self.lines[self.i]
            if not line.strip():
                # A blank line ends the list unless the next line continues it.
                nxt = self.i + 1
                if nxt < len(self.lines) and (
                    ULIST_RE.match(self.lines[nxt]) or OLIST_RE.match(self.lines[nxt])
                ):
                    self.i += 1
                    continue
                self.i += 1
                break

            mt = TASK_RE.match(line)
            mu = ULIST_RE.match(line)
            mo = OLIST_RE.match(line)
            if not (mu or mo):
                break

            indent = self._indent_of(line)
            if indent < base_indent:
                break
            if indent > base_indent:
                self._emit_list(base_indent=indent)
                continue

            this_ordered = bool(mo)
            if this_ordered != ordered:
                break

            if mt:
                box = "$\\boxtimes$" if mt.group(2).lower() == "x" else "$\\square$"
                content = mt.group(3)
                self.out.append("\\item[%s] %s" % (box, self.inline(content)))
            else:
                content = mo.group(3) if mo else mu.group(2)
                rendered = self.inline(content)
                # "\item [W] ..." would make "[W]" the bullet label.
                if rendered.lstrip().startswith("["):
                    rendered = "{}" + rendered
                self.out.append("\\item %s" % rendered)
            self.i += 1

        self.out.append("\\end{%s}" % env)
        self.out.append("")

    def _try_table(self):
        line = self.lines[self.i]
        if "|" not in line:
            return False
        if self.i + 1 >= len(self.lines):
            return False
        if not TABLE_SEP_RE.match(self.lines[self.i + 1]):
            return False

        header = split_table_row(line)
        aligns_raw = split_table_row(self.lines[self.i + 1])
        self.i += 2

        rows = []
        while self.i < len(self.lines) and "|" in self.lines[self.i]:
            if not self.lines[self.i].strip():
                break
            rows.append(split_table_row(self.lines[self.i]))
            self.i += 1

        ncols = max([len(header)] + [len(r) for r in rows]) if rows else len(header)

        aligns = []
        for a in aligns_raw[:ncols]:
            left, right = a.startswith(":"), a.endswith(":")
            aligns.append("c" if left and right else "r" if right else "l")
        while len(aligns) < ncols:
            aligns.append("l")

        # Tables in these notes are wide and full of maths; p-columns wrap,
        # fixed to an even share of the line width.
        colspec = "".join(
            ">{\\raggedright\\arraybackslash}p{%.3f\\linewidth}" % (0.92 / ncols)
            for _ in range(ncols)
        )

        # <br> has to survive escaping, so it goes in as a sentinel and comes
        # back out as \newline afterwards. Substituting it first would leave
        # a literal "\textbackslash{}newline" in the cell.
        BR = ""

        def cell(c):
            c = re.sub(r"<br\s*/?>", BR, c, flags=re.IGNORECASE)
            return self.inline(c).replace(BR, " \\newline ")

        self.out.append("")
        self.out.append("\\begin{center}")
        self.out.append("\\begin{tabular}{%s}" % colspec)
        self.out.append("\\toprule")
        self.out.append(
            " & ".join("\\hmctablehead{%s}" % cell(h) for h in self._pad(header, ncols))
            + " \\\\"
        )
        self.out.append("\\midrule")
        for r in rows:
            self.out.append(" & ".join(cell(c) for c in self._pad(r, ncols)) + " \\\\")
        self.out.append("\\bottomrule")
        self.out.append("\\end{tabular}")
        self.out.append("\\end{center}")
        self.out.append("")
        return True

    @staticmethod
    def _pad(cells, n):
        return list(cells) + [""] * (n - len(cells))

    def _paragraph(self):
        buf = []
        while self.i < len(self.lines):
            line = self.lines[self.i]
            if not line.strip():
                self.i += 1
                break
            if (
                HEADING_RE.match(line)
                or FENCE_RE.match(line)
                or HRULE_RE.match(line)
                or QUOTE_RE.match(line)
                or ULIST_RE.match(line)
                or OLIST_RE.match(line)
                or line.strip().startswith("$$")
            ):
                break
            if "|" in line and self.i + 1 < len(self.lines) and TABLE_SEP_RE.match(
                self.lines[self.i + 1]
            ):
                break
            buf.append(line)
            self.i += 1
        if not buf:
            if self.i < len(self.lines) and not self.lines[self.i].strip():
                self.i += 1
            return

        # Protect maths across the WHOLE paragraph first: a $$...$$ block runs
        # over several lines, so protecting each line on its own would never
        # match it and the maths would get escaped into literal text. After
        # stashing, each block is a single placeholder token on one line, so
        # splitting for line breaks is then safe.
        vault = Vault()
        protected = protect_math_and_code("\n".join(buf), vault)
        pieces = [convert_protected(line, self.ctx, vault)
                  for line in protected.split("\n")]

        # Images and display maths are blocks: a "\\" before or after one is
        # either a LaTeX error or an ugly gap, so they interrupt the run of
        # line-broken text rather than joining it.
        def is_block(p):
            return "\\embed" in p or "\\[" in p

        def join_run(lines_in_run):
            if not self.line_breaks:
                return "\n".join(lines_in_run)
            # "\\" followed by "[" or "*" is read as \\[<length>] or \\*, so a
            # line like "[W] refers to the units of Wb" became a bogus
            # vertical-space argument and killed the build. "\\{}" stops that.
            out = lines_in_run[0]
            for nxt in lines_in_run[1:]:
                guard = "{}" if nxt.lstrip().startswith(("[", "*")) else ""
                out += " \\\\%s\n%s" % (guard, nxt)
            return out

        rendered, run = [], []
        for p in pieces:
            if is_block(p):
                if run:
                    rendered.append(join_run(run))
                    run = []
                rendered.append(p)
            else:
                run.append(p)
        if run:
            rendered.append(join_run(run))

        self.out.append("\n".join(rendered))
        self.out.append("")


# ---------------------------------------------------------------------------
# Frontmatter + document assembly
# ---------------------------------------------------------------------------

def split_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip("\"'")
    return meta, text[m.end():]


PREAMBLE_TEMPLATE = r"""%% Generated by build/md2tex.py from %(source)s
%% Edit the .md and rebuild; changes here will be overwritten.
\documentclass[%(mode)s]{hmcnote}
\usepackage{preamble}
\usepackage{soul}
\usepackage[normalem]{ulem}
\usepackage{fancyvrb}

\course{%(course)s}

\begin{document}

\lecture{%(number)s}{%(title)s}{%(date)s}

"""


def build_document(source, body, meta, mode):
    title = meta.get("title") or Path(source).stem
    course = meta.get("course") or Path(source).resolve().parent.parent.name
    date = meta.get("date", "")
    number = meta.get("lecture", "")

    # "12 Wavefunctions.md" -> lecture 12, title "Wavefunctions"
    m = re.match(r"^(\d+)[\s.\-_]+(.*)$", title)
    if m and not number:
        number, title = m.group(1), m.group(2)

    head = PREAMBLE_TEMPLATE % {
        "source": Path(source).name.replace("_", "\\_"),
        "mode": mode,
        "course": escape_text(course),
        "number": escape_text(str(number)),
        "title": escape_text(title),
        "date": escape_text(date),
    }
    return head + body + "\n\n\\end{document}\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="markdown note")
    ap.add_argument("-o", "--output", help="output .tex (default: alongside source)")
    ap.add_argument("--vault-root", help="search root for embedded images")
    ap.add_argument("--dark", action="store_true", help="dark PDF (default)")
    ap.add_argument("--light", action="store_true", help="light PDF")
    ap.add_argument("--body-only", action="store_true",
                    help="emit the body without a document wrapper")
    args = ap.parse_args()

    mode = "light" if args.light else "dark"

    src = Path(args.source)
    if not src.exists():
        sys.exit("No such file: %s" % src)

    raw = src.read_text(encoding="utf-8", errors="replace")
    meta, body_md = split_frontmatter(raw)

    out = Path(args.output) if args.output else src.with_suffix(".tex")
    ctx = Context(src, args.vault_root, out_dir=out.parent)
    body = Converter(ctx).convert(body_md)

    if args.body_only:
        result = body
    else:
        result = build_document(src, body, meta, mode)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result, encoding="utf-8")

    print("Wrote %s" % out)
    if ctx.missing_assets:
        print("  %d unresolved image(s):" % len(ctx.missing_assets))
        for a in sorted(ctx.missing_assets)[:10]:
            print("    %s" % a)


if __name__ == "__main__":
    main()
