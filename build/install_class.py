#!/usr/bin/env python3
"""
install_class.py -- Put hmcnote.cls and preamble.sty where TeX always finds them.

Relying on TEXINPUTS is fragile: LaTeX Workshop does not expand
${workspaceFolder} inside a tool's `env`, so the variable never reaches
LuaLaTeX and you get "File `hmcnote.cls' not found". Installing into TEXMFHOME
removes the problem for every tool, from any folder, forever.

    python build/install_class.py           # install / refresh
    python build/install_class.py --status
    python build/install_class.py --remove

build.py calls this automatically when tex/ is newer than the installed copy,
so editing the class is enough -- you do not have to remember to re-run it.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TEXDIR = ROOT / "tex"
PACKAGE = "hmcnote"


def texmfhome():
    try:
        out = subprocess.run(
            ["kpsewhich", "-var-value", "TEXMFHOME"],
            capture_output=True, text=True, errors="replace",
        ).stdout.strip()
    except FileNotFoundError:
        out = ""
    if not out:
        out = str(Path.home() / "texmf")
    return Path(out.replace("\\", "/"))


def target_dir():
    return texmfhome() / "tex" / "latex" / PACKAGE


def sources():
    return sorted(
        list(TEXDIR.glob("*.cls")) + list(TEXDIR.glob("*.sty"))
    )


def needs_install():
    """True when any source is newer than its installed copy (or missing)."""
    dest = target_dir()
    for src in sources():
        tgt = dest / src.name
        if not tgt.exists() or src.stat().st_mtime > tgt.stat().st_mtime:
            return True
    return False


def install(quiet=False):
    dest = target_dir()
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for src in sources():
        shutil.copy2(src, dest / src.name)
        copied.append(src.name)
    if not quiet:
        print("Installed into %s" % dest)
        for name in copied:
            print("    %s" % name)
    return copied


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--remove", action="store_true")
    args = ap.parse_args()

    dest = target_dir()

    if args.remove:
        for src in sources():
            tgt = dest / src.name
            if tgt.exists():
                tgt.unlink()
                print("Removed %s" % tgt)
        return 0

    if args.status:
        print("TEXMFHOME : %s" % texmfhome())
        print("Target    : %s" % dest)
        for src in sources():
            tgt = dest / src.name
            if not tgt.exists():
                state = "NOT INSTALLED"
            elif src.stat().st_mtime > tgt.stat().st_mtime:
                state = "STALE (source is newer)"
            else:
                state = "up to date"
            print("    %-16s %s" % (src.name, state))
        # Prove TeX can actually find it.
        found = subprocess.run(
            ["kpsewhich", "hmcnote.cls"],
            capture_output=True, text=True, errors="replace",
        ).stdout.strip()
        print("\nkpsewhich hmcnote.cls -> %s" % (found or "NOT FOUND"))
        return 0

    install()
    found = subprocess.run(
        ["kpsewhich", "hmcnote.cls"],
        capture_output=True, text=True, errors="replace",
    ).stdout.strip()
    print("\nkpsewhich hmcnote.cls -> %s" % (found or "NOT FOUND"))
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
