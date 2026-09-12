#!/usr/bin/env python3
"""
build.py -- Markdown or LaTeX note  ->  PDF.

This is what the VS Code build task calls. Give it either a .md or a .tex:

    python build/build.py notes/Junior/Big Quantum/Lectures/1 Spin.md
    python build/build.py template.tex --light
    python build/build.py --all notes/Junior/Big Quantum/Lectures

For a .md it runs md2tex.py first, dropping the generated .tex next to the
source (so relative image paths resolve), then compiles it. The PDF lands in
out/ mirroring the note's folder structure.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TEXDIR = ROOT / "tex"
OUTDIR = ROOT / "out"


def texinputs():
    """TeX needs to find hmcnote.cls and preamble.sty wherever we build."""
    env = dict(os.environ)
    sep = ";" if os.name == "nt" else ":"
    existing = env.get("TEXINPUTS", "")
    env["TEXINPUTS"] = sep.join([".", str(TEXDIR), existing])
    return env


def run_latex(tex_path, out_dir, engine="lualatex", passes=2, quiet=True):
    tex_path = Path(tex_path).resolve()
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd_base = [
        engine,
        "-interaction=nonstopmode",
        "-file-line-error",
        "-output-directory=%s" % out_dir,
    ]

    log_tail = ""
    for i in range(passes):
        proc = subprocess.run(
            cmd_base + [tex_path.name],
            cwd=str(tex_path.parent),
            env=texinputs(),
            capture_output=True,
            text=True,
            errors="replace",
        )
        log_tail = proc.stdout
        pdf = out_dir / (tex_path.stem + ".pdf")
        if proc.returncode != 0 and not pdf.exists():
            errs = [
                l for l in log_tail.splitlines()
                if l.startswith("!") or ".tex:" in l and "Error" in l
            ]
            print("LaTeX failed on pass %d:" % (i + 1), file=sys.stderr)
            for e in errs[:12]:
                print("   ", e, file=sys.stderr)
            if not errs:
                print("\n".join(log_tail.splitlines()[-25:]), file=sys.stderr)
            return None
    return out_dir / (tex_path.stem + ".pdf")


def build_one(source, mode, engine, keep_tex, quiet=False):
    source = Path(source).resolve()
    if not source.exists():
        print("No such file: %s" % source, file=sys.stderr)
        return None

    t0 = time.time()

    if source.suffix.lower() == ".md":
        generated = source.with_suffix(".tex")
        cmd = [
            sys.executable,
            str(HERE / "md2tex.py"),
            str(source),
            "-o", str(generated),
            "--vault-root", str(ROOT / "notes"),
            "--%s" % mode,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        if proc.returncode != 0:
            print(proc.stdout + proc.stderr, file=sys.stderr)
            return None
        if not quiet and proc.stdout.strip():
            for line in proc.stdout.strip().splitlines()[1:]:
                print("   ", line)
        tex = generated
    elif source.suffix.lower() == ".tex":
        tex = source
    else:
        print("Not a .md or .tex: %s" % source, file=sys.stderr)
        return None

    # Mirror the note's location under out/ so PDFs don't collide.
    try:
        rel_parent = tex.parent.relative_to(ROOT)
    except ValueError:
        rel_parent = Path(".")
    out_dir = OUTDIR / rel_parent

    pdf = run_latex(tex, out_dir, engine=engine)

    if tex != source and not keep_tex:
        try:
            tex.unlink()
        except OSError:
            pass

    if pdf and pdf.exists():
        print("%s  ->  %s  (%.1fs)"
              % (source.name, pdf.relative_to(ROOT), time.time() - t0))
        return pdf
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help=".md or .tex file, or a folder with --all")
    ap.add_argument("--all", action="store_true",
                    help="treat SOURCE as a folder and build every .md in it")
    ap.add_argument("--light", action="store_true", help="light PDF")
    ap.add_argument("--dark", action="store_true", help="dark PDF (default)")
    ap.add_argument("--engine", default="lualatex",
                    choices=["lualatex", "xelatex", "pdflatex"])
    ap.add_argument("--keep-tex", action="store_true",
                    help="keep the generated .tex next to the .md")
    args = ap.parse_args()

    mode = "light" if args.light else "dark"

    if args.all:
        folder = Path(args.source)
        notes = sorted(
            p for p in folder.rglob("*.md")
            if not p.name.endswith(".excalidraw.md")
        )
        print("Building %d note(s) from %s\n" % (len(notes), folder))
        ok = fail = 0
        failures = []
        for n in notes:
            if build_one(n, mode, args.engine, args.keep_tex, quiet=True):
                ok += 1
            else:
                fail += 1
                failures.append(n)
        print("\n%d succeeded, %d failed" % (ok, fail))
        for f in failures[:20]:
            print("   FAILED  %s" % f)
        return 0 if fail == 0 else 1

    return 0 if build_one(args.source, mode, args.engine, args.keep_tex) else 1


if __name__ == "__main__":
    sys.exit(main())
