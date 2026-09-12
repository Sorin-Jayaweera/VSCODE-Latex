#!/usr/bin/env python3
"""
smoke_test.py -- Run the markdown converter over every note and report trouble.

Conversion is fast; compiling is not. So this converts all of them to catch
crashes and suspicious output, and optionally compiles a sample.

    python build/smoke_test.py                # convert everything, report
    python build/smoke_test.py --compile 12   # also compile 12 random notes
"""

import argparse
import random
import re
import subprocess
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from md2tex import Context, Converter, split_frontmatter, build_document  # noqa: E402

NOTES = ROOT / "notes"

# Things that mean the converter produced something LaTeX will choke on.
SUSPECT = [
    (re.compile(r"\\textbackslash\{\}(newline|item|begin|end|embed)"),
     "escaped LaTeX command leaked into text"),
    (re.compile(r"\ue000|\ue001|\ue010"), "unrestored placeholder"),
    (re.compile(r"\\begin\{(itemize|enumerate)\}\s*\\end\{"), "empty list"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--compile", type=int, default=0,
                    help="also compile N randomly chosen notes")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    notes = sorted(
        p for p in NOTES.rglob("*.md") if not p.name.endswith(".excalidraw.md")
    )
    print("Converting %d notes...\n" % len(notes))

    crashed, suspect, missing_assets = [], [], {}
    total_missing = 0

    for p in notes:
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
            meta, body_md = split_frontmatter(raw)
            ctx = Context(p, NOTES, out_dir=p.parent)
            body = Converter(ctx).convert(body_md)
            tex = build_document(p, body, meta, "dark")
        except Exception:
            crashed.append((p, traceback.format_exc().strip().splitlines()[-1]))
            continue

        for rx, why in SUSPECT:
            if rx.search(tex):
                suspect.append((p, why))
                break

        if ctx.missing_assets:
            missing_assets[p] = ctx.missing_assets
            total_missing += len(ctx.missing_assets)

    print("crashed          : %d" % len(crashed))
    print("suspect output   : %d" % len(suspect))
    print("notes w/ missing images: %d  (%d refs)"
          % (len(missing_assets), total_missing))

    for p, err in crashed[:10]:
        print("\n  CRASH %s\n        %s" % (p.relative_to(NOTES), err))
    for p, why in suspect[:10]:
        print("\n  SUSPECT %s\n          %s" % (p.relative_to(NOTES), why))

    if missing_assets:
        print("\n  first few notes with unresolved images:")
        for p, assets in list(missing_assets.items())[:5]:
            print("    %s" % p.relative_to(NOTES))
            for a in list(assets)[:3]:
                print("        %s" % a)

    if args.compile:
        random.seed(args.seed)
        sample = random.sample(notes, min(args.compile, len(notes)))
        print("\n\nCompiling %d sampled notes...\n" % len(sample))
        ok, bad = 0, []
        for p in sample:
            proc = subprocess.run(
                [sys.executable, str(HERE / "build.py"), str(p)],
                capture_output=True, text=True, errors="replace",
            )
            if proc.returncode == 0:
                ok += 1
                print("  ok    %s" % p.relative_to(NOTES))
            else:
                bad.append((p, proc.stderr.strip().splitlines()[:6]))
                print("  FAIL  %s" % p.relative_to(NOTES))
        print("\n%d/%d compiled" % (ok, len(sample)))
        for p, err in bad:
            print("\n  %s" % p.relative_to(NOTES))
            for line in err:
                print("      %s" % line)

    return 1 if crashed else 0


if __name__ == "__main__":
    sys.exit(main())
