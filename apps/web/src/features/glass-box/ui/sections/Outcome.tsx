import { useTranslation } from 'react-i18next';

import { useRecord } from '../../model/scope';
import { Section } from './Section';

/** How the turn ended: the handoff it opened, the cases it touched, and the reply's grounding. */
export function Outcome() {
  const { t } = useTranslation();
  const { record } = useRecord();
  const escalated = record.handoff_ref !== null;
  return (
    <Section
      tone={escalated || record.grounding.violations.length > 0 ? 'risk' : 'neutral'}
      title={t(`glass.outcomes.${record.outcome}`)}
      kind={t('glass.kinds.outcome')}
    >
      <ul className="flex flex-col gap-0.5">
        {escalated && (
          <li>
            {t('glass.handoff')} <span className="font-mono break-all">{record.handoff_ref}</span>
          </li>
        )}
        {record.case_refs.map((ref) => (
          <li key={ref}>
            {t('glass.case')} <span className="font-mono break-all">{ref}</span>
          </li>
        ))}
        <li>
          {record.grounding.llm_phrasing_used ? t('glass.phrased') : t('glass.template')}{' '}
          {record.grounding.template_id !== null && (
            <span className="font-mono">{record.grounding.template_id}</span>
          )}
        </li>
        <li>
          {record.grounding.violations.length === 0
            ? t('glass.grounded')
            : t('glass.violations', { list: record.grounding.violations.join(', ') })}
        </li>
      </ul>
    </Section>
  );
}
