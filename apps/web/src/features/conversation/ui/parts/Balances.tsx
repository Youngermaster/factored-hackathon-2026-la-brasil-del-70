import { useTranslation } from 'react-i18next';

import { AsOfNote, WarningIcon } from '@/shared/ui';

import { useMessage } from '../../model/message-context';
import { Amount } from './Amount';
import { Masked } from './Masked';
import { PartCard } from './PartCard';

/** One row per product: the balance, credit figures when the product has them, and its as-of instant, always. */
export function Balances() {
  const { t } = useTranslation();
  const { message } = useMessage();
  if (message.balances.length === 0) {
    return null;
  }
  return (
    <PartCard title={t('parts.balances.title')}>
      <ul className="flex flex-col divide-y divide-border">
        {message.balances.map((balance) => (
          <li key={balance.product_ref} className="flex flex-col gap-1.5 py-3 first:pt-0 last:pb-0">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <p className="text-small text-fg">
                <span className="font-semibold">
                  {t(`parts.productTypes.${balance.product_type}`)}
                </span>{' '}
                <span className="text-fg-secondary">
                  <Masked last4={balance.masked_number.last4} />
                </span>
              </p>
              <p className="flex items-baseline gap-2 text-small">
                <span className="text-fg-muted">{t('parts.balances.current')}</span>
                <Amount
                  value={balance.current_balance}
                  className="text-body font-semibold text-fg"
                />
              </p>
            </div>
            {(balance.available_credit !== null || balance.credit_limit !== null) && (
              <dl className="flex flex-wrap gap-x-6 gap-y-1 text-small">
                {balance.available_credit !== null && (
                  <div className="flex gap-2">
                    <dt className="text-fg-muted">{t('parts.balances.available')}</dt>
                    <dd>
                      <Amount value={balance.available_credit} />
                    </dd>
                  </div>
                )}
                {balance.credit_limit !== null && (
                  <div className="flex gap-2">
                    <dt className="text-fg-muted">{t('parts.balances.limit')}</dt>
                    <dd>
                      <Amount value={balance.credit_limit} />
                    </dd>
                  </div>
                )}
              </dl>
            )}
            {balance.over_limit && (
              <p className="flex items-center gap-1.5 text-small font-medium text-risk-text">
                <WarningIcon aria-hidden="true" size={16} />
                {t('parts.balances.overLimit')}
              </p>
            )}
            <AsOfNote at={balance.as_of} className="text-caption" />
          </li>
        ))}
      </ul>
    </PartCard>
  );
}
