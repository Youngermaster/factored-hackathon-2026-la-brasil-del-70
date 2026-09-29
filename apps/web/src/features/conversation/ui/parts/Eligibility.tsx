import { useTranslation } from 'react-i18next';

import { Badge, Button, InfoIcon } from '@/shared/ui';

import { useConversation } from '../../model/context';
import { useMessage } from '../../model/message-context';
import { PartCard } from './PartCard';
import { useEligibilityCopy } from './eligibility-copy';

/**
 * The customer-facing eligibility view. It states the outcome in plain words, each reason with its rule, the
 * uncertainty, the review path as a button that asks for a person, and the disclaimer. It never uses the verified
 * style, a check icon, or approval wording, and it never shows a score, a probability, or a band.
 */
export function Eligibility() {
  const { t } = useTranslation();
  const copy = useEligibilityCopy();
  const { message, interactive } = useMessage();
  const { reply } = useConversation();
  const view = message.eligibility;
  if (view === null || view === undefined) {
    return null;
  }
  const excerpt = (clause: string) =>
    message.citations.find((citation) => citation.clause === clause)?.excerpt;
  return (
    <PartCard
      title={t('parts.eligibility.title')}
      meta={<Badge>{t('parts.eligibility.synthetic')}</Badge>}
    >
      <p data-outcome={view.outcome} className="text-body font-semibold text-fg">
        {copy.outcome(view.outcome)}
      </p>
      {view.reasons.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-small text-fg-muted">{copy.heading('reasons')}</p>
          <ul className="flex flex-col gap-2">
            {view.reasons.map((reason) => (
              <li
                key={`${reason.reason_code}-${reason.clause}`}
                className="flex flex-col gap-0.5 border-l-2 border-border-strong pl-3"
              >
                <span className="text-small text-fg">{copy.reason(reason.reason_code)}</span>
                <span className="text-caption text-fg-muted">
                  {t('parts.eligibility.rule')} <span className="font-mono">{reason.clause}</span>
                  {excerpt(reason.clause) !== undefined && (
                    <span className="sr-only">: {excerpt(reason.clause)}</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {view.missing_facts.length > 0 && (
        <div className="flex flex-col gap-1">
          <p className="text-small text-fg-muted">{copy.heading('missing')}</p>
          <ul className="list-disc pl-5 text-small text-fg">
            {view.missing_facts.map((fact) => (
              <li key={fact}>{copy.missingFact(fact)}</li>
            ))}
          </ul>
        </div>
      )}
      <p className="flex items-start gap-2 text-small text-fg-secondary">
        <InfoIcon aria-hidden="true" size={18} className="mt-0.5 shrink-0" />
        {copy.uncertainty(view.uncertainty)}
      </p>
      <div className="flex flex-col gap-2 border-t border-border pt-3">
        <p className="text-small text-fg">{copy.reviewPath(view.review_path)}</p>
        <div>
          <Button
            variant="secondary"
            disabled={!interactive}
            onClick={() => {
              reply({ kind: 'review' });
            }}
          >
            {t(`parts.eligibility.reviewButton.${view.review_path}`)}
          </Button>
        </div>
      </div>
      <p className="text-caption text-fg-muted">
        {copy.heading('synthetic_notice')} {t('parts.disclaimer')}
      </p>
    </PartCard>
  );
}
