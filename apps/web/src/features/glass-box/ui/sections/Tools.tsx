import { useTranslation } from 'react-i18next';

import { useFormat } from '@/shared/i18n';

import { isWrite, toolTone } from '../../model/records';
import { useRecord } from '../../model/scope';
import { Section } from './Section';

/** Tool calls in order: name, redacted arguments, status, result, and for writes the read-back verification. */
export function Tools() {
  const { t } = useTranslation();
  const format = useFormat();
  const { record } = useRecord();
  return record.tool_calls.map((tool) => {
    const args = Object.entries(tool.arguments);
    return (
      <Section
        key={tool.sequence}
        tone={toolTone(tool)}
        title={<span className="font-mono">{tool.tool}</span>}
        kind={isWrite(tool) ? t('glass.kinds.write') : t('glass.kinds.read')}
        meta={t('glass.ms', { value: format.number(tool.latency_ms) })}
      >
        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-caption">
          <dt>{t('glass.status')}</dt>
          <dd className="text-fg">
            {t(`glass.toolStatus.${tool.status}`)}
            {tool.attempts > 1 && ` (${t('glass.attempts', { count: tool.attempts })})`}
          </dd>
          {args.length > 0 && (
            <>
              <dt>{t('glass.arguments')}</dt>
              <dd className="font-mono break-all text-fg">
                {args.map(([name, value]) => `${name}=${String(value)}`).join(', ')}
              </dd>
            </>
          )}
          {tool.result_summary !== null && (
            <>
              <dt>{t('glass.resultSummary')}</dt>
              <dd className="font-mono break-all text-fg">{tool.result_summary}</dd>
            </>
          )}
          {tool.verification !== null && (
            <>
              <dt>{t('glass.verification')}</dt>
              <dd className="text-fg">
                <span className="font-semibold">
                  {tool.verification.verified ? t('glass.verified') : t('glass.notVerified')}
                </span>{' '}
                <span className="font-mono break-all">{tool.verification.check}</span>
                {tool.verification.evidence !== null && (
                  <span className="block font-mono break-all">
                    {t('glass.evidence')} {tool.verification.evidence}
                  </span>
                )}
                {tool.verification.mismatch_code !== null && (
                  <span className="block font-mono">{tool.verification.mismatch_code}</span>
                )}
              </dd>
            </>
          )}
        </dl>
      </Section>
    );
  });
}
