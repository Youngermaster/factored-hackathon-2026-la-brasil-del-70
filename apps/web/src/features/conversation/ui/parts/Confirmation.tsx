import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { useFormat } from '@/shared/i18n';
import { Button, KeyValueList } from '@/shared/ui';

import type { Schema } from '@/shared/api';

import type { AssistantMessage } from '../../api/conversation';
import { useConversation } from '../../model/context';
import { isPurpose } from '../../model/labels';
import { useMessage } from '../../model/message-context';
import { Amount } from './Amount';
import { Masked } from './Masked';
import { PartCard } from './PartCard';

/** What the customer confirms before a write, with the planned actions and Confirm and Cancel. */
export function Confirmation() {
  const { t } = useTranslation();
  const { message } = useMessage();
  const body = confirmationBody(message);
  if (body === null) {
    return null;
  }
  return (
    <PartCard title={t(body.title)}>
      {body.details}
      <div className="flex flex-col gap-1">
        <p className="text-small text-fg-muted">{t('parts.confirm.planned')}</p>
        <ul className="list-disc pl-5 text-small text-fg">
          {body.planned.map((action) => (
            <li key={action}>{t(`parts.actionKinds.${action}`)}</li>
          ))}
        </ul>
      </div>
      {body.note}
      <ConfirmButtons destructive={body.destructive} />
    </PartCard>
  );
}

function ConfirmButtons({ destructive }: { readonly destructive: boolean }) {
  const { t } = useTranslation();
  const { interactive } = useMessage();
  const { reply } = useConversation();
  return (
    <div className="flex flex-wrap gap-3">
      <Button
        variant={destructive ? 'danger' : 'primary'}
        disabled={!interactive}
        onClick={() => {
          reply({ kind: 'confirm' });
        }}
      >
        {t('parts.confirm.confirm')}
      </Button>
      <Button
        variant="secondary"
        disabled={!interactive}
        onClick={() => {
          reply({ kind: 'cancel' });
        }}
      >
        {t('parts.confirm.cancel')}
      </Button>
    </div>
  );
}

type TitleKey =
  'parts.confirm.disputeTitle' | 'parts.confirm.cardTitle' | 'parts.confirm.creditTitle';

interface Body {
  readonly title: TitleKey;
  readonly details: ReactNode;
  readonly planned: readonly Schema<'ActionKind'>[];
  readonly note: ReactNode;
  readonly destructive: boolean;
}

function confirmationBody(message: AssistantMessage): Body | null {
  if (message.confirmation) {
    return {
      title: 'parts.confirm.disputeTitle',
      details: <DisputeDetails card={message.confirmation} />,
      planned: message.confirmation.planned_actions,
      note: null,
      destructive: false,
    };
  }
  if (message.card_action_confirmation) {
    return {
      title: 'parts.confirm.cardTitle',
      details: <CardDetails card={message.card_action_confirmation} />,
      planned: message.card_action_confirmation.planned_actions,
      note: null,
      destructive: message.card_action_confirmation.action === 'block',
    };
  }
  if (message.credit_intake_confirmation) {
    return {
      title: 'parts.confirm.creditTitle',
      details: <CreditDetails card={message.credit_intake_confirmation} />,
      planned: message.credit_intake_confirmation.planned_actions,
      note: <CreditNote />,
      destructive: false,
    };
  }
  return null;
}

function DisputeDetails({
  card,
}: {
  readonly card: NonNullable<AssistantMessage['confirmation']>;
}) {
  const { t } = useTranslation();
  const format = useFormat();
  return (
    <KeyValueList.Root columns={2}>
      <KeyValueList.Item label={t('parts.confirm.amount')} numeric>
        <Amount value={card.amount} />
      </KeyValueList.Item>
      <KeyValueList.Item label={t('parts.confirm.date')}>
        <time dateTime={card.occurred_on}>{format.day(card.occurred_on)}</time>
      </KeyValueList.Item>
      {card.merchant_display !== null && (
        <KeyValueList.Item label={t('parts.confirm.merchant')}>
          {card.merchant_display}
        </KeyValueList.Item>
      )}
      {card.card_last4 !== null && (
        <KeyValueList.Item label={t('parts.confirm.card')}>
          <Masked last4={card.card_last4} />
        </KeyValueList.Item>
      )}
      <KeyValueList.Item label={t('parts.confirm.reason')}>
        {t(`parts.disputeReasons.${card.reason}`)}
      </KeyValueList.Item>
      {card.expected_resolution_by !== null && (
        <KeyValueList.Item label={t('parts.confirm.expectedBy')}>
          <time dateTime={card.expected_resolution_by}>
            {format.day(card.expected_resolution_by)}
          </time>
        </KeyValueList.Item>
      )}
    </KeyValueList.Root>
  );
}

function CardDetails({
  card,
}: {
  readonly card: NonNullable<AssistantMessage['card_action_confirmation']>;
}) {
  const { t } = useTranslation();
  return (
    <KeyValueList.Root columns={2}>
      <KeyValueList.Item label={t('parts.confirm.card')}>
        <Masked last4={card.card_last4} />
      </KeyValueList.Item>
      <KeyValueList.Item label={t('parts.confirm.action')}>
        {t(`parts.cardActions.${card.action}`)}
      </KeyValueList.Item>
      {card.reason !== null && (
        <KeyValueList.Item label={t('parts.confirm.reason')}>
          {t(`parts.cardBlockReasons.${card.reason}`)}
        </KeyValueList.Item>
      )}
    </KeyValueList.Root>
  );
}

function CreditDetails({
  card,
}: {
  readonly card: NonNullable<AssistantMessage['credit_intake_confirmation']>;
}) {
  const { t } = useTranslation();
  return (
    <KeyValueList.Root columns={2}>
      <KeyValueList.Item label={t('parts.confirm.product')}>
        {t(`parts.creditTypes.${card.product_type}`)}{' '}
        <span className="font-mono text-fg-muted">{card.product_code}</span>
      </KeyValueList.Item>
      <KeyValueList.Item label={t('parts.confirm.amount')} numeric>
        <Amount value={card.requested_amount} />
      </KeyValueList.Item>
      <KeyValueList.Item label={t('parts.confirm.term')}>
        {t('parts.confirm.months', { count: card.requested_term_months })}
      </KeyValueList.Item>
      <KeyValueList.Item label={t('parts.confirm.purpose')}>
        {isPurpose(card.purpose) ? t(`parts.purposes.${card.purpose}`) : card.purpose}
      </KeyValueList.Item>
      {card.eligibility_outcome !== null && (
        <KeyValueList.Item label={t('parts.confirm.indication')}>
          {t(`parts.eligibilityOutcomes.${card.eligibility_outcome}`)}
        </KeyValueList.Item>
      )}
    </KeyValueList.Root>
  );
}

function CreditNote() {
  const { t } = useTranslation();
  return <p className="text-small text-fg-secondary">{t('parts.disclaimer')}</p>;
}
