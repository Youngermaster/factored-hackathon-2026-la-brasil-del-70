import { useTranslation } from 'react-i18next';

import { useRecord } from '../../model/scope';
import { Section } from './Section';

/** The clauses behind this turn, as `clause_id@version`, with the excerpt the customer saw when it was cited. */
export function Clauses() {
  const { t } = useTranslation();
  const { record, excerpts } = useRecord();
  if (record.clause_refs.length === 0) {
    return null;
  }
  const cited = record.clause_refs.filter((clause) => excerpts.has(clause));
  const other = record.clause_refs.filter((clause) => !excerpts.has(clause));
  return (
    <Section tone="decision" title={t('glass.clauses')} kind={t('glass.kinds.policy')}>
      {cited.length > 0 && (
        <ul className="flex flex-col gap-2">
          {cited.map((clause) => (
            <li key={clause} className="flex flex-col gap-0.5">
              <span className="font-mono text-caption text-fg">{clause}</span>
              <span className="line-clamp-3">{excerpts.get(clause)}</span>
            </li>
          ))}
        </ul>
      )}
      {other.length > 0 && (
        <p className="mt-2">
          {t('glass.otherClauses')}{' '}
          <span className="font-mono text-caption break-words">{other.join(', ')}</span>
        </p>
      )}
    </Section>
  );
}
