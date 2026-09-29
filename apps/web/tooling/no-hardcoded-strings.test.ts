// @vitest-environment node
// Fails on user-facing text written directly in components: every string a person reads comes from the locale
// files (CLAUDE.md section 6). Tests are exempt; they assert on rendered copy.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

import ts from 'typescript';
import { describe, expect, it } from 'vitest';

const srcRoot = fileURLToPath(new URL('../src', import.meta.url));

/** Attributes that screen readers or sighted users read. */
const USER_FACING_ATTRIBUTES = new Set([
  'aria-label',
  'title',
  'placeholder',
  'alt',
  'label',
  'aria-description',
]);

const LETTER = /\p{L}/u;

function componentFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      return componentFiles(path);
    }
    return path.endsWith('.tsx') && !path.endsWith('.test.tsx') ? [path] : [];
  });
}

export interface Finding {
  readonly file: string;
  readonly line: number;
  readonly text: string;
}

export function findHardcodedStrings(file: string, source: string): Finding[] {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const findings: Finding[] = [];
  const report = (node: ts.Node, text: string) => {
    findings.push({
      file,
      line: sf.getLineAndCharacterOfPosition(node.getStart()).line + 1,
      text: text.trim(),
    });
  };
  const visit = (node: ts.Node) => {
    if (ts.isJsxText(node) && LETTER.test(node.getText())) {
      report(node, node.getText());
    }
    if (ts.isJsxAttribute(node) && USER_FACING_ATTRIBUTES.has(node.name.getText())) {
      const value = node.initializer;
      if (value !== undefined && ts.isStringLiteral(value) && LETTER.test(value.text)) {
        report(node, value.text);
      }
      if (
        value !== undefined &&
        ts.isJsxExpression(value) &&
        value.expression !== undefined &&
        (ts.isStringLiteral(value.expression) ||
          ts.isNoSubstitutionTemplateLiteral(value.expression)) &&
        LETTER.test(value.expression.text)
      ) {
        report(node, value.expression.text);
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
  return findings;
}

describe('hard-coded user-facing strings', () => {
  it('finds none in src/**/*.tsx', () => {
    const findings = componentFiles(srcRoot).flatMap((file) =>
      findHardcodedStrings(relative(srcRoot, file), readFileSync(file, 'utf8')),
    );
    expect(findings).toEqual([]);
  });

  it('catches JSX text and literal labels (negative control)', () => {
    const findings = findHardcodedStrings(
      'fixture.tsx',
      [
        'export const A = () => <p>Saldo disponible</p>;',
        'export const B = () => <button aria-label="Cerrar" />;',
        "export const C = () => <input placeholder={'Buscar'} />;",
        'export const D = () => <p>{t("ok")} : 12</p>;',
        'export const E = () => <img alt="" />;',
      ].join('\n'),
    );
    expect(findings.map((finding) => finding.text)).toEqual([
      'Saldo disponible',
      'Cerrar',
      'Buscar',
    ]);
  });
});
