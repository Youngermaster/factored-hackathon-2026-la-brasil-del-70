#!/usr/bin/env node
// Validate every fenced mermaid block in the repository's Markdown by parsing it with the mermaid package.
//
// Usage:
//   node scripts/checks/check_mermaid.mjs            every committed or new Markdown file (git ls-files)
//   node scripts/checks/check_mermaid.mjs FILE ...   specific files
//
// mermaid and jsdom are resolved from apps/web, where they are devDependencies. mermaid's parser needs a DOM
// for some diagram types (DOMPurify), so a jsdom window is installed on globalThis before mermaid is
// imported; no headless browser is involved. Exit status: 1 when any block fails to parse, 0 otherwise.

import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const EXCLUDED_PREFIXES = ['kit/', '.claude/skills/'];
const FENCE_OPEN = /^\s*(```|~~~)\s*mermaid\s*$/;

function markdownFiles() {
  const output = execFileSync(
    'git',
    ['ls-files', '--cached', '--others', '--exclude-standard', '-z', '--', '*.md'],
    { cwd: repositoryRoot, encoding: 'utf8' },
  );
  return output
    .split('\0')
    .filter((path) => path && !path.includes('node_modules/'))
    .filter((path) => !EXCLUDED_PREFIXES.some((prefix) => path.startsWith(prefix)))
    .map((path) => join(repositoryRoot, path));
}

/** Return every mermaid block in the text as { line, source }, where line is the fence line (1-based). */
export function extractMermaidBlocks(text) {
  const lines = text.split(/\r?\n/);
  const blocks = [];
  for (let index = 0; index < lines.length; index += 1) {
    const open = FENCE_OPEN.exec(lines[index]);
    if (!open) continue;
    const fence = open[1];
    const body = [];
    let cursor = index + 1;
    while (cursor < lines.length && lines[cursor].trim() !== fence) {
      body.push(lines[cursor]);
      cursor += 1;
    }
    blocks.push({ line: index + 1, source: body.join('\n'), closed: cursor < lines.length });
    index = cursor;
  }
  return blocks;
}

async function loadMermaid() {
  const webRequire = createRequire(join(repositoryRoot, 'apps', 'web', 'package.json'));
  const { JSDOM } = await import(pathToFileURL(webRequire.resolve('jsdom')).href);
  const { window } = new JSDOM('');
  globalThis.window = window;
  globalThis.document = window.document;
  const { default: mermaid } = await import(pathToFileURL(webRequire.resolve('mermaid')).href);
  mermaid.initialize({ startOnLoad: false, securityLevel: 'strict' });
  return mermaid;
}

async function main(argv) {
  const files = argv.length > 0 ? argv.map((path) => resolve(path)) : markdownFiles();
  const mermaid = await loadMermaid();
  let blocks = 0;
  let failures = 0;
  for (const file of files) {
    const relative = file.startsWith(repositoryRoot) ? file.slice(repositoryRoot.length + 1) : file;
    for (const block of extractMermaidBlocks(readFileSync(file, 'utf8'))) {
      blocks += 1;
      if (!block.closed) {
        console.log(`${relative}:${block.line}: mermaid block is not closed`);
        failures += 1;
        continue;
      }
      try {
        await mermaid.parse(block.source);
      } catch (error) {
        const message = String(error?.message ?? error).split('\n').slice(0, 3).join(' ');
        console.log(`${relative}:${block.line}: ${message}`);
        failures += 1;
      }
    }
  }
  if (failures > 0) {
    console.error(`check-mermaid: ${failures} of ${blocks} mermaid block(s) failed to parse`);
    return 1;
  }
  console.log(`check-mermaid: ${blocks} mermaid block(s) in ${files.length} file(s) parsed`);
  return 0;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}
