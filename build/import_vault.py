#!/usr/bin/env python3
"""
import_vault.py -- Copy the Obsidian vault's notes into notes/.

Copies markdown and images verbatim. Excludes Obsidian's own machinery
(.obsidian, .git, .trash) and anything that is not a note or an asset.

Excalidraw drawings (*.excalidraw.md) are copied but flagged: they are vector
JSON, not prose, and cannot be typeset. Install the Excalidraw plugin in
Obsidian and export them to SVG if you want them in a PDF.

Usage:
    python build/import_vault.py                 # from the default vault
    python build/import_vault.py PATH_TO_VAULT
    python build/import_vault.py --dry-run
"""

import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_VAULT = ROOT.parent / "HMC"

SKIP_DIRS = {".obsidian", ".git", ".trash", ".smart-env", "node_modules"}
COPY_EXT = {
    ".md", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg",
    ".pdf", ".sty", ".bib", ".csv", ".txt",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vault", nargs="?", default=str(DEFAULT_VAULT))
    ap.add_argument("--dest", default=str(ROOT / "notes"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-pdfs", action="store_true",
                    help="skip loose reference PDFs (~194 MB of the vault); "
                         "markdown and images are always copied")
    args = ap.parse_args()

    copy_ext = set(COPY_EXT)
    if args.no_pdfs:
        copy_ext.discard(".pdf")

    vault = Path(args.vault).resolve()
    dest = Path(args.dest).resolve()
    if not vault.exists():
        sys.exit("No vault at %s" % vault)

    copied = skipped = 0
    excalidraw = []
    bytes_copied = 0

    for src in vault.rglob("*"):
        if not src.is_file():
            continue
        if any(part in SKIP_DIRS for part in src.relative_to(vault).parts):
            continue
        if src.suffix.lower() not in copy_ext:
            skipped += 1
            continue

        rel = src.relative_to(vault)
        if src.name.endswith(".excalidraw.md"):
            excalidraw.append(rel)

        target = dest / rel
        if not args.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
        copied += 1
        bytes_copied += src.stat().st_size

    print("Vault : %s" % vault)
    print("Dest  : %s" % dest)
    print("Copied: %d files (%.1f MB)%s"
          % (copied, bytes_copied / 1048576.0, " [dry run]" if args.dry_run else ""))
    print("Skipped %d files of other types" % skipped)
    if excalidraw:
        print("\n%d Excalidraw drawing(s) copied verbatim (cannot be typeset):"
              % len(excalidraw))
        for r in excalidraw[:3]:
            print("    %s" % r)
        if len(excalidraw) > 3:
            print("    ... and %d more" % (len(excalidraw) - 3))


if __name__ == "__main__":
    main()
