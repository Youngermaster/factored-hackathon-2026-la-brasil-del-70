import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { SessionStatus, useSession } from '@/features/auth';
import { ChartIcon, ForwardIcon, InboxIcon, ReceiptIcon, TraceIcon, type Icon } from '@/shared/ui';

interface Destination {
  readonly to: string;
  readonly icon: Icon;
  readonly title:
    | 'layout.inbox'
    | 'layout.creditApplications'
    | 'layout.dashboard'
    | 'layout.evaluation'
    | 'layout.traces';
  readonly body:
    | 'console.inboxBody'
    | 'console.applicationsBody'
    | 'console.dashboardBody'
    | 'console.evaluationBody'
    | 'console.tracesBody';
}

const AGENT: readonly Destination[] = [
  { to: '/console/inbox', icon: InboxIcon, title: 'layout.inbox', body: 'console.inboxBody' },
  {
    to: '/console/credit-applications',
    icon: ReceiptIcon,
    title: 'layout.creditApplications',
    body: 'console.applicationsBody',
  },
];

const EVALUATOR: readonly Destination[] = [
  {
    to: '/console/dashboard',
    icon: ChartIcon,
    title: 'layout.dashboard',
    body: 'console.dashboardBody',
  },
  {
    to: '/console/evaluation',
    icon: ChartIcon,
    title: 'layout.evaluation',
    body: 'console.evaluationBody',
  },
  { to: '/console/traces', icon: TraceIcon, title: 'layout.traces', body: 'console.tracesBody' },
];

/** The console start for agents and evaluators: what the role handles, where to go, and the session. */
export function ConsoleOverviewPage() {
  const { t } = useTranslation();
  const session = useSession();
  const role = session.data?.role;
  const destinations = role === 'agent' ? AGENT : role === 'evaluator' ? EVALUATOR : [];
  return (
    <div className="flex max-w-4xl flex-col gap-8">
      <div className="flex flex-col gap-2">
        <h1 className="font-display text-heading font-semibold tracking-tight text-fg">
          {t('console.heading')}
        </h1>
        {role === 'agent' && (
          <p className="max-w-prose text-body text-fg-secondary">{t('console.agentBody')}</p>
        )}
        {role === 'evaluator' && (
          <p className="max-w-prose text-body text-fg-secondary">{t('console.evaluatorBody')}</p>
        )}
      </div>
      <ul className="grid grid-cols-1 gap-px overflow-hidden rounded-card border border-border bg-border sm:grid-cols-2">
        {destinations.map(({ to, icon: DestinationIcon, title, body }) => (
          <li key={to} className="bg-surface">
            <Link to={to} className="flex h-full gap-4 p-5 hover:bg-surface-hover">
              <DestinationIcon aria-hidden="true" size={24} className="mt-0.5 shrink-0 text-fg" />
              <span className="flex flex-col gap-1">
                <span className="flex items-center gap-1.5 text-body font-semibold text-fg">
                  {t(title)}
                  <ForwardIcon aria-hidden="true" size={16} />
                </span>
                <span className="text-small text-fg-secondary">{t(body)}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
      <SessionStatus />
    </div>
  );
}
