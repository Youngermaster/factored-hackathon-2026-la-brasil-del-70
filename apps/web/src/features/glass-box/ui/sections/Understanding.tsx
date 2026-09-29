import { useTranslation } from 'react-i18next';

import { useFormat } from '@/shared/i18n';

import { useRecord } from '../../model/scope';
import { Section } from './Section';

/** What the models understood: intent with confidence, language, retrieval, and language model calls. */
export function Understanding() {
  const { t } = useTranslation();
  const format = useFormat();
  const { record } = useRecord();
  const percent = (value: number) => `${format.number(Math.round(value * 100))} %`;
  return (
    <Section tone="understanding" title={t('glass.understanding')} kind={t('glass.kinds.model')}>
      <ul className="flex flex-col gap-1">
        {record.intent !== null && (
          <li>
            {t('glass.intentLabel')} <span className="font-mono">{record.intent.intent}</span>,{' '}
            {t('glass.confidence', { value: percent(record.intent.confidence) })}
            <span className="block font-mono text-caption">{record.intent.model}</span>
            {record.intent.below_threshold && (
              <span className="block text-caption">{t('glass.belowThreshold')}</span>
            )}
          </li>
        )}
        {record.language_detection !== null && (
          <li>
            {t('glass.languageLabel')}{' '}
            <span className="font-mono">
              {record.language_detection.language ?? t('glass.uncertain')}
            </span>
            , {t('glass.confidence', { value: percent(record.language_detection.confidence) })}
            <span className="block font-mono text-caption">
              {record.language_detection.detector}
            </span>
          </li>
        )}
        {record.retrieval !== null && (
          <li>
            {t(`glass.retrieval.${record.retrieval.decision}`)}{' '}
            <span className="font-mono text-caption">{record.retrieval.retriever}</span>
          </li>
        )}
        {record.llm_calls.map((call, index) => (
          <li key={`${call.prompt}-${String(index)}`}>
            <span className="font-mono text-caption">{call.prompt}</span>{' '}
            {t(`glass.llmStatus.${call.status}`)}
            {call.status !== 'fallback' && (
              <span className="font-mono text-caption"> {call.model_id}</span>
            )}
          </li>
        ))}
        {record.intent === null &&
          record.language_detection === null &&
          record.llm_calls.length === 0 && <li>{t('glass.noUnderstanding')}</li>}
      </ul>
    </Section>
  );
}
