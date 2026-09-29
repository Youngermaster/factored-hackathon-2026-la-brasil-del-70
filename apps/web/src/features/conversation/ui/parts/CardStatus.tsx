import { useTranslation } from 'react-i18next';

import { useFormat } from '@/shared/i18n';
import { KeyValueList } from '@/shared/ui';

import { useMessage } from '../../model/message-context';
import { Masked } from './Masked';
import { PartCard } from './PartCard';

/** Card status: type, masked number, status in words, and expiry. */
export function CardStatus() {
  const { t } = useTranslation();
  const format = useFormat();
  const { message } = useMessage();
  if (message.card_status.length === 0) {
    return null;
  }
  return (
    <ul className="flex flex-col gap-3" aria-label={t('parts.cards.title')}>
      {message.card_status.map((card) => (
        <li key={card.product_ref}>
          <PartCard
            title={t(`parts.productTypes.${card.card_type}`)}
            meta={<Masked last4={card.masked_number.last4} />}
          >
            <KeyValueList.Root columns={2}>
              <KeyValueList.Item label={t('parts.cards.status')}>
                <span className="font-semibold">{t(`parts.productStatuses.${card.status}`)}</span>
              </KeyValueList.Item>
              <KeyValueList.Item label={t('parts.cards.expires')}>
                {card.expires_on === null ? (
                  t('parts.cards.noExpiry')
                ) : (
                  <time dateTime={card.expires_on}>{format.day(card.expires_on)}</time>
                )}
              </KeyValueList.Item>
            </KeyValueList.Root>
          </PartCard>
        </li>
      ))}
    </ul>
  );
}
