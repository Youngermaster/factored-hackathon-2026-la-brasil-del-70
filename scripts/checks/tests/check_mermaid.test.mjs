// Self-test for check_mermaid.mjs, run with `node --test scripts/checks/tests/`.
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { after, describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

import { extractMermaidBlocks } from '../check_mermaid.mjs';

const script = resolve(fileURLToPath(import.meta.url), '..', '..', 'check_mermaid.mjs');
const workDir = mkdtempSync(join(tmpdir(), 'check-mermaid-'));
after(() => rmSync(workDir, { recursive: true, force: true }));

function writeMarkdown(name, content) {
  const path = join(workDir, name);
  writeFileSync(path, content, 'utf8');
  return path;
}

const fence = '```';

describe('extractMermaidBlocks', () => {
  it('finds mermaid blocks with their fence line and ignores other code blocks', () => {
    const text = `# Title\n\n${fence}bash\necho hi\n${fence}\n\n${fence}mermaid\nflowchart LR\n  A --> B\n${fence}\n`;

    assert.deepEqual(extractMermaidBlocks(text), [{ line: 7, source: 'flowchart LR\n  A --> B', closed: true }]);
  });

  it('reports an unclosed block', () => {
    assert.equal(extractMermaidBlocks(`${fence}mermaid\nflowchart LR\n`)[0].closed, false);
  });
});

describe('check_mermaid.mjs', () => {
  it('passes valid flowchart, sequence, state, and class diagrams', () => {
    const file = writeMarkdown(
      'valid.md',
      [
        `${fence}mermaid\nflowchart TD\n  api --> domain\n${fence}`,
        `${fence}mermaid\nsequenceDiagram\n  Customer->>API: dispute\n${fence}`,
        `${fence}mermaid\nstateDiagram-v2\n  [*] --> Open\n  Open --> Closed\n${fence}`,
        `${fence}mermaid\nclassDiagram\n  class Money {\n    +Decimal amount\n  }\n${fence}`,
      ].join('\n\n'),
    );

    const output = execFileSync(process.execPath, [script, file], { encoding: 'utf8' });

    assert.match(output, /4 mermaid block\(s\) in 1 file\(s\) parsed/);
  });

  it('fails an invalid diagram and names the file and line', () => {
    const file = writeMarkdown('invalid.md', `# Broken\n\n${fence}mermaid\nflowchart LR\n  A -->\n${fence}\n`);

    const result = spawnSync(process.execPath, [script, file], { encoding: 'utf8' });

    assert.equal(result.status, 1);
    assert.match(result.stdout, /invalid\.md:3: /);
    assert.match(result.stderr, /1 of 1 mermaid block\(s\) failed to parse/);
  });

  it('fails a block with no diagram type', () => {
    const file = writeMarkdown('unknown.md', `${fence}mermaid\nnot a diagram\n${fence}\n`);

    const result = spawnSync(process.execPath, [script, file], { encoding: 'utf8' });

    assert.equal(result.status, 1);
    assert.match(result.stdout, /No diagram type detected/);
  });
});
