import { useTranslation } from 'react-i18next';
import { NavLink, Outlet } from 'react-router';

import { LogoutButton, RequireSession, useSession } from '@/features/auth';
import type { Schema } from '@/shared/api';
import { cx } from '@/shared/lib/cx';
import { ChartIcon, InboxIcon, OverviewIcon, ReceiptIcon, TraceIcon, type Icon } from '@/shared/ui';

import { Preferences } from './Preferences';
import { SkipLink } from './SkipLink';
import { useRouteFocus } from './use-route-focus';
import { Wordmark } from './Wordmark';

interface NavItem {
  readonly to: string;
  readonly label:
    | 'layout.overview'
    | 'layout.dashboard'
    | 'layout.inbox'
    | 'layout.creditApplications'
    | 'layout.evaluation'
    | 'layout.traces';
  readonly icon: Icon;
  /** Only the overview matches its path exactly; the others stay active on their detail pages. */
  readonly end?: boolean;
}

const OVERVIEW: NavItem = {
  to: '/console',
  label: 'layout.overview',
  icon: OverviewIcon,
  end: true,
};

/** Console destinations per role: agents work handoffs and credit review items; evaluators read results and records. */
const NAV: Record<Exclude<Schema<'Role'>, 'customer'>, readonly NavItem[]> = {
  agent: [
    OVERVIEW,
    { to: '/console/inbox', label: 'layout.inbox', icon: InboxIcon },
    { to: '/console/credit-applications', label: 'layout.creditApplications', icon: ReceiptIcon },
  ],
  evaluator: [
    OVERVIEW,
    { to: '/console/dashboard', label: 'layout.dashboard', icon: ChartIcon },
    { to: '/console/evaluation', label: 'layout.evaluation', icon: ChartIcon },
    { to: '/console/traces', label: 'layout.traces', icon: TraceIcon },
  ],
};

/**
 * The agent and evaluator surface: desktop-first and denser. A sidebar with the console destinations on wide
 * screens; on narrow screens the destinations sit in a row under the header.
 */
export function ConsoleLayout() {
  const { t } = useTranslation();
  const mainRef = useRouteFocus<HTMLElement>();
  const role = useSession().data?.role;
  const items = role === 'agent' || role === 'evaluator' ? NAV[role] : [OVERVIEW];
  const links = items.map(({ to, label, icon: ItemIcon, end = false }) => (
    <li key={to}>
      <NavLink
        to={to}
        end={end}
        className={({ isActive }) =>
          cx(
            'flex h-9 items-center gap-2 rounded-control px-3 text-small font-medium whitespace-nowrap',
            isActive
              ? 'bg-surface-sunken text-fg'
              : 'text-fg-secondary hover:bg-surface-hover hover:text-fg',
          )
        }
      >
        <ItemIcon aria-hidden="true" size={18} />
        {t(label)}
      </NavLink>
    </li>
  ));

  return (
    <RequireSession roles={['agent', 'evaluator']}>
      <div className="flex min-h-dvh flex-col bg-canvas">
        <SkipLink />
        <header className="sticky top-0 z-30 border-b border-border bg-surface">
          <div className="flex h-14 items-center justify-between gap-4 px-4 lg:px-6">
            <Wordmark to="/console" />
            <div className="flex items-center gap-1">
              <Preferences />
              <LogoutButton />
            </div>
          </div>
        </header>
        <div className="grid flex-1 grid-cols-1 lg:grid-cols-[14rem_minmax(0,1fr)]">
          {/* One navigation landmark: a row under the header on narrow screens, a sidebar on wide ones. */}
          <nav
            aria-label={t('layout.consoleNav')}
            className="border-b border-border bg-surface px-2 py-1 lg:border-r lg:border-b-0 lg:p-3"
          >
            <ul className="flex gap-1 overflow-x-auto lg:flex-col">{links}</ul>
          </nav>
          <main
            id="main"
            ref={mainRef}
            tabIndex={-1}
            className="min-w-0 px-4 py-6 outline-none lg:px-8 lg:py-8"
          >
            <Outlet />
          </main>
        </div>
      </div>
    </RequireSession>
  );
}
