const vscode = require("vscode");
const fs = require("fs");
const path = require("path");

let snippets = [];
let inserting = false;

const MATH_ENVS = new Set([
  "equation", "equation*", "align", "align*", "gather", "gather*",
  "multline", "multline*", "flalign", "flalign*", "alignat", "alignat*",
  "eqnarray", "eqnarray*", "math", "displaymath",
]);
const CODE_ENVS = new Set(["verbatim", "verbatim*", "Verbatim", "lstlisting", "minted", "comment"]);
const TEXT_GROUP = /^\\(?:text|textrm|textit|textbf|textsf|texttt|mbox|intertext)\s*\{/;

function loadSnippets(context) {
  const file = path.join(context.extensionPath, "snippets.generated.json");
  const payload = JSON.parse(fs.readFileSync(file, "utf8"));
  snippets = payload.snippets || [];
  vscode.window.setStatusBarMessage(`Latex Suite Auto loaded ${snippets.length} snippets`, 2500);
}

function linePrefix(document, position) {
  return document.getText(new vscode.Range(new vscode.Position(position.line, 0), position));
}

function documentPrefix(document, position) {
  return document.getText(new vscode.Range(new vscode.Position(0, 0), position));
}

function scanContext(text, languageId) {
  const isTex = languageId === "latex" || languageId === "tex" || languageId === "latex-expl3";
  let inline = false;
  let display = false;
  let envDepth = 0;
  let codeEnv = 0;
  let fence = false;
  let inlineCode = false;
  let braces = [];
  let textDepth = 0;
  const lines = text.split("\n");

  for (let li = 0; li < lines.length; li++) {
    const line = lines[li];
    const last = li === lines.length - 1;

    if (!isTex) {
      if (/^\s*(```|~~~)/.test(line)) {
        fence = !fence;
        continue;
      }
      if (fence) continue;
      if (!display && line.trim() === "") inline = false;
    }

    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (!isTex && inlineCode) {
        if (c === "`") inlineCode = false;
        continue;
      }
      if (c === "\\") {
        const rest = line.slice(i);
        let m;
        if (isTex && (m = /^\\begin\{([^}]*)\}/.exec(rest))) {
          if (CODE_ENVS.has(m[1])) codeEnv++;
          else if (!codeEnv && MATH_ENVS.has(m[1])) envDepth++;
          i += m[0].length - 1;
          continue;
        }
        if (isTex && (m = /^\\end\{([^}]*)\}/.exec(rest))) {
          if (CODE_ENVS.has(m[1])) codeEnv = Math.max(0, codeEnv - 1);
          else if (!codeEnv && MATH_ENVS.has(m[1])) envDepth = Math.max(0, envDepth - 1);
          i += m[0].length - 1;
          continue;
        }
        if (isTex && codeEnv) {
          i++;
          continue;
        }
        if (isTex && (rest.startsWith("\\(") || rest.startsWith("\\["))) {
          display = true;
          i++;
          continue;
        }
        if (isTex && (rest.startsWith("\\)") || rest.startsWith("\\]"))) {
          display = false;
          i++;
          continue;
        }
        if ((m = TEXT_GROUP.exec(rest)) && (inline || display || envDepth)) {
          braces.push(true);
          textDepth++;
          i += m[0].length - 1;
          continue;
        }
        i++;
        continue;
      }
      if (isTex && codeEnv) continue;
      if (isTex && c === "%") break;
      if (!isTex && c === "`") {
        inlineCode = true;
        continue;
      }
      if (c === "{") {
        braces.push(false);
        continue;
      }
      if (c === "}") {
        if (braces.pop()) textDepth--;
        continue;
      }
      if (c === "$") {
        if (line[i + 1] === "$") {
          display = !display;
          inline = false;
          i++;
        } else if (!display) {
          inline = !inline;
        }
        if (!inline && !display && !envDepth) {
          braces = [];
          textDepth = 0;
        }
      }
    }
    if (!isTex && inlineCode && !last) inlineCode = false;
  }

  const code = isTex ? codeEnv > 0 : (fence || inlineCode);
  const math = (inline || display || envDepth > 0) && textDepth === 0 && !code;
  return { math, code };
}

function snippetEscapeLiteral(text) {
  return String(text).replace(/[\\$}]/g, (c) => "\\" + c);
}

function replacementToSnippet(replacement, match) {
  let out = "";
  for (let i = 0; i < replacement.length; i++) {
    if (replacement.startsWith("[[", i)) {
      const m = /^\[\[(\d+)\]\]/.exec(replacement.slice(i));
      if (m) {
        out += snippetEscapeLiteral(match?.[Number(m[1]) + 1] || "");
        i += m[0].length - 1;
        continue;
      }
    }
    if (replacement[i] === "$") {
      const rest = replacement.slice(i);
      let m = /^\$(\d+)/.exec(rest);
      if (m) {
        out += "$" + (Number(m[1]) + 1);
        i += m[0].length - 1;
        continue;
      }
      m = /^\$\{(\d+)(?::((?:[^{}]|\{[^{}]*\})*))?\}/.exec(rest);
      if (m) {
        const n = Number(m[1]) + 1;
        out += m[2] == null ? "${" + n + "}" : "${" + n + ":" + snippetEscapeLiteral(m[2]) + "}";
        i += m[0].length - 1;
        continue;
      }
    }
    out += snippetEscapeLiteral(replacement[i]);
  }
  return out;
}

function dynamicSnippet(snippet, match) {
  const n = Math.max(1, Math.min(30, Number(match?.[1] || 0)));
  if (snippet.dynamic === "identity") {
    const rows = [];
    for (let r = 0; r < n; r++) {
      const row = [];
      for (let c = 0; c < n; c++) row.push(r === c ? "1" : "0");
      rows.push(row.join(" & "));
    }
    return snippetEscapeLiteral("\\begin{pmatrix}\n" + rows.join(" \\\\\n") + "\n\\end{pmatrix}");
  }
  if (snippet.dynamic === "zeros") {
    const row = Array(n).fill("0").join(" & ");
    return snippetEscapeLiteral("\\begin{pmatrix}\n" + Array(n).fill(row).join(" \\\\\n") + "\n\\end{pmatrix}");
  }
  return "";
}

function contextAllowed(snippet, state) {
  if (snippet.context === "math") return state.math;
  if (snippet.context === "text") return !state.math && !state.code;
  if (snippet.context === "code") return state.code;
  return true;
}

function findMatch(document, position, snippet) {
  const prefix = linePrefix(document, position);
  if (snippet.regex) {
    const flags = (snippet.regexFlags || "").replace(/[gy]/g, "");
    const re = new RegExp(snippet.trigger + "$", flags.includes("m") ? flags : flags + "m");
    const match = re.exec(prefix);
    if (!match) return null;
    return {
      range: new vscode.Range(position.translate(0, -match[0].length), position),
      match,
    };
  }

  const trigger = snippet.trigger;
  const tokenMatch = /\S*$/.exec(prefix);
  const token = tokenMatch ? tokenMatch[0] : "";
  const opts = snippet.options || "";
  if (opts.includes("w")) {
    if (token !== trigger) return null;
  } else if (!token.endsWith(trigger)) {
    return null;
  }
  return {
    range: new vscode.Range(position.translate(0, -trigger.length), position),
    match: null,
  };
}

async function maybeExpand(event) {
  if (inserting) return;
  if (!vscode.workspace.getConfiguration("latexSuiteAuto").get("enabled", true)) return;
  if (!event.contentChanges.length || event.contentChanges[0].text.length !== 1) return;

  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document !== event.document) return;

  const change = event.contentChanges[0];
  const position = change.range.start.translate(0, change.text.length);
  const languageId = event.document.languageId;
  const relevant = new Set(["markdown", "mdx", "quarto", "latex", "tex", "latex-expl3", "plaintext"]);
  if (!relevant.has(languageId)) return;

  const state = scanContext(documentPrefix(event.document, position), languageId);
  for (const snippet of snippets) {
    if (!snippet.options.includes("A")) continue;
    if (!contextAllowed(snippet, state)) continue;
    const found = findMatch(event.document, position, snippet);
    if (!found) continue;
    const body = snippet.dynamic
      ? dynamicSnippet(snippet, found.match)
      : replacementToSnippet(snippet.replacement, found.match);
    inserting = true;
    try {
      await editor.insertSnippet(new vscode.SnippetString(body), found.range, {
        undoStopBefore: false,
        undoStopAfter: false,
      });
    } finally {
      inserting = false;
    }
    return;
  }
}

function activate(context) {
  loadSnippets(context);
  context.subscriptions.push(vscode.workspace.onDidChangeTextDocument(maybeExpand));
  context.subscriptions.push(vscode.commands.registerCommand("latexSuiteAuto.reload", () => loadSnippets(context)));
}

function deactivate() {}

module.exports = { activate, deactivate };
