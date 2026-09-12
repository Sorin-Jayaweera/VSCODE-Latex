#!/usr/bin/env python3
"""
build.py -- Markdown or LaTeX note  ->  PDF, saved next to the note.

    python build/build.py "notes/Junior/Big Quantum/Lectures/1 Spin angular momentum.md"
    python build/build.py template.tex --light
    python build/build.py --all "notes/Junior/Big Quantum/Lectures"

Output:   <folder the note is in>/pdfs/<same name>.pdf
Scratch:  .build/   generated .tex, .aux, .log -- git-ignored, safe to delete

A .md is converted into .build/ rather than next to the note, so a hand-written
.tex that happens to share the note's name is never overwritten.
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TEXDIR = ROOT / "tex"
BUILDDIR = ROOT / ".build"

# Left over from a failed run, these can themselves abort the next one
# (a half-written .out made Lab 1 die with "Emergency stop" on line 1).
STALE_AUX = (".aux", ".out", ".toc", ".lof", ".lot")


def texinputs():
    """Belt and braces: the class is in TEXMFHOME, but tex/ wins if newer."""
    env = dict(os.environ)
    sep = ";" if os.name == "nt" else ":"
    existing = env.get("TEXINPUTS", "")
    env["TEXINPUTS"] = sep.join([".", str(TEXDIR), existing])
    return env


def ensure_class_installed():
    """
    Keep the copy in TEXMFHOME in step with tex/.

    The class lives in TEXMFHOME so that LaTeX Workshop -- which never passes
    our TEXINPUTS through -- can find it from any folder. Refreshing here
    means editing tex/ is enough; nobody has to remember to reinstall.
    """
    try:
        sys.path.insert(0, str(HERE))
        import install_class

        if install_class.needs_install():
            install_class.install(quiet=True)
            print("(refreshed hmcnote.cls in TEXMFHOME)")
    except Exception as exc:  # never let this break a build
        print("Warning: could not refresh the installed class: %s" % exc,
              file=sys.stderr)


def scratch_dir_for(source):
    """Mirror the note's folder under .build/, or hash it if outside the repo."""
    parent = source.resolve().parent
    try:
        return BUILDDIR / parent.relative_to(ROOT)
    except ValueError:
        digest = hashlib.sha1(str(parent).encode("utf-8")).hexdigest()[:10]
        return BUILDDIR / "external" / digest


def pdf_destination(source):
    return source.resolve().parent / "pdfs" / (source.stem + ".pdf")


def vault_root_for(source):
    """Where to look for embedded images: the enclosing vault, or notes/."""
    notes = (ROOT / "notes").resolve()
    for p in [source.resolve().parent] + list(source.resolve().parents):
        if (p / ".obsidian").is_dir() or p == notes:
            return p
    return source.resolve().parent


def display(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def run_latex(tex_path, work_dir, engine="lualatex", passes=2):
    tex_path = Path(tex_path).resolve()
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    for ext in STALE_AUX:
        stale = work_dir / (tex_path.stem + ext)
        if stale.exists():
            stale.unlink()
    pdf = work_dir / (tex_path.stem + ".pdf")
    if pdf.exists():
        pdf.unlink()

    cmd = [
        engine,
        "-interaction=nonstopmode",
        "-file-line-error",
        "-synctex=1",
        "-output-directory=%s" % work_dir,
        tex_path.name,
    ]

    def complete_pdf(path):
        """A fully written PDF ends with %%EOF; a fatal or aborted run doesn't."""
        try:
            with open(path, "rb") as fh:
                fh.seek(0, 2)
                size = fh.tell()
                fh.seek(max(0, size - 2048))
                return size > 0 and b"%%EOF" in fh.read()
        except OSError:
            return False

    log_path = work_dir / (tex_path.stem + ".log")
    rc, stdout, attempt, fatal = 0, "", 0, False
    for attempt in range(1, passes + 1):
        proc = subprocess.run(
            cmd,
            cwd=str(tex_path.parent),
            env=texinputs(),
            capture_output=True,
            text=True,
            errors="replace",
        )
        rc, stdout = proc.returncode, proc.stdout
        fatal = "no output PDF file produced" in stdout or not complete_pdf(pdf)
        if fatal:
            break

    errs = [
        l for l in stdout.splitlines()
        if l.startswith("!") or (".tex:" in l and "rror" in l)
    ]

    # Fatal = no PDF, or a truncated one (which is what once looked like
    # success but had no images). Don't leave that behind as "output".
    if fatal:
        print("LaTeX failed (pass %d) on %s:" % (attempt, tex_path.name), file=sys.stderr)
        for e in errs[:12]:
            print("   ", e, file=sys.stderr)
        if not errs:
            print("\n".join(stdout.splitlines()[-25:]), file=sys.stderr)
        print("    full log: %s" % log_path, file=sys.stderr)
        if pdf.exists():
            pdf.unlink()
        return None

    # A non-zero exit with a complete PDF means nonstopmode recovered from an
    # error (typically MathJax-only syntax). Keep the PDF, but say so.
    if rc != 0:
        print("  warning: %s had LaTeX errors but produced a complete PDF -- "
              "check the flagged spots:" % tex_path.name, file=sys.stderr)
        for e in errs[:6]:
            print("   ", e, file=sys.stderr)
        print("    full log: %s" % log_path, file=sys.stderr)
    return pdf


def build_one(source, mode, engine, keep_tex=False, quiet=False):
    source = Path(source).resolve()
    if not source.exists():
        print("No such file: %s" % source, file=sys.stderr)
        return None

    t0 = time.time()
    scratch = scratch_dir_for(source)
    scratch.mkdir(parents=True, exist_ok=True)

    suffix = source.suffix.lower()
    if suffix == ".md":
        tex = scratch / (source.stem + ".tex")
        cmd = [
            sys.executable, str(HERE / "md2tex.py"), str(source),
            "-o", str(tex),
            "--vault-root", str(vault_root_for(source)),
            "--%s" % mode,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        if proc.returncode != 0:
            print(proc.stdout + proc.stderr, file=sys.stderr)
            return None
        if not quiet:
            for line in proc.stdout.strip().splitlines()[1:]:
                print("   ", line)
        if keep_tex:
            print("    generated LaTeX: %s" % display(tex))
    elif suffix == ".tex":
        tex = source
    else:
        print("Not a .md or .tex: %s" % source, file=sys.stderr)
        return None

    pdf = run_latex(tex, scratch, engine=engine)
    if not pdf:
        return None

    dest = pdf_destination(source)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(pdf, dest)
    except PermissionError:
        print("Built, but could not write %s -- is it open in a PDF viewer "
              "that locks files (Acrobat)? Close it and rebuild." % dest,
              file=sys.stderr)
        return None

    print("%s  ->  %s  (%.1fs)" % (source.name, display(dest), time.time() - t0))
    return dest


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
                    help="print where the generated .tex is (it stays in .build/)")
    args = ap.parse_args()

    mode = "light" if args.light else "dark"
    ensure_class_installed()

    if args.all:
        folder = Path(args.source)
        notes = sorted(
            p for p in folder.rglob("*.md")
            if not p.name.endswith(".excalidraw.md")
        )
        print("Building %d note(s) from %s\n" % (len(notes), folder))
        ok, failures = 0, []
        for n in notes:
            if build_one(n, mode, args.engine, args.keep_tex, quiet=True):
                ok += 1
            else:
                failures.append(n)
        print("\n%d succeeded, %d failed" % (ok, len(failures)))
        for f in failures[:20]:
            print("   FAILED  %s" % display(f))
        return 0 if not failures else 1

    return 0 if build_one(args.source, mode, args.engine, args.keep_tex) else 1


if __name__ == "__main__":
    sys.exit(main())
