# HMC Notes in VS Code

Your Obsidian setup, rebuilt as a local LaTeX workspace: the same 425 snippets,
the same Tokyo Night look, the same 559 notes — plus real LaTeX when you want it.

---

## 1. One-time setup (about three minutes)

**Install two extensions.** Open this folder in VS Code; it will offer them.
Or run:

```bash
code --install-extension james-yu.latex-workshop --install-extension draivin.hsnips
```

| Extension | What it does here |
| --- | --- |
| **LaTeX Workshop** | Compiles, shows the PDF side by side, SyncTeX, hover math preview |
| **HyperSnips** | Runs your ported Latex Suite snippets — auto-expanding, math-aware |

**Copy the keybindings.** VS Code stores these per-user, so the repo can't set
them. Open `Ctrl+Shift+P` → *Preferences: Open Keyboard Shortcuts (JSON)* and
paste in the entries from [.vscode/keybindings-to-copy.json](.vscode/keybindings-to-copy.json).

That's it. TeX Live 2025 and Python are already on this machine.

---

## 2. Writing a note in Markdown (the daily driver)

Your notes already work. Open any file under `notes/` and type exactly as you do
in Obsidian — `$...$`, `![[Pasted image ...]]`, tables, `> [!note]` callouts.

| Key | Action |
| --- | --- |
| `Ctrl+Alt+V` | Live preview beside the editor. Math renders as you type. |
| `Ctrl+Alt+B` | Build this note to PDF |

The PDF lands in `out/`, mirroring the note's folder.

### About seeing math rendered

You asked to see the rendered form once you leave an equation. Here is the
honest state of things: **nothing in VS Code reproduces Latex Suite's inline
concealment**, where `\frac{1}{2}` visually collapses to a fraction in the
editor itself. That is an Obsidian-specific editor extension and there is no
equivalent for `.tex` or `.md` in VS Code.

What you get instead, and it is close in practice:

1. **Side-by-side live preview** (`Ctrl+Alt+V` on markdown). Math re-renders as
   you type, in a pane next to your source. Your macros — `\bb`, `\pardx`,
   `\vspan`, `\ket` — are configured in `.vscode/settings.json` so they render
   here exactly as in Obsidian.
2. **Hover preview.** Hover any math span and a rendered image of it pops up,
   right where the cursor is. This is the nearest thing to "check what I just
   typed" without leaving the line.
3. **Math preview panel** (`Ctrl+Alt+M`) — a docked pane that continuously shows
   the equation your cursor is currently inside.

For LaTeX files, `Ctrl+Alt+J` jumps from the cursor to that exact spot in the
PDF, and `Ctrl+click` in the PDF jumps back to the source line.

---

## 3. Writing a note in LaTeX

Copy [`template.tex`](template.tex), rename it, and start typing. Save, and
LaTeX Workshop compiles and refreshes the PDF pane automatically.

```latex
\documentclass[dark]{hmcnote}   % or [light]
\usepackage{preamble}

\course{Phys 116 -- Quantum Mechanics}
\begin{document}
\lecture{4}{Stern--Gerlach}{2026-01-21}

Your text. $\ket{\psi} = c_+\ket{+z} + c_-\ket{-z}$ and so on.

\end{document}
```

### What the class gives you

| Command | Result |
| --- | --- |
| `\lecture{4}{Title}{date}` | The title block at the top |
| `\course{...}` | Running header on later pages |
| `\embed{Pasted image ....png}` | An image, centred and clamped to the page |
| `\begin{note}[Title]` | Blue callout card (also `tip`, `warning`, `important`, `example`) |
| `\begin{theorem}` | Numbered theorem (also `lemma`, `definition`, `corollary`, `proposition`, `remark`) |
| `\hmctablehead{...}` | Table header cell in the accent colour |

Your macros from Obsidian's `preamble.sty` are all in
[`tex/preamble.sty`](tex/preamble.sty): `\bb`, `\bvec`, `\pardx`, `\ddx`,
`\norm`, `\abs`, `\curl`, `\div`, `\grad`, `\vspan`, plus `\ket`, `\bra`,
`\braket`, `\ketbra`.

`\braket{ +z | +n }` works with the bar inside, the way you already write it —
including the three-part form `\braket{ \psi | \hat{A} | \psi }`.

---

## 4. Snippets

All **425** of your Latex Suite snippets are ported and live in
[`hsnips/`](hsnips/). They behave the same way: type `sq` in math and you get
`\sqrt[]{ }`, type `//` and you get a fraction, `@a` gives `\alpha`.

They expand **automatically**, with no Tab, exactly as in Obsidian, and only
fire where they should — math snippets don't trigger in prose.

### The three things that changed

**1. Selection-wrapping snippets work differently.** Latex Suite's `${VISUAL}`
snippets (`U` for underbrace, `C` for cancel, `S` for sqrt, and the bracket
wrappers) have no HyperSnips equivalent. They became VS Code *surround-with*
snippets instead:

> Select the expression → `Ctrl+Alt+S` → pick `underbrace` / `cancel` / `sqrt` / …

**2. `iden3` got rewritten by hand.** It was a JavaScript function snippet;
HyperSnips runs JS too, so it was re-implemented in
[`build/manual_snippets.hsnips`](build/manual_snippets.hsnips). `zeros3` came
along for free. Put any other custom snippets in that file — it is appended to
both snippet files on every re-sync and never overwritten.

**3. Everything else is generated.** Don't hand-edit `hsnips/latex.hsnips` or
`hsnips/markdown.hsnips`; they are rebuilt from Obsidian.

### Keeping snippets in sync with Obsidian

Add a snippet in Obsidian as usual, then run the task
**Re-sync snippets from Obsidian** (`Ctrl+Shift+P` → *Tasks: Run Task*), or:

```bash
python build/port_snippets.py
```

It reads Latex Suite's `data.json` directly, so Obsidian stays the place you
manage snippets.

---

## 5. Dark and light

Every PDF builds either way from the same source.

```bash
python build/build.py "notes/Junior/Big Quantum/Lectures/1 Spin angular momentum.md" --dark
python build/build.py "notes/Junior/Big Quantum/Lectures/1 Spin angular momentum.md" --light
```

In `.tex` files it is the class option: `\documentclass[dark]{hmcnote}` or
`[light]`.

- **dark** — `#1a1b26` page, `#c0caf5` text, your `#aa62d0` accent. Matches
  Obsidian on screen.
- **light** — white page, same palette but deepened so the accent colours don't
  wash out in print. Use this for anything you hand in.

---

## 6. Re-importing notes from Obsidian

`notes/` is a **copy**. Obsidian is still the live vault. To refresh:

```bash
python build/import_vault.py
```

It copies markdown and images, skips `.obsidian` and `.git`. Add `--no-pdfs`
to leave out the ~194 MB of reference PDFs.

---

## 7. What is where

```
vscode latex/
├── template.tex              <- copy this to start a LaTeX note
├── tex/
│   ├── hmcnote.cls           <- the document class: palette, headings, callouts
│   └── preamble.sty          <- your maths macros
├── hsnips/
│   ├── latex.hsnips          <- 425 snippets for .tex   (generated)
│   └── markdown.hsnips       <- 425 snippets for .md    (generated)
├── notes/                    <- your 559 notes + images, copied from the vault
├── build/
│   ├── port_snippets.py      <- Latex Suite  -> HyperSnips
│   ├── manual_snippets.hsnips<- hand-written snippets (edit this one)
│   ├── md2tex.py             <- Obsidian markdown -> LaTeX
│   ├── build.py              <- note -> PDF          (what the tasks call)
│   ├── import_vault.py       <- refresh notes/ from Obsidian
│   └── smoke_test.py         <- convert every note, report anything broken
├── out/                      <- PDFs and build files (git-ignored)
└── .vscode/                  <- settings, tasks, keybindings to copy
```

---

## 8. Known gaps

- **Inline concealment doesn't exist in VS Code.** See §2. Use the preview pane
  or hover.
- **21 Excalidraw drawings** (in `notes/special/FriendsNotes/Phys51/Attachments/`)
  are copied but can't be typeset — they're vector JSON, not prose. Install the
  Excalidraw plugin in Obsidian and export them to SVG if you want them in a PDF.
- **19 image references are missing**, across 9 notes, all in
  `notes/special/FriendsNotes/` — those images were never in your vault to begin
  with. They render as *[missing image: ...]* rather than failing the build.
- **Wikilinks** `[[Note]]` become italic text in the PDF. There is no sensible
  cross-document link in a standalone PDF.

---

## 9. If something breaks

**A note won't compile.** Get the generated LaTeX and read the error in context:

```bash
python build/md2tex.py "notes/path/to/Note.md" -o out/debug.tex --vault-root notes
```

**Check nothing regressed after editing the converter:**

```bash
python build/smoke_test.py --compile 10
```

Converts all 538 notes, reports crashes and suspicious output, then compiles a
random sample. Currently: 0 crashes, 10/10 compiled.

**Snippets stopped firing.** Check `hsnips.hsnipsPath` in
`.vscode/settings.json` still points at `hsnips/`, and that the HyperSnips
extension is enabled. Math snippets only fire inside `$...$`.
