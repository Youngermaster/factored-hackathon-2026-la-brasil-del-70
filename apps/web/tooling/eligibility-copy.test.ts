// @vitest-environment node
// The chat renders eligibility sentences from the locale files' `eligibility` tree. The policy pack owns that
// wording (policies/messages/eligibility.<language>.yaml, reviewed for approval wording); this test keeps the web
// copy identical to it, word for word, so the two never drift.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { resources } from '../src/shared/i18n/resources';

type Tree = Record<string, Record<string, string>>;

const policyDir = fileURLToPath(new URL('../../../policies/messages/', import.meta.url));

/**
 * Reads the pack's two-level message files: `section:` lines, then `  key: "text"` lines, comments ignored. Any
 * other shape fails the test, so a format change is noticed rather than half-read.
 */
export function parseMessages(source: string): Tree {
  const tree: Tree = {};
  let section: Record<string, string> | null = null;
  for (const line of source.split('\n')) {
    if (line.trim() === '' || line.startsWith('#')) {
      continue;
    }
    const heading = /^([a-z_]+):$/.exec(line);
    if (heading?.[1] !== undefined) {
      section = {};
      tree[heading[1]] = section;
      continue;
    }
    const entry = /^ {2}([a-z_]+): (".*")$/.exec(line);
    if (entry?.[1] === undefined || entry[2] === undefined || section === null) {
      throw new Error(`unexpected line in the message file: ${line}`);
    }
    section[entry[1]] = JSON.parse(entry[2]) as string;
  }
  return tree;
}

describe('eligibility copy', () => {
  it.each(['es', 'pt', 'en'] as const)('%s matches the policy pack word for word', (language) => {
    const pack = parseMessages(readFileSync(`${policyDir}eligibility.${language}.yaml`, 'utf8'));
    expect(resources[language].translation.eligibility).toEqual(pack);
  });

  it('refuses a line it does not understand (negative control)', () => {
    expect(() => parseMessages('outcome:\n  review_required: unquoted text\n')).toThrow();
  });
});
