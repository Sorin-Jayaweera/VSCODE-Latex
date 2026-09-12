// Obsidian embeds for VS Code's built-in markdown preview.
//
// The preview is markdown-it underneath, and VS Code lets an extension add
// markdown-it plugins. This one teaches it two Obsidian constructs:
//
//   ![[Pasted image 2026....png|300]]   -> <img>, resolved the way Obsidian does
//   [[Some note|alias]]                 -> a link to that note
//
// Obsidian resolves an embed by filename anywhere in the vault, so a note can
// embed an image that lives in a different folder. We keep an index of every
// image and note in the workspace and look there when the image is not next to
// the note or in its images/ folder.

const vscode = require('vscode');
const path = require('path');
const fs = require('fs');

const IMAGE_RE = /\.(png|jpe?g|gif|svg|webp|bmp)$/i;
const NEAR_DIRS = ['', 'images', 'attachments', 'Attachments', 'assets'];

/** lower-cased basename -> [absolute paths] */
let fileIndex = new Map();

async function rebuildIndex() {
  const found = await vscode.workspace.findFiles(
    '**/*.{png,jpg,jpeg,gif,svg,webp,bmp,PNG,JPG,JPEG,GIF,SVG,WEBP,md}',
    '**/{node_modules,.git,.build}/**'
  );
  const next = new Map();
  for (const uri of found) {
    const key = path.basename(uri.fsPath).toLowerCase();
    if (!next.has(key)) next.set(key, []);
    next.get(key).push(uri.fsPath);
  }
  fileIndex = next;
}

/** Of several same-named files, prefer the one closest to the note. */
function closest(candidates, docDir) {
  if (!docDir || candidates.length === 1) return candidates[0];
  let best = candidates[0];
  let bestScore = -1;
  for (const c of candidates) {
    const a = path.dirname(c).split(path.sep);
    const b = docDir.split(path.sep);
    let shared = 0;
    while (shared < a.length && shared < b.length && a[shared].toLowerCase() === b[shared].toLowerCase()) shared++;
    if (shared > bestScore) {
      bestScore = shared;
      best = c;
    }
  }
  return best;
}

function resolveTarget(name, docPath, wantMarkdown) {
  const docDir = docPath ? path.dirname(docPath) : null;
  let fileName = name;
  if (wantMarkdown && !/\.md$/i.test(fileName)) fileName += '.md';

  if (docDir) {
    for (const sub of NEAR_DIRS) {
      const candidate = path.join(docDir, sub, fileName);
      if (fs.existsSync(candidate)) return candidate;
    }
  }
  const hits = fileIndex.get(path.basename(fileName).toLowerCase());
  return hits && hits.length ? closest(hits, docDir) : null;
}

function relativeHref(md, target, docPath) {
  const from = docPath ? path.dirname(docPath) : process.cwd();
  const rel = path.relative(from, target).split(path.sep).join('/');
  return md.normalizeLink(encodeURI(rel));
}

function obsidianPlugin(md) {
  md.inline.ruler.before('link', 'obsidian_wikilink', (state, silent) => {
    const src = state.src;
    const pos = state.pos;
    const isEmbed = src.startsWith('![[', pos);
    if (!isEmbed && !src.startsWith('[[', pos)) return false;

    const innerStart = pos + (isEmbed ? 3 : 2);
    const close = src.indexOf(']]', innerStart);
    if (close < 0) return false;
    const inner = src.slice(innerStart, close);
    if (!inner || inner.includes('\n')) return false;

    if (!silent) {
      const bar = inner.indexOf('|');
      const target = (bar >= 0 ? inner.slice(0, bar) : inner).trim();
      const option = bar >= 0 ? inner.slice(bar + 1).trim() : '';
      const doc = state.env && state.env.currentDocument;
      const docPath = doc && doc.fsPath ? doc.fsPath : null;

      if (isEmbed && IMAGE_RE.test(target)) {
        const resolved = resolveTarget(target, docPath, false);
        const token = state.push('image', 'img', 0);
        token.attrs = [
          ['src', resolved ? relativeHref(md, resolved, docPath) : md.normalizeLink(target)],
          ['alt', ''],
        ];
        // Obsidian sizes: |300 or |300x200
        const size = /^(\d+)(?:x(\d+))?$/.exec(option);
        if (size) {
          token.attrs.push(['width', size[1]]);
          if (size[2]) token.attrs.push(['height', size[2]]);
        }
        token.children = [];
        token.content = '';
      } else if (isEmbed) {
        // Note transclusion: we can't inline another note, so say what it is.
        const open = state.push('em_open', 'em', 1);
        open.markup = '*';
        const text = state.push('text', '', 0);
        text.content = 'embed: ' + target;
        state.push('em_close', 'em', -1);
      } else {
        const heading = target.indexOf('#');
        const noteName = heading >= 0 ? target.slice(0, heading) : target;
        const resolved = noteName ? resolveTarget(noteName, docPath, true) : null;
        const open = state.push('link_open', 'a', 1);
        open.attrs = [['href', resolved ? relativeHref(md, resolved, docPath) : '#']];
        const text = state.push('text', '', 0);
        text.content = option || target;
        state.push('link_close', 'a', -1);
      }
    }

    state.pos = close + 2;
    return true;
  });
  return md;
}

function activate(context) {
  rebuildIndex();
  const watcher = vscode.workspace.createFileSystemWatcher(
    '**/*.{png,jpg,jpeg,gif,svg,webp,bmp,md}'
  );
  watcher.onDidCreate(rebuildIndex);
  watcher.onDidDelete(rebuildIndex);
  context.subscriptions.push(watcher);

  return {
    extendMarkdownIt(md) {
      return md.use(obsidianPlugin);
    },
  };
}

function deactivate() {}

module.exports = { activate, deactivate, obsidianPlugin };
