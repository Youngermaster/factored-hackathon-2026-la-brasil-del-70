import { useTranslation } from 'react-i18next';

import { RateCell } from '@/features/eval-report';
import { Badge, DataTable } from '@/shared/ui';

import type { ModelCard, ModelInventory, PromotionDecision } from '../api/supervision';
import {
  cardGroups,
  HEADLINE,
  isServing,
  lowerIsBetter,
  metricNames,
  metricOf,
  type CardGroup,
} from '../model/evidence';
import { useEvidenceFormat } from './format';
import { IntervalPlot } from './IntervalPlot';
import { useSupervisionLabels } from './labels';
import { Section } from './Section';

/**
 * The published offline evidence per component: a dot-and-whisker plot of the headline metric and a table with every
 * metric and its interval, the served model marked; then the end-to-end promotion decisions that explain why the
 * baselines serve.
 */
export function OfflineEvidence({
  cards,
  promotions,
  inventory,
}: {
  readonly cards: readonly ModelCard[];
  readonly promotions: readonly PromotionDecision[];
  readonly inventory: ModelInventory;
}) {
  const { t } = useTranslation();
  const groups = cardGroups(cards);
  return (
    <>
      <Section
        id="supervision-offline"
        title={t('supervision.offline.title')}
        intro={t('supervision.offline.intro')}
        aside={<p className="text-caption text-fg-muted">{t('supervision.offline.kindHelp')}</p>}
      >
        {groups.length === 0 ? (
          <p className="text-small text-fg-muted">{t('supervision.offline.empty')}</p>
        ) : (
          <div className="flex flex-col gap-6">
            {groups.map((group) => (
              <CardGroupView key={group.key} group={group} inventory={inventory} />
            ))}
          </div>
        )}
      </Section>
      {promotions.length > 0 && (
        <Section
          id="supervision-promotion"
          title={t('supervision.promotion.title')}
          intro={t('supervision.promotion.intro')}
        >
          <div className="flex flex-col gap-6">
            {promotions.map((promotion) => (
              <PromotionView key={promotion.decision} promotion={promotion} />
            ))}
          </div>
        </Section>
      )}
    </>
  );
}

function CardGroupView({
  group,
  inventory,
}: {
  readonly group: CardGroup;
  readonly inventory: ModelInventory;
}) {
  const { t } = useTranslation();
  const labels = useSupervisionLabels();
  const format = useEvidenceFormat();
  const first = group.cards[0];
  if (first === undefined) return null;
  const title =
    group.use === null
      ? labels.component(group.component)
      : t('supervision.offline.groupUse', {
          component: labels.component(group.component),
          use: labels.use(group.use),
        });
  const headline = HEADLINE[group.component];
  const plotted = group.cards.flatMap((card) => {
    const metric = metricOf(card, headline);
    return metric?.unit !== 'ratio'
      ? []
      : [
          {
            label: card.model,
            value: metric.value,
            low: metric.low,
            high: metric.high,
            tone: card.role === 'default' ? ('decision' as const) : ('understanding' as const),
            serving: isServing(card, inventory),
          },
        ];
  });
  const kinds = [...new Set(group.cards.map((card) => card.kind))];
  return (
    <article className="flex flex-col gap-4 rounded-card border border-border bg-surface p-5">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-body font-semibold text-fg">{title}</h3>
        <span className="flex flex-wrap items-center gap-2">
          <span className="text-caption text-fg-muted">
            {t('supervision.offline.sample', {
              split: labels.split(first.split),
              count: format.number(first.sample_size),
              unit: labels.unit(first.sample_unit),
            })}
          </span>
          <Badge tone="neutral">{t('eval.measurement.offline')}</Badge>
          {kinds.includes('provisional') && (
            <Badge tone="neutral">{labels.cardKind('provisional')}</Badge>
          )}
        </span>
      </header>
      {plotted.length > 0 && <IntervalPlot metric={labels.metric(headline)} points={plotted} />}
      <MetricMatrix title={title} cards={group.cards} inventory={inventory} />
      <p className="text-caption text-fg-muted">
        {t('supervision.offline.provenance', {
          report: first.report,
          sha: first.git_sha,
          generated: format.dateTime(first.generated_at),
          source: first.source,
        })}
      </p>
    </article>
  );
}

function MetricMatrix({
  title,
  cards,
  inventory,
}: {
  readonly title: string;
  readonly cards: readonly ModelCard[];
  readonly inventory: ModelInventory;
}) {
  const { t } = useTranslation();
  const labels = useSupervisionLabels();
  const format = useEvidenceFormat();
  return (
    <DataTable.Root caption={t('supervision.offline.caption', { group: title })} captionHidden>
      <DataTable.Head>
        <tr>
          <DataTable.HeaderCell>{t('supervision.offline.model')}</DataTable.HeaderCell>
          {cards.map((card) => (
            <DataTable.HeaderCell key={card.model} numeric>
              <span className="flex flex-col items-end gap-1">
                <span className="font-mono text-caption font-semibold break-all text-fg">
                  {card.model}
                </span>
                <span className="flex flex-wrap justify-end gap-1">
                  <Badge tone={card.role === 'default' ? 'decision' : 'understanding'}>
                    {labels.role(card.role)}
                  </Badge>
                  {isServing(card, inventory) && (
                    <Badge tone="neutral">{t('supervision.offline.serving')}</Badge>
                  )}
                </span>
                {card.note !== null && (
                  <span className="text-caption font-normal text-fg-muted">
                    {labels.note(card.note)}
                  </span>
                )}
              </span>
            </DataTable.HeaderCell>
          ))}
        </tr>
      </DataTable.Head>
      <DataTable.Body>
        {metricNames(cards).map((name) => (
          <DataTable.Row key={name}>
            <th scope="row" className="px-4 py-3 text-left align-top font-medium text-fg">
              {labels.metric(name)}
              {lowerIsBetter(name) && (
                <span className="block text-caption font-normal text-fg-muted">
                  {t('supervision.offline.lowerBetter')}
                </span>
              )}
            </th>
            {cards.map((card) => {
              const metric = metricOf(card, name);
              return (
                <DataTable.Cell key={card.model} numeric>
                  {metric === undefined ? (
                    <span className="text-fg-muted">{t('eval.notDefined')}</span>
                  ) : (
                    <span className="flex flex-col items-end gap-0.5">
                      <span className="font-semibold text-fg">{format.decimal(metric.value)}</span>
                      {metric.low !== null && metric.high !== null && (
                        <span className="text-caption text-fg-muted">
                          {t('supervision.offline.interval', {
                            low: format.decimal(metric.low),
                            high: format.decimal(metric.high),
                          })}
                        </span>
                      )}
                    </span>
                  )}
                </DataTable.Cell>
              );
            })}
          </DataTable.Row>
        ))}
      </DataTable.Body>
    </DataTable.Root>
  );
}

function PromotionView({ promotion }: { readonly promotion: PromotionDecision }) {
  const { t } = useTranslation();
  const labels = useSupervisionLabels();
  const decision = labels.decision(promotion.decision);
  const optional = (metric: { count: number; denominator: number } | null) =>
    metric === null ? (
      <span className="text-fg-muted">{t('eval.notDefined')}</span>
    ) : (
      <RateCell metric={metric} counts />
    );
  return (
    <article className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <span className="flex flex-wrap items-center gap-2">
          <h3 className="text-body font-semibold text-fg">{decision}</h3>
          <Badge tone="understanding">{t(`eval.measurement.${promotion.measurement}`)}</Badge>
        </span>
        <p className="text-small text-fg">
          {t('supervision.promotion.verdict', {
            outcome: labels.outcome(promotion.outcome),
            reason: labels.promotionReason(promotion.reason),
          })}
        </p>
        <p className="text-caption text-fg-muted">
          {t('supervision.promotion.meta', {
            split: labels.split(promotion.split),
            model: promotion.language_model,
            session: promotion.session,
            source: promotion.source,
          })}
        </p>
      </div>
      <DataTable.Root caption={t('supervision.promotion.caption', { decision })} captionHidden>
        <DataTable.Head>
          <tr>
            <DataTable.HeaderCell>{t('supervision.promotion.configuration')}</DataTable.HeaderCell>
            <DataTable.HeaderCell>{t('supervision.promotion.status')}</DataTable.HeaderCell>
            <DataTable.HeaderCell numeric>
              {t('eval.rows.safe_automated_resolution')}
            </DataTable.HeaderCell>
            <DataTable.HeaderCell numeric>{t('eval.rows.unsafe_outcomes')}</DataTable.HeaderCell>
            <DataTable.HeaderCell numeric>
              {t('supervision.promotion.routing')}
            </DataTable.HeaderCell>
            <DataTable.HeaderCell numeric>
              {t('eval.rows.escalation_unnecessary')}
            </DataTable.HeaderCell>
            <DataTable.HeaderCell numeric>{t('eval.rows.escalation_missed')}</DataTable.HeaderCell>
          </tr>
        </DataTable.Head>
        <DataTable.Body>
          {promotion.rows.map((row) => (
            <DataTable.Row key={row.models.join('+')}>
              <th scope="row" className="px-4 py-3 text-left align-top font-normal">
                <span className="flex flex-col gap-0.5">
                  {row.models.map((model) => (
                    <span key={model} className="font-mono text-caption text-fg">
                      {model}
                    </span>
                  ))}
                  {row.run_id !== null && (
                    <span className="text-caption text-fg-muted">
                      {row.git_sha === null ? row.run_id : `${row.run_id}, ${row.git_sha}`}
                    </span>
                  )}
                </span>
              </th>
              <DataTable.Cell>
                {row.served ? (
                  <Badge tone="decision">{t('supervision.promotion.served')}</Badge>
                ) : (
                  <Badge tone="neutral">{t('supervision.promotion.notServed')}</Badge>
                )}
              </DataTable.Cell>
              <DataTable.Cell numeric>
                <RateCell metric={row.safe_automated_resolution} />
              </DataTable.Cell>
              <DataTable.Cell numeric>
                <RateCell metric={row.unsafe_outcomes} counts />
              </DataTable.Cell>
              <DataTable.Cell numeric>{optional(row.routing_correct)}</DataTable.Cell>
              <DataTable.Cell numeric>{optional(row.escalation_unnecessary)}</DataTable.Cell>
              <DataTable.Cell numeric>{optional(row.escalation_missed)}</DataTable.Cell>
            </DataTable.Row>
          ))}
        </DataTable.Body>
      </DataTable.Root>
    </article>
  );
}
