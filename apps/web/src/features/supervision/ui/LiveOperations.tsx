import { useTranslation } from 'react-i18next';

import { errorMessageKey, errorRequestId } from '@/shared/api';
import {
  Badge,
  Button,
  ErrorState,
  KeyValueList,
  Skeleton,
  TextLink,
  type BadgeTone,
} from '@/shared/ui';

import { useHealthDetails, type HealthDetails } from '../api/supervision';
import { useEvidenceFormat } from './format';
import { useSupervisionLabels } from './labels';
import { Section } from './Section';

/** Where the observability profile serves the Grafana dashboards behind the same host (ADR 0036, ADR 0045). */
export const GRAFANA_PATH = '/grafana/';

const STATE_TONE: Record<HealthDetails['components'][string], BadgeTone> = {
  ok: 'decision',
  degraded: 'risk',
  unavailable: 'risk',
  disabled: 'neutral',
};

/**
 * The degradation level of the worker that answered `/health/details` (which answers 503 with the same body at L4),
 * each dependency's state, and the share of the daily model budget spent; live time series stay in Grafana.
 */
export function LiveOperations() {
  const { t } = useTranslation();
  const labels = useSupervisionLabels();
  const format = useEvidenceFormat();
  const health = useHealthDetails();
  let body;
  if (health.isPending) {
    body = <Skeleton className="h-32 w-full" />;
  } else if (health.isError) {
    body = (
      <ErrorState
        title={t('supervision.live.error')}
        description={t(errorMessageKey(health.error))}
        requestId={errorRequestId(health.error)}
        action={
          <Button variant="secondary" onClick={() => void health.refetch()}>
            {t('common.retry')}
          </Button>
        }
      />
    );
  } else {
    const details = health.data;
    const degraded = details.level !== 'L0';
    body = (
      <div className="flex flex-col gap-5 rounded-card border border-border bg-surface p-5">
        <KeyValueList.Root columns={3}>
          <KeyValueList.Item label={t('supervision.live.level')}>
            <Badge tone={degraded ? 'risk' : 'decision'}>{labels.level(details.level)}</Badge>
          </KeyValueList.Item>
          <KeyValueList.Item label={t('supervision.live.status')}>
            {labels.status(details.status)}
          </KeyValueList.Item>
          <KeyValueList.Item label={t('supervision.live.budget')} numeric>
            {format.percent(details.budget_used_ratio)}
          </KeyValueList.Item>
          <KeyValueList.Item label={t('supervision.live.templateOnly')}>
            {details.template_only ? t('supervision.live.yes') : t('supervision.live.no')}
          </KeyValueList.Item>
          <KeyValueList.Item label={t('supervision.live.reasons')}>
            {details.reasons.length === 0 ? (
              <span className="text-fg-muted">{t('supervision.live.noReasons')}</span>
            ) : (
              <span className="flex flex-wrap gap-1">
                {details.reasons.map((reason) => (
                  <Badge key={reason} tone="risk">
                    {labels.healthReason(reason)}
                  </Badge>
                ))}
              </span>
            )}
          </KeyValueList.Item>
        </KeyValueList.Root>
        <div className="flex flex-col gap-2">
          <h3 className="text-small font-semibold text-fg">
            {t('supervision.live.componentsCaption')}
          </h3>
          <ul className="flex flex-wrap gap-2">
            {Object.entries(details.components).map(([component, state]) => (
              <li
                key={component}
                className="flex items-center gap-2 rounded-control border border-border px-3 py-1.5 text-small text-fg"
              >
                {labels.healthComponent(component)}
                <Badge tone={STATE_TONE[state]}>{labels.healthState(state)}</Badge>
              </li>
            ))}
          </ul>
        </div>
        <p className="text-caption text-fg-muted">{t('supervision.live.perWorker')}</p>
      </div>
    );
  }
  return (
    <Section
      id="supervision-live"
      title={t('supervision.live.title')}
      intro={t('supervision.live.intro')}
      aside={
        <TextLink href={GRAFANA_PATH} external className="text-small">
          {t('supervision.live.grafana')}
        </TextLink>
      }
    >
      {body}
    </Section>
  );
}
