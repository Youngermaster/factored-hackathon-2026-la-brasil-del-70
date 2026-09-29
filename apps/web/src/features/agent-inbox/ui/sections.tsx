import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { useFormat } from '@/shared/i18n';
import { Badge, Card, KeyValueList, StatusPill } from '@/shared/ui';

import { useHandoffView } from '../model/handoff-context';
import { useInboxLabels } from './labels';

function Section({
  id,
  title,
  children,
}: {
  readonly id: string;
  readonly title: string;
  readonly children: ReactNode;
}) {
  return (
    <Card.Root aria-labelledby={id}>
      <Card.Header title={<span id={id}>{title}</span>} />
      <Card.Body className="text-small">{children}</Card.Body>
    </Card.Root>
  );
}

function Empty({ children }: { readonly children: ReactNode }) {
  return <p className="text-fg-muted">{children}</p>;
}

/** Facts the system verified, each with the record that proves it (`table:id`). */
export function VerifiedFacts() {
  const { t } = useTranslation();
  const handoff = useHandoffView();
  return (
    <Section id="handoff-facts" title={t('inbox.detail.facts')}>
      {handoff.verified_facts.length === 0 ? (
        <Empty>{t('inbox.detail.none')}</Empty>
      ) : (
        <ul className="flex flex-col gap-3">
          {handoff.verified_facts.map((fact) => (
            <li key={`${fact.source}-${fact.fact}`} className="flex flex-col gap-0.5">
              <span className="text-fg">{fact.fact}</span>
              <span className="font-mono text-caption break-all text-fg-muted">{fact.source}</span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

/** Actions taken before the handoff, with their verification; only a read-back gets the verified style. */
export function ActionsTaken() {
  const { t } = useTranslation();
  const labels = useInboxLabels();
  const handoff = useHandoffView();
  return (
    <Section id="handoff-actions" title={t('inbox.detail.actions')}>
      {handoff.actions_taken.length === 0 ? (
        <Empty>{t('inbox.detail.noActions')}</Empty>
      ) : (
        <ul className="flex flex-col gap-3">
          {handoff.actions_taken.map((action) => (
            <li key={`${action.action}-${action.target}`} className="flex flex-col gap-1">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-fg">
                  {labels.code('action', action.action)}
                </span>
                <StatusPill
                  status={
                    action.verification === 'verified'
                      ? 'verified'
                      : action.status === 'failed'
                        ? 'failed'
                        : 'pending'
                  }
                />
              </span>
              <span className="text-fg-secondary">
                {labels.code('verification', action.verification)}
                {action.confirmed ? `, ${t('inbox.detail.confirmed')}` : ''}
              </span>
              <span className="font-mono text-caption break-all text-fg-muted">
                {action.target}
                {action.evidence === null ? '' : `, ${action.evidence}`}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

/** The clauses behind the handoff, as `clause_id@version`, with the excerpt in the handoff's language. */
export function PolicyBasis() {
  const { t } = useTranslation();
  const handoff = useHandoffView();
  const excerpts = new Map(handoff.policy_excerpts.map((item) => [item.clause, item.excerpt]));
  return (
    <Section id="handoff-policy" title={t('inbox.detail.policy')}>
      {handoff.policy_basis.length === 0 ? (
        <Empty>{t('inbox.detail.none')}</Empty>
      ) : (
        <ul className="flex flex-col gap-3">
          {handoff.policy_basis.map((clause) => (
            <li key={clause} className="flex flex-col gap-0.5">
              <span className="font-mono text-caption text-fg">{clause}</span>
              {excerpts.has(clause) && (
                <span className="line-clamp-4 whitespace-pre-line text-fg-secondary">
                  {excerpts.get(clause)}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

/** What the next person still has to find out. */
export function OpenQuestions() {
  const { t } = useTranslation();
  const handoff = useHandoffView();
  return (
    <Section id="handoff-questions" title={t('inbox.detail.questions')}>
      {handoff.open_questions.length === 0 ? (
        <Empty>{t('inbox.detail.noQuestions')}</Empty>
      ) : (
        <ul className="flex list-disc flex-col gap-1.5 pl-5 text-fg">
          {handoff.open_questions.map((question) => (
            <li key={question}>{question}</li>
          ))}
        </ul>
      )}
    </Section>
  );
}

/**
 * The credit review: the synthetic eligibility outcome and its reasons, and, separately, the internal risk
 * estimate with its interval. Agents see the estimate; customers never do. Neither is a lending decision.
 */
export function CreditReviewSection() {
  const { t } = useTranslation();
  const format = useFormat();
  const review = useHandoffView().credit_review;
  if (review === null) {
    return null;
  }
  const percent = (value: string) => `${format.number(Math.round(Number(value) * 1000) / 10)} %`;
  return (
    <Section id="handoff-credit" title={t('inbox.detail.credit')}>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-3 rounded-card border border-border-strong bg-decision-subtle p-4">
          <p className="flex items-center justify-between gap-2 font-semibold text-fg">
            {t('inbox.detail.eligibility')}
            <Badge>{t('parts.eligibility.synthetic')}</Badge>
          </p>
          <KeyValueList.Root>
            <KeyValueList.Item label={t('inbox.detail.product')}>
              <span className="font-mono">{review.product_code}</span>
            </KeyValueList.Item>
            <KeyValueList.Item label={t('inbox.detail.outcome')}>
              {review.eligibility_outcome === null
                ? t('inbox.detail.none')
                : t(`parts.eligibilityOutcomes.${review.eligibility_outcome}`)}
            </KeyValueList.Item>
            <KeyValueList.Item label={t('inbox.detail.reasons')}>
              <span className="font-mono text-caption break-all">
                {[...review.reason_codes, ...review.rule_ids].join(', ') || t('inbox.detail.none')}
              </span>
            </KeyValueList.Item>
            <KeyValueList.Item label={t('inbox.detail.reviewReasons')}>
              {review.review_reasons
                .map((reason) => t(`glass.credit.review.${reason}`))
                .join(', ') || t('inbox.detail.none')}
            </KeyValueList.Item>
            {review.missing_facts.length > 0 && (
              <KeyValueList.Item label={t('inbox.detail.missing')}>
                <span className="font-mono text-caption">{review.missing_facts.join(', ')}</span>
              </KeyValueList.Item>
            )}
            {review.application_ref !== null && (
              <KeyValueList.Item label={t('inbox.detail.application')}>
                <Link
                  className="font-mono underline underline-offset-4"
                  to={`/console/credit-applications/${review.application_ref.replace(/^credit_applications:/, '')}`}
                >
                  {review.application_ref}
                </Link>
              </KeyValueList.Item>
            )}
          </KeyValueList.Root>
        </div>
        <div className="flex flex-col gap-3 rounded-card border border-understanding bg-understanding-subtle p-4">
          <p className="font-semibold text-fg">{t('glass.credit.riskTitle')}</p>
          <p className="text-understanding-text">{t('glass.credit.riskLabel')}</p>
          {review.risk === null ? (
            <Empty>{t('inbox.detail.noEstimate')}</Empty>
          ) : (
            <KeyValueList.Root>
              <KeyValueList.Item label={t('glass.credit.band')}>
                {t(`glass.credit.bands.${review.risk.band}`)}
              </KeyValueList.Item>
              <KeyValueList.Item label={t('glass.credit.interval')} numeric>
                {percent(review.risk.interval_low)} {t('glass.credit.to')}{' '}
                {percent(review.risk.interval_high)}
              </KeyValueList.Item>
              <KeyValueList.Item label={t('glass.credit.model')}>
                <span className="font-mono text-caption break-all">{review.risk.model}</span>
              </KeyValueList.Item>
              <KeyValueList.Item label={t('glass.credit.label')}>
                <span className="font-mono text-caption break-all">
                  {review.risk.label_definition}
                </span>
              </KeyValueList.Item>
            </KeyValueList.Root>
          )}
          <p className="text-caption text-fg-muted">{t('inbox.detail.estimateNote')}</p>
        </div>
      </div>
    </Section>
  );
}

/** The card request a handoff carries: what the customer asked for, and for which card. */
export function CardRequestSection() {
  const { t } = useTranslation();
  const request = useHandoffView().card_request;
  if (request === null) {
    return null;
  }
  return (
    <Section id="handoff-card" title={t('inbox.detail.card')}>
      <KeyValueList.Root columns={2}>
        <KeyValueList.Item label={t('inbox.detail.cardAction')}>
          {t(`parts.cardActions.${request.action}`)}
        </KeyValueList.Item>
        <KeyValueList.Item label={t('inbox.detail.cardProduct')}>
          <span className="font-mono text-caption break-all">{request.product_ref}</span>
        </KeyValueList.Item>
      </KeyValueList.Root>
    </Section>
  );
}
