import type { Schema } from '@/shared/api';

type Citation = Schema<'Citation'>;

/**
 * The answer without the policy text it quotes. The engine appends each cited clause's excerpt to the reply; the
 * chat shows those under "cited policies" instead, next to their `clause_id@version`, so the answer reads first.
 * Only an exact, verbatim excerpt moves; every other word stays where it was.
 */
export function withoutCitedParagraphs(text: string, citations: readonly Citation[]): string {
  let body = text;
  for (const { excerpt } of citations) {
    if (excerpt.trim() !== '' && body.includes(excerpt)) {
      body = body.replace(excerpt, '');
    }
  }
  return body === text ? text : body.replace(/\n{3,}/g, '\n\n').trim();
}
