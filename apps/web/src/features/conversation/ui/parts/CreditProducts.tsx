import { useTranslation } from 'react-i18next';

import { useFormat } from '@/shared/i18n';
import { Badge, KeyValueList } from '@/shared/ui';

import { useMessage } from '../../model/message-context';
import { isRequiredInformation } from '../../model/labels';
import { PartCard } from './PartCard';

/** Synthetic catalog entries: indicative ranges only, labeled as such. Never an offer. */
export function CreditProducts() {
  const { t } = useTranslation();
  const format = useFormat();
  const { message } = useMessage();
  if (message.credit_products.length === 0) {
    return null;
  }
  const rate = (value: string) => format.number(Number(value));
  return (
    <ul className="flex flex-col gap-3" aria-label={t('parts.products.title')}>
      {message.credit_products.map((product) => (
        <li key={product.product_code}>
          <PartCard
            title={
              <span className="flex flex-col">
                <span>
                  {product.display_name ?? t(`parts.creditTypes.${product.product_type}`)}
                </span>
                <span className="font-mono text-caption font-normal text-fg-muted">
                  {product.product_code}
                </span>
              </span>
            }
            meta={<Badge>{t('parts.products.synthetic')}</Badge>}
          >
            <KeyValueList.Root columns={3}>
              <KeyValueList.Item label={t('parts.products.amount')} numeric>
                {t('parts.products.amountRange', {
                  min: format.money(product.min_amount),
                  max: format.money(product.max_amount),
                })}
              </KeyValueList.Item>
              <KeyValueList.Item label={t('parts.products.term')}>
                {t('parts.products.termRange', {
                  min: product.min_term_months,
                  max: product.max_term_months,
                })}
              </KeyValueList.Item>
              <KeyValueList.Item label={t('parts.products.rate')}>
                {t('parts.products.rateRange', {
                  min: rate(product.min_annual_rate),
                  max: rate(product.max_annual_rate),
                })}
              </KeyValueList.Item>
            </KeyValueList.Root>
            {product.required_information.length > 0 && (
              <p className="text-small text-fg-secondary">
                {t('parts.products.required')}{' '}
                {product.required_information
                  .map((item) =>
                    isRequiredInformation(item) ? t(`parts.requiredInformation.${item}`) : item,
                  )
                  .join(', ')}
              </p>
            )}
            {!product.self_service_eligibility && (
              <p className="text-small text-fg-secondary">{t('parts.products.humanOnly')}</p>
            )}
            <p className="text-caption text-fg-muted">{t('parts.products.indicative')}</p>
          </PartCard>
        </li>
      ))}
    </ul>
  );
}
