import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router';

import { homeFor, LoginFlow, SessionNotice, type LoginReason } from '@/features/auth';
import { isDemoMode } from '@/shared/config';
import { safeNextPath } from '@/shared/lib/safe-next';

import { LoginAside } from './LoginAside';

function reasonOf(value: string | null): LoginReason | null {
  return value === 'expired' || value === 'signed-out' ? value : null;
}

/** Sign-in for every role. After the code, the person lands where they were going, or on their role's home. */
/** `header` is a slot: the app passes its public header (product name and preferences). */
export function LoginPage({ header }: { readonly header: ReactNode }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const reason = reasonOf(params.get('reason'));
  const next = params.get('next');

  return (
    <div className="flex min-h-dvh flex-col bg-canvas">
      {header}
      <main
        id="main"
        className="mx-auto grid w-full max-w-6xl flex-1 grid-cols-1 gap-12 px-4 py-10 sm:px-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)] lg:gap-16 lg:py-16"
      >
        <div className="flex max-w-xl flex-col gap-8">
          <div className="flex flex-col gap-3">
            <h1 className="font-display text-display font-semibold tracking-tight text-fg">
              {t('auth.title')}
            </h1>
            <p className="max-w-prose text-lead text-fg-secondary">{t('auth.intro')}</p>
            {isDemoMode() && <p className="text-small text-fg-muted">{t('app.demoModeHint')}</p>}
          </div>
          {reason !== null && <SessionNotice reason={reason} />}
          <LoginFlow
            onSignedIn={(session) => {
              void navigate(safeNextPath(next, homeFor(session.role)), { replace: true });
            }}
          />
        </div>
        <LoginAside />
      </main>
    </div>
  );
}
