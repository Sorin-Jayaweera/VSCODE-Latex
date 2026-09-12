#!/usr/bin/env python3
"""Regenerate and reinstall all VS Code snippet support."""

import subprocess
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(*args):
    print("+", " ".join(map(str, args)))
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True)


def main():
    py = sys.executable
    code = shutil.which("code") or shutil.which("code.cmd")
    if not code:
        raise SystemExit("Could not find VS Code's code command on PATH.")
    run(py, "build/port_snippets.py", "--install")
    aliases = {
        "markdown.hsnips": ["mdx.hsnips", "quarto.hsnips", "plaintext.hsnips"],
        "latex.hsnips": ["tex.hsnips", "latex-expl3.hsnips"],
    }
    global_dir = Path.home() / "AppData" / "Roaming" / "Code" / "User" / "globalStorage" / "draivin.hsnips" / "hsnips"
    for source, targets in aliases.items():
        for target in targets:
            shutil.copy2(ROOT / "hsnips" / source, ROOT / "hsnips" / target)
            if global_dir.exists():
                shutil.copy2(ROOT / "hsnips" / source, global_dir / target)
    run("node", "build/test_snippets.js")
    run(py, "build/export_latex_suite_auto.py")
    run(py, "tools/latex-suite-auto/pack_vsix.py")
    vsix = ROOT / "tools" / "latex-suite-auto" / "latex-suite-auto-0.1.0.vsix"
    run(code, "--install-extension", vsix, "--force")
    print("\nReload VS Code, or run: Ctrl+Shift+P -> Developer: Reload Window")


if __name__ == "__main__":
    main()
