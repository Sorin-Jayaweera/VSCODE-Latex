# HMC Notes in VS Code

Your Obsidian setup, rebuilt as a local LaTeX workspace: the same Latex Suite
snippets, the same Tokyo Night look, the same notes — plus real LaTeX when you
want it.

---

## 1. One-time setup

### Extensions

Already installed on this machine:

| Extension | What it does here |
| --- | --- |
| **LaTeX Workshop** | Builds `.tex`, PDF beside the editor, SyncTeX, hover maths preview |
| **HyperSnips** (+ its helper **hscopes**) | Runs your ported Latex Suite snippets |
| **Obsidian Embeds Preview** | Shows `![[Pasted image ...]]` images in the markdown preview. Lives in this repo at `tools/obsidian-preview/` |

If you ever need to reinstall the embeds extension:

```bash
python tools/obsidian-preview/pack_vsix.py
```

```bash
code --install-extension tools/obsidian-preview/obsidian-embeds-preview-0.1.0.vsix --force
```

### Disable the conflicting extensions (important)

`Ctrl+Shift+X`, search each name, gear icon → **Disable**:

| Extension | Problem |
| --- | --- |
| `oskar-idland.hypersnipsv2` | A HyperSnips fork. Registers the same `.hsnips` language; can double-fire snippets. |
| `jeffersonqin.latex-snippets-jeff` | Its own LaTeX triggers collide with yours. |
| `mathematic.vscode-latex` | Duplicate LaTeX grammar, fights LaTeX Workshop. |
| `torn4dom4n.latex-support` | Same. |

Keep `tecosaur.latex-utilities` — it complements LaTeX Workshop.

Then `Ctrl+Shift+P` → **Developer: Reload Window**.

### Keybindings

VS Code stores these per-user, so the repo can't set them. `Ctrl+Shift+P` →
*Preferences: Open Keyboard Shortcuts (JSON)*, and paste the entries from
[.vscode/keybindings-to-copy.json](.vscode/keybindings-to-copy.json) inside the
existing `[ ... ]`.

### Check it works

`File → Open Folder` → this folder, then:

1. Open any note under `notes/`. Inside `$ $` type `ptl` → `\partial`. On an
   empty line type `dm` → a `$$ \begin{align} … \end{align} $$` block.
2. `Ctrl+Alt+V` → preview beside the note, with maths **and images**.
3. `Ctrl+Alt+B` → the PDF appears in `pdfs/` next to the note.

---

## 2. Where PDFs go

Every build — markdown or LaTeX, from the task or from LaTeX Workshop — writes:

```
<folder the note is in>/pdfs/<same name>.pdf
```

`notes/Junior/Big Quantum/Lectures/1 Spin angular momentum.md` →
`notes/Junior/Big Quantum/Lectures/pdfs/1 Spin angular momentum.pdf`

Scratch files (generated `.tex`, `.aux`, `.log`) go to `.build/`, which is
git-ignored and safe to delete. A markdown note is converted **into `.build/`**,
never next to the note, so a hand-written `.tex` with the same name is never
overwritten.

> 52 notes already had an Obsidian-exported PDF with the same name in their
> `pdfs/` folder. Building one of those notes replaces that PDF in this copy.
> The originals in your Obsidian vault are untouched, and git keeps history.

---

## 3. Writing in Markdown (the daily driver)

Open a note under `notes/` and write exactly as in Obsidian — `$...$`,
`$$...$$`, `![[Pasted image ...]]`, tables, `> [!note]` callouts.

| Key | Action |
| --- | --- |
| `Ctrl+Alt+V` | Live preview beside the editor: maths and images |
| `Ctrl+Alt+B` | Build this note → `pdfs/` |
| `Ctrl+Alt+M` | Maths preview panel following your cursor |
| `Ctrl+Alt+S` | Wrap selection (the old `${VISUAL}` snippets) |

**About seeing maths rendered:** nothing in VS Code reproduces Latex Suite's
in-editor concealment (where `\frac{1}{2}` collapses to a fraction inside the
editor itself). The side-by-side preview re-renders as you type, and hovering
any maths shows it rendered at the cursor.

---

## 4. Writing in LaTeX

Copy [`template.tex`](template.tex), rename it, start typing. Save → LaTeX
Workshop builds with latexmk and refreshes the PDF tab. `Ctrl+Alt+J` jumps from
the cursor to that spot in the PDF; `Ctrl+click` in the PDF jumps back.

```latex
\documentclass[dark]{hmcnote}   % or [light] for printing
\usepackage{preamble}

\course{Phys 116 -- Quantum Mechanics}
\begin{document}
\lecture{4}{Stern--Gerlach}{2026-01-21}

$\ket{\psi} = c_+\ket{+z} + c_-\ket{-z}$, and $\braket{ +z | \psi } = c_+$.

\end{document}
```

| Command | Result |
| --- | --- |
| `\lecture{4}{Title}{date}` | Title block |
| `\course{...}` | Running header on later pages |
| `\embed{Pasted image ....png}` | Centred image, clamped to the page |
| `\begin{note}[Title]` | Callout card (also `tip`, `warning`, `important`, `example`) |
| `\begin{theorem}` | Numbered (also `lemma`, `definition`, `corollary`, `proposition`, `remark`) |

Your Obsidian macros are in [`tex/preamble.sty`](tex/preamble.sty): `\bb`,
`\bvec`, `\pardx`, `\ddx`, `\norm`, `\abs`, `\curl`, `\div`, `\grad`, `\vspan`,
plus `\ket`, `\bra`, `\braket{ a | b }` (bar inside, as you write it), `\ketbra`.
`\sqrt[]{x}` — what your `sq` snippet produces — is handled; unicode-math would
otherwise crash on the empty `[]`.

`hmcnote.cls` and `preamble.sty` are installed into your TeX user tree
(`C:\Users\Sorin\texmf`), so any `.tex` anywhere finds them. Editing `tex/` is
enough: every build refreshes the installed copy.

---

## 5. Snippets

All of your Latex Suite snippets are ported into [`hsnips/`](hsnips/) and
behave as in Obsidian: auto-expanding, maths-only ones only in maths, tabstops
in the same order (`//` puts you in the numerator first).

**Selection wrappers** (`U` underbrace, `C` cancel, `S` sqrt, brackets): select
the expression, `Ctrl+Alt+S`, pick one. HyperSnips can't do Latex Suite's
`${VISUAL}`.

**Custom snippets:** put them in
[`build/manual_snippets.hsnips`](build/manual_snippets.hsnips). Don't edit
`hsnips/*.hsnips` — they are regenerated.

**After adding snippets in Obsidian:**

```bash
python build/port_snippets.py --install
```

```bash
node build/test_snippets.js
```

The second command loads HyperSnips' **own** parser and matcher and types test
cases, so a broken snippet file shows up here instead of silently doing nothing
in the editor. Add a case to the `CASES` list if you want a snippet guarded.

`--install` also copies the snippets into HyperSnips' own folder so they work
in any VS Code window. Your previous HyperSnips `latex.hsnips` from before this
setup was backed up to `build/backup-original-global-hsnips/`.

---

## 6. Dark and light

```bash
python build/build.py "notes/Junior/Big Quantum/Lectures/1 Spin angular momentum.md" --light
```

In `.tex`: `\documentclass[dark]{hmcnote}` or `[light]`. Dark matches Obsidian
on screen; light deepens the accents so they survive on white paper.

---

## 7. Re-importing notes from Obsidian

`notes/` is a copy; Obsidian is still the live vault.

```bash
python build/import_vault.py
```

---

## 8. GitHub sync

Pushes to
[Sorin-Jayaweera/VSCODE-Latex](https://github.com/Sorin-Jayaweera/VSCODE-Latex).
A scheduled task, *HMC Notes GitHub Sync*, commits and pushes every 30 minutes.

```powershell
.\build\autosync.ps1 -Status
```

```powershell
.\build\autosync.ps1 -Remove
```

Sync now: task **Sync to GitHub now**, or `python build/sync.py`.

---

## 9. What is where

```
vscode latex/
├── template.tex              copy this to start a LaTeX note
├── tex/                      hmcnote.cls (look) + preamble.sty (macros)
├── hsnips/                   generated snippets
├── notes/                    your notes; PDFs build into each folder's pdfs/
├── tools/obsidian-preview/   the ![[embed]] preview extension
├── build/
│   ├── build.py              note -> <folder>/pdfs/<name>.pdf
│   ├── md2tex.py             Obsidian markdown -> LaTeX
│   ├── port_snippets.py      Latex Suite -> HyperSnips
│   ├── manual_snippets.hsnips  your hand-written snippets
│   ├── test_snippets.js      runs HyperSnips' real code on the snippets
│   ├── install_class.py      puts the class where TeX finds it
│   ├── smoke_test.py         converts every note, compiles a sample
│   ├── import_vault.py, sync.py, autosync.ps1
├── .build/                   scratch (git-ignored)
└── .vscode/                  settings, tasks, keybindings to copy
```

---

## 10. Known gaps

- **No in-editor maths concealment** in VS Code (see §3).
- **Notes written for MathJax don't always compile in real LaTeX.** MathJax
  forgives things LaTeX doesn't. The converter repairs the common ones (empty
  `\sqrt[]`, `\begin{align}` nested inside `$$`, `\\` just before `\right`,
  maths in headings); when a note still fails, the build prints the line and the
  full log path under `.build/`.
- **21 Excalidraw drawings** in `notes/special/FriendsNotes/Phys51/` can't be
  typeset (vector JSON, not prose).
- **19 image references point at images that were never in the vault**, all in
  `notes/special/FriendsNotes/`. They render as *[missing image]*.

---

## 11. If something breaks

**A note won't build.** The error and log path are printed. The generated LaTeX
is in `.build/` at the same relative path as the note.

**Snippets stopped firing.** Run `node build/test_snippets.js`. If that passes,
check HyperSnips is enabled and the conflicting extensions in §1 are disabled,
then reload the window.

**Images missing in the preview.** Check *Obsidian Embeds Preview* is enabled,
then reload the window.
