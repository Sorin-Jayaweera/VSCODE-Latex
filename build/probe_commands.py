#!/usr/bin/env python3
"""
probe_commands.py -- Which commands do the notes use that real LaTeX lacks?

Obsidian renders maths with MathJax, which ships extensions (mhchem's \\pu and
\\ce, physics-style shorthands, ...) that a LaTeX document only has if it loads
the right package. Rather than discovering those one failed build at a time,
this collects every \\command used inside $...$ / $$...$$ across the notes and
asks LuaLaTeX, under hmcnote + preamble, which ones are undefined.

    python build/probe_commands.py
"""

import collections
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NOTES = ROOT / "notes"
WORK = ROOT / ".build" / "probe"

MATH_RE = re.compile(r"\$\$(.+?)\$\$|\$([^$\n]+?)\$", re.S)
CMD_RE = re.compile(r"\\([A-Za-z]+)")


def main():
    counts = collections.Counter()
    where = collections.defaultdict(set)
    for p in NOTES.rglob("*.md"):
        if p.name.endswith(".excalidraw.md"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in MATH_RE.finditer(text):
            for name in CMD_RE.findall(m.group(1) or m.group(2) or ""):
                counts[name] += 1
                where[name].add(str(p.relative_to(NOTES)))

    names = sorted(counts)
    lines = [r"\documentclass[dark]{hmcnote}", r"\usepackage{preamble}", r"\begin{document}"]
    for n in names:
        lines.append(r"\ifcsname %s\endcsname\else\typeout{UNDEF:%s}\fi" % (n, n))
    lines.append(r"\end{document}")

    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "probe.tex").write_text("\n".join(lines), encoding="utf-8")
    subprocess.run(
        ["lualatex", "-interaction=nonstopmode", "probe.tex"],
        cwd=str(WORK), capture_output=True, text=True, errors="replace",
    )
    log = (WORK / "probe.log").read_text(encoding="utf-8", errors="replace")
    undefined = sorted(set(re.findall(r"UNDEF:([A-Za-z]+)", log)), key=lambda n: -counts[n])

    print("%d distinct commands used in maths; %d undefined under hmcnote + preamble\n"
          % (len(names), len(undefined)))
    print("  uses  notes  command              example note")
    for n in undefined:
        print("  %4d  %5d  \\%-19s %s" % (counts[n], len(where[n]), n, sorted(where[n])[0][:60]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
