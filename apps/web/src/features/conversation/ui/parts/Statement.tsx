import { useTranslation } from 'react-i18next';

import { useFormat } from '@/shared/i18n';
import { AsOfNote, DataTable } from '@/shared/ui';

import { useMessage } from '../../model/message-context';
import { Amount } from './Amount';
import { PartCard } from './PartCard';

/**
 * A statement summary: the period, totals with one row per currency (amounts in different currencies are never
 * added together), the counts the totals leave out, the listed lines, and the as-of instant.
 */
export function Statement() {
  const { t } = useTranslation();
  const format = useFormat();
  const { message } = useMessage();
  const statement = message.statement;
  if (statement === null || statement === undefined) {
    return null;
  }
  const { start, end } = statement.period.dates;
  return (
    <PartCard
      title={t('parts.statement.title')}
      meta={
        <p className="text-small text-fg-secondary">
          {t('parts.statement.period', { start: format.day(start), end: format.day(end) })}
        </p>
      }
    >
      <DataTable.Root caption={t('parts.statement.totals')}>
        <DataTable.Head>
          <tr>
            <DataTable.HeaderCell>{t('parts.statement.currency')}</DataTable.HeaderCell>
            <DataTable.HeaderCell numeric>{t('parts.statement.debits')}</DataTable.HeaderCell>
            <DataTable.HeaderCell numeric>{t('parts.statement.credits')}</DataTable.HeaderCell>
          </tr>
        </DataTable.Head>
        <DataTable.Body>
          {statement.totals.map((total) => (
            <DataTable.Row key={total.currency}>
              <DataTable.Cell className="font-mono">{total.currency}</DataTable.Cell>
              <DataTable.Cell numeric>
                <Amount value={total.debits} />
                <span className="block text-caption text-fg-muted">
                  {t('parts.statement.movements', { count: total.debit_count })}
                </span>
              </DataTable.Cell>
              <DataTable.Cell numeric>
                <Amount value={total.credits} />
                <span className="block text-caption text-fg-muted">
                  {t('parts.statement.movements', { count: total.credit_count })}
                </span>
              </DataTable.Cell>
            </DataTable.Row>
          ))}
        </DataTable.Body>
      </DataTable.Root>
      <p className="text-small text-fg-secondary">
        {t('parts.statement.counts', {
          total: statement.transaction_count,
          notSettled: statement.not_settled_count,
          unclassified: statement.unclassified_count,
        })}
      </p>
      {statement.lines.length > 0 && (
        <DataTable.Root caption={t('parts.statement.lines')}>
          <DataTable.Head>
            <tr>
              <DataTable.HeaderCell>{t('parts.statement.date')}</DataTable.HeaderCell>
              <DataTable.HeaderCell>{t('parts.statement.detail')}</DataTable.HeaderCell>
              <DataTable.HeaderCell>{t('parts.statement.status')}</DataTable.HeaderCell>
              <DataTable.HeaderCell numeric>{t('parts.statement.amount')}</DataTable.HeaderCell>
            </tr>
          </DataTable.Head>
          <DataTable.Body>
            {statement.lines.map((line) => (
              <DataTable.Row key={line.source}>
                <DataTable.Cell className="whitespace-nowrap">
                  <time dateTime={line.occurred_on}>{format.day(line.occurred_on)}</time>
                </DataTable.Cell>
                <DataTable.Cell>
                  {line.display_text ?? t(`parts.transactionTypes.${line.transaction_type}`)}
                  <span className="block text-caption text-fg-muted">
                    {t(`parts.directions.${line.direction}`)}
                  </span>
                </DataTable.Cell>
                <DataTable.Cell>{t(`parts.transactionStatuses.${line.status}`)}</DataTable.Cell>
                <DataTable.Cell numeric>
                  <Amount value={line.amount} />
                </DataTable.Cell>
              </DataTable.Row>
            ))}
          </DataTable.Body>
        </DataTable.Root>
      )}
      {statement.truncated && (
        <p className="text-small text-fg-muted">{t('parts.statement.truncated')}</p>
      )}
      <AsOfNote at={statement.as_of} />
    </PartCard>
  );
}
