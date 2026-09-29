import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { errorMessageKey, errorRequestId, hasProblem } from '@/shared/api';
import { useFormat } from '@/shared/i18n';
import {
  Badge,
  Button,
  Card,
  DataTable,
  EmptyState,
  ErrorState,
  KeyValueList,
  ReceiptIcon,
  Skeleton,
  SkeletonGroup,
  Timeline,
} from '@/shared/ui';

import { useCreditApplication, useCreditApplications } from '../api/handoffs';
import { useInboxLabels } from './labels';

function Loading() {
  const { t } = useTranslation();
  return (
    <SkeletonGroup label={t('inbox.loading')}>
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
    </SkeletonGroup>
  );
}

/**
 * Credit intakes recorded for human review, read only. Each is a review item of its own (ADR 0021), never a
 * lending decision, and the policy behind it is synthetic.
 */
export function CreditApplicationList() {
  const { t } = useTranslation();
  const format = useFormat();
  const labels = useInboxLabels();
  const applications = useCreditApplications();
  if (applications.isPending) {
    return <Loading />;
  }
  if (applications.isError) {
    return (
      <ErrorState
        title={t('applications.error')}
        description={t(errorMessageKey(applications.error))}
        requestId={errorRequestId(applications.error)}
        action={
          <Button variant="secondary" onClick={() => void applications.refetch()}>
            {t('common.retry')}
          </Button>
        }
      />
    );
  }
  const rows = applications.data.applications;
  if (rows.length === 0) {
    return (
      <EmptyState
        icon={ReceiptIcon}
        title={t('applications.emptyTitle')}
        description={t('applications.emptyBody')}
      />
    );
  }
  return (
    <DataTable.Root caption={t('applications.tableCaption', { count: rows.length })}>
      <DataTable.Head>
        <tr>
          <DataTable.HeaderCell>{t('applications.columns.application')}</DataTable.HeaderCell>
          <DataTable.HeaderCell>{t('applications.columns.product')}</DataTable.HeaderCell>
          <DataTable.HeaderCell numeric>{t('applications.columns.amount')}</DataTable.HeaderCell>
          <DataTable.HeaderCell>{t('applications.columns.status')}</DataTable.HeaderCell>
          <DataTable.HeaderCell>{t('applications.columns.created')}</DataTable.HeaderCell>
        </tr>
      </DataTable.Head>
      <DataTable.Body>
        {rows.map((application) => (
          <DataTable.Row key={application.application_id}>
            <DataTable.Cell>
              <Link
                to={`/console/credit-applications/${application.application_id}`}
                className="font-mono font-semibold text-fg underline-offset-4 hover:underline"
              >
                {application.application_id}
              </Link>
            </DataTable.Cell>
            <DataTable.Cell className="font-mono">{application.product_code}</DataTable.Cell>
            <DataTable.Cell numeric>
              {format.money(application.requested_amount)}
              <span className="block text-caption text-fg-muted">
                {t('parts.confirm.months', { count: application.requested_term_months })}
              </span>
            </DataTable.Cell>
            <DataTable.Cell>{labels.code('application', application.status)}</DataTable.Cell>
            <DataTable.Cell className="whitespace-nowrap text-fg-secondary">
              <time dateTime={application.created_at}>
                {format.dateTime(application.created_at)}
              </time>
            </DataTable.Cell>
          </DataTable.Row>
        ))}
      </DataTable.Body>
    </DataTable.Root>
  );
}

/** One intake: what was requested, its links to the assessment and the conversation, and its status history. */
export function CreditApplicationDetail({ applicationId }: { readonly applicationId: string }) {
  const { t } = useTranslation();
  const format = useFormat();
  const labels = useInboxLabels();
  const application = useCreditApplication(applicationId);
  if (application.isPending) {
    return <Loading />;
  }
  if (application.isError) {
    return hasProblem(application.error, 'resource-not-found') ? (
      <EmptyState
        title={t('applications.notFoundTitle')}
        description={t('applications.notFoundBody')}
      />
    ) : (
      <ErrorState
        title={t('applications.error')}
        description={t(errorMessageKey(application.error))}
        requestId={errorRequestId(application.error)}
      />
    );
  }
  const view = application.data;
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-display text-heading font-semibold tracking-tight text-fg">
          <span className="font-mono">{view.application_id}</span>
        </h1>
        {view.synthetic_policy && <Badge>{t('applications.synthetic')}</Badge>}
        <Badge>{labels.code('application', view.status)}</Badge>
      </div>
      <p className="max-w-prose text-small text-fg-secondary">{t('applications.notADecision')}</p>
      <Card.Root aria-labelledby="application-request">
        <Card.Header title={<span id="application-request">{t('applications.request')}</span>} />
        <Card.Body>
          <KeyValueList.Root columns={3}>
            <KeyValueList.Item label={t('applications.columns.product')}>
              <span className="font-mono">{view.product_code}</span>
            </KeyValueList.Item>
            <KeyValueList.Item label={t('applications.columns.amount')} numeric>
              {format.money(view.requested_amount)}
            </KeyValueList.Item>
            <KeyValueList.Item label={t('parts.confirm.term')}>
              {t('parts.confirm.months', { count: view.requested_term_months })}
            </KeyValueList.Item>
            <KeyValueList.Item label={t('parts.confirm.purpose')}>
              <span className="font-mono">{view.purpose}</span>
            </KeyValueList.Item>
            <KeyValueList.Item label={t('applications.income')} numeric>
              {view.declared_monthly_income === null
                ? t('inbox.detail.none')
                : format.money(view.declared_monthly_income)}
            </KeyValueList.Item>
            <KeyValueList.Item label={t('applications.assessment')}>
              <span className="font-mono text-small break-all">
                {view.assessment_ref ?? t('inbox.detail.none')}
              </span>
            </KeyValueList.Item>
            <KeyValueList.Item label={t('applications.conversation')}>
              <span className="font-mono text-small break-all">
                {view.origin_conversation_id ?? t('inbox.detail.none')}
              </span>
            </KeyValueList.Item>
            <KeyValueList.Item label={t('applications.customer')}>
              <span className="font-mono text-small break-all">{view.customer_id}</span>
            </KeyValueList.Item>
          </KeyValueList.Root>
        </Card.Body>
      </Card.Root>
      <Card.Root aria-labelledby="application-history">
        <Card.Header title={<span id="application-history">{t('applications.history')}</span>} />
        <Card.Body>
          <Timeline.Root>
            <Timeline.Item
              title={labels.code('application', 'submitted')}
              meta={format.dateTime(view.created_at)}
            />
            {view.status_history.map((change) => (
              <Timeline.Item
                key={`${change.at}-${change.to_status}`}
                title={labels.code('application', change.to_status)}
                meta={format.dateTime(change.at)}
              >
                <span className="font-mono text-caption">{change.reason_code}</span>
              </Timeline.Item>
            ))}
          </Timeline.Root>
        </Card.Body>
      </Card.Root>
    </div>
  );
}
