import { useTranslation } from 'react-i18next';

import { useFormat } from '@/shared/i18n';
import { KeyValueList } from '@/shared/ui';

import { useMessage } from '../../model/message-context';
import { Amount } from './Amount';
import { Masked } from './Masked';
import { PartCard } from './PartCard';

/** Payment and transfer statuses, in words. The status is data about a record, so it never uses the verified style. */
export function Payments() {
  const { t } = useTranslation();
  const format = useFormat();
  const { message } = useMessage();
  if (message.payment_statuses.length === 0) {
    return null;
  }
  return (
    <ul className="flex flex-col gap-3" aria-label={t('parts.payments.title')}>
      {message.payment_statuses.map((payment) => (
        <li key={payment.transaction_ref}>
          <PartCard
            title={t(`parts.transactionTypes.${payment.transaction_type}`)}
            meta={<Masked last4={payment.masked_number.last4} />}
          >
            <KeyValueList.Root columns={2}>
              <KeyValueList.Item label={t('parts.payments.status')}>
                <span className="font-semibold">
                  {t(`parts.transactionStatuses.${payment.status}`)}
                </span>
              </KeyValueList.Item>
              <KeyValueList.Item label={t('parts.payments.amount')} numeric>
                <Amount value={payment.amount} />
              </KeyValueList.Item>
              <KeyValueList.Item label={t('parts.payments.date')}>
                <time dateTime={payment.occurred_on}>{format.day(payment.occurred_on)}</time>
              </KeyValueList.Item>
              {payment.payee_display !== null && (
                <KeyValueList.Item label={t('parts.payments.payee')}>
                  {payment.payee_display}
                </KeyValueList.Item>
              )}
            </KeyValueList.Root>
          </PartCard>
        </li>
      ))}
    </ul>
  );
}
