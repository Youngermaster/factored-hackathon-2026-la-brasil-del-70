import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, useLocation } from 'react-router';

import { errorMessageKey, errorRequestId, type Schema } from '@/shared/api';
import { Button, ErrorState, Skeleton, SkeletonGroup } from '@/shared/ui';

import { useSession } from '../api/session';
import { homeFor } from '../model/personas';

/**
 * Route guard by role through `GET /v1/auth/me`: no session goes to sign-in (keeping the destination), a role that
 * may not open this area goes to its own home.
 */
export function RequireSession({
  roles,
  children,
}: {
  readonly roles: readonly Schema<'Role'>[];
  readonly children: ReactNode;
}) {
  const { t } = useTranslation();
  const location = useLocation();
  const session = useSession();

  if (session.isPending) {
    return (
      <div className="mx-auto w-full max-w-3xl p-6">
        <SkeletonGroup>
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-full max-w-md" />
          <Skeleton className="h-40 w-full" />
        </SkeletonGroup>
      </div>
    );
  }

  if (session.isError) {
    return (
      <div className="mx-auto w-full max-w-3xl p-6">
        <ErrorState
          title={t(errorMessageKey(session.error))}
          requestId={errorRequestId(session.error)}
          action={
            <Button
              variant="secondary"
              onClick={() => {
                void session.refetch();
              }}
            >
              {t('common.retry')}
            </Button>
          }
        />
      </div>
    );
  }

  if (session.data === null) {
    const next = encodeURIComponent(`${location.pathname}${location.search}`);
    return <Navigate to={`/login?next=${next}`} replace />;
  }

  if (!roles.includes(session.data.role)) {
    return <Navigate to={homeFor(session.data.role)} replace />;
  }

  return children;
}
